"""add notes to accounts

Revision ID: 4f06beb1b074
Revises: 52538b2c851a
Create Date: 2026-06-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f06beb1b074'
down_revision: Union[str, None] = 'ab82e8b310d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column('notes', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('accounts', 'notes')
