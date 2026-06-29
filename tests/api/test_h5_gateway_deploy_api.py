from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, H5GatewayJob, H5GatewayNode, H5Site, H5SiteConfig


def _super_admin_headers() -> dict[str, str]:
    return {
        "X-Actor-Id": "super-admin-h5-deploy",
        "X-Actor-Role": "super_admin",
    }


def _seed_site_and_node(session: Session) -> tuple[str, str]:
    session.add(Account(account_id="acct-deploy", display_name="acct-deploy", provider_type="mock"))
    site = H5Site(
        id="site-deploy",
        account_id="acct-deploy",
        site_key="deploy-site",
        domain="deploy.example.com",
        brand_name="Deploy Site",
    )
    config = H5SiteConfig(
        id="cfg-deploy",
        site_id="site-deploy",
        domain="gateway.example.com",
        deploy_type="gateway",
        ssl_enabled=True,
        certificate_mode="certbot_http01",
    )
    node = H5GatewayNode(
        id="node-deploy",
        name="Gateway Node",
        node_code="gateway-node-1",
        ssh_host="10.0.0.12",
        ssh_port=22,
        ssh_user="whatsapp-gateway",
        ssh_credential_id="cred-1",
        status="active",
        agent_mode="pull",
        public_ip="1.2.3.4",
    )
    session.add_all([site, config, node])
    session.commit()
    return site.id, node.id


def test_deploy_to_gateway_selects_node_and_creates_sync_config_job(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        site_id, node_id = _seed_site_and_node(session)

    response = client.post(
        f"/api/h5/sites/{site_id}/deploy-to-gateway",
        headers=_super_admin_headers(),
        json={"gateway_node_id": node_id},
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job"]["job_type"] == "sync_config"
    assert payload["job"]["node_id"] == node_id
    assert payload["job"]["input_json"]["domains"][0]["domain"] == "gateway.example.com"
    assert payload["job"]["input_json"]["domains"][0]["blocked"] is False

    with db_session_factory() as session:
        config = session.get(H5SiteConfig, "cfg-deploy")
        job = session.get(H5GatewayJob, payload["job"]["id"])

    assert config is not None
    assert config.gateway_node_id == node_id
    assert config.desired_gateway_config_version == 1
    assert config.last_deploy_job_id == payload["job"]["id"]
    assert job is not None
    assert job.job_type == "sync_config"


def test_block_unblock_and_health_check_jobs_use_bound_gateway_node(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        site_id, node_id = _seed_site_and_node(session)
        config = session.get(H5SiteConfig, "cfg-deploy")
        assert config is not None
        config.gateway_node_id = node_id
        session.commit()

    block_response = client.post(
        f"/api/h5/sites/{site_id}/block-domain",
        headers=_super_admin_headers(),
    )
    unblock_response = client.post(
        f"/api/h5/sites/{site_id}/unblock-domain",
        headers=_super_admin_headers(),
    )
    health_response = client.post(
        f"/api/h5/sites/{site_id}/gateway-health-check",
        headers=_super_admin_headers(),
    )

    assert block_response.status_code == 202, block_response.text
    assert unblock_response.status_code == 202, unblock_response.text
    assert health_response.status_code == 202, health_response.text
    assert block_response.json()["job"]["job_type"] == "block_domain"
    assert unblock_response.json()["job"]["job_type"] == "unblock_domain"
    assert health_response.json()["job"]["job_type"] == "health_check"

    with db_session_factory() as session:
        config = session.get(H5SiteConfig, "cfg-deploy")

    assert config is not None
    assert config.last_verify_job_id == health_response.json()["job"]["id"]


def test_issue_certificate_uses_bound_gateway_node_and_tracks_job(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        site_id, node_id = _seed_site_and_node(session)
        config = session.get(H5SiteConfig, "cfg-deploy")
        assert config is not None
        config.gateway_node_id = node_id
        session.commit()

    response = client.post(
        f"/api/h5/sites/{site_id}/issue-certificate",
        headers=_super_admin_headers(),
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job"]["job_type"] == "issue_cert"
    assert payload["job"]["node_id"] == node_id
    assert payload["job"]["input_json"]["domain"] == "gateway.example.com"
    assert payload["job"]["input_json"]["certificate_mode"] == "certbot_http01"

    with db_session_factory() as session:
        config = session.get(H5SiteConfig, "cfg-deploy")

    assert config is not None
    assert config.last_verify_job_id == payload["job"]["id"]


def test_deploy_to_gateway_requires_gateway_node_selection(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        site_id, _node_id = _seed_site_and_node(session)

    response = client.post(
        f"/api/h5/sites/{site_id}/deploy-to-gateway",
        headers=_super_admin_headers(),
        json={},
    )

    assert response.status_code == 409
    assert "gateway node" in response.json()["detail"].lower()
