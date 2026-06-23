"""canned_responses + initial data

Revision ID: 0068
Revises: 0067
Create Date: 2026-06-12 12:30:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0068"
down_revision: str | None = "0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INITIAL_RESPONSES = [
    ("greeting", "您好，欢迎联系我们的客服！请问有什么可以帮您？", "问候语"),
    ("farewell", "感谢您的咨询，祝您生活愉快！如有其他问题，随时联系我们。", "结束语"),
    ("waiting", "您好，正在为您查询，请稍等片刻。", "等待提示"),
    ("order_status", "您好，您的订单当前状态为：{status}。如有疑问请随时联系我们。", "订单查询"),
    ("delivery_info", "您的物流单号是 {tracking_no}，当前运输状态为：{status}。", "物流查询"),
    ("payment_confirm", "您好，您的付款已确认，订单正在处理中。预计 {eta} 内完成。", "支付确认"),
    ("refund_policy", "关于退款政策：订单在签收后 7 天内可申请退款，请联系我们提交退款申请。", "退款政策"),
    ("business_hours_info", "我们的工作时间是工作日 09:00-18:00（{timezone}），非工作时间将由 AI 为您服务。", "工作时间"),
    ("complaint_received", "您好，我们已收到您的投诉工单（编号：{ticket_no}），将在 24 小时内回复您。", "投诉处理"),
    ("handover_to_human", "您好，已为您转接人工客服，请稍候。", "转人工"),
]


def upgrade() -> None:
    bind = op.get_bind()
    json_array_default = (
        sa.text("'[]'")
        if bind.dialect.name == "sqlite"
        else sa.text("'[]'::json")
    )

    op.create_table(
        "canned_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(128), sa.ForeignKey("accounts.account_id"), nullable=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False, server_default=json_array_default),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_canned_responses_account_category",
        "canned_responses",
        ["account_id", "category"],
    )

    # Seed 10 initial global canned responses
    conn = op.get_bind()
    for title, content, category in _INITIAL_RESPONSES:
        conn.execute(
            sa.text("""
                INSERT INTO canned_responses (id, account_id, title, content, category, variables, is_active, created_by)
                VALUES (:id, NULL, :title, :content, :category, :variables, TRUE, 'system')
            """),
            {
                "id": str(uuid4()),
                "title": title,
                "content": content,
                "category": category,
                "variables": "[]",
            },
        )


def downgrade() -> None:
    op.drop_index("ix_canned_responses_account_category", table_name="canned_responses")
    op.drop_table("canned_responses")
