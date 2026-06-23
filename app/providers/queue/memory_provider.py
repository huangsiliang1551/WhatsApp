from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4

from app.db.models import utc_now
from app.providers.queue.base import QueueProvider, ReservedQueueJob
from app.schemas.queue import QueueJob, QueueName


class InMemoryQueueProvider(QueueProvider):
    provider_name = "memory"

    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, QueueJob] = {}
        self._pending: dict[QueueName, deque[str]] = defaultdict(deque)
        self._dead_letter: dict[QueueName, deque[str]] = defaultdict(deque)

    def enqueue(self, queue_name: QueueName, payload: dict[str, object], max_retries: int) -> QueueJob:
        with self._lock:
            job = self._build_job(queue_name=queue_name, payload=payload, max_retries=max_retries)
            self._jobs[job.job_id] = job
            self._pending[queue_name].append(job.job_id)
            return job

    def reserve(self, queue_name: QueueName, timeout_seconds: int | None = None) -> ReservedQueueJob | None:
        del timeout_seconds
        with self._lock:
            if not self._pending[queue_name]:
                return None
            job_id = self._pending[queue_name].popleft()
            job = self._jobs[job_id].model_copy(
                update={
                    "status": "processing",
                    "attempt_count": self._jobs[job_id].attempt_count + 1,
                    "last_attempt_at": utc_now().isoformat(),
                    "updated_at": utc_now().isoformat(),
                }
            )
            self._jobs[job_id] = job
            return ReservedQueueJob(queue=queue_name, job=job)

    def get_job(self, job_id: str) -> QueueJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def save_job(self, job: QueueJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def requeue(self, queue_name: QueueName, job: QueueJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            self._pending[queue_name].append(job.job_id)

    def list_jobs(self) -> list[QueueJob]:
        with self._lock:
            return list(self._jobs.values())

    def move_to_dead_letter(self, queue_name: QueueName, job: QueueJob) -> None:
        updated = job.model_copy(
            update={
                "status": "dead_letter",
                "updated_at": utc_now().isoformat(),
            }
        )
        with self._lock:
            self._jobs[job.job_id] = updated
            self._dead_letter[queue_name].append(job.job_id)

    def list_dead_letter_jobs(self, queue_name: QueueName | None = None) -> list[QueueJob]:
        with self._lock:
            if queue_name is not None:
                return [self._jobs[jid] for jid in self._dead_letter.get(queue_name, []) if jid in self._jobs]
            result: list[QueueJob] = []
            for qname in self._dead_letter:
                result.extend(
                    self._jobs[jid] for jid in self._dead_letter[qname] if jid in self._jobs
                )
            return result

    def requeue_dead_letter(self, job_id: str) -> QueueJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != "dead_letter":
                return None
            dl_queue = self._dead_letter.get(job.queue, deque())
            if job_id in dl_queue:
                dl_queue.remove(job_id)
            updated = job.model_copy(
                update={
                    "status": "queued",
                    "retry_count": 0,
                    "error_history": [],
                    "failed_at": None,
                    "updated_at": utc_now().isoformat(),
                }
            )
            self._jobs[job_id] = updated
            self._pending[job.queue].append(job_id)
            return updated

    def reset(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._pending.clear()
            self._dead_letter.clear()

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


MEMORY_QUEUE_PROVIDER = InMemoryQueueProvider()
