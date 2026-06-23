"""Agent presence service backed by Redis for real-time online status tracking.

Provides TTL-based presence expiration, heartbeat mechanism, and per-account
scope isolation. Used by HandoverService to augment DB-based agent status with
real-time online/offline detection.
"""

import json
import time
from collections.abc import Mapping
from typing import Any, Literal

from app.core.settings import Settings

AgentPresenceStatus = Literal["online", "offline", "busy", "away"]
PRESENCE_TTL_SECONDS = 120  # auto-offline after 2 minutes without heartbeat
PRESENCE_KEY_PREFIX = "presence"


class AgentPresenceRecord(Mapping[str, Any]):
    """Immutable record of an agent's presence state."""

    def __init__(
        self,
        account_id: str | None,
        agent_id: str,
        status: AgentPresenceStatus,
        last_heartbeat: float,
        display_name: str = "",
    ) -> None:
        self._data = {
            "account_id": account_id,
            "agent_id": agent_id,
            "status": status,
            "last_heartbeat": last_heartbeat,
            "display_name": display_name,
        }

    def __getitem__(self, key: str) -> Any:  # type: ignore[override]
        return self._data[key]

    def __iter__(self) -> Any:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    @property
    def account_id(self) -> str | None:
        return self._data["account_id"]

    @property
    def agent_id(self) -> str:
        return self._data["agent_id"]

    @property
    def status(self) -> AgentPresenceStatus:
        return self._data["status"]

    @property
    def last_heartbeat(self) -> float:
        return self._data["last_heartbeat"]

    @property
    def display_name(self) -> str:
        return self._data["display_name"]

    @property
    def is_online(self) -> bool:
        return self.status in {"online", "busy", "away"}

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class _MemoryPresenceStore:
    """In-memory fallback for test mode."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:  # noqa: ARG002
        self._store[key] = value.encode("utf-8")

    def get(self, key: str) -> bytes | None:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def scan_iter(self, match: str) -> list[str]:
        import fnmatch

        return [k for k in self._store if fnmatch.fnmatch(k, match)]

    def expire(self, key: str, seconds: int) -> None:  # noqa: ARG002
        self._store.pop(key, None)


class AgentPresenceService:
    """Manages agent online/offline presence with Redis-backed TTL."""

    def __init__(self, settings: Settings, redis_client: object | None = None) -> None:
        self._settings = settings
        if settings.test_mode:
            self._redis = _MemoryPresenceStore()
        elif redis_client is not None:
            self._redis = redis_client
        else:
            from redis import Redis

            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)

    @staticmethod
    def _presence_key(account_id: str | None, agent_id: str) -> str:
        scope = account_id or "__global__"
        return f"{PRESENCE_KEY_PREFIX}:{scope}:{agent_id}"

    @staticmethod
    def _scan_pattern(account_id: str | None) -> str:
        scope = account_id or "*"
        return f"{PRESENCE_KEY_PREFIX}:{scope}:*"

    async def set_online(
        self,
        agent_id: str,
        account_id: str | None = None,
        display_name: str = "",
    ) -> AgentPresenceRecord:
        return await self._set_presence(agent_id, "online", account_id, display_name)

    async def set_offline(
        self,
        agent_id: str,
        account_id: str | None = None,
    ) -> None:
        key = self._presence_key(account_id, agent_id)
        self._redis.delete(key)

    async def set_busy(
        self,
        agent_id: str,
        account_id: str | None = None,
        display_name: str = "",
    ) -> AgentPresenceRecord:
        return await self._set_presence(agent_id, "busy", account_id, display_name)

    async def set_away(
        self,
        agent_id: str,
        account_id: str | None = None,
        display_name: str = "",
    ) -> AgentPresenceRecord:
        return await self._set_presence(agent_id, "away", account_id, display_name)

    async def heartbeat(
        self,
        agent_id: str,
        account_id: str | None = None,
    ) -> AgentPresenceRecord | None:
        key = self._presence_key(account_id, agent_id)
        raw = self._redis.get(key)
        if raw is None:
            return None
        record = self._deserialize(raw)
        updated = AgentPresenceRecord(
            account_id=record.account_id,
            agent_id=record.agent_id,
            status=record.status,
            last_heartbeat=time.time(),
            display_name=record.display_name,
        )
        self._redis.set(key, json.dumps(updated.to_dict()), ex=PRESENCE_TTL_SECONDS)
        return updated

    async def get_presence(
        self,
        agent_id: str,
        account_id: str | None = None,
    ) -> AgentPresenceRecord | None:
        key = self._presence_key(account_id, agent_id)
        raw = self._redis.get(key)
        if raw is None:
            return None
        return self._deserialize(raw)

    async def list_online_agents(
        self,
        account_id: str | None = None,
    ) -> list[AgentPresenceRecord]:
        pattern = self._scan_pattern(account_id)
        keys = self._redis.scan_iter(match=pattern)
        records: list[AgentPresenceRecord] = []
        for key in keys:
            raw = self._redis.get(key)
            if raw is None:
                continue
            record = self._deserialize(raw)
            if record.is_online:
                records.append(record)
        return sorted(records, key=lambda r: r.agent_id)

    async def is_online(
        self,
        agent_id: str,
        account_id: str | None = None,
    ) -> bool:
        record = await self.get_presence(agent_id, account_id)
        return record is not None and record.is_online

    async def clear_all(self, account_id: str | None = None) -> int:
        pattern = self._scan_pattern(account_id)
        keys = self._redis.scan_iter(match=pattern)
        count = 0
        for key in keys:
            self._redis.delete(key)
            count += 1
        return count

    async def _set_presence(
        self,
        agent_id: str,
        status: AgentPresenceStatus,
        account_id: str | None = None,
        display_name: str = "",
    ) -> AgentPresenceRecord:
        record = AgentPresenceRecord(
            account_id=account_id,
            agent_id=agent_id,
            status=status,
            last_heartbeat=time.time(),
            display_name=display_name,
        )
        key = self._presence_key(account_id, agent_id)
        self._redis.set(key, json.dumps(record.to_dict()), ex=PRESENCE_TTL_SECONDS)
        return record

    @staticmethod
    def _deserialize(raw: bytes | str) -> AgentPresenceRecord:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return AgentPresenceRecord(
            account_id=data.get("account_id"),
            agent_id=data["agent_id"],
            status=data["status"],
            last_heartbeat=data["last_heartbeat"],
            display_name=data.get("display_name", ""),
        )
