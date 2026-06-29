from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.h5_gateway_config_service import H5GatewayConfigService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="/etc/nginx/conf.d/h5_gateway.conf")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    config_preview = H5GatewayConfigService().render_config(
        domains=payload["domains"],
        upstream_base_url=payload["upstream_base_url"],
        origin_verify_header=payload.get("origin_verify_header", ""),
    )
    result = {
        "ok": True,
        "dry_run": args.dry_run,
        "config_path": args.output,
        "config_preview": config_preview,
    }
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(config_preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
