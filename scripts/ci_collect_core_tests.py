from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence


COLLECT_COMMAND: tuple[str, ...] = (
    sys.executable,
    "-m",
    "pytest",
    "--collect-only",
    "tests",
    "tests/api",
    "tests/services",
    "-q",
)

REQUIRED_GROUPS: dict[str, tuple[str, ...]] = {
    "tests/api": ("tests/api/",),
    "tests/services": ("tests/services/",),
    "wallet": ("wallet",),
    "finance": ("finance",),
    "withdrawal": ("withdrawal",),
    "payment": ("payment",),
    "webhook": ("webhook",),
    "whatsapp": ("whatsapp",),
    "h5_gateway": ("h5_gateway",),
    "permission": ("permission",),
}


def parse_nodeids(stdout: str) -> list[str]:
    nodeids: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("=") or line.startswith("-") or line.startswith("warnings summary"):
            continue
        if " collected" in line and line.endswith("s"):
            continue
        if ".py::" in line:
            nodeids.append(line)
    return nodeids


def find_missing_groups(nodeids: Sequence[str]) -> list[str]:
    lowered = [nodeid.lower() for nodeid in nodeids]
    missing: list[str] = []
    for group, needles in REQUIRED_GROUPS.items():
        if not any(any(needle in nodeid for needle in needles) for nodeid in lowered):
            missing.append(group)
    return missing


def main() -> int:
    result = subprocess.run(
        COLLECT_COMMAND,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "pytest collection failed",
                    "command": list(COLLECT_COMMAND),
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                ensure_ascii=False,
            )
        )
        return 2

    nodeids = parse_nodeids(result.stdout)
    missing_groups = find_missing_groups(nodeids)
    payload = {
        "ok": not missing_groups,
        "command": list(COLLECT_COMMAND),
        "collected_count": len(nodeids),
        "missing_groups": missing_groups,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not missing_groups else 1


if __name__ == "__main__":
    raise SystemExit(main())
