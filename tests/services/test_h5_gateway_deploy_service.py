from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, H5GatewayNode, H5Site, H5SiteConfig
from app.services.h5_deploy_service import H5DeployService


def _seed_site(session: Session) -> tuple[H5Site, H5SiteConfig, H5GatewayNode]:
    session.add(Account(account_id="acct-deploy-svc", display_name="acct-deploy-svc", provider_type="mock"))
    site = H5Site(
        id="site-deploy-svc",
        account_id="acct-deploy-svc",
        site_key="deploy-svc-site",
        domain="deploy-svc.example.com",
        brand_name="Deploy Service Site",
    )
    config = H5SiteConfig(
        id="cfg-deploy-svc",
        site_id="site-deploy-svc",
        domain="gateway-svc.example.com",
        deploy_type="gateway",
        certificate_mode="certbot_http01",
        ssl_enabled=True,
    )
    node = H5GatewayNode(
        id="node-deploy-svc",
        name="Gateway Service Node",
        node_code="gateway-svc-node-1",
        ssh_host="10.0.0.13",
        ssh_port=22,
        ssh_user="whatsapp-gateway",
        ssh_credential_id="cred-svc",
        status="active",
        agent_mode="pull",
        public_ip="1.2.3.5",
    )
    session.add_all([site, config, node])
    session.commit()
    return site, config, node


def test_build_sync_config_payload_blocks_admin_apis_and_tracks_domain(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        site, config, node = _seed_site(session)

        payload = H5DeployService(session).build_sync_config_payload(
            site=site,
            config=config,
            node=node,
            blocked=False,
        )

    assert payload["upstream_base_url"] == "https://a-server.internal"
    assert payload["domains"][0]["domain"] == "gateway-svc.example.com"
    assert payload["domains"][0]["blocked"] is False
    assert payload["domains"][0]["certificate_mode"] == "certbot_http01"


def test_deploy_service_requires_resolved_gateway_node(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        site, config, _node = _seed_site(session)

        service = H5DeployService(session)

        try:
            service.resolve_gateway_node(site=site, config=config, gateway_node_id=None)
        except ValueError as exc:
            message = str(exc)
        else:
            raise AssertionError("expected ValueError when gateway node is missing")

    assert "gateway node" in message.lower()


def test_queue_issue_certificate_tracks_verify_job_and_domain_context(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        site, config, node = _seed_site(session)
        node_id = node.id
        config.gateway_node_id = node.id
        session.commit()

        job = H5DeployService(session).queue_issue_certificate(
            site=site,
            config=config,
            gateway_node_id=None,
            requested_by="super-admin",
        )
        session.commit()

        session.refresh(config)
        job_id = job.id
        job_type = job.job_type
        input_json = dict(job.input_json or {})
        last_verify_job_id = config.last_verify_job_id

    assert job_type == "issue_cert"
    assert input_json["domain"] == "gateway-svc.example.com"
    assert input_json["certificate_mode"] == "certbot_http01"
    assert input_json["gateway_node_id"] == node_id
    assert last_verify_job_id == job_id
