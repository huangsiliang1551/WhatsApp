"""agency_username_and_billing_line_items

Revision ID: 9eded4d8393d
Revises: 20260619_0100
Create Date: 2026-06-18 03:04:00.733947
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9eded4d8393d'
down_revision = '20260619_0100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add username column to agencies
    op.add_column("agencies", sa.Column("username", sa.String(100), nullable=True))
    op.create_index("ix_agencies_username", "agencies", ["username"], unique=True)
    # Add password_hash column to agencies
    op.add_column("agencies", sa.Column("password_hash", sa.String(256), nullable=True))
    # Add line_items JSON column to agency_billing
    op.add_column("agency_billing", sa.Column("line_items", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("agency_billing", "line_items")
    op.drop_column("agencies", "password_hash")
    op.drop_index("ix_agencies_username", table_name="agencies")
    op.drop_column("agencies", "username")
