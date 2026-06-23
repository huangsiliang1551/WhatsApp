"""business_hours

Revision ID: 0069
Revises: 0068
Create Date: 2026-06-12 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    weekdays_default = (
        sa.text("'[1,2,3,4,5]'")
        if bind.dialect.name == "sqlite"
        else sa.text("'[1,2,3,4,5]'::json")
    )

    op.create_table(
        "business_hours",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=False, unique=True, index=True),
        sa.Column("weekdays", sa.JSON(), nullable=False, server_default=weekdays_default),
        sa.Column("start_time", sa.String(5), nullable=False, server_default="09:00"),
        sa.Column("end_time", sa.String(5), nullable=False, server_default="18:00"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Shanghai"),
        sa.Column("off_hours_behavior", sa.String(20), nullable=False, server_default="ai_managed"),
        sa.Column("off_hours_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("business_hours")
