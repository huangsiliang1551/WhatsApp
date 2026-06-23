"""add_sleeping_and_cold_fields

Revision ID: ab82e8b310d0
Revises: 20260613_0073
Create Date: 2026-06-15 15:39:46.989347
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'ab82e8b310d0'
down_revision = '20260613_0073'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Conversation: is_sleeping + last_customer_message_at
    op.add_column('conversations', sa.Column('is_sleeping', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index(op.f('ix_conversations_is_sleeping'), 'conversations', ['is_sleeping'])
    op.add_column('conversations', sa.Column('last_customer_message_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_conversations_last_customer_message_at'), 'conversations', ['last_customer_message_at'])

    # Message: is_cold
    op.add_column('messages', sa.Column('is_cold', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.create_index(op.f('ix_messages_is_cold'), 'messages', ['is_cold'])


def downgrade() -> None:
    # Message: is_cold
    op.drop_index(op.f('ix_messages_is_cold'), table_name='messages')
    op.drop_column('messages', 'is_cold')

    # Conversation: is_sleeping + last_customer_message_at
    op.drop_index(op.f('ix_conversations_last_customer_message_at'), table_name='conversations')
    op.drop_column('conversations', 'last_customer_message_at')
    op.drop_index(op.f('ix_conversations_is_sleeping'), table_name='conversations')
    op.drop_column('conversations', 'is_sleeping')
