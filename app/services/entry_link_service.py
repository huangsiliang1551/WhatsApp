"""入口链接服务（spec 6.1）。

EntryLink 统一表示客服注册链接 / AI H5 注册链接 / AI WhatsApp 对话链接 /
会员邀请入口映射 / 站点总客服链接 / 站点总 AI 链接 / 二维码 / 广告链接。

完整 URL 由 EntryLink + Site + WABA/phone 派生，不作为唯一事实来源。
record_usage_once 必须幂等，不能因重复 webhook / 重复注册请求重复计数。
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import H5Site, utc_now
from app.db.ownership_models import EntryLink, OwnershipAuditEvent

ENTRY_LINK_CODE_PREFIX = "EL"


class EntryLinkUnavailableError(ValueError):
    """EntryLink 不可用（禁用 / 过期 / 用尽 / 目标不可用）。"""


class EntryLinkNotFoundError(LookupError):
    """EntryLink code 未命中。"""


class EntryLinkService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── 默认链接生成 ──
    def get_or_create_default_staff_link(
        self,
        *,
        account_id: str,
        site_id: str | None,
        staff_user_id: str,
        actor_id: str | None = None,
        agency_id: str | None = None,
    ) -> EntryLink:
        existing = self._find_active_default(
            account_id=account_id,
            site_id=site_id,
            link_type="site_default_staff",
            target_type="staff",
            target_staff_user_id=staff_user_id,
        )
        if existing is not None:
            return existing
        return self._create(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            link_type="site_default_staff",
            channel="h5",
            target_type="staff",
            target_staff_user_id=staff_user_id,
            created_by_actor_id=actor_id,
        )

    def get_or_create_default_ai_link(
        self,
        *,
        account_id: str,
        site_id: str | None,
        ai_agent_id: str,
        actor_id: str | None = None,
        agency_id: str | None = None,
    ) -> EntryLink:
        existing = self._find_active_default(
            account_id=account_id,
            site_id=site_id,
            link_type="site_default_ai",
            target_type="ai_agent",
            target_ai_agent_id=ai_agent_id,
        )
        if existing is not None:
            return existing
        return self._create(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            link_type="site_default_ai",
            channel="h5",
            target_type="ai_agent",
            target_ai_agent_id=ai_agent_id,
            created_by_actor_id=actor_id,
        )

    def get_or_create_staff_ai_link(
        self,
        *,
        account_id: str,
        site_id: str | None,
        staff_user_id: str,
        ai_agent_id: str,
        actor_id: str | None = None,
        agency_id: str | None = None,
    ) -> EntryLink:
        existing = self._find_active_default(
            account_id=account_id,
            site_id=site_id,
            link_type="staff_ai_register",
            target_type="staff_ai",
            target_staff_user_id=staff_user_id,
            target_ai_agent_id=ai_agent_id,
        )
        if existing is not None:
            return existing
        return self._create(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            link_type="staff_ai_register",
            channel="h5",
            target_type="staff_ai",
            target_staff_user_id=staff_user_id,
            target_ai_agent_id=ai_agent_id,
            created_by_actor_id=actor_id,
        )

    def create_staff_register_link(
        self,
        *,
        account_id: str,
        site_id: str | None,
        staff_user_id: str,
        agency_member_id: str | None = None,
        agency_id: str | None = None,
        usage_limit: int | None = None,
        expires_at: datetime | None = None,
        actor_id: str | None = None,
    ) -> EntryLink:
        return self._create(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            link_type="staff_register",
            channel="h5",
            target_type="staff",
            target_staff_user_id=staff_user_id,
            target_agency_member_id=agency_member_id,
            usage_limit=usage_limit,
            expires_at=expires_at,
            created_by_actor_id=actor_id,
        )

    def create_ai_register_link(
        self,
        *,
        account_id: str,
        site_id: str | None,
        ai_agent_id: str,
        agency_id: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        whatsapp_phone_number: str | None = None,
        usage_limit: int | None = None,
        expires_at: datetime | None = None,
        actor_id: str | None = None,
    ) -> EntryLink:
        return self._create(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            link_type="ai_register",
            channel="h5",
            target_type="ai_agent",
            target_ai_agent_id=ai_agent_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            whatsapp_phone_number=whatsapp_phone_number,
            usage_limit=usage_limit,
            expires_at=expires_at,
            created_by_actor_id=actor_id,
        )

    def create_ai_chat_link(
        self,
        *,
        account_id: str,
        site_id: str | None,
        ai_agent_id: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        whatsapp_phone_number: str | None = None,
        agency_id: str | None = None,
        usage_limit: int | None = None,
        expires_at: datetime | None = None,
        actor_id: str | None = None,
    ) -> EntryLink:
        return self._create(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            link_type="ai_chat",
            channel="whatsapp",
            target_type="ai_agent",
            target_ai_agent_id=ai_agent_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            whatsapp_phone_number=whatsapp_phone_number,
            usage_limit=usage_limit,
            expires_at=expires_at,
            created_by_actor_id=actor_id,
        )

    # ── 解析与校验 ──
    def resolve_code(
        self,
        code: str,
        *,
        site_id: str | None = None,
        account_id: str | None = None,
    ) -> EntryLink:
        link = self._session.scalar(select(EntryLink).where(EntryLink.code == code))
        if link is None:
            raise EntryLinkNotFoundError(f"EntryLink code '{code}' not found.")
        if site_id is not None and link.site_id is not None and link.site_id != site_id:
            raise EntryLinkNotFoundError(
                f"EntryLink code '{code}' does not belong to site '{site_id}'."
            )
        if account_id is not None and link.account_id != account_id:
            raise EntryLinkNotFoundError(
                f"EntryLink code '{code}' does not belong to account '{account_id}'."
            )
        return link

    def ensure_active_and_usable(
        self, entry_link: EntryLink, *, site_id: str | None = None
    ) -> EntryLink:
        if entry_link.status != "active":
            raise EntryLinkUnavailableError(
                f"EntryLink '{entry_link.code}' is {entry_link.status}."
            )
        if entry_link.expires_at is not None and entry_link.expires_at <= utc_now():
            raise EntryLinkUnavailableError(
                f"EntryLink '{entry_link.code}' has expired."
            )
        if entry_link.usage_limit is not None and entry_link.usage_count >= entry_link.usage_limit:
            raise EntryLinkUnavailableError(
                f"EntryLink '{entry_link.code}' has reached its usage limit."
            )
        if site_id is not None and entry_link.site_id is not None and entry_link.site_id != site_id:
            raise EntryLinkUnavailableError(
                f"EntryLink '{entry_link.code}' does not belong to site '{site_id}'."
            )
        return entry_link

    # ── 幂等使用计数 ──
    def record_usage_once(
        self,
        *,
        idempotency_key: str,
        entry_link: EntryLink,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """幂等记录一次使用。

        同一 idempotency_key 重复调用不会重复增加 usage_count。幂等键存在
        entry_link.metadata_json['usage_keys'] 中。重复 webhook / 重复注册
        请求必须传相同 idempotency_key（例如 account_id+provider_message_id）。
        """
        meta = dict(entry_link.metadata_json or {})
        used_keys: set[str] = set(meta.get("usage_keys") or [])
        if idempotency_key in used_keys:
            return False  # 已记录过，幂等不重复计数
        used_keys.add(idempotency_key)
        meta["usage_keys"] = sorted(used_keys)
        entry_link.metadata_json = meta
        entry_link.usage_count = (entry_link.usage_count or 0) + 1
        entry_link.last_used_at = utc_now()
        if entry_link.usage_limit is not None and entry_link.usage_count >= entry_link.usage_limit:
            entry_link.status = "usage_limit_reached"
        self._session.add(entry_link)
        return True

    # ── 撤销 / 轮换 ──
    def revoke(self, link_id: str, *, actor_id: str | None, reason: str | None) -> EntryLink:
        link = self._require(link_id)
        link.status = "revoked"
        self._session.add(link)
        self._audit(link, action="entry_link_revoked", actor_id=actor_id, payload={"reason": reason})
        return link

    def rotate(self, link_id: str, *, actor_id: str | None, reason: str | None) -> EntryLink:
        """轮换：旧链接撤销，新建同配置 active 链接。"""
        old = self._require(link_id)
        old.status = "revoked"
        self._session.add(old)
        new = self._create(
            account_id=old.account_id,
            agency_id=old.agency_id,
            site_id=old.site_id,
            link_type=old.link_type,
            channel=old.channel,
            target_type=old.target_type,
            target_staff_user_id=old.target_staff_user_id,
            target_agency_member_id=old.target_agency_member_id,
            target_ai_agent_id=old.target_ai_agent_id,
            referrer_user_id=old.referrer_user_id,
            waba_id=old.waba_id,
            phone_number_id=old.phone_number_id,
            whatsapp_phone_number=old.whatsapp_phone_number,
            usage_limit=old.usage_limit,
            expires_at=old.expires_at,
            created_by_actor_id=actor_id,
        )
        self._audit(new, action="entry_link_rotated", actor_id=actor_id, payload={"reason": reason, "replaces": old.id})
        return new

    # ── 列表 ──
    def list_links(
        self,
        *,
        account_id: str | None = None,
        site_id: str | None = None,
        link_type: str | None = None,
        target_type: str | None = None,
        target_staff_user_id: str | None = None,
        target_ai_agent_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[EntryLink]:
        stmt = select(EntryLink).order_by(EntryLink.created_at.desc()).limit(limit)
        if account_id is not None:
            stmt = stmt.where(EntryLink.account_id == account_id)
        if site_id is not None:
            stmt = stmt.where(EntryLink.site_id == site_id)
        if link_type is not None:
            stmt = stmt.where(EntryLink.link_type == link_type)
        if target_type is not None:
            stmt = stmt.where(EntryLink.target_type == target_type)
        if target_staff_user_id is not None:
            stmt = stmt.where(EntryLink.target_staff_user_id == target_staff_user_id)
        if target_ai_agent_id is not None:
            stmt = stmt.where(EntryLink.target_ai_agent_id == target_ai_agent_id)
        if status is not None:
            stmt = stmt.where(EntryLink.status == status)
        return list(self._session.scalars(stmt).all())

    # ── URL 派生 ──
    def build_urls(self, entry_link: EntryLink) -> dict[str, str | None]:
        """根据 EntryLink + Site + WABA/phone 派生完整 URL。"""
        h5_register_url: str | None = None
        whatsapp_chat_url: str | None = None
        qr_payload: str | None = entry_link.code

        if entry_link.site_id is not None:
            site = self._session.get(H5Site, entry_link.site_id)
            if site is not None and site.domain:
                base = site.domain.rstrip("/")
                params = f"site_key={site.site_key}&entry_code={entry_link.code}"
                h5_register_url = f"https://{base}/h5/register?{params}"

        if entry_link.channel == "whatsapp" and entry_link.whatsapp_phone_number:
            phone = entry_link.whatsapp_phone_number.lstrip("+")
            whatsapp_chat_url = f"https://wa.me/{phone}?text=/start%20{entry_link.code}"

        return {
            "h5_register_url": h5_register_url,
            "whatsapp_chat_url": whatsapp_chat_url,
            "qr_payload": qr_payload,
        }

    # ── 内部 ──
    def _create(
        self,
        *,
        account_id: str,
        link_type: str,
        channel: str,
        target_type: str,
        site_id: str | None = None,
        agency_id: str | None = None,
        target_staff_user_id: str | None = None,
        target_agency_member_id: str | None = None,
        target_ai_agent_id: str | None = None,
        referrer_user_id: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        whatsapp_phone_number: str | None = None,
        usage_limit: int | None = None,
        expires_at: datetime | None = None,
        created_by_actor_id: str | None = None,
    ) -> EntryLink:
        link = EntryLink(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            code=self._generate_code(),
            link_type=link_type,
            channel=channel,
            status="active",
            target_type=target_type,
            target_staff_user_id=target_staff_user_id,
            target_agency_member_id=target_agency_member_id,
            target_ai_agent_id=target_ai_agent_id,
            referrer_user_id=referrer_user_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            whatsapp_phone_number=whatsapp_phone_number,
            usage_count=0,
            usage_limit=usage_limit,
            expires_at=expires_at,
            created_by_actor_id=created_by_actor_id,
        )
        self._session.add(link)
        self._session.flush()
        self._audit(link, action="entry_link_created", actor_id=created_by_actor_id)
        return link

    def _find_active_default(
        self,
        *,
        account_id: str,
        site_id: str | None,
        link_type: str,
        target_type: str,
        target_staff_user_id: str | None = None,
        target_ai_agent_id: str | None = None,
    ) -> EntryLink | None:
        stmt = select(EntryLink).where(
            EntryLink.account_id == account_id,
            EntryLink.link_type == link_type,
            EntryLink.target_type == target_type,
            EntryLink.status == "active",
        )
        if site_id is not None:
            stmt = stmt.where(EntryLink.site_id == site_id)
        if target_staff_user_id is not None:
            stmt = stmt.where(EntryLink.target_staff_user_id == target_staff_user_id)
        if target_ai_agent_id is not None:
            stmt = stmt.where(EntryLink.target_ai_agent_id == target_ai_agent_id)
        return self._session.scalar(stmt)

    def _require(self, link_id: str) -> EntryLink:
        link = self._session.get(EntryLink, link_id)
        if link is None:
            raise EntryLinkNotFoundError(f"EntryLink '{link_id}' not found.")
        return link

    def _audit(
        self,
        link: EntryLink,
        *,
        action: str,
        actor_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            OwnershipAuditEvent(
                account_id=link.account_id,
                agency_id=link.agency_id,
                site_id=link.site_id,
                action=action,
                target_type="entry_link",
                target_id=link.id,
                actor_type="staff" if actor_id else "system",
                actor_id=actor_id,
                payload={"code": link.code, "link_type": link.link_type, **(payload or {})},
            )
        )

    @staticmethod
    def _generate_code() -> str:
        return f"{ENTRY_LINK_CODE_PREFIX}-{secrets.token_urlsafe(8)}"
