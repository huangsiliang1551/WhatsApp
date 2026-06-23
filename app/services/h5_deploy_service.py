from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.db.models import H5Site, H5SiteConfig


class H5DeployService:
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
        except Exception as exc:  # pragma: no cover - network failures depend on environment
            results["error"] = str(exc)

        try:
            response = httpx.get(brand_config_url, timeout=10, follow_redirects=True)
            results["api_proxy_working"] = response.status_code == 200
        except Exception:  # pragma: no cover - network failures depend on environment
            pass

        try:
            response = httpx.get(preview_url, timeout=10, follow_redirects=True)
            results["h5_preview_working"] = response.status_code == 200
        except Exception:  # pragma: no cover - network failures depend on environment
            pass

        return results
