from __future__ import annotations

from pathlib import Path

from app.core.settings import Settings, get_settings
from app.db.models import H5GatewayNode
from sqlalchemy.orm import Session


class H5GatewaySSHWhitelistError(ValueError):
    pass


class H5GatewaySSHService:
    SCRIPT_MAP: dict[str, str] = {
        "test_ssh": "health_check.py",
        "bootstrap": "bootstrap_b_node.py",
        "install_agent": "install_or_update_agent.py",
        "deploy_frontend": "deploy_frontend_release.py",
        "sync_config": "render_gateway_config.py",
        "issue_cert": "issue_cert.py",
        "renew_cert": "renew_certs.py",
        "reload_nginx": "reload_nginx.py",
        "security_hardening": "security_hardening.py",
        "block_domain": "block_domain.py",
        "unblock_domain": "unblock_domain.py",
        "health_check": "health_check.py",
        "rollback": "rollback_release.py",
    }

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def execute_whitelisted(
        self,
        *,
        node: H5GatewayNode,
        command_name: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        script_name = self.SCRIPT_MAP.get(command_name)
        if script_name is None:
            raise H5GatewaySSHWhitelistError(f"Command '{command_name}' is not in the H5 gateway whitelist.")
        if not node.ssh_host or not node.ssh_user:
            raise ValueError(f"H5 gateway node '{node.id}' is missing SSH host/user configuration.")
        if not node.ssh_credential_id:
            raise ValueError(f"H5 gateway node '{node.id}' is missing SSH credentials.")

        script_path = Path(self.settings.h5_gateway_script_root) / script_name
        return {
            "ok": True,
            "dry_run": True,
            "node_id": node.id,
            "node_code": node.node_code,
            "command_name": command_name,
            "script_path": str(script_path).replace("\\", "/"),
            "ssh_target": f"{node.ssh_user}@{node.ssh_host}:{node.ssh_port}",
            "payload": payload or {},
        }
