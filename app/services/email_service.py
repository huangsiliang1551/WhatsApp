"""Email service — IV-BE-008.

Provides SMTP email sending capability with config stored in email_config table.
"""

from __future__ import annotations

import asyncio
import json
import smtplib
from email.mime.text import MIMEText
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EmailConfig

logger = structlog.get_logger()


class EmailService:
    """Send emails via SMTP using persisted email config."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_config(self) -> EmailConfig | None:
        return self._session.scalar(
            select(EmailConfig).where(EmailConfig.is_enabled.is_(True))
        )

    def save_config(self, data: dict[str, Any]) -> EmailConfig:
        config = self.get_config()
        if config:
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        else:
            config = EmailConfig(**data)
            self._session.add(config)
        self._session.flush()
        return config

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        config: EmailConfig | None = None,
    ) -> dict[str, Any]:
        """Send an email using the stored SMTP configuration.

        Runs the SMTP call in a thread executor to avoid blocking.
        """
        if config is None:
            config = self.get_config()
        if not config:
            return {"success": False, "error": "邮件服务未配置"}

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = config.from_email or config.smtp_user
        msg["To"] = to

        def _send() -> None:
            smtp_class = smtplib.SMTP_SSL if config.smtp_ssl else smtplib.SMTP
            with smtp_class(config.smtp_host, config.smtp_port, timeout=30) as server:
                if not config.smtp_ssl:
                    server.starttls()
                server.login(config.smtp_user, config.smtp_password)
                server.send_message(msg)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _send)
            logger.info("email_sent", to=to, subject=subject)
            return {"success": True, "to": to, "subject": subject}
        except Exception as exc:
            logger.error("email_failed", to=to, subject=subject, error=str(exc))
            return {"success": False, "error": str(exc)}

    async def send_health_alert(
        self,
        check_type: str,
        target: str,
        status: str,
        details: str | None,
        checked_at: str | None,
    ) -> dict[str, Any]:
        """Send a health check alert email."""
        config = self.get_config()
        if not config:
            return {"success": False, "error": "邮件服务未配置"}

        subject = f"[系统告警] {check_type} 异常: {target}"
        body = (
            f"检查类型: {check_type}\n"
            f"目标: {target}\n"
            f"状态: {status}\n"
            f"详情: {details or '无'}\n"
            f"检查时间: {checked_at or '未知'}"
        )
        # Use the config's from_email as recipient for alerts
        return await self.send_email(
            to=config.from_email or config.smtp_user,
            subject=subject,
            body=body,
            config=config,
        )
