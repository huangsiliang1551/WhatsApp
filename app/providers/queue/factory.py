from app.core.settings import Settings
from app.providers.queue.base import QueueProvider
from app.providers.queue.memory_provider import MEMORY_QUEUE_PROVIDER
from app.providers.queue.redis_provider import RedisQueueProvider


def get_queue_provider(settings: Settings) -> QueueProvider:
    provider_name = settings.queue_provider.lower()

    if settings.test_mode or provider_name == "memory":
        return MEMORY_QUEUE_PROVIDER

    if provider_name == "redis":
        return RedisQueueProvider(settings.queue_redis_url)

    raise ValueError(f"Unsupported queue provider '{settings.queue_provider}'.")
