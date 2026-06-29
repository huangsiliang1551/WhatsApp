from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-output", action="store_true")
    args = parser.parse_args()
    payload = {"ok": True, "dry_run": args.dry_run, "reloaded": True}
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print("reloaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
