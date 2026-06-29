from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import glob

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""

def main() -> int:
    repo = Path(".").resolve()
    base = repo / "docs" / "dev-run" / "parallel"
    status_dir = base / "status"
    out = base / "RESUME_SUMMARY.md"

    lines = []
    lines.append("# RESUME_SUMMARY")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append("## Master Progress")
    lines.append(read(base / "MASTER_PROGRESS.md")[:4000] or "MASTER_PROGRESS.md not found")
    lines.append("")
    lines.append("## Worker Status Summary")

    for p in sorted(status_dir.glob("W*.md")):
        text = read(p)
        head = "\n".join(text.splitlines()[:40])
        lines.append(f"### {p.name}")
        lines.append("```text")
        lines.append(head)
        lines.append("```")

    progress_dir = repo / ".codex-run" / "progress"
    if progress_dir.exists():
        progress_files = sorted(progress_dir.glob("*.json"))
        lines.append("")
        lines.append(f"## Existing .codex-run/progress")
        lines.append(f"Found {len(progress_files)} json progress files. Do not delete them.")
        for p in progress_files[-20:]:
            lines.append(f"- {p.name}")

    blockers = read(base / "env" / "EXTERNAL_BLOCKERS.md")
    lines.append("")
    lines.append("## External Blockers")
    lines.append(blockers[:3000] or "No external blockers file yet.")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[resume] wrote {out}")
    print("[resume] Read RESUME_SUMMARY.md and continue incomplete Worker. Do not restart completed phases.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
