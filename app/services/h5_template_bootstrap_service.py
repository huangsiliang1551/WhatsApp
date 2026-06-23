from __future__ import annotations

from sqlalchemy.orm import Session

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.db.models import H5Template


DEFAULT_TEMPLATE_PREVIEW_URL = "/h5/login?site_key=mall-cn"


class H5TemplateBootstrapService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_default_template(self) -> bool:
        template = self._session.get(H5Template, DEFAULT_H5_TEMPLATE_ID)
        if template is not None:
            changed = False
            if template.preview_url != DEFAULT_TEMPLATE_PREVIEW_URL:
                template.preview_url = DEFAULT_TEMPLATE_PREVIEW_URL
                changed = True
            if template.preview_path != DEFAULT_TEMPLATE_PREVIEW_URL:
                template.preview_path = DEFAULT_TEMPLATE_PREVIEW_URL
                changed = True
            if template.status != "ready":
                template.status = "ready"
                changed = True
            if template.publish_status != "published":
                template.publish_status = "published"
                changed = True
            if template.template_data != self._template_data():
                template.template_data = self._template_data()
                changed = True
            if changed:
                self._session.commit()
            return False

        self._session.add(
            H5Template(
                id=DEFAULT_H5_TEMPLATE_ID,
                name="固定默认 H5",
                description="系统固定使用的默认 H5 运行时模板记录。",
                preview_url=DEFAULT_TEMPLATE_PREVIEW_URL,
                preview_path=DEFAULT_TEMPLATE_PREVIEW_URL,
                template_data=self._template_data(),
                created_by="system",
                status="ready",
                publish_status="published",
            )
        )
        self._session.commit()
        return True

    @staticmethod
    def _template_data() -> dict[str, str]:
        return {
            "mode": "single_template",
            "entry": "/h5/login",
            "site_key_param": "site_key",
            "default_site_key": "mall-cn",
        }
