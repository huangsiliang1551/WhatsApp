import asyncio
import signal
import time
from datetime import UTC, datetime, timedelta

import structlog

from app.core.settings import get_settings
from app.db import models as db_models
from app.db.models import Conversation, H5Site, H5SiteConfig, utc_now
from app.db.session import SessionLocal
from app.providers.queue import get_queue_provider
from app.schemas.queue import QueueJob, QueueName
from app.services.ai_queue_processor import process_ai_generation_job
from app.services.queue_service import QueueService
from app.services.runtime_state import RuntimeStateStore
from app.services.task_scheduler import TaskScheduler
from app.services.uptime_service import UptimeService
from app.services.data_retention_service import DataRetentionService
from app.services.worker_health import update_worker_health

logger = structlog.get_logger()

RUNNING = True
PROCESSED_COUNT = 0
FAILED_COUNT = 0
CONSECUTIVE_FAILURES = 0
MAX_CONSECUTIVE_FAILURES = 10
LAST_PROCESSED_AT: str | None = None
PAUSED = False


def stop_worker(*_: object) -> None:
    global RUNNING
    RUNNING = False


def get_worker_health() -> dict[str, object]:
    settings = get_settings()
    queue_service = QueueService(settings)
    stats = queue_service.get_stats()
    total_queued = sum(qs.queued for qs in stats.queues)
    return {
        "is_running": RUNNING and not PAUSED,
        "last_processed_at": LAST_PROCESSED_AT,
        "processed_count": PROCESSED_COUNT,
        "failed_count": FAILED_COUNT,
        "consecutive_failures": CONSECUTIVE_FAILURES,
        "is_paused": PAUSED,
        "queue_depth": total_queued,
    }


async def _report_health(settings) -> None:
    try:
        await update_worker_health(
            settings,
            processed_count=PROCESSED_COUNT,
            failed_count=FAILED_COUNT,
            consecutive_failures=CONSECUTIVE_FAILURES,
            is_paused=PAUSED,
            is_running=RUNNING,
        )
    except Exception:
        logger.warning("worker_health_update_failed", exc_info=True)


async def process_reserved_job(
    queue_name: QueueName,
    queue_service: QueueService,
    runtime_state: RuntimeStateStore | None = None,
) -> QueueJob | None:
    global PROCESSED_COUNT, FAILED_COUNT, CONSECUTIVE_FAILURES, PAUSED, LAST_PROCESSED_AT

    if PAUSED:
        return None

    reserved = queue_service.reserve_next_job(queue_name)
    if reserved is None:
        return None

    settings = get_settings()
    try:
        if queue_name == "ai_generation":
            payload = dict(reserved.job.payload)
            job_id = getattr(reserved.job, "job_id", None)
            if job_id is not None:
                payload["job_id"] = job_id

            if runtime_state is None:
                result = await process_ai_generation_job(payload, settings)
            else:
                result = await process_ai_generation_job(
                    payload,
                    settings,
                    runtime_state=runtime_state,
                )
        else:
            raise ValueError(f"Unsupported queue '{queue_name}'.")

        PROCESSED_COUNT += 1
        CONSECUTIVE_FAILURES = 0
        LAST_PROCESSED_AT = datetime.now(UTC).isoformat()

        return queue_service.mark_completed(reserved.job, result=result)
    except Exception as exc:
        FAILED_COUNT += 1
        CONSECUTIVE_FAILURES += 1
        LAST_PROCESSED_AT = datetime.now(UTC).isoformat()

        logger.warning(
            "worker_job_failed",
            queue=queue_name,
            job_id=getattr(reserved.job, "job_id", "unknown"),
            error=str(exc),
            consecutive_failures=CONSECUTIVE_FAILURES,
        )

        if CONSECUTIVE_FAILURES >= MAX_CONSECUTIVE_FAILURES and not PAUSED:
            PAUSED = True
            logger.error(
                "worker_paused_due_to_consecutive_failures",
                consecutive_failures=CONSECUTIVE_FAILURES,
                max_allowed=MAX_CONSECUTIVE_FAILURES,
            )

        return queue_service.mark_failed(reserved, error=str(exc))


async def run_worker() -> None:
    settings = get_settings()
    queue_service = QueueService(settings)
    idle_backoff = settings.queue_poll_timeout_seconds
    health_report_interval = 5
    last_health_report = 0.0

    logger.info("worker_started", queue_poll_timeout=idle_backoff, sleeping_scan_interval=settings.sleeping_scan_interval_seconds)

    async def _ai_loop():
        nonlocal last_health_report
        while RUNNING:
            try:
                job = await process_reserved_job("ai_generation", queue_service)
                if job is None:
                    await asyncio.sleep(idle_backoff)

                now = time.monotonic()
                if now - last_health_report >= health_report_interval:
                    await _report_health(settings)
                    last_health_report = now
            except Exception as exc:
                logger.error("worker_loop_error", error=str(exc))
                await asyncio.sleep(idle_backoff)

    await asyncio.gather(_ai_loop(), sleeping_scanner(settings), _marketing_scheduler(), uptime_monitor_loop(), data_retention_loop(), health_check_loop(settings), backup_schedule_loop(settings), monthly_billing_loop(), daily_reconciliation_loop(), quota_warning_loop())


async def _marketing_scheduler():
    """Run the marketing task scheduler loop (delayed tasks, scheduled push, expiry)."""
    settings = get_settings()
    from app.providers.queue import get_queue_provider

    provider = get_queue_provider(settings)
    # If provider has a raw redis client, use it; otherwise skip scheduler
    redis_client = getattr(provider, "_redis", None) or getattr(provider, "redis", None)
    if redis_client is None:
        # Try to get redis via settings
        try:
            import redis.asyncio as aioredis

            redis_client = aioredis.from_url(settings.redis_url or "redis://localhost:6379/0")
        except Exception as exc:
            logger.warning("marketing_scheduler_redis_unavailable", error=str(exc))
            return
    scheduler = TaskScheduler(redis_client)
    await scheduler.run_scheduler_loop()


async def sleeping_scanner(settings) -> None:
    """Periodically scan for conversations that should be marked as sleeping."""
    interval = settings.sleeping_scan_interval_seconds
    threshold_hours = settings.sleeping_threshold_hours
    logger.info("sleeping_scanner_started", interval_seconds=interval, threshold_hours=threshold_hours)
    while RUNNING:
        await asyncio.sleep(interval)
        try:
            db = SessionLocal()
            try:
                threshold = utc_now() - timedelta(hours=threshold_hours)
                # Batch-scan conversations: is_sleeping=False, status=open, last_customer_message_at < threshold
                batch_size = 200
                offset = 0
                total_marked = 0
                while True:
                    stmt = (
                        db.query(Conversation)
                        .filter(
                            Conversation.is_sleeping.is_(False),
                            Conversation.status == "open",
                            Conversation.last_customer_message_at.isnot(None),
                            Conversation.last_customer_message_at < threshold,
                        )
                        .order_by(Conversation.account_id)
                        .offset(offset)
                        .limit(batch_size)
                    )
                    conversations = stmt.all()
                    if not conversations:
                        break
                    for conv in conversations:
                        conv.is_sleeping = True
                        # Mark messages older than threshold as cold
                        db.execute(
                            db.query(db_models.Message)
                            .filter(
                                db_models.Message.conversation_id == conv.id,
                                db_models.Message.is_cold.is_(False),
                                db_models.Message.created_at < threshold,
                            )
                            .update({"is_cold": True}, synchronize_session=False)
                        )
                        db.add(conv)
                    db.commit()
                    total_marked += len(conversations)
                    offset += batch_size
                if total_marked > 0:
                    logger.info("sleeping_scanner_marked", count=total_marked, threshold_utc=threshold.isoformat())
            finally:
                db.close()
        except Exception as exc:
            logger.error("sleeping_scanner_error", error=str(exc))


async def uptime_monitor_loop() -> None:
    """Every 5 minutes, check all active H5 sites for availability."""
    logger.info("uptime_monitor_started", interval_seconds=300)
    while RUNNING:
        await asyncio.sleep(300)
        try:
            db = SessionLocal()
            try:
                sites = db.scalars(
                    select(H5Site).where(H5Site.status == "active")
                ).all()
                svc = UptimeService(db)
                for site in sites:
                    config = db.scalar(
                        select(H5SiteConfig).where(H5SiteConfig.site_id == site.id)
                    )
                    if config and config.domain:
                        await svc.check_site(site, config)
                logger.info("uptime_monitor_cycle", sites_checked=len(sites))
            finally:
                db.close()
        except Exception as exc:
            logger.error("uptime_monitor_error", error=str(exc))


async def data_retention_loop() -> None:
    """Every minute, check if it's 3 AM and run data retention cleanup."""
    logger.info("data_retention_loop_started")
    while RUNNING:
        await asyncio.sleep(60)
        from datetime import datetime
        now = datetime.now()
        if now.hour == 3 and now.minute == 0:
            try:
                db = SessionLocal()
                try:
                    svc = DataRetentionService(db)
                    msg_count = svc.cleanup_old_messages(days=90)
                    log_count = svc.cleanup_old_logs(days=90)
                    logger.info(
                        "data_retention_completed",
                        messages=msg_count,
                        logs=log_count,
                    )
                finally:
                    db.close()
            except Exception as exc:
                logger.error("data_retention_error", error=str(exc))


def main() -> None:
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)

    logger.info("worker_main_started")
    asyncio.run(run_worker())

    # Graceful shutdown: re-queue any in-flight (processing) tasks
    _requeue_inflight_tasks()

async def backup_schedule_loop(settings) -> None:
    """Check every 60 seconds if it's 3:00 AM, then run auto backup."""
    logger.info("backup_schedule_loop_started")
    last_backup_date = ""
    while RUNNING:
        await asyncio.sleep(60)
        from datetime import datetime as bdt
        now = bdt.now()
        today_str = now.strftime("%Y-%m-%d")
        if now.hour == 3 and 0 <= now.minute < 2 and today_str != last_backup_date:
            last_backup_date = today_str
            try:
                from app.db.session import SessionLocal as BSession
                from app.services.backup_service import BackupService
                db = BSession()
                try:
                    svc = BackupService(db, settings)
                    record = await svc.schedule_auto_backup()
                    logger.info("auto_backup_completed", filename=record.filename, status=record.status)
                finally:
                    db.close()
            except Exception as exc:
                logger.error("auto_backup_failed", error=str(exc))


async def health_check_loop(settings) -> None:
    """Run health checks every 60 minutes."""
    interval = (settings.health_check_interval_minutes or 60) * 60
    logger.info("health_check_loop_started", interval_seconds=interval)
    while RUNNING:
        await asyncio.sleep(interval)
        try:
            from app.db.session import SessionLocal as HCSession
            from app.services.health_check_service import HealthCheckService
            db = HCSession()
            try:
                svc = HealthCheckService(db, settings)
                results = await svc.check_all()
                logger.info("health_check_cycle_completed", count=len(results))
            finally:
                db.close()
        except Exception as exc:
            logger.error("health_check_loop_error", error=str(exc))


async def monthly_billing_loop() -> None:
    """On 1st of each month at 00:00, generate monthly bills for all agencies."""
    logger.info("monthly_billing_loop_started")
    last_run_date = ""
    while RUNNING:
        await asyncio.sleep(60)
        from datetime import datetime as bdt
        now = bdt.now()
        today_str = now.strftime("%Y-%m-%d")
        if now.day == 1 and now.hour == 0 and now.minute == 0 and today_str != last_run_date:
            last_run_date = today_str
            prev_month = now.replace(day=1) - __import__("datetime").timedelta(days=1)
            month = prev_month.strftime("%Y-%m")
            try:
                from app.db.session import SessionLocal as BSession
                from app.services.ai_usage_service import AiUsageService
                from app.db.models import Agency
                db = BSession()
                try:
                    agencies = db.execute(select(Agency)).scalars().all()
                    svc = AiUsageService(db)
                    for agency in agencies:
                        try:
                            svc.generate_monthly_bill(agency.id, month)
                            logger.info("monthly_bill_generated", agency_id=agency.id, month=month)
                        except Exception as bill_err:
                            logger.warning("monthly_bill_failed", agency_id=agency.id, error=str(bill_err))
                    db.commit()
                    logger.info("monthly_billing_completed", agency_count=len(agencies), month=month)
                finally:
                    db.close()
            except Exception as exc:
                logger.error("monthly_billing_loop_error", error=str(exc))


async def daily_reconciliation_loop() -> None:
    """At 00:00 daily, auto-reconcile previous day's payment records."""
    logger.info("daily_reconciliation_loop_started")
    last_run_date = ""
    while RUNNING:
        await asyncio.sleep(60)
        from datetime import datetime as bdt, timedelta
        now = bdt.now()
        today_str = now.strftime("%Y-%m-%d")
        if now.hour == 0 and now.minute == 0 and today_str != last_run_date:
            last_run_date = today_str
            prev_date = (now - timedelta(days=1)).date()
            try:
                from app.db.session import SessionLocal as RSession
                from app.services.payment_reconciliation_service import PaymentReconciliationService
                from app.db.models import PaymentChannel
                db = RSession()
                try:
                    channels = db.execute(select(PaymentChannel)).scalars().all()
                    svc = PaymentReconciliationService(db)
                    for ch in channels:
                        try:
                            rec = svc.auto_reconcile(ch.id, prev_date)
                            logger.info("daily_reconciliation_done", channel_id=ch.id, date=str(prev_date), status=rec.status)
                        except Exception as rec_err:
                            logger.warning("daily_reconciliation_failed", channel_id=ch.id, error=str(rec_err))
                    db.commit()
                finally:
                    db.close()
            except Exception as exc:
                logger.error("daily_reconciliation_loop_error", error=str(exc))


async def quota_warning_loop() -> None:
    """Every 60 minutes, check AI usage quota warnings and send notifications."""
    logger.info("quota_warning_loop_started")
    while RUNNING:
        await asyncio.sleep(3600)
        try:
            from app.db.session import SessionLocal as QSession
            from app.services.ai_usage_service import AiUsageService
            from app.db.models import AgencyFreeQuota
            db = QSession()
            try:
                svc = AiUsageService(db)
                agencies = db.execute(select(AgencyFreeQuota.agency_id).distinct()).scalars().all()
                for aid in agencies:
                    try:
                        warning = svc.check_quota_warning(aid)
                        if warning and warning.get("level") == "critical":
                            from app.services.notification_service import NotificationService
                            notif_svc = NotificationService(db)
                            notif_svc.create_notification(
                                account_id=aid,
                                type="alert",
                                category="billing",
                                title="AI 用量超额警告",
                                message=f"代理商 {aid[:12]}... AI 用量已达 {warning.get('ai_usage_ratio', 0)*100}%，请及时充值。",
                                severity="warning",
                            )
                    except Exception as w_err:
                        logger.warning("quota_warning_check_failed", agency_id=aid, error=str(w_err))
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.error("quota_warning_loop_error", error=str(exc))


def _requeue_inflight_tasks() -> None:
    """Re-queue any in-flight (processing) tasks back to the pending queue on shutdown."""
    try:
        settings = get_settings()
        provider = get_queue_provider(settings)
        all_jobs = provider.list_jobs()
        requeued = 0
        for job in all_jobs:
            if job.status == "processing":
                requeued_job = job.model_copy(
                    update={
                        "status": "queued",
                        "updated_at": utc_now().isoformat(),
                    }
                )
                provider.requeue(job.queue, requeued_job)
                requeued += 1
        if requeued:
            logger.info("worker_requeued_inflight_tasks", count=requeued)
    except Exception:
        logger.warning("worker_requeue_failed", exc_info=True)


if __name__ == "__main__":
    main()
