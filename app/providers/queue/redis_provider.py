from uuid import uuid4

from redis import Redis

from app.db.models import utc_now
from app.providers.queue.base import QueueProvider, ReservedQueueJob
from app.schemas.queue import QueueJob, QueueName


class RedisQueueProvider(QueueProvider):
    provider_name = "redis"

    def __init__(self, redis_url: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)

    def enqueue(self, queue_name: QueueName, payload: dict[str, object], max_retries: int) -> QueueJob:
        job = self._build_job(queue_name=queue_name, payload=payload, max_retries=max_retries)
        pipe = self._client.pipeline()
        pipe.set(self._job_key(job.job_id), job.model_dump_json())
        pipe.rpush(self._pending_key(queue_name), job.job_id)
        pipe.execute()
        return job

    def reserve(self, queue_name: QueueName, timeout_seconds: int | None = None) -> ReservedQueueJob | None:
        result = self._client.blpop(
            self._pending_key(queue_name),
            timeout=timeout_seconds or 0,
        )
        if result is None:
            return None
        _, job_id = result
        job = self.get_job(job_id)
        if job is None:
            return None
        job = job.model_copy(
            update={
                "status": "processing",
                "attempt_count": job.attempt_count + 1,
                "last_attempt_at": utc_now().isoformat(),
                "updated_at": utc_now().isoformat(),
            }
        )
        self.save_job(job)
        return ReservedQueueJob(queue=queue_name, job=job)

    def get_job(self, job_id: str) -> QueueJob | None:
        payload = self._client.get(self._job_key(job_id))
        if payload is None:
            return None
        return QueueJob.model_validate_json(payload)

    def save_job(self, job: QueueJob) -> None:
        self._client.set(self._job_key(job.job_id), job.model_dump_json())

    def requeue(self, queue_name: QueueName, job: QueueJob) -> None:
        pipe = self._client.pipeline()
        pipe.set(self._job_key(job.job_id), job.model_dump_json())
        pipe.rpush(self._pending_key(queue_name), job.job_id)
        pipe.execute()

    def list_jobs(self) -> list[QueueJob]:
        jobs: list[QueueJob] = []
        for key in self._client.scan_iter(match="queue:job:*"):
            payload = self._client.get(key)
            if payload is None:
                continue
            jobs.append(QueueJob.model_validate_json(payload))
        return jobs

    def move_to_dead_letter(self, queue_name: QueueName, job: QueueJob) -> None:
        updated = job.model_copy(
            update={
                "status": "dead_letter",
                "updated_at": utc_now().isoformat(),
            }
        )
        pipe = self._client.pipeline()
        pipe.set(self._job_key(job.job_id), updated.model_dump_json())
        pipe.rpush(self._dead_letter_key(queue_name), job.job_id)
        pipe.execute()

    def list_dead_letter_jobs(self, queue_name: QueueName | None = None) -> list[QueueJob]:
        # Dead-letter keys are Redis *lists* (populated by rpush in
        # ``move_to_dead_letter``), so we must read them with ``lrange``.
        # Using ``GET`` on a list key raises WRONGTYPE. The scan pattern must
        # match ``queue:*:dead_letter`` (the shape returned by
        # ``_dead_letter_key``), not ``queue:dead:*``.
        jobs: list[QueueJob] = []
        if queue_name is not None:
            dead_keys = [self._dead_letter_key(queue_name)]
        else:
            dead_keys = list(self._client.scan_iter(match="queue:*:dead_letter"))

        for dead_key in dead_keys:
            job_ids = self._client.lrange(dead_key, 0, -1)
            for job_id in job_ids:
                job = self.get_job(job_id)
                if job is not None:
                    jobs.append(job)
        return jobs

    def requeue_dead_letter(self, job_id: str) -> QueueJob | None:
        payload = self._client.get(self._job_key(job_id))
        if payload is None:
            return None
        job = QueueJob.model_validate_json(payload)
        if job.status != "dead_letter":
            return None
        updated = job.model_copy(
            update={
                "status": "queued",
                "retry_count": 0,
                "error_history": [],
                "failed_at": None,
                "updated_at": utc_now().isoformat(),
            }
        )
        pipe = self._client.pipeline()
        pipe.set(self._job_key(job.job_id), updated.model_dump_json())
        pipe.rpush(self._pending_key(job.queue), job.job_id)
        pipe.lrem(self._dead_letter_key(job.queue), 1, job.job_id)
        pipe.execute()
        return updated

    def reset(self) -> None:
        return None

    def _build_job(self, queue_name: QueueName, payload: dict[str, object], max_retries: int) -> QueueJob:
        timestamp = utc_now().isoformat()
        return QueueJob(
            job_id=str(uuid4()),
            queue=queue_name,
            status="queued",
            payload=payload,
            attempt_count=0,
            retry_count=0,
            max_retries=max_retries,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def _job_key(self, job_id: str) -> str:
        return f"queue:job:{job_id}"

    def _pending_key(self, queue_name: QueueName) -> str:
        return f"queue:{queue_name}:pending"

    def _dead_letter_key(self, queue_name: QueueName) -> str:
        return f"queue:{queue_name}:dead_letter"
