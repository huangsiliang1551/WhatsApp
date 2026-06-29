import importlib
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any, cast

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.routes.admin_auth import router as admin_auth_router
from app.api.routes.agency import router as agency_router
from app.api.routes.agent_auth import router as agent_auth_router
from app.api.routes.agent_auth import unified_router as unified_auth_router
from app.api.routes.agent_dashboard import router as agent_dashboard_router
from app.api.routes.agent_audit import router as agent_audit_router
from app.api.routes.agents import router as agents_router
from app.api.routes.ai_providers import router as ai_providers_router
from app.api.routes.client_errors import router as client_errors_router
from app.api.routes.conversation_notes import router as conversation_notes_router
from app.api.routes.conversation_poll import router as conversation_poll_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.customers import router as customers_router
from app.api.routes.canned_responses import router as canned_responses_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.deploy_history import router as deploy_history_router
from app.api.routes.dev import router as dev_router
from app.api.routes.domain_verification import router as domain_verification_router
from app.api.routes.ecommerce import router as ecommerce_router
from app.api.routes.exports import router as exports_router
from app.api.routes.health import router as health_router
from app.api.routes.h5 import router as h5_router
from app.api.routes.h5_auth import router as h5_auth_router
from app.api.routes.h5_deploy import router as h5_deploy_router
from app.api.routes.h5_languages import router as h5_languages_router
from app.api.routes.h5_member_commerce import router as h5_member_commerce_router
from app.api.routes.h5_member_fragments import router as h5_member_fragments_router
from app.api.routes.h5_member_messages import router as h5_member_messages_router
from app.api.routes.h5_member_verification import router as h5_member_verification_router
from app.api.routes.h5_member_whatsapp_binding import router as h5_member_whatsapp_binding_router
from app.api.routes.h5_translations import router as h5_translations_router
from app.api.routes.h5_site_analytics import router as h5_site_analytics_router
from app.api.routes.h5_templates import router as h5_templates_router
from app.api.routes.invites import router as invites_router
from app.api.routes.marketing_stats import router as marketing_stats_router
from app.api.routes.media_assets import router as media_assets_router
from app.api.routes.meta_callbacks import router as meta_callbacks_router
from app.api.routes.meta_accounts import router as meta_accounts_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.platform import router as platform_router
from app.api.routes.platform_member_whatsapp_bindings import (
    router as platform_member_whatsapp_bindings_router,
)
from app.api.routes.platform_member_verifications import router as platform_member_verifications_router
from app.api.routes.platform_withdrawals import router as platform_withdrawals_router
from app.api.routes.product_packages import router as product_packages_router
from app.api.routes.products import router as products_router
from app.api.routes.queue import router as queue_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.search import router as search_router
from app.api.routes.sign_in import router as sign_in_router
from app.api.routes.site_permissions import router as site_permissions_router
from app.api.routes.site_waba import router as site_waba_router
from app.api.routes.task_instances import router as task_instances_router
from app.api.routes.task_rules import router as task_rules_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.tickets import router as tickets_router
from app.api.routes.translation_providers import router as translation_providers_router
from app.api.routes.templates import router as templates_router
from app.api.routes.whatsapp_analytics import router as whatsapp_analytics_router
from app.api.routes.waba_assignment import router as waba_assignment_router
from app.api.routes.webhooks import router as webhooks_router
from app.api.routes.performance import router as performance_router
from app.api.routes.permissions_api import router as permissions_router
from app.api.routes.worker_health import router as worker_health_router
from app.api.routes.workspace_auth import router as workspace_auth_router
from app.api.routes.reports import router as reports_router
from app.api.routes.operations import router as operations_router
from app.api.routes.backups import router as backups_router
from app.api.routes.batch import router as batch_router
from app.api.routes.knowledge_base import router as knowledge_base_router
from app.api.routes.customer_profile import router as customer_profile_router
from app.api.routes.template_preview import router as template_preview_router
from app.api.routes.api_stats import router as api_stats_router
from app.api.routes.rate_limits import router as rate_limits_router
from app.api.routes.health_check_routes import router as health_check_routes_router
from app.api.routes.ai_chat_config import router as ai_chat_config_router
from app.api.routes.ai_billing import router as ai_billing_router
from app.api.routes.exchange_rates import router as exchange_rates_router
from app.api.routes.finance_channels import router as finance_channels_router
from app.api.routes.payment_callback import router as payment_callback_router
from app.api.routes.finance import router as finance_router
from app.api.routes.ownership import (
    ai_agents_router,
    conversation_ai_router,
    entry_links_router,
    member_ai_ownership_router,
    member_ownership_router,
    ownership_audit_router,
    ownership_report_router,
)
from app.api.routes.ai_outbound_jobs import router as ai_outbound_jobs_router
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.api_stats_middleware import ApiStatsMiddleware
from app.core.logging import configure_logging
from app.core.pid_lock import PidLock
from app.core.request_context import REQUEST_ID_HEADER, build_request_id
from app.core.settings import get_settings
from app.db.db_health import check_db_at_startup
from app.db.session import get_sessionmaker
from app.services.h5_demo_user_seed_service import H5DemoUserSeedService
from app.services.h5_site_bootstrap_service import H5SiteBootstrapService
from app.services.h5_template_bootstrap_service import H5TemplateBootstrapService
from app.services.ai_provider_config_service import AIProviderConfigService

logger = structlog.get_logger()


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_to_json_safe(item) for item in value]
    return str(value)


def _serialize_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], _to_json_safe(error))
        for error in exc.errors()
    ]


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    logger = structlog.get_logger()
    logger.info(
        "app_startup",
        app_name=settings.app_name,
        environment=settings.app_env,
        ai_provider=settings.ai_provider,
        test_mode=settings.test_mode,
    )

    # ── Process lock & DB pre-flight (skipped in test mode or test context) ──
    _in_test_context = "PYTEST_CURRENT_TEST" in __import__("os").environ
    if not settings.test_mode and not _in_test_context:
        pid_lock = PidLock()
        pid_lock.acquire_or_exit()

        db_ok = check_db_at_startup()
        if not db_ok:
            logger.error(
                "db_unreachable_at_startup",
                hint=(
                    "PostgreSQL is not reachable. The app will start but DB-dependent "
                    "features will return errors. Check: (1) Is PostgreSQL running? "
                    "(2) Is DATABASE_URL correct? On Windows outside Docker, "
                    "replace 'postgres' with 'localhost'."
                ),
            )

    if not settings.test_mode:
        try:
            session_factory = get_sessionmaker()
            with session_factory() as session:
                template_created = H5TemplateBootstrapService(session).ensure_default_template()
            logger.info(
                "h5_default_template_bootstrap",
                created=template_created,
            )
        except Exception as template_error:
            logger.warning(
                "h5_default_template_bootstrap_failed",
                error=str(template_error),
            )

    if settings.app_env == "development" and not settings.test_mode:
        try:
            session_factory = get_sessionmaker()
            with session_factory() as session:
                bootstrap_service = H5SiteBootstrapService(session)
                created = bootstrap_service.ensure_default_sites(only_when_empty=False)
                repaired = bootstrap_service.backfill_default_template_bindings()
            logger.info(
                "h5_default_sites_bootstrap",
                created=created,
                repaired=repaired,
            )
            try:
                with session_factory() as session:
                    seeded = H5DemoUserSeedService(session).ensure_demo_user()
                logger.info(
                    "h5_demo_user_seed",
                    created=seeded,
                    phone="13800000000",
                    site_key="mall-cn",
                )
            except Exception as seed_error:
                logger.warning(
                    "h5_demo_user_seed_skipped",
                    reason=str(seed_error),
                )
        except Exception as bootstrap_error:
            logger.warning(
                "h5_sites_bootstrap_skipped",
                reason=str(bootstrap_error),
            )

    # ── Seed AI provider configs from .env (if table empty) ──
    if settings.ai_config_db_enabled:
        try:
            session_factory = get_sessionmaker()
            with session_factory() as session:
                service = AIProviderConfigService(session)
                seeded = service.seed_from_env(settings)
                if seeded > 0:
                    logger.info(
                        "seeded_ai_provider_configs",
                        count=seeded,
                    )
        except Exception as seed_error:
            logger.warning(
                "ai_provider_config_seed_skipped",
                reason=str(seed_error),
            )

    yield
    # ── Graceful shutdown ──
    if not settings.test_mode and not _in_test_context:
        pid_lock.release()
    logger.info(
        "app_shutdown_complete",
        app_name=settings.app_name,
    )


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(ApiStatsMiddleware)


origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",
        "X-Actor-Id",
        "X-Actor-Name",
        "X-Actor-Role",
        "X-Actor-Account-Ids",
    ],
)

# ── Static files: template preview (P2-03: paths from settings, not hard-coded) ──
_static_dir = settings.resolved_template_static_root
_upload_dir = settings.resolved_template_upload_root
_static_dir.mkdir(parents=True, exist_ok=True)
_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/templates", StaticFiles(directory=str(_static_dir)), name="templates")


def _include_optional_router(
    app_instance: FastAPI,
    module_path: str,
    *,
    attr_name: str = "router",
) -> None:
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.info("optional_router_module_missing", module_path=module_path)
        return

    router = getattr(module, attr_name, None)
    if router is None:
        logger.info("optional_router_attr_missing", module_path=module_path, attr_name=attr_name)
        return
    app_instance.include_router(router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = build_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = request_id
    clear_contextvars()
    bind_contextvars(request_id=request_id)
    logger.info(
        "request_started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    try:
        response = await call_next(request)
    finally:
        clear_contextvars()
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", build_request_id())
    payload = {"detail": exc.detail, "request_id": request_id}
    headers = dict(exc.headers or {})
    headers[REQUEST_ID_HEADER] = request_id
    logger.warning(
        "http_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content=payload, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", build_request_id())
    serialized_errors = _serialize_validation_errors(exc)
    payload = {
        "detail": serialized_errors,
        "request_id": request_id,
    }
    logger.warning(
        "request_validation_failed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        error_count=len(serialized_errors),
    )
    return JSONResponse(
        status_code=422,
        content=payload,
        headers={REQUEST_ID_HEADER: request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", build_request_id())
    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        error=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "request_id": request_id,
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


app.include_router(admin_auth_router)
app.include_router(agency_router)
app.include_router(agent_auth_router)
app.include_router(unified_auth_router)
app.include_router(agent_dashboard_router)
app.include_router(ai_providers_router)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(notifications_router)
# P2-01: dev/mock routes are only registered outside production so they can
# never be reached in a production deployment (returns 404 instead of relying
# on in-route checks alone).
if settings.app_env.strip().lower() != "production" or settings.test_mode:
    app.include_router(dev_router)
app.include_router(queue_router)
app.include_router(exports_router)
app.include_router(h5_auth_router)
app.include_router(h5_member_commerce_router)
app.include_router(h5_member_fragments_router)
app.include_router(h5_member_messages_router)
app.include_router(h5_member_verification_router)
app.include_router(h5_member_whatsapp_binding_router)
app.include_router(h5_router)
app.include_router(h5_deploy_router)
app.include_router(h5_languages_router)
app.include_router(h5_translations_router)
app.include_router(site_permissions_router)
app.include_router(site_waba_router)
app.include_router(client_errors_router)
app.include_router(deploy_history_router)
app.include_router(domain_verification_router)
app.include_router(h5_site_analytics_router)
app.include_router(h5_templates_router)
app.include_router(agents_router)
app.include_router(agent_audit_router)
app.include_router(performance_router)
app.include_router(canned_responses_router)
app.include_router(conversation_poll_router)
app.include_router(conversations_router)
app.include_router(conversation_notes_router)
app.include_router(customers_router)
app.include_router(dashboard_router)
app.include_router(ecommerce_router)
app.include_router(media_assets_router)
app.include_router(meta_callbacks_router)
app.include_router(search_router)
app.include_router(meta_accounts_router)
app.include_router(platform_router)
app.include_router(platform_member_whatsapp_bindings_router)
app.include_router(platform_member_verifications_router)
app.include_router(platform_withdrawals_router)
app.include_router(runtime_router)
app.include_router(tasks_router)
app.include_router(reviews_router)
app.include_router(tickets_router)
app.include_router(templates_router)
app.include_router(translation_providers_router)
app.include_router(products_router)
app.include_router(product_packages_router)
app.include_router(task_rules_router)
app.include_router(task_instances_router)
app.include_router(sign_in_router)
app.include_router(invites_router)
app.include_router(marketing_stats_router)
app.include_router(whatsapp_analytics_router)
app.include_router(waba_assignment_router)
app.include_router(webhooks_router)
app.include_router(permissions_router)
app.include_router(worker_health_router)
app.include_router(workspace_auth_router)
app.include_router(reports_router)
app.include_router(operations_router)
app.include_router(backups_router)
app.include_router(batch_router)
app.include_router(knowledge_base_router)
app.include_router(customer_profile_router)
app.include_router(template_preview_router)
app.include_router(api_stats_router)
app.include_router(rate_limits_router)
app.include_router(health_check_routes_router)
app.include_router(ai_chat_config_router)
app.include_router(ai_billing_router)
app.include_router(exchange_rates_router)
app.include_router(finance_channels_router)
app.include_router(payment_callback_router)
app.include_router(finance_router)
# ── 归属 / AI 接待 / 入口链接（spec 第 10 节） ──
app.include_router(entry_links_router)
app.include_router(ai_agents_router)
app.include_router(member_ownership_router)
app.include_router(member_ai_ownership_router)
app.include_router(conversation_ai_router)
app.include_router(ownership_audit_router)
app.include_router(ownership_report_router)
app.include_router(ai_outbound_jobs_router)

for _optional_router in (
    "app.api.routes.whatsapp_auth_admin",
    "app.api.routes.whatsapp_auth_h5",
    "app.api.routes.h5_gateway_admin",
    "app.api.routes.h5_gateway_agent",
):
    _include_optional_router(app, _optional_router)


# ── Client error reporting ──
@app.post("/api/client-errors", status_code=204)
async def report_client_error(payload: dict):
    """Record a frontend JS error via the client_errors service."""
    from app.db.session import get_sessionmaker
    from app.services.client_error_service import ClientErrorService
    session = get_sessionmaker()()
    try:
        svc = ClientErrorService(session)
        svc.record_error(
            error_type=payload.get("error_type", "javascript"),
            message=payload.get("message", "unknown"),
            stack_trace=payload.get("stack"),
            url=payload.get("url"),
            user_agent=payload.get("user_agent"),
        )
    except Exception:
        pass
    finally:
        session.close()
