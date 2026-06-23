from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.queue import QueueJob, QueueName


@dataclass
class ReservedQueueJob:
    queue: QueueName
    job: QueueJob


class QueueProvider(ABC):
    provider_name: str

    @abstractmethod
    def enqueue(self, queue_name: QueueName, payload: dict[str, object], max_retries: int) -> QueueJob:
        raise NotImplementedError

    @abstractmethod
    def reserve(self, queue_name: QueueName, timeout_seconds: int | None = None) -> ReservedQueueJob | None:
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job_id: str) -> QueueJob | None:
        raise NotImplementedError

    @abstractmethod
    def save_job(self, job: QueueJob) -> None:
        raise NotImplementedError

    @abstractmethod
    def requeue(self, queue_name: QueueName, job: QueueJob) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_jobs(self) -> list[QueueJob]:
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def move_to_dead_letter(self, queue_name: QueueName, job: QueueJob) -> None:
        """Move a job to the dead letter queue after max retries exhausted."""
        raise NotImplementedError

    @abstractmethod
    def list_dead_letter_jobs(self, queue_name: QueueName | None = None) -> list[QueueJob]:
        """List all jobs in the dead letter queue."""
        raise NotImplementedError

    @abstractmethod
    def requeue_dead_letter(self, job_id: str) -> QueueJob | None:
        """Re-queue a dead letter job for retry."""
        raise NotImplementedError
