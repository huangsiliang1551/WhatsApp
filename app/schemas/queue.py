from typing import Any, Literal

from pydantic import BaseModel, Field


QueueName = Literal["ai_generation"]
QueueJobStatus = Literal["queued", "processing", "completed", "failed", "dead_letter"]


class QueueJob(BaseModel):
    job_id: str
    queue: QueueName
    status: QueueJobStatus
    payload: dict[str, Any]
    attempt_count: int = 0
    retry_count: int = 0
    max_retries: int = 0
    created_at: str
    updated_at: str
    last_attempt_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    error_history: list[str] = Field(default_factory=list)


class QueueEnqueueResult(BaseModel):
    job_id: str
    queue: QueueName
    status: QueueJobStatus = "queued"


class QueueStatsItem(BaseModel):
    queue: QueueName
    queued: int
    processing: int
    completed: int
    failed: int
    retried_total: int = 0


class QueueStatsResponse(BaseModel):
    queues: list[QueueStatsItem] = Field(default_factory=list)
    recent_failed_jobs: list[QueueJob] = Field(default_factory=list)
    dead_letter_count: int = 0


class WorkerHealthResponse(BaseModel):
    is_running: bool
    last_processed_at: str | None = None
    processed_count: int = 0
    failed_count: int = 0
    consecutive_failures: int = 0
    is_paused: bool = False
    queue_depth: int = 0
