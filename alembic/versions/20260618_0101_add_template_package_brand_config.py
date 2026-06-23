"""add template package and brand config columns

Revision ID: 20260618_0101
Revises: 20260618_0100
Create Date: 2026-06-18 22:55:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260618_0101"
down_revision = "20260618_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── A1: h5_templates new columns ──
    op.add_column("h5_templates", sa.Column("package_filename", sa.String(500), nullable=True))
    op.add_column("h5_templates", sa.Column("package_size", sa.Integer, nullable=True))
    op.add_column("h5_templates", sa.Column("package_uploaded_at", sa.DateTime, nullable=True))
    op.add_column("h5_templates", sa.Column("preview_path", sa.String(500), nullable=True))
    op.add_column("h5_templates", sa.Column("status", sa.String(20), server_default="draft", nullable=False))

    # ── B1: h5_sites new columns ──
    op.add_column("h5_sites", sa.Column("favicon_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("h5_sites", "favicon_url")
    op.drop_column("h5_templates", "status")
    op.drop_column("h5_templates", "preview_path")
    op.drop_column("h5_templates", "package_uploaded_at")
    op.drop_column("h5_templates", "package_size")
    op.drop_column("h5_templates", "package_filename")
