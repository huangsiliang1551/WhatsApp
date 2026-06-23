import pytest

from tests.fake_redis import FakeRedis


@pytest.mark.anyio
async def test_fake_redis_supports_fifo_queue_flow(fake_redis: FakeRedis) -> None:
    queue_name = "worker:default"

    size = await fake_redis.rpush(queue_name, "job-1", "job-2")

    assert size == 2
    assert await fake_redis.llen(queue_name) == 2
    assert await fake_redis.blpop(queue_name) == (queue_name, "job-1")
    assert await fake_redis.brpop(queue_name) == (queue_name, "job-2")
    assert await fake_redis.llen(queue_name) == 0


@pytest.mark.anyio
async def test_fake_redis_isolates_multiple_queues_and_flushes_state(
    fake_redis: FakeRedis,
) -> None:
    await fake_redis.lpush("worker:priority", "job-priority")
    await fake_redis.rpush("worker:default", "job-default")

    assert await fake_redis.blpop(["worker:priority", "worker:default"]) == (
        "worker:priority",
        "job-priority",
    )
    assert await fake_redis.blpop(["worker:priority", "worker:default"]) == (
        "worker:default",
        "job-default",
    )

    await fake_redis.rpush("worker:default", "job-later")
    await fake_redis.flushall()

    assert await fake_redis.blpop(["worker:priority", "worker:default"]) is None
