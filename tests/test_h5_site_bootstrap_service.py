from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, H5Site
from app.services.h5_site_bootstrap_service import (
    DEFAULT_H5_SITE_DEFINITIONS,
    H5SiteBootstrapService,
)


def test_h5_site_bootstrap_seeds_default_sites_and_accounts(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        service = H5SiteBootstrapService(session)

        created = service.ensure_default_sites(only_when_empty=True)
        created_again = service.ensure_default_sites(only_when_empty=True)

        sites = session.scalars(select(H5Site).order_by(H5Site.site_key)).all()
        accounts = session.scalars(select(Account).order_by(Account.account_id)).all()

    assert created == len(DEFAULT_H5_SITE_DEFINITIONS)
    assert created_again == 0
    assert [site.site_key for site in sites] == sorted(
        definition.site_key for definition in DEFAULT_H5_SITE_DEFINITIONS
    )
    assert [account.account_id for account in accounts] == sorted(
        definition.account_id for definition in DEFAULT_H5_SITE_DEFINITIONS
    )


def test_h5_site_bootstrap_skips_defaults_when_sites_already_exist(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as session:
        session.add(
            Account(
                account_id="acct-existing-h5",
                display_name="Existing H5 Account",
            )
        )
        session.add(
            H5Site(
                account_id="acct-existing-h5",
                site_key="existing-h5",
                domain="existing-h5.example.com",
                brand_name="Existing H5",
            )
        )
        session.commit()

        service = H5SiteBootstrapService(session)
        created = service.ensure_default_sites(only_when_empty=True)

        sites = session.scalars(select(H5Site).order_by(H5Site.site_key)).all()

    assert created == 0
    assert [site.site_key for site in sites] == ["existing-h5"]
