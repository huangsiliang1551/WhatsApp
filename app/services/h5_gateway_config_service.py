from __future__ import annotations


class H5GatewayConfigService:
    def render_config(
        self,
        *,
        domains: list[dict[str, object]],
        upstream_base_url: str,
        origin_verify_header: str,
    ) -> str:
        parts = [
            "map $http_x_origin_verify $origin_verified {",
            "    default 0;",
            f'    "{origin_verify_header}" 1;',
            "}",
            "",
        ]
        for domain in domains:
            parts.extend(self._render_server_block(domain=domain, upstream_base_url=upstream_base_url))
            parts.append("")
        return "\n".join(parts).strip() + "\n"

    def _render_server_block(self, *, domain: dict[str, object], upstream_base_url: str) -> list[str]:
        hostname = str(domain["domain"])
        root_dir = str(domain["root_dir"])
        blocked = bool(domain.get("blocked", False))
        server = [
            "server {",
            "    listen 80;",
            f"    server_name {hostname};",
            "",
        ]
        if blocked:
            server.extend(
                [
                    "    location / {",
                    "        return 451;",
                    "    }",
                ]
            )
        else:
            server.extend(
                [
                    "    location /api/h5/ {",
                    "        if ($origin_verified = 0) { return 403; }",
                    f"        proxy_pass {upstream_base_url};",
                    "    }",
                    "",
                    "    location /api/admin/ {",
                    "        return 403;",
                    "    }",
                    "",
                    "    location /api/finance/ {",
                    "        return 403;",
                    "    }",
                    "",
                    "    location / {",
                    f"        root {root_dir};",
                    "        try_files $uri $uri/ /index.html;",
                    "    }",
                ]
            )
        server.append("}")
        return server
