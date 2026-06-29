from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITES: tuple[tuple[str, str], ...] = (
    ("runtime_e2e", r"tests\e2e\test_w6_runtime_message_flows.py"),
    ("legacy_migrated_e2e", r"tests\e2e\test_w6_legacy_integration_e2e_migrated.py"),
    ("payment_smoke", r"tests\integration\test_w6_payment_callback_smoke.py"),
    ("permissions_h5_smoke", r"tests\integration\test_w6_permissions_h5_smoke.py"),
    ("gateway_agent_placeholder", r"tests\integration\test_w6_gateway_agent_placeholder.py"),
)
TMP_DIRS: tuple[Path, ...] = (
    ROOT / ".tmp_pytest",
    ROOT / ".tmp_pytest_local",
    ROOT / ".tmp_runtime_check",
)


def cleanup_runtime_dirs() -> None:
    for path in TMP_DIRS:
        shutil.rmtree(path, ignore_errors=True)


def run_suite(label: str, relative_path: str) -> int:
    cleanup_runtime_dirs()
    command = [sys.executable, "-m", "pytest", relative_path, "-q"]
    print(f"[W6] running {label}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    print(f"[W6] {label} exit_code={completed.returncode}", flush=True)
    return completed.returncode


def main() -> int:
    failures: list[str] = []
    for label, relative_path in SUITES:
        exit_code = run_suite(label, relative_path)
        if exit_code != 0:
            failures.append(label)

    if failures:
        print(f"[W6] smoke failed: {', '.join(failures)}", flush=True)
        return 1

    print("[W6] smoke passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
