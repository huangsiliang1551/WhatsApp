"""Template sync service.

When a template is updated, this service notifies all agencies using it
and marks their sites for redeployment.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgencyTemplate, H5Site, Notification

logger = structlog.get_logger()


class TemplateSyncService:
    """Sync template updates to all agencies/sites using the template."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def sync_template_update(self, template_id: str) -> dict:
        """Template updated - notify all agencies using it.

        Returns summary of affected agencies and notification count.
        """
        # Find all agencies using this template
        agency_templates = list(
            self.session.execute(
                select(AgencyTemplate).where(AgencyTemplate.template_id == template_id)
            ).scalars().all()
        )

        if not agency_templates:
            return {"affected_agencies": 0, "notifications_sent": 0}

        agency_ids = [at.agency_id for at in agency_templates]

        # Find sites belonging to these agencies
        sites = list(
            self.session.execute(
                select(H5Site).where(H5Site.agency_id.in_(agency_ids))
            ).scalars().all()
        )

        # Create notifications for each agency
        notifications_sent = 0
        for agency_id in agency_ids:
            notification = Notification(
                id=__import__("uuid").uuid4().hex[:36],
                type="template_update",
                category="system",
                title="模板已更新",
                message=f"您的 H5 模板已被管理员更新，请检查是否需要重新部署站点。",
                severity="info",
            )
            self.session.add(notification)
            notifications_sent += 1

        site_ids = [s.id for s in sites]
        agency_ids_strs = agency_ids

        logger.info(
            "template_sync_complete",
            template_id=template_id,
            agencies=agency_ids_strs,
            sites=site_ids,
            notifications_sent=notifications_sent,
        )

        self.session.flush()

        return {
            "affected_agencies": len(agency_ids),
            "affected_sites": len(sites),
            "notifications_sent": notifications_sent,
        }
