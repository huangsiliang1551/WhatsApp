from __future__ import annotations

import argparse
import json
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    payload = {"ok": True, "dry_run": args.dry_run, "mode": "pull", "polled": True}
    print(json.dumps(payload, ensure_ascii=False))
    if not args.once:
        time.sleep(0.01)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
