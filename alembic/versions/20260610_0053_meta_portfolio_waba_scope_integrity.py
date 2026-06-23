"""Harden Meta portfolio/WABA account-scope integrity.

Revision ID: 20260610_0053
Revises: 20260610_0052
Create Date: 2026-06-10 16:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260610_0053"
down_revision: str | None = "20260610_0052"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _format_scope_rows(rows: Sequence[sa.RowMapping]) -> str:
    return ", ".join(
        f"{row['id']}({row.get('meta_business_portfolio_id', row.get('waba_id', 'unknown'))})"
        for row in rows
    )


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE meta_business_portfolios
            SET account_id = (
                SELECT MIN(whatsapp_business_accounts.account_id)
                FROM whatsapp_business_accounts
                WHERE whatsapp_business_accounts.portfolio_id = meta_business_portfolios.id
            )
            WHERE account_id IS NULL
              AND (
                SELECT COUNT(DISTINCT whatsapp_business_accounts.account_id)
                FROM whatsapp_business_accounts
                WHERE whatsapp_business_accounts.portfolio_id = meta_business_portfolios.id
              ) = 1
            """
        )
    )

    conflicting_portfolios = bind.execute(
        sa.text(
            """
            SELECT
                meta_business_portfolios.id,
                meta_business_portfolios.meta_business_portfolio_id
            FROM meta_business_portfolios
            JOIN whatsapp_business_accounts
              ON whatsapp_business_accounts.portfolio_id = meta_business_portfolios.id
            GROUP BY
                meta_business_portfolios.id,
                meta_business_portfolios.meta_business_portfolio_id
            HAVING COUNT(DISTINCT whatsapp_business_accounts.account_id) > 1
            ORDER BY meta_business_portfolios.id
            LIMIT 5
            """
        )
    ).mappings().all()
    if conflicting_portfolios:
        raise RuntimeError(
            "Cannot enforce Meta portfolio account scope integrity because some portfolios are "
            "linked to WABAs from multiple accounts: "
            f"{_format_scope_rows(conflicting_portfolios)}."
        )

    unscoped_portfolios = bind.execute(
        sa.text(
            """
            SELECT id, meta_business_portfolio_id
            FROM meta_business_portfolios
            WHERE account_id IS NULL
            ORDER BY id
            LIMIT 5
            """
        )
    ).mappings().all()
    if unscoped_portfolios:
        raise RuntimeError(
            "Cannot enforce Meta portfolio account scope integrity because some portfolios still "
            "have no account scope after backfill: "
            f"{_format_scope_rows(unscoped_portfolios)}."
        )

    mismatched_wabas = bind.execute(
        sa.text(
            """
            SELECT
                whatsapp_business_accounts.id,
                whatsapp_business_accounts.waba_id,
                meta_business_portfolios.meta_business_portfolio_id
            FROM whatsapp_business_accounts
            JOIN meta_business_portfolios
              ON meta_business_portfolios.id = whatsapp_business_accounts.portfolio_id
            WHERE whatsapp_business_accounts.portfolio_id IS NOT NULL
              AND whatsapp_business_accounts.account_id <> meta_business_portfolios.account_id
            ORDER BY whatsapp_business_accounts.id
            LIMIT 5
            """
        )
    ).mappings().all()
    if mismatched_wabas:
        raise RuntimeError(
            "Cannot enforce Meta portfolio/WABA account scope integrity because some WABAs are "
            "linked to portfolios owned by a different account: "
            f"{_format_scope_rows(mismatched_wabas)}."
        )

    with op.batch_alter_table("meta_business_portfolios") as batch_op:
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_meta_business_portfolios_id_account",
            ["id", "account_id"],
        )

    with op.batch_alter_table("whatsapp_business_accounts") as batch_op:
        batch_op.create_foreign_key(
            "fk_whatsapp_business_accounts_portfolio_account_scope",
            "meta_business_portfolios",
            ["portfolio_id", "account_id"],
            ["id", "account_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_business_accounts") as batch_op:
        batch_op.drop_constraint(
            "fk_whatsapp_business_accounts_portfolio_account_scope",
            type_="foreignkey",
        )

    with op.batch_alter_table("meta_business_portfolios") as batch_op:
        batch_op.drop_constraint(
            "uq_meta_business_portfolios_id_account",
            type_="unique",
        )
        batch_op.alter_column(
            "account_id",
            existing_type=sa.String(length=128),
            nullable=True,
        )
