"""P1-01 regression tests: Redis dead-letter list reading.

``list_dead_letter_jobs`` previously used ``GET`` on dead-letter keys, but
``move_to_dead_letter`` stores job ids in a Redis *list* (via ``rpush``).
Reading a list key with ``GET`` raises ``WRONGTYPE`` on a real Redis. The scan
pattern was also wrong (``queue:dead:*`` instead of ``queue:*:dead_letter``).

These tests use a minimal fake *synchronous* redis client (matching the sync
``redis.Redis`` surface used by ``RedisQueueProvider``) so they run without a
real Redis instance.
"""

from typing import Any

from app.providers.queue.redis_provider import RedisQueueProvider


class _FakePipeline:
    def __init__(self, client: "_FakeSyncRedis") -> None:
        self._client = client
        self._commands: list[tuple[str, tuple, dict]] = []

    def set(self, key: str, value: str, **kwargs: Any) -> None:
        self._commands.append(("set", (key, value), kwargs))

    def rpush(self, key: str, *values: str) -> None:
        self._commands.append(("rpush", (key, *values), {}))

    def lrem(self, key: str, count: int, value: str) -> None:
        self._commands.append(("lrem", (key, count, value), {}))

    def execute(self) -> list:
        results: list = []
        for cmd, args, _kwargs in self._commands:
            if cmd == "set":
                self._client._store[args[0]] = args[1]
                results.append(True)
            elif cmd == "rpush":
                lst = self._client._lists.setdefault(args[0], [])
                lst.extend(args[1:])
                results.append(len(lst))
            elif cmd == "lrem":
                key, _count, value = args
                lst = self._client._lists.get(key, [])
                if value in lst:
                    lst.remove(value)
                    results.append(1)
                else:
                    results.append(0)
        self._commands.clear()
        return results


class _FakeSyncRedis:
    """Minimal sync redis surface for RedisQueueProvider tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)

    def set(self, key: str, value: str, **kwargs: Any) -> None:
        del kwargs
        self._store[key] = value

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def rpush(self, key: str, *values: str) -> int:
        lst = self._lists.setdefault(key, [])
        lst.extend(values)
        return len(lst)

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        lst = self._lists.get(key, [])
        if stop == -1:
            return list(lst[start:])
        return list(lst[start : stop + 1])

    def scan_iter(self, match: str):
        import fnmatch

        # Dead-letter list keys live in _lists, so scan there too.
        keys = list(self._store.keys()) + list(self._lists.keys())
        return iter([k for k in keys if fnmatch.fnmatch(k, match)])


def _make_provider() -> RedisQueueProvider:
    provider = RedisQueueProvider.__new__(RedisQueueProvider)
    provider._client = _FakeSyncRedis()
    return provider


def test_list_dead_letter_jobs_reads_list_entries_for_queue() -> None:
    provider = _make_provider()
    job = provider.enqueue("ai_generation", {"x": 1}, max_retries=3)
    provider.move_to_dead_letter("ai_generation", job)

    dead_jobs = provider.list_dead_letter_jobs("ai_generation")

    assert [j.job_id for j in dead_jobs] == [job.job_id]
    assert dead_jobs[0].status == "dead_letter"


def test_list_dead_letter_jobs_reads_all_queues_when_unspecified() -> None:
    provider = _make_provider()
    job_a = provider.enqueue("ai_generation", {"x": 1}, max_retries=3)
    provider.move_to_dead_letter("ai_generation", job_a)

    dead_jobs = provider.list_dead_letter_jobs()

    assert len(dead_jobs) == 1
    assert dead_jobs[0].job_id == job_a.job_id


def test_list_dead_letter_jobs_ignores_missing_job_payload() -> None:
    """If a job id is listed but its payload was evicted, skip it gracefully."""
    provider = _make_provider()
    job = provider.enqueue("ai_generation", {"x": 1}, max_retries=3)
    provider.move_to_dead_letter("ai_generation", job)
    # Simulate payload eviction: keep the dead-letter list entry, drop the job.
    del provider._client._store[f"queue:job:{job.job_id}"]

    dead_jobs = provider.list_dead_letter_jobs("ai_generation")

    assert dead_jobs == []
