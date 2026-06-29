from fastapi import APIRouter, Depends, HTTPException, Query, Response

from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_platform_service, get_runtime_state_service, require_permission
from app.constants.h5_templates import CHANGE_TEMPLATE_DISABLED_ERROR, DEFAULT_H5_TEMPLATE_ID
from app.core.auth import RequestActor
from app.db.models import AppUser
from app.schemas.platform import (
    AudienceRuleSetCreateRequest,
    AudienceRuleSetUpdateRequest,
    H5SiteResponse,
    H5SiteConfigUpdateRequest,
    H5SiteCreateRequest,
    H5SiteUpdateRequest,
    PlatformUserCreateRequest,
    PlatformUserPaginatedResponse,
    PlatformUserResponse,
    UserTagCreateRequest,
)
from app.services.platform_service import PlatformService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(prefix="/api/platform", tags=["platform"])


async def _get_accessible_site_or_404(
    platform_service: PlatformService,
    actor: RequestActor,
    site_id: str,
) -> H5SiteResponse:
    site = await platform_service.get_site(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found.")
    actor.require_account_access(site.account_id)
    return site


def _resolve_actor_site_account_id(actor: RequestActor) -> str:
    unique_account_ids = list(dict.fromkeys(actor.account_ids))
    if len(unique_account_ids) == 1:
        return unique_account_ids[0]
    if not unique_account_ids:
        raise HTTPException(status_code=403, detail="Actor has no accessible account scope for site import.")
    raise HTTPException(
        status_code=409,
        detail="Site import requires a single resolved account scope.",
    )


@router.get(
    "/sites",
    summary="List H5 sites",
    description="List all H5 sites with account scope filtering.",
    tags=["platform"],
)
async def list_sites(
    platform_service: PlatformService = Depends(get_platform_service),
    actor: RequestActor = Depends(require_permission("sites.view")),
) -> list[dict[str, object]]:
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    return [
        item.model_dump(mode="json")
        for item in await platform_service.list_sites(allowed_account_ids=allowed_account_ids)
    ]


@router.post(
    "/sites",
    summary="Create H5 site",
    description="Create a new H5 site under a specific account.",
    tags=["platform"],
)
async def create_site(
    payload: H5SiteCreateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("sites.create")),
) -> dict[str, object]:
    actor.require_account_access(payload.account_id)
    try:
        site = await platform_service.create_site(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=site.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_site_created",
        target_type="h5_site",
        target_id=site.site_key,
        payload={"domain": site.domain, "status": site.status},
    )
    runtime_state.commit()
    return site.model_dump(mode="json")


@router.put(
    "/sites/{site_id}",
    summary="Update H5 site",
    description="Partial update of an existing H5 site.",
    tags=["platform"],
)
async def update_site(
    site_id: str,
    payload: H5SiteUpdateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict[str, object]:
    await _get_accessible_site_or_404(platform_service, actor, site_id)
    try:
        site = await platform_service.update_site(site_id, payload)
    except ValueError as exc:
        if "not found" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=site.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_site_updated",
        target_type="h5_site",
        target_id=site.site_key,
        payload=payload.model_dump(exclude_none=True, mode="json"),
    )
    runtime_state.commit()
    return site.model_dump(mode="json")


@router.delete(
    "/sites/{site_id}",
    summary="Delete (archive) H5 site",
    description="Soft-delete an H5 site by setting its status to archived.",
    tags=["platform"],
)
async def delete_site(
    site_id: str,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("sites.delete")),
) -> dict[str, str | None]:
    await _get_accessible_site_or_404(platform_service, actor, site_id)
    try:
        account_id = await platform_service.delete_site(site_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_site_deleted",
        target_type="h5_site",
        target_id=site_id,
        payload={},
    )
    runtime_state.commit()
    return {"id": site_id, "status": "archived"}


class ChangeTemplateRequest(BaseModel):
    template_id: str


@router.post(
    "/sites/{site_id}/change-template",
    summary="Change site template",
    description="Change the H5 template bound to a site.",
    tags=["platform"],
)
async def change_site_template(
    site_id: str,
    body: ChangeTemplateRequest,
    actor: RequestActor = Depends(require_permission("sites.template")),
) -> dict:
    """Changing templates is no longer supported after single-template convergence."""
    _ = site_id, body, actor
    raise HTTPException(status_code=410, detail=CHANGE_TEMPLATE_DISABLED_ERROR)


@router.get(
    "/sites/{site_id}/preview",
    summary="Get fixed H5 preview entry",
    description="Return the fixed H5 preview URL for a site in single-template mode.",
    tags=["platform"],
)
async def get_site_preview(
    site_id: str,
    platform_service: PlatformService = Depends(get_platform_service),
    actor: RequestActor = Depends(require_permission("sites.view")),
) -> dict[str, str]:
    site = await _get_accessible_site_or_404(platform_service, actor, site_id)
    return {
        "site_id": site.id,
        "site_key": site.site_key,
        "template_id": DEFAULT_H5_TEMPLATE_ID,
        "preview_url": f"/h5/login?site_key={site.site_key}",
        "brand_config_url": f"/api/h5/sites/{site.site_key}/brand-config",
    }


@router.get(
    "/sites/{site_id}/config",
    summary="Get H5 site config",
    description="Get the brand & deploy configuration for an H5 site.",
    tags=["platform"],
)
async def get_site_config(
    site_id: str,
    platform_service: PlatformService = Depends(get_platform_service),
    actor: RequestActor = Depends(require_permission("sites.brand_config")),
) -> dict[str, object]:
    await _get_accessible_site_or_404(platform_service, actor, site_id)
    config = await platform_service.get_site_config(site_id)
    if config is None:
        return {"id": None, "site_id": site_id}
    return config.model_dump(mode="json")


@router.put(
    "/sites/{site_id}/config",
    summary="Update H5 site config",
    description="Upsert brand & deploy configuration for an H5 site.",
    tags=["platform"],
)
async def update_site_config(
    site_id: str,
    payload: H5SiteConfigUpdateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("sites.brand_config")),
) -> dict[str, object]:
    site = await _get_accessible_site_or_404(platform_service, actor, site_id)
    config = await platform_service.update_site_config(site_id, payload)

    runtime_state.add_audit_log(
        account_id=site.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_site_config_updated",
        target_type="h5_site_config",
        target_id=site_id,
        payload=payload.model_dump(exclude_none=True, mode="json"),
    )
    runtime_state.commit()
    return config.model_dump(mode="json")


@router.get(
    "/users",
    summary="List platform users",
    description="List platform users with optional filters, pagination, search, and aggregate fields.",
    tags=["platform"],
)
async def list_users(
    page: int | None = Query(default=None, ge=1, description="Page number (omit for full list backward compat)"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    sort: str = Query(default="created_at:desc", description="Sort field and direction, e.g. created_at:desc"),
    search: str | None = Query(default=None, description="Search by public_user_id, display_name, or phone number"),
    account_id: str | None = Query(default=None, description="Filter by account_id"),
    has_whatsapp: bool | None = Query(default=None, description="Filter by WhatsApp binding status"),
    registration_site_id: str | None = None,
    lifecycle_status: str | None = None,
    is_anonymous: bool | None = None,
    platform_service: PlatformService = Depends(get_platform_service),
    actor: RequestActor = Depends(require_permission("users.view")),
) -> PlatformUserPaginatedResponse | list[PlatformUserResponse]:
    if registration_site_id is not None:
        site = await platform_service.get_site(registration_site_id)
        if site is not None:
            actor.require_account_access(site.account_id)
    if account_id:
        actor.require_account_access(account_id)
    allowed_account_ids = None if actor.is_super_admin else set(actor.account_ids)
    result = await platform_service.list_users_enhanced(
        page=page,
        size=size,
        sort=sort,
        search=search,
        account_id=account_id,
        has_whatsapp=has_whatsapp,
        registration_site_id=registration_site_id,
        lifecycle_status=lifecycle_status,
        is_anonymous=is_anonymous,
        allowed_account_ids=allowed_account_ids,
        scope_actor=actor,
    )
    return result


@router.post(
    "/users",
    summary="Create platform user",
    description="Create a new platform user.",
    tags=["platform"],
)
async def create_user(
    payload: PlatformUserCreateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("users.create")),
) -> dict[str, object]:
    try:
        resolved_account_id = platform_service.resolve_create_user_account_id(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    actor.require_account_access(resolved_account_id)
    try:
        user = await platform_service.create_user(payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=user.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_user_created",
        target_type="app_user",
        target_id=user.public_user_id,
        payload={
            "registration_site_id": user.registration_site_id,
            "is_anonymous": user.is_anonymous,
            "lifecycle_status": user.lifecycle_status,
            "tag_keys": [tag.tag_key for tag in user.tags],
        },
    )
    runtime_state.commit()
    return user.model_dump(mode="json")


@router.delete(
    "/users/{user_id}",
    summary="Delete platform user",
    description="Delete a platform user by ID.",
    tags=["platform"],
    status_code=204,
)
async def delete_platform_user(
    user_id: str,
    db_session: Session = Depends(get_db_session),
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("users.delete")),
) -> Response:
    user = db_session.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' was not found.")
    actor.require_account_access(user.account_id)
    try:
        await platform_service.delete_user(user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=user.account_id,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_user_deleted",
        target_type="app_user",
        target_id=user_id,
        payload={},
    )
    runtime_state.commit()
    return Response(status_code=204)


@router.get(
    "/tags",
    summary="List user tags",
    description="List user tags with optional active filter.",
    tags=["platform"],
)
async def list_tags(
    is_active: bool | None = None,
    platform_service: PlatformService = Depends(get_platform_service),
    actor: RequestActor = Depends(require_permission("tags.view")),
) -> list[dict[str, object]]:
    _ = actor
    return [item.model_dump(mode="json") for item in await platform_service.list_tags(is_active=is_active)]


@router.post(
    "/tags",
    summary="Create user tag",
    description="Create a new user tag.",
    tags=["platform"],
)
async def create_tag(
    payload: UserTagCreateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("tags.create")),
) -> dict[str, object]:
    try:
        tag = await platform_service.create_tag(payload, created_by=actor.actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=None,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_tag_created",
        target_type="user_tag",
        target_id=tag.tag_key,
        payload={"source_type": tag.source_type, "is_active": tag.is_active},
    )
    runtime_state.commit()
    return tag.model_dump(mode="json")


@router.get(
    "/audience-rules",
    summary="List audience rules",
    description="List audience rule sets with optional filters.",
    tags=["platform"],
)
async def list_audience_rule_sets(
    scope_type: str | None = None,
    status: str | None = None,
    platform_service: PlatformService = Depends(get_platform_service),
    actor: RequestActor = Depends(require_permission("audience_rules.view")),
) -> list[dict[str, object]]:
    _ = actor
    return [
        item.model_dump(mode="json")
        for item in await platform_service.list_audience_rule_sets(scope_type=scope_type, status=status)
    ]


@router.post(
    "/audience-rules",
    summary="Create audience rule",
    description="Create a new audience rule set.",
    tags=["platform"],
)
async def create_audience_rule_set(
    payload: AudienceRuleSetCreateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("audience_rules.create")),
) -> dict[str, object]:
    try:
        rule = await platform_service.create_audience_rule_set(payload, created_by=actor.actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=None,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_audience_rule_created",
        target_type="audience_rule_set",
        target_id=rule.rule_key,
        payload={"scope_type": rule.scope_type, "status": rule.status},
    )
    runtime_state.commit()
    return rule.model_dump(mode="json")


@router.patch(
    "/audience-rules/{rule_set_id}",
    summary="Update audience rule",
    description="Update an existing audience rule set by ID.",
    tags=["platform"],
)
async def update_audience_rule_set(
    rule_set_id: str,
    payload: AudienceRuleSetUpdateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("audience_rules.edit")),
) -> dict[str, object]:
    try:
        rule = await platform_service.update_audience_rule_set(
            rule_set_id, payload, updated_by=actor.actor_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=None,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_audience_rule_updated",
        target_type="audience_rule_set",
        target_id=rule.rule_key,
        payload=payload.model_dump(exclude_none=True, mode="json"),
    )
    runtime_state.commit()
    return rule.model_dump(mode="json")


@router.delete(
    "/audience-rules/{rule_set_id}",
    summary="Delete audience rule",
    description="Delete an audience rule set by ID.",
    tags=["platform"],
    status_code=204,
)
async def delete_audience_rule_set(
    rule_set_id: str,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("audience_rules.delete")),
) -> Response:
    try:
        await platform_service.delete_audience_rule_set(rule_set_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=None,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_audience_rule_deleted",
        target_type="audience_rule_set",
        target_id=rule_set_id,
        payload={},
    )
    runtime_state.commit()
    return Response(status_code=204)


# ──────────────────────────────────────────────
# SITE-BE-002: Clone Site
# ──────────────────────────────────────────────


class CloneSiteRequest(BaseModel):
    new_site_key: str
    new_brand_name: str
    new_domain: str
    clone_brand_config: bool = True
    clone_deploy_config: bool = True
    clone_translations: bool = False
    clone_permissions: bool = False


@router.post(
    "/sites/{site_id}/clone",
    summary="Clone H5 site",
    description="Clone a site's configurations to create a new site.",
    tags=["platform"],
)
async def clone_site(
    site_id: str,
    payload: CloneSiteRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("sites.clone")),
) -> dict:
    await _get_accessible_site_or_404(platform_service, actor, site_id)
    try:
        site = await platform_service.clone_site(
            source_site_id=site_id,
            new_site_key=payload.new_site_key,
            new_brand_name=payload.new_brand_name,
            new_domain=payload.new_domain,
            clone_brand_config=payload.clone_brand_config,
            clone_deploy_config=payload.clone_deploy_config,
            clone_translations=payload.clone_translations,
            clone_permissions=payload.clone_permissions,
        )
    except (LookupError, ValueError) as exc:
        status_code = 404 if isinstance(exc, LookupError) else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=site["account_id"],
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_site_cloned",
        target_type="h5_site",
        target_id=site["site_key"],
        payload={"source_site_id": site_id, **payload.model_dump(mode="json")},
    )
    runtime_state.commit()
    return site


# ──────────────────────────────────────────────
# SITE-BE-003: Export / Import Config
# ──────────────────────────────────────────────


@router.get(
    "/sites/{site_id}/export-config",
    summary="Export site config",
    description="Export a site's full configuration as JSON.",
    tags=["platform"],
)
async def export_site_config(
    site_id: str,
    platform_service: PlatformService = Depends(get_platform_service),
    actor: RequestActor = Depends(require_permission("sites.deploy")),
) -> dict:
    await _get_accessible_site_or_404(platform_service, actor, site_id)
    try:
        return await platform_service.export_config(site_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ImportConfigRequest(BaseModel):
    site: dict
    config: dict | None = None
    translations: list[dict] = []
    permissions: list[dict] = []


@router.post(
    "/sites/import-config",
    summary="Import site config",
    description="Import a full site configuration and create a new site.",
    tags=["platform"],
    status_code=201,
)
async def import_site_config(
    payload: ImportConfigRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("sites.deploy")),
) -> dict:
    account_id = _resolve_actor_site_account_id(actor)
    try:
        site = await platform_service.import_config(
            payload=payload.model_dump(mode="json"),
            account_id=account_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    runtime_state.add_audit_log(
        account_id=site["account_id"],
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action="platform_site_imported",
        target_type="h5_site",
        target_id=site["site_key"],
        payload={},
    )
    runtime_state.commit()
    return site


# ──────────────────────────────────────────────
# SITE-BE-004: Batch Update
# ──────────────────────────────────────────────


class BatchUpdateRequest(BaseModel):
    site_ids: list[str]
    action: str  # pause / resume / delete / update_config
    config: dict | None = None


@router.post(
    "/sites/batch-update",
    summary="Batch update sites",
    description="Perform batch actions on multiple sites (pause/resume/delete/update_config).",
    tags=["platform"],
)
async def batch_update_sites(
    payload: BatchUpdateRequest,
    platform_service: PlatformService = Depends(get_platform_service),
    runtime_state: RuntimeStateStore = Depends(get_runtime_state_service),
    actor: RequestActor = Depends(require_permission("sites.edit")),
) -> dict:
    for site_id in payload.site_ids:
        await _get_accessible_site_or_404(platform_service, actor, site_id)
    result = await platform_service.batch_update(
        site_ids=payload.site_ids,
        action=payload.action,
        config=payload.config,
    )

    runtime_state.add_audit_log(
        account_id=None,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        action=f"platform_sites_batch_{payload.action}",
        target_type="h5_site",
        target_id=",".join(payload.site_ids),
        payload={"action": payload.action},
    )
    runtime_state.commit()
    return result
