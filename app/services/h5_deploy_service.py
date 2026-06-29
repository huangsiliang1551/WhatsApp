from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.core.settings import Settings, get_settings
from app.db.models import H5GatewayJob, H5GatewayNode, H5Site, H5SiteConfig
from app.services.h5_gateway_job_service import H5GatewayJobService
from app.services.h5_gateway_node_service import H5GatewayNodeService


class H5DeployService:
    def __init__(self, session: Session | None = None, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def generate_deploy_script(self, site: H5Site, config: H5SiteConfig) -> str:
        """Generate a Docker-based deployment script for the fixed H5 stack."""
        domain = config.domain or site.domain
        deploy_root = f"/opt/whatsapp-sites/{site.site_key}"

        return f"""#!/bin/bash
# Fixed H5 Docker deployment
# Site: {site.brand_name} ({site.site_key})
# Generated at: {datetime.now(UTC).isoformat()}

set -euo pipefail

SITE_KEY={site.site_key}
PUBLIC_SITE_DOMAIN={domain}
PUBLIC_TEMPLATE_ID={DEFAULT_H5_TEMPLATE_ID}
DEPLOY_ROOT={deploy_root}

echo "=== Deploy fixed H5 stack for $SITE_KEY ==="

mkdir -p "$DEPLOY_ROOT"
cd "$DEPLOY_ROOT"

cat > .env <<'ENV'
SITE_KEY={site.site_key}
PUBLIC_SITE_DOMAIN={domain}
PUBLIC_TEMPLATE_ID={DEFAULT_H5_TEMPLATE_ID}
APP_ENV=production
ENV

cat > docker-compose.h5.yml <<'COMPOSE'
services:
  app:
    image: ghcr.io/example/whatsapp-app:latest
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "8000:8000"

  frontend:
    image: ghcr.io/example/whatsapp-frontend:latest
    restart: unless-stopped
    env_file:
      - .env
    ports:
      - "80:80"
    depends_on:
      - app
COMPOSE

docker compose -f docker-compose.h5.yml pull
docker compose -f docker-compose.h5.yml up -d

echo "=== Deployment started ==="
echo "Preview URL: http://$PUBLIC_SITE_DOMAIN/h5/login?site_key=$SITE_KEY"
echo "Brand config: http://$PUBLIC_SITE_DOMAIN/api/h5/sites/$SITE_KEY/brand-config"
"""

    def verify_deployment(self, site: H5Site, config: H5SiteConfig) -> dict:
        """Verify fixed H5 frontend, SSL, and backend connectivity."""
        domain = config.domain or site.domain
        base_url = f"https://{domain}"
        preview_url = f"{base_url}/h5/login?site_key={site.site_key}"
        brand_config_url = f"{base_url}/api/h5/sites/{site.site_key}/brand-config"

        results: dict[str, object] = {
            "domain_accessible": False,
            "ssl_valid": False,
            "api_proxy_working": False,
            "h5_preview_working": False,
        }

        try:
            response = httpx.get(base_url, timeout=10, follow_redirects=True)
            results["domain_accessible"] = response.status_code < 500
            results["ssl_valid"] = True
        except Exception as exc:  # pragma: no cover
            results["error"] = str(exc)

        try:
            response = httpx.get(brand_config_url, timeout=10, follow_redirects=True)
            results["api_proxy_working"] = response.status_code == 200
        except Exception:  # pragma: no cover
            pass

        try:
            response = httpx.get(preview_url, timeout=10, follow_redirects=True)
            results["h5_preview_working"] = response.status_code == 200
        except Exception:  # pragma: no cover
            pass

        return results

    def resolve_gateway_node(
        self,
        *,
        site: H5Site,
        config: H5SiteConfig,
        gateway_node_id: str | None,
    ) -> H5GatewayNode:
        if self.session is None:
            raise ValueError("H5DeployService requires a database session for gateway orchestration.")
        resolved_node_id = gateway_node_id or config.gateway_node_id
        if not resolved_node_id:
            raise ValueError(f"H5 site '{site.id}' requires a gateway node selection before deployment.")
        return H5GatewayNodeService(self.session).get_node(resolved_node_id)

    def build_sync_config_payload(
        self,
        *,
        site: H5Site,
        config: H5SiteConfig,
        node: H5GatewayNode,
        blocked: bool,
    ) -> dict[str, object]:
        domain = config.domain or site.domain
        return {
            "site_id": site.id,
            "site_key": site.site_key,
            "gateway_node_id": node.id,
            "upstream_base_url": "https://a-server.internal",
            "origin_verify_header": "gateway-origin-placeholder",
            "domains": [
                {
                    "domain": domain,
                    "site_key": site.site_key,
                    "root_dir": f"/srv/h5/sites/{site.site_key}/current",
                    "certificate_mode": config.certificate_mode,
                    "blocked": blocked,
                }
            ],
        }

    def queue_gateway_deploy(
        self,
        *,
        site: H5Site,
        config: H5SiteConfig,
        gateway_node_id: str | None,
        requested_by: str,
    ) -> H5GatewayJob:
        node = self.resolve_gateway_node(site=site, config=config, gateway_node_id=gateway_node_id)
        payload = self.build_sync_config_payload(site=site, config=config, node=node, blocked=False)
        config.gateway_node_id = node.id
        config.dns_expected_value = node.public_ip or node.ssh_host
        config.desired_gateway_config_version += 1
        payload["config_version"] = config.desired_gateway_config_version
        job = self._job_service().create_job(
            node_id=node.id,
            job_type="sync_config",
            requested_by=requested_by,
            input_json=payload,
        )
        config.last_deploy_job_id = job.id
        return job

    def queue_domain_block(
        self,
        *,
        site: H5Site,
        config: H5SiteConfig,
        gateway_node_id: str | None,
        requested_by: str,
        blocked: bool,
    ) -> H5GatewayJob:
        node = self.resolve_gateway_node(site=site, config=config, gateway_node_id=gateway_node_id)
        payload = self.build_sync_config_payload(site=site, config=config, node=node, blocked=blocked)
        config.gateway_node_id = node.id
        config.desired_gateway_config_version += 1
        payload["config_version"] = config.desired_gateway_config_version
        job = self._job_service().create_job(
            node_id=node.id,
            job_type="block_domain" if blocked else "unblock_domain",
            requested_by=requested_by,
            input_json=payload,
        )
        config.last_deploy_job_id = job.id
        return job

    def queue_gateway_health_check(
        self,
        *,
        site: H5Site,
        config: H5SiteConfig,
        gateway_node_id: str | None,
        requested_by: str,
    ) -> H5GatewayJob:
        node = self.resolve_gateway_node(site=site, config=config, gateway_node_id=gateway_node_id)
        job = self._job_service().create_job(
            node_id=node.id,
            job_type="health_check",
            requested_by=requested_by,
            input_json={
                "site_id": site.id,
                "site_key": site.site_key,
                "domain": config.domain or site.domain,
                "gateway_node_id": node.id,
            },
        )
        config.last_verify_job_id = job.id
        return job

    def queue_issue_certificate(
        self,
        *,
        site: H5Site,
        config: H5SiteConfig,
        gateway_node_id: str | None,
        requested_by: str,
    ) -> H5GatewayJob:
        node = self.resolve_gateway_node(site=site, config=config, gateway_node_id=gateway_node_id)
        domain = config.domain or site.domain
        config.gateway_node_id = node.id
        job = self._job_service().create_job(
            node_id=node.id,
            job_type="issue_cert",
            requested_by=requested_by,
            input_json={
                "site_id": site.id,
                "site_key": site.site_key,
                "domain": domain,
                "gateway_node_id": node.id,
                "certificate_mode": config.certificate_mode,
                "dns_target_type": config.dns_target_type,
                "dns_expected_value": config.dns_expected_value,
            },
        )
        config.last_verify_job_id = job.id
        return job

    def _job_service(self) -> H5GatewayJobService:
        if self.session is None:
            raise ValueError("H5DeployService requires a database session for gateway orchestration.")
        return H5GatewayJobService(self.session, self.settings)
