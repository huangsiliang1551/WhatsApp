from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from datetime import datetime, timezone

def human_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total

def fmt(n: int) -> str:
    for unit in ["B","KB","MB","GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"

def remove(path: Path, delete: bool):
    size = human_size(path)
    if delete:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()
        print(f"DELETED {path} ({fmt(size)})")
    else:
        print(f"DRY-RUN delete {path} ({fmt(size)})")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--delete", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-latest", type=int, default=3)
    ap.add_argument("--include-codex-run-logs", action="store_true")
    ap.add_argument("--keep-progress", action="store_true", default=True)
    ap.add_argument("--include-build-cache", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    delete = args.delete and not args.dry_run
    print(f"[cleanup] repo={repo}")
    print(f"[cleanup] mode={'DELETE' if delete else 'DRY-RUN'}")

    archive = repo / "docs" / "archive"
    if archive.exists():
        legacy_dirs = sorted([p for p in archive.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        for idx, p in enumerate(legacy_dirs):
            if idx >= args.keep_latest:
                remove(p, delete)
            else:
                print(f"KEEP {p}")

    if args.include_codex_run_logs:
        codex_run = repo / ".codex-run"
        if codex_run.exists():
            for p in codex_run.iterdir():
                if p.name == "progress" and args.keep_progress:
                    print(f"KEEP {p}")
                    continue
                if p.is_file() and p.suffix in {".log", ".err", ".out"}:
                    remove(p, delete)

    if args.include_build_cache:
        candidates = [
            repo / "frontend" / "dist",
            repo / "frontend" / ".vite",
            repo / ".pytest_cache",
        ]
        candidates += list(repo.glob(".tmp_pytest*"))
        for p in candidates:
            if p.exists():
                remove(p, delete)

    print("[cleanup] done")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
