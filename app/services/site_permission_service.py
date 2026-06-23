from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SitePermission

ROLE_HIERARCHY: dict[str, int] = {
    "admin": 4,
    "editor": 3,
    "analyst": 2,
    "support": 1,
}


class SitePermissionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_permissions(self, user_id: str) -> list[SitePermission]:
        """获取用户的所有站点权限"""
        return list(
            self._session.scalars(
                select(SitePermission).where(SitePermission.user_id == user_id)
            ).all()
        )

    def get_site_permissions(self, site_id: str) -> list[SitePermission]:
        """获取某个站点的所有权限分配"""
        return list(
            self._session.scalars(
                select(SitePermission).where(SitePermission.site_id == site_id)
            ).all()
        )

    def grant_permission(self, user_id: str, site_id: str, role: str) -> SitePermission:
        """授予用户站点权限"""
        perm = SitePermission(
            id=str(uuid4()),
            user_id=user_id,
            site_id=site_id,
            role=role,
        )
        self._session.add(perm)
        self._session.commit()
        return perm

    def revoke_permission(self, permission_id: str) -> None:
        """撤销权限"""
        perm = self._session.get(SitePermission, permission_id)
        if not perm:
            raise LookupError(f"Permission '{permission_id}' not found.")
        self._session.delete(perm)
        self._session.commit()

    def update_role(self, permission_id: str, role: str) -> SitePermission:
        """更新角色"""
        perm = self._session.get(SitePermission, permission_id)
        if not perm:
            raise LookupError(f"Permission '{permission_id}' not found.")
        perm.role = role
        self._session.commit()
        return perm

    def check_permission(self, user_id: str, site_id: str, required_role: str) -> bool:
        """检查用户是否有指定站点的访问权限（角色层级）"""
        perm = self._session.scalar(
            select(SitePermission).where(
                SitePermission.user_id == user_id,
                SitePermission.site_id == site_id,
            )
        )
        if not perm:
            return False
        user_level = ROLE_HIERARCHY.get(perm.role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level
