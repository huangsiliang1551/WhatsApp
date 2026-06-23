from __future__ import annotations

from io import BytesIO
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    Account,
    Agency,
    AgencyTemplate,
    DeployHistory,
    H5Site,
    H5SiteConfig,
    H5Template,
)

DEFAULT_SINGLE_TEMPLATE_ID = "h5-default-v1"


def _build_template_zip(*, manifest: dict | None = None, include_index: bool = True) -> bytes:
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        if manifest is not None:
            archive.writestr("manifest.json", __import__("json").dumps(manifest))
        if include_index:
            archive.writestr("index.html", "<!doctype html><html><body>ok</body></html>")
    return payload.getvalue()


def _seed_account(session: Session, account_id: str) -> None:
    session.add(
        Account(
            account_id=account_id,
            display_name=account_id,
            provider_type="mock",
        )
    )
    session.commit()


def _seed_template(session: Session, *, template_id: str, name: str, status: str = "draft") -> H5Template:
    template = H5Template(
        id=template_id,
        name=name,
        description=f"{name} description",
        created_by="test-admin",
        status=status,
        publish_status="draft",
        template_data=None,
    )
    session.add(template)
    session.commit()
    return template


def _agent_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "agent-h5-template-market",
        "X-Actor-Role": "agent",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def _operator_headers(*account_ids: str) -> dict[str, str]:
    return {
        "X-Actor-Id": "operator-h5-template-market",
        "X-Actor-Role": "operator",
        "X-Actor-Account-Ids": ",".join(account_ids),
    }


def _seed_agency(session: Session, *, agency_id: str, name: str) -> Agency:
    agency = Agency(id=agency_id, name=name, status="active")
    session.add(agency)
    session.commit()
    return agency


def _seed_site(
    session: Session,
    *,
    site_id: str,
    account_id: str,
    agency_id: str | None,
    site_key: str,
    domain: str,
    template_id: str | None,
) -> H5Site:
    metadata_json = {"template_id": template_id} if template_id is not None else {}
    site = H5Site(
        id=site_id,
        account_id=account_id,
        agency_id=agency_id,
        site_key=site_key,
        domain=domain,
        brand_name=site_key,
        default_language="zh-CN",
        status="active",
        metadata_json=metadata_json,
    )
    session.add(site)
    session.commit()
    return site


def _seed_site_config(
    session: Session,
    *,
    site_id: str,
    domain: str,
    deploy_type: str = "ssh",
    ssh_host: str | None = "10.0.0.8",
    ssh_user: str | None = "deploy",
) -> None:
    session.add(
        H5SiteConfig(
            site_id=site_id,
            domain=domain,
            deploy_type=deploy_type,
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            ssh_key_path="/tmp/test-key",
            ssl_enabled=True,
        )
    )
    session.commit()


def test_upload_preview_and_list_share_real_template_preview_url(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_template(session, template_id="tpl-preview-1", name="Preview Template")

    archive = _build_template_zip(
        manifest={"name": "Preview Template", "version": "1.2.3", "entry": "index.html"}
    )
    upload_response = client.post(
        "/api/h5-templates/tpl-preview-1/upload-package",
        files={"file": ("template.zip", archive, "application/zip")},
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["status"] == "ready"
    assert upload_payload["preview_url"] == "/templates/tpl-preview-1/index.html"
    assert upload_payload["manifest"]["version"] == "1.2.3"

    preview_response = client.get("/api/h5-templates/tpl-preview-1/preview")
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["preview_url"] == "/templates/tpl-preview-1/index.html"
    assert preview_payload["manifest"]["version"] == "1.2.3"
    assert "test_account" not in preview_payload

    list_response = client.get("/api/h5-templates")
    assert list_response.status_code == 200
    listed = next(item for item in list_response.json() if item["id"] == "tpl-preview-1")
    assert listed["preview_url"] == "/templates/tpl-preview-1/index.html"
    assert listed["status"] == "ready"


def test_list_templates_filters_unpublished_for_agent_role(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        draft = _seed_template(session, template_id="tpl-draft-visible", name="Draft Visible", status="ready")
        published = _seed_template(session, template_id="tpl-published-visible", name="Published Visible", status="ready")
        published.publish_status = "published"
        published.published_by = "super-admin"
        session.commit()
        draft_id = draft.id
        published_id = published.id

    super_admin_response = client.get("/api/h5-templates")
    assert super_admin_response.status_code == 200
    super_admin_ids = {item["id"] for item in super_admin_response.json()}
    assert {draft_id, published_id}.issubset(super_admin_ids)

    agent_response = client.get(
        "/api/h5-templates",
        headers=_agent_headers("acct-template-market"),
    )
    assert agent_response.status_code == 200
    assert [item["id"] for item in agent_response.json() if item["id"] in {draft_id, published_id}] == [published_id]
    visible = next(item for item in agent_response.json() if item["id"] == published_id)
    assert visible["publish_status"] == "published"


def test_list_and_delete_template_use_site_level_bindings(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-template-binding")
        _seed_template(session, template_id="tpl-site-bound", name="Site Bound Template", status="ready")
        _seed_site(
            session,
            site_id="site-bound-direct",
            account_id="acct-template-binding",
            agency_id=None,
            site_key="site-bound-direct",
            domain="site-bound-direct.example.com",
            template_id="tpl-site-bound",
        )

    list_response = client.get("/api/h5-templates")
    assert list_response.status_code == 200
    listed = next(item for item in list_response.json() if item["id"] == "tpl-site-bound")
    assert listed["ref_count"] == 1

    delete_response = client.delete("/api/h5-templates/tpl-site-bound")
    assert delete_response.status_code == 409


def test_list_counts_legacy_agency_template_bindings_when_site_metadata_is_missing(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-template-legacy")
        _seed_agency(session, agency_id="agency-template-legacy", name="Legacy Agency")
        _seed_template(session, template_id="tpl-legacy-bound", name="Legacy Bound Template", status="ready")
        _seed_site(
            session,
            site_id="site-bound-legacy",
            account_id="acct-template-legacy",
            agency_id="agency-template-legacy",
            site_key="site-bound-legacy",
            domain="site-bound-legacy.example.com",
            template_id=None,
        )
        session.add(
            AgencyTemplate(
                id="agency-template-legacy-row",
                agency_id="agency-template-legacy",
                template_id="tpl-legacy-bound",
            )
        )
        session.commit()

    list_response = client.get("/api/h5-templates")
    assert list_response.status_code == 200
    listed = next(item for item in list_response.json() if item["id"] == "tpl-legacy-bound")
    assert listed["ref_count"] == 1


def test_agent_preview_requires_published_template(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        draft = _seed_template(session, template_id="tpl-preview-draft", name="Draft Preview", status="ready")
        published = _seed_template(session, template_id="tpl-preview-published", name="Published Preview", status="ready")
        published.publish_status = "published"
        published.published_at = published.created_at
        published.published_by = "super-admin"
        session.commit()
        draft_id = draft.id
        published_id = published.id

    forbidden_response = client.get(
        f"/api/h5-templates/{draft_id}/preview",
        headers=_agent_headers("acct-template-market"),
    )
    assert forbidden_response.status_code == 403
    assert "published" in forbidden_response.json()["detail"]

    allowed_response = client.get(
        f"/api/h5-templates/{published_id}/preview",
        headers=_agent_headers("acct-template-market"),
    )
    assert allowed_response.status_code == 200
    assert allowed_response.json()["id"] == published_id
    assert allowed_response.json()["publish_status"] == "published"


def test_publish_and_unpublish_template_updates_market_state(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_template(session, template_id="tpl-publish-toggle", name="Toggle Template", status="ready")

    publish_response = client.post("/api/h5-templates/tpl-publish-toggle/publish")
    assert publish_response.status_code == 200
    publish_payload = publish_response.json()
    assert publish_payload["publish_status"] == "published"
    assert publish_payload["published_by"] == "local-dev-admin"
    assert publish_payload["published_at"] is not None

    with db_session_factory() as session:
        template = session.get(H5Template, "tpl-publish-toggle")
        assert template is not None
        assert template.publish_status == "published"
        assert template.published_by == "local-dev-admin"
        assert template.published_at is not None

    unpublish_response = client.post("/api/h5-templates/tpl-publish-toggle/unpublish")
    assert unpublish_response.status_code == 200
    unpublish_payload = unpublish_response.json()
    assert unpublish_payload["publish_status"] == "draft"
    assert unpublish_payload["published_by"] is None
    assert unpublish_payload["published_at"] is None


def test_replace_package_keeps_previous_preview_when_new_package_is_invalid(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_template(session, template_id="tpl-replace-1", name="Replace Template")

    valid_archive = _build_template_zip(
        manifest={"name": "Replace Template", "version": "1.0.0", "entry": "index.html"}
    )
    first_upload = client.post(
        "/api/h5-templates/tpl-replace-1/upload-package",
        files={"file": ("template.zip", valid_archive, "application/zip")},
    )
    assert first_upload.status_code == 200

    invalid_archive = _build_template_zip(
        manifest={"name": "Replace Template", "version": "2.0.0", "entry": "index.html"},
        include_index=False,
    )
    replace_response = client.post(
        "/api/h5-templates/tpl-replace-1/replace-package",
        files={"file": ("broken.zip", invalid_archive, "application/zip")},
    )

    assert replace_response.status_code == 400

    preview_response = client.get("/api/h5-templates/tpl-replace-1/preview")
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["preview_url"] == "/templates/tpl-replace-1/index.html"
    assert preview_payload["manifest"]["version"] == "1.0.0"


def test_change_site_template_endpoint_is_disabled_in_single_template_mode(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-template-change")
        _seed_site(
            session,
            site_id="site-a",
            account_id="acct-template-change",
            agency_id=None,
            site_key="site-a",
            domain="site-a.example.com",
            template_id=DEFAULT_SINGLE_TEMPLATE_ID,
        )

    response = client.post(
        "/api/platform/sites/site-a/change-template",
        json={"template_id": DEFAULT_SINGLE_TEMPLATE_ID},
    )

    assert response.status_code == 410
    assert "single-template" in response.json()["detail"]

    with db_session_factory() as session:
        site = session.get(H5Site, "site-a")
        assert site is not None
        assert site.metadata_json == {"template_id": DEFAULT_SINGLE_TEMPLATE_ID}


def test_brand_config_prefers_site_metadata_and_falls_back_to_default_template(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-template-brand")
        _seed_agency(session, agency_id="agency-template-brand", name="Brand Agency")
        _seed_site(
            session,
            site_id="site-brand-explicit",
            account_id="acct-template-brand",
            agency_id="agency-template-brand",
            site_key="site-brand-explicit",
            domain="site-brand-explicit.example.com",
            template_id=DEFAULT_SINGLE_TEMPLATE_ID,
        )
        _seed_site(
            session,
            site_id="site-brand-fallback",
            account_id="acct-template-brand",
            agency_id="agency-template-brand",
            site_key="site-brand-fallback",
            domain="site-brand-fallback.example.com",
            template_id=None,
        )
        session.add(
            AgencyTemplate(
                id="agency-template-brand-row",
                agency_id="agency-template-brand",
                template_id="tpl-legacy-brand",
            )
        )
        session.commit()

    explicit_response = client.get("/api/h5/sites/site-brand-explicit/brand-config")
    assert explicit_response.status_code == 200
    assert explicit_response.json()["template_id"] == DEFAULT_SINGLE_TEMPLATE_ID

    fallback_response = client.get("/api/h5/sites/site-brand-fallback/brand-config")
    assert fallback_response.status_code == 200
    assert fallback_response.json()["template_id"] == DEFAULT_SINGLE_TEMPLATE_ID


def test_apply_template_writes_per_site_status_and_deploy_history_without_template_data(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-template-apply")
        _seed_agency(session, agency_id="agency-template-apply", name="Apply Agency")
        _seed_template(session, template_id="tpl-apply", name="Apply Template", status="ready")
        _seed_site(
            session,
            site_id="apply-site-ok",
            account_id="acct-template-apply",
            agency_id="agency-template-apply",
            site_key="apply-site-ok",
            domain="apply-ok.example.com",
            template_id="tpl-apply",
        )
        _seed_site(
            session,
            site_id="apply-site-missing",
            account_id="acct-template-apply",
            agency_id="agency-template-apply",
            site_key="apply-site-missing",
            domain="apply-missing.example.com",
            template_id="tpl-apply",
        )
        _seed_site_config(
            session,
            site_id="apply-site-ok",
            domain="apply-ok.example.com",
        )
        session.add(
            AgencyTemplate(
                id="agency-template-apply-row",
                agency_id="agency-template-apply",
                template_id="tpl-apply",
            )
        )
        session.commit()

    response = client.post("/api/h5-templates/tpl-apply/apply")

    assert response.status_code == 200
    payload = response.json()
    assert payload["template_id"] == "tpl-apply"
    assert payload["success_count"] == 1
    assert payload["failure_count"] == 1
    by_site = {item["site_id"]: item for item in payload["items"]}
    assert by_site["apply-site-ok"]["status"] == "success"
    assert by_site["apply-site-missing"]["status"] == "error"

    with db_session_factory() as session:
        ok_site = session.get(H5Site, "apply-site-ok")
        failed_site = session.get(H5Site, "apply-site-missing")
        assert ok_site is not None
        assert failed_site is not None
        assert ok_site.metadata_json["template_apply_status"] == "success"
        assert failed_site.metadata_json["template_apply_status"] == "error"
        assert "template_apply_error" in failed_site.metadata_json

        deploy_rows = session.execute(
            select(DeployHistory).order_by(DeployHistory.site_id)
        ).scalars().all()
        assert len(deploy_rows) == 2
        assert {row.site_id for row in deploy_rows} == {"apply-site-ok", "apply-site-missing"}
        assert {row.status for row in deploy_rows} == {"success", "error"}


def test_apply_template_uses_site_metadata_binding_without_agency_template(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-template-metadata")
        _seed_template(session, template_id="tpl-metadata-apply", name="Metadata Apply", status="ready")
        _seed_site(
            session,
            site_id="metadata-site-1",
            account_id="acct-template-metadata",
            agency_id=None,
            site_key="metadata-site-1",
            domain="metadata-site-1.example.com",
            template_id="tpl-metadata-apply",
        )
        _seed_site_config(
            session,
            site_id="metadata-site-1",
            domain="metadata-site-1.example.com",
        )

    response = client.post("/api/h5-templates/tpl-metadata-apply/apply")

    assert response.status_code == 200
    payload = response.json()
    assert payload["template_id"] == "tpl-metadata-apply"
    assert payload["sites_affected"] == 1
    assert payload["success_count"] == 1
    assert payload["failure_count"] == 0


def test_create_site_defaults_single_template_without_agency_template_write(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-create-site-default")

    response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "acct-create-site-default",
            "site_key": "site-default-bind",
            "domain": "site-default-bind.example.com",
            "brand_name": "Default Bind",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metadata_json"]["template_id"] == DEFAULT_SINGLE_TEMPLATE_ID

    with db_session_factory() as session:
        site = session.get(H5Site, payload["id"])
        assert site is not None
        assert site.metadata_json == {"template_id": DEFAULT_SINGLE_TEMPLATE_ID}
        agency_template_count = session.scalar(select(func.count()).select_from(AgencyTemplate))
        assert agency_template_count == 0


def test_create_site_rejects_non_default_template_values(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-create-site-invalid-template")

    explicit_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "acct-create-site-invalid-template",
            "site_key": "site-invalid-template-id",
            "domain": "site-invalid-template-id.example.com",
            "brand_name": "Invalid Template Id",
            "template_id": "tpl-not-allowed",
        },
    )
    assert explicit_response.status_code == 422
    assert "template_id" in explicit_response.text

    metadata_response = client.post(
        "/api/platform/sites",
        json={
            "account_id": "acct-create-site-invalid-template",
            "site_key": "site-invalid-metadata-template",
            "domain": "site-invalid-metadata-template.example.com",
            "brand_name": "Invalid Metadata Template",
            "metadata_json": {"template_id": "tpl-not-allowed"},
        },
    )
    assert metadata_response.status_code == 422
    assert "template_id" in metadata_response.text
