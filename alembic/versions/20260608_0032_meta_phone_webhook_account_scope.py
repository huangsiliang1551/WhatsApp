"""Add direct account scope to Meta phone numbers and webhook subscriptions."""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0032"
down_revision = "20260608_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_phone_numbers",
        sa.Column("account_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "webhook_subscriptions",
        sa.Column("account_id", sa.String(length=128), nullable=True),
    )

    op.execute(
        """
        UPDATE whatsapp_phone_numbers
        SET account_id = (
            SELECT whatsapp_business_accounts.account_id
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.id = whatsapp_phone_numbers.waba_account_id
        )
        """
    )
    op.execute(
        """
        UPDATE webhook_subscriptions
        SET account_id = (
            SELECT whatsapp_business_accounts.account_id
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.id = webhook_subscriptions.waba_account_id
        )
        """
    )

    with op.batch_alter_table("whatsapp_phone_numbers") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_whatsapp_phone_numbers_account_id_accounts",
            "accounts",
            ["account_id"],
            ["account_id"],
        )
    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_webhook_subscriptions_account_id_accounts",
            "accounts",
            ["account_id"],
            ["account_id"],
        )

    op.create_index(
        "ix_whatsapp_phone_numbers_account_id",
        "whatsapp_phone_numbers",
        ["account_id"],
    )
    op.create_index(
        "ix_webhook_subscriptions_account_id",
        "webhook_subscriptions",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_subscriptions_account_id", table_name="webhook_subscriptions")
    op.drop_index("ix_whatsapp_phone_numbers_account_id", table_name="whatsapp_phone_numbers")

    with op.batch_alter_table("webhook_subscriptions") as batch_op:
        batch_op.drop_constraint(
            "fk_webhook_subscriptions_account_id_accounts",
            type_="foreignkey",
        )
        batch_op.drop_column("account_id")
    with op.batch_alter_table("whatsapp_phone_numbers") as batch_op:
        batch_op.drop_constraint(
            "fk_whatsapp_phone_numbers_account_id_accounts",
            type_="foreignkey",
        )
        batch_op.drop_column("account_id")
