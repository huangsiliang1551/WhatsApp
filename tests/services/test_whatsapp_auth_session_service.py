from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.models import AppUser, H5Site, UserWhatsAppServiceAssignment, WhatsAppIdentity
from app.services.whatsapp_auth_session_service import WhatsAppAuthSessionService
from app.services.whatsapp_identity_service import WhatsAppBindingConflictError
from tests.services.test_whatsapp_phone_pool_service import _seed_pool
from tests.test_h5_member_auth import _create_site, _register_member


def test_start_bind_reuses_pending_session_for_same_user(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-auth-bind", site_key="w2-auth-bind")
    auth_payload = _register_member(
        client,
        site_key="w2-auth-bind",
        phone="+8613900101001",
        display_name="Bind Session",
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        _seed_pool(
            session,
            account_id="acct-w2-auth-bind",
            site_id=site["id"],
            waba_id="waba-bind",
            phone_number_id="phone-bind-1",
            display_phone_number="15550000101",
        )
        session.commit()

        service = WhatsAppAuthSessionService(session=session, settings=get_settings())
        first = service.start_bind_session(site_id=site["id"], user_id=user.id)
        second = service.start_bind_session(site_id=site["id"], user_id=user.id)

    assert first.id == second.id
    assert first.command_text == second.command_text
    assert "BIND " in first.command_text
    assert first.selected_phone_number_id == "phone-bind-1"


def test_consume_bind_command_creates_identity_and_assignment(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-auth-consume", site_key="w2-auth-consume")
    auth_payload = _register_member(
        client,
        site_key="w2-auth-consume",
        phone="+8613900101002",
        display_name="Consume Bind",
    )

    with db_session_factory() as session:
        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        _seed_pool(
            session,
            account_id="acct-w2-auth-consume",
            site_id=site["id"],
            waba_id="waba-consume",
            phone_number_id="phone-consume-1",
            display_phone_number="15550000102",
        )
        session.commit()

        service = WhatsAppAuthSessionService(session=session, settings=get_settings())
        auth_session = service.start_bind_session(site_id=site["id"], user_id=user.id)
        token = auth_session.command_text.split(" ", 1)[1]
        completed = service.consume_auth_command(
            command_text=f"BIND {token}",
            wa_id="wa-bind-success",
            inbound_phone_number_id="phone-consume-1",
            inbound_waba_id="waba-consume",
            inbound_message_id="wamid-bind-success",
        )

        identity = session.query(WhatsAppIdentity).filter(
            WhatsAppIdentity.wa_id == "wa-bind-success"
        ).one_or_none()
        assignment = session.query(UserWhatsAppServiceAssignment).filter(
            UserWhatsAppServiceAssignment.wa_id == "wa-bind-success"
        ).one_or_none()

    assert completed.status == "confirmed"
    assert identity is not None
    assert identity.site_id == site["id"]
    assert assignment is not None
    assert assignment.assigned_phone_number_id == "phone-consume-1"


def test_consume_bind_command_rejects_cross_site_wa_id_conflict(
    client,
    db_session_factory: sessionmaker[Session],
) -> None:
    site_a = _create_site(client, account_id="acct-w2-auth-conflict", site_key="w2-auth-conflict-a")
    site_b = _create_site(client, account_id="acct-w2-auth-conflict", site_key="w2-auth-conflict-b")
    auth_payload_a = _register_member(
        client,
        site_key="w2-auth-conflict-a",
        phone="+8613900101003",
        display_name="Conflict A",
    )
    auth_payload_b = _register_member(
        client,
        site_key="w2-auth-conflict-b",
        phone="+8613900101004",
        display_name="Conflict B",
    )

    with db_session_factory() as session:
        user_a = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload_a["member"]["publicUserId"]
        ).one()
        user_b = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload_b["member"]["publicUserId"]
        ).one()
        site_a_model = session.query(H5Site).filter(H5Site.id == site_a["id"]).one()
        site_b_model = session.query(H5Site).filter(H5Site.id == site_b["id"]).one()
        _seed_pool(
            session,
            account_id="acct-w2-auth-conflict",
            site_id=site_a_model.id,
            waba_id="waba-conflict-a",
            phone_number_id="phone-conflict-a",
            display_phone_number="15550000103",
        )
        _seed_pool(
            session,
            account_id="acct-w2-auth-conflict",
            site_id=site_b_model.id,
            waba_id="waba-conflict-b",
            phone_number_id="phone-conflict-b",
            display_phone_number="15550000104",
        )
        session.add(
            WhatsAppIdentity(
                wa_id="wa-global-conflict",
                account_id="acct-w2-auth-conflict",
                site_id=site_a_model.id,
                user_id=user_a.id,
                binding_status="bound",
                bound_at=site_a_model.created_at,
            )
        )
        session.commit()

        service = WhatsAppAuthSessionService(session=session, settings=get_settings())
        auth_session = service.start_bind_session(site_id=site_b_model.id, user_id=user_b.id)
        token = auth_session.command_text.split(" ", 1)[1]

        try:
            service.consume_auth_command(
                command_text=f"BIND {token}",
                wa_id="wa-global-conflict",
                inbound_phone_number_id="phone-conflict-b",
                inbound_waba_id="waba-conflict-b",
                inbound_message_id="wamid-bind-conflict",
            )
        except WhatsAppBindingConflictError as exc:
            assert exc.code == "wa_id_already_bound"
        else:
            raise AssertionError("expected WhatsAppBindingConflictError")
