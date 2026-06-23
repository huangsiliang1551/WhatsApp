"""add invitee_ip and invitee_device_id to invite_records

Revision ID: a3f5c2d1e6b7
Revises: 698b1cc1f0c7
Create Date: 2026-06-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f5c2d1e6b7"
down_revision: str | None = "20260616_0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invite_records",
        sa.Column("invitee_ip", sa.String(45), nullable=True),
    )
    op.add_column(
        "invite_records",
        sa.Column("invitee_device_id", sa.String(128), nullable=True),
    )
    op.create_index("ix_invite_records_invitee_ip", "invite_records", ["invitee_ip"])
    op.create_index(
        "ix_invite_records_invitee_device_id",
        "invite_records",
        ["invitee_device_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_invite_records_invitee_device_id")
    op.drop_index("ix_invite_records_invitee_ip")
    op.drop_column("invite_records", "invitee_device_id")
    op.drop_column("invite_records", "invitee_ip")
