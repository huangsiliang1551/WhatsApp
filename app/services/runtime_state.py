from decimal import Decimal
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import Select, and_, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.metrics import (
    business_template_send_failures_total,
    business_template_sends_total,
    message_delivery_events_total,
    provider_status_event_buffer_events_total,
    provider_status_event_buffer_oldest_age_seconds,
    provider_status_event_buffer_pending_current,
)
from app.db.models import (
    Account,
    Agent,
    AppUser,
    AuditLog,
    Conversation,
    H5Site,
    HandoverLog,
    Message,
    MessageEvent,
    ProviderStatusEventBuffer,
    SystemSetting,
    TemplateSendLog,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    utc_now,
)
from app.schemas.messaging import ProviderStatusUpdate
from app.schemas.runtime import (
    AccountRegistrationRequest,
    AccountRuntimeState,
    ConversationAiStatusResponse,
    ConversationRuntimeState,
    RuntimeStateResponse,
)
from app.services.meta_scope_validation import MetaScopeValidator
from app.services.media_asset_telemetry import MediaAssetTelemetryRecorder
from app.services.template_stats_aggregator import TemplateStatsAggregator
from app.services.whatsapp_stats_aggregator import WhatsAppStatsAggregator

GLOBAL_AI_SETTING_KEY = "global_ai_enabled"
MANAGEMENT_MODES = {"ai_managed", "human_managed", "paused"}
MANAGEMENT_TRANSITIONS: dict[str, set[str]] = {
    "ai_managed": {"ai_managed", "human_managed"},
    "human_managed": {"human_managed", "ai_managed", "paused"},
    "paused": {"paused", "human_managed", "ai_managed"},
}
DEFAULT_MANAGEMENT_REASONS: dict[tuple[str, str], str] = {
    ("ai_managed", "human_managed"): "manual_takeover",
    ("human_managed", "paused"): "manual_pause",
    ("paused", "human_managed"): "resume_human_management",
    ("human_managed", "ai_managed"): "resume_ai_management",
    ("paused", "ai_managed"): "resume_ai_management",
}


class RuntimeStateStore:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._meta_scope_validator = MetaScopeValidator(session)
        self._media_asset_telemetry = MediaAssetTelemetryRecorder(session)
        self._template_stats_aggregator = TemplateStatsAggregator(session)
        self._whatsapp_stats_aggregator = WhatsAppStatsAggregator(session)

    @property
    def session(self) -> Session:
        return self._session

    async def list_state(self) -> RuntimeStateResponse:
        global_ai_enabled = self._get_global_ai_enabled()
        accounts = self._session.scalars(select(Account).order_by(Account.account_id)).all()
        conversations = self._session.scalars(self._conversation_query()).all()
        return RuntimeStateResponse(
            global_ai_enabled=global_ai_enabled,
            accounts=[self._serialize_account(account) for account in accounts],
            conversations=[self._serialize_conversation(conversation) for conversation in conversations],
        )

    async def register_account(self, payload: AccountRegistrationRequest) -> AccountRuntimeState:
        account = await self.ensure_account(
            account_id=payload.account_id,
            display_name=payload.display_name,
            provider_type=payload.provider_type,
        )
        return self._serialize_account(account)

    async def ensure_account(
        self,
        account_id: str,
        display_name: str,
        provider_type: str,
        actor_type: str = "system",
        actor_id: str | None = None,
        notes: str | None = None,
    ) -> Account:
        account = self._session.get(Account, account_id)
        should_commit = False
        if account is None:
            account = Account(
                account_id=account_id,
                display_name=display_name,
                provider_type=provider_type,
                is_active=True,
                ai_enabled=True,
                notes=notes,
            )
            self._session.add(account)
            should_commit = True
            self.add_audit_log(
                account_id=account_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="account_created",
                target_type="account",
                target_id=account_id,
                payload={
                    "display_name": display_name,
                    "provider_type": provider_type,
                },
            )
        else:
            changed = False
            if account.display_name != display_name:
                account.display_name = display_name
                changed = True
            if account.provider_type != provider_type:
                account.provider_type = provider_type
                changed = True
            if notes is not None and account.notes != notes:
                account.notes = notes
                changed = True
            if changed:
                should_commit = True
                self.add_audit_log(
                    account_id=account_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action="account_updated",
                    target_type="account",
                    target_id=account_id,
                    payload={
                        "display_name": display_name,
                        "provider_type": provider_type,
                    },
                )

        if should_commit:
            self._session.commit()
            self._session.refresh(account)
        return account

    async def set_global_ai_enabled(
        self,
        enabled: bool,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> RuntimeStateResponse:
        setting = self._get_or_create_global_setting()
        setting.value_json = {"enabled": enabled}
        self._session.add(setting)
        self.add_audit_log(
            account_id=None,
            actor_type=actor_type,
            actor_id=actor_id,
            action="global_ai_updated",
            target_type="system_setting",
            target_id=GLOBAL_AI_SETTING_KEY,
            payload={"enabled": enabled},
        )
        self._session.commit()
        return await self.list_state()

    async def set_account_ai_enabled(
        self,
        account_id: str,
        enabled: bool,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> AccountRuntimeState:
        account = self._session.get(Account, account_id)
        if account is None:
            raise ValueError(f"Account '{account_id}' was not found.")

        account.ai_enabled = enabled
        self._session.add(account)
        self.add_audit_log(
            account_id=account.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="account_ai_updated",
            target_type="account",
            target_id=account.account_id,
            payload={"enabled": enabled},
        )
        self._session.commit()
        self._session.refresh(account)
        return self._serialize_account(account)

    async def set_account_active(
        self,
        account_id: str,
        is_active: bool,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> AccountRuntimeState:
        account = self._session.get(Account, account_id)
        if account is None:
            raise ValueError(f"Account '{account_id}' was not found.")

        account.is_active = is_active
        self._session.add(account)
        self.add_audit_log(
            account_id=account.account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="account_status_updated",
            target_type="account",
            target_id=account.account_id,
            payload={"is_active": is_active},
        )
        self._session.commit()
        self._session.refresh(account)
        return self._serialize_account(account)

    async def list_agent_models(
        self,
        account_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        status: str | None = None,
        is_active: bool | None = None,
    ) -> list[Agent]:
        query = select(Agent).order_by(Agent.account_id, Agent.display_name, Agent.agent_key, Agent.id)
        if account_id is not None:
            query = query.where(Agent.account_id == account_id)
        elif allowed_account_ids is not None:
            query = query.where(
                or_(
                    Agent.account_id.is_(None),
                    Agent.account_id.in_(allowed_account_ids),
                )
            )
        if status is not None:
            query = query.where(Agent.status == status)
        if is_active is not None:
            query = query.where(Agent.is_active.is_(is_active))
        return self._session.scalars(query).all()

    async def list_agent_workloads(
        self,
        account_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        status: str | None = None,
        is_active: bool | None = None,
    ) -> list[dict[str, object]]:
        agents = await self.list_agent_models(
            account_id=account_id,
            allowed_account_ids=allowed_account_ids,
            status=status,
            is_active=is_active,
        )
        conversation_query = self._conversation_query()
        if account_id is not None:
            conversation_query = conversation_query.where(Conversation.account_id == account_id)
        elif allowed_account_ids is not None:
            conversation_query = conversation_query.where(Conversation.account_id.in_(allowed_account_ids))
        conversations = self._session.scalars(conversation_query).all()

        workloads: list[dict[str, object]] = []
        for agent in agents:
            assigned_conversations = [
                conversation
                for conversation in conversations
                if conversation.assigned_agent_id == agent.id
            ]
            open_assigned_conversations = [
                conversation
                for conversation in assigned_conversations
                if conversation.status == "open"
            ]
            assigned_account_count = len(
                {conversation.account_id for conversation in assigned_conversations}
            )
            workloads.append(
                {
                    "agent": agent,
                    "assigned_open_conversations": len(open_assigned_conversations),
                    "assigned_total_conversations": len(assigned_conversations),
                    "assigned_account_count": assigned_account_count,
                }
            )

        workloads.sort(
            key=lambda item: (
                -int(item["assigned_open_conversations"]),
                -int(item["assigned_total_conversations"]),
                str(item["agent"].display_name),
            )
        )
        return workloads

    async def upsert_agent(
        self,
        agent_id: str,
        display_name: str,
        email: str | None,
        status: str,
        is_active: bool,
        account_id: str | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> Agent:
        agent = self._find_registered_agent(account_id=account_id, agent_id=agent_id)
        should_commit = False
        if agent is None:
            agent = Agent(
                account_id=account_id,
                agent_key=agent_id,
                display_name=display_name,
                email=email,
                status=status,
                is_active=is_active,
            )
            self._session.add(agent)
            should_commit = True
            self.add_audit_log(
                account_id=account_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="agent_registered",
                target_type="agent",
                target_id=agent_id,
                payload={
                    "account_id": account_id,
                    "display_name": display_name,
                    "email": email,
                    "status": status,
                    "is_active": is_active,
                },
            )
        else:
            if (
                agent.account_id != account_id
                or agent.agent_key != agent_id
                or
                agent.display_name != display_name
                or agent.email != email
                or agent.status != status
                or agent.is_active != is_active
            ):
                agent.account_id = account_id
                agent.agent_key = agent_id
                agent.display_name = display_name
                agent.email = email
                agent.status = status
                agent.is_active = is_active
                should_commit = True
                self.add_audit_log(
                    account_id=account_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action="agent_updated",
                    target_type="agent",
                    target_id=agent_id,
                    payload={
                        "account_id": account_id,
                        "display_name": display_name,
                        "email": email,
                        "status": status,
                        "is_active": is_active,
                    },
                )

        if should_commit:
            self._session.commit()
            self._session.refresh(agent)
        return agent

    async def ensure_agent(
        self,
        agent_id: str,
        account_id: str | None = None,
        display_name: str | None = None,
        email: str | None = None,
        default_status: str = "offline",
    ) -> Agent:
        agent = self._find_registered_agent(account_id=account_id, agent_id=agent_id)
        if agent is None:
            agent = Agent(
                account_id=account_id,
                agent_key=agent_id,
                display_name=display_name or agent_id,
                email=email,
                status=default_status,
                is_active=True,
            )
            self._session.add(agent)
            self._session.commit()
            self._session.refresh(agent)
            return agent

        updated = False
        if agent.account_id != account_id:
            agent.account_id = account_id
            updated = True
        if agent.agent_key != agent_id:
            agent.agent_key = agent_id
            updated = True
        if display_name and agent.display_name != display_name:
            agent.display_name = display_name
            updated = True
        if email is not None and agent.email != email:
            agent.email = email
            updated = True
        if updated:
            self._session.add(agent)
            self._session.commit()
            self._session.refresh(agent)
        return agent

    async def set_agent_status(
        self,
        agent_id: str,
        status: str,
        account_id: str | None = None,
        actor_type: str = "agent",
        actor_id: str | None = None,
    ) -> Agent:
        agent = self._find_agent(account_id=account_id, agent_id=agent_id)
        if agent is None:
            raise LookupError(self._format_agent_not_found(account_id=account_id, agent_id=agent_id))

        agent.status = status
        self._session.add(agent)
        self.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id or agent_id,
            action="agent_status_updated",
            target_type="agent",
            target_id=agent_id,
            payload={"account_id": account_id, "status": status},
        )
        self._session.commit()
        self._session.refresh(agent)
        return agent

    async def ensure_conversation(
        self,
        account_id: str,
        conversation_id: str,
        customer_id: str | None = None,
        customer_language: str | None = None,
        customer_language_source: str | None = None,
        provider_phone_number_id: str | None = None,
    ) -> ConversationRuntimeState:
        await self.ensure_account(account_id=account_id, display_name=account_id, provider_type="mock")
        conversation = self._get_conversation(account_id=account_id, conversation_id=conversation_id)
        phone_number = self._get_phone_number_by_provider_id(
            account_id=account_id,
            provider_phone_number_id=provider_phone_number_id,
        )

        if conversation is None:
            # Resolve site_key from customer's registration site
            site_key = None
            if customer_id:
                user = self._session.scalar(
                    select(AppUser).where(AppUser.public_user_id == customer_id)
                )
                if user and user.registration_site_id:
                    h5_site = self._session.get(H5Site, user.registration_site_id)
                    if h5_site:
                        site_key = h5_site.site_key

            conversation = Conversation(
                account_id=account_id,
                external_conversation_id=conversation_id,
                phone_number_id=phone_number.id if phone_number is not None else None,
                customer_id=customer_id or conversation_id,
                customer_language=customer_language or "und",
                customer_language_source=customer_language_source or "unknown",
                ai_enabled=True,
                management_mode="ai_managed",
                site_key=site_key,
            )
            self._session.add(conversation)
        elif customer_id and conversation.customer_id != customer_id:
            conversation.customer_id = customer_id
        if phone_number is not None and conversation.phone_number_id != phone_number.id:
            conversation.phone_number_id = phone_number.id

        if customer_language:
            conversation.customer_language = customer_language
        if customer_language_source:
            conversation.customer_language_source = customer_language_source

        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def set_conversation_ai_enabled(
        self,
        account_id: str,
        conversation_id: str,
        enabled: bool,
        agent_id: str | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        admin_override: bool = False,
    ) -> ConversationRuntimeState:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        if conversation.assigned_agent_id is not None and not admin_override:
            self._ensure_agent_controls_conversation(
                conversation=conversation,
                account_id=account_id,
                agent_id=agent_id,
                action=f"update AI state for conversation '{conversation_id}'",
            )
        conversation.ai_enabled = enabled
        self._session.add(conversation)
        self.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="conversation_ai_updated",
            target_type="conversation",
            target_id=conversation.external_conversation_id,
            payload={
                "enabled": enabled,
                "agent_id": agent_id,
                "admin_override": admin_override,
                "phone_number_id": (
                    conversation.phone_number.phone_number_id
                    if conversation.phone_number is not None
                    else None
                ),
                "waba_id": self._resolve_phone_waba_id(conversation.phone_number),
            },
        )
        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def set_conversation_management_mode(
        self,
        account_id: str,
        conversation_id: str,
        management_mode: str,
        agent_id: str | None,
        reason: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        admin_override: bool = False,
    ) -> ConversationRuntimeState:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        from_mode = conversation.management_mode
        assigned_agent_id = conversation.assigned_agent_id
        status_before = conversation.status

        self._ensure_management_transition_allowed(
            conversation=conversation,
            target_mode=management_mode,
        )
        if not agent_id:
            raise ValueError("agent_id is required when switching conversation management mode.")

        if management_mode == "human_managed":
            if not admin_override and conversation.assigned_agent_id is not None:
                self._ensure_agent_controls_conversation(
                    conversation=conversation,
                    account_id=account_id,
                    agent_id=agent_id,
                    action=f"switch conversation '{conversation_id}' to {management_mode}",
                )
            if admin_override:
                # admin_override 时若 agent 未注册则自动创建
                agent = self._find_agent(account_id=account_id, agent_id=agent_id)
                if agent is None:
                    agent = Agent(
                        id=agent_id,
                        account_id=account_id if account_id != "*" else None,
                        agent_key=agent_id,
                        display_name=agent_id,
                        status="online",
                        is_active=True,
                    )
                    self._session.add(agent)
                assigned_agent_id = agent.id
            else:
                agent = self._require_agent(account_id=account_id, agent_id=agent_id)
                if not agent.is_active:
                    raise ValueError(f"Agent '{agent_id}' is inactive.")
                if agent.status == "offline":
                    raise ValueError(f"Agent '{agent_id}' is offline and cannot take over conversations.")
                assigned_agent_id = agent.id
        else:
            if not admin_override:
                self._ensure_agent_controls_conversation(
                    conversation=conversation,
                    account_id=account_id,
                    agent_id=agent_id,
                    action=f"switch conversation '{conversation_id}' to {management_mode}",
                )
            if management_mode == "ai_managed":
                assigned_agent_id = None

        conversation.status = "open"
        conversation.management_mode = management_mode
        conversation.assigned_agent_id = assigned_agent_id
        handover_reason = self._resolve_management_reason(
            from_mode=from_mode,
            to_mode=management_mode,
            reason=reason,
        )
        triggered_by_type = actor_type or ("agent" if agent_id else "system")
        triggered_by_id = actor_id or agent_id
        self._session.add(conversation)
        self._session.add(
            HandoverLog(
                account_id=account_id,
                conversation_id=conversation.id,
                triggered_by_type=triggered_by_type,
                triggered_by_id=triggered_by_id,
                from_mode=from_mode,
                to_mode=management_mode,
                reason=handover_reason,
            )
        )
        self.add_audit_log(
            account_id=account_id,
            actor_type=triggered_by_type,
            actor_id=triggered_by_id,
            action="conversation_management_updated",
            target_type="conversation",
            target_id=conversation.external_conversation_id,
            payload={
                "status_before": status_before,
                "status_after": conversation.status,
                "from_mode": from_mode,
                "to_mode": management_mode,
                "assigned_agent_id": self.get_public_agent_id(
                    conversation.assigned_agent,
                    fallback=agent_id if assigned_agent_id is not None else None,
                ),
                "reason": handover_reason,
                "transition": f"{from_mode}->{management_mode}",
                "admin_override": admin_override,
                "phone_number_id": (
                    conversation.phone_number.phone_number_id
                    if conversation.phone_number is not None
                    else None
                ),
                "waba_id": self._resolve_phone_waba_id(conversation.phone_number),
            },
        )
        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def assign_conversation(
        self,
        account_id: str,
        conversation_id: str,
        agent_id: str,
        assigned_by_agent_id: str | None = None,
        reason: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        admin_override: bool = False,
    ) -> ConversationRuntimeState:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        self._ensure_conversation_open_for_management(
            conversation=conversation,
            action="assign",
        )
        if conversation.assigned_agent_id is not None and not admin_override:
            if assigned_by_agent_id is None:
                raise PermissionError(
                    "assigned_by_agent_id is required when reassigning an already assigned conversation."
                )
            self._ensure_agent_controls_conversation(
                conversation=conversation,
                account_id=account_id,
                agent_id=assigned_by_agent_id,
                action=f"reassign conversation '{conversation_id}'",
            )
        agent = self._require_agent(account_id=account_id, agent_id=agent_id)
        if not agent.is_active:
            raise ValueError(f"Agent '{agent_id}' is inactive.")
        if agent.status == "offline":
            raise ValueError(f"Agent '{agent_id}' is offline and cannot receive assignments.")

        from_mode = conversation.management_mode
        status_before = conversation.status
        conversation.status = "open"
        conversation.management_mode = "human_managed"
        conversation.assigned_agent_id = agent.id
        handover_reason = reason or "conversation_assigned"
        triggered_by_id = actor_id or assigned_by_agent_id or self.get_public_agent_id(agent)
        triggered_by_type = actor_type or ("agent" if triggered_by_id else "system")
        self._session.add(conversation)
        self._session.add(
            HandoverLog(
                account_id=account_id,
                conversation_id=conversation.id,
                triggered_by_type=triggered_by_type,
                triggered_by_id=triggered_by_id,
                from_mode=from_mode,
                to_mode="human_managed",
                reason=handover_reason,
            )
        )
        self.add_audit_log(
            account_id=account_id,
            actor_type=triggered_by_type,
            actor_id=triggered_by_id,
            action="conversation_assigned",
            target_type="conversation",
            target_id=conversation.external_conversation_id,
            payload={
                "agent_id": self.get_public_agent_id(agent),
                "assigned_by_agent_id": assigned_by_agent_id,
                "reason": handover_reason,
                "status_before": status_before,
                "status_after": conversation.status,
                "from_mode": from_mode,
                "to_mode": "human_managed",
                "admin_override": admin_override,
                "phone_number_id": (
                    conversation.phone_number.phone_number_id
                    if conversation.phone_number is not None
                    else None
                ),
                "waba_id": self._resolve_phone_waba_id(conversation.phone_number),
            },
        )
        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def close_conversation(
        self,
        account_id: str,
        conversation_id: str,
        closed_by_agent_id: str | None = None,
        reason: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        admin_override: bool = False,
    ) -> ConversationRuntimeState:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        if conversation.status == "closed":
            raise ValueError(
                f"Conversation '{conversation_id}' is already closed and cannot be closed again."
            )
        if not admin_override and not closed_by_agent_id:
            raise ValueError("agent_id is required when closing a conversation.")
        if not admin_override:
            self._ensure_agent_controls_conversation(
                conversation=conversation,
                account_id=account_id,
                agent_id=closed_by_agent_id,
                action=f"close conversation '{conversation_id}'",
            )
        from_mode = conversation.management_mode
        status_before = conversation.status
        conversation.status = "closed"
        conversation.management_mode = "ai_managed"
        conversation.assigned_agent_id = None
        close_reason = reason or "conversation_closed_return_to_ai"
        triggered_by_type = actor_type or ("agent" if closed_by_agent_id else "system")
        triggered_by_id = actor_id or closed_by_agent_id
        self._session.add(conversation)
        self._session.add(
            HandoverLog(
                account_id=account_id,
                conversation_id=conversation.id,
                triggered_by_type=triggered_by_type,
                triggered_by_id=triggered_by_id,
                from_mode=from_mode,
                to_mode="ai_managed",
                reason=close_reason,
            )
        )
        self.add_audit_log(
            account_id=account_id,
            actor_type=triggered_by_type,
            actor_id=triggered_by_id,
            action="conversation_closed",
            target_type="conversation",
            target_id=conversation.external_conversation_id,
            payload={
                "reason": close_reason,
                "status_before": status_before,
                "status_after": conversation.status,
                "from_mode": from_mode,
                "to_mode": "ai_managed",
                "admin_override": admin_override,
                "phone_number_id": (
                    conversation.phone_number.phone_number_id
                    if conversation.phone_number is not None
                    else None
                ),
                "waba_id": self._resolve_phone_waba_id(conversation.phone_number),
            },
        )
        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def reopen_conversation(
        self,
        account_id: str,
        conversation_id: str,
        reopened_by_agent_id: str | None = None,
        reason: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        admin_override: bool = False,
    ) -> ConversationRuntimeState:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        if conversation.status != "closed":
            raise ValueError(
                f"Conversation '{conversation_id}' is not closed and cannot be reopened."
            )
        if not admin_override and not reopened_by_agent_id:
            raise ValueError("agent_id is required when reopening a conversation.")

        status_before = conversation.status
        conversation.status = "open"
        conversation.management_mode = "ai_managed"
        conversation.assigned_agent_id = None
        reopen_reason = reason or "conversation_reopened"
        triggered_by_type = actor_type or ("agent" if reopened_by_agent_id else "system")
        triggered_by_id = actor_id or reopened_by_agent_id
        self._session.add(conversation)
        self._session.add(
            HandoverLog(
                account_id=account_id,
                conversation_id=conversation.id,
                triggered_by_type=triggered_by_type,
                triggered_by_id=triggered_by_id,
                from_mode="ai_managed",
                to_mode="ai_managed",
                reason=reopen_reason,
            )
        )
        self.add_audit_log(
            account_id=account_id,
            actor_type=triggered_by_type,
            actor_id=triggered_by_id,
            action="conversation_reopened",
            target_type="conversation",
            target_id=conversation.external_conversation_id,
            payload={
                "reason": reopen_reason,
                "status_before": status_before,
                "status_after": conversation.status,
                "admin_override": admin_override,
            },
        )
        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def list_audit_logs(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
        allowed_account_ids: set[str] | None = None,
    ) -> list[AuditLog]:
        self._validate_meta_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=allowed_account_ids,
        )
        query = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        if account_id is not None:
            query = query.where(AuditLog.account_id == account_id)
        if actor_type is not None:
            query = query.where(AuditLog.actor_type == actor_type)
        if actor_id is not None:
            query = query.where(AuditLog.actor_id == actor_id)
        if action is not None:
            query = query.where(AuditLog.action == action)
        if target_type is not None:
            query = query.where(AuditLog.target_type == target_type)
        if target_id is not None:
            query = query.where(AuditLog.target_id == target_id)
        if date_from is not None:
            query = query.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
        if date_to is not None:
            query = query.where(
                AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min)
            )
        rows = self._session.scalars(query).all()
        if waba_id is not None:
            rows = [item for item in rows if self._extract_audit_waba_id(item) == waba_id]
        if phone_number_id is not None:
            rows = [
                item
                for item in rows
                if self._extract_audit_phone_number_id(item.payload) == phone_number_id
            ]
        return rows[:limit]

    async def get_effective_ai_status(self, account_id: str, conversation_id: str) -> dict[str, object]:
        account = self._session.get(Account, account_id)
        if account is None:
            raise ValueError(f"Account '{account_id}' was not found.")

        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        global_enabled = self._get_global_ai_enabled()
        blocking_reasons = self._build_ai_blocking_reasons(
            global_enabled=global_enabled,
            account=account,
            conversation=conversation,
        )
        effective_enabled = (
            len(blocking_reasons) == 0
        )
        return ConversationAiStatusResponse(
            account_id=account_id,
            conversation_id=conversation_id,
            phone_number_id=(
                conversation.phone_number.phone_number_id
                if conversation.phone_number is not None
                else None
            ),
            global_ai_enabled=global_enabled,
            account_ai_enabled=account.ai_enabled,
            conversation_ai_enabled=conversation.ai_enabled,
            status=conversation.status,
            management_mode=conversation.management_mode,
            effective_ai_enabled=effective_enabled,
            assigned_agent_id=self.get_public_agent_id(
                conversation.assigned_agent,
                fallback=conversation.assigned_agent_id,
            ),
            blocking_reasons=blocking_reasons,
            primary_blocking_reason=blocking_reasons[0] if blocking_reasons else None,
        ).model_dump()

    async def record_inbound_message(
        self,
        account_id: str,
        conversation_id: str,
        sender_id: str,
        text: str,
        language_code: str,
        translated_text: str | None,
        translated_language_code: str | None,
        payload: dict[str, object],
        message_type: str = "text",
        provider_message_id: str | None = None,
    ) -> Message:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        self._ensure_conversation_phone_number_scope(conversation)
        if conversation.status == "closed":
            conversation.status = "open"
        conversation.last_message_at = utc_now()
        # Sleeping: update last_customer_message_at + auto-wake if sleeping
        conversation.last_customer_message_at = utc_now()
        was_sleeping = conversation.is_sleeping
        if was_sleeping:
            conversation.is_sleeping = False
            # Restore cold messages to hot
            self._session.execute(
                update(Message)
                .where(Message.conversation_id == conversation.id, Message.is_cold.is_(True))
                .values(is_cold=False)
            )
        message = Message(
            account_id=account_id,
            conversation_id=conversation.id,
            phone_number_id=conversation.phone_number_id,
            provider_message_id=provider_message_id or f"mock-in-{uuid4()}",
            direction="inbound",
            message_type=message_type,
            language_code=language_code,
            translated_text=translated_text,
            translated_language_code=translated_language_code,
            sender_id=sender_id,
            recipient_id=account_id,
            content_text=text,
            payload=payload,
            ai_generated=False,
        )
        self._session.add(conversation)
        self._session.add(message)
        event_type = self._resolve_inbound_event_type(payload)
        message_event = MessageEvent(
            account_id=account_id,
            conversation_id=conversation.id,
            message=message,
            event_type=event_type,
            payload=payload,
            **self._resolve_message_event_provider_scope(
                payload=payload,
                conversation=conversation,
                provider_message_id=message.provider_message_id,
                event_type=event_type,
            ),
        )
        self._session.add(message_event)
        self._session.flush()
        self._whatsapp_stats_aggregator.record_message_created(
            message=message,
            conversation=conversation,
        )
        self._session.commit()
        self._session.refresh(message)
        return message

    # ── Sleeping Conversation ──────────────────────────────────────────

    async def mark_sleeping(
        self,
        account_id: str,
        conversation_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> ConversationRuntimeState:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        if conversation.is_sleeping:
            return self._serialize_conversation(conversation)
        conversation.is_sleeping = True
        # Mark messages older than 48h as cold
        threshold = utc_now() - timedelta(hours=48)
        self._session.execute(
            update(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.is_cold.is_(False),
                Message.created_at < threshold,
            )
            .values(is_cold=True)
        )
        self._session.add(conversation)
        self.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="conversation_sleeping",
            target_type="conversation",
            target_id=conversation.external_conversation_id,
            payload={"is_sleeping": True},
        )
        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def wake_conversation(
        self,
        account_id: str,
        conversation_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> ConversationRuntimeState:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        if not conversation.is_sleeping:
            return self._serialize_conversation(conversation)
        conversation.is_sleeping = False
        conversation.last_customer_message_at = utc_now()
        # Restore all cold messages back to hot
        self._session.execute(
            update(Message)
            .where(Message.conversation_id == conversation.id, Message.is_cold.is_(True))
            .values(is_cold=False)
        )
        self._session.add(conversation)
        self.add_audit_log(
            account_id=account_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="conversation_woken",
            target_type="conversation",
            target_id=conversation.external_conversation_id,
            payload={"is_sleeping": False},
        )
        self._session.commit()
        self._session.refresh(conversation)
        return self._serialize_conversation(conversation)

    async def record_outbound_message(
        self,
        account_id: str,
        conversation_id: str,
        recipient_id: str,
        text: str | None,
        language_code: str | None,
        translated_text: str | None,
        translated_language_code: str | None,
        delivery_mode: str,
        ai_generated: bool,
        payload: dict[str, object],
        message_type: str = "text",
        sent_by_agent_id: str | None = None,
        provider_message_id: str | None = None,
        # ── 归属快照（spec 5.9 / 8.4） ──
        actor_type: str | None = None,
        actor_id: str | None = None,
        ai_agent_id: str | None = None,
        ai_assignment_id_snapshot: str | None = None,
        source_entry_link_id_snapshot: str | None = None,
        owner_agency_id_snapshot: str | None = None,
        owner_staff_user_id_snapshot: str | None = None,
        owner_agency_member_id_snapshot: str | None = None,
        owner_assignment_id_snapshot: str | None = None,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        ai_prompt_version: str | None = None,
        source_job_id: str | None = None,
        failover_from_ai_agent_id: str | None = None,
        failover_reason: str | None = None,
    ) -> Message:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        self._ensure_conversation_phone_number_scope(conversation)
        conversation.last_message_at = utc_now()
        resolved_actor_type = actor_type
        if resolved_actor_type is None:
            # 默认口径：AI 自动消息 = ai_agent；echo = system；其他 = system
            if ai_generated or (ai_agent_id is not None):
                resolved_actor_type = "ai_agent"
            else:
                resolved_actor_type = "system"
        resolved_ai_agent_id = ai_agent_id
        if resolved_ai_agent_id is None and ai_generated:
            resolved_ai_agent_id = conversation.current_ai_agent_id
        message = Message(
            account_id=account_id,
            conversation_id=conversation.id,
            phone_number_id=conversation.phone_number_id,
            provider_message_id=provider_message_id or f"mock-out-{uuid4()}",
            direction="outbound",
            message_type=message_type,
            language_code=language_code,
            translated_text=translated_text,
            translated_language_code=translated_language_code,
            sender_id=account_id,
            recipient_id=recipient_id,
            content_text=text,
            payload=payload,
            ai_generated=ai_generated,
            sent_by_agent_id=sent_by_agent_id,
            # ── 归属快照写入 ──
            actor_type=resolved_actor_type,
            actor_id=actor_id or resolved_ai_agent_id,
            ai_agent_id=resolved_ai_agent_id,
            ai_assignment_id_snapshot=ai_assignment_id_snapshot or conversation.current_ai_assignment_id,
            source_entry_link_id_snapshot=source_entry_link_id_snapshot or conversation.current_entry_link_id,
            owner_agency_id_snapshot=owner_agency_id_snapshot or conversation.current_owner_agency_id_snapshot,
            owner_staff_user_id_snapshot=owner_staff_user_id_snapshot or conversation.current_owner_staff_user_id_snapshot,
            owner_agency_member_id_snapshot=owner_agency_member_id_snapshot or conversation.current_owner_agency_member_id_snapshot,
            owner_assignment_id_snapshot=owner_assignment_id_snapshot or conversation.current_owner_assignment_id_snapshot,
            ai_provider=ai_provider,
            ai_model=ai_model,
            ai_prompt_version=ai_prompt_version,
            source_job_id=source_job_id,
            delivery_mode=delivery_mode,
            failover_from_ai_agent_id=failover_from_ai_agent_id or conversation.ai_failover_from_agent_id,
            failover_reason=failover_reason or conversation.ai_failover_reason,
        )
        self._session.add(conversation)
        self._session.add(message)
        message_event = MessageEvent(
            account_id=account_id,
            conversation_id=conversation.id,
            message=message,
            event_type=delivery_mode,
            payload=payload,
            **self._resolve_message_event_provider_scope(
                payload=payload,
                conversation=conversation,
                provider_message_id=message.provider_message_id,
                event_type=delivery_mode,
            ),
        )
        self._session.add(message_event)
        self._session.flush()
        self._whatsapp_stats_aggregator.record_message_created(
            message=message,
            conversation=conversation,
        )
        self._session.commit()
        self._session.refresh(message)
        return message

    async def record_queue_event(
        self,
        account_id: str,
        conversation_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        self._session.add(
            MessageEvent(
                account_id=account_id,
                conversation_id=conversation.id,
                event_type=event_type,
                payload=payload,
                **self._resolve_message_event_provider_scope(
                    payload=payload,
                    conversation=conversation,
                    provider_message_id=None,
                    event_type=event_type,
                ),
            )
        )
        self._session.commit()

    async def record_provider_status_event(
        self,
        *,
        account_id: str,
        update: ProviderStatusUpdate,
    ) -> bool:
        message = self._get_message_by_provider_message_id(
            account_id=account_id,
            provider_message_id=update.provider_message_id,
        )
        if message is None:
            self._record_unmatched_provider_status_event(
                account_id=account_id,
                update=update,
            )
            return False
        if not self._provider_status_matches_message_scope(message=message, update=update):
            self._record_unmatched_provider_status_event(
                account_id=account_id,
                update=update,
            )
            return False

        previous_message_payload = dict(message.payload) if isinstance(message.payload, dict) else {}
        provider_payload = dict(update.payload) if isinstance(update.payload, dict) else {}
        updated_message_payload = {
            **previous_message_payload,
            **provider_payload,
        }
        if updated_message_payload != previous_message_payload:
            message.payload = updated_message_payload
            self._session.add(message)

        resolved_conversation = message.conversation
        if resolved_conversation is None:
            resolved_conversation = self._session.get(Conversation, message.conversation_id)

        payload = self._build_provider_status_event_payload(
            update=update,
            provider_payload=updated_message_payload,
            extra_payload=self._build_conversation_identity_payload(resolved_conversation),
        )
        provider_event_id = self._build_provider_status_event_id(update)
        provider_occurred_at = self._parse_provider_occurred_at(update.occurred_at)
        resolved_update_waba_id, resolved_update_phone_number_id = (
            self._resolve_provider_status_update_scope(update)
        )
        message_scope_waba_id, message_scope_phone_number_id = (
            self._resolve_message_scope_identifiers(message)
        )
        status_event_waba_id = resolved_update_waba_id or message_scope_waba_id
        status_event_phone_number_id = (
            resolved_update_phone_number_id or message_scope_phone_number_id
        )
        payload["waba_id"] = status_event_waba_id
        payload["phone_number_id"] = status_event_phone_number_id
        status_event: MessageEvent | None = None
        status_event_created = False
        for event in message.events:
            if event.event_type != f"{update.provider_name}_status_{update.external_status}":
                continue
            if not isinstance(event.payload, dict):
                continue
            if (
                event.payload.get("provider_message_id") == update.provider_message_id
                and event.payload.get("external_status") == update.external_status
            ):
                status_event = event
                status_event.provider_name = update.provider_name
                status_event.waba_id = status_event_waba_id
                status_event.phone_number_id = status_event_phone_number_id
                status_event.provider_event_id = provider_event_id
                status_event.occurred_at = provider_occurred_at
                self._session.add(status_event)
                break
        if status_event is None:
            self._whatsapp_stats_aggregator.reclassify_message_dimensions(
                message=message,
                previous_payload=previous_message_payload,
                conversation=message.conversation,
            )
            status_event = MessageEvent(
                account_id=account_id,
                conversation_id=message.conversation_id,
                message_id=message.id,
                event_type=f"{update.provider_name}_status_{update.external_status}",
                provider_name=update.provider_name,
                waba_id=status_event_waba_id,
                phone_number_id=status_event_phone_number_id,
                provider_event_id=provider_event_id,
                occurred_at=provider_occurred_at,
                payload=payload,
            )
            self._session.add(status_event)
            status_event_created = True
            message_delivery_events_total.labels(
                provider=update.provider_name,
                status=update.external_status.lower(),
            ).inc()

        template_send_log = self._get_template_send_log_by_message_id(
            account_id=account_id,
            message_id=update.provider_message_id,
        )
        template_status_transitioned = False
        if template_send_log is not None:
            transition_snapshot = self._template_stats_aggregator.capture_transition_snapshot(
                template_send_log
            )
            mapped_status = self._map_template_send_status(update.external_status)
            effective_status = self._resolve_template_send_status_transition(
                current_status=template_send_log.status,
                incoming_status=mapped_status,
            )
            template_send_log.status = effective_status
            if effective_status == mapped_status:
                template_send_log.error_code = update.error_code
            template_send_log.conversation_origin_type = self._pick_optional_string(
                payload,
                "conversation_origin_type",
            )
            template_send_log.conversation_category = self._pick_optional_string(
                payload,
                "conversation_category",
            )
            template_send_log.pricing_model = self._pick_optional_string(
                payload,
                "pricing_model",
            )
            template_send_log.billable = bool(payload.get("billable", template_send_log.billable))
            provider_estimated_cost = self._extract_estimated_cost(payload)
            if provider_estimated_cost > 0:
                template_send_log.estimated_cost = Decimal(str(provider_estimated_cost))
            template_send_log.last_status_at = provider_occurred_at
            if mapped_status == "DELIVERED":
                template_send_log.delivered_at = template_send_log.last_status_at or utc_now()
            elif mapped_status == "READ":
                template_send_log.read_at = template_send_log.last_status_at or utc_now()
                if template_send_log.delivered_at is None:
                    template_send_log.delivered_at = template_send_log.read_at
            elif mapped_status == "FAILED":
                template_send_log.failed_at = template_send_log.last_status_at or utc_now()
            self._session.add(template_send_log)
            self._template_stats_aggregator.record_status_transition(
                template_send_log,
                transition_snapshot,
            )
            template_status_transitioned = (
                (template_send_log.delivered_at is not None and not transition_snapshot.had_delivered_at)
                or (template_send_log.read_at is not None and not transition_snapshot.had_read_at)
                or (template_send_log.failed_at is not None and not transition_snapshot.had_failed_at)
            )
            if template_status_transitioned:
                business_template_sends_total.labels(
                    provider=update.provider_name,
                    status=effective_status,
                ).inc()
                if effective_status == "FAILED":
                    business_template_send_failures_total.labels(
                        provider=update.provider_name,
                        reason=update.error_code or "provider_failed",
                    ).inc()

        self._session.flush()
        if status_event_created:
            self._whatsapp_stats_aggregator.record_status_event(
                event=status_event,
                message=message,
                conversation=message.conversation,
            )
        if status_event_created or template_status_transitioned:
            self._media_asset_telemetry.record_provider_status_update(
                account_id=account_id,
                update=update,
                message=message,
                conversation=message.conversation,
                template_send_log=template_send_log,
            )
        self._session.commit()
        return True

    @staticmethod
    def _build_conversation_identity_payload(
        conversation: Conversation | None,
    ) -> dict[str, str | None]:
        if conversation is None:
            return {}
        external_conversation_id = conversation.external_conversation_id
        return {
            "conversation_id": external_conversation_id,
            "external_conversation_id": external_conversation_id,
            "internal_conversation_id": conversation.id,
        }

    async def replay_unmatched_provider_status_events(
        self,
        *,
        account_id: str,
        provider_message_id: str | None,
    ) -> int:
        if not provider_message_id:
            return 0

        unmatched_events = self._find_unmatched_provider_status_events(
            account_id=account_id,
            provider_message_id=provider_message_id,
        )
        touched_scopes: set[tuple[str, str, str | None, str | None]] = set()
        replayed_count = 0
        for buffered_event in unmatched_events:
            update = self._provider_status_update_from_unmatched_event(buffered_event)
            if update is None:
                continue
            matched = await self.record_provider_status_event(
                account_id=account_id,
                update=update,
            )
            if not matched:
                continue
            status_event = self._get_message_status_event(
                account_id=account_id,
                provider_name=update.provider_name,
                provider_message_id=update.provider_message_id,
                external_status=update.external_status,
            )
            buffered_event.replay_state = "replayed"
            buffered_event.replayed_at = utc_now()
            buffered_event.replayed_message_event_id = status_event.id if status_event else None
            buffered_event.replay_error = None
            self._session.add(buffered_event)
            touched_scopes.add(self._provider_status_buffer_scope(buffered_event))
            provider_status_event_buffer_events_total.labels(
                **self._provider_status_buffer_metric_labels(
                    provider_name=buffered_event.provider_name,
                    account_id=buffered_event.account_id,
                    waba_id=buffered_event.waba_id,
                    phone_number_id=buffered_event.phone_number_id,
                ),
                outcome="applied",
            ).inc()
            replayed_count += 1
        if replayed_count > 0:
            self._session.commit()
            for scope in touched_scopes:
                self._refresh_provider_status_buffer_pending_metrics(
                    provider_name=scope[0],
                    account_id=scope[1],
                    waba_id=scope[2],
                    phone_number_id=scope[3],
                )
        return replayed_count

    async def count_provider_status_buffer_events(
        self,
        *,
        account_id: str | None = None,
        replay_state: str = "pending",
        account_ids: set[str] | None = None,
        provider_name: str | None = None,
        provider_message_id: str | None = None,
        external_status: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> dict[str, int]:
        self._validate_meta_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=account_ids,
        )
        query = select(ProviderStatusEventBuffer).where(
            ProviderStatusEventBuffer.replay_state == replay_state,
        )
        if account_ids is not None:
            if not account_ids:
                return {}
            query = query.where(ProviderStatusEventBuffer.account_id.in_(account_ids))
        if account_id is not None:
            query = query.where(ProviderStatusEventBuffer.account_id == account_id)
        if provider_name is not None:
            query = query.where(ProviderStatusEventBuffer.provider_name == provider_name)
        if provider_message_id is not None:
            query = query.where(
                ProviderStatusEventBuffer.provider_message_id == provider_message_id
            )
        if external_status is not None:
            query = query.where(ProviderStatusEventBuffer.external_status == external_status)
        buffered_events = self._session.scalars(query).all()
        counts: dict[str, int] = {}
        for event in buffered_events:
            if not self._provider_status_buffer_matches_scope_filters(
                event=event,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
            ):
                continue
            counts[event.account_id] = counts.get(event.account_id, 0) + 1
        return counts

    async def list_provider_status_buffer_events(
        self,
        *,
        account_id: str | None = None,
        account_ids: set[str] | None = None,
        provider_name: str | None = None,
        provider_message_id: str | None = None,
        external_status: str | None = None,
        replay_state: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        limit: int = 100,
        oldest_first: bool = False,
    ) -> list[ProviderStatusEventBuffer]:
        self._validate_meta_scope_filters(
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            allowed_account_ids=account_ids,
        )
        query = select(ProviderStatusEventBuffer)
        if account_ids is not None:
            if not account_ids:
                return []
            query = query.where(ProviderStatusEventBuffer.account_id.in_(account_ids))
        if account_id is not None:
            query = query.where(ProviderStatusEventBuffer.account_id == account_id)
        if provider_name is not None:
            query = query.where(ProviderStatusEventBuffer.provider_name == provider_name)
        if provider_message_id is not None:
            query = query.where(
                ProviderStatusEventBuffer.provider_message_id == provider_message_id
            )
        if external_status is not None:
            query = query.where(ProviderStatusEventBuffer.external_status == external_status)
        if replay_state is not None:
            query = query.where(ProviderStatusEventBuffer.replay_state == replay_state)
        ordering = (
            (
                ProviderStatusEventBuffer.first_seen_at.asc(),
                ProviderStatusEventBuffer.last_seen_at.asc(),
                ProviderStatusEventBuffer.id.asc(),
            )
            if oldest_first
            else (
                ProviderStatusEventBuffer.last_seen_at.desc(),
                ProviderStatusEventBuffer.first_seen_at.desc(),
                ProviderStatusEventBuffer.id.desc(),
            )
        )
        rows = list(self._session.scalars(query.order_by(*ordering)).all())
        filtered_rows = [
            event
            for event in rows
            if self._provider_status_buffer_matches_scope_filters(
                event=event,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
            )
        ]
        return filtered_rows[:limit]

    async def replay_provider_status_buffer_events(
        self,
        *,
        account_id: str,
        provider_name: str | None = None,
        provider_message_id: str | None = None,
        external_status: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        limit: int = 100,
    ) -> tuple[int, int]:
        pending_events = await self.list_provider_status_buffer_events(
            account_id=account_id,
            account_ids={account_id},
            provider_name=provider_name,
            provider_message_id=provider_message_id,
            external_status=external_status,
            replay_state="pending",
            waba_id=waba_id,
            phone_number_id=phone_number_id,
            limit=limit,
        )
        touched_scopes: set[tuple[str, str, str | None, str | None]] = set()
        replayed_count = 0
        for buffered_event in pending_events:
            update = self._provider_status_update_from_unmatched_event(buffered_event)
            if update is None:
                buffered_event.replay_error = "buffer_payload_invalid"
                self._session.add(buffered_event)
                continue
            message = self._get_message_by_provider_message_id(
                account_id=account_id,
                provider_message_id=update.provider_message_id,
            )
            if message is None:
                buffered_event.replay_error = "matching_message_not_found"
                self._session.add(buffered_event)
                continue
            if not self._provider_status_matches_message_scope(message=message, update=update):
                buffered_event.replay_error = "message_scope_mismatch"
                self._session.add(buffered_event)
                continue
            matched = await self.record_provider_status_event(
                account_id=account_id,
                update=update,
            )
            if not matched:
                buffered_event.replay_error = "matching_message_not_found"
                self._session.add(buffered_event)
                continue
            status_event = self._get_message_status_event(
                account_id=account_id,
                provider_name=update.provider_name,
                provider_message_id=update.provider_message_id,
                external_status=update.external_status,
            )
            buffered_event.replay_state = "replayed"
            buffered_event.replayed_at = utc_now()
            buffered_event.replayed_message_event_id = status_event.id if status_event else None
            buffered_event.replay_error = None
            self._session.add(buffered_event)
            touched_scopes.add(self._provider_status_buffer_scope(buffered_event))
            provider_status_event_buffer_events_total.labels(
                **self._provider_status_buffer_metric_labels(
                    provider_name=buffered_event.provider_name,
                    account_id=buffered_event.account_id,
                    waba_id=buffered_event.waba_id,
                    phone_number_id=buffered_event.phone_number_id,
                ),
                outcome="applied",
            ).inc()
            replayed_count += 1
        if pending_events:
            self._session.commit()
        for scope in touched_scopes:
            self._refresh_provider_status_buffer_pending_metrics(
                provider_name=scope[0],
                account_id=scope[1],
                waba_id=scope[2],
                phone_number_id=scope[3],
            )
        return len(pending_events), replayed_count

    async def list_conversation_models(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        assigned_agent_id: str | None = None,
        status: str | None = None,
        management_mode: str | None = None,
        is_sleeping: bool | None = None,
        agency_id: str | None = None,
        *,
        sort_by: str | None = None,
        sort_desc: bool = True,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Conversation]:
        query = self._conversation_query(sort_by=sort_by, sort_desc=sort_desc)
        if account_id is not None:
            query = query.where(Conversation.account_id == account_id)
        if agency_id is not None:
            agency_account_ids = select(H5Site.account_id).where(H5Site.agency_id == agency_id)
            query = query.where(Conversation.account_id.in_(agency_account_ids))
        if waba_id is not None:
            query = query.where(
                Conversation.phone_number.has(
                    WhatsAppPhoneNumber.waba_account.has(
                        WhatsAppBusinessAccount.waba_id == waba_id,
                    )
                )
            )
        if phone_number_id is not None:
            query = query.where(
                Conversation.phone_number.has(
                    WhatsAppPhoneNumber.phone_number_id == phone_number_id,
                )
            )
        if assigned_agent_id is not None:
            query = query.join(Conversation.assigned_agent).where(
                or_(
                    Agent.agent_key == assigned_agent_id,
                    Conversation.assigned_agent_id == assigned_agent_id,
                )
            )
        if status is not None:
            query = query.where(Conversation.status == status)
        if management_mode is not None:
            query = query.where(Conversation.management_mode == management_mode)
        if is_sleeping is not None:
            query = query.where(Conversation.is_sleeping.is_(is_sleeping))
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return self._session.scalars(query).all()

    async def count_conversation_models(
        self,
        account_id: str | None = None,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
        assigned_agent_id: str | None = None,
        status: str | None = None,
        management_mode: str | None = None,
        is_sleeping: bool | None = None,
        agency_id: str | None = None,
    ) -> int:
        """Count conversations matching filters (for pagination total)."""
        from sqlalchemy import func
        query = select(func.count()).select_from(Conversation)
        if account_id is not None:
            query = query.where(Conversation.account_id == account_id)
        if agency_id is not None:
            agency_account_ids = select(H5Site.account_id).where(H5Site.agency_id == agency_id)
            query = query.where(Conversation.account_id.in_(agency_account_ids))
        if waba_id is not None:
            query = query.where(
                Conversation.phone_number.has(
                    WhatsAppPhoneNumber.waba_account.has(
                        WhatsAppBusinessAccount.waba_id == waba_id,
                    )
                )
            )
        if phone_number_id is not None:
            query = query.where(
                Conversation.phone_number.has(
                    WhatsAppPhoneNumber.phone_number_id == phone_number_id,
                )
            )
        if assigned_agent_id is not None:
            query = query.join(Conversation.assigned_agent).where(
                or_(
                    Agent.agent_key == assigned_agent_id,
                    Conversation.assigned_agent_id == assigned_agent_id,
                )
            )
        if status is not None:
            query = query.where(Conversation.status == status)
        if management_mode is not None:
            query = query.where(Conversation.management_mode == management_mode)
        if is_sleeping is not None:
            query = query.where(Conversation.is_sleeping.is_(is_sleeping))
        return self._session.scalar(query) or 0

    async def list_message_models(self, account_id: str, conversation_id: str, *, offset: int = 0, limit: int | None = None, include_cold: bool = False) -> list[Message]:
        conversation = self._get_conversation_with_phone(account_id=account_id, conversation_id=conversation_id)
        if conversation is None:
            raise LookupError(
                f"Conversation '{conversation_id}' for account '{account_id}' was not found."
            )
        # Cache conversation scope for serialization (avoids per-message phone_number JOIN)
        phone_number = conversation.phone_number
        self._conv_waba_id: str | None = phone_number.waba_id if phone_number else None
        self._conv_phone_number_id: str | None = phone_number.phone_number_id if phone_number else None
        query = (
            select(Message)
            .where(Message.conversation_id == conversation.id)
        )
        if not include_cold:
            query = query.where(Message.is_cold.is_(False))
        query = query.order_by(Message.created_at.desc(), Message.id.desc())
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        messages = self._session.scalars(query).all()
        # Return in chronological order (oldest first) for UI display
        return list(reversed(messages))

    async def list_latest_messages_batch(
        self,
        conv_db_ids: list[str],
    ) -> dict[str, Message | None]:
        """Get the latest message for each conversation DB ID in a single query.

        Uses PostgreSQL DISTINCT ON to return one message per conversation.
        Returns dict mapping conversation_db_id → latest Message (or None).
        """
        if not conv_db_ids:
            return {}
        # DISTINCT ON gives us the first row per group after ordering
        stmt = (
            select(Message)
            .where(Message.conversation_id.in_(conv_db_ids))
            .order_by(Message.conversation_id, Message.created_at.desc(), Message.id.desc())
            .distinct(Message.conversation_id)
        )
        rows = self._session.scalars(stmt).all()
        result: dict[str, Message | None] = {cid: None for cid in conv_db_ids}
        for row in rows:
            result[row.conversation_id] = row
        return result

    async def list_latest_inbound_messages_batch(
        self,
        conv_db_ids: list[str],
    ) -> dict[str, Message | None]:
        """Get the latest inbound message for each conversation DB ID in a single query."""
        if not conv_db_ids:
            return {}
        stmt = (
            select(Message)
            .where(
                Message.conversation_id.in_(conv_db_ids),
                Message.direction == "inbound",
            )
            .order_by(Message.conversation_id, Message.created_at.desc(), Message.id.desc())
            .distinct(Message.conversation_id)
        )
        rows = self._session.scalars(stmt).all()
        result: dict[str, Message | None] = {cid: None for cid in conv_db_ids}
        for row in rows:
            result[row.conversation_id] = row
        return result

    @property
    def conv_waba_id(self) -> str | None:
        return getattr(self, '_conv_waba_id', None)

    @property
    def conv_phone_number_id(self) -> str | None:
        return getattr(self, '_conv_phone_number_id', None)

    async def list_message_event_models(
        self,
        account_id: str,
        conversation_id: str,
        *,
        message_ids: list[str] | None = None,
    ) -> list[MessageEvent]:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        stmt = select(MessageEvent).where(MessageEvent.conversation_id == conversation.id)
        if message_ids:
            stmt = stmt.where(MessageEvent.message_id.in_(message_ids))
        else:
            stmt = stmt.order_by(MessageEvent.created_at.desc(), MessageEvent.id.desc())
        return self._session.scalars(stmt).all()

    async def list_handover_logs(
        self,
        account_id: str,
        conversation_id: str,
    ) -> list[HandoverLog]:
        conversation = self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        return self._session.scalars(
            select(HandoverLog)
            .where(HandoverLog.conversation_id == conversation.id)
            .order_by(HandoverLog.created_at.desc(), HandoverLog.id.desc())
        ).all()

    async def list_conversation_audit_logs(
        self,
        account_id: str,
        conversation_id: str,
        limit: int = 100,
    ) -> list[AuditLog]:
        self._require_conversation(account_id=account_id, conversation_id=conversation_id)
        return self._session.scalars(
            select(AuditLog)
            .where(
                AuditLog.account_id == account_id,
                AuditLog.target_type == "conversation",
                AuditLog.target_id == conversation_id,
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        ).all()

    async def get_conversation_model(self, account_id: str, conversation_id: str) -> Conversation:
        return self._require_conversation(account_id=account_id, conversation_id=conversation_id)

    def get_account_model(self, account_id: str) -> Account | None:
        return self._session.get(Account, account_id)

    def ensure_account_active(self, account_id: str) -> Account:
        account = self.get_account_model(account_id)
        if account is None:
            raise LookupError(f"Account '{account_id}' was not found.")
        if not account.is_active:
            raise ValueError(f"Account '{account_id}' is inactive.")
        return account

    def ensure_conversation_messaging_available(self, conversation: Conversation) -> None:
        self._ensure_conversation_phone_number_scope(conversation)
        account = self.ensure_account_active(conversation.account_id)
        phone_number = conversation.phone_number
        if phone_number is None:
            return
        waba_account = phone_number.waba_account
        if waba_account is not None and not waba_account.is_active:
            raise ValueError(f"WABA '{waba_account.waba_id}' is inactive.")
        if not phone_number.is_active:
            raise ValueError(f"Phone number '{phone_number.phone_number_id}' is inactive.")
        if waba_account is not None and not waba_account.access_token:
            raise ValueError(
                f"WABA '{waba_account.waba_id}' is missing access token for outbound messaging."
            )
        if not phone_number.is_registered:
            raise ValueError(
                f"Phone number '{phone_number.phone_number_id}' is not registered for outbound messaging."
            )

    def get_phone_number_in_scope(
        self,
        *,
        account_id: str,
        waba_id: str | None,
        provider_phone_number_id: str | None,
        include_inactive: bool = False,
    ) -> WhatsAppPhoneNumber | None:
        if not provider_phone_number_id:
            return None
        query = (
            select(WhatsAppPhoneNumber)
            .options(selectinload(WhatsAppPhoneNumber.waba_account))
            .where(
                WhatsAppPhoneNumber.phone_number_id == provider_phone_number_id,
                or_(
                    WhatsAppPhoneNumber.account_id == account_id,
                    WhatsAppPhoneNumber.waba_account.has(
                        WhatsAppBusinessAccount.account_id == account_id
                    ),
                ),
            )
        )
        if waba_id is not None:
            query = query.where(
                or_(
                    WhatsAppPhoneNumber.waba_id == waba_id,
                    WhatsAppPhoneNumber.waba_account.has(
                        WhatsAppBusinessAccount.waba_id == waba_id
                    ),
                )
            )
        if not include_inactive:
            query = query.where(
                WhatsAppPhoneNumber.is_active.is_(True),
            )
            query = query.where(
                or_(
                    WhatsAppPhoneNumber.waba_account_id.is_(None),
                    WhatsAppPhoneNumber.waba_account.has(
                        WhatsAppBusinessAccount.is_active.is_(True)
                    ),
                )
            )
        return self._session.scalars(query).first()

    async def get_message_model_by_provider_message_id(
        self,
        account_id: str,
        provider_message_id: str,
    ) -> Message | None:
        return self._get_message_by_provider_message_id(
            account_id=account_id,
            provider_message_id=provider_message_id,
        )

    async def get_outbound_message_by_source_job_id(
        self,
        *,
        account_id: str,
        conversation_id: str,
        source_job_id: str,
    ) -> Message | None:
        messages = await self.list_message_models(account_id=account_id, conversation_id=conversation_id)
        for message in reversed(messages):
            if message.direction != "outbound":
                continue
            if not isinstance(message.payload, dict):
                continue
            if message.payload.get("source_job_id") == source_job_id:
                return message
        return None

    def add_audit_log(
        self,
        account_id: str | None,
        actor_type: str,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str | None,
        payload: dict[str, object] | None,
    ) -> None:
        self._session.add(
            AuditLog(
                account_id=account_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                payload=payload,
            )
        )

    def commit(self) -> None:
        self._session.commit()

    def _get_global_ai_enabled(self) -> bool:
        setting = self._get_or_create_global_setting()
        if not setting.value_json:
            return True
        return bool(setting.value_json.get("enabled", True))

    def _get_or_create_global_setting(self) -> SystemSetting:
        setting = self._session.get(SystemSetting, GLOBAL_AI_SETTING_KEY)
        if setting is None:
            setting = SystemSetting(key=GLOBAL_AI_SETTING_KEY, value_json={"enabled": True})
            self._session.add(setting)
            self._session.commit()
            self._session.refresh(setting)
        return setting

    def _conversation_query(self, *, sort_by: str | None = None, sort_desc: bool = True) -> Select[tuple[Conversation]]:
        order_col = Conversation.last_message_at
        if sort_by:
            col = getattr(Conversation, sort_by, None)
            if col is not None:
                order_col = col
        ordering = order_col.desc() if sort_desc else order_col.asc()
        return (
            select(Conversation)
            .options(selectinload(Conversation.assigned_agent))
            .options(
                selectinload(Conversation.phone_number).selectinload(
                    WhatsAppPhoneNumber.waba_account
                )
            )
            .order_by(ordering, Conversation.external_conversation_id)
        )

    def _get_conversation(self, account_id: str, conversation_id: str) -> Conversation | None:
        return self._session.scalars(
            select(Conversation).where(
                Conversation.account_id == account_id,
                Conversation.external_conversation_id == conversation_id,
            )
        ).first()

    def _get_conversation_with_phone(self, account_id: str, conversation_id: str) -> Conversation | None:
        return self._session.scalars(
            select(Conversation)
            .options(selectinload(Conversation.phone_number))
            .where(
                Conversation.account_id == account_id,
                Conversation.external_conversation_id == conversation_id,
            )
        ).first()

    def _require_conversation(self, account_id: str, conversation_id: str) -> Conversation:
        conversation = self._get_conversation(account_id=account_id, conversation_id=conversation_id)
        if conversation is None:
            raise LookupError(
                f"Conversation '{conversation_id}' for account '{account_id}' was not found."
            )
        return conversation

    def _find_agent(self, *, account_id: str | None, agent_id: str) -> Agent | None:
        if account_id is not None:
            scoped_agent = self._session.scalars(
                select(Agent).where(
                    Agent.account_id == account_id,
                    Agent.agent_key == agent_id,
                )
            ).first()
            if scoped_agent is not None:
                return scoped_agent
        legacy_agent = self._session.scalars(
            select(Agent).where(
                Agent.account_id.is_(None),
                or_(
                    Agent.agent_key == agent_id,
                    Agent.id == agent_id,
                ),
            )
        ).first()
        if legacy_agent is not None:
            return legacy_agent
        return self._session.get(Agent, agent_id) if account_id is None else None

    def _find_registered_agent(self, *, account_id: str | None, agent_id: str) -> Agent | None:
        if account_id is None:
            return self._find_agent(account_id=None, agent_id=agent_id)
        return self._session.scalars(
            select(Agent).where(
                Agent.account_id == account_id,
                Agent.agent_key == agent_id,
            )
        ).first()

    def _format_agent_not_found(self, *, account_id: str | None, agent_id: str) -> str:
        if account_id is None:
            return f"Agent '{agent_id}' was not found."
        return f"Agent '{agent_id}' was not found for account '{account_id}'."

    def _require_agent(self, *, account_id: str | None, agent_id: str) -> Agent:
        agent = self._find_agent(account_id=account_id, agent_id=agent_id)
        if agent is None:
            raise LookupError(self._format_agent_not_found(account_id=account_id, agent_id=agent_id))
        return agent

    @staticmethod
    def get_public_agent_id(agent: Agent | None, fallback: str | None = None) -> str | None:
        if agent is None:
            return fallback
        return agent.agent_key or fallback or agent.id

    def resolve_agent_storage_id(self, *, account_id: str, agent_id: str | None) -> str | None:
        if agent_id is None:
            return None
        agent = self._find_agent(account_id=account_id, agent_id=agent_id)
        if agent is None:
            return agent_id
        return agent.id

    def _get_phone_number_by_provider_id(
        self,
        *,
        account_id: str,
        provider_phone_number_id: str | None,
    ) -> WhatsAppPhoneNumber | None:
        return self.get_phone_number_in_scope(
            account_id=account_id,
            waba_id=None,
            provider_phone_number_id=provider_phone_number_id,
        )

    def _get_message_by_provider_message_id(
        self,
        *,
        account_id: str,
        provider_message_id: str,
    ) -> Message | None:
        return self._session.scalars(
            select(Message).where(
                Message.account_id == account_id,
                Message.provider_message_id == provider_message_id,
            )
        ).first()

    def _ensure_conversation_phone_number_scope(self, conversation: Conversation) -> None:
        phone_number = conversation.phone_number
        if phone_number is None:
            return
        if phone_number.account_id != conversation.account_id:
            raise ValueError(
                "Conversation "
                f"'{conversation.external_conversation_id}' references phone number "
                f"'{phone_number.phone_number_id}' from account '{phone_number.account_id}', "
                f"not '{conversation.account_id}'."
            )
        waba_account = phone_number.waba_account
        if waba_account is None:
            return
        if waba_account.account_id != conversation.account_id:
            raise ValueError(
                "Conversation "
                f"'{conversation.external_conversation_id}' references phone number "
                f"'{phone_number.phone_number_id}' through WABA '{waba_account.waba_id}' "
                f"owned by account '{waba_account.account_id}', not '{conversation.account_id}'."
            )

    def _provider_status_matches_message_scope(
        self,
        *,
        message: Message,
        update: ProviderStatusUpdate,
    ) -> bool:
        update_waba_id, update_phone_number_id = self._resolve_provider_status_update_scope(
            update
        )
        message_waba_id, message_phone_number_id = self._resolve_message_scope_identifiers(
            message
        )
        if (
            update_phone_number_id is not None
            and message_phone_number_id != update_phone_number_id
        ):
            return False
        if update_waba_id is not None and message_waba_id != update_waba_id:
            return False
        return True

    def _resolve_message_scope_identifiers(
        self,
        message: Message,
    ) -> tuple[str | None, str | None]:
        payload = message.payload if isinstance(message.payload, dict) else {}
        snapshot_waba_id = self._pick_nested_optional_string(payload, "waba_id")
        snapshot_phone_number_id = self._pick_nested_optional_string(payload, "phone_number_id")
        phone_number = message.phone_number
        current_phone_number_id = (
            phone_number.phone_number_id if phone_number is not None else None
        )
        current_waba_id = self._resolve_phone_waba_id(phone_number)
        return (
            snapshot_waba_id or current_waba_id,
            snapshot_phone_number_id or current_phone_number_id,
        )

    def _get_template_send_log_by_message_id(
        self,
        *,
        account_id: str,
        message_id: str,
    ) -> TemplateSendLog | None:
        return self._session.scalars(
            select(TemplateSendLog).where(
                TemplateSendLog.account_id == account_id,
                TemplateSendLog.message_id == message_id,
            )
        ).first()

    def _record_unmatched_provider_status_event(
        self,
        *,
        account_id: str,
        update: ProviderStatusUpdate,
    ) -> None:
        now = utc_now()
        resolved_waba_id, resolved_phone_number_id = self._resolve_provider_status_update_scope(
            update
        )
        buffered_event = self._session.scalars(
            select(ProviderStatusEventBuffer).where(
                ProviderStatusEventBuffer.account_id == account_id,
                ProviderStatusEventBuffer.provider_name == update.provider_name,
                ProviderStatusEventBuffer.provider_message_id == update.provider_message_id,
                ProviderStatusEventBuffer.external_status == update.external_status,
            )
        ).first()
        previous_scope = (
            self._provider_status_buffer_scope(buffered_event)
            if buffered_event is not None
            else None
        )
        if buffered_event is None:
            buffered_event = ProviderStatusEventBuffer(
                account_id=account_id,
                provider_name=update.provider_name,
                waba_id=resolved_waba_id,
                phone_number_id=resolved_phone_number_id,
                provider_message_id=update.provider_message_id,
                external_status=update.external_status,
                recipient_id=update.recipient_id,
                occurred_at=update.occurred_at,
                error_code=update.error_code,
                payload=dict(update.payload),
                first_seen_at=now,
                last_seen_at=now,
                seen_count=1,
                replay_state="pending",
            )
        else:
            buffered_event.waba_id = resolved_waba_id
            buffered_event.phone_number_id = resolved_phone_number_id
            buffered_event.recipient_id = update.recipient_id
            buffered_event.occurred_at = update.occurred_at
            buffered_event.error_code = update.error_code
            buffered_event.payload = dict(update.payload)
            buffered_event.last_seen_at = now
            buffered_event.seen_count += 1
            if buffered_event.replay_state != "replayed":
                buffered_event.replay_state = "pending"
                buffered_event.replay_error = None
        self._session.add(buffered_event)
        provider_status_event_buffer_events_total.labels(
            **self._provider_status_buffer_metric_labels(
                provider_name=buffered_event.provider_name,
                account_id=buffered_event.account_id,
                waba_id=buffered_event.waba_id,
                phone_number_id=buffered_event.phone_number_id,
            ),
            outcome="buffered",
        ).inc()
        self._session.commit()
        current_scope = self._provider_status_buffer_scope(buffered_event)
        if previous_scope is not None and previous_scope != current_scope:
            self._refresh_provider_status_buffer_pending_metrics(
                provider_name=previous_scope[0],
                account_id=previous_scope[1],
                waba_id=previous_scope[2],
                phone_number_id=previous_scope[3],
            )
        self._refresh_provider_status_buffer_pending_metrics(
            provider_name=current_scope[0],
            account_id=current_scope[1],
            waba_id=current_scope[2],
            phone_number_id=current_scope[3],
        )

    def _find_unmatched_provider_status_events(
        self,
        *,
        account_id: str,
        provider_message_id: str,
        provider_name: str | None = None,
    ) -> list[ProviderStatusEventBuffer]:
        query = select(ProviderStatusEventBuffer).where(
            ProviderStatusEventBuffer.account_id == account_id,
            ProviderStatusEventBuffer.provider_message_id == provider_message_id,
            ProviderStatusEventBuffer.replay_state == "pending",
        )
        if provider_name is not None:
            query = query.where(ProviderStatusEventBuffer.provider_name == provider_name)
        return list(
            self._session.scalars(
                query.order_by(
                    ProviderStatusEventBuffer.first_seen_at,
                    ProviderStatusEventBuffer.external_status,
                )
            ).all()
        )

    def _provider_status_buffer_scope(
        self,
        event: ProviderStatusEventBuffer,
    ) -> tuple[str, str, str | None, str | None]:
        resolved_waba_id, resolved_phone_number_id = self._resolve_provider_status_buffer_scope(
            event
        )
        return (
            event.provider_name,
            event.account_id,
            resolved_waba_id,
            resolved_phone_number_id,
        )

    @staticmethod
    def _provider_status_buffer_metric_labels(
        *,
        provider_name: str,
        account_id: str,
        waba_id: str | None,
        phone_number_id: str | None,
    ) -> dict[str, str]:
        return {
            "provider": provider_name,
            "account_id": account_id,
            "waba_id": waba_id or "unknown",
            "phone_number_id": phone_number_id or "unknown",
        }

    def _refresh_provider_status_buffer_pending_metrics(
        self,
        *,
        provider_name: str,
        account_id: str,
        waba_id: str | None,
        phone_number_id: str | None,
    ) -> None:
        query = select(ProviderStatusEventBuffer).where(
            ProviderStatusEventBuffer.provider_name == provider_name,
            ProviderStatusEventBuffer.account_id == account_id,
            ProviderStatusEventBuffer.replay_state == "pending",
        )
        if waba_id is None:
            query = query.where(ProviderStatusEventBuffer.waba_id.is_(None))
        else:
            query = query.where(ProviderStatusEventBuffer.waba_id == waba_id)
        if phone_number_id is None:
            query = query.where(ProviderStatusEventBuffer.phone_number_id.is_(None))
        else:
            query = query.where(ProviderStatusEventBuffer.phone_number_id == phone_number_id)

        pending_events = list(self._session.scalars(query).all())
        oldest_seen_at = min(
            (event.first_seen_at for event in pending_events if event.first_seen_at is not None),
            default=None,
        )
        oldest_age_seconds = (
            max(0.0, (utc_now() - oldest_seen_at).total_seconds())
            if oldest_seen_at is not None
            else 0.0
        )
        labels = self._provider_status_buffer_metric_labels(
            provider_name=provider_name,
            account_id=account_id,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )
        provider_status_event_buffer_pending_current.labels(**labels).set(len(pending_events))
        provider_status_event_buffer_oldest_age_seconds.labels(**labels).set(oldest_age_seconds)

    def _get_message_status_event(
        self,
        *,
        account_id: str,
        provider_name: str,
        provider_message_id: str,
        external_status: str,
    ) -> MessageEvent | None:
        event_type = f"{provider_name}_status_{external_status}"
        events = self._session.scalars(
            select(MessageEvent).where(
                MessageEvent.account_id == account_id,
                MessageEvent.event_type == event_type,
            )
        ).all()
        for event in events:
            payload = event.payload if isinstance(event.payload, dict) else {}
            if payload.get("provider_message_id") != provider_message_id:
                continue
            if payload.get("external_status") != external_status:
                continue
            return event
        return None

    def _provider_status_update_from_unmatched_event(
        self,
        event: ProviderStatusEventBuffer,
    ) -> ProviderStatusUpdate | None:
        if not event.provider_name or not event.provider_message_id or not event.external_status:
            return None
        resolved_waba_id, resolved_phone_number_id = self._resolve_provider_status_buffer_scope(
            event
        )
        return ProviderStatusUpdate(
            provider_name=event.provider_name,
            account_id=event.account_id,
            waba_id=resolved_waba_id,
            phone_number_id=resolved_phone_number_id,
            provider_message_id=event.provider_message_id,
            external_status=event.external_status,
            recipient_id=event.recipient_id,
            occurred_at=event.occurred_at,
            error_code=event.error_code,
            payload=dict(event.payload) if isinstance(event.payload, dict) else {},
        )

    @staticmethod
    def _build_provider_status_event_payload(
        *,
        update: ProviderStatusUpdate,
        provider_payload: dict[str, object],
        extra_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            **provider_payload,
            "provider": update.provider_name,
            "provider_message_id": update.provider_message_id,
            "external_status": update.external_status,
            "waba_id": update.waba_id,
            "phone_number_id": update.phone_number_id,
            "recipient_id": update.recipient_id,
            "occurred_at": update.occurred_at,
            "error_code": update.error_code,
            "provider_payload": provider_payload,
        }
        if extra_payload:
            payload.update(extra_payload)
        return payload

    @staticmethod
    def _map_template_send_status(external_status: str) -> str:
        status = external_status.upper()
        if status in {"SENT", "DELIVERED", "READ", "FAILED"}:
            return status
        return "SENT"

    @staticmethod
    def _resolve_template_send_status_transition(
        *,
        current_status: str,
        incoming_status: str,
    ) -> str:
        precedence = {
            "QUEUED": 0,
            "SENT": 1,
            "DELIVERED": 2,
            "READ": 3,
            "FAILED": 4,
        }
        current_rank = precedence.get(current_status.upper(), 0)
        incoming_rank = precedence.get(incoming_status.upper(), 0)
        if incoming_rank < current_rank:
            return current_status
        return incoming_status

    @staticmethod
    def _pick_optional_string(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        return None

    @classmethod
    def _pick_nested_optional_string(
        cls,
        payload: dict[str, object] | None,
        key: str,
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        direct_value = cls._pick_optional_string(payload, key)
        if direct_value is not None:
            return direct_value
        for candidate_key in ("metadata", "provider_payload", "raw_payload"):
            candidate = payload.get(candidate_key)
            if not isinstance(candidate, dict):
                continue
            nested_value = cls._pick_nested_optional_string(candidate, key)
            if nested_value is not None:
                return nested_value
        return None

    @staticmethod
    def _extract_audit_phone_number_id(payload: dict[str, object] | None) -> str | None:
        return RuntimeStateStore._pick_nested_optional_string(payload, "phone_number_id")

    def _extract_audit_waba_id(self, audit_log: AuditLog) -> str | None:
        payload = audit_log.payload
        if isinstance(payload, dict):
            value = self._pick_nested_optional_string(payload, "waba_id")
            if value is not None:
                return value
            phone_number_id = self._extract_audit_phone_number_id(payload)
            if phone_number_id is not None:
                phone_number = self._session.scalar(
                    select(WhatsAppPhoneNumber)
                    .options(selectinload(WhatsAppPhoneNumber.waba_account))
                    .where(WhatsAppPhoneNumber.phone_number_id == phone_number_id)
                )
                resolved_waba_id = self._resolve_phone_waba_id(phone_number)
                if resolved_waba_id is not None:
                    return resolved_waba_id
        if audit_log.target_type == "waba_account" and audit_log.target_id:
            return audit_log.target_id
        return None

    def resolve_provider_status_buffer_scope(
        self,
        event: ProviderStatusEventBuffer,
    ) -> tuple[str | None, str | None]:
        return self._resolve_provider_status_buffer_scope(event)

    def _provider_status_buffer_matches_scope_filters(
        self,
        *,
        event: ProviderStatusEventBuffer,
        waba_id: str | None,
        phone_number_id: str | None,
    ) -> bool:
        resolved_waba_id, resolved_phone_number_id = self._resolve_provider_status_buffer_scope(
            event
        )
        if waba_id is not None and resolved_waba_id != waba_id:
            return False
        if phone_number_id is not None and resolved_phone_number_id != phone_number_id:
            return False
        return True

    def _resolve_provider_status_update_scope(
        self,
        update: ProviderStatusUpdate,
    ) -> tuple[str | None, str | None]:
        payload = update.payload if isinstance(update.payload, dict) else {}
        phone_number_id = update.phone_number_id or self._pick_nested_optional_string(
            payload,
            "phone_number_id",
        )
        waba_id = update.waba_id or self._pick_nested_optional_string(payload, "waba_id")
        if waba_id is None and phone_number_id is not None:
            phone_number = self._session.scalar(
                select(WhatsAppPhoneNumber)
                .options(selectinload(WhatsAppPhoneNumber.waba_account))
                .where(WhatsAppPhoneNumber.phone_number_id == phone_number_id)
            )
            resolved_waba_id = self._resolve_phone_waba_id(phone_number)
            if resolved_waba_id is not None:
                waba_id = resolved_waba_id
        return waba_id, phone_number_id

    def _resolve_provider_status_buffer_scope(
        self,
        event: ProviderStatusEventBuffer,
    ) -> tuple[str | None, str | None]:
        payload = event.payload if isinstance(event.payload, dict) else {}
        phone_number_id = self._pick_nested_optional_string(payload, "phone_number_id")
        if phone_number_id is None:
            phone_number_id = event.phone_number_id

        waba_id = self._pick_nested_optional_string(payload, "waba_id")
        if waba_id is None:
            waba_id = event.waba_id
        if waba_id is None and phone_number_id is not None:
            phone_number = self._session.scalar(
                select(WhatsAppPhoneNumber)
                .options(selectinload(WhatsAppPhoneNumber.waba_account))
                .where(WhatsAppPhoneNumber.phone_number_id == phone_number_id)
            )
            resolved_waba_id = self._resolve_phone_waba_id(phone_number)
            if resolved_waba_id is not None:
                waba_id = resolved_waba_id
        return waba_id, phone_number_id

    def _validate_meta_scope_filters(
        self,
        *,
        account_id: str | None,
        waba_id: str | None,
        phone_number_id: str | None,
        allowed_account_ids: set[str] | None,
    ) -> None:
        self._meta_scope_validator.validate_waba_scope(
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
        )
        self._meta_scope_validator.validate_phone_number_scope(
            phone_number_id=phone_number_id,
            account_id=account_id,
            waba_id=waba_id,
            allowed_account_ids=allowed_account_ids,
            enforce_waba_match=True,
        )

    @staticmethod
    def _resolve_inbound_event_type(payload: dict[str, object]) -> str:
        provider = payload.get("provider")
        if isinstance(provider, str) and provider:
            return f"{provider}_inbound_received"
        return "inbound_received"

    def _resolve_message_event_provider_scope(
        self,
        *,
        payload: dict[str, object],
        conversation: Conversation | None,
        provider_message_id: str | None,
        event_type: str,
    ) -> dict[str, str | datetime | None]:
        provider_name = self._pick_nested_optional_string(payload, "provider")
        waba_id = self._pick_nested_optional_string(payload, "waba_id")
        phone_number_id = self._pick_nested_optional_string(payload, "phone_number_id")

        phone_number = conversation.phone_number if conversation is not None else None
        if phone_number_id is None and phone_number is not None:
            phone_number_id = phone_number.phone_number_id
        if waba_id is None and phone_number is not None:
            waba_id = self._resolve_phone_waba_id(phone_number)

        provider_event_id = (
            f"{event_type}:{provider_message_id}"
            if provider_name is not None and provider_message_id
            else None
        )
        return {
            "provider_name": provider_name,
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "provider_event_id": provider_event_id,
            "occurred_at": None,
        }

    def _resolve_phone_waba_id(self, phone_number: WhatsAppPhoneNumber | None) -> str | None:
        if phone_number is None:
            return None
        if phone_number.waba_id:
            return phone_number.waba_id
        if phone_number.waba_account is not None and phone_number.waba_account.waba_id:
            return phone_number.waba_account.waba_id
        if phone_number.waba_account_id is None:
            return None
        waba_account = self._session.get(WhatsAppBusinessAccount, phone_number.waba_account_id)
        if waba_account is None or not waba_account.waba_id:
            return None
        return waba_account.waba_id

    @staticmethod
    def _build_provider_status_event_id(update: ProviderStatusUpdate) -> str:
        return f"status:{update.provider_message_id}:{update.external_status}"

    @staticmethod
    def _parse_provider_occurred_at(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            if value.isdigit():
                return datetime.fromtimestamp(int(value), UTC).replace(tzinfo=None)
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            return None

    @staticmethod
    def _extract_estimated_cost(payload: dict[str, object] | None) -> float:
        if not isinstance(payload, dict):
            return 0.0
        value = payload.get("estimated_cost")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def _ensure_agent_controls_conversation(
        self,
        conversation: Conversation,
        account_id: str,
        agent_id: str | None,
        action: str,
    ) -> None:
        if agent_id is None:
            return
        if conversation.assigned_agent_id is None:
            raise PermissionError(
                f"Agent '{agent_id}' cannot {action} because the conversation is not assigned."
            )
        assigned_agent = conversation.assigned_agent
        if assigned_agent is not None and assigned_agent.account_id not in {None, account_id}:
            raise PermissionError(
                f"Agent '{agent_id}' cannot {action}; conversation is assigned outside account '{account_id}'."
            )
        acting_agent = self._find_agent(account_id=account_id, agent_id=agent_id)
        assigned_agent_id = self.get_public_agent_id(
            assigned_agent,
            fallback=conversation.assigned_agent_id,
        )
        if acting_agent is not None:
            if conversation.assigned_agent_id == acting_agent.id:
                return
            raise PermissionError(
                f"Agent '{agent_id}' cannot {action}; conversation is assigned to '{assigned_agent_id}'."
            )
        elif agent_id == conversation.assigned_agent_id:
            return
        if assigned_agent_id != agent_id:
            raise PermissionError(
                f"Agent '{agent_id}' cannot {action}; conversation is assigned to '{assigned_agent_id}'."
            )

    def _ensure_management_transition_allowed(
        self,
        *,
        conversation: Conversation,
        target_mode: str,
    ) -> None:
        if target_mode not in MANAGEMENT_MODES:
            raise ValueError(f"Unsupported management_mode '{target_mode}'.")
        self._ensure_conversation_open_for_management(
            conversation=conversation,
            action=f"switch to {target_mode}",
        )
        allowed_targets = MANAGEMENT_TRANSITIONS.get(conversation.management_mode, set())
        if target_mode not in allowed_targets:
            raise ValueError(
                "Illegal management transition "
                f"'{conversation.management_mode}' -> '{target_mode}'."
            )

    def _ensure_conversation_open_for_management(
        self,
        *,
        conversation: Conversation,
        action: str,
    ) -> None:
        if conversation.status == "closed":
            raise ValueError(
                f"Conversation '{conversation.external_conversation_id}' is closed and cannot {action}. "
                "Wait for a new inbound message to reopen it."
            )

    def _resolve_management_reason(
        self,
        *,
        from_mode: str,
        to_mode: str,
        reason: str | None,
    ) -> str:
        normalized_reason = (reason or "").strip()
        if normalized_reason:
            return normalized_reason
        return DEFAULT_MANAGEMENT_REASONS.get((from_mode, to_mode), "management_mode_updated")

    def _build_ai_blocking_reasons(
        self,
        *,
        global_enabled: bool,
        account: Account,
        conversation: Conversation,
    ) -> list[dict[str, str]]:
        reasons: list[dict[str, str]] = []
        if not global_enabled:
            reasons.append(
                {
                    "scope": "global",
                    "code": "global_ai_disabled",
                    "message": "Global AI is disabled.",
                }
            )
        if not account.ai_enabled:
            reasons.append(
                {
                    "scope": "account",
                    "code": "account_ai_disabled",
                    "message": "Account AI is disabled.",
                }
            )
        if not account.is_active:
            reasons.append(
                {
                    "scope": "account",
                    "code": "account_inactive",
                    "message": "Account is inactive.",
                }
            )
        if not conversation.ai_enabled:
            reasons.append(
                {
                    "scope": "conversation",
                    "code": "conversation_ai_disabled",
                    "message": "Conversation AI is disabled.",
                }
            )
        if conversation.status != "open":
            reasons.append(
                {
                    "scope": "conversation",
                    "code": "conversation_closed",
                    "message": "Conversation is closed.",
                }
            )
        if conversation.management_mode == "human_managed":
            reasons.append(
                {
                    "scope": "management_mode",
                    "code": "human_managed",
                    "message": "Conversation is under human management.",
                }
            )
        if conversation.management_mode == "paused":
            reasons.append(
                {
                    "scope": "management_mode",
                    "code": "paused",
                    "message": "Conversation is paused.",
                }
            )
        phone_number = conversation.phone_number
        waba_account = phone_number.waba_account if phone_number is not None else None
        if waba_account is not None and not waba_account.is_active:
            reasons.append(
                {
                    "scope": "waba",
                    "code": "waba_inactive",
                    "message": "WABA is inactive.",
                }
            )
        if phone_number is not None and not phone_number.is_active:
            reasons.append(
                {
                    "scope": "phone_number",
                    "code": "phone_number_inactive",
                    "message": "Phone number is inactive.",
                }
            )
        return reasons

    def _serialize_account(self, account: Account) -> AccountRuntimeState:
        return AccountRuntimeState(
            account_id=account.account_id,
            display_name=account.display_name,
            provider_type=account.provider_type,
            is_active=account.is_active,
            ai_enabled=account.ai_enabled,
        )

    def _serialize_conversation(self, conversation: Conversation) -> ConversationRuntimeState:
        return ConversationRuntimeState(
            account_id=conversation.account_id,
            conversation_id=conversation.external_conversation_id,
            phone_number_id=(
                conversation.phone_number.phone_number_id
                if conversation.phone_number is not None
                else None
            ),
            status=conversation.status,
            ai_enabled=conversation.ai_enabled,
            management_mode=conversation.management_mode,
            assigned_agent_id=self.get_public_agent_id(
                conversation.assigned_agent,
                fallback=conversation.assigned_agent_id,
            ),
            assigned_agent_name=(
                conversation.assigned_agent.display_name if conversation.assigned_agent is not None else None
            ),
        )
