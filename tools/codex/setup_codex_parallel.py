from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
from pathlib import Path

MARKER = "<!-- CODEX_PARALLEL_AUTORUN_V2_START -->"

def copytree_merge(src: Path, dst: Path, overwrite: bool = True) -> None:
    if not src.exists():
        return
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if overwrite or not target.exists():
                shutil.copy2(item, target)

def archive_docs(repo: Path, package_docs: Path, reset_progress: bool = False) -> None:
    docs = repo / "docs"
    docs.mkdir(exist_ok=True)
    marker = docs / ".codex_parallel_v2_installed"

    if not marker.exists():
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_root = docs / "archive" / f"legacy_{ts}"
        archive_root.mkdir(parents=True, exist_ok=True)
        for child in list(docs.iterdir()):
            if child.name == "archive":
                continue
            if child.name == ".codex_parallel_v2_installed":
                continue
            shutil.move(str(child), str(archive_root / child.name))
        print(f"[setup] archived old docs to {archive_root}")
    else:
        print("[setup] docs already initialized; updating active specs only")

    # Copy docs/README and active specs always.
    for rel in ["README.md", "specs"]:
        src = package_docs / rel
        dst = docs / rel
        if src.is_dir():
            copytree_merge(src, dst, overwrite=True)
        elif src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # dev-run templates: do not overwrite status unless reset_progress.
    src_dev = package_docs / "dev-run"
    dst_dev = docs / "dev-run"
    for item in src_dev.rglob("*"):
        rel = item.relative_to(src_dev)
        target = dst_dev / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            if reset_progress or not target.exists():
                shutil.copy2(item, target)

    marker.write_text(_dt.datetime.now().isoformat(), encoding="utf-8")

def append_agents(repo: Path, addon: Path) -> None:
    agents = repo / "AGENTS.md"
    legacy = repo / "Agents.md"
    if not agents.exists() and legacy.exists():
        shutil.copy2(legacy, agents)
        print("[setup] copied Agents.md to AGENTS.md")
    elif not agents.exists():
        agents.write_text("# AGENTS.md\n\n", encoding="utf-8")
        print("[setup] created AGENTS.md")

    addon_text = addon.read_text(encoding="utf-8")
    cur = agents.read_text(encoding="utf-8", errors="ignore")
    if MARKER not in cur:
        with agents.open("a", encoding="utf-8") as f:
            f.write("\n\n" + addon_text.strip() + "\n")
        print("[setup] appended parallel addon to AGENTS.md")
    else:
        print("[setup] AGENTS.md already contains parallel addon")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--reset-progress", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    package = Path(__file__).resolve().parents[2]

    print(f"[setup] repo={repo}")
    print(f"[setup] package={package}")

    archive_docs(repo, package / "docs", reset_progress=args.reset_progress)

    tools_dst = repo / "tools" / "codex"
    copytree_merge(package / "tools" / "codex", tools_dst, overwrite=True)
    append_agents(repo, package / "AGENTS_parallel_addon.md")

    print("[setup] OK")
    print("Next: send 01_发给Codex的一次性全自动启动指令.md to Codex.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
