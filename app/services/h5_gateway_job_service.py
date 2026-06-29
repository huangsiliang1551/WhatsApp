from __future__ import annotations

from datetime import UTC, datetime

from app.core.settings import Settings, get_settings
from app.db.models import H5GatewayJob, H5GatewayJobStep
from sqlalchemy import select
from sqlalchemy.orm import Session


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class H5GatewayJobService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.allowed_job_types = {
            value.strip()
            for value in self.settings.h5_gateway_allowed_job_types.split(",")
            if value.strip()
        }

    def create_job(
        self,
        *,
        node_id: str,
        job_type: str,
        requested_by: str | None,
        trigger_source: str = "manual",
        input_json: dict[str, object] | None = None,
        idempotency_key: str | None = None,
        lock_key: str | None = None,
    ) -> H5GatewayJob:
        self._validate_job_type(job_type)
        if idempotency_key:
            existing = self.session.scalar(
                select(H5GatewayJob).where(H5GatewayJob.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return existing
        job = H5GatewayJob(
            node_id=node_id,
            job_type=job_type,
            requested_by=requested_by,
            trigger_source=trigger_source,
            input_json=input_json or {},
            idempotency_key=idempotency_key,
            lock_key=lock_key or f"h5_gateway_node:{node_id}:mutating",
        )
        self.session.add(job)
        self.session.flush()
        return job

    def poll_pending_job(self, *, node_id: str) -> H5GatewayJob | None:
        return self.session.scalar(
            select(H5GatewayJob)
            .where(H5GatewayJob.node_id == node_id, H5GatewayJob.status == "pending")
            .order_by(H5GatewayJob.created_at.asc())
        )

    def start_job(self, job: H5GatewayJob) -> H5GatewayJob:
        if job.status == "pending":
            job.status = "running"
            job.started_at = _utc_now()
            self.session.flush()
        return job

    def append_step(
        self,
        *,
        job: H5GatewayJob,
        step_name: str,
        command_name: str | None,
        status: str,
        stdout_tail: str | None = None,
        stderr_tail: str | None = None,
        result_json: dict[str, object] | None = None,
        exit_code: int | None = None,
    ) -> H5GatewayJobStep:
        started_at = _utc_now()
        finished_at = started_at if status in {"success", "failed", "skipped"} else None
        step = H5GatewayJobStep(
            job_id=job.id,
            node_id=job.node_id,
            step_name=step_name,
            command_name=command_name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            result_json=result_json or {},
            exit_code=exit_code,
        )
        self.session.add(step)
        self.session.flush()
        return step

    def finish_job(
        self,
        job: H5GatewayJob,
        *,
        status: str,
        result_json: dict[str, object] | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> H5GatewayJob:
        job.status = status
        job.finished_at = _utc_now()
        job.result_json = result_json or {}
        job.failure_code = failure_code
        job.failure_message = failure_message
        self.session.flush()
        return job

    def _validate_job_type(self, job_type: str) -> None:
        if job_type not in self.allowed_job_types:
            raise ValueError(f"Unsupported H5 gateway job type '{job_type}'.")
