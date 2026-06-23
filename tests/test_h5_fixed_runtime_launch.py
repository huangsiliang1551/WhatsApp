from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.db.models import Account, H5Site, H5SiteConfig, H5Template
from app.services.h5_deploy_service import H5DeployService
from app.services.h5_site_bootstrap_service import (
    DEFAULT_H5_SITE_DEFINITIONS,
    H5SiteBootstrapService,
)
from app.services.h5_template_bootstrap_service import H5TemplateBootstrapService


def _seed_account(session: Session, account_id: str) -> None:
    session.add(
        Account(
            account_id=account_id,
            display_name=account_id,
            provider_type="mock",
        )
    )
    session.commit()


def _seed_site(
    session: Session,
    *,
    site_id: str,
    account_id: str,
    site_key: str,
    domain: str,
    brand_name: str,
    logo_url: str | None = None,
    metadata_json: dict | None = None,
) -> H5Site:
    site = H5Site(
        id=site_id,
        account_id=account_id,
        site_key=site_key,
        domain=domain,
        brand_name=brand_name,
        logo_url=logo_url,
        default_language="zh-CN",
        status="active",
        metadata_json=metadata_json or {},
    )
    session.add(site)
    session.commit()
    return site


def _seed_site_config(session: Session, *, site_id: str) -> H5SiteConfig:
    config = H5SiteConfig(
        site_id=site_id,
        logo_url="https://cdn.example.com/runtime-logo.png",
        favicon_url="https://cdn.example.com/runtime-favicon.ico",
        primary_color="#0f766e",
        font_family="Source Han Sans SC",
        footer_text="Runtime footer copy",
        domain="runtime-preview.example.com",
        deploy_type="docker",
        ssl_enabled=True,
    )
    session.add(config)
    session.commit()
    return config


def _super_admin_headers() -> dict[str, str]:
    return {
        "X-Actor-Id": "super-admin-fixed-h5",
        "X-Actor-Role": "super_admin",
    }


def test_h5_site_bootstrap_sets_default_template_binding(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        service = H5SiteBootstrapService(session)
        created = service.ensure_default_sites(only_when_empty=True)
        repaired = service.backfill_default_template_bindings()
        sites = session.scalars(select(H5Site).order_by(H5Site.site_key)).all()

    assert created == len(DEFAULT_H5_SITE_DEFINITIONS)
    assert repaired == 0
    assert [site.metadata_json for site in sites] == [
        {"template_id": DEFAULT_H5_TEMPLATE_ID}
        for _ in DEFAULT_H5_SITE_DEFINITIONS
    ]


def test_h5_site_bootstrap_backfills_existing_sites_without_template_binding(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-existing-site-backfill")
        _seed_site(
            session,
            site_id="site-existing-site-backfill",
            account_id="acct-existing-site-backfill",
            site_key="existing-site-backfill",
            domain="existing-site-backfill.example.com",
            brand_name="Existing Site Backfill",
            metadata_json={},
        )

        service = H5SiteBootstrapService(session)
        repaired = service.backfill_default_template_bindings()
        site = session.get(H5Site, "site-existing-site-backfill")

    assert repaired == 1
    assert site is not None
    assert site.metadata_json == {"template_id": DEFAULT_H5_TEMPLATE_ID}


def test_h5_site_bootstrap_creates_missing_default_sites_when_other_sites_already_exist(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-existing-non-default")
        _seed_site(
            session,
            site_id="site-existing-non-default",
            account_id="acct-existing-non-default",
            site_key="existing-non-default",
            domain="existing-non-default.example.com",
            brand_name="Existing Non Default",
            metadata_json={"template_id": DEFAULT_H5_TEMPLATE_ID},
        )

        service = H5SiteBootstrapService(session)
        created = service.ensure_default_sites(only_when_empty=False)
        site_keys = session.scalars(select(H5Site.site_key).order_by(H5Site.site_key)).all()

    assert created == len(DEFAULT_H5_SITE_DEFINITIONS)
    assert site_keys == sorted(
        ["existing-non-default", *[definition.site_key for definition in DEFAULT_H5_SITE_DEFINITIONS]]
    )


def test_default_template_bootstrap_creates_fixed_published_template(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        service = H5TemplateBootstrapService(session)

        created = service.ensure_default_template()
        created_again = service.ensure_default_template()

        template = session.get(H5Template, DEFAULT_H5_TEMPLATE_ID)

    assert created is True
    assert created_again is False
    assert template is not None
    assert template.id == DEFAULT_H5_TEMPLATE_ID
    assert template.status == "ready"
    assert template.publish_status == "published"
    assert template.preview_url == "/h5/login?site_key=mall-cn"
    assert template.preview_path == "/h5/login?site_key=mall-cn"
    assert template.template_data == {
        "mode": "single_template",
        "entry": "/h5/login",
        "site_key_param": "site_key",
        "default_site_key": "mall-cn",
    }


def test_brand_config_returns_runtime_site_config_and_fixed_template(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-runtime-brand-config")
        _seed_site(
            session,
            site_id="site-runtime-brand-config",
            account_id="acct-runtime-brand-config",
            site_key="runtime-brand-config",
            domain="runtime-brand-config.example.com",
            brand_name="Runtime Brand Config",
            logo_url="https://cdn.example.com/site-logo.png",
            metadata_json={"template_id": "tpl-legacy-ignored"},
        )
        _seed_site_config(session, site_id="site-runtime-brand-config")

    response = client.get("/api/h5/sites/runtime-brand-config/brand-config")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "brand_name": "Runtime Brand Config",
        "logo_url": "https://cdn.example.com/runtime-logo.png",
        "favicon_url": "https://cdn.example.com/runtime-favicon.ico",
        "site_key": "runtime-brand-config",
        "default_language": "zh-CN",
        "template_id": DEFAULT_H5_TEMPLATE_ID,
        "primary_color": "#0f766e",
        "font_family": "Source Han Sans SC",
        "footer_text": "Runtime footer copy",
    }


def test_platform_site_preview_endpoint_returns_fixed_h5_entry(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-fixed-preview")
        _seed_site(
            session,
            site_id="site-fixed-preview",
            account_id="acct-fixed-preview",
            site_key="fixed-preview",
            domain="fixed-preview.example.com",
            brand_name="Fixed Preview",
        )

    response = client.get(
        "/api/platform/sites/site-fixed-preview/preview",
        headers=_super_admin_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "site_id": "site-fixed-preview",
        "site_key": "fixed-preview",
        "template_id": DEFAULT_H5_TEMPLATE_ID,
        "preview_url": "/h5/login?site_key=fixed-preview",
        "brand_config_url": "/api/h5/sites/fixed-preview/brand-config",
    }


def test_generate_deploy_script_uses_docker_stack_for_fixed_h5() -> None:
    site = H5Site(
        id="site-fixed-deploy",
        account_id="acct-fixed-deploy",
        site_key="fixed-deploy",
        domain="fixed-deploy.example.com",
        brand_name="Fixed Deploy",
        default_language="zh-CN",
        status="active",
        metadata_json={"template_id": DEFAULT_H5_TEMPLATE_ID},
    )
    config = H5SiteConfig(
        site_id="site-fixed-deploy",
        domain="fixed-deploy.example.com",
        deploy_type="docker",
        ssl_enabled=True,
    )

    script = H5DeployService().generate_deploy_script(site, config)

    assert "docker compose" in script
    assert "frontend" in script
    assert "SITE_KEY=fixed-deploy" in script
    assert "PUBLIC_SITE_DOMAIN=fixed-deploy.example.com" in script
    assert "PUBLIC_TEMPLATE_ID=h5-default-v1" in script
    assert "apt-get install -y nginx certbot" not in script
