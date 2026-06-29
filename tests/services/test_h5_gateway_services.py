from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import H5GatewayCredential, H5GatewayJob, H5GatewayJobStep, H5GatewayNode
from app.services.h5_gateway_agent_service import H5GatewayAgentAuthError, H5GatewayAgentService
from app.services.h5_gateway_config_service import H5GatewayConfigService
from app.services.h5_gateway_credential_service import H5GatewayCredentialService
from app.services.h5_gateway_job_service import H5GatewayJobService
from app.services.h5_gateway_ssh_service import H5GatewaySSHService, H5GatewaySSHWhitelistError


def _seed_node(session: Session, *, node_id: str = "node-1", node_code: str = "b-sg-1") -> H5GatewayNode:
    node = H5GatewayNode(
        id=node_id,
        name="Singapore Gateway",
        node_code=node_code,
        ssh_host="10.10.10.10",
        ssh_port=22,
        ssh_user="whatsapp-gateway",
        status="bootstrap_required",
        agent_mode="pull",
    )
    session.add(node)
    session.commit()
    return node


def test_credential_service_encrypts_secret_and_stores_last4(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        service = H5GatewayCredentialService(session)

        credential = service.create_credential(
            name="B node SSH key",
            credential_type="ssh_private_key",
            secret="-----BEGIN PRIVATE KEY-----\nabc123XYZ\n-----END PRIVATE KEY-----",
            created_by="super-admin",
        )
        stored = session.get(H5GatewayCredential, credential.id)

    assert stored is not None
    assert stored.encrypted_secret != "-----BEGIN PRIVATE KEY-----\nabc123XYZ\n-----END PRIVATE KEY-----"
    assert stored.secret_last4 == "KEY-"
    assert service.get_secret(credential.id).endswith("-----END PRIVATE KEY-----")
    assert service.serialize_credential(credential)["has_secret"] is True
    assert "encrypted_secret" not in service.serialize_credential(credential)


def test_ssh_service_rejects_non_whitelisted_commands(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        credential = H5GatewayCredentialService(session).create_credential(
            name="SSH key",
            credential_type="ssh_private_key",
            secret="private-key-material",
            created_by="super-admin",
        )
        node = _seed_node(session)
        node.ssh_credential_id = credential.id
        session.commit()

        service = H5GatewaySSHService(session)

        with pytest.raises(H5GatewaySSHWhitelistError):
            service.execute_whitelisted(
                node=node,
                command_name="bash",
                payload={"script": "rm -rf /"},
            )


def test_agent_service_polls_starts_steps_and_finishes_job(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        node = _seed_node(session)
        node.agent_token_hash = H5GatewayAgentService.hash_token("shared-secret")
        session.commit()

        job_service = H5GatewayJobService(session)
        job = job_service.create_job(
            node_id=node.id,
            job_type="sync_config",
            requested_by="super-admin",
            trigger_source="manual",
            input_json={
                "domains": [
                    {
                        "domain": "shop.example.com",
                        "site_key": "mall-cn",
                        "root_dir": "/srv/h5/mall-cn",
                        "certificate_mode": "certbot_http01",
                        "blocked": False,
                    }
                ]
            },
        )

        agent_service = H5GatewayAgentService(session, shared_secret="shared-secret")
        polled = agent_service.poll_job(node_code=node.node_code, bearer_token="shared-secret")
        assert polled is not None
        assert polled["job_id"] == job.id
        assert polled["job_type"] == "sync_config"

        started = agent_service.start_job(job.id, bearer_token="shared-secret")
        assert started.status == "running"

        step = agent_service.append_job_step(
            job.id,
            bearer_token="shared-secret",
            step_name="render_config",
            command_name="apply_config",
            status="success",
            stdout_tail="config rendered",
            result_json={"path": "/etc/nginx/conf.d/h5_gateway.conf"},
        )
        assert step.status == "success"

        finished = agent_service.finish_job(
            job.id,
            bearer_token="shared-secret",
            status="success",
            result_json={"config_version": 3},
        )
        assert finished.status == "success"

        refreshed_job = session.get(H5GatewayJob, job.id)
        steps = session.scalars(select(H5GatewayJobStep).where(H5GatewayJobStep.job_id == job.id)).all()

    assert refreshed_job is not None
    assert refreshed_job.result_json == {"config_version": 3}
    assert len(steps) == 1
    assert steps[0].step_name == "render_config"


def test_agent_service_rejects_invalid_token(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        node = _seed_node(session)
        node.agent_token_hash = H5GatewayAgentService.hash_token("shared-secret")
        session.commit()

        service = H5GatewayAgentService(session, shared_secret="shared-secret")

        with pytest.raises(H5GatewayAgentAuthError):
            service.poll_job(node_code=node.node_code, bearer_token="wrong-secret")


def test_config_service_renders_h5_only_nginx_config() -> None:
    config_text = H5GatewayConfigService().render_config(
        domains=[
            {
                "domain": "shop.example.com",
                "site_key": "mall-cn",
                "root_dir": "/srv/h5/mall-cn/current",
                "certificate_mode": "certbot_http01",
                "blocked": False,
            },
            {
                "domain": "blocked.example.com",
                "site_key": "mall-cn",
                "root_dir": "/srv/h5/mall-cn/current",
                "certificate_mode": "certbot_http01",
                "blocked": True,
            },
        ],
        upstream_base_url="https://a-server.internal",
        origin_verify_header="origin-secret",
    )

    assert "location /api/h5/" in config_text
    assert "proxy_pass https://a-server.internal;" in config_text
    assert "location /api/admin/" in config_text
    assert "return 403;" in config_text
    assert "blocked.example.com" in config_text
    assert "return 451;" in config_text


def test_render_gateway_config_script_supports_dry_run_json_output(tmp_path: Path) -> None:
    payload_path = tmp_path / "domains.json"
    payload_path.write_text(
        json.dumps(
            {
                "upstream_base_url": "https://a-server.internal",
                "origin_verify_header": "origin-secret",
                "domains": [
                    {
                        "domain": "shop.example.com",
                        "site_key": "mall-cn",
                        "root_dir": "/srv/h5/mall-cn/current",
                        "certificate_mode": "certbot_http01",
                        "blocked": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    script_path = Path("deploy/h5-gateway/scripts/render_gateway_config.py")
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--input",
            str(payload_path),
            "--dry-run",
            "--json-output",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["config_path"].endswith("h5_gateway.conf")
    assert "location /api/admin/" in payload["config_preview"]
