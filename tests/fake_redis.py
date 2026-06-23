from collections import deque
from collections.abc import Iterable
from typing import Any


RedisValue = str | bytes


class FakeRedis:
    """In-memory Redis-like store for queue, worker, and agent presence tests."""

    def __init__(self) -> None:
        self._queues: dict[str, deque[RedisValue]] = {}
        self._store: dict[str, Any] = {}
        self._ttls: dict[str, float] = {}
        self._sorted_sets: dict[str, dict[str, float]] = {}

    # ---- Sorted Set operations ----

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        ss = self._sorted_sets.setdefault(key, {})
        count = 0
        for member, score in mapping.items():
            if member not in ss or ss[member] != score:
                count += 1
            ss[member] = score
        return count

    async def zrangebyscore(self, key: str, min_score: float, max_score: float) -> list[str]:
        ss = self._sorted_sets.get(key, {})
        return [m for m, s in ss.items() if min_score <= s <= max_score]

    async def zrem(self, key: str, *members: str) -> int:
        ss = self._sorted_sets.get(key)
        if ss is None:
            return 0
        count = 0
        for m in members:
            if m in ss:
                del ss[m]
                count += 1
        return count

    # ---- Queue operations (list-based) ----

    async def lpush(self, key: str, *values: RedisValue) -> int:
        queue = self._queue(key)
        for value in values:
            queue.appendleft(value)
        return len(queue)

    async def rpush(self, key: str, *values: RedisValue) -> int:
        queue = self._queue(key)
        queue.extend(values)
        return len(queue)

    async def lpop(self, key: str) -> RedisValue | None:
        queue = self._queue(key)
        if not queue:
            return None
        return queue.popleft()

    async def rpop(self, key: str) -> RedisValue | None:
        queue = self._queue(key)
        if not queue:
            return None
        return queue.pop()

    async def blpop(
        self,
        keys: str | Iterable[str],
        timeout: int | float = 0,
    ) -> tuple[str, RedisValue] | None:
        del timeout
        for key in self._iter_keys(keys):
            value = await self.lpop(key)
            if value is not None:
                return key, value
        return None

    async def brpop(
        self,
        keys: str | Iterable[str],
        timeout: int | float = 0,
    ) -> tuple[str, RedisValue] | None:
        del timeout
        for key in self._iter_keys(keys):
            value = await self.rpop(key)
            if value is not None:
                return key, value
        return None

    async def llen(self, key: str) -> int:
        return len(self._queue(key))

    # ---- Key-value operations (set/get/delete) ----

    def set(self, key: str, value: object, ex: int | None = None) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = __import__("time").time() + ex

    def get(self, key: str) -> object | None:
        self._purge_expired()
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._ttls.pop(key, None)

    def expire(self, key: str, seconds: int) -> None:
        self._ttls[key] = __import__("time").time() + seconds

    def scan_iter(self, match: str) -> list[str]:
        self._purge_expired()
        import fnmatch

        return [k for k in self._store if fnmatch.fnmatch(k, match)]

    def _purge_expired(self) -> None:
        now = __import__("time").time()
        expired = [k for k, t in self._ttls.items() if t <= now]
        for k in expired:
            self._store.pop(k, None)
            self._ttls.pop(k, None)

    async def flushall(self) -> None:
        self._queues.clear()
        self._store.clear()
        self._ttls.clear()

    def _queue(self, key: str) -> deque[RedisValue]:
        return self._queues.setdefault(key, deque())

    def _iter_keys(self, keys: str | Iterable[str]) -> list[str]:
        if isinstance(keys, str):
            return [keys]
        return list(keys)
