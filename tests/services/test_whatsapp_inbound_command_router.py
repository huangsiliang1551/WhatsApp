from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.models import AppUser, WhatsAppAutoBindInvite, WhatsAppIdentity
from app.services.whatsapp_auth_session_service import WhatsAppAuthSessionService
from app.services.whatsapp_inbound_command_router import WhatsAppInboundCommandRouter
from app.services.whatsapp_identity_service import WhatsAppIdentityService
from tests.services.test_whatsapp_phone_pool_service import _seed_pool
from tests.test_h5_member_auth import _create_site, _register_member


def test_bind_command_is_handled_before_ai(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-router-bind", site_key="w2-router-bind")
    auth_payload = _register_member(
        client,
        site_key="w2-router-bind",
        phone="+8613900103001",
        display_name="Router Bind",
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        _seed_pool(
            session,
            account_id="acct-w2-router-bind",
            site_id=site["id"],
            waba_id="waba-router-bind",
            phone_number_id="phone-router-bind",
            display_phone_number="15550000301",
        )
        session.commit()

        auth_service = WhatsAppAuthSessionService(session=session, settings=get_settings())
        auth_session = auth_service.start_bind_session(site_id=site["id"], user_id=user.id)
        router = WhatsAppInboundCommandRouter(session=session, settings=get_settings())
        result = router.try_handle_inbound(
            text=auth_session.command_text,
            wa_id="wa-router-bind",
            inbound_phone_number_id="phone-router-bind",
            inbound_waba_id="waba-router-bind",
            inbound_message_id="wamid-router-bind",
        )
        session.commit()

        identity = session.query(WhatsAppIdentity).filter(
            WhatsAppIdentity.wa_id == "wa-router-bind"
        ).one_or_none()

    assert result.action == "auth_command"
    assert result.handled is True
    assert result.should_enter_ai is False
    assert identity is not None
    assert identity.site_id == site["id"]


def test_unbound_normal_message_returns_binding_prompt_and_creates_invite(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-router-unbound", site_key="w2-router-unbound")
    _register_member(
        client,
        site_key="w2-router-unbound",
        phone="+8613900103002",
        display_name="Router Unbound",
    )

    with db_session_factory() as session:
        _seed_pool(
            session,
            account_id="acct-w2-router-unbound",
            site_id=site["id"],
            waba_id="waba-router-unbound",
            phone_number_id="phone-router-unbound",
            display_phone_number="15550000302",
        )
        session.commit()

        router = WhatsAppInboundCommandRouter(session=session, settings=get_settings())
        result = router.try_handle_inbound(
            text="hello",
            wa_id="wa-router-unbound",
            inbound_phone_number_id="phone-router-unbound",
            inbound_waba_id="waba-router-unbound",
            inbound_message_id="wamid-router-unbound",
        )
        session.commit()

        invite = session.query(WhatsAppAutoBindInvite).filter(
            WhatsAppAutoBindInvite.wa_id == "wa-router-unbound"
        ).one_or_none()

    assert result.action == "binding_prompt"
    assert result.handled is True
    assert result.should_enter_ai is False
    assert result.invite_link is not None
    assert invite is not None
    assert invite.site_id == site["id"]


def test_bound_message_to_other_site_pool_is_rejected(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site_a = _create_site(client, account_id="acct-w2-router-cross", site_key="w2-router-cross-a")
    site_b = _create_site(client, account_id="acct-w2-router-cross", site_key="w2-router-cross-b")
    auth_payload = _register_member(
        client,
        site_key="w2-router-cross-a",
        phone="+8613900103003",
        display_name="Router Cross",
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        pool_a = _seed_pool(
            session,
            account_id="acct-w2-router-cross",
            site_id=site_a["id"],
            waba_id="waba-router-cross-a",
            phone_number_id="phone-router-cross-a",
            display_phone_number="15550000303",
        )
        _seed_pool(
            session,
            account_id="acct-w2-router-cross",
            site_id=site_b["id"],
            waba_id="waba-router-cross-b",
            phone_number_id="phone-router-cross-b",
            display_phone_number="15550000304",
        )
        WhatsAppIdentityService(session=session).bind_identity(
            account_id="acct-w2-router-cross",
            site_id=site_a["id"],
            user_id=user.id,
            wa_id="wa-router-cross",
            assigned_waba_id=pool_a.waba_id,
            assigned_phone_number_id=pool_a.phone_number_id,
            assigned_display_phone_number=pool_a.display_phone_number,
        )
        session.commit()

        router = WhatsAppInboundCommandRouter(session=session, settings=get_settings())
        result = router.try_handle_inbound(
            text="need help",
            wa_id="wa-router-cross",
            inbound_phone_number_id="phone-router-cross-b",
            inbound_waba_id="waba-router-cross-b",
            inbound_message_id="wamid-router-cross",
        )

    assert result.action == "reject_cross_site"
    assert result.handled is True
    assert result.should_enter_ai is False


def test_bound_message_in_same_site_pool_can_enter_ai(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-router-bound", site_key="w2-router-bound")
    auth_payload = _register_member(
        client,
        site_key="w2-router-bound",
        phone="+8613900103004",
        display_name="Router Bound",
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        pool = _seed_pool(
            session,
            account_id="acct-w2-router-bound",
            site_id=site["id"],
            waba_id="waba-router-bound",
            phone_number_id="phone-router-bound",
            display_phone_number="15550000305",
        )
        WhatsAppIdentityService(session=session).bind_identity(
            account_id="acct-w2-router-bound",
            site_id=site["id"],
            user_id=user.id,
            wa_id="wa-router-bound",
            assigned_waba_id=pool.waba_id,
            assigned_phone_number_id=pool.phone_number_id,
            assigned_display_phone_number=pool.display_phone_number,
        )
        session.commit()

        router = WhatsAppInboundCommandRouter(session=session, settings=get_settings())
        result = router.try_handle_inbound(
            text="hello bound user",
            wa_id="wa-router-bound",
            inbound_phone_number_id="phone-router-bound",
            inbound_waba_id="waba-router-bound",
            inbound_message_id="wamid-router-bound",
        )

    assert result.action == "bound_message"
    assert result.handled is False
    assert result.should_enter_ai is True
    assert result.reply_phone_number_id == "phone-router-bound"


def test_bound_message_to_other_phone_in_same_site_pool_keeps_same_user_context(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-router-merge", site_key="w2-router-merge")
    auth_payload = _register_member(
        client,
        site_key="w2-router-merge",
        phone="+8613900103005",
        display_name="Router Merge",
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        user_id = user.id
        assigned_pool = _seed_pool(
            session,
            account_id="acct-w2-router-merge",
            site_id=site["id"],
            waba_id="waba-router-merge-a",
            phone_number_id="phone-router-merge-a",
            display_phone_number="15550000306",
        )
        _seed_pool(
            session,
            account_id="acct-w2-router-merge",
            site_id=site["id"],
            waba_id="waba-router-merge-b",
            phone_number_id="phone-router-merge-b",
            display_phone_number="15550000307",
        )
        WhatsAppIdentityService(session=session).bind_identity(
            account_id="acct-w2-router-merge",
            site_id=site["id"],
            user_id=user.id,
            wa_id="wa-router-merge",
            assigned_waba_id=assigned_pool.waba_id,
            assigned_phone_number_id=assigned_pool.phone_number_id,
            assigned_display_phone_number=assigned_pool.display_phone_number,
        )
        session.commit()

        router = WhatsAppInboundCommandRouter(session=session, settings=get_settings())
        result = router.try_handle_inbound(
            text="same site different number",
            wa_id="wa-router-merge",
            inbound_phone_number_id="phone-router-merge-b",
            inbound_waba_id="waba-router-merge-b",
            inbound_message_id="wamid-router-merge",
        )

    assert result.action == "bound_message"
    assert result.should_enter_ai is True
    assert result.reply_phone_number_id == "phone-router-merge-b"
    assert result.reply_waba_id == "waba-router-merge-b"
    assert result.conversation_scope_key == f"acct-w2-router-merge:{user_id}:whatsapp"
    assert result.message_routing_metadata == {
        "site_id": site["id"],
        "user_id": user_id,
        "wa_id": "wa-router-merge",
        "inbound_phone_number_id": "phone-router-merge-b",
        "inbound_waba_id": "waba-router-merge-b",
        "reply_phone_number_id": "phone-router-merge-b",
        "reply_waba_id": "waba-router-merge-b",
    }
