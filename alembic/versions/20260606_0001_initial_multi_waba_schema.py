"""initial multi waba schema

Revision ID: 20260606_0001
Revises:
Create Date: 2026-06-06 18:50:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260606_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.String(length=128), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="offline"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "meta_business_portfolios",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("meta_business_portfolio_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("meta_business_portfolio_id"),
    )
    op.create_index("ix_meta_business_portfolios_meta_business_portfolio_id", "meta_business_portfolios", ["meta_business_portfolio_id"])
    op.create_table(
        "whatsapp_business_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36)),
        sa.Column("waba_id", sa.String(length=128), nullable=False),
        sa.Column("onboarding_mode", sa.String(length=32), nullable=False),
        sa.Column("token_source", sa.String(length=32), nullable=False),
        sa.Column("access_token", sa.Text()),
        sa.Column("verify_token", sa.String(length=255)),
        sa.Column("app_secret", sa.String(length=255)),
        sa.Column("webhook_subscribed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["meta_business_portfolios.id"]),
        sa.UniqueConstraint("waba_id"),
        sa.UniqueConstraint("account_id", "waba_id", name="uq_whatsapp_business_accounts_account_waba"),
    )
    op.create_index("ix_whatsapp_business_accounts_account_id", "whatsapp_business_accounts", ["account_id"])
    op.create_index("ix_whatsapp_business_accounts_waba_id", "whatsapp_business_accounts", ["waba_id"])
    op.create_table(
        "embedded_signup_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("waba_account_id", sa.String(length=36)),
        sa.Column("redirect_uri", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["waba_account_id"], ["whatsapp_business_accounts.id"]),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_embedded_signup_sessions_account_id", "embedded_signup_sessions", ["account_id"])
    op.create_index("ix_embedded_signup_sessions_session_id", "embedded_signup_sessions", ["session_id"])
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("waba_account_id", sa.String(length=36), nullable=False),
        sa.Column("callback_url", sa.String(length=1024), nullable=False),
        sa.Column("verify_token", sa.String(length=255)),
        sa.Column("app_id", sa.String(length=128)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("subscribed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["waba_account_id"], ["whatsapp_business_accounts.id"]),
    )
    op.create_index("ix_webhook_subscriptions_waba_account_id", "webhook_subscriptions", ["waba_account_id"])
    op.create_table(
        "whatsapp_phone_numbers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("waba_account_id", sa.String(length=36), nullable=False),
        sa.Column("phone_number_id", sa.String(length=128), nullable=False),
        sa.Column("display_phone_number", sa.String(length=64), nullable=False),
        sa.Column("verified_name", sa.String(length=255)),
        sa.Column("quality_rating", sa.String(length=16), nullable=False, server_default="UNKNOWN"),
        sa.Column("is_registered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["waba_account_id"], ["whatsapp_business_accounts.id"]),
        sa.UniqueConstraint("phone_number_id"),
    )
    op.create_index("ix_whatsapp_phone_numbers_waba_account_id", "whatsapp_phone_numbers", ["waba_account_id"])
    op.create_index("ix_whatsapp_phone_numbers_phone_number_id", "whatsapp_phone_numbers", ["phone_number_id"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("external_conversation_id", sa.String(length=128), nullable=False),
        sa.Column("phone_number_id", sa.String(length=36)),
        sa.Column("customer_id", sa.String(length=128), nullable=False),
        sa.Column("customer_language", sa.String(length=32), nullable=False, server_default="und"),
        sa.Column("customer_language_source", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("management_mode", sa.String(length=32), nullable=False, server_default="ai_managed"),
        sa.Column("assigned_agent_id", sa.String(length=36)),
        sa.Column("last_message_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["phone_number_id"], ["whatsapp_phone_numbers.id"]),
        sa.UniqueConstraint("account_id", "external_conversation_id", name="uq_conversations_account_external_id"),
    )
    op.create_index("ix_conversations_account_id", "conversations", ["account_id"])
    op.create_index("ix_conversations_customer_id", "conversations", ["customer_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128)),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128)),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128)),
        sa.Column("payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
    )
    op.create_index("ix_audit_logs_account_id", "audit_logs", ["account_id"])
    op.create_table(
        "handover_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("triggered_by_type", sa.String(length=32), nullable=False),
        sa.Column("triggered_by_id", sa.String(length=128)),
        sa.Column("from_mode", sa.String(length=32)),
        sa.Column("to_mode", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
    )
    op.create_index("ix_handover_logs_account_id", "handover_logs", ["account_id"])
    op.create_index("ix_handover_logs_conversation_id", "handover_logs", ["conversation_id"])
    op.create_table(
        "message_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("waba_account_id", sa.String(length=36)),
        sa.Column("meta_template_id", sa.String(length=255)),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("components", sa.JSON()),
        sa.Column("rejected_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["waba_account_id"], ["whatsapp_business_accounts.id"]),
        sa.UniqueConstraint("meta_template_id"),
    )
    op.create_index("ix_message_templates_account_id", "message_templates", ["account_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255)),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("language_code", sa.String(length=32)),
        sa.Column("translated_text", sa.Text()),
        sa.Column("translated_language_code", sa.String(length=32)),
        sa.Column("sender_id", sa.String(length=128)),
        sa.Column("recipient_id", sa.String(length=128)),
        sa.Column("content_text", sa.Text()),
        sa.Column("payload", sa.JSON()),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sent_by_agent_id", sa.String(length=36)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["sent_by_agent_id"], ["agents.id"]),
        sa.UniqueConstraint("provider_message_id"),
    )
    op.create_index("ix_messages_account_id", "messages", ["account_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table(
        "message_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.String(length=36)),
        sa.Column("message_id", sa.String(length=36)),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
    )
    op.create_index("ix_message_events_account_id", "message_events", ["account_id"])
    op.create_table(
        "template_send_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=36)),
        sa.Column("conversation_id", sa.String(length=36)),
        sa.Column("wa_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("error_code", sa.String(length=64)),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"]),
    )
    op.create_index("ix_template_send_logs_account_id", "template_send_logs", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_template_send_logs_account_id", table_name="template_send_logs")
    op.drop_table("template_send_logs")
    op.drop_index("ix_message_events_account_id", table_name="message_events")
    op.drop_table("message_events")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_messages_account_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_message_templates_account_id", table_name="message_templates")
    op.drop_table("message_templates")
    op.drop_index("ix_handover_logs_conversation_id", table_name="handover_logs")
    op.drop_index("ix_handover_logs_account_id", table_name="handover_logs")
    op.drop_table("handover_logs")
    op.drop_index("ix_audit_logs_account_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_conversations_customer_id", table_name="conversations")
    op.drop_index("ix_conversations_account_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_whatsapp_phone_numbers_phone_number_id", table_name="whatsapp_phone_numbers")
    op.drop_index("ix_whatsapp_phone_numbers_waba_account_id", table_name="whatsapp_phone_numbers")
    op.drop_table("whatsapp_phone_numbers")
    op.drop_index("ix_webhook_subscriptions_waba_account_id", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
    op.drop_index("ix_embedded_signup_sessions_session_id", table_name="embedded_signup_sessions")
    op.drop_index("ix_embedded_signup_sessions_account_id", table_name="embedded_signup_sessions")
    op.drop_table("embedded_signup_sessions")
    op.drop_index("ix_whatsapp_business_accounts_waba_id", table_name="whatsapp_business_accounts")
    op.drop_index("ix_whatsapp_business_accounts_account_id", table_name="whatsapp_business_accounts")
    op.drop_table("whatsapp_business_accounts")
    op.drop_index("ix_meta_business_portfolios_meta_business_portfolio_id", table_name="meta_business_portfolios")
    op.drop_table("meta_business_portfolios")
    op.drop_table("agents")
    op.drop_table("system_settings")
    op.drop_table("accounts")
