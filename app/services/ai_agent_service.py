"""AI Agent 服务（spec 6.2）。

AI Agent 是独立主体（不伪装成人工客服），但可归属某个 staff 管理。
不允许物理删除曾产生链接、客户绑定、消息或 job 的 AI Agent；
删除 = status 改成 archived/deleted，并触发客户/会话 AI 自动迁移或标记。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import utc_now
from app.db.ownership_models import AIAgent, EntryLink, OwnershipAuditEvent


class AIAgentNotFoundError(LookupError):
    pass


class AIAgentService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_ai_agent(
        self,
        *,
        account_id: str,
        name: str,
        display_name: str,
        agency_id: str | None = None,
        site_id: str | None = None,
        provider_name: str = "openai",
        model_name: str = "gpt-4o-mini",
        prompt_version: str | None = None,
        system_prompt: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        owning_staff_user_id: str | None = None,
        owning_agency_member_id: str | None = None,
        fallback_staff_user_id: str | None = None,
        fallback_agency_member_id: str | None = None,
        fallback_ai_agent_id: str | None = None,
        auto_reply_enabled: bool = True,
        proactive_send_enabled: bool = False,
        actor_id: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> AIAgent:
        agent = AIAgent(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            name=name,
            display_name=display_name,
            status="active",
            provider_name=provider_name,
            model_name=model_name,
            prompt_version=prompt_version,
            system_prompt=system_prompt,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            owning_staff_user_id=owning_staff_user_id,
            owning_agency_member_id=owning_agency_member_id,
            fallback_staff_user_id=fallback_staff_user_id,
            fallback_agency_member_id=fallback_agency_member_id,
            fallback_ai_agent_id=fallback_ai_agent_id,
            auto_reply_enabled=auto_reply_enabled,
            proactive_send_enabled=proactive_send_enabled,
            health_status="healthy",
            metadata_json=metadata_json,
        )
        self._session.add(agent)
        self._session.flush()
        self._audit(agent, action="ai_agent_created", actor_id=actor_id)
        return agent

    def update_ai_agent(self, agent_id: str, *, actor_id: str | None, **fields: Any) -> AIAgent:
        agent = self.require(agent_id)
        for key, value in fields.items():
            if hasattr(agent, key) and value is not None:
                setattr(agent, key, value)
        self._session.add(agent)
        return agent

    def disable_ai_agent(self, agent_id: str, *, actor_id: str | None, reason: str | None = None) -> AIAgent:
        agent = self.require(agent_id)
        agent.status = "disabled"
        agent.health_status = "disabled"
        self._session.add(agent)
        self._audit(agent, action="ai_agent_disabled", actor_id=actor_id, payload={"reason": reason})
        return agent

    def archive_ai_agent(self, agent_id: str, *, actor_id: str | None, reason: str | None = None) -> AIAgent:
        agent = self.require(agent_id)
        agent.status = "archived"
        agent.health_status = "disabled"
        # 禁用相关 EntryLink
        for link in self._session.scalars(
            select(EntryLink).where(EntryLink.target_ai_agent_id == agent_id, EntryLink.status == "active")
        ).all():
            link.status = "target_unavailable"
            self._session.add(link)
        self._session.add(agent)
        self._audit(agent, action="ai_agent_archived", actor_id=actor_id, payload={"reason": reason})
        return agent

    def health_check(self, agent_id: str) -> AIAgent:
        agent = self.require(agent_id)
        agent.last_health_check_at = utc_now()
        # 简单健康检查：status active + provider/model 已配置
        if agent.status != "active":
            agent.health_status = "disabled"
        elif not agent.provider_name or not agent.model_name:
            agent.health_status = "degraded"
        else:
            agent.health_status = "healthy"
        self._session.add(agent)
        return agent

    def is_agent_available(self, agent: AIAgent, channel_context: str | None = None) -> bool:
        """AI 可接待检查：status active + auto_reply + provider/model 可用 + WABA 可用（whatsapp 场景）。"""
        if agent.status != "active":
            return False
        if not agent.auto_reply_enabled:
            return False
        if not agent.provider_name or not agent.model_name:
            return False
        if channel_context == "whatsapp" and not agent.waba_id:
            return False
        return True

    def resolve_fallback_chain(
        self,
        ai_agent: AIAgent,
        *,
        site_id: str | None = None,
        account_id: str | None = None,
        reason: str | None = None,
        channel_context: str | None = None,
    ) -> AIAgent | None:
        """fallback 查找：AI-A.fallback_ai_agent_id -> 站点默认 AI -> 账号可用 AI 池最优。"""
        # 1. AI-A.fallback_ai_agent_id
        if ai_agent.fallback_ai_agent_id:
            fb = self._session.get(AIAgent, ai_agent.fallback_ai_agent_id)
            if fb is not None and self.is_agent_available(fb, channel_context=channel_context):
                return fb
        # 2. 站点默认 AI
        if site_id is not None:
            default_agent = self._session.scalar(
                select(AIAgent).where(
                    AIAgent.site_id == site_id,
                    AIAgent.status == "active",
                    AIAgent.id != ai_agent.id,
                ).order_by(AIAgent.created_at)
            )
            if default_agent is not None and self.is_agent_available(
                default_agent, channel_context=channel_context
            ):
                return default_agent
        # 3. 账号可用 AI 池
        if account_id is not None:
            pool_agent = self._session.scalar(
                select(AIAgent).where(
                    AIAgent.account_id == account_id,
                    AIAgent.status == "active",
                    AIAgent.id != ai_agent.id,
                ).order_by(AIAgent.created_at)
            )
            if pool_agent is not None and self.is_agent_available(
                pool_agent, channel_context=channel_context
            ):
                return pool_agent
        return None

    def ensure_default_agent_for_site(self, site_id: str) -> AIAgent | None:
        """确保站点有默认 AI；若无则不强制创建（由显式配置决定）。"""
        from app.db.models import H5Site

        site = self._session.get(H5Site, site_id)
        if site is None:
            return None
        if site.default_ai_agent_id:
            agent = self._session.get(AIAgent, site.default_ai_agent_id)
            if agent is not None:
                return agent
        # 返回站点下任意 active agent
        return self._session.scalar(
            select(AIAgent).where(AIAgent.site_id == site_id, AIAgent.status == "active").order_by(AIAgent.created_at)
        )

    def ensure_default_links(self, ai_agent_id: str, site_id: str | None) -> EntryLink | None:
        from app.services.entry_link_service import EntryLinkService

        agent = self.require(ai_agent_id)
        if agent.account_id is None:
            return None
        svc = EntryLinkService(self._session)
        return svc.get_or_create_default_ai_link(
            account_id=agent.account_id,
            site_id=site_id or agent.site_id,
            ai_agent_id=ai_agent_id,
        )

    def list_ai_agents(
        self,
        *,
        account_id: str | None = None,
        site_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[AIAgent]:
        stmt = select(AIAgent).order_by(AIAgent.created_at.desc()).limit(limit)
        if account_id is not None:
            stmt = stmt.where(AIAgent.account_id == account_id)
        if site_id is not None:
            stmt = stmt.where(AIAgent.site_id == site_id)
        if status is not None:
            stmt = stmt.where(AIAgent.status == status)
        return list(self._session.scalars(stmt).all())

    def require(self, agent_id: str) -> AIAgent:
        agent = self._session.get(AIAgent, agent_id)
        if agent is None:
            raise AIAgentNotFoundError(f"AI Agent '{agent_id}' not found.")
        return agent

    def _audit(
        self,
        agent: AIAgent,
        *,
        action: str,
        actor_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            OwnershipAuditEvent(
                account_id=agent.account_id,
                agency_id=agent.agency_id,
                site_id=agent.site_id,
                action=action,
                target_type="ai_agent",
                target_id=agent.id,
                actor_type="staff" if actor_id else "system",
                actor_id=actor_id,
                payload={"name": agent.name, **(payload or {})},
            )
        )
