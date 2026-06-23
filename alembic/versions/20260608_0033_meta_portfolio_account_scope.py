"""Add direct account scope to Meta business portfolios."""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0033"
down_revision = "20260608_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meta_business_portfolios",
        sa.Column("account_id", sa.String(length=128), nullable=True),
    )

    op.execute(
        """
        UPDATE meta_business_portfolios
        SET account_id = (
            SELECT MIN(whatsapp_business_accounts.account_id)
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.portfolio_id = meta_business_portfolios.id
        )
        WHERE (
            SELECT COUNT(DISTINCT whatsapp_business_accounts.account_id)
            FROM whatsapp_business_accounts
            WHERE whatsapp_business_accounts.portfolio_id = meta_business_portfolios.id
        ) = 1
        """
    )

    with op.batch_alter_table("meta_business_portfolios") as batch_op:
        batch_op.create_foreign_key(
            "fk_meta_business_portfolios_account_id_accounts",
            "accounts",
            ["account_id"],
            ["account_id"],
        )

    op.create_index(
        "ix_meta_business_portfolios_account_id",
        "meta_business_portfolios",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_meta_business_portfolios_account_id", table_name="meta_business_portfolios")

    with op.batch_alter_table("meta_business_portfolios") as batch_op:
        batch_op.drop_constraint(
            "fk_meta_business_portfolios_account_id_accounts",
            type_="foreignkey",
        )
        batch_op.drop_column("account_id")
