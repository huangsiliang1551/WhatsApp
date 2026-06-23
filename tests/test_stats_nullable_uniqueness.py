from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Account, Conversation, TemplateDailyStat, WhatsAppConversationStat, WhatsAppDailyStat


def _open_session(db_session_factory: sessionmaker[Session]) -> Session:
    return db_session_factory()


def _create_account(session: Session, account_id: str) -> Account:
    account = Account(
        account_id=account_id,
        display_name=f"Stats test {account_id}",
        provider_type="whatsapp",
    )
    session.add(account)
    session.commit()
    return account


def _create_conversation(session: Session, account_id: str, conversation_id: str) -> Conversation:
    conversation = Conversation(
        id=conversation_id,
        account_id=account_id,
        external_conversation_id=f"external-{conversation_id}",
        customer_id=f"customer-{conversation_id}",
    )
    session.add(conversation)
    session.commit()
    return conversation


def test_template_daily_stats_reject_duplicate_scope_when_nullable_dimensions_are_null(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = _open_session(db_session_factory)
    try:
        account_id = "stats-null-template-account"
        _create_account(session, account_id)

        first_row = TemplateDailyStat(
            date=date(2026, 6, 8),
            account_id=account_id,
            template_id=None,
            waba_id=None,
            phone_number_id=None,
            template_name="order_update",
            template_category="UTILITY",
            template_language="en_US",
        )
        duplicate_row = TemplateDailyStat(
            date=date(2026, 6, 8),
            account_id=account_id,
            template_id=None,
            waba_id=None,
            phone_number_id=None,
            template_name="order_update",
            template_category="UTILITY",
            template_language="en_US",
        )

        session.add(first_row)
        session.commit()
        session.add(duplicate_row)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_whatsapp_daily_stats_reject_duplicate_scope_when_nullable_dimensions_are_null(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = _open_session(db_session_factory)
    try:
        account_id = "stats-null-whatsapp-account"
        _create_account(session, account_id)

        first_row = WhatsAppDailyStat(
            date=date(2026, 6, 8),
            account_id=account_id,
            waba_id=None,
            phone_number_id=None,
            conversation_origin_type=None,
            conversation_category=None,
            pricing_model=None,
            billable=False,
            hour_bucket=None,
        )
        duplicate_row = WhatsAppDailyStat(
            date=date(2026, 6, 8),
            account_id=account_id,
            waba_id=None,
            phone_number_id=None,
            conversation_origin_type=None,
            conversation_category=None,
            pricing_model=None,
            billable=False,
            hour_bucket=None,
        )

        session.add(first_row)
        session.commit()
        session.add(duplicate_row)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_whatsapp_conversation_stats_reject_duplicate_scope_when_nullable_dimensions_are_null(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = _open_session(db_session_factory)
    try:
        account_id = "stats-null-conversation-account"
        conversation_id = "stats-null-conversation"
        _create_account(session, account_id)
        _create_conversation(session, account_id, conversation_id)

        first_row = WhatsAppConversationStat(
            date=date(2026, 6, 8),
            account_id=account_id,
            conversation_id=conversation_id,
            customer_id="customer-stats-null-conversation",
            waba_id=None,
            phone_number_id=None,
            conversation_origin_type=None,
            conversation_category=None,
            pricing_model=None,
            billable=False,
            billable_key=None,
            hour_bucket=None,
        )
        duplicate_row = WhatsAppConversationStat(
            date=date(2026, 6, 8),
            account_id=account_id,
            conversation_id=conversation_id,
            customer_id="customer-stats-null-conversation",
            waba_id=None,
            phone_number_id=None,
            conversation_origin_type=None,
            conversation_category=None,
            pricing_model=None,
            billable=False,
            billable_key=None,
            hour_bucket=None,
        )

        session.add(first_row)
        session.commit()
        session.add(duplicate_row)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()
