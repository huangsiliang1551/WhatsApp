from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import H5FrontendRelease, H5GatewayJob, H5GatewayNode, H5GatewayNodeRelease
from app.services.h5_gateway_agent_service import H5GatewayAgentService


def _super_admin_headers() -> dict[str, str]:
    return {
        "X-Actor-Id": "super-admin-h5-gateway",
        "X-Actor-Role": "super_admin",
    }


def test_h5_gateway_node_crud_and_test_ssh(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node",
            "node_code": "b-sg-1",
            "public_ip": "1.1.1.1",
            "ssh_host": "10.0.0.10",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret",
        },
    )
    assert create_response.status_code == 201, create_response.text
    payload = create_response.json()
    assert payload["node_code"] == "b-sg-1"
    assert payload["credential"]["has_secret"] is True
    assert payload["agent_mode"] == "pull"

    list_response = client.get("/api/h5-gateway/nodes", headers=_super_admin_headers())
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["items"][0]["node_code"] == "b-sg-1"

    node_id = payload["id"]
    ssh_response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/test-ssh",
        headers=_super_admin_headers(),
    )
    assert ssh_response.status_code == 200, ssh_response.text
    ssh_payload = ssh_response.json()
    assert ssh_payload["ok"] is True
    assert ssh_payload["command_name"] == "test_ssh"
    assert ssh_payload["dry_run"] is True

    with db_session_factory() as session:
        stored = session.get(H5GatewayNode, node_id)

    assert stored is not None
    assert stored.status == "bootstrap_required"


def test_h5_gateway_agent_job_lifecycle_api(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node",
            "node_code": "b-sg-2",
            "ssh_host": "10.0.0.11",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-2",
        },
    )
    assert create_response.status_code == 201, create_response.text
    node_id = create_response.json()["id"]

    bootstrap_response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/bootstrap",
        headers=_super_admin_headers(),
    )
    assert bootstrap_response.status_code == 202, bootstrap_response.text
    job_id = bootstrap_response.json()["job"]["id"]

    poll_response = client.get(
        "/api/h5-gateway/agent/jobs/poll",
        params={"node_code": "b-sg-2"},
        headers={"Authorization": "Bearer shared-secret-2"},
    )
    assert poll_response.status_code == 200, poll_response.text
    poll_payload = poll_response.json()
    assert poll_payload["job_id"] == job_id
    assert poll_payload["job_type"] == "bootstrap"

    start_response = client.post(
        f"/api/h5-gateway/agent/jobs/{job_id}/start",
        headers={"Authorization": "Bearer shared-secret-2"},
    )
    assert start_response.status_code == 200, start_response.text
    assert start_response.json()["status"] == "running"

    step_response = client.post(
        f"/api/h5-gateway/agent/jobs/{job_id}/step",
        headers={"Authorization": "Bearer shared-secret-2"},
        json={
            "step_name": "bootstrap_b_node",
            "command_name": "bootstrap",
            "status": "success",
            "stdout_tail": "bootstrap ok",
            "result_json": {"port_80_available": True},
        },
    )
    assert step_response.status_code == 200, step_response.text
    assert step_response.json()["status"] == "success"

    finish_response = client.post(
        f"/api/h5-gateway/agent/jobs/{job_id}/finish",
        headers={"Authorization": "Bearer shared-secret-2"},
        json={
            "status": "success",
            "result_json": {"agent_installed": True},
        },
    )
    assert finish_response.status_code == 200, finish_response.text
    assert finish_response.json()["status"] == "success"

    heartbeat_response = client.post(
        "/api/h5-gateway/agent/heartbeat",
        headers={"Authorization": "Bearer shared-secret-2"},
        json={
            "node_code": "b-sg-2",
            "agent_version": "0.1.0",
            "nginx_status": "active",
            "frontend_version": "2026.06.28",
            "config_version": 3,
            "blocked_domain_count": 1,
            "cpu": 24.5,
            "memory": 51.2,
            "disk": 61.7,
            "load": "0.50 0.60 0.70",
        },
    )
    assert heartbeat_response.status_code == 200, heartbeat_response.text
    assert heartbeat_response.json()["ok"] is True

    detail_response = client.get(
        f"/api/h5-gateway/nodes/{node_id}",
        headers=_super_admin_headers(),
    )
    assert detail_response.status_code == 200, detail_response.text
    detail_payload = detail_response.json()
    assert detail_payload["agent_status"] == "online"
    assert detail_payload["nginx_status"] == "active"
    assert detail_payload["actual_config_version"] == 3


def test_h5_gateway_node_security_hardening_creates_job(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node",
            "node_code": "b-sg-3",
            "ssh_host": "10.0.0.12",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-3",
        },
    )
    assert create_response.status_code == 201, create_response.text
    node_id = create_response.json()["id"]

    response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/security-hardening",
        headers=_super_admin_headers(),
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job"]["job_type"] == "security_hardening"
    assert payload["job"]["status"] == "pending"


def test_h5_gateway_node_install_reload_and_rollback_create_jobs(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node",
            "node_code": "b-sg-4",
            "ssh_host": "10.0.0.13",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-4",
        },
    )
    assert create_response.status_code == 201, create_response.text
    node_id = create_response.json()["id"]

    install_response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/install-agent",
        headers=_super_admin_headers(),
    )
    reload_response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/reload-nginx",
        headers=_super_admin_headers(),
    )
    rollback_response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/rollback",
        headers=_super_admin_headers(),
    )

    assert install_response.status_code == 202, install_response.text
    assert reload_response.status_code == 202, reload_response.text
    assert rollback_response.status_code == 202, rollback_response.text
    assert install_response.json()["job"]["job_type"] == "install_agent"
    assert reload_response.json()["job"]["job_type"] == "reload_nginx"
    assert rollback_response.json()["job"]["job_type"] == "rollback"


def test_h5_gateway_node_deploy_frontend_creates_job_with_release_payload(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node",
            "node_code": "b-sg-5",
            "ssh_host": "10.0.0.14",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-5",
        },
    )
    assert create_response.status_code == 201, create_response.text
    node_id = create_response.json()["id"]

    response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/deploy-frontend",
        headers=_super_admin_headers(),
        json={
            "version": "2026.06.29",
            "artifact_url": "https://example.internal/h5-frontend-2026.06.29.tar.gz",
            "artifact_sha256": "abc123sha256",
        },
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job"]["job_type"] == "deploy_frontend"
    assert payload["job"]["input_json"]["version"] == "2026.06.29"
    assert payload["job"]["input_json"]["artifact_url"].endswith(".tar.gz")
    assert payload["job"]["input_json"]["artifact_sha256"] == "abc123sha256"


def test_h5_gateway_node_sync_config_creates_job_with_gateway_payload(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    create_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node",
            "node_code": "b-sg-6",
            "ssh_host": "10.0.0.15",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-6",
        },
    )
    assert create_response.status_code == 201, create_response.text
    node_id = create_response.json()["id"]

    response = client.post(
        f"/api/h5-gateway/nodes/{node_id}/sync-config",
        headers=_super_admin_headers(),
        json={
            "upstream_base_url": "https://a-server.internal",
            "origin_verify_header": "origin-secret",
            "domains": [
                {
                    "domain": "shop.example.com",
                    "site_key": "mall-cn",
                    "root_dir": "/srv/h5/sites/mall-cn/current",
                    "certificate_mode": "certbot_http01",
                    "blocked": False,
                }
            ],
        },
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job"]["job_type"] == "sync_config"
    assert payload["job"]["input_json"]["upstream_base_url"] == "https://a-server.internal"
    assert payload["job"]["input_json"]["domains"][0]["domain"] == "shop.example.com"


def test_h5_gateway_release_registry_create_list_and_deploy_to_node(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    node_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node",
            "node_code": "b-sg-7",
            "ssh_host": "10.0.0.16",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-7",
        },
    )
    assert node_response.status_code == 201, node_response.text
    node_id = node_response.json()["id"]

    create_response = client.post(
        "/api/h5-gateway/releases",
        headers=_super_admin_headers(),
        json={
            "version": "2026.06.29-r1",
            "artifact_url": "https://example.internal/h5-frontend-2026.06.29-r1.tar.gz",
            "artifact_sha256": "sha256-r1",
            "build_commit": "abcdef123456",
        },
    )

    assert create_response.status_code == 201, create_response.text
    release_payload = create_response.json()
    assert release_payload["version"] == "2026.06.29-r1"

    list_response = client.get("/api/h5-gateway/releases", headers=_super_admin_headers())
    assert list_response.status_code == 200, list_response.text
    assert list_response.json()["items"][0]["version"] == "2026.06.29-r1"

    deploy_response = client.post(
        f"/api/h5-gateway/releases/{release_payload['id']}/deploy-to-node",
        headers=_super_admin_headers(),
        json={"node_id": node_id},
    )
    assert deploy_response.status_code == 202, deploy_response.text
    job_payload = deploy_response.json()["job"]
    assert job_payload["job_type"] == "deploy_frontend"
    assert job_payload["node_id"] == node_id
    assert job_payload["input_json"]["version"] == "2026.06.29-r1"

    with db_session_factory() as session:
        release = session.get(H5FrontendRelease, release_payload["id"])
        job = session.get(H5GatewayJob, job_payload["id"])
        node_release = session.query(H5GatewayNodeRelease).filter(
            H5GatewayNodeRelease.node_id == node_id,
            H5GatewayNodeRelease.release_id == release_payload["id"],
        ).one_or_none()

    assert release is not None
    assert release.build_commit == "abcdef123456"
    assert job is not None
    assert job.job_type == "deploy_frontend"
    assert node_release is not None
    assert node_release.status == "deploying"


def test_h5_gateway_release_deploy_to_all_creates_jobs_for_active_nodes(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    node_a_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node A",
            "node_code": "b-sg-8a",
            "ssh_host": "10.0.0.17",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-8a",
        },
    )
    node_b_response = client.post(
        "/api/h5-gateway/nodes",
        headers=_super_admin_headers(),
        json={
            "name": "Singapore B Node B",
            "node_code": "b-sg-8b",
            "ssh_host": "10.0.0.18",
            "ssh_port": 22,
            "ssh_user": "whatsapp-gateway",
            "ssh_secret": "private-key-material",
            "agent_token": "shared-secret-8b",
        },
    )
    assert node_a_response.status_code == 201, node_a_response.text
    assert node_b_response.status_code == 201, node_b_response.text
    node_a_id = node_a_response.json()["id"]
    node_b_id = node_b_response.json()["id"]

    with db_session_factory() as session:
        node_a = session.get(H5GatewayNode, node_a_id)
        node_b = session.get(H5GatewayNode, node_b_id)
        assert node_a is not None
        assert node_b is not None
        node_a.status = "active"
        node_b.status = "active"
        session.commit()

    create_response = client.post(
        "/api/h5-gateway/releases",
        headers=_super_admin_headers(),
        json={
            "version": "2026.06.29-r2",
            "artifact_url": "https://example.internal/h5-frontend-2026.06.29-r2.tar.gz",
            "artifact_sha256": "sha256-r2",
        },
    )
    assert create_response.status_code == 201, create_response.text
    release_id = create_response.json()["id"]

    deploy_response = client.post(
        f"/api/h5-gateway/releases/{release_id}/deploy-to-all",
        headers=_super_admin_headers(),
    )

    assert deploy_response.status_code == 202, deploy_response.text
    payload = deploy_response.json()
    assert payload["job_count"] == 2
    assert {item["node_id"] for item in payload["jobs"]} == {node_a_id, node_b_id}
    assert all(item["job_type"] == "deploy_frontend" for item in payload["jobs"])

    with db_session_factory() as session:
        jobs = session.query(H5GatewayJob).filter(H5GatewayJob.input_json["release_id"].as_string() == release_id).all()
        node_releases = session.query(H5GatewayNodeRelease).filter(H5GatewayNodeRelease.release_id == release_id).all()

    assert len(jobs) == 2
    assert len(node_releases) == 2
    assert {item.node_id for item in node_releases} == {node_a_id, node_b_id}
    assert all(item.status == "deploying" for item in node_releases)


def test_h5_gateway_agent_rejects_bad_token(client) -> None:
    response = client.get(
        "/api/h5-gateway/agent/jobs/poll",
        params={"node_code": "missing"},
        headers={"Authorization": "Bearer wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid H5 gateway agent token."
