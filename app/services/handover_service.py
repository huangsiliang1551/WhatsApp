from app.db.models import Agent
from app.schemas.handover import (
    AgentPresenceRecordSchema,
    AgentRegistrationRequest,
    AgentSummary,
    AgentWorkloadSummary,
)
from app.schemas.runtime import ConversationRuntimeState
from app.services.agent_presence_service import AgentPresenceService
from app.services.runtime_state import RuntimeStateStore


class HandoverService:
    def __init__(
        self,
        runtime_state: RuntimeStateStore,
        presence_service: AgentPresenceService | None = None,
    ) -> None:
        self._runtime_state = runtime_state
        self._presence_service = presence_service

    async def list_agents(
        self,
        account_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        status: str | None = None,
        is_active: bool | None = None,
    ) -> list[AgentSummary]:
        return [
            self._serialize_agent(agent)
            for agent in await self._runtime_state.list_agent_models(
                account_id=account_id,
                allowed_account_ids=allowed_account_ids,
                status=status,
                is_active=is_active,
            )
        ]

    async def list_agent_workloads(
        self,
        account_id: str | None = None,
        allowed_account_ids: set[str] | None = None,
        status: str | None = None,
        is_active: bool | None = None,
    ) -> list[AgentWorkloadSummary]:
        return [
            AgentWorkloadSummary(
                account_id=item["agent"].account_id,
                agent_id=item["agent"].agent_key,
                display_name=item["agent"].display_name,
                email=item["agent"].email,
                status=item["agent"].status,
                is_active=item["agent"].is_active,
                assigned_open_conversations=int(item["assigned_open_conversations"]),
                assigned_total_conversations=int(item["assigned_total_conversations"]),
                assigned_account_count=int(item["assigned_account_count"]),
            )
            for item in await self._runtime_state.list_agent_workloads(
                account_id=account_id,
                allowed_account_ids=allowed_account_ids,
                status=status,
                is_active=is_active,
            )
        ]

    async def set_agent_status(
        self,
        account_id: str | None,
        agent_id: str,
        status: str,
        actor_type: str = "agent",
        actor_id: str | None = None,
    ) -> AgentSummary:
        agent = await self._runtime_state.set_agent_status(
            account_id=account_id,
            agent_id=agent_id,
            status=status,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        # Sync Redis presence when presence service is available
        if self._presence_service is not None:
            if status == "offline":
                await self._presence_service.set_offline(agent_id, account_id)
            elif status == "online":
                await self._presence_service.set_online(
                    agent_id, account_id, display_name=agent.display_name
                )
            elif status == "busy":
                await self._presence_service.set_busy(
                    agent_id, account_id, display_name=agent.display_name
                )
            elif status == "away":
                await self._presence_service.set_away(
                    agent_id, account_id, display_name=agent.display_name
                )
        return self._serialize_agent(agent)

    async def register_agent(
        self,
        payload: AgentRegistrationRequest,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> AgentSummary:
        agent = await self._runtime_state.upsert_agent(
            account_id=payload.account_id,
            agent_id=payload.agent_id,
            display_name=payload.display_name,
            email=payload.email,
            status=payload.status,
            is_active=payload.is_active,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        # Sync Redis presence when registered as online
        if self._presence_service is not None and payload.status == "online":
            await self._presence_service.set_online(
                payload.agent_id,
                payload.account_id,
                display_name=payload.display_name,
            )
        return self._serialize_agent(agent)

    # ---- Agent presence (Redis-based) ----

    async def list_online_agents(
        self,
        account_id: str | None = None,
    ) -> list[AgentPresenceRecordSchema]:
        if self._presence_service is None:
            return []
        records = await self._presence_service.list_online_agents(
            account_id=account_id,
        )
        return [self._serialize_presence(r) for r in records]

    async def is_agent_online(
        self,
        agent_id: str,
        account_id: str | None = None,
    ) -> bool:
        if self._presence_service is None:
            # Fall back to DB status - list agents matching the key
            agents = await self._runtime_state.list_agent_models(
                account_id=account_id,
            )
            for agent in agents:
                if agent.agent_key == agent_id:
                    return agent.status != "offline"
            return False
        return await self._presence_service.is_online(agent_id, account_id)

    async def presence_heartbeat(
        self,
        agent_id: str,
        account_id: str | None = None,
    ) -> AgentPresenceRecordSchema | None:
        if self._presence_service is None:
            return None
        record = await self._presence_service.heartbeat(agent_id, account_id)
        if record is None:
            return None
        return self._serialize_presence(record)

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
        return await self._runtime_state.assign_conversation(
            account_id=account_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            assigned_by_agent_id=assigned_by_agent_id,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            admin_override=admin_override,
        )

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
        return await self._runtime_state.close_conversation(
            account_id=account_id,
            conversation_id=conversation_id,
            closed_by_agent_id=closed_by_agent_id,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            admin_override=admin_override,
        )

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
        return await self._runtime_state.reopen_conversation(
            account_id=account_id,
            conversation_id=conversation_id,
            reopened_by_agent_id=reopened_by_agent_id,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            admin_override=admin_override,
        )

    def _serialize_agent(self, agent: Agent) -> AgentSummary:
        return AgentSummary(
            account_id=agent.account_id,
            agent_id=agent.agent_key,
            display_name=agent.display_name,
            email=agent.email,
            status=agent.status,
            is_active=agent.is_active,
        )

    @staticmethod
    def _serialize_presence(record: object) -> AgentPresenceRecordSchema:
        return AgentPresenceRecordSchema(
            account_id=getattr(record, "account_id", None),
            agent_id=getattr(record, "agent_id", ""),
            status=getattr(record, "status", "offline"),
            last_heartbeat=getattr(record, "last_heartbeat", 0.0),
            display_name=getattr(record, "display_name", ""),
        )
