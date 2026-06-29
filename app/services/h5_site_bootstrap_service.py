from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants.h5_templates import DEFAULT_H5_TEMPLATE_ID
from app.db.models import Account, H5Site


@dataclass(frozen=True, slots=True)
class DefaultH5SiteDefinition:
    account_id: str
    account_display_name: str
    site_key: str
    domain: str
    brand_name: str
    default_language: str = "zh-CN"


DEFAULT_H5_SITE_DEFINITIONS: tuple[DefaultH5SiteDefinition, ...] = (
    DefaultH5SiteDefinition(
        account_id="acct-h5-mall-cn",
        account_display_name="H5 Mall CN",
        site_key="mall-cn",
        domain="mall-cn.example.com",
        brand_name="Brand mall-cn",
    ),
    DefaultH5SiteDefinition(
        account_id="acct-h5-daily-cn",
        account_display_name="H5 Daily CN",
        site_key="daily-cn",
        domain="daily-cn.example.com",
        brand_name="Brand daily-cn",
    ),
    DefaultH5SiteDefinition(
        account_id="acct-h5-flash-sale",
        account_display_name="H5 Flash Sale",
        site_key="flash-sale",
        domain="flash-sale.example.com",
        brand_name="Brand flash-sale",
    ),
)


class H5SiteBootstrapService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_default_sites(self, *, only_when_empty: bool) -> int:
        existing_sites = self._session.scalars(select(H5Site.site_key)).all()
        if only_when_empty and existing_sites:
            return 0

        existing_site_keys = set(existing_sites)
        created = 0

        for definition in DEFAULT_H5_SITE_DEFINITIONS:
            if definition.site_key in existing_site_keys:
                continue

            account = self._session.get(Account, definition.account_id)
            if account is None:
                account = Account(
                    account_id=definition.account_id,
                    display_name=definition.account_display_name,
                )
                self._session.add(account)

            self._session.add(
                H5Site(
                    account_id=definition.account_id,
                    site_key=definition.site_key,
                    domain=definition.domain,
                    brand_name=definition.brand_name,
                    default_language=definition.default_language,
                    metadata_json={"template_id": DEFAULT_H5_TEMPLATE_ID},
                )
            )
            created += 1

        if created > 0:
            self._session.commit()

        return created

    def backfill_default_template_bindings(self) -> int:
        sites = self._session.scalars(select(H5Site)).all()
        updated = 0

        for site in sites:
            metadata = dict(site.metadata_json or {})
            if metadata.get("template_id") == DEFAULT_H5_TEMPLATE_ID:
                continue

            metadata["template_id"] = DEFAULT_H5_TEMPLATE_ID
            site.metadata_json = metadata
            updated += 1

        if updated > 0:
            self._session.commit()

        return updated
