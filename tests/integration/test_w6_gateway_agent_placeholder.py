from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker


def _super_admin_headers() -> dict[str, str]:
    return {
        "X-Actor-Id": "w6-super-admin-h5-gateway",
        "X-Actor-Role": "super_admin",
    }


def test_w6_gateway_agent_placeholder_job_lifecycle(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    create = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "W6 Gateway Node",
            "node_code": "w6-b-sg-1",
            "ssh_host": "10.0.0.21",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "w6-private-key",
            "agent_token": "w6-agent-token",
        },
    )
    assert create.status_code == 201, create.text
    node_id = create.json()["id"]

    bootstrap = client.post(
        f"/api/h5-gateway/nodes/{node_id}/bootstrap",
        headers=_super_admin_headers(),
    )
    assert bootstrap.status_code == 202, bootstrap.text
    job_id = bootstrap.json()["job"]["id"]

    poll = client.get(
        "/api/h5-gateway/agent/jobs/poll",
        params={"node_code": "w6-b-sg-1"},
        headers={"Authorization": "Bearer w6-agent-token"},
    )
    assert poll.status_code == 200, poll.text
    assert poll.json()["job_id"] == job_id
    assert poll.json()["job_type"] == "bootstrap"

    start = client.post(
        f"/api/h5-gateway/agent/jobs/{job_id}/start",
        headers={"Authorization": "Bearer w6-agent-token"},
    )
    assert start.status_code == 200, start.text
    assert start.json()["status"] == "running"

    step = client.post(
        f"/api/h5-gateway/agent/jobs/{job_id}/step",
        headers={"Authorization": "Bearer w6-agent-token"},
        json={
            "step_name": "placeholder_bootstrap_step",
            "command_name": "bootstrap",
            "status": "success",
            "stdout_tail": "placeholder ok",
            "result_json": {"placeholder": True},
        },
    )
    assert step.status_code == 200, step.text
    assert step.json()["status"] == "success"

    finish = client.post(
        f"/api/h5-gateway/agent/jobs/{job_id}/finish",
        headers={"Authorization": "Bearer w6-agent-token"},
        json={
            "status": "success",
            "result_json": {"config_version": 5, "frontend_version": "2026.06.29"},
        },
    )
    assert finish.status_code == 200, finish.text
    assert finish.json()["status"] == "success"

    heartbeat = client.post(
        "/api/h5-gateway/agent/heartbeat",
        headers={"Authorization": "Bearer w6-agent-token"},
        json={
            "node_code": "w6-b-sg-1",
            "agent_version": "0.0.1-w6",
            "nginx_status": "active",
            "frontend_version": "2026.06.29",
            "config_version": 5,
            "blocked_domain_count": 0,
            "cpu": 12.5,
            "memory": 33.2,
            "disk": 44.8,
            "load": "0.10 0.20 0.30",
        },
    )
    assert heartbeat.status_code == 200, heartbeat.text
    assert heartbeat.json()["ok"] is True

    detail = client.get(
        f"/api/h5-gateway/nodes/{node_id}",
        headers=_super_admin_headers(),
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["agent_status"] == "online"
    assert payload["actual_config_version"] == 5
    assert payload["actual_frontend_version"] == "2026.06.29"


def test_w6_gateway_agent_placeholder_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/h5-gateway/agent/jobs/poll",
        params={"node_code": "missing-node"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid H5 gateway agent token."
