from app.core.metrics import queue_jobs_current, queue_jobs_total
from app.core.settings import Settings
from app.providers.queue import ReservedQueueJob, get_queue_provider
from app.providers.queue.base import QueueProvider
from app.schemas.queue import QueueEnqueueResult, QueueJob, QueueName, QueueStatsItem, QueueStatsResponse

QUEUE_NAMES: tuple[QueueName, ...] = ("ai_generation",)


class QueueService:
    def __init__(
        self,
        settings: Settings,
        provider: QueueProvider | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider or get_queue_provider(settings)

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    def enqueue_ai_generation(self, payload: dict[str, object]) -> QueueEnqueueResult:
        job = self._provider.enqueue(
            queue_name="ai_generation",
            payload=payload,
            max_retries=self._settings.queue_max_retries,
        )
        queue_jobs_total.labels(queue="ai_generation", status="queued").inc()
        self._update_gauges()
        return QueueEnqueueResult(job_id=job.job_id, queue=job.queue, status=job.status)

    def reserve_next_job(self, queue_name: QueueName) -> ReservedQueueJob | None:
        reserved = self._provider.reserve(
            queue_name=queue_name,
            timeout_seconds=self._settings.queue_poll_timeout_seconds,
        )
        if reserved is not None:
            self._update_gauges()
        return reserved

    def mark_completed(self, job: QueueJob, result: dict[str, object]) -> QueueJob:
        from app.db.models import utc_now

        updated = job.model_copy(
            update={
                "status": "completed",
                "result": result,
                "error": None,
                "completed_at": utc_now().isoformat(),
                "updated_at": utc_now().isoformat(),
            }
        )
        self._provider.save_job(updated)
        queue_jobs_total.labels(queue=updated.queue, status="completed").inc()
        self._update_gauges()
        return updated

    def mark_failed(self, reserved: ReservedQueueJob, error: str) -> QueueJob:
        from app.db.models import utc_now

        job = reserved.job
        can_retry = job.retry_count < job.max_retries
        next_status = "queued" if can_retry else "dead_letter"
        updated = job.model_copy(
            update={
                "status": next_status,
                "retry_count": job.retry_count + 1 if can_retry else job.retry_count,
                "error": error,
                "error_history": [*job.error_history, error],
                "failed_at": utc_now().isoformat() if not can_retry else None,
                "updated_at": utc_now().isoformat(),
            }
        )
        if can_retry:
            self._provider.requeue(reserved.queue, updated)
            queue_jobs_total.labels(queue=updated.queue, status="retried").inc()
        else:
            self._provider.move_to_dead_letter(reserved.queue, updated)
            queue_jobs_total.labels(queue=updated.queue, status="dead_letter").inc()
        self._update_gauges()
        return updated

    def get_job(self, job_id: str) -> QueueJob | None:
        return self._provider.get_job(job_id)

    def list_dead_letter_jobs(self, queue_name: QueueName | None = None) -> list[QueueJob]:
        return self._provider.list_dead_letter_jobs(queue_name=queue_name)

    def requeue_dead_letter(self, job_id: str) -> QueueJob | None:
        updated = self._provider.requeue_dead_letter(job_id)
        if updated is not None:
            queue_jobs_total.labels(queue=updated.queue, status="requeued_dead_letter").inc()
            self._update_gauges()
        return updated

    def requeue_all_dead_letters(self, queue_name: QueueName | None = None) -> int:
        dead_letter_jobs = self.list_dead_letter_jobs(queue_name=queue_name)
        count = 0
        for job in dead_letter_jobs:
            updated = self._provider.requeue_dead_letter(job.job_id)
            if updated is not None:
                queue_jobs_total.labels(queue=updated.queue, status="requeued_dead_letter").inc()
                count += 1
        if count > 0:
            self._update_gauges()
        return count

    def reset(self) -> None:
        self._provider.reset()

    def get_stats(self) -> QueueStatsResponse:
        jobs = self._provider.list_jobs()
        dead_letter_jobs = self._provider.list_dead_letter_jobs()
        grouped: dict[QueueName, dict[str, int]] = {
            queue_name: {
                "queued": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "retried_total": 0,
            }
            for queue_name in QUEUE_NAMES
        }
        for job in jobs:
            if job.status != "dead_letter":
                grouped[job.queue][job.status] += 1
            grouped[job.queue]["retried_total"] += job.retry_count
        # Count dead_letter jobs separately
        dead_letter_count = len(dead_letter_jobs)
        stats = QueueStatsResponse(
            queues=[
                QueueStatsItem(queue=queue_name, **grouped[queue_name])
                for queue_name in QUEUE_NAMES
            ],
            recent_failed_jobs=sorted(
                [job for job in jobs if job.status == "failed"],
                key=lambda job: job.failed_at or job.updated_at,
                reverse=True,
            )[:10],
            dead_letter_count=dead_letter_count,
        )
        self._update_gauges(stats)
        return stats

    def _update_gauges(self, stats: QueueStatsResponse | None = None) -> None:
        effective_stats = stats or self.get_stats()
        for queue_stat in effective_stats.queues:
            queue_jobs_current.labels(queue=queue_stat.queue, status="queued").set(queue_stat.queued)
            queue_jobs_current.labels(queue=queue_stat.queue, status="processing").set(queue_stat.processing)
            queue_jobs_current.labels(queue=queue_stat.queue, status="completed").set(queue_stat.completed)
            queue_jobs_current.labels(queue=queue_stat.queue, status="failed").set(queue_stat.failed)
