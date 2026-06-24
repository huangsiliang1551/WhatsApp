"""归属快照是否进入 customer summary 的回归测试（spec 5.7 + P1-02）。

不走 TestClient，直接调用 service，避免依赖 PG。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from app.db.models import AppUser, MemberProfile
from app.services.customer_summary_service import CustomerSummaryService


class _StubSession:
    """最小 stub：只支持 execute() 拿到 scalar_one_or_none 或 scalars().all()。"""

    def __init__(self, rows: list[Any]):
        self._rows = list(rows)

    def execute(self, stmt):  # noqa: ANN001 - 简化
        # 简单队列：每次 execute 弹一个 row
        row = self._rows.pop(0) if self._rows else None
        return SimpleNamespace(
            scalar_one_or_none=lambda: row,
            scalars=lambda: SimpleNamespace(all_=lambda: [row] if row else []),
        )

    def scalar(self, stmt):  # noqa: ANN001
        # 用于 get_conversations/_get_member_profile 的最后一步
        if not self._rows:
            return None
        return self._rows.pop(0)


def _make_user(uid: str = "u-1", pub: str = "pub-1") -> AppUser:
    user = AppUser(
        id=uid,
        public_user_id=pub,
        account_id="acc-1",
        display_name="User 1",
        has_phone=True,
    )
    return user


def _make_member(uid: str = "u-1", owner: str | None = "staff-1", ai: str | None = "ai-1") -> MemberProfile:
    m = MemberProfile(
        id="mp-1",
        account_id="acc-1",
        user_id=uid,
        member_no="00000001",
        password_hash="x" * 64,
        password_salt="s" * 32,
        current_owner_staff_user_id=owner,
        current_ai_agent_id=ai,
        attribution_status="owned",
        registration_channel="staff_register",
    )
    return m


def test_get_member_profile_returns_owned_data() -> None:
    user = _make_user()
    member = _make_member()
    # _get_member_profile 调用 AppUser 查询 + MemberProfile 查询
    session = _StubSession([user, member])
    svc = CustomerSummaryService(session)  # type: ignore[arg-type]
    out = asyncio.run(svc._get_member_profile("u-1", "acc-1"))
    assert out["current_owner_staff_user_id"] == "staff-1"
    assert out["current_ai_agent_id"] == "ai-1"
    assert out["attribution_status"] == "owned"
    assert out["member_no"] == "00000001"


def test_get_member_profile_unattributed_returns_empty() -> None:
    user = _make_user()
    member = _make_member(owner=None, ai=None)
    member.attribution_status = "unattributed"
    session = _StubSession([user, member])
    svc = CustomerSummaryService(session)  # type: ignore[arg-type]
    out = asyncio.run(svc._get_member_profile("u-1", "acc-1"))
    assert out["current_owner_staff_user_id"] is None
    assert out["current_ai_agent_id"] is None
    assert out["attribution_status"] == "unattributed"


def test_get_member_profile_user_not_found() -> None:
    session = _StubSession([None, None])
    svc = CustomerSummaryService(session)  # type: ignore[arg-type]
    out = asyncio.run(svc._get_member_profile("u-ghost", "acc-1"))
    assert out == svc._empty_member_profile()
    assert out["attribution_status"] == "unattributed"
