"""归属 / AI 接待 / 入口链接 旧数据 backfill 脚本（spec 15.2-15.4）。

执行：
    python scripts/backfill_attribution.py --account-id <id> [--site-id <id>] [--apply]

默认 dry-run：不写库，只输出报告。
--apply 才会 commit。
幂等：重复执行不会重复创建 current assignment。
不伪造历史：无法确定时写 unattributed，snapshot 标记 migration_default + confidence=low。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from sqlalchemy import and_, or_, select

from app.db.models import (
    AppUser,
    H5Site,
    MemberProfile,
    utc_now,
)
from app.db.ownership_models import (
    AIAgent,
    EntryLink,
    MemberAIAssignment,
    MemberOwnerAssignment,
    OwnershipAuditEvent,
)
from app.db.session import get_sessionmaker


def _backfill_member_owner(
    session,
    *,
    member: MemberProfile,
    site: H5Site | None,
    actor_id: str | None,
    apply: bool,
) -> str:
    """返回本次 backfill 结果标签。"""
    if member.current_owner_staff_user_id:
        return "skipped_has_owner"
    invite_code_str = member.user.registration_invite_code if member.user else None
    if invite_code_str:
        # 看能否找到邀请人
        referrer = session.scalar(
            select(AppUser).where(AppUser.registration_invite_code == invite_code_str)
        )
        if referrer is not None:
            referrer_member = session.scalar(
                select(MemberProfile).where(
                    MemberProfile.account_id == member.account_id,
                    MemberProfile.user_id == referrer.id,
                )
            )
            if referrer_member and referrer_member.current_owner_staff_user_id:
                if apply:
                    _create_owner_assignment(
                        session,
                        account_id=member.account_id,
                        site_id=site.id if site else None,
                        user_id=member.user_id,
                        member_profile_id=member.id,
                        owner_staff_user_id=referrer_member.current_owner_staff_user_id,
                        source_type="member_invite_inherited",
                        source_invite_code=invite_code_str,
                        source_referrer_user_id=referrer.id,
                        actor_id=actor_id,
                    )
                    member.current_owner_agency_id = referrer_member.current_owner_agency_id
                    member.current_owner_staff_user_id = referrer_member.current_owner_staff_user_id
                    member.current_owner_agency_member_id = referrer_member.current_owner_agency_member_id
                    member.current_owner_assignment_id = None  # 写完再刷
                    member.owner_assigned_at = utc_now()
                    member.attribution_status = "owned"
                return "inherited_from_inviter"
    # 回退到站点默认
    if site and site.default_staff_entry_link_id:
        link = session.get(EntryLink, site.default_staff_entry_link_id)
        if link is not None and link.target_staff_user_id:
            if apply:
                _create_owner_assignment(
                    session,
                    account_id=member.account_id,
                    site_id=site.id,
                    user_id=member.user_id,
                    member_profile_id=member.id,
                    owner_staff_user_id=link.target_staff_user_id,
                    source_type="site_default_staff",
                    source_entry_link_id=link.id,
                    actor_id=actor_id,
                )
                member.current_owner_staff_user_id = link.target_staff_user_id
                member.owner_assigned_at = utc_now()
                member.attribution_status = "owned"
            return "inherited_from_site_default"
    if apply:
        member.attribution_status = member.attribution_status or "unattributed"
    return "unattributed"


def _backfill_member_ai(
    session,
    *,
    member: MemberProfile,
    site: H5Site | None,
    actor_id: str | None,
    apply: bool,
) -> str:
    if member.current_ai_agent_id:
        return "skipped_has_ai"
    if site and site.default_ai_agent_id:
        agent = session.get(AIAgent, site.default_ai_agent_id)
        if agent is not None and agent.status == "active":
            if apply:
                _create_ai_assignment(
                    session,
                    account_id=member.account_id,
                    site_id=site.id,
                    user_id=member.user_id,
                    member_profile_id=member.id,
                    ai_agent_id=agent.id,
                    source_type="site_default_ai",
                    source_entry_link_id=site.default_ai_entry_link_id,
                    actor_id=actor_id,
                )
                member.current_ai_agent_id = agent.id
                member.ai_assigned_at = utc_now()
            return "inherited_site_default_ai"
    return "no_ai"


def _create_owner_assignment(
    session,
    *,
    account_id: str,
    site_id: str | None,
    user_id: str,
    member_profile_id: str,
    owner_staff_user_id: str,
    source_type: str,
    source_entry_link_id: str | None = None,
    source_invite_code: str | None = None,
    source_referrer_user_id: str | None = None,
    actor_id: str | None = None,
) -> None:
    # 先把同 user 的 current 全部关掉
    existing = session.scalars(
        select(MemberOwnerAssignment).where(
            MemberOwnerAssignment.account_id == account_id,
            MemberOwnerAssignment.user_id == user_id,
            MemberOwnerAssignment.is_current.is_(True),
        )
    ).all()
    for item in existing:
        item.is_current = False
        item.ended_at = utc_now()
        session.add(item)
    new_item = MemberOwnerAssignment(
        account_id=account_id,
        site_id=site_id,
        user_id=user_id,
        member_profile_id=member_profile_id,
        owner_staff_user_id=owner_staff_user_id,
        source_type=source_type,
        source_entry_link_id=source_entry_link_id,
        source_invite_code=source_invite_code,
        source_referrer_user_id=source_referrer_user_id,
        is_current=True,
        changed_by_actor_id=actor_id,
        reason="backfill_attribution",
    )
    session.add(new_item)
    session.flush()
    member = session.get(MemberProfile, member_profile_id)
    if member is not None:
        member.current_owner_assignment_id = new_item.id


def _create_ai_assignment(
    session,
    *,
    account_id: str,
    site_id: str | None,
    user_id: str,
    member_profile_id: str,
    ai_agent_id: str,
    source_type: str,
    source_entry_link_id: str | None = None,
    actor_id: str | None = None,
) -> None:
    existing = session.scalars(
        select(MemberAIAssignment).where(
            MemberAIAssignment.account_id == account_id,
            MemberAIAssignment.user_id == user_id,
            MemberAIAssignment.is_current.is_(True),
        )
    ).all()
    for item in existing:
        item.is_current = False
        item.ended_at = utc_now()
        session.add(item)
    new_item = MemberAIAssignment(
        account_id=account_id,
        site_id=site_id,
        user_id=user_id,
        member_profile_id=member_profile_id,
        ai_agent_id=ai_agent_id,
        source_type=source_type,
        source_entry_link_id=source_entry_link_id,
        is_current=True,
        changed_by_actor_id=actor_id,
        reason="backfill_attribution",
    )
    session.add(new_item)
    session.flush()
    member = session.get(MemberProfile, member_profile_id)
    if member is not None:
        member.current_ai_assignment_id = new_item.id


def main() -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Backfill attribution / AI ownership")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--site-id", default=None)
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run")
    parser.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args()

    session_factory = get_sessionmaker()
    session = session_factory()
    try:
        stmt = select(MemberProfile).where(MemberProfile.account_id == args.account_id)
        if args.site_id:
            stmt = stmt.join(AppUser, AppUser.id == MemberProfile.user_id).where(
                AppUser.registration_site_id == args.site_id
            )
        stmt = stmt.limit(args.limit)
        members = list(session.scalars(stmt).all())

        report: dict[str, Any] = {
            "scanned": 0,
            "owner_inherited_from_inviter": 0,
            "owner_inherited_from_site_default": 0,
            "owner_skipped_has_owner": 0,
            "owner_unattributed": 0,
            "ai_inherited_site_default": 0,
            "ai_skipped_has_ai": 0,
            "ai_no_ai": 0,
            "errors": [],
            "dry_run": not args.apply,
        }

        for member in members:
            try:
                site = None
                if member.user and member.user.registration_site_id:
                    site = session.get(H5Site, member.user.registration_site_id)
                report["scanned"] += 1
                owner_label = _backfill_member_owner(
                    session,
                    member=member,
                    site=site,
                    actor_id="backfill_script",
                    apply=args.apply,
                )
                ai_label = _backfill_member_ai(
                    session,
                    member=member,
                    site=site,
                    actor_id="backfill_script",
                    apply=args.apply,
                )
                report[f"owner_{owner_label}"] = report.get(f"owner_{owner_label}", 0) + 1
                report[f"ai_{ai_label}"] = report.get(f"ai_{ai_label}", 0) + 1
            except Exception as exc:  # noqa: BLE001
                report["errors"].append({"member_profile_id": member.id, "error": str(exc)})

        if args.apply:
            # 写一个 audit 事件
            session.add(
                OwnershipAuditEvent(
                    account_id=args.account_id,
                    action="backfill_attribution_completed",
                    target_type="backfill_run",
                    target_id=args.site_id or args.account_id,
                    actor_type="system",
                    actor_id="backfill_script",
                    payload={
                        "site_id": args.site_id,
                        "scanned": report["scanned"],
                        "errors": len(report["errors"]),
                    },
                )
            )
            session.commit()
        else:
            session.rollback()
        return report
    finally:
        session.close()


if __name__ == "__main__":
    report = main()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0)
