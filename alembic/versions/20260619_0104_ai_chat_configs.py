"""Create ai_chat_configs table.

Revision ID: 20260619_0104
Revises: 20260619_0103
Create Date: 2026-06-19 10:04:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_0104"
down_revision: str | None = "20260619_0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if not op.get_bind().dialect.has_table(op.get_bind(), "ai_chat_configs"):
        op.create_table(
            "ai_chat_configs",
            # ── PK ──
            sa.Column("id", sa.String(36), primary_key=True),
            # ── scope: NULL=system default, non-NULL=agency override, unique ──
            sa.Column("agency_id", sa.String(36), nullable=True, unique=True, index=True),

            # ── 1. 系统提示词 ──
            sa.Column("system_prompt_template", sa.Text(), nullable=True),
            sa.Column("brand_name", sa.String(200), nullable=True),
            sa.Column("customer_language", sa.String(20), nullable=True, server_default=sa.text("'auto'")),

            # ── 2. 模型参数 ──
            sa.Column("model_temperature", sa.Float(), nullable=True, server_default=sa.text("0.3")),
            sa.Column("model_max_tokens", sa.Integer(), nullable=True, server_default=sa.text("300")),
            sa.Column("model_top_p", sa.Float(), nullable=True, server_default=sa.text("0.9")),
            sa.Column("model_frequency_penalty", sa.Float(), nullable=True, server_default=sa.text("0.0")),
            sa.Column("model_presence_penalty", sa.Float(), nullable=True, server_default=sa.text("0.0")),

            # ── 3. 会话行为 ──
            sa.Column("context_max_messages", sa.Integer(), nullable=True, server_default=sa.text("20")),
            sa.Column("context_max_chars", sa.Integer(), nullable=True, server_default=sa.text("6000")),
            sa.Column("max_message_chars", sa.Integer(), nullable=True, server_default=sa.text("500")),
            sa.Column("greeting_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("greeting_message", sa.String(500), nullable=True),

            # ── 4. 自动回复 ──
            sa.Column("auto_reply_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("auto_reply_delay_seconds", sa.Integer(), nullable=True, server_default=sa.text("2")),
            sa.Column("non_working_hours_reply", sa.Text(), nullable=True),

            # ── 5. 转人工触发 ──
            sa.Column("escalate_keywords", sa.JSON(), nullable=True),
            sa.Column("escalate_intents", sa.JSON(), nullable=True),
            sa.Column("escalate_unknown_count", sa.Integer(), nullable=True, server_default=sa.text("3")),
            sa.Column("escalate_unknown_window_minutes", sa.Integer(), nullable=True, server_default=sa.text("30")),

            # ── 6. 安全过滤 ──
            sa.Column("blocked_keywords", sa.JSON(), nullable=True),
            sa.Column("max_reply_length", sa.Integer(), nullable=True, server_default=sa.text("2000")),
            sa.Column("sensitive_content_check", sa.Boolean(), nullable=True, server_default=sa.text("true")),

            # ── 7. 高级设置 ──
            sa.Column("fallback_message", sa.Text(), nullable=True),
            sa.Column("translation_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("context_window_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("conversation_sleep_minutes", sa.Integer(), nullable=True, server_default=sa.text("5")),

            # ── 8. AI 工具调用 ──
            sa.Column("tools_enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("tool_call_timeout_seconds", sa.Integer(), nullable=True, server_default=sa.text("15")),
            sa.Column("max_tool_calls_per_session", sa.Integer(), nullable=True, server_default=sa.text("10")),
            sa.Column("allowed_tools", sa.JSON(), nullable=True),

            # ── 元数据 ──
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "ai_chat_configs"):
        op.drop_table("ai_chat_configs")
