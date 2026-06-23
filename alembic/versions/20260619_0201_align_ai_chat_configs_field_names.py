"""Align ai_chat_configs field names with spec — 8 categories.

Drop old table (created by 20260619_0104) and recreate with spec-correct field names.

Revision ID: 20260619_0201
Revises: 20260619_0104
Create Date: 2026-06-19 20:01:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_0201"
down_revision: str | None = "20260619_0104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop old table if it exists (created with wrong field names by 0104)
    if op.get_bind().dialect.has_table(op.get_bind(), "ai_chat_configs"):
        op.drop_table("ai_chat_configs")

    op.create_table(
        "ai_chat_configs",
        # ── PK ──
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agency_id", sa.String(36), nullable=True, unique=True, index=True),

        # ── 1. 系统提示词 ──
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("prompt_append_context", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("prompt_variables", sa.JSON(), nullable=True),

        # ── 2. 模型参数 ──
        sa.Column("temperature", sa.Float(), nullable=True, server_default=sa.text("0.3")),
        sa.Column("max_tokens", sa.Integer(), nullable=True, server_default=sa.text("300")),
        sa.Column("top_p", sa.Float(), nullable=True, server_default=sa.text("1.0")),
        sa.Column("frequency_penalty", sa.Float(), nullable=True, server_default=sa.text("0.0")),
        sa.Column("presence_penalty", sa.Float(), nullable=True, server_default=sa.text("0.0")),
        sa.Column("stop_sequences", sa.JSON(), nullable=True),

        # ── 3. 会话行为 ──
        sa.Column("context_window_messages", sa.Integer(), nullable=True, server_default=sa.text("10")),
        sa.Column("context_window_tokens", sa.Integer(), nullable=True, server_default=sa.text("2000")),
        sa.Column("conversation_memory", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("greeting_message", sa.Text(), nullable=True),
        sa.Column("off_hours_message", sa.Text(), nullable=True),
        sa.Column("off_hours_start", sa.String(5), nullable=True),
        sa.Column("off_hours_end", sa.String(5), nullable=True),
        sa.Column("off_hours_timezone", sa.String(50), nullable=True, server_default=sa.text("'Asia/Shanghai'")),

        # ── 4. 自动回复 ──
        sa.Column("auto_reply_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("auto_reply_delay_seconds", sa.Integer(), nullable=True, server_default=sa.text("2")),
        sa.Column("auto_reply_keywords", sa.JSON(), nullable=True),
        sa.Column("auto_reply_fallback", sa.Text(), nullable=True),
        sa.Column("duplicate_message_filter", sa.Boolean(), nullable=True, server_default=sa.text("true")),

        # ── 5. 转人工 ──
        sa.Column("auto_escalation_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("escalation_keywords", sa.JSON(), nullable=True),
        sa.Column("escalation_max_failures", sa.Integer(), nullable=True, server_default=sa.text("3")),
        sa.Column("escalation_sentiment_threshold", sa.Float(), nullable=True, server_default=sa.text("-0.5")),
        sa.Column("escalation_max_rounds", sa.Integer(), nullable=True, server_default=sa.text("20")),
        sa.Column("escalation_message", sa.Text(), nullable=True),

        # ── 6. 安全 ──
        sa.Column("blocked_topics", sa.JSON(), nullable=True),
        sa.Column("content_filter_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("pii_protection", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("max_response_length", sa.Integer(), nullable=True, server_default=sa.text("500")),
        sa.Column("language_lock", sa.Boolean(), nullable=True, server_default=sa.text("false")),

        # ── 7. 高级 ──
        sa.Column("response_format", sa.String(20), nullable=True, server_default=sa.text("'text'")),
        sa.Column("inject_brand_info", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("inject_knowledge_base", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("debug_mode", sa.Boolean(), nullable=True, server_default=sa.text("false")),

        # ── 8. AI 工具调用 ──
        sa.Column("tools_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("enabled_tools", sa.JSON(), nullable=True),
        sa.Column("max_tool_calls_per_session", sa.Integer(), nullable=True, server_default=sa.text("10")),
        sa.Column("identity_verify_method", sa.String(20), nullable=True, server_default=sa.text("'whatsapp'")),
        sa.Column("identity_auto_verify", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.Column("tool_call_timeout_seconds", sa.Integer(), nullable=True, server_default=sa.text("5")),

        # ── 元数据 ──
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "ai_chat_configs"):
        op.drop_table("ai_chat_configs")
