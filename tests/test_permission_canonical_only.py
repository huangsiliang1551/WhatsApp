from __future__ import annotations

from pathlib import Path

from app.core.permission_defs import PERMISSION_REGISTRY


ROOTS = ("app/api", "app/core")
SUFFIXES = (".py", ".ts", ".tsx")

LEGACY_PERMISSION_CODES = {
    "runtime.read",
    "runtime.write",
    "sites.read",
    "sites.manage",
    "users.read",
    "users.manage",
    "tags.read",
    "tags.manage",
    "audience_rules.read",
    "audience_rules.manage",
    "tasks.read",
    "tasks.manage",
    "tasks.review",
    "tickets.read",
    "tickets.manage",
    "internal_messages.read",
    "internal_messages.manage",
    "ledger.read",
    "ledger.manage",
    "withdrawals.read",
    "withdrawals.manage",
    "risk.read",
    "risk.manage",
    "leaderboard.read",
    "settings.read",
    "settings.manage",
    "metrics.read",
    "metrics.manage",
    "queue.read",
    "queue.write",
    "ecommerce.read",
    "meta.read",
    "meta.manage",
    "media_library.read",
    "media_library.manage",
    "support_knowledge.read",
    "support_knowledge.write",
    "ai.global.manage",
    "ai.account.manage",
    "conversations.read",
    "conversations.manage",
    "templates.read",
    "templates.manage",
}

COMPATIBILITY_MARKERS = (
    "class Permission(",
    "_LEGACY_PERMISSION_EXPORTS",
    "class _PermissionCode(",
)


def _iter_source_files() -> list[Path]:
    files: list[Path] = []
    for root in ROOTS:
        for path in Path(root).rglob("*"):
            if path.suffix in SUFFIXES:
                files.append(path)
    return files


def test_permission_registry_does_not_expose_legacy_codes() -> None:
    remaining = sorted(LEGACY_PERMISSION_CODES & set(PERMISSION_REGISTRY))
    assert remaining == []


def test_runtime_sources_do_not_depend_on_legacy_codes_or_shims() -> None:
    offenders: list[str] = []

    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")

        for marker in COMPATIBILITY_MARKERS:
            if marker in text:
                offenders.append(f"{path}: {marker}")

        for code in sorted(LEGACY_PERMISSION_CODES):
            if f'"{code}"' in text or f"'{code}'" in text:
                offenders.append(f"{path}: {code}")

    assert offenders == []
