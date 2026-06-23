"""AI & Translation usage metering and billing service."""
import structlog
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.db.models import (
    AiUsageRecord,
    TranslationUsageRecord,
    AiProviderRate,
    AgencyFreeQuota,
    AgencyMonthlyBill,
)

logger = structlog.get_logger()


class AiUsageService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Record AI usage ──
    def record_ai_usage(
        self,
        agency_id: str | None = None,
        site_id: str | None = None,
        conversation_id: str | None = None,
        provider_name: str | None = None,
        message_count: int = 1,
    ) -> AiUsageRecord:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        # Look up provider rate
        rate_obj = None
        if provider_name:
            rate_obj = self._session.execute(
                select(AiProviderRate).where(
                    AiProviderRate.provider_name == provider_name,
                    AiProviderRate.is_enabled.is_(True),
                )
            ).scalar_one_or_none()

        cost_per_msg = Decimal(str(rate_obj.cost_per_message)) if rate_obj else Decimal("0")
        total_cost = cost_per_msg * Decimal(str(message_count))

        record = AiUsageRecord(
            id=str(uuid4()),
            agency_id=agency_id,
            site_id=site_id,
            conversation_id=conversation_id,
            provider_name=provider_name,
            message_count=message_count,
            cost=total_cost,
            billing_month=month,
        )
        self._session.add(record)

        # Update free quota usage
        if agency_id:
            self._update_free_quota_usage(agency_id, month, ai_messages=message_count)

        self._session.flush()
        return record

    # ── Record translation usage ──
    def record_translation_usage(
        self,
        agency_id: str | None = None,
        site_id: str | None = None,
        translation_count: int = 1,
    ) -> TranslationUsageRecord:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        cost_per_translation = Decimal("0.01")  # Default translation rate
        total_cost = cost_per_translation * Decimal(str(translation_count))

        record = TranslationUsageRecord(
            id=str(uuid4()),
            agency_id=agency_id,
            site_id=site_id,
            translation_count=translation_count,
            cost=total_cost,
            billing_month=month,
        )
        self._session.add(record)

        # Update free quota usage
        if agency_id:
            self._update_free_quota_usage(agency_id, month, translations=translation_count)

        self._session.flush()
        return record

    # ── Get monthly usage ──
    def get_monthly_usage(self, agency_id: str, month: str) -> dict:
        ai_total = self._session.scalar(
            select(func.sum(AiUsageRecord.cost)).where(
                AiUsageRecord.agency_id == agency_id,
                AiUsageRecord.billing_month == month,
            )
        ) or Decimal("0")

        ai_count = self._session.scalar(
            select(func.sum(AiUsageRecord.message_count)).where(
                AiUsageRecord.agency_id == agency_id,
                AiUsageRecord.billing_month == month,
            )
        ) or 0

        trans_total = self._session.scalar(
            select(func.sum(TranslationUsageRecord.cost)).where(
                TranslationUsageRecord.agency_id == agency_id,
                TranslationUsageRecord.billing_month == month,
            )
        ) or Decimal("0")

        trans_count = self._session.scalar(
            select(func.sum(TranslationUsageRecord.translation_count)).where(
                TranslationUsageRecord.agency_id == agency_id,
                TranslationUsageRecord.billing_month == month,
            )
        ) or 0

        return {
            "agency_id": agency_id,
            "month": month,
            "ai_message_count": ai_count,
            "ai_cost": float(ai_total),
            "translation_count": trans_count,
            "translation_cost": float(trans_total),
            "total_cost": float(ai_total + trans_total),
        }

    # ── Get site-level usage ──
    def get_site_usage(self, site_id: str, month: str) -> dict:
        ai_total = self._session.scalar(
            select(func.sum(AiUsageRecord.cost)).where(
                AiUsageRecord.site_id == site_id,
                AiUsageRecord.billing_month == month,
            )
        ) or Decimal("0")

        ai_count = self._session.scalar(
            select(func.sum(AiUsageRecord.message_count)).where(
                AiUsageRecord.site_id == site_id,
                AiUsageRecord.billing_month == month,
            )
        ) or 0

        return {
            "site_id": site_id,
            "month": month,
            "ai_message_count": ai_count,
            "ai_cost": float(ai_total),
        }

    # ── Generate monthly bill ──
    def generate_monthly_bill(self, agency_id: str, month: str) -> AgencyMonthlyBill:
        usage = self.get_monthly_usage(agency_id, month)

        # Get free quota for this month
        quota = self._session.execute(
            select(AgencyFreeQuota).where(
                AgencyFreeQuota.agency_id == agency_id,
                AgencyFreeQuota.billing_month == month,
            )
        ).scalar_one_or_none()

        free_ai_used = quota.used_ai_messages if quota else 0
        free_trans_used = quota.used_translations if quota else 0

        # Upsert bill
        existing = self._session.execute(
            select(AgencyMonthlyBill).where(
                AgencyMonthlyBill.agency_id == agency_id,
                AgencyMonthlyBill.billing_month == month,
            )
        ).scalar_one_or_none()

        if existing:
            existing.ai_cost = Decimal(str(usage["ai_cost"]))
            existing.translation_cost = Decimal(str(usage["translation_cost"]))
            existing.total_cost = Decimal(str(usage["total_cost"]))
            existing.free_ai_used = free_ai_used
            existing.free_translation_used = free_trans_used
            bill = existing
        else:
            bill = AgencyMonthlyBill(
                id=str(uuid4()),
                agency_id=agency_id,
                billing_month=month,
                ai_cost=Decimal(str(usage["ai_cost"])),
                translation_cost=Decimal(str(usage["translation_cost"])),
                total_cost=Decimal(str(usage["total_cost"])),
                free_ai_used=free_ai_used,
                free_translation_used=free_trans_used,
                status="pending",
            )
            self._session.add(bill)

        self._session.flush()
        return bill

    # ── Check quota warning ──
    def check_quota_warning(self, agency_id: str) -> dict | None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        quota = self._session.execute(
            select(AgencyFreeQuota).where(
                AgencyFreeQuota.agency_id == agency_id,
                AgencyFreeQuota.billing_month == month,
            )
        ).scalar_one_or_none()

        if quota is None:
            return None

        ai_ratio = quota.used_ai_messages / max(quota.free_ai_messages, 1)
        trans_ratio = quota.used_translations / max(quota.free_translations, 1)
        max_ratio = max(ai_ratio, trans_ratio)

        warning = None
        if max_ratio >= 0.9:
            warning = "critical"
        elif max_ratio >= 0.75:
            warning = "warning"

        if warning:
            return {
                "agency_id": agency_id,
                "month": month,
                "level": warning,
                "ai_usage_ratio": round(ai_ratio, 2),
                "translation_usage_ratio": round(trans_ratio, 2),
                "ai_used": quota.used_ai_messages,
                "ai_free": quota.free_ai_messages,
                "translation_used": quota.used_translations,
                "translation_free": quota.free_translations,
            }
        return None

    # ── Internal: update free quota counters ──
    def _update_free_quota_usage(
        self,
        agency_id: str,
        month: str,
        ai_messages: int = 0,
        translations: int = 0,
    ) -> None:
        quota = self._session.execute(
            select(AgencyFreeQuota).where(
                AgencyFreeQuota.agency_id == agency_id,
                AgencyFreeQuota.billing_month == month,
            )
        ).scalar_one_or_none()

        if quota:
            quota.used_ai_messages += ai_messages
            quota.used_translations += translations
