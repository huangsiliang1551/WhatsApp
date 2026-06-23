from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AppUser, MemberNotification, MemberProfile, Ticket
from tests.test_h5_member_auth import _create_site, _register_member


def _seed_member_notification(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    public_user_id: str,
    site_id: str,
    category: str,
    title: str,
    body_text: str,
    is_read: bool = False,
) -> str:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        member_profile = session.query(MemberProfile).filter(MemberProfile.user_id == user.id).one()
        notification = MemberNotification(
            account_id=account_id,
            user_id=user.id,
            member_profile_id=member_profile.id,
            site_id=site_id,
            category=category,
            title=title,
            body_text=body_text,
            is_read=is_read,
        )
        session.add(notification)
        session.commit()
        return notification.id


def _seed_help_ticket(
    db_session_factory: sessionmaker[Session],
    *,
    account_id: str,
    public_user_id: str,
    site_id: str,
) -> str:
    with db_session_factory() as session:
        user = session.query(AppUser).filter(AppUser.public_user_id == public_user_id).one()
        ticket = Ticket(
            account_id=account_id,
            ticket_no=f"TKT-{public_user_id[-8:].upper()}",
            user_id=user.id,
            site_id=site_id,
            ticket_type="help",
            status="open",
            title="Need help from member center",
            priority="normal",
        )
        session.add(ticket)
        session.commit()
        return ticket.id


def test_h5_member_messages_list_detail_and_mark_read_flow(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-messages", site_key="h5-messages")
    auth_payload = _register_member(
        client,
        site_key="h5-messages",
        phone="+8613900030303",
        display_name="Message Member",
    )

    first_message_id = _seed_member_notification(
        db_session_factory,
        account_id="acct-h5-messages",
        public_user_id=auth_payload["member"]["publicUserId"],
        site_id=site["id"],
        category="task",
        title="Task package dispatched",
        body_text="Your rookie package is waiting to be claimed.",
        is_read=False,
    )
    _seed_member_notification(
        db_session_factory,
        account_id="acct-h5-messages",
        public_user_id=auth_payload["member"]["publicUserId"],
        site_id=site["id"],
        category="wallet",
        title="Reward credited",
        body_text="Your reward has arrived in task balance.",
        is_read=False,
    )
    _seed_member_notification(
        db_session_factory,
        account_id="acct-h5-messages",
        public_user_id=auth_payload["member"]["publicUserId"],
        site_id=site["id"],
        category="system",
        title="Already read notice",
        body_text="This one should stay read.",
        is_read=True,
    )

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    assert home_response.json()["unreadMessageCount"] == 2

    list_response = client.get("/api/h5/messages")
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert len(items) == 3
    assert {item["category"] for item in items} == {"task", "wallet", "system"}

    detail_response = client.get(f"/api/h5/messages/{first_message_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["id"] == first_message_id
    assert detail["title"] == "Task package dispatched"
    assert detail["bodyText"] == "Your rookie package is waiting to be claimed."
    assert detail["isRead"] is False

    mark_read_response = client.post(f"/api/h5/messages/{first_message_id}/read")
    assert mark_read_response.status_code == 200, mark_read_response.text
    assert mark_read_response.json()["isRead"] is True
    assert mark_read_response.json()["readAt"] is not None

    home_after_read = client.get("/api/h5/member/home")
    assert home_after_read.status_code == 200, home_after_read.text
    assert home_after_read.json()["unreadMessageCount"] == 1


def test_h5_member_messages_are_member_scoped_and_do_not_mix_tickets(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    site = _create_site(client, account_id="acct-h5-message-scope", site_key="h5-message-scope")
    first_member = _register_member(
        client,
        site_key="h5-message-scope",
        phone="+8613900040404",
        display_name="Scoped Member A",
    )
    client.post("/api/h5/auth/logout")
    second_member = _register_member(
        client,
        site_key="h5-message-scope",
        phone="+8613900040405",
        display_name="Scoped Member B",
    )
    client.post("/api/h5/auth/logout")
    login_response = client.post(
        "/api/h5/auth/login",
        json={
            "site_key": "h5-message-scope",
            "phone": "+8613900040404",
            "password": "pass123456",
        },
    )
    assert login_response.status_code == 200, login_response.text

    member_a_message_id = _seed_member_notification(
        db_session_factory,
        account_id="acct-h5-message-scope",
        public_user_id=first_member["member"]["publicUserId"],
        site_id=site["id"],
        category="wallet",
        title="Member A wallet notice",
        body_text="Visible only to member A.",
        is_read=False,
    )
    member_b_message_id = _seed_member_notification(
        db_session_factory,
        account_id="acct-h5-message-scope",
        public_user_id=second_member["member"]["publicUserId"],
        site_id=site["id"],
        category="task",
        title="Member B task notice",
        body_text="Should stay hidden from member A.",
        is_read=False,
    )
    _seed_help_ticket(
        db_session_factory,
        account_id="acct-h5-message-scope",
        public_user_id=first_member["member"]["publicUserId"],
        site_id=site["id"],
    )

    list_response = client.get("/api/h5/messages")
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    assert [item["id"] for item in items] == [member_a_message_id]

    missing_detail = client.get(f"/api/h5/messages/{member_b_message_id}")
    assert missing_detail.status_code == 404, missing_detail.text

    read_all_response = client.post("/api/h5/messages/read-all")
    assert read_all_response.status_code == 200, read_all_response.text
    assert read_all_response.json()["updated"] == 1

    home_response = client.get("/api/h5/member/home")
    assert home_response.status_code == 200, home_response.text
    payload = home_response.json()
    assert payload["unreadMessageCount"] == 0
    assert payload["openTicketCount"] == 1

    with db_session_factory() as session:
        member_a_message = session.get(MemberNotification, member_a_message_id)
        member_b_message = session.get(MemberNotification, member_b_message_id)
        assert member_a_message is not None
        assert member_b_message is not None
        assert member_a_message.is_read is True
        assert member_b_message.is_read is False
