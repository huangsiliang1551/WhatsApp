from __future__ import annotations

import hashlib

from app.db.models import H5GatewayNode
from app.services.h5_gateway_credential_service import H5GatewayCredentialService
from sqlalchemy import select
from sqlalchemy.orm import Session


class H5GatewayNodeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.credential_service = H5GatewayCredentialService(session)

    def list_nodes(self) -> list[H5GatewayNode]:
        return self.session.scalars(select(H5GatewayNode).order_by(H5GatewayNode.created_at.asc())).all()

    def get_node(self, node_id: str) -> H5GatewayNode:
        node = self.session.get(H5GatewayNode, node_id)
        if node is None:
            raise ValueError(f"H5 gateway node '{node_id}' not found.")
        return node

    def get_node_by_code(self, node_code: str) -> H5GatewayNode:
        node = self.session.scalar(select(H5GatewayNode).where(H5GatewayNode.node_code == node_code))
        if node is None:
            raise ValueError(f"H5 gateway node code '{node_code}' not found.")
        return node

    def create_node(
        self,
        *,
        name: str,
        node_code: str,
        ssh_host: str,
        ssh_port: int,
        ssh_user: str,
        created_by: str,
        ssh_secret: str,
        public_ip: str | None = None,
        private_ip: str | None = None,
        region: str | None = None,
        agent_token: str | None = None,
    ) -> tuple[H5GatewayNode, dict[str, object]]:
        credential = self.credential_service.create_credential(
            name=f"{name} SSH credential",
            credential_type="ssh_private_key",
            secret=ssh_secret,
            created_by=created_by,
            metadata_json={"node_code": node_code},
        )
        node = H5GatewayNode(
            name=name,
            node_code=node_code,
            public_ip=public_ip,
            private_ip=private_ip,
            region=region,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            ssh_user=ssh_user,
            ssh_credential_id=credential.id,
            agent_mode="pull",
            status="bootstrap_required",
            agent_token_hash=self.hash_token(agent_token) if agent_token else None,
        )
        self.session.add(node)
        self.session.flush()
        return node, self.credential_service.serialize_credential(credential)

    @staticmethod
    def hash_token(token: str | None) -> str | None:
        if not token:
            return None
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def serialize_node(
        self,
        node: H5GatewayNode,
        *,
        credential_summary: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "id": node.id,
            "name": node.name,
            "node_code": node.node_code,
            "public_ip": node.public_ip,
            "private_ip": node.private_ip,
            "region": node.region,
            "ssh_host": node.ssh_host,
            "ssh_port": node.ssh_port,
            "ssh_user": node.ssh_user,
            "agent_mode": node.agent_mode,
            "status": node.status,
            "agent_status": node.agent_status,
            "nginx_status": node.nginx_status,
            "firewall_status": node.firewall_status,
            "certbot_status": node.certbot_status,
            "desired_config_version": node.desired_config_version,
            "actual_config_version": node.actual_config_version,
            "desired_frontend_version": node.desired_frontend_version,
            "actual_frontend_version": node.actual_frontend_version,
            "last_heartbeat_at": node.last_heartbeat_at.isoformat() if node.last_heartbeat_at else None,
            "cpu_usage_percent": float(node.cpu_usage_percent) if node.cpu_usage_percent is not None else None,
            "memory_usage_percent": float(node.memory_usage_percent) if node.memory_usage_percent is not None else None,
            "disk_usage_percent": float(node.disk_usage_percent) if node.disk_usage_percent is not None else None,
            "load_average": node.load_average,
            "credential": credential_summary,
            "metadata_json": node.metadata_json or {},
        }
