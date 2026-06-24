"""会员人力归属 + 会员 AI 归属服务（spec 6.5, 6.6）。

同一 account_id + user_id 只能有一个 is_current=true 的人力/AI 归属。
新建当前归属前必须结束旧归属。划转只影响未来，不改历史 snapshot。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import H5Site, MemberProfile, utc_now
from app.db.ownership_models import (
    AIAgent,
    MemberAIAssignment,
    MemberOwnerAssignment,
    MemberOwnerTransferBatch,
    MemberOwnerTransferItem,
    OwnershipAuditEvent,
)
from app.services.ai_agent_service import AIAgentService


class AttributionError(ValueError):
    """归属解析失败（如 AI 链接无 fallback staff、无 entry_code 且站点要求）。"""


class TransferUnauthorizedError(PermissionError):
    """普通客服越权划转 / 跨代理商划转。"""


class MemberOwnershipService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── 注册解析 ──
    def resolve_registration_entry(
        self,
        site: H5Site,
        entry_code_or_invite_code: str | None,
    ) -> tuple[Any | None, str]:
        """解析注册入口。

        返回 (entry_link_or_None, resolved_code)。优先 EntryLink，
        兼容旧 InviteCode（通过 allow_invite_code_alias）。
        站点 registration_entry_required=true 且无 code：抛 AttributionError。
        """
        from app.db.models import InviteCode
        from app.services.entry_link_service import (
            EntryLinkNotFoundError,
            EntryLinkService,
        )

        code = (entry_code_or_invite_code or "").strip()
        if not code:
            if site.registration_entry_required:
                raise AttributionError(
                    "registration_entry_required: 必须通过客服或 AI 专属链接注册。"
                )
            return None, ""

        svc = EntryLinkService(self._session)
        try:
            link = svc.resolve_code(code, site_id=site.id)
            return link, code
        except EntryLinkNotFoundError:
            pass
        # 兼容旧 InviteCode
        if site.allow_invite_code_alias:
            invite = self._session.scalar(select(InviteCode).where(InviteCode.code == code))
            if invite is not None:
                return None, code
        if site.registration_entry_required:
            raise AttributionError(f"无效的注册入口码 '{code}'。")
        return None, code

    def assign_new_member_human_owner(
        self,
        *,
        account_id: str,
        user_id: str,
        member_profile_id: str,
        entry_link: Any | None,
        invite_code: str | None,
        referrer_user_id: str | None,
        site: H5Site,
        actor_id: str | None = None,
    ) -> MemberOwnerAssignment:
        """注册时创建会员人力归属。

        - EntryLink target staff：归属该 staff。
        - EntryLink target ai_agent：人力归属为 AI 的 fallback_staff / owning_staff；
          无人力兜底则拒绝正式注册。
        - 会员邀请：继承邀请人当前人力归属。
        """
        owner_staff: str | None = None
        owner_agency_member_id: str | None = None
        source_type: str
        source_entry_link_id: str | None = None

        if entry_link is not None:
            source_entry_link_id = entry_link.id
            if entry_link.target_type == "staff" and entry_link.target_staff_user_id:
                owner_staff = entry_link.target_staff_user_id
                owner_agency_member_id = entry_link.target_agency_member_id
                source_type = "staff_entry_link"
            elif entry_link.target_type == "ai_agent":
                agent = self._session.get(AIAgent, entry_link.target_ai_agent_id)
                owner_staff = (agent.fallback_staff_user_id or agent.owning_staff_user_id) if agent else None
                if not owner_staff:
                    raise AttributionError(
                        "AI 链接未配置兜底客服，无法完成正式注册。"
                    )
                source_type = "ai_entry_link_fallback_staff"
            elif entry_link.target_type == "staff_ai" and entry_link.target_staff_user_id:
                owner_staff = entry_link.target_staff_user_id
                owner_agency_member_id = entry_link.target_agency_member_id
                source_type = "staff_entry_link"
            else:
                raise AttributionError("EntryLink 缺少有效 staff 目标。")
        elif referrer_user_id is not None and site.member_invite_inherits_human_owner:
            referrer_assignment = self.get_current_human_assignment(
                user_id=referrer_user_id, account_id=account_id
            )
            if referrer_assignment is None:
                raise AttributionError(
                    "邀请人当前无人力归属，无法继承；请联系客服处理。"
                )
            owner_staff = referrer_assignment.owner_staff_user_id
            owner_agency_member_id = referrer_assignment.owner_agency_member_id
            source_type = "member_invite_inherited"
        else:
            raise AttributionError("无法解析人力归属：缺少 entry_link 且无邀请继承。")

        assignment = self._end_old_and_create_current(
            account_id=account_id,
            user_id=user_id,
            member_profile_id=member_profile_id,
            owner_staff_user_id=owner_staff,
            owner_agency_member_id=owner_agency_member_id,
            source_type=source_type,
            source_entry_link_id=source_entry_link_id,
            source_invite_code=invite_code,
            source_referrer_user_id=referrer_user_id,
            site_id=site.id,
            agency_id=site.agency_id,
            actor_id=actor_id,
        )
        # 同步 MemberProfile.current_*
        self._sync_member_current_owner(
            member_profile_id=member_profile_id,
            assignment=assignment,
            entry_link_id=source_entry_link_id,
            channel="h5",
            source_type=source_type,
        )
        return assignment

    def get_current_human_assignment(
        self, *, user_id: str, account_id: str
    ) -> MemberOwnerAssignment | None:
        return self._session.scalar(
            select(MemberOwnerAssignment).where(
                MemberOwnerAssignment.account_id == account_id,
                MemberOwnerAssignment.user_id == user_id,
                MemberOwnerAssignment.is_current.is_(True),
            )
        )

    def transfer_members(
        self,
        *,
        account_id: str,
        from_staff_user_id: str,
        to_staff_user_id: str,
        member_profile_ids: list[str],
        actor_id: str,
        agency_id: str | None = None,
        site_id: str | None = None,
        transfer_all_current_owned_members: bool = False,
        dry_run: bool = False,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """人力归属划转。只能划转本代理商/本账号范围内会员。dry_run 不写库。"""
        if not member_profile_ids and not transfer_all_current_owned_members:
            raise TransferUnauthorizedError("未指定划转会员。")

        stmt = select(MemberOwnerAssignment).where(
            MemberOwnerAssignment.account_id == account_id,
            MemberOwnerAssignment.owner_staff_user_id == from_staff_user_id,
            MemberOwnerAssignment.is_current.is_(True),
        )
        if member_profile_ids:
            stmt = stmt.where(MemberOwnerAssignment.member_profile_id.in_(member_profile_ids))
        current_assignments = list(self._session.scalars(stmt).all())

        if dry_run:
            return {
                "dry_run": True,
                "affected_count": len(current_assignments),
                "member_profile_ids": [a.member_profile_id for a in current_assignments],
            }

        batch = MemberOwnerTransferBatch(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            from_staff_user_id=from_staff_user_id,
            to_staff_user_id=to_staff_user_id,
            status="completed",
            total_items=len(current_assignments),
            dry_run=False,
            reason=reason,
            changed_by_actor_id=actor_id,
        )
        self._session.add(batch)
        self._session.flush()

        transferred: list[MemberOwnerTransferItem] = []
        for old in current_assignments:
            old.is_current = False
            old.ended_at = utc_now()
            self._session.add(old)
            new = MemberOwnerAssignment(
                account_id=account_id,
                agency_id=agency_id,
                site_id=site_id,
                user_id=old.user_id,
                member_profile_id=old.member_profile_id,
                owner_staff_user_id=to_staff_user_id,
                owner_agency_member_id=old.owner_agency_member_id,
                source_type="manual_transfer",
                source_entry_link_id=old.source_entry_link_id,
                source_invite_code=old.source_invite_code,
                source_referrer_user_id=old.source_referrer_user_id,
                is_current=True,
                changed_by_actor_id=actor_id,
                transfer_batch_id=batch.id,
                reason=reason,
            )
            self._session.add(new)
            self._session.flush()
            self._sync_member_current_owner(
                member_profile_id=old.member_profile_id,
                assignment=new,
                entry_link_id=None,
                channel=None,
                source_type="manual_transfer",
            )
            transferred.append(
                MemberOwnerTransferItem(
                    batch_id=batch.id,
                    member_profile_id=old.member_profile_id,
                    user_id=old.user_id,
                    from_staff_user_id=from_staff_user_id,
                    to_staff_user_id=to_staff_user_id,
                    status="transferred",
                )
            )
        for item in transferred:
            self._session.add(item)
        self._session.add(
            OwnershipAuditEvent(
                account_id=account_id,
                agency_id=agency_id,
                site_id=site_id,
                action="member_owner_transferred",
                target_type="transfer_batch",
                target_id=batch.id,
                actor_type="staff",
                actor_id=actor_id,
                payload={
                    "from_staff_user_id": from_staff_user_id,
                    "to_staff_user_id": to_staff_user_id,
                    "affected_count": len(current_assignments),
                    "reason": reason,
                },
            )
        )
        return {
            "batch_id": batch.id,
            "affected_count": len(current_assignments),
            "dry_run": False,
        }

    # ── 内部 ──
    def _end_old_and_create_current(
        self,
        *,
        account_id: str,
        user_id: str,
        member_profile_id: str,
        owner_staff_user_id: str,
        owner_agency_member_id: str | None,
        source_type: str,
        source_entry_link_id: str | None,
        source_invite_code: str | None,
        source_referrer_user_id: str | None,
        site_id: str | None,
        agency_id: str | None,
        actor_id: str | None,
    ) -> MemberOwnerAssignment:
        # 结束旧 current
        self._session.execute(
            update(MemberOwnerAssignment)
            .where(
                MemberOwnerAssignment.account_id == account_id,
                MemberOwnerAssignment.user_id == user_id,
                MemberOwnerAssignment.is_current.is_(True),
            )
            .values(is_current=False, ended_at=utc_now())
        )
        assignment = MemberOwnerAssignment(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            user_id=user_id,
            member_profile_id=member_profile_id,
            owner_staff_user_id=owner_staff_user_id,
            owner_agency_member_id=owner_agency_member_id,
            source_type=source_type,
            source_entry_link_id=source_entry_link_id,
            source_invite_code=source_invite_code,
            source_referrer_user_id=source_referrer_user_id,
            is_current=True,
            changed_by_actor_id=actor_id,
        )
        self._session.add(assignment)
        self._session.flush()
        return assignment

    def _sync_member_current_owner(
        self,
        *,
        member_profile_id: str,
        assignment: MemberOwnerAssignment,
        entry_link_id: str | None,
        channel: str | None,
        source_type: str,
    ) -> None:
        member = self._session.get(MemberProfile, member_profile_id)
        if member is None:
            return
        member.current_owner_agency_id = assignment.agency_id
        member.current_owner_staff_user_id = assignment.owner_staff_user_id
        member.current_owner_agency_member_id = assignment.owner_agency_member_id
        member.current_owner_assignment_id = assignment.id
        member.owner_assigned_at = assignment.assigned_at
        if entry_link_id:
            member.registration_entry_link_id = entry_link_id
        if channel:
            member.registration_channel = channel
        member.registration_source_type = source_type
        member.registration_staff_user_id = assignment.owner_staff_user_id
        member.attribution_status = "owned"
        self._session.add(member)


class MemberAIOwnershipService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def assign_new_member_ai(
        self,
        *,
        account_id: str,
        user_id: str,
        member_profile_id: str,
        entry_link: Any | None,
        referrer_user_id: str | None,
        site: H5Site,
        actor_id: str | None = None,
    ) -> MemberAIAssignment | None:
        """注册时创建会员 AI 归属。

        - EntryLink target ai_agent：AI 归属该 AI。
        - EntryLink target staff 且站点有 default_ai_agent：AI 归属站点默认 AI。
        - 会员邀请：默认继承邀请人当前 AI；站点关闭继承则用站点默认 AI。
        """
        ai_agent_id: str | None = None
        source_type: str
        source_entry_link_id: str | None = None

        if entry_link is not None and entry_link.target_ai_agent_id:
            ai_agent_id = entry_link.target_ai_agent_id
            source_type = "ai_entry_link"
            source_entry_link_id = entry_link.id
        elif entry_link is not None and entry_link.target_type in ("staff", "staff_ai"):
            if site.default_ai_agent_id:
                ai_agent_id = site.default_ai_agent_id
                source_type = "staff_link_default_ai"
            else:
                source_type = "staff_link_default_ai"
            source_entry_link_id = entry_link.id
        elif referrer_user_id is not None and site.member_invite_inherits_ai:
            ref_ai = self.get_current_ai_assignment(user_id=referrer_user_id, account_id=account_id)
            if ref_ai is not None:
                ai_agent_id = ref_ai.ai_agent_id
                source_type = "member_invite_inherited_ai"
            elif site.default_ai_agent_id:
                ai_agent_id = site.default_ai_agent_id
                source_type = "staff_link_default_ai"
            else:
                return None
        elif site.default_ai_agent_id:
            ai_agent_id = site.default_ai_agent_id
            source_type = "staff_link_default_ai"
        else:
            return None

        if ai_agent_id is None:
            return None

        assignment = self._end_old_and_create_current(
            account_id=account_id,
            user_id=user_id,
            member_profile_id=member_profile_id,
            ai_agent_id=ai_agent_id,
            source_type=source_type,
            source_entry_link_id=source_entry_link_id,
            site_id=site.id,
            agency_id=site.agency_id,
            actor_id=actor_id,
        )
        member = self._session.get(MemberProfile, member_profile_id)
        if member is not None:
            member.current_ai_agent_id = ai_agent_id
            member.current_ai_assignment_id = assignment.id
            member.ai_assigned_at = assignment.assigned_at
            if entry_link is not None:
                member.registration_ai_agent_id = ai_agent_id
            self._session.add(member)
        return assignment

    def get_current_ai_assignment(
        self, *, user_id: str, account_id: str
    ) -> MemberAIAssignment | None:
        return self._session.scalar(
            select(MemberAIAssignment).where(
                MemberAIAssignment.account_id == account_id,
                MemberAIAssignment.user_id == user_id,
                MemberAIAssignment.is_current.is_(True),
            )
        )

    def inherit_ai_from_referrer(self, referrer_user_id: str, *, account_id: str) -> str | None:
        ref_ai = self.get_current_ai_assignment(user_id=referrer_user_id, account_id=account_id)
        return ref_ai.ai_agent_id if ref_ai else None

    def auto_reassign_unavailable_ai(
        self,
        *,
        from_ai_agent_id: str,
        to_ai_agent_id: str,
        account_id: str,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> int:
        """AI 永久迁移：把所有 current AI=from 的会员迁到 to。不改历史。"""
        current = list(
            self._session.scalars(
                select(MemberAIAssignment).where(
                    MemberAIAssignment.ai_agent_id == from_ai_agent_id,
                    MemberAIAssignment.is_current.is_(True),
                )
            ).all()
        )
        for old in current:
            old.is_current = False
            old.ended_at = utc_now()
            self._session.add(old)
            new = MemberAIAssignment(
                account_id=old.account_id,
                agency_id=old.agency_id,
                site_id=old.site_id,
                user_id=old.user_id,
                member_profile_id=old.member_profile_id,
                ai_agent_id=to_ai_agent_id,
                source_type="auto_failover_reassign",
                source_entry_link_id=old.source_entry_link_id,
                is_current=True,
                changed_by_actor_id=actor_id,
                reason=reason or "auto_reassign_unavailable_ai",
            )
            self._session.add(new)
            self._session.flush()
            member = self._session.get(MemberProfile, old.member_profile_id)
            if member is not None:
                member.current_ai_agent_id = to_ai_agent_id
                member.current_ai_assignment_id = new.id
                self._session.add(member)
        return len(current)

    def transfer_member_ai(
        self,
        *,
        account_id: str,
        from_ai_agent_id: str,
        to_ai_agent_id: str,
        member_profile_ids: list[str],
        actor_id: str,
        include_open_conversations: bool = True,
        dry_run: bool = False,
        reason: str | None = None,
    ) -> dict[str, Any]:
        from app.db.ownership_models import (
            MemberAITransferBatch,
            MemberAITransferItem,
        )

        if dry_run:
            stmt = select(MemberAIAssignment).where(
                MemberAIAssignment.account_id == account_id,
                MemberAIAssignment.ai_agent_id == from_ai_agent_id,
                MemberAIAssignment.is_current.is_(True),
            )
            if member_profile_ids:
                stmt = stmt.where(MemberAIAssignment.member_profile_id.in_(member_profile_ids))
            count = len(list(self._session.scalars(stmt).all()))
            return {"dry_run": True, "affected_count": count}

        batch = MemberAITransferBatch(
            account_id=account_id,
            from_ai_agent_id=from_ai_agent_id,
            to_ai_agent_id=to_ai_agent_id,
            status="completed",
            total_items=0,
            include_open_conversations=include_open_conversations,
            dry_run=False,
            reason=reason,
            changed_by_actor_id=actor_id,
        )
        self._session.add(batch)
        self._session.flush()
        affected = self.auto_reassign_unavailable_ai(
            from_ai_agent_id=from_ai_agent_id,
            to_ai_agent_id=to_ai_agent_id,
            account_id=account_id,
            actor_id=actor_id,
            reason=reason,
        )
        batch.total_items = affected
        self._session.add(batch)
        self._session.add(
            OwnershipAuditEvent(
                account_id=account_id,
                action="member_ai_transferred",
                target_type="transfer_batch",
                target_id=batch.id,
                actor_type="staff",
                actor_id=actor_id,
                payload={"from_ai_agent_id": from_ai_agent_id, "to_ai_agent_id": to_ai_agent_id, "affected_count": affected},
            )
        )
        return {"batch_id": batch.id, "affected_count": affected, "dry_run": False}

    def _end_old_and_create_current(
        self,
        *,
        account_id: str,
        user_id: str,
        member_profile_id: str,
        ai_agent_id: str,
        source_type: str,
        source_entry_link_id: str | None,
        site_id: str | None,
        agency_id: str | None,
        actor_id: str | None,
    ) -> MemberAIAssignment:
        self._session.execute(
            update(MemberAIAssignment)
            .where(
                MemberAIAssignment.account_id == account_id,
                MemberAIAssignment.user_id == user_id,
                MemberAIAssignment.is_current.is_(True),
            )
            .values(is_current=False, ended_at=utc_now())
        )
        assignment = MemberAIAssignment(
            account_id=account_id,
            agency_id=agency_id,
            site_id=site_id,
            user_id=user_id,
            member_profile_id=member_profile_id,
            ai_agent_id=ai_agent_id,
            source_type=source_type,
            source_entry_link_id=source_entry_link_id,
            is_current=True,
            changed_by_actor_id=actor_id,
        )
        self._session.add(assignment)
        self._session.flush()
        return assignment
