"""H5 Template management and selection API routes."""

from datetime import datetime, timezone
from http import HTTPStatus
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_permission
from app.core.auth import RequestActor
from app.db.models import AgencyTemplate, DeployHistory, H5Site, H5SiteConfig, H5Template
from app.services.template_package_service import TemplatePackageService

router = APIRouter(prefix="/api/h5-templates", tags=["h5-templates"])


class CreateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    template_data: dict | None = None


class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    template_data: dict | None = None


class SelectTemplateRequest(BaseModel):
    agency_id: str


def _template_preview_path(template: H5Template) -> str:
    return template.preview_path or template.preview_url or f"/templates/{template.id}/index.html"


def _require_super_admin(actor: RequestActor, operation: str) -> None:
    if actor.is_super_admin:
        return
    raise HTTPException(
        status_code=HTTPStatus.FORBIDDEN,
        detail=f"Only super admins can {operation}.",
    )


def _load_template_manifest(template_id: str, session: Session) -> dict | None:
    try:
        return TemplatePackageService(session).get_template_manifest(template_id)
    except HTTPException:
        return None


def _effective_site_template_id(
    site: H5Site,
    *,
    agency_template_map: dict[str, str],
) -> str | None:
    metadata = site.metadata_json if isinstance(site.metadata_json, dict) else {}
    template_id = metadata.get("template_id")
    if isinstance(template_id, str) and template_id:
        return template_id
    if site.agency_id:
        return agency_template_map.get(site.agency_id)
    return None


def _template_ref_counts(session: Session) -> dict[str, int]:
    agency_template_map = {
        agency_id: template_id
        for agency_id, template_id in session.execute(
            select(AgencyTemplate.agency_id, AgencyTemplate.template_id)
        ).all()
    }
    counts: dict[str, int] = {}
    for site in session.execute(select(H5Site)).scalars().all():
        template_id = _effective_site_template_id(site, agency_template_map=agency_template_map)
        if not template_id:
            continue
        counts[template_id] = counts.get(template_id, 0) + 1
    return counts


def _serialize_template(
    template: H5Template,
    *,
    session: Session,
    ref_count: int = 0,
    include_manifest: bool = False,
) -> dict[str, object]:
    preview_path = _template_preview_path(template)
    payload: dict[str, object] = {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "preview_url": preview_path,
        "preview_path": preview_path,
        "ref_count": ref_count,
        "status": template.status,
        "package_filename": template.package_filename,
        "package_size": template.package_size,
        "package_uploaded_at": template.package_uploaded_at.isoformat() if template.package_uploaded_at else None,
        "created_by": template.created_by,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "publish_status": template.publish_status,
        "published_at": template.published_at.isoformat() if template.published_at else None,
        "published_by": template.published_by,
    }
    if include_manifest:
        payload["manifest"] = _load_template_manifest(template.id, session)
    return payload


def _is_template_published(template: H5Template) -> bool:
    return template.publish_status == "published"


def _require_template_market_visibility(template: H5Template, actor: RequestActor) -> None:
    if actor.is_super_admin or _is_template_published(template):
        return
    raise HTTPException(
        status_code=HTTPStatus.FORBIDDEN,
        detail="Only published templates are available to non-super-admin actors.",
    )


@router.get("")
async def list_templates(
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("sites.view")),
) -> list[dict[str, object]]:
    """List all H5 templates with reference count (ref_count = agencies using this template)."""
    stmt = select(H5Template).order_by(H5Template.created_at.desc())
    if not actor.is_super_admin:
        stmt = stmt.where(H5Template.publish_status == "published")
    templates = list(session.execute(stmt).scalars().all())
    ref_counts = _template_ref_counts(session)

    return [
        _serialize_template(template, session=session, ref_count=ref_counts.get(template.id, 0))
        for template in templates
    ]


@router.post("/{template_id}/publish")
async def publish_template(
    template_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, object]:
    template = session.get(H5Template, template_id)
    if template is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Template not found")

    template.publish_status = "published"
    template.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    template.published_by = actor.actor_id
    session.flush()
    session.commit()
    return _serialize_template(template, session=session)


@router.post("/{template_id}/unpublish")
async def unpublish_template(
    template_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, object]:
    template = session.get(H5Template, template_id)
    if template is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Template not found")

    template.publish_status = "draft"
    template.published_at = None
    template.published_by = None
    session.flush()
    session.commit()
    return _serialize_template(template, session=session)


@router.post("", status_code=201)
async def create_template(
    data: CreateTemplateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, object]:
    """Create a new H5 template."""
    template = H5Template(
        id=uuid4().hex[:36],
        name=data.name,
        description=data.description,
        preview_url="",
        preview_path="",
        template_data=data.template_data,
        created_by=actor.actor_id,
    )
    template.preview_url = f"/templates/{template.id}/index.html"
    template.preview_path = template.preview_url
    session.add(template)
    session.flush()
    return _serialize_template(template, session=session)


@router.patch("/{template_id}")
async def update_template(
    template_id: str,
    data: UpdateTemplateRequest,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, str]:
    """Update an H5 template. Auto-marks referencing sites for re-sync."""
    template = session.get(H5Template, template_id)
    if template is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Template not found")

    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.template_data is not None:
        template.template_data = data.template_data
    session.flush()

    at_rows = session.execute(select(AgencyTemplate).where(AgencyTemplate.template_id == template_id)).scalars().all()
    agency_ids = [at.agency_id for at in at_rows]

    if agency_ids:
        sites = session.execute(select(H5Site).where(H5Site.agency_id.in_(agency_ids))).scalars().all()
        now_iso = datetime.now(timezone.utc).isoformat()
        for site in sites:
            meta = dict(site.metadata_json or {})
            meta["template_updated"] = True
            meta["template_updated_at"] = now_iso
            site.metadata_json = meta

        session.flush()

    return {"id": template.id, "name": template.name}


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, str]:
    """Delete an H5 template. Blocks if any agency references it."""
    template = session.get(H5Template, template_id)
    if template is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Template not found")

    ref_count = _template_ref_counts(session).get(template_id, 0)
    if ref_count > 0:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=f"模板正在被 {ref_count} 个站点使用，无法删除",
        )

    session.delete(template)
    session.flush()
    return {"message": "Template deleted"}


@router.post("/{template_id}/select")
async def select_template(
    template_id: str,
    data: SelectTemplateRequest,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, str]:
    """Agency selects an H5 template (one per agency)."""
    _require_super_admin(actor, "select templates outside the site creation flow")
    template = session.get(H5Template, template_id)
    if template is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Template not found")

    existing = session.execute(
        select(AgencyTemplate).where(AgencyTemplate.agency_id == data.agency_id)
    ).scalar_one_or_none()

    if existing:
        existing.template_id = template_id
    else:
        session.add(
            AgencyTemplate(
                id=uuid4().hex[:36],
                agency_id=data.agency_id,
                template_id=template_id,
            )
        )

    session.flush()
    return {"message": "Template selected", "agency_id": data.agency_id, "template_id": template_id}


@router.post("/{template_id}/apply")
async def apply_template(
    template_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, object]:
    """Apply a template selection to sites and persist per-site deploy status."""
    _require_super_admin(actor, "apply templates in bulk")
    template = session.get(H5Template, template_id)
    if template is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Template not found")

    sites_by_id: dict[str, H5Site] = {
        site.id: site
        for site in session.execute(
            select(H5Site).where(H5Site.metadata_json["template_id"].as_string() == template_id)
        ).scalars().all()
    }

    agency_templates = session.execute(
        select(AgencyTemplate).where(AgencyTemplate.template_id == template_id)
    ).scalars().all()
    agency_ids = [agency_template.agency_id for agency_template in agency_templates]
    if agency_ids:
        for site in session.execute(select(H5Site).where(H5Site.agency_id.in_(agency_ids))).scalars().all():
            sites_by_id.setdefault(site.id, site)

    sites = list(sites_by_id.values())
    if not sites:
        raise HTTPException(status_code=400, detail="No sites are currently bound to this template")

    preview_path = _template_preview_path(template)
    now = datetime.now(timezone.utc)
    site_ids = [site.id for site in sites]
    configs = (
        {
            config.site_id: config
            for config in session.execute(
                select(H5SiteConfig).where(H5SiteConfig.site_id.in_(site_ids))
            ).scalars().all()
        }
        if site_ids
        else {}
    )

    items: list[dict[str, object]] = []
    success_count = 0
    failure_count = 0

    for site in sites:
        actor.require_account_access(site.account_id)
        config = configs.get(site.id)
        meta = dict(site.metadata_json or {})
        meta["template_id"] = template_id
        meta["template_preview_url"] = preview_path
        meta["template_applied_at"] = now.isoformat()

        details: dict[str, object] = {
            "template_id": template_id,
            "template_name": template.name,
            "site_key": site.site_key,
            "domain": site.domain,
            "preview_url": preview_path,
            "deploy_type": config.deploy_type if config else None,
        }
        error_message: str | None = None

        if config is None:
            error_message = "Missing H5 site deploy config"
        elif not config.deploy_type or not config.domain:
            error_message = "Incomplete H5 site deploy config"

        if error_message is None:
            meta["template_apply_status"] = "success"
            meta.pop("template_apply_error", None)
            success_count += 1
            status = "success"
        else:
            meta["template_apply_status"] = "error"
            meta["template_apply_error"] = error_message
            failure_count += 1
            status = "error"
            details["error"] = error_message

        site.metadata_json = meta
        session.add(
            DeployHistory(
                site_id=site.id,
                action="apply_template",
                status=status,
                details=details,
                created_by=actor.actor_id,
            )
        )
        items.append(
            {
                "site_id": site.id,
                "site_key": site.site_key,
                "domain": site.domain,
                "status": status,
                "error": error_message,
            }
        )

    session.flush()
    session.commit()
    return {
        "template_id": template_id,
        "template_name": template.name,
        "sites_affected": len(sites),
        "success_count": success_count,
        "failure_count": failure_count,
        "items": items,
    }


@router.get("/{template_id}/preview")
async def preview_template(
    template_id: str,
    session: Session = Depends(get_db_session),
    actor: RequestActor = Depends(require_permission("sites.view")),
) -> dict[str, object]:
    """Get the real template preview path and package metadata."""
    template = session.get(H5Template, template_id)
    if template is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Template not found")
    _require_template_market_visibility(template, actor)

    return _serialize_template(template, session=session, include_manifest=True)


@router.post("/{template_id}/upload-package")
async def upload_template_package(
    template_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, object]:
    """Upload a template package (ZIP/RAR)."""
    svc = TemplatePackageService(session)
    result = await svc.upload_package(template_id, file)
    session.commit()
    return result


@router.post("/{template_id}/replace-package")
async def replace_template_package(
    template_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, object]:
    """Replace an existing template package while keeping the last good build on failure."""
    svc = TemplatePackageService(session)
    result = await svc.replace_package(template_id, file)
    session.commit()
    return result


@router.get("/{template_id}/manifest")
async def get_template_manifest(
    template_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.view")),
) -> dict:
    """Get the manifest.json content for a template."""
    svc = TemplatePackageService(session)
    return svc.get_template_manifest(template_id)


@router.get("/{template_id}/download-spec")
async def get_template_download_spec(
    template_id: str,
    session: Session = Depends(get_db_session),
    _actor: RequestActor = Depends(require_permission("sites.view")),
) -> str:
    """Return the template development specification document."""
    _ = template_id
    svc = TemplatePackageService(session)
    return svc.get_download_spec()
