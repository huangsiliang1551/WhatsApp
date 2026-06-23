"""Health checks and email config API — IV-BE-008.

Endpoints:
  # Email config
  GET   /api/email-config                — get email config
  PUT   /api/email-config                — update email config
  POST  /api/email-config/test           — send test email

  # Health checks
  GET   /api/health-checks               — latest results
  POST  /api/health-checks/run           — run all checks now
  GET   /api/health-checks/summary       — dashboard summary
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.core.settings import Settings, get_settings
from app.services.email_service import EmailService
from app.services.health_check_service import HealthCheckService

router = APIRouter(tags=["health"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class EmailConfigRequest(BaseModel):
    smtp_host: str
    smtp_port: int = 465
    smtp_user: str
    smtp_password: str
    smtp_ssl: bool = True
    from_name: str | None = None
    from_email: str | None = None


class TestEmailRequest(BaseModel):
    to: str


# ─── Email Config ───────────────────────────────────────────────────────────


@router.get("/api/email-config", summary="获取邮件配置")
def get_email_config(session: Session = Depends(get_db_session)):
    svc = EmailService(session)
    config = svc.get_config()
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "smtp_user": config.smtp_user,
        "smtp_ssl": config.smtp_ssl,
        "from_name": config.from_name,
        "from_email": config.from_email,
        "is_enabled": config.is_enabled,
    }


@router.put("/api/email-config", summary="更新邮件配置")
def update_email_config(
    body: EmailConfigRequest,
    session: Session = Depends(get_db_session),
):
    svc = EmailService(session)
    config = svc.save_config(body.model_dump())
    return {
        "success": True,
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "from_email": config.from_email,
    }


@router.post("/api/email-config/test", summary="发送测试邮件")
async def test_email(
    body: TestEmailRequest,
    session: Session = Depends(get_db_session),
):
    svc = EmailService(session)
    result = await svc.send_email(
        to=body.to,
        subject="[测试邮件] 系统邮件配置测试",
        body="这是一封来自 WhatsApp Support Platform 的测试邮件。\n\n如果收到此邮件，说明邮件配置正确。",
    )
    return result


# ─── Health Checks ──────────────────────────────────────────────────────────


@router.get("/api/health-checks", summary="最近检查结果")
def get_health_checks(session: Session = Depends(get_db_session)):
    svc = HealthCheckService(session)
    results = svc.get_latest_results()
    return [
        {
            "id": r.id,
            "check_type": r.check_type,
            "target": r.target,
            "status": r.status,
            "response_time_ms": r.response_time_ms,
            "details": r.details,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None,
        }
        for r in results
    ]


@router.post("/api/health-checks/run", summary="手动执行检查")
async def run_health_checks(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    svc = HealthCheckService(session, settings)
    results = await svc.check_all()
    return [
        {
            "id": r.id,
            "check_type": r.check_type,
            "target": r.target,
            "status": r.status,
            "response_time_ms": r.response_time_ms,
            "details": r.details,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None,
        }
        for r in results
    ]


@router.get("/api/health-checks/summary", summary="健康检查汇总")
def get_health_summary(session: Session = Depends(get_db_session)):
    svc = HealthCheckService(session)
    return svc.get_summary()
