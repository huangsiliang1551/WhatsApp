"""add task review, proof, and ticket workflow tables

Revision ID: 20260608_0021
Revises: 20260608_0020
Create Date: 2026-06-08 23:59:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608_0021"
down_revision = "20260608_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_proof_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_instance_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("storage_provider", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=128), nullable=False),
        sa.Column("uploaded_by_type", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["task_instance_id"], ["task_instances.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_proof_files_task_instance_id", "task_proof_files", ["task_instance_id"])
    op.create_index("ix_task_proof_files_user_id", "task_proof_files", ["user_id"])
    op.create_index("ix_task_proof_files_site_id", "task_proof_files", ["site_id"])
    op.create_index("ix_task_proof_files_object_key", "task_proof_files", ["object_key"])
    op.create_index("ix_task_proof_files_sha256", "task_proof_files", ["sha256"])

    op.create_table(
        "task_submissions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_instance_id", sa.String(length=36), nullable=False),
        sa.Column("submitted_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("submission_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="submitted"),
        sa.Column("source_channel", sa.String(length=32), nullable=False, server_default="h5"),
        sa.Column("submitted_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("review_started_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("review_completed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("review_required_snapshot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["task_instance_id"], ["task_instances.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_instance_id", "submission_no", name="uq_task_submissions_instance_attempt"),
    )
    op.create_index("ix_task_submissions_task_instance_id", "task_submissions", ["task_instance_id"])
    op.create_index("ix_task_submissions_submitted_by_user_id", "task_submissions", ["submitted_by_user_id"])
    op.create_index("ix_task_submissions_site_id", "task_submissions", ["site_id"])

    op.create_table(
        "task_submission_proofs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("proof_file_id", sa.String(length=36), nullable=False),
        sa.Column("proof_role", sa.String(length=32), nullable=False, server_default="evidence"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["proof_file_id"], ["task_proof_files.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["task_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", "proof_file_id", name="uq_task_submission_proofs_scope"),
    )
    op.create_index("ix_task_submission_proofs_submission_id", "task_submission_proofs", ["submission_id"])
    op.create_index("ix_task_submission_proofs_proof_file_id", "task_submission_proofs", ["proof_file_id"])

    op.create_table(
        "task_review_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_instance_id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("decision_source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("reviewer_actor_id", sa.String(length=128), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["task_submissions.id"]),
        sa.ForeignKeyConstraint(["task_instance_id"], ["task_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_review_decisions_task_instance_id", "task_review_decisions", ["task_instance_id"])
    op.create_index("ix_task_review_decisions_submission_id", "task_review_decisions", ["submission_id"])
    op.create_index("ix_task_review_decisions_reviewer_actor_id", "task_review_decisions", ["reviewer_actor_id"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_no", sa.String(length=64), nullable=False),
        sa.Column("linked_task_instance_id", sa.String(length=36), nullable=True),
        sa.Column("linked_submission_id", sa.String(length=36), nullable=True),
        sa.Column("review_decision_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("site_id", sa.String(length=36), nullable=True),
        sa.Column("ticket_type", sa.String(length=32), nullable=False, server_default="appeal"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("latest_reply_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("resolved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["review_decision_id"], ["task_review_decisions.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["h5_sites.id"]),
        sa.ForeignKeyConstraint(["linked_submission_id"], ["task_submissions.id"]),
        sa.ForeignKeyConstraint(["linked_task_instance_id"], ["task_instances.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_no"),
    )
    op.create_index("ix_tickets_ticket_no", "tickets", ["ticket_no"])
    op.create_index("ix_tickets_linked_task_instance_id", "tickets", ["linked_task_instance_id"])
    op.create_index("ix_tickets_linked_submission_id", "tickets", ["linked_submission_id"])
    op.create_index("ix_tickets_review_decision_id", "tickets", ["review_decision_id"])
    op.create_index("ix_tickets_user_id", "tickets", ["user_id"])
    op.create_index("ix_tickets_site_id", "tickets", ["site_id"])
    op.create_index(
        "uq_tickets_active_appeal_per_task_instance",
        "tickets",
        ["linked_task_instance_id"],
        unique=True,
        sqlite_where=sa.text("ticket_type = 'appeal' AND is_active = 1"),
        postgresql_where=sa.text("ticket_type = 'appeal' AND is_active = true"),
    )

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("sender_type", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("sender_id", sa.String(length=128), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("attachments_json", sa.JSON(), nullable=True),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])
    op.create_index("ix_ticket_messages_sender_id", "ticket_messages", ["sender_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_messages_sender_id", table_name="ticket_messages")
    op.drop_index("ix_ticket_messages_ticket_id", table_name="ticket_messages")
    op.drop_table("ticket_messages")

    op.drop_index("ix_tickets_ticket_no", table_name="tickets")
    op.drop_index("uq_tickets_active_appeal_per_task_instance", table_name="tickets")
    op.drop_index("ix_tickets_site_id", table_name="tickets")
    op.drop_index("ix_tickets_user_id", table_name="tickets")
    op.drop_index("ix_tickets_review_decision_id", table_name="tickets")
    op.drop_index("ix_tickets_linked_submission_id", table_name="tickets")
    op.drop_index("ix_tickets_linked_task_instance_id", table_name="tickets")
    op.drop_table("tickets")

    op.drop_index("ix_task_review_decisions_reviewer_actor_id", table_name="task_review_decisions")
    op.drop_index("ix_task_review_decisions_submission_id", table_name="task_review_decisions")
    op.drop_index("ix_task_review_decisions_task_instance_id", table_name="task_review_decisions")
    op.drop_table("task_review_decisions")

    op.drop_index("ix_task_submission_proofs_proof_file_id", table_name="task_submission_proofs")
    op.drop_index("ix_task_submission_proofs_submission_id", table_name="task_submission_proofs")
    op.drop_table("task_submission_proofs")

    op.drop_index("ix_task_submissions_site_id", table_name="task_submissions")
    op.drop_index("ix_task_submissions_submitted_by_user_id", table_name="task_submissions")
    op.drop_index("ix_task_submissions_task_instance_id", table_name="task_submissions")
    op.drop_table("task_submissions")

    op.drop_index("ix_task_proof_files_sha256", table_name="task_proof_files")
    op.drop_index("ix_task_proof_files_object_key", table_name="task_proof_files")
    op.drop_index("ix_task_proof_files_site_id", table_name="task_proof_files")
    op.drop_index("ix_task_proof_files_user_id", table_name="task_proof_files")
    op.drop_index("ix_task_proof_files_task_instance_id", table_name="task_proof_files")
    op.drop_table("task_proof_files")
