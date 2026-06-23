"""add finance payment and billing tables

Revision ID: 20260618_0100
Revises: 20260619_0201
Create Date: 2026-06-18 22:50:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "20260618_0100"
down_revision = "20260619_0201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── A1: ai_usage_records ──
    op.create_table(
        "ai_usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), nullable=True),
        sa.Column("site_id", sa.String(36), nullable=True),
        sa.Column("conversation_id", sa.String(36), nullable=True),
        sa.Column("provider_name", sa.String(64), nullable=True),
        sa.Column("message_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("cost", sa.Numeric(10, 4), server_default="0", nullable=False),
        sa.Column("billing_month", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── A2: translation_usage_records ──
    op.create_table(
        "translation_usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), nullable=True),
        sa.Column("site_id", sa.String(36), nullable=True),
        sa.Column("translation_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("cost", sa.Numeric(10, 4), server_default="0", nullable=False),
        sa.Column("billing_month", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── A3: ai_provider_rates ──
    op.create_table(
        "ai_provider_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_name", sa.String(64), nullable=False),
        sa.Column("cost_per_message", sa.Numeric(10, 6), nullable=False),
        sa.Column("currency", sa.String(10), server_default="CNY", nullable=False),
        sa.Column("is_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── A4: agency_free_quotas ──
    op.create_table(
        "agency_free_quotas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), nullable=False),
        sa.Column("free_ai_messages", sa.Integer, server_default="0", nullable=False),
        sa.Column("free_translations", sa.Integer, server_default="0", nullable=False),
        sa.Column("billing_month", sa.String(7), nullable=False),
        sa.Column("used_ai_messages", sa.Integer, server_default="0", nullable=False),
        sa.Column("used_translations", sa.Integer, server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agency_id", "billing_month", name="uq_agency_free_quotas_month"),
    )
    # ── A5: agency_monthly_bills ──
    op.create_table(
        "agency_monthly_bills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), nullable=False),
        sa.Column("billing_month", sa.String(7), nullable=False),
        sa.Column("ai_cost", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("translation_cost", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("total_cost", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("free_ai_used", sa.Integer, server_default="0", nullable=False),
        sa.Column("free_translation_used", sa.Integer, server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("details", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agency_id", "billing_month", name="uq_agency_monthly_bills_month"),
    )
    # ── B1: site_currencies ──
    op.create_table(
        "site_currencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("site_id", sa.String(36), nullable=False, unique=True),
        sa.Column("currency_code", sa.String(10), nullable=False),
        sa.Column("currency_symbol", sa.String(5), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── B2: exchange_rates ──
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("from_currency", sa.String(10), nullable=False),
        sa.Column("to_currency", sa.String(10), nullable=False),
        sa.Column("rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("source", sa.String(20), server_default="manual", nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("from_currency", "to_currency", name="uq_exchange_rates_pair"),
    )
    # ── C1: payment_channels ──
    op.create_table(
        "payment_channels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("app_id", sa.String(200), nullable=True),
        sa.Column("app_secret_encrypted", sa.String(1024), nullable=True),
        sa.Column("callback_url", sa.String(500), nullable=True),
        sa.Column("fee_rate", sa.Numeric(5, 4), server_default="0", nullable=False),
        sa.Column("min_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("is_sandbox", sa.Boolean, server_default="false", nullable=False),
        sa.Column("callback_secret", sa.String(200), nullable=True),
        sa.Column("config_json", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── C2: agent_payment_channel_settings ──
    op.create_table(
        "agent_payment_channel_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), nullable=False),
        sa.Column("channel_id", sa.String(36), nullable=True),
        sa.Column("is_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("is_recharge_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("is_withdraw_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("custom_merchant_id", sa.String(200), nullable=True),
        sa.Column("custom_secret_encrypted", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agency_id", "channel_id", name="uq_agent_channel_settings"),
    )
    # ── D1: withdrawal_settings ──
    op.create_table(
        "withdrawal_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), nullable=False, unique=True),
        sa.Column("auto_approve_below", sa.Numeric(12, 2), nullable=True),
        sa.Column("min_withdraw_amount", sa.Numeric(12, 2), server_default="10", nullable=False),
        sa.Column("max_daily_withdraw", sa.Numeric(12, 2), nullable=True),
        sa.Column("fee_enabled", sa.Boolean, server_default="false", nullable=False),
        sa.Column("fee_rate", sa.Numeric(5, 4), server_default="0", nullable=False),
        sa.Column("freeze_enabled", sa.Boolean, server_default="true", nullable=False),
        sa.Column("freeze_threshold_count", sa.Integer, server_default="5", nullable=False),
        sa.Column("freeze_threshold_hours", sa.Integer, server_default="24", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── D2: recharge_records ──
    op.create_table(
        "recharge_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("agency_id", sa.String(36), nullable=True),
        sa.Column("site_id", sa.String(36), nullable=True),
        sa.Column("channel_id", sa.String(36), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(12, 6), nullable=True),
        sa.Column("status", sa.String(20), server_default="completed", nullable=False),
        sa.Column("channel_order_id", sa.String(200), nullable=True),
        sa.Column("callback_data", JSON, nullable=True),
        sa.Column("callback_verified", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── D3: withdrawal_records ──
    op.create_table(
        "withdrawal_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("agency_id", sa.String(36), nullable=True),
        sa.Column("site_id", sa.String(36), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("fee", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("auto_approved", sa.Boolean, server_default="false", nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("reject_reason", sa.Text, nullable=True),
        sa.Column("frozen_at", sa.DateTime, nullable=True),
        sa.Column("frozen_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    # ── D4: payment_callbacks ──
    op.create_table(
        "payment_callbacks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("channel_id", sa.String(36), nullable=True),
        sa.Column("recharge_record_id", sa.String(36), nullable=True),
        sa.Column("raw_payload", JSON, nullable=False),
        sa.Column("signature_valid", sa.Boolean, server_default="false", nullable=False),
        sa.Column("processed", sa.Boolean, server_default="false", nullable=False),
        sa.Column("retry_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("max_retries", sa.Integer, server_default="3", nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime, nullable=True),
    )
    # ── E1: payment_reconciliations ──
    op.create_table(
        "payment_reconciliations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("channel_id", sa.String(36), nullable=True),
        sa.Column("reconcile_date", sa.Date, nullable=False),
        sa.Column("platform_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("channel_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("difference", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("details", JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("payment_reconciliations")
    op.drop_table("payment_callbacks")
    op.drop_table("withdrawal_records")
    op.drop_table("recharge_records")
    op.drop_table("withdrawal_settings")
    op.drop_table("agent_payment_channel_settings")
    op.drop_table("payment_channels")
    op.drop_table("exchange_rates")
    op.drop_table("site_currencies")
    op.drop_table("agency_monthly_bills")
    op.drop_table("agency_free_quotas")
    op.drop_table("ai_provider_rates")
    op.drop_table("translation_usage_records")
    op.drop_table("ai_usage_records")
