from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, MemberWhatsAppBindingRequest
from tests.test_h5_member_auth import _create_site, _register_member


def test_h5_whatsapp_binding_placeholder_contract_and_start_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_site(client, account_id="acct-h5-whatsapp", site_key="h5-whatsapp")
    auth_payload = _register_member(
        client,
        site_key="h5-whatsapp",
        phone="+8613900088001",
        display_name="WhatsApp Member",
    )

    binding_response = client.get("/api/h5/whatsapp-binding")
    assert binding_response.status_code == 200, binding_response.text
    binding_payload = binding_response.json()
    assert binding_payload["isBound"] is False
    assert binding_payload["bindingStatus"] == "not_started"
    assert binding_payload["requestId"] is None
    assert binding_payload["phoneNumber"] is None
    assert binding_payload["requestedAt"] is None
    assert binding_payload["startCount"] == 0
    assert binding_payload["lastUpdatedAt"] is None

    start_response = client.post("/api/h5/whatsapp-binding/start")
    assert start_response.status_code == 200, start_response.text
    started_payload = start_response.json()
    assert started_payload["isBound"] is False
    assert started_payload["bindingStatus"] == "pending"
    assert started_payload["requestId"] is not None
    assert started_payload["phoneNumber"] is None
    assert started_payload["requestedAt"] is not None
    assert started_payload["startCount"] == 1
    assert started_payload["lastUpdatedAt"] is not None

    with db_session_factory() as session:
        binding_request = session.query(MemberWhatsAppBindingRequest).filter(
            MemberWhatsAppBindingRequest.account_id == "acct-h5-whatsapp",
            MemberWhatsAppBindingRequest.user_id == session.query(AppUser).filter(
                AppUser.public_user_id == auth_payload["member"]["publicUserId"]
            ).one().id,
        ).one()
        assert binding_request.status == "pending"
        assert binding_request.requested_phone_number == "+8613900088001"
        assert binding_request.start_count == 1
        assert binding_request.last_started_at is not None

        user = session.query(AppUser).filter(
            AppUser.public_user_id == auth_payload["member"]["publicUserId"]
        ).one()
        user.has_whatsapp = True
        session.add(user)
        session.commit()

    rebound_response = client.get("/api/h5/whatsapp-binding")
    assert rebound_response.status_code == 200, rebound_response.text
    rebound_payload = rebound_response.json()
    assert rebound_payload["isBound"] is True
    assert rebound_payload["bindingStatus"] == "bound"
    assert rebound_payload["requestId"] == started_payload["requestId"]
    assert rebound_payload["phoneNumber"] == "+8613900088001"
    assert rebound_payload["requestedAt"] == started_payload["requestedAt"]
    assert rebound_payload["startCount"] == 1
    assert rebound_payload["lastUpdatedAt"] is not None

    with db_session_factory() as session:
        synced_request = session.query(MemberWhatsAppBindingRequest).filter(
            MemberWhatsAppBindingRequest.id == started_payload["requestId"]
        ).one()
        assert synced_request.status == "bound"
        assert synced_request.bound_at is not None


def test_h5_whatsapp_binding_requires_member_authentication(client: TestClient) -> None:
    response = client.get("/api/h5/whatsapp-binding")
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "H5 member authentication is required."

    start_response = client.post("/api/h5/whatsapp-binding/start")
    assert start_response.status_code == 401, start_response.text
    assert start_response.json()["detail"] == "H5 member authentication is required."


def test_h5_whatsapp_binding_start_reuses_existing_request_scope(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    _create_site(client, account_id="acct-h5-whatsapp-restart", site_key="h5-whatsapp-restart")
    _register_member(
        client,
        site_key="h5-whatsapp-restart",
        phone="+8613900088002",
        display_name="WhatsApp Restart Member",
    )

    first_start = client.post("/api/h5/whatsapp-binding/start")
    assert first_start.status_code == 200, first_start.text
    first_payload = first_start.json()
    assert first_payload["bindingStatus"] == "pending"
    assert first_payload["startCount"] == 1

    second_start = client.post("/api/h5/whatsapp-binding/start")
    assert second_start.status_code == 200, second_start.text
    second_payload = second_start.json()
    assert second_payload["requestId"] == first_payload["requestId"]
    assert second_payload["bindingStatus"] == "pending"
    assert second_payload["startCount"] == 2

    with db_session_factory() as session:
        requests = session.query(MemberWhatsAppBindingRequest).filter(
            MemberWhatsAppBindingRequest.account_id == "acct-h5-whatsapp-restart"
        ).all()
        assert len(requests) == 1
        assert requests[0].start_count == 2
