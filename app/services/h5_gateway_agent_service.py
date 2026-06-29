from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.db.models import H5GatewayJob, H5GatewayNode
from app.services.h5_gateway_job_service import H5GatewayJobService
from app.services.h5_gateway_node_service import H5GatewayNodeService
from sqlalchemy.orm import Session


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class H5GatewayAgentAuthError(ValueError):
    pass


class H5GatewayAgentService:
    def __init__(self, session: Session, shared_secret: str = "") -> None:
        self.session = session
        self.shared_secret = shared_secret
        self.node_service = H5GatewayNodeService(session)
        self.job_service = H5GatewayJobService(session)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def poll_job(self, *, node_code: str, bearer_token: str) -> dict[str, object] | None:
        node = self._authenticate(node_code=node_code, bearer_token=bearer_token)
        job = self.job_service.poll_pending_job(node_id=node.id)
        if job is None:
            return None
        return self.serialize_job(job)

    def start_job(self, job_id: str, *, bearer_token: str) -> H5GatewayJob:
        job = self._load_job(job_id)
        self._authenticate(node_code=self.node_service.get_node(job.node_id).node_code, bearer_token=bearer_token)
        return self.job_service.start_job(job)

    def append_job_step(
        self,
        job_id: str,
        *,
        bearer_token: str,
        step_name: str,
        command_name: str | None,
        status: str,
        stdout_tail: str | None = None,
        stderr_tail: str | None = None,
        result_json: dict[str, object] | None = None,
        exit_code: int | None = None,
    ):
        job = self._load_job(job_id)
        self._authenticate(node_code=self.node_service.get_node(job.node_id).node_code, bearer_token=bearer_token)
        return self.job_service.append_step(
            job=job,
            step_name=step_name,
            command_name=command_name,
            status=status,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
            result_json=result_json,
            exit_code=exit_code,
        )

    def finish_job(
        self,
        job_id: str,
        *,
        bearer_token: str,
        status: str,
        result_json: dict[str, object] | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> H5GatewayJob:
        job = self._load_job(job_id)
        node = self.node_service.get_node(job.node_id)
        self._authenticate(node_code=node.node_code, bearer_token=bearer_token)
        finished = self.job_service.finish_job(
            job,
            status=status,
            result_json=result_json,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        if result_json:
            if "config_version" in result_json:
                node.actual_config_version = int(result_json["config_version"])
            if "frontend_version" in result_json:
                node.actual_frontend_version = str(result_json["frontend_version"])
        if status == "success":
            node.status = "active"
            node.agent_status = "online"
        self.session.flush()
        return finished

    def record_heartbeat(
        self,
        *,
        node_code: str,
        bearer_token: str,
        payload: dict[str, object],
    ) -> H5GatewayNode:
        node = self._authenticate(node_code=node_code, bearer_token=bearer_token)
        node.agent_status = "online"
        node.status = "active"
        node.last_heartbeat_at = _utc_now()
        node.nginx_status = str(payload.get("nginx_status") or node.nginx_status or "unknown")
        node.actual_frontend_version = str(payload.get("frontend_version") or node.actual_frontend_version or "")
        node.actual_config_version = int(payload.get("config_version") or node.actual_config_version or 0)
        node.cpu_usage_percent = payload.get("cpu")
        node.memory_usage_percent = payload.get("memory")
        node.disk_usage_percent = payload.get("disk")
        node.load_average = str(payload.get("load") or node.load_average or "")
        self.session.flush()
        return node

    def serialize_job(self, job: H5GatewayJob) -> dict[str, object]:
        return {
            "job_id": job.id,
            "node_id": job.node_id,
            "job_type": job.job_type,
            "status": job.status,
            "trigger_source": job.trigger_source,
            "input_json": job.input_json or {},
            "result_json": job.result_json or {},
        }

    def _authenticate(self, *, node_code: str, bearer_token: str) -> H5GatewayNode:
        try:
            node = self.node_service.get_node_by_code(node_code)
        except ValueError as exc:
            raise H5GatewayAgentAuthError("Invalid H5 gateway agent token.") from exc
        token_hash = self.hash_token(bearer_token)
        if node.agent_token_hash != token_hash:
            raise H5GatewayAgentAuthError("Invalid H5 gateway agent token.")
        return node

    def _load_job(self, job_id: str) -> H5GatewayJob:
        job = self.session.get(H5GatewayJob, job_id)
        if job is None:
            raise ValueError(f"H5 gateway job '{job_id}' not found.")
        return job
