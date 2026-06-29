from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import get_settings
from app.db.models import H5Site, WhatsAppAuthSession, WhatsAppAutoBindInvite, WhatsAppIdentity
from app.services.whatsapp_auto_bind_invite_service import WhatsAppAutoBindInviteService
from tests.services.test_whatsapp_phone_pool_service import _seed_pool
from tests.test_h5_member_auth import _create_site, _register_member


def test_h5_whatsapp_login_start_returns_session_and_wa_link(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-h5-login", site_key="w2-h5-login")
    _register_member(
        client,
        site_key="w2-h5-login",
        phone="+8613900102001",
        display_name="H5 Login",
    )

    with db_session_factory() as session:
        _seed_pool(
            session,
            account_id="acct-w2-h5-login",
            site_id=site["id"],
            waba_id="waba-h5-login",
            phone_number_id="phone-h5-login",
            display_phone_number="15550000201",
        )
        session.commit()

    response = client.post(
        "/api/h5/auth/whatsapp/start",
        json={"siteKey": "w2-h5-login", "sessionType": "login"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sessionType"] == "login"
    assert payload["status"] == "pending"
    assert payload["selectedPhoneNumberId"] == "phone-h5-login"
    assert payload["waLink"].startswith("https://wa.me/15550000201?text=LOGIN%20")
    assert payload["commandText"].startswith("LOGIN ")


def test_h5_whatsapp_bind_start_requires_auth_and_reuses_pending_session(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-h5-bind", site_key="w2-h5-bind")
    _register_member(
        client,
        site_key="w2-h5-bind",
        phone="+8613900102002",
        display_name="H5 Bind",
    )

    with db_session_factory() as session:
        _seed_pool(
            session,
            account_id="acct-w2-h5-bind",
            site_id=site["id"],
            waba_id="waba-h5-bind",
            phone_number_id="phone-h5-bind",
            display_phone_number="15550000202",
        )
        session.commit()

    first = client.post("/api/h5/auth/whatsapp/start", json={"sessionType": "bind"})
    assert first.status_code == 200, first.text
    second = client.post("/api/h5/auth/whatsapp/start", json={"sessionType": "bind"})
    assert second.status_code == 200, second.text

    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["id"] == second_payload["id"]
    assert first_payload["commandText"] == second_payload["commandText"]
    assert first_payload["commandText"].startswith("BIND ")

    status_response = client.get(f"/api/h5/auth/whatsapp/sessions/{first_payload['id']}")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["id"] == first_payload["id"]


def test_h5_whatsapp_login_start_rejects_unknown_site(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/h5/auth/whatsapp/start",
        json={"siteKey": "missing-site", "sessionType": "login"},
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "site_not_found"


def test_h5_whatsapp_session_status_returns_confirmed_after_bind_consume(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-h5-confirm", site_key="w2-h5-confirm")
    _register_member(
        client,
        site_key="w2-h5-confirm",
        phone="+8613900102003",
        display_name="H5 Confirm",
    )

    with db_session_factory() as session:
        _seed_pool(
            session,
            account_id="acct-w2-h5-confirm",
            site_id=site["id"],
            waba_id="waba-h5-confirm",
            phone_number_id="phone-h5-confirm",
            display_phone_number="15550000203",
        )
        session.commit()

    start_response = client.post("/api/h5/auth/whatsapp/start", json={"sessionType": "bind"})
    assert start_response.status_code == 200, start_response.text
    session_payload = start_response.json()
    token = session_payload["commandText"].split(" ", 1)[1]

    consume_response = client.post(
        f"/api/h5/auth/whatsapp/sessions/{session_payload['id']}/consume",
        json={
            "commandText": f"BIND {token}",
            "waId": "wa-h5-confirmed",
            "inboundPhoneNumberId": "phone-h5-confirm",
            "inboundWabaId": "waba-h5-confirm",
            "inboundMessageId": "wamid-h5-confirm",
        },
    )
    assert consume_response.status_code == 200, consume_response.text

    status_response = client.get(f"/api/h5/auth/whatsapp/sessions/{session_payload['id']}")
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["status"] == "confirmed"

    with db_session_factory() as session:
        saved = session.query(WhatsAppAuthSession).filter(
            WhatsAppAuthSession.id == session_payload["id"]
        ).one()
        assert saved.status == "confirmed"


def test_h5_whatsapp_auto_bind_consume_binds_current_member(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-w2-h5-auto-bind", site_key="w2-h5-auto-bind")
    auth_payload = _register_member(
        client,
        site_key="w2-h5-auto-bind",
        phone="+8613900102004",
        display_name="H5 Auto Bind",
    )

    with db_session_factory() as session:
        _seed_pool(
            session,
            account_id="acct-w2-h5-auto-bind",
            site_id=site["id"],
            waba_id="waba-h5-auto-bind",
            phone_number_id="phone-h5-auto-bind",
            display_phone_number="15550000204",
        )
        invite = WhatsAppAutoBindInviteService(
            session=session,
            settings=get_settings(),
        ).create_invite(
            account_id="acct-w2-h5-auto-bind",
            site_id=site["id"],
            wa_id="wa-h5-auto-bind",
            inbound_phone_number_id="phone-h5-auto-bind",
            inbound_waba_id="waba-h5-auto-bind",
            inbound_message_id="wamid-h5-auto-bind",
        )
        token = invite.metadata_json["plain_token"]
        session.commit()

    response = client.post(
        "/api/h5/auth/whatsapp/auto-bind/consume",
        json={"token": token},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "bound"
    assert payload["waId"] == "wa-h5-auto-bind"
    assert payload["siteId"] == site["id"]
    assert payload["publicUserId"] == auth_payload["member"]["publicUserId"]

    with db_session_factory() as session:
        invite = session.query(WhatsAppAutoBindInvite).filter(
            WhatsAppAutoBindInvite.wa_id == "wa-h5-auto-bind"
        ).one()
        identity = session.query(WhatsAppIdentity).filter(
            WhatsAppIdentity.wa_id == "wa-h5-auto-bind"
        ).one_or_none()
        assert invite.status == "consumed"
        assert identity is not None
        assert identity.site_id == site["id"]


def test_h5_whatsapp_auto_bind_consume_rejects_cross_site_wa_conflict(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site_a = _create_site(client, account_id="acct-w2-h5-auto-conflict", site_key="w2-h5-auto-conflict-a")
    site_b = _create_site(client, account_id="acct-w2-h5-auto-conflict", site_key="w2-h5-auto-conflict-b")
    _register_member(
        client,
        site_key="w2-h5-auto-conflict-b",
        phone="+8613900102005",
        display_name="H5 Auto Conflict B",
    )
    client.post("/api/h5/auth/logout")
    auth_payload_a = _register_member(
        client,
        site_key="w2-h5-auto-conflict-a",
        phone="+8613900102006",
        display_name="H5 Auto Conflict A",
    )
    client.post("/api/h5/auth/logout")
    _register_member(
        client,
        site_key="w2-h5-auto-conflict-b",
        username="auto-conflict-b-user",
        display_name="H5 Auto Conflict Current",
    )

    with db_session_factory() as session:
        _seed_pool(
            session,
            account_id="acct-w2-h5-auto-conflict",
            site_id=site_a["id"],
            waba_id="waba-h5-auto-conflict-a",
            phone_number_id="phone-h5-auto-conflict-a",
            display_phone_number="15550000205",
        )
        _seed_pool(
            session,
            account_id="acct-w2-h5-auto-conflict",
            site_id=site_b["id"],
            waba_id="waba-h5-auto-conflict-b",
            phone_number_id="phone-h5-auto-conflict-b",
            display_phone_number="15550000206",
        )
        invite = WhatsAppAutoBindInviteService(
            session=session,
            settings=get_settings(),
        ).create_invite(
            account_id="acct-w2-h5-auto-conflict",
            site_id=site_b["id"],
            wa_id="wa-h5-auto-conflict",
            inbound_phone_number_id="phone-h5-auto-conflict-b",
            inbound_waba_id="waba-h5-auto-conflict-b",
            inbound_message_id="wamid-h5-auto-conflict-b",
        )
        token = invite.metadata_json["plain_token"]
        owner = session.query(WhatsAppIdentity).filter(
            WhatsAppIdentity.wa_id == "wa-h5-auto-conflict"
        ).one_or_none()
        if owner is None:
            from app.db.models import AppUser
            user_a = session.query(AppUser).filter(
                AppUser.public_user_id == auth_payload_a["member"]["publicUserId"]
            ).one()
            session.add(
                WhatsAppIdentity(
                    wa_id="wa-h5-auto-conflict",
                    account_id="acct-w2-h5-auto-conflict",
                    site_id=site_a["id"],
                    user_id=user_a.id,
                    binding_status="bound",
                )
            )
        session.commit()

    response = client.post(
        "/api/h5/auth/whatsapp/auto-bind/consume",
        json={"token": token},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "wa_id_already_bound"
