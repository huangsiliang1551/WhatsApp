from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    AppUser,
    SiteWhatsAppPhonePool,
    UserWhatsAppServiceAssignment,
)
from app.services.whatsapp_phone_selection_service import WhatsAppPhoneSelectionService
from tests.test_h5_member_auth import _create_site, _register_member


def _seed_pool(
    session: Session,
    *,
    account_id: str,
    site_id: str,
    waba_id: str,
    phone_number_id: str,
    display_phone_number: str,
    status: str = "active",
    weight: int = 100,
    priority: int = 100,
    allow_new_users: bool = True,
    allow_existing_users: bool = True,
    only_existing_users: bool = False,
    ready_for_webhook_delivery: bool = True,
    ready_for_outbound_messages: bool = True,
    low_quality_stop_new_users: bool = True,
    quality_rating_snapshot: str | None = "GREEN",
    active_conversation_count: int = 0,
) -> SiteWhatsAppPhonePool:
    pool = SiteWhatsAppPhonePool(
        account_id=account_id,
        site_id=site_id,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
        display_phone_number=display_phone_number,
        status=status,
        weight=weight,
        priority=priority,
        allow_new_users=allow_new_users,
        allow_existing_users=allow_existing_users,
        only_existing_users=only_existing_users,
        ready_for_webhook_delivery=ready_for_webhook_delivery,
        ready_for_outbound_messages=ready_for_outbound_messages,
        low_quality_stop_new_users=low_quality_stop_new_users,
        quality_rating_snapshot=quality_rating_snapshot,
        active_conversation_count=active_conversation_count,
    )
    session.add(pool)
    session.flush()
    return pool


def test_phone_selection_prefers_existing_assignment(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-pool-existing", site_key="w2-pool-existing")
    auth_payload = _register_member(
        client,
        site_key="w2-pool-existing",
        phone="+8613900100001",
        display_name="Pool Existing",
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        assigned_pool = _seed_pool(
            session,
            account_id="acct-w2-pool-existing",
            site_id=site["id"],
            waba_id="waba-existing",
            phone_number_id="phone-existing-a",
            display_phone_number="15550000001",
            active_conversation_count=18,
        )
        _seed_pool(
            session,
            account_id="acct-w2-pool-existing",
            site_id=site["id"],
            waba_id="waba-existing",
            phone_number_id="phone-existing-b",
            display_phone_number="15550000002",
            weight=200,
            priority=50,
            active_conversation_count=1,
        )
        session.add(
            UserWhatsAppServiceAssignment(
                account_id="acct-w2-pool-existing",
                site_id=site["id"],
                user_id=user.id,
                wa_id="wa-existing-user",
                assigned_waba_id=assigned_pool.waba_id,
                assigned_phone_number_id=assigned_pool.phone_number_id,
                assigned_display_phone_number=assigned_pool.display_phone_number,
                assignment_source="bind",
                status="active",
            )
        )
        session.commit()

        service = WhatsAppPhoneSelectionService(session=session)
        selected = service.select_phone(
            account_id="acct-w2-pool-existing",
            site_id=site["id"],
            user_id=user.id,
            wa_id="wa-existing-user",
            prefer_existing_assignment=True,
        )

    assert selected.phone_number_id == "phone-existing-a"
    assert selected.display_phone_number == "15550000001"


def test_phone_selection_skips_low_quality_pool_for_new_user(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-pool-new", site_key="w2-pool-new")
    _register_member(
        client,
        site_key="w2-pool-new",
        phone="+8613900100002",
        display_name="Pool New",
    )

    with db_session_factory() as session:
        _seed_pool(
            session,
            account_id="acct-w2-pool-new",
            site_id=site["id"],
            waba_id="waba-new",
            phone_number_id="phone-low-quality",
            display_phone_number="15550000011",
            allow_new_users=False,
            only_existing_users=True,
            quality_rating_snapshot="LOW",
            active_conversation_count=0,
        )
        _seed_pool(
            session,
            account_id="acct-w2-pool-new",
            site_id=site["id"],
            waba_id="waba-new",
            phone_number_id="phone-healthy",
            display_phone_number="15550000012",
            weight=120,
            priority=10,
            quality_rating_snapshot="GREEN",
            active_conversation_count=2,
        )
        session.commit()

        service = WhatsAppPhoneSelectionService(session=session)
        selected = service.select_phone(
            account_id="acct-w2-pool-new",
            site_id=site["id"],
            user_id=None,
            wa_id=None,
            prefer_existing_assignment=False,
        )

    assert selected.phone_number_id == "phone-healthy"
    assert selected.display_phone_number == "15550000012"
