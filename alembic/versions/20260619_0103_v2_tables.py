"""Create V2.0 tables: db_backups, knowledge_categories, knowledge_articles,
customer_auto_tag_rules, api_rate_limits, email_config, health_checks.

Revision ID: 20260619_0103
Revises: 20260619_0102
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260619_0103"
down_revision: str | None = "20260619_0102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── db_backups ──────────────────────────────────────────────────────────────
    if not op.get_bind().dialect.has_table(op.get_bind(), "db_backups"):
        op.create_table(
            "db_backups",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("filename", sa.String(200), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("file_size", sa.BigInteger(), nullable=True),
            sa.Column("backup_type", sa.String(20), nullable=False, server_default="manual"),
            sa.Column("status", sa.String(20), nullable=False, server_default="running"),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
        )

    # ── knowledge_categories ────────────────────────────────────────────────────
    if not op.get_bind().dialect.has_table(op.get_bind(), "knowledge_categories"):
        op.create_table(
            "knowledge_categories",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("agency_id", sa.String(36), nullable=True, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # ── knowledge_articles ──────────────────────────────────────────────────────
    if not op.get_bind().dialect.has_table(op.get_bind(), "knowledge_articles"):
        op.create_table(
            "knowledge_articles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("category_id", sa.String(36), sa.ForeignKey("knowledge_categories.id"), nullable=True, index=True),
            sa.Column("agency_id", sa.String(36), nullable=True, index=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("keywords", sa.Text(), nullable=True),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # ── customer_auto_tag_rules ─────────────────────────────────────────────────
    if not op.get_bind().dialect.has_table(op.get_bind(), "customer_auto_tag_rules"):
        op.create_table(
            "customer_auto_tag_rules",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("agency_id", sa.String(36), nullable=True, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("condition_type", sa.String(50), nullable=False),
            sa.Column("condition_operator", sa.String(10), nullable=False),
            sa.Column("condition_value", sa.Numeric(12, 2), nullable=False),
            sa.Column("tag_name", sa.String(100), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # ── api_rate_limits ─────────────────────────────────────────────────────────
    if not op.get_bind().dialect.has_table(op.get_bind(), "api_rate_limits"):
        op.create_table(
            "api_rate_limits",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("agency_id", sa.String(36), nullable=True, index=True),
            sa.Column("endpoint_pattern", sa.String(200), nullable=False),
            sa.Column("max_requests", sa.Integer(), nullable=False),
            sa.Column("window_seconds", sa.Integer(), nullable=False),
            sa.Column("ban_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # ── email_config ────────────────────────────────────────────────────────────
    if not op.get_bind().dialect.has_table(op.get_bind(), "email_config"):
        op.create_table(
            "email_config",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("smtp_host", sa.String(200), nullable=False),
            sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="465"),
            sa.Column("smtp_user", sa.String(200), nullable=False),
            sa.Column("smtp_password", sa.String(500), nullable=False),
            sa.Column("smtp_ssl", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("from_name", sa.String(100), nullable=True),
            sa.Column("from_email", sa.String(200), nullable=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # ── health_checks ───────────────────────────────────────────────────────────
    if not op.get_bind().dialect.has_table(op.get_bind(), "health_checks"):
        op.create_table(
            "health_checks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("check_type", sa.String(50), nullable=False),
            sa.Column("target", sa.String(200), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("response_time_ms", sa.Integer(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("checked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("health_checks")
    op.drop_table("email_config")
    op.drop_table("api_rate_limits")
    op.drop_table("customer_auto_tag_rules")
    op.drop_table("knowledge_articles")
    op.drop_table("knowledge_categories")
    op.drop_table("db_backups")
