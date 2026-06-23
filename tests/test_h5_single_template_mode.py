from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.db.models import Account, Agency, AgencyTemplate, H5Site, H5Template
from app.schemas.platform import H5SiteCreateRequest
from app.services.platform_service import PlatformService


def _seed_account(session: Session, account_id: str) -> None:
    session.add(
        Account(
            account_id=account_id,
            display_name=account_id,
            provider_type="mock",
        )
    )
    session.commit()


def _seed_template(
    session: Session,
    *,
    template_id: str,
    name: str,
    publish_status: str = "published",
) -> H5Template:
    template = H5Template(
        id=template_id,
        name=name,
        description=f"{name} description",
        created_by="test-admin",
        status="ready",
        publish_status=publish_status,
    )
    session.add(template)
    session.commit()
    return template


def test_create_site_defaults_to_fixed_h5_when_template_id_is_omitted(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-single-template-default")
        _seed_template(session, template_id=DEFAULT_H5_TEMPLATE_ID, name="Default H5")
        service = PlatformService(session)

        created = asyncio.run(
            service.create_site(
                H5SiteCreateRequest(
                    account_id="acct-single-template-default",
                    site_key="single-template-default",
                    domain="single-template-default.example.com",
                    brand_name="Single Template Default",
                )
            )
        )

        assert created.metadata_json is not None
        assert created.metadata_json["template_id"] == DEFAULT_H5_TEMPLATE_ID


def test_create_site_rejects_non_default_template_even_when_template_exists(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-single-template-guard")
        _seed_template(session, template_id=DEFAULT_H5_TEMPLATE_ID, name="Default H5")
        _seed_template(session, template_id="tpl-legacy-market", name="Legacy Market Template")
        service = PlatformService(session)

        try:
            asyncio.run(
                service.create_site(
                    H5SiteCreateRequest(
                        account_id="acct-single-template-guard",
                        site_key="single-template-guard",
                        domain="single-template-guard.example.com",
                        brand_name="Single Template Guard",
                        template_id="tpl-legacy-market",
                    )
                )
            )
            raise AssertionError("Expected site creation to reject non-default template IDs.")
        except ValueError as exc:
            assert "default" in str(exc).lower()


def test_brand_config_falls_back_to_default_template_when_site_has_no_template_binding(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-brand-config-default")
        _seed_template(session, template_id=DEFAULT_H5_TEMPLATE_ID, name="Default H5")
        agency = Agency(id="agency-brand-config-default", name="Brand Config Agency", status="active")
        session.add(agency)
        session.add(
            H5Site(
                id="site-brand-config-default",
                account_id="acct-brand-config-default",
                agency_id=agency.id,
                site_key="brand-config-default",
                domain="brand-config-default.example.com",
                brand_name="Brand Config Default",
                default_language="zh-CN",
                status="active",
                metadata_json={},
            )
        )
        session.add(
            AgencyTemplate(
                id="agency-template-brand-config-default",
                agency_id=agency.id,
                template_id="tpl-legacy-market",
            )
        )
        session.commit()

    response = client.get("/api/h5/sites/brand-config-default/brand-config")

    assert response.status_code == 200
    assert response.json()["template_id"] == DEFAULT_H5_TEMPLATE_ID


def test_change_template_endpoint_is_retired(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        _seed_account(session, "acct-change-template-retired")
        _seed_template(session, template_id=DEFAULT_H5_TEMPLATE_ID, name="Default H5")
        session.add(
            H5Site(
                id="site-change-template-retired",
                account_id="acct-change-template-retired",
                site_key="change-template-retired",
                domain="change-template-retired.example.com",
                brand_name="Change Template Retired",
                default_language="zh-CN",
                status="active",
                metadata_json={"template_id": DEFAULT_H5_TEMPLATE_ID},
            )
        )
        session.commit()

    response = client.post(
        "/api/platform/sites/site-change-template-retired/change-template",
        json={"template_id": DEFAULT_H5_TEMPLATE_ID},
    )

    assert response.status_code in {403, 410}
    assert "template" in response.json()["detail"].lower()
