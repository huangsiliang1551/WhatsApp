from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
import pytest
from app.db.base import Base
from app.db.models import (
    Account,
    Agent,
    AppUser,
    Conversation,
    EmbeddedSignupSession,
    FragmentDefinition,
    FragmentDropLog,
    FragmentExchangeRequest,
    FragmentInventory,
    FragmentLedgerEntry,
    H5Site,
    Message,
    MediaAssetEvent,
    MediaAssetProviderSync,
    MessageEvent,
    MessageTemplate,
    MemberAuthSession,
    MemberNotification,
    MemberOrder,
    MemberProfile,
    MemberWhatsAppBindingRequest,
    PromotionTaskInstance,
    PromotionTaskTemplate,
    MemberVerificationDocument,
    MemberVerificationRequest,
    MetaBusinessPortfolio,
    ProviderStatusEventBuffer,
    SupportKnowledgeEntry,
    SystemSetting,
    TaskInstance,
    TaskPackageInstance,
    TaskPackageInstanceItem,
    TaskPackageTemplate,
    TaskPackageTemplateItem,
    TaskProofFile,
    TaskReviewDecision,
    TaskSubmission,
    TaskSubmissionProof,
    TemplateSendLog,
    TaskTemplate,
    Ticket,
    UserIdentity,
    UserReferral,
    UserTag,
    WalletAccount,
    WalletLedgerEntry,
    WalletRechargeOrder,
    WalletTransferRequest,
    MailingRequest,
    WithdrawalAuditLog,
    WithdrawalRequest,
    WebhookSubscription,
    WhatsAppBusinessAccount,
    WhatsAppPhoneNumber,
    utc_now,
)
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

META_STATUS_CHECKS: dict[str, dict[str, tuple[str, tuple[str, ...]]]] = {
    "meta_business_portfolios": {
        "ck_meta_business_portfolios_status": ("status", ("active",)),
    },
    "whatsapp_business_accounts": {
        "ck_whatsapp_business_accounts_webhook_verification_status": (
            "webhook_verification_status",
            ("pending", "verified", "failed", "unavailable"),
        ),
        "ck_whatsapp_business_accounts_webhook_runtime_status": (
            "webhook_runtime_status",
            ("pending", "healthy", "verification_pending", "signature_failed", "payload_invalid"),
        ),
    },
    "webhook_subscriptions": {
        "ck_webhook_subscriptions_status": (
            "status",
            ("pending", "mock_subscribed", "remote_pending", "remote_subscribed", "subscribed"),
        ),
    },
    "embedded_signup_sessions": {
        "ck_embedded_signup_sessions_status": (
            "status",
            ("created", "completed", "failed"),
        ),
        "ck_embedded_signup_sessions_completion_stage": (
            "completion_stage",
            (
                "pending_callback",
                "callback_recorded",
                "remote_confirmed",
                "local_waba_linked",
                "webhook_verification_pending",
                "failed",
            ),
        ),
        "ck_embedded_signup_sessions_last_event_source": (
            "last_event_source",
            ("operator", "provider_callback", "system_sync"),
        ),
    },
}


def test_expected_tables_exist() -> None:
    expected_tables = {
        "accounts",
        "system_settings",
        "meta_business_portfolios",
        "whatsapp_business_accounts",
        "whatsapp_phone_numbers",
        "webhook_subscriptions",
        "embedded_signup_sessions",
        "conversations",
        "messages",
        "message_events",
        "provider_status_event_buffer",
        "handover_logs",
        "agents",
        "message_templates",
        "template_send_logs",
        "template_daily_stats",
        "template_hourly_stats",
        "template_failure_stats",
        "whatsapp_daily_stats",
        "whatsapp_conversation_stats",
        "media_assets",
        "media_asset_events",
        "media_asset_provider_syncs",
        "audit_logs",
        "support_knowledge_entries",
        "h5_sites",
        "app_users",
        "member_profiles",
        "member_auth_sessions",
        "member_whatsapp_binding_requests",
        "member_verification_requests",
        "member_verification_documents",
        "task_package_templates",
        "task_package_template_items",
        "task_package_instances",
        "task_package_instance_items",
        "user_identities",
        "invite_codes",
        "user_tags",
        "user_tag_assignments",
        "audience_rule_sets",
        "task_templates",
        "task_instances",
        "task_proof_files",
        "task_submissions",
        "task_submission_proofs",
        "task_review_decisions",
        "tickets",
        "ticket_messages",
        "wallet_accounts",
        "wallet_ledger_entries",
        "wallet_transfer_requests",
        "wallet_recharge_orders",
        "withdrawal_requests",
        "withdrawal_audit_logs",
        "fragment_definitions",
        "fragment_inventory",
        "fragment_ledger_entries",
        "fragment_drop_logs",
        "fragment_exchange_requests",
        "member_orders",
        "member_notifications",
        "mailing_requests",
        "promotion_task_templates",
        "promotion_task_instances",
        "user_referrals",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_key_relationship_columns_exist() -> None:
    assert "account_id" in Account.__table__.c
    assert "key" in SystemSetting.__table__.c
    assert "account_id" in MetaBusinessPortfolio.__table__.c
    assert "waba_id" in WhatsAppBusinessAccount.__table__.c
    assert "webhook_verification_status" in WhatsAppBusinessAccount.__table__.c
    assert "webhook_last_verified_at" in WhatsAppBusinessAccount.__table__.c
    assert "webhook_runtime_status" in WhatsAppBusinessAccount.__table__.c
    assert "webhook_last_event_received_at" in WhatsAppBusinessAccount.__table__.c
    assert "webhook_signature_failure_count" in WhatsAppBusinessAccount.__table__.c
    assert "webhook_last_management_event_at" in WhatsAppBusinessAccount.__table__.c
    assert "account_id" in WhatsAppPhoneNumber.__table__.c
    assert "waba_id" in WhatsAppPhoneNumber.__table__.c
    assert "phone_number_id" in WhatsAppPhoneNumber.__table__.c
    assert "quality_event" in WhatsAppPhoneNumber.__table__.c
    assert "previous_quality_rating" in WhatsAppPhoneNumber.__table__.c
    assert "messaging_limit_tier" in WhatsAppPhoneNumber.__table__.c
    assert "max_daily_conversations_per_business" in WhatsAppPhoneNumber.__table__.c
    assert "last_quality_event_at" in WhatsAppPhoneNumber.__table__.c
    assert "last_status_payload" in WhatsAppPhoneNumber.__table__.c
    assert "account_id" in WebhookSubscription.__table__.c
    assert "waba_id" in WebhookSubscription.__table__.c
    assert "app_secret" in WebhookSubscription.__table__.c
    assert "session_id" in EmbeddedSignupSession.__table__.c
    assert "provider_name" in EmbeddedSignupSession.__table__.c
    assert "completion_stage" in EmbeddedSignupSession.__table__.c
    assert "provider_waba_id" in EmbeddedSignupSession.__table__.c
    assert "provider_business_portfolio_id" in EmbeddedSignupSession.__table__.c
    assert "linked_phone_number_ids_json" in EmbeddedSignupSession.__table__.c
    assert "completion_payload" in EmbeddedSignupSession.__table__.c
    assert "created_webhook_subscription_id" in EmbeddedSignupSession.__table__.c
    assert "management_mode" in Conversation.__table__.c
    assert "external_conversation_id" in Conversation.__table__.c
    assert "customer_language" in Conversation.__table__.c
    assert "account_id" in Agent.__table__.c
    assert "agent_key" in Agent.__table__.c
    assert "translated_text" in Message.__table__.c
    assert "provider_message_id" in Message.__table__.c
    assert "phone_number_id" in Message.__table__.c
    assert "provider_message_id" in ProviderStatusEventBuffer.__table__.c
    assert "external_status" in ProviderStatusEventBuffer.__table__.c
    assert "replay_state" in ProviderStatusEventBuffer.__table__.c
    assert "seen_count" in ProviderStatusEventBuffer.__table__.c
    assert "replayed_message_event_id" in ProviderStatusEventBuffer.__table__.c
    assert "phone_number_id" in Base.metadata.tables["template_send_logs"].c
    assert "idempotency_key" in Base.metadata.tables["template_send_logs"].c
    assert "header_media_asset_id" in Base.metadata.tables["template_send_logs"].c
    assert "header_media_provider_media_id" in Base.metadata.tables["template_send_logs"].c
    assert "header_media_meta_media_id" in Base.metadata.tables["template_send_logs"].c
    assert "header_media_sync_status" in Base.metadata.tables["template_send_logs"].c
    assert "waba_id" in Base.metadata.tables["message_templates"].c
    assert "conversation_origin_type" in Base.metadata.tables["template_send_logs"].c
    assert "conversation_category" in Base.metadata.tables["template_send_logs"].c
    assert "pricing_model" in Base.metadata.tables["template_send_logs"].c
    assert "billable" in Base.metadata.tables["template_send_logs"].c
    assert "estimated_cost" in Base.metadata.tables["template_send_logs"].c
    assert "estimated_cost" in Base.metadata.tables["template_daily_stats"].c
    assert "hour_bucket" in Base.metadata.tables["template_hourly_stats"].c
    assert "estimated_cost" in Base.metadata.tables["template_hourly_stats"].c
    assert "error_code" in Base.metadata.tables["template_failure_stats"].c
    assert "failed_count" in Base.metadata.tables["template_failure_stats"].c
    assert "conversation_origin_type" in Base.metadata.tables["whatsapp_daily_stats"].c
    assert "inbound_message_count" in Base.metadata.tables["whatsapp_daily_stats"].c
    assert "outbound_message_count" in Base.metadata.tables["whatsapp_daily_stats"].c
    assert "delivered_count" in Base.metadata.tables["whatsapp_daily_stats"].c
    assert "unique_customer_count" in Base.metadata.tables["whatsapp_daily_stats"].c
    assert "meta_media_id" in Base.metadata.tables["media_assets"].c
    assert "waba_id" in MediaAssetEvent.__table__.c
    assert "event_type" in Base.metadata.tables["media_asset_events"].c
    assert "provider_media_id" in Base.metadata.tables["media_asset_events"].c
    assert "provider_name" in Base.metadata.tables["media_asset_provider_syncs"].c
    assert "waba_id" in Base.metadata.tables["media_asset_provider_syncs"].c
    assert "sync_status" in Base.metadata.tables["media_asset_provider_syncs"].c
    assert "phone_number_id" in Base.metadata.tables["media_asset_provider_syncs"].c
    assert "provider_media_id" in Base.metadata.tables["media_asset_provider_syncs"].c
    assert "account_id" in SupportKnowledgeEntry.__table__.c
    assert "keywords_json" in SupportKnowledgeEntry.__table__.c
    assert "site_key" in H5Site.__table__.c
    assert "domain" in H5Site.__table__.c
    assert "account_id" in H5Site.__table__.c
    assert "account_id" in AppUser.__table__.c
    assert "public_user_id" in AppUser.__table__.c
    assert "registration_invite_code" in AppUser.__table__.c
    assert "account_id" in MemberProfile.__table__.c
    assert "member_no" in MemberProfile.__table__.c
    assert "password_hash" in MemberProfile.__table__.c
    assert "session_token_hash" in MemberAuthSession.__table__.c
    assert "refresh_token_hash" in MemberAuthSession.__table__.c
    assert "requested_phone_number" in MemberWhatsAppBindingRequest.__table__.c
    assert "start_count" in MemberWhatsAppBindingRequest.__table__.c
    assert "member_profile_id" in MemberVerificationRequest.__table__.c
    assert "review_note" in MemberVerificationRequest.__table__.c
    assert "reviewer_actor_id" in MemberVerificationRequest.__table__.c
    assert "verification_request_id" in MemberVerificationDocument.__table__.c
    assert "reward_ratio" in TaskPackageTemplate.__table__.c
    assert "product_name" in TaskPackageTemplateItem.__table__.c
    assert "status" in TaskPackageInstance.__table__.c
    assert "order_id" in TaskPackageInstanceItem.__table__.c
    assert "identity_type" in UserIdentity.__table__.c
    assert "identity_value" in UserIdentity.__table__.c
    assert "tag_key" in UserTag.__table__.c
    assert "scope_type" in Base.metadata.tables["audience_rule_sets"].c
    assert "rules_json" in Base.metadata.tables["audience_rule_sets"].c
    assert "task_key" in Base.metadata.tables["task_templates"].c
    assert "account_id" in Base.metadata.tables["task_templates"].c
    assert "claim_timeout_seconds" in Base.metadata.tables["task_templates"].c
    assert "account_id" in Base.metadata.tables["task_instances"].c
    assert "claim_deadline_at" in Base.metadata.tables["task_instances"].c
    assert "account_id" in Base.metadata.tables["task_proof_files"].c
    assert "object_key" in Base.metadata.tables["task_proof_files"].c
    assert "sha256" in Base.metadata.tables["task_proof_files"].c
    assert "account_id" in Base.metadata.tables["task_submissions"].c
    assert "submission_no" in Base.metadata.tables["task_submissions"].c
    assert "review_required_snapshot" in Base.metadata.tables["task_submissions"].c
    assert "account_id" in Base.metadata.tables["task_submission_proofs"].c
    assert "task_instance_id" in Base.metadata.tables["task_submission_proofs"].c
    assert "proof_role" in Base.metadata.tables["task_submission_proofs"].c
    assert "account_id" in Base.metadata.tables["task_review_decisions"].c
    assert "decision_source" in Base.metadata.tables["task_review_decisions"].c
    assert "account_id" in Base.metadata.tables["tickets"].c
    assert "review_decision_id" in Base.metadata.tables["tickets"].c
    assert "ticket_type" in Base.metadata.tables["tickets"].c
    assert "attachments_json" in Base.metadata.tables["ticket_messages"].c
    assert "system_balance" in WalletAccount.__table__.c
    assert "transaction_type" in WalletLedgerEntry.__table__.c
    assert "wallet_account_id" in WalletTransferRequest.__table__.c
    assert "credited_at" in WalletRechargeOrder.__table__.c
    assert "request_no" in WithdrawalRequest.__table__.c
    assert "withdrawal_request_id" in WithdrawalAuditLog.__table__.c
    assert "fragment_key" in FragmentDefinition.__table__.c
    assert "owned_count" in FragmentInventory.__table__.c
    assert "fragment_definition_id" in FragmentLedgerEntry.__table__.c
    assert "source" in FragmentDropLog.__table__.c
    assert "reward_name" in FragmentExchangeRequest.__table__.c
    assert "order_no" in MemberOrder.__table__.c
    assert "body_text" in MemberNotification.__table__.c
    assert "is_read" in MemberNotification.__table__.c
    assert "reference_id" in MemberNotification.__table__.c
    assert "receiver" in MailingRequest.__table__.c
    assert "fragment_exchange_request_id" in MailingRequest.__table__.c
    assert "task_package_template_id" in PromotionTaskTemplate.__table__.c
    assert "promotion_task_template_id" in PromotionTaskInstance.__table__.c
    assert "invite_code" in UserReferral.__table__.c
    assert "first_recharged_at" in UserReferral.__table__.c


def test_wallet_ledger_entries_keep_idempotent_reference_unique_constraint() -> None:
    unique_constraints = [
        constraint
        for constraint in WalletLedgerEntry.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert any(
        constraint.name == "uq_wallet_ledger_entries_reference_scope"
        and [column.name for column in constraint.columns]
        == [
            "account_id",
            "wallet_account_id",
            "user_id",
            "ledger_type",
            "transaction_type",
            "direction",
            "reference_type",
            "reference_id",
        ]
        for constraint in unique_constraints
    )


def test_whatsapp_daily_stats_unique_scope_includes_billable_dimension() -> None:
    constraints = [
        constraint
        for constraint in Base.metadata.tables["whatsapp_daily_stats"].constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name == "uq_whatsapp_daily_stats_scope"
    ]

    assert len(constraints) == 1
    assert "billable" in [column.name for column in constraints[0].columns]


def test_whatsapp_conversation_stats_unique_scope_includes_conversation_id() -> None:
    constraints = [
        constraint
        for constraint in Base.metadata.tables["whatsapp_conversation_stats"].constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_whatsapp_conversation_stats_scope"
    ]

    assert len(constraints) == 1
    column_names = [column.name for column in constraints[0].columns]
    assert "conversation_id" in column_names
    assert "billable" in column_names
    assert "billable_key" in column_names


def test_template_send_logs_phone_number_id_is_indexed() -> None:
    indexes = [
        index
        for index in Base.metadata.tables["template_send_logs"].indexes
        if isinstance(index, Index) and index.name == "ix_template_send_logs_phone_number_id"
    ]

    assert len(indexes) == 1
    assert [column.name for column in indexes[0].columns] == ["phone_number_id"]


def test_template_send_logs_phone_number_id_is_provider_snapshot_column() -> None:
    table = Base.metadata.tables["template_send_logs"]
    phone_number_column = table.c["phone_number_id"]

    assert isinstance(phone_number_column.type, String)
    assert phone_number_column.type.length == 128
    assert not any(
        isinstance(constraint, ForeignKeyConstraint)
        and [column.name for column in constraint.columns] == ["phone_number_id"]
        for constraint in table.constraints
    )


def test_meta_webhook_template_and_send_log_idempotency_indexes_exist() -> None:
    portfolio_indexes = {
        index.name: index for index in Base.metadata.tables["meta_business_portfolios"].indexes
    }
    phone_indexes = {
        index.name: index for index in Base.metadata.tables["whatsapp_phone_numbers"].indexes
    }
    webhook_indexes = {
        index.name: index for index in Base.metadata.tables["webhook_subscriptions"].indexes
    }
    template_indexes = {
        index.name: index for index in Base.metadata.tables["message_templates"].indexes
    }
    send_log_indexes = {
        index.name: index for index in Base.metadata.tables["template_send_logs"].indexes
    }

    assert [column.name for column in portfolio_indexes["ix_meta_business_portfolios_account_id"].columns] == [
        "account_id"
    ]
    assert [column.name for column in phone_indexes["ix_whatsapp_phone_numbers_account_id"].columns] == [
        "account_id"
    ]
    assert [column.name for column in phone_indexes["ix_whatsapp_phone_numbers_waba_id"].columns] == [
        "waba_id"
    ]
    assert [column.name for column in webhook_indexes["ix_webhook_subscriptions_account_id"].columns] == [
        "account_id"
    ]
    assert [column.name for column in webhook_indexes["ix_webhook_subscriptions_waba_id"].columns] == [
        "waba_id"
    ]

    webhook_index = webhook_indexes["uq_webhook_subscriptions_waba_callback"]
    assert webhook_index.unique is True
    assert [column.name for column in webhook_index.columns] == ["account_id", "waba_id", "callback_url"]

    meta_template_index = template_indexes["uq_message_templates_account_waba_meta_template_id"]
    assert meta_template_index.unique is True
    assert [column.name for column in meta_template_index.columns] == [
        "account_id",
        "waba_id",
        "meta_template_id",
    ]

    template_identity_index = template_indexes["uq_message_templates_account_waba_name_language"]
    assert template_identity_index.unique is True
    assert [column.name for column in template_identity_index.columns] == [
        "account_id",
        "waba_id",
        "name",
        "language",
    ]
    assert [column.name for column in template_indexes["ix_message_templates_waba_id"].columns] == [
        "waba_id"
    ]

    message_index = send_log_indexes["uq_template_send_logs_account_message_id"]
    assert message_index.unique is True
    assert [column.name for column in message_index.columns] == ["account_id", "message_id"]

    idempotency_index = send_log_indexes["uq_template_send_logs_account_idempotency_key"]
    assert idempotency_index.unique is True
    assert [column.name for column in idempotency_index.columns] == ["account_id", "idempotency_key"]


def test_message_templates_do_not_keep_global_meta_template_id_unique_constraint() -> None:
    template_table = Base.metadata.tables["message_templates"]
    global_meta_template_constraints = [
        constraint
        for constraint in template_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["meta_template_id"]
    ]

    assert global_meta_template_constraints == []


def test_member_notifications_migration_schema_contract() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "member_notifications_schema.db"
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            assert "member_notifications" in table_names

            columns = {column["name"] for column in inspector.get_columns("member_notifications")}
            assert columns == {
                "id",
                "account_id",
                "user_id",
                "member_profile_id",
                "site_id",
                "category",
                "title",
                "body_text",
                "reference_type",
                "reference_id",
                "is_read",
                "read_at",
                "metadata_json",
                "created_at",
                "updated_at",
            }

            indexes = {
                index["name"]: index for index in inspector.get_indexes("member_notifications")
            }
            assert "ix_member_notifications_account_id" in indexes
            assert "ix_member_notifications_user_id" in indexes
            assert "ix_member_notifications_member_profile_id" in indexes
            assert "ix_member_notifications_site_id" in indexes
            assert "ix_member_notifications_is_read" in indexes
            assert "ix_member_notifications_reference_id" in indexes

            foreign_keys = inspector.get_foreign_keys("member_notifications")
            assert any(
                fk["constrained_columns"] == ["account_id"]
                and fk["referred_table"] == "accounts"
                and fk["referred_columns"] == ["account_id"]
                for fk in foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["user_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id"]
                for fk in foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["member_profile_id"]
                and fk["referred_table"] == "member_profiles"
                and fk["referred_columns"] == ["id"]
                for fk in foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["site_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id"]
                for fk in foreign_keys
            )
        finally:
            engine.dispose()


def test_member_whatsapp_binding_requests_migration_schema_contract() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "member_whatsapp_binding_requests_schema.db"
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            assert "member_whatsapp_binding_requests" in table_names

            columns = {column["name"] for column in inspector.get_columns("member_whatsapp_binding_requests")}
            assert columns == {
                "id",
                "account_id",
                "user_id",
                "member_profile_id",
                "site_id",
                "status",
                "requested_phone_number",
                "start_count",
                "last_started_at",
                "bound_at",
                "last_error",
                "metadata_json",
                "created_at",
                "updated_at",
            }

            indexes = {
                index["name"]: index for index in inspector.get_indexes("member_whatsapp_binding_requests")
            }
            assert "ix_member_whatsapp_binding_requests_account_id" in indexes
            assert "ix_member_whatsapp_binding_requests_user_id" in indexes
            assert "ix_member_whatsapp_binding_requests_member_profile_id" in indexes
            assert "ix_member_whatsapp_binding_requests_site_id" in indexes

            unique_constraints = inspector.get_unique_constraints("member_whatsapp_binding_requests")
            assert any(
                constraint["name"] == "uq_member_whatsapp_binding_requests_account_member_profile"
                and constraint["column_names"] == ["account_id", "member_profile_id"]
                for constraint in unique_constraints
            )

            foreign_keys = inspector.get_foreign_keys("member_whatsapp_binding_requests")
            assert any(
                fk["constrained_columns"] == ["account_id"]
                and fk["referred_table"] == "accounts"
                and fk["referred_columns"] == ["account_id"]
                for fk in foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["user_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id"]
                for fk in foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["member_profile_id"]
                and fk["referred_table"] == "member_profiles"
                and fk["referred_columns"] == ["id"]
                for fk in foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["site_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id"]
                for fk in foreign_keys
            )
        finally:
            engine.dispose()


def test_fragment_and_mailing_migration_schema_contract() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "fragment_and_mailing_schema.db"
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            assert "fragment_definitions" in table_names
            assert "fragment_inventory" in table_names
            assert "fragment_ledger_entries" in table_names
            assert "fragment_drop_logs" in table_names
            assert "fragment_exchange_requests" in table_names
            assert "mailing_requests" in table_names

            fragment_definition_columns = {
                column["name"] for column in inspector.get_columns("fragment_definitions")
            }
            assert fragment_definition_columns == {
                "id",
                "account_id",
                "fragment_key",
                "name",
                "rarity",
                "color",
                "required_count",
                "reward_name",
                "status",
                "metadata_json",
                "created_at",
                "updated_at",
            }

            fragment_definition_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_definitions")
            }
            assert "ix_fragment_definitions_account_id" in fragment_definition_indexes
            assert "ix_fragment_definitions_fragment_key" in fragment_definition_indexes

            fragment_definition_uniques = inspector.get_unique_constraints("fragment_definitions")
            assert any(
                constraint["name"] == "uq_fragment_definitions_account_key"
                and constraint["column_names"] == ["account_id", "fragment_key"]
                for constraint in fragment_definition_uniques
            )

            fragment_inventory_columns = {
                column["name"] for column in inspector.get_columns("fragment_inventory")
            }
            assert fragment_inventory_columns == {
                "id",
                "account_id",
                "user_id",
                "member_profile_id",
                "fragment_definition_id",
                "owned_count",
                "created_at",
                "updated_at",
            }

            fragment_inventory_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_inventory")
            }
            assert "ix_fragment_inventory_account_id" in fragment_inventory_indexes
            assert "ix_fragment_inventory_user_id" in fragment_inventory_indexes
            assert "ix_fragment_inventory_member_profile_id" in fragment_inventory_indexes
            assert "ix_fragment_inventory_fragment_definition_id" in fragment_inventory_indexes

            fragment_ledger_columns = {
                column["name"] for column in inspector.get_columns("fragment_ledger_entries")
            }
            assert fragment_ledger_columns == {
                "id",
                "account_id",
                "user_id",
                "member_profile_id",
                "fragment_definition_id",
                "entry_type",
                "direction",
                "quantity",
                "source_type",
                "source_id",
                "note",
                "created_at",
                "updated_at",
            }

            fragment_ledger_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_ledger_entries")
            }
            assert "ix_fragment_ledger_entries_account_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_fragment_definition_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_member_profile_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_user_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_source_id" in fragment_ledger_indexes

            fragment_drop_log_columns = {
                column["name"] for column in inspector.get_columns("fragment_drop_logs")
            }
            assert fragment_drop_log_columns == {
                "id",
                "account_id",
                "user_id",
                "member_profile_id",
                "fragment_definition_id",
                "source",
                "fragment_ledger_entry_id",
                "source_id",
                "created_at",
                "updated_at",
            }

            fragment_drop_log_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_drop_logs")
            }
            assert "ix_fragment_drop_logs_account_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_user_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_member_profile_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_fragment_definition_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_fragment_ledger_entry_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_source_id" in fragment_drop_log_indexes

            fragment_exchange_columns = {
                column["name"] for column in inspector.get_columns("fragment_exchange_requests")
            }
            assert fragment_exchange_columns == {
                "id",
                "account_id",
                "user_id",
                "member_profile_id",
                "reward_name",
                "status",
                "mailing_request_id",
                "metadata_json",
                "created_at",
                "updated_at",
            }

            fragment_exchange_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_exchange_requests")
            }
            assert "ix_fragment_exchange_requests_account_id" in fragment_exchange_indexes
            assert "ix_fragment_exchange_requests_user_id" in fragment_exchange_indexes
            assert "ix_fragment_exchange_requests_member_profile_id" in fragment_exchange_indexes
            assert "ix_fragment_exchange_requests_mailing_request_id" in fragment_exchange_indexes

            mailing_request_columns = {
                column["name"] for column in inspector.get_columns("mailing_requests")
            }
            assert mailing_request_columns == {
                "id",
                "account_id",
                "user_id",
                "member_profile_id",
                "fragment_exchange_request_id",
                "reward_name",
                "status",
                "receiver",
                "phone",
                "country",
                "province",
                "city",
                "address_line",
                "tracking_no",
                "submitted_at",
                "packed_at",
                "shipped_at",
                "delivered_at",
                "completed_at",
                "metadata_json",
                "created_at",
                "updated_at",
            }

            mailing_request_indexes = {
                index["name"]: index for index in inspector.get_indexes("mailing_requests")
            }
            assert "ix_mailing_requests_account_id" in mailing_request_indexes
            assert "ix_mailing_requests_user_id" in mailing_request_indexes
            assert "ix_mailing_requests_member_profile_id" in mailing_request_indexes
            assert "ix_mailing_requests_fragment_exchange_request_id" in mailing_request_indexes
        finally:
            engine.dispose()


def test_message_templates_reject_duplicate_official_waba_scope_after_local_waba_rebind(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        account_id = "schema-template-waba-snapshot-account"
        session.add(
            Account(
                account_id=account_id,
                display_name="Schema Template Snapshot Account",
                provider_type="whatsapp",
            )
        )
        session.commit()

        session.add_all(
            [
                WhatsAppBusinessAccount(
                    id="schema-waba-legacy-row",
                    account_id=account_id,
                    waba_id="waba-schema-template-legacy",
                    onboarding_mode="manual",
                    token_source="system_user",
                    access_token="token-legacy",
                    webhook_subscribed=False,
                    is_active=True,
                    ai_enabled=True,
                ),
                WhatsAppBusinessAccount(
                    id="schema-waba-current-row",
                    account_id=account_id,
                    waba_id="waba-schema-template-official",
                    onboarding_mode="manual",
                    token_source="system_user",
                    access_token="token-current",
                    webhook_subscribed=False,
                    is_active=True,
                    ai_enabled=True,
                ),
            ]
        )
        session.commit()

        session.add(
            MessageTemplate(
                id="schema-template-stale-row",
                account_id=account_id,
                waba_account_id="schema-waba-legacy-row",
                waba_id="waba-schema-template-official",
                meta_template_id="meta-schema-template-1",
                name="shipping_update",
                language="en",
                category="UTILITY",
                status="APPROVED",
                components={"body_text": "Legacy local row snapshot"},
            )
        )
        session.commit()

        session.add(
            MessageTemplate(
                id="schema-template-current-row",
                account_id=account_id,
                waba_account_id="schema-waba-current-row",
                waba_id="waba-schema-template-official",
                meta_template_id="meta-schema-template-1",
                name="shipping_update",
                language="en",
                category="UTILITY",
                status="APPROVED",
                components={"body_text": "Rebound local row snapshot"},
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_provider_status_event_buffer_constraints_and_indexes_exist() -> None:
    table = ProviderStatusEventBuffer.__table__
    constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_provider_status_buffer_status"
    ]
    assert len(constraints) == 1
    assert [column.name for column in constraints[0].columns] == [
        "account_id",
        "provider_name",
        "provider_message_id",
        "external_status",
    ]

    indexes = {index.name: index for index in table.indexes if isinstance(index, Index)}
    assert [column.name for column in indexes["ix_provider_status_buffer_account_state"].columns] == [
        "account_id",
        "replay_state",
        "last_seen_at",
    ]
    assert [column.name for column in indexes["ix_provider_status_buffer_provider_message"].columns] == [
        "account_id",
        "provider_name",
        "provider_message_id",
    ]


def test_message_events_provider_status_scope_columns_and_idempotency_index_exist() -> None:
    table = MessageEvent.__table__

    for column_name in (
        "provider_name",
        "waba_id",
        "phone_number_id",
        "provider_event_id",
        "occurred_at",
    ):
        assert column_name in table.c

    indexes = {index.name: index for index in table.indexes if isinstance(index, Index)}
    idempotency_index = indexes["uq_message_events_account_provider_event"]
    assert idempotency_index.unique is True
    assert [column.name for column in idempotency_index.columns] == [
        "account_id",
        "provider_name",
        "provider_event_id",
    ]


def test_media_asset_event_waba_scope_is_indexed() -> None:
    table = MediaAssetEvent.__table__
    indexes = {index.name: index for index in table.indexes if isinstance(index, Index)}

    assert "waba_id" in table.c
    assert "ix_media_asset_events_waba_id" in indexes
    assert [column.name for column in indexes["ix_media_asset_events_waba_id"].columns] == ["waba_id"]
    assert "ix_media_asset_events_provider_media_id" in indexes
    assert [column.name for column in indexes["ix_media_asset_events_provider_media_id"].columns] == [
        "provider_media_id"
    ]


def test_media_asset_provider_sync_null_scope_unique_index_exists() -> None:
    table = MediaAssetProviderSync.__table__
    indexes = {index.name: index for index in table.indexes if isinstance(index, Index)}

    assert "ix_media_asset_provider_syncs_provider_media_id" in indexes
    assert [column.name for column in indexes["ix_media_asset_provider_syncs_provider_media_id"].columns] == [
        "provider_media_id"
    ]
    index = indexes["ux_media_asset_provider_syncs_scope_nulls_not_distinct"]
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "asset_id",
        "provider_name",
        "phone_number_id",
    ]


def test_template_send_log_accepts_legacy_provider_phone_number_snapshot(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        account_id = "schema-template-send-log-provider-phone-account"
        session.add(
            Account(
                account_id=account_id,
                display_name="Schema Template Send Log Provider Phone",
                provider_type="whatsapp",
            )
        )
        session.commit()

        session.add(
            MessageTemplate(
                id="schema-template-send-log-provider-phone-template",
                account_id=account_id,
                waba_id="waba-schema-template-send-log-provider-phone",
                name="provider_phone_snapshot",
                language="en",
                category="UTILITY",
                status="APPROVED",
                components={"body_text": "Hello {{first_name}}"},
            )
        )
        session.commit()

        session.add(
            TemplateSendLog(
                account_id=account_id,
                template_id="schema-template-send-log-provider-phone-template",
                waba_id="waba-schema-template-send-log-provider-phone",
                template_name="provider_phone_snapshot",
                template_language="en",
                template_category="UTILITY",
                phone_number_id="provider-phone-id-template-send-log",
                wa_id="wa-schema-template-send-log-provider-phone",
                message_id="msg-schema-template-send-log-provider-phone",
                status="SENT",
                sent_at=utc_now(),
                last_status_at=utc_now(),
            )
        )
        session.commit()
    finally:
        session.close()


def test_template_send_log_phone_relationship_supports_provider_snapshot_and_legacy_local_id(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        account_id = "schema-template-send-log-phone-relationship-account"
        session.add(
            Account(
                account_id=account_id,
                display_name="Schema Template Send Log Phone Relationship",
                provider_type="whatsapp",
            )
        )
        session.commit()

        portfolio = MetaBusinessPortfolio(
            account_id=account_id,
            meta_business_portfolio_id="portfolio-schema-template-send-log-phone-relationship",
            display_name="Schema Send Log Relationship Portfolio",
            status="active",
        )
        session.add(portfolio)
        session.flush()

        waba = WhatsAppBusinessAccount(
            account_id=account_id,
            portfolio_id=portfolio.id,
            waba_id="waba-schema-template-send-log-phone-relationship",
            onboarding_mode="manual",
            token_source="manual",
        )
        session.add(waba)
        session.flush()

        phone_number = WhatsAppPhoneNumber(
            account_id=account_id,
            waba_account_id=waba.id,
            waba_id=waba.waba_id,
            phone_number_id="provider-phone-schema-send-log-relationship",
            display_phone_number="+1 555 400 0101",
            verified_name="Schema Send Log Relationship Number",
            quality_rating="GREEN",
            is_registered=True,
        )
        session.add(phone_number)
        session.flush()

        provider_snapshot_log = TemplateSendLog(
            account_id=account_id,
            waba_id=waba.waba_id,
            template_name="provider_snapshot_relationship",
            template_language="en",
            template_category="UTILITY",
            phone_number_id=phone_number.phone_number_id,
            wa_id="wa-schema-send-log-provider-snapshot",
            message_id="msg-schema-send-log-provider-snapshot",
            status="SENT",
            sent_at=utc_now(),
            last_status_at=utc_now(),
        )
        legacy_local_id_log = TemplateSendLog(
            account_id=account_id,
            waba_id=waba.waba_id,
            template_name="legacy_local_id_relationship",
            template_language="en",
            template_category="UTILITY",
            phone_number_id=phone_number.id,
            wa_id="wa-schema-send-log-legacy-local-id",
            message_id="msg-schema-send-log-legacy-local-id",
            status="SENT",
            sent_at=utc_now(),
            last_status_at=utc_now(),
        )
        session.add_all([provider_snapshot_log, legacy_local_id_log])
        session.commit()

        provider_snapshot_log = session.get(TemplateSendLog, provider_snapshot_log.id)
        legacy_local_id_log = session.get(TemplateSendLog, legacy_local_id_log.id)
        session.refresh(phone_number)

        assert provider_snapshot_log is not None
        assert legacy_local_id_log is not None
        assert provider_snapshot_log.phone_number is not None
        assert provider_snapshot_log.phone_number.id == phone_number.id
        assert legacy_local_id_log.phone_number is not None
        assert legacy_local_id_log.phone_number.id == phone_number.id
        assert {item.id for item in phone_number.template_send_logs} == {
            provider_snapshot_log.id,
            legacy_local_id_log.id,
        }
    finally:
        session.close()


def test_task_submission_review_ticket_constraints_exist() -> None:
    instance_constraints = [
        constraint
        for constraint in Base.metadata.tables["task_instances"].constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_task_instances_id_account_scope"
    ]
    assert len(instance_constraints) == 1
    assert [column.name for column in instance_constraints[0].columns] == [
        "id",
        "account_id",
    ]

    submission_constraints = [
        constraint
        for constraint in Base.metadata.tables["task_submissions"].constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_task_submissions_instance_attempt"
    ]
    assert len(submission_constraints) == 1
    assert [column.name for column in submission_constraints[0].columns] == [
        "task_instance_id",
        "submission_no",
    ]

    proof_constraints = [
        constraint
        for constraint in Base.metadata.tables["task_submission_proofs"].constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_task_submission_proofs_scope"
    ]
    assert len(proof_constraints) == 1
    assert [column.name for column in proof_constraints[0].columns] == [
        "submission_id",
        "proof_file_id",
    ]

    proof_file_scope_constraints = [
        constraint
        for constraint in Base.metadata.tables["task_proof_files"].constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_task_proof_files_id_task_instance_account_scope"
    ]
    assert len(proof_file_scope_constraints) == 1
    assert [column.name for column in proof_file_scope_constraints[0].columns] == [
        "id",
        "task_instance_id",
        "account_id",
    ]

    decision_constraints = [
        constraint
        for constraint in Base.metadata.tables["task_review_decisions"].constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_task_review_decisions_id_submission_account_scope"
    ]
    assert len(decision_constraints) == 1
    assert [column.name for column in decision_constraints[0].columns] == [
        "id",
        "task_instance_id",
        "submission_id",
        "account_id",
    ]

    submission_scope_constraints = [
        constraint
        for constraint in Base.metadata.tables["task_submissions"].constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_task_submissions_id_instance_account_scope"
    ]
    assert len(submission_scope_constraints) == 1
    assert [column.name for column in submission_scope_constraints[0].columns] == [
        "id",
        "task_instance_id",
        "account_id",
    ]


def test_task_submission_and_ticket_partial_unique_indexes_exist() -> None:
    submission_indexes = [
        index
        for index in Base.metadata.tables["task_submissions"].indexes
        if isinstance(index, Index) and index.name == "uq_task_submissions_active_per_task_instance"
    ]
    assert len(submission_indexes) == 1
    assert [column.name for column in submission_indexes[0].columns] == ["task_instance_id"]

    ticket_indexes = [
        index
        for index in Base.metadata.tables["tickets"].indexes
        if isinstance(index, Index) and index.name == "uq_tickets_active_appeal_per_task_instance"
    ]
    assert len(ticket_indexes) == 1
    assert [column.name for column in ticket_indexes[0].columns] == ["linked_task_instance_id"]


def test_task_submission_partial_unique_index_keeps_rejected_status_guard() -> None:
    submission_index = next(
        index
        for index in Base.metadata.tables["task_submissions"].indexes
        if isinstance(index, Index) and index.name == "uq_task_submissions_active_per_task_instance"
    )

    sqlite_where_clause = submission_index.dialect_options["sqlite"].get("where")
    postgresql_where_clause = submission_index.dialect_options["postgresql"].get("where")
    sqlite_where = str(sqlite_where_clause) if sqlite_where_clause is not None else ""
    postgresql_where = (
        str(postgresql_where_clause) if postgresql_where_clause is not None else ""
    )

    assert "'submitted'" in sqlite_where
    assert "'under_review'" in sqlite_where
    assert "'rejected'" in sqlite_where
    assert "'submitted'" in postgresql_where
    assert "'under_review'" in postgresql_where
    assert "'rejected'" in postgresql_where


def test_task_workflow_enum_check_constraints_exist() -> None:
    table_constraints = {
        "task_instances": "ck_task_instances_status",
        "task_submissions": "ck_task_submissions_status",
        "task_review_decisions": "ck_task_review_decisions_decision",
        "tickets": "ck_tickets_ticket_type",
    }

    for table_name, constraint_suffix in table_constraints.items():
        constraints = [
            constraint
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, CheckConstraint)
            and isinstance(constraint.name, str)
            and constraint.name.endswith(constraint_suffix)
        ]
        assert len(constraints) == 1


def test_ticket_status_check_constraint_keeps_legacy_waiting_user_compatibility() -> None:
    constraints = [
        constraint
        for constraint in Base.metadata.tables["tickets"].constraints
        if isinstance(constraint, CheckConstraint)
        and isinstance(constraint.name, str)
        and constraint.name.endswith("ck_tickets_status")
    ]
    assert len(constraints) == 1
    sql_text = str(constraints[0].sqltext)
    assert "'waiting_user'" in sql_text
    assert "'pending_user'" in sql_text


def test_ticket_status_check_allows_legacy_waiting_user_rows() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    try:
        with factory() as session:
            account = Account(
                account_id="schema-ticket-legacy-waiting-user",
                display_name="Schema Ticket Legacy Waiting User",
                provider_type="mock",
            )
            site = H5Site(
                id="schema-site-ticket-legacy-waiting-user",
                account_id=account.account_id,
                site_key="schema-site-ticket-legacy-waiting-user",
                domain="schema-ticket-legacy-waiting-user.example.com",
                brand_name="Schema Ticket Legacy Waiting User",
                default_language="zh-CN",
                status="active",
            )
            user = AppUser(
                id="schema-user-ticket-legacy-waiting-user",
                account_id=account.account_id,
                public_user_id="schema-public-ticket-legacy-waiting-user",
                registration_site_id=site.id,
                display_name="Schema Legacy Waiting User",
                language_code="zh-CN",
            )
            ticket = Ticket(
                id="schema-ticket-legacy-waiting-user",
                account_id=account.account_id,
                ticket_no="TKT-SCHEMA-LEGACY-WAITING",
                user_id=user.id,
                site_id=site.id,
                ticket_type="help",
                status="waiting_user",
                priority="normal",
                title="Legacy waiting_user compatibility",
                latest_reply_at=utc_now(),
                is_active=True,
            )
            session.add_all([account, site, user, ticket])
            session.commit()

            persisted = session.get(Ticket, ticket.id)
            assert persisted is not None
            assert persisted.status == "waiting_user"
    finally:
        engine.dispose()


def test_meta_status_check_constraints_exist_in_orm_metadata() -> None:
    for table_name, expected_constraints in META_STATUS_CHECKS.items():
        constraints_by_name = {
            constraint.name: constraint
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, CheckConstraint)
        }

        for constraint_name, (column_name, allowed_values) in expected_constraints.items():
            assert constraint_name in constraints_by_name
            sql_text = str(constraints_by_name[constraint_name].sqltext)
            assert column_name in sql_text
            for allowed_value in allowed_values:
                assert f"'{allowed_value}'" in sql_text


def test_task_workflow_linkage_constraints_exist() -> None:
    submission_proof_submission_scope_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["task_submission_proofs"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_task_submission_proofs_submission_account_scope"
    ]
    assert len(submission_proof_submission_scope_foreign_keys) == 1
    assert [
        element.parent.name
        for element in submission_proof_submission_scope_foreign_keys[0].elements
    ] == ["submission_id", "task_instance_id", "account_id"]

    submission_proof_file_scope_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["task_submission_proofs"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_task_submission_proofs_proof_file_account_scope"
    ]
    assert len(submission_proof_file_scope_foreign_keys) == 1
    assert [
        element.parent.name
        for element in submission_proof_file_scope_foreign_keys[0].elements
    ] == ["proof_file_id", "task_instance_id", "account_id"]

    proof_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["task_proof_files"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_task_proof_files_task_instance_account_scope"
    ]
    assert len(proof_foreign_keys) == 1
    assert [element.parent.name for element in proof_foreign_keys[0].elements] == [
        "task_instance_id",
        "account_id",
    ]

    submission_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["task_submissions"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_task_submissions_task_instance_account_scope"
    ]
    assert len(submission_foreign_keys) == 1
    assert [element.parent.name for element in submission_foreign_keys[0].elements] == [
        "task_instance_id",
        "account_id",
    ]

    submission_proof_submission_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["task_submission_proofs"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_task_submission_proofs_submission_account_scope"
    ]
    assert len(submission_proof_submission_foreign_keys) == 1
    assert [element.parent.name for element in submission_proof_submission_foreign_keys[0].elements] == [
        "submission_id",
        "task_instance_id",
        "account_id",
    ]

    submission_proof_file_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["task_submission_proofs"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_task_submission_proofs_proof_file_account_scope"
    ]
    assert len(submission_proof_file_foreign_keys) == 1
    assert [element.parent.name for element in submission_proof_file_foreign_keys[0].elements] == [
        "proof_file_id",
        "task_instance_id",
        "account_id",
    ]

    decision_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["task_review_decisions"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_task_review_decisions_submission_account_scope"
    ]
    assert len(decision_foreign_keys) == 1
    assert [element.parent.name for element in decision_foreign_keys[0].elements] == [
        "submission_id",
        "task_instance_id",
        "account_id",
    ]

    ticket_submission_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["tickets"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_tickets_submission_account_scope"
    ]
    assert len(ticket_submission_foreign_keys) == 1
    assert [element.parent.name for element in ticket_submission_foreign_keys[0].elements] == [
        "linked_submission_id",
        "linked_task_instance_id",
        "account_id",
    ]

    ticket_decision_foreign_keys = [
        constraint
        for constraint in Base.metadata.tables["tickets"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_tickets_review_decision_account_scope"
    ]
    assert len(ticket_decision_foreign_keys) == 1
    assert [element.parent.name for element in ticket_decision_foreign_keys[0].elements] == [
        "review_decision_id",
        "linked_task_instance_id",
        "linked_submission_id",
        "account_id",
    ]

    ticket_checks = {
        constraint.name
        for constraint in Base.metadata.tables["tickets"].constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert any(name.endswith("ck_tickets_linked_submission_requires_task") for name in ticket_checks)
    assert any(name.endswith("ck_tickets_review_decision_requires_submission") for name in ticket_checks)
    assert any(name.endswith("ck_tickets_appeal_requires_review_chain") for name in ticket_checks)


def test_h5_task_workflow_account_scope_columns_reference_accounts() -> None:
    scoped_tables = (
        H5Site.__table__,
        TaskTemplate.__table__,
        TaskInstance.__table__,
        TaskProofFile.__table__,
        TaskSubmission.__table__,
        TaskSubmissionProof.__table__,
        TaskReviewDecision.__table__,
        Ticket.__table__,
    )

    for table in scoped_tables:
        assert "account_id" in table.c
        foreign_keys = {
            (fk.parent.name, fk.column.table.name, fk.column.name)
            for fk in table.foreign_keys
            if fk.parent.name == "account_id"
        }
        assert ("account_id", "accounts", "account_id") in foreign_keys

    assert TaskInstance.__table__.c.account_id.nullable is False
    assert TaskProofFile.__table__.c.account_id.nullable is False
    assert TaskSubmission.__table__.c.account_id.nullable is False
    assert TaskSubmissionProof.__table__.c.account_id.nullable is False
    assert TaskReviewDecision.__table__.c.account_id.nullable is False
    assert Ticket.__table__.c.account_id.nullable is False


def test_task_h5_parent_scope_uniques_and_composite_foreign_keys_exist() -> None:
    parent_unique_constraints = {
        "h5_sites": ["id", "account_id"],
        "app_users": ["id", "account_id"],
        "task_templates": ["id", "account_id"],
    }

    for table_name, expected_columns in parent_unique_constraints.items():
        constraints = [
            constraint
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, UniqueConstraint)
            and [column.name for column in constraint.columns] == expected_columns
        ]
        assert len(constraints) == 1

    scoped_foreign_keys = {
        "app_users": {
            "fk_app_users_registration_site_account_scope": ["registration_site_id", "account_id"],
        },
        "task_instances": {
            "fk_task_instances_template_account_scope": ["template_id", "account_id"],
            "fk_task_instances_user_account_scope": ["user_id", "account_id"],
            "fk_task_instances_site_account_scope": ["site_id", "account_id"],
        },
        "task_proof_files": {
            "fk_task_proof_files_user_account_scope": ["user_id", "account_id"],
            "fk_task_proof_files_site_account_scope": ["site_id", "account_id"],
        },
        "task_submissions": {
            "fk_task_submissions_submitted_by_user_account_scope": ["submitted_by_user_id", "account_id"],
            "fk_task_submissions_site_account_scope": ["site_id", "account_id"],
        },
        "task_review_decisions": {
            "fk_task_review_decisions_task_instance_account_scope": ["task_instance_id", "account_id"],
        },
        "tickets": {
            "fk_tickets_task_instance_account_scope": ["linked_task_instance_id", "account_id"],
            "fk_tickets_user_account_scope": ["user_id", "account_id"],
            "fk_tickets_site_account_scope": ["site_id", "account_id"],
        },
    }

    for table_name, expected_constraints in scoped_foreign_keys.items():
        constraints_by_name = {
            constraint.name: constraint
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        for constraint_name, expected_columns in expected_constraints.items():
            assert constraint_name in constraints_by_name
            assert [element.parent.name for element in constraints_by_name[constraint_name].elements] == expected_columns


def test_task_submission_proof_scope_constraints_reject_cross_task_or_cross_account_links(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        session.execute(text("PRAGMA foreign_keys = ON"))
        _seed_task_workflow_scope(
            session,
            account_id="schema-task-proof-account-a",
            user_id="schema-task-proof-user-a",
            template_id="schema-task-proof-template-a",
            instance_id="schema-task-proof-instance-a",
        )
        _seed_task_workflow_scope(
            session,
            account_id="schema-task-proof-account-b",
            user_id="schema-task-proof-user-b",
            template_id="schema-task-proof-template-b",
            instance_id="schema-task-proof-instance-b",
        )

        session.add_all(
            [
                TaskProofFile(
                    id="schema-task-proof-file-a",
                    account_id="schema-task-proof-account-a",
                    task_instance_id="schema-task-proof-instance-a",
                    user_id="schema-task-proof-user-a",
                    status="uploaded",
                    storage_provider="local",
                    object_key="proof/a",
                    mime_type="image/png",
                    original_filename="proof-a.png",
                    size_bytes=128,
                    sha256="sha-proof-a",
                    uploaded_by_type="user",
                ),
                TaskProofFile(
                    id="schema-task-proof-file-b",
                    account_id="schema-task-proof-account-b",
                    task_instance_id="schema-task-proof-instance-b",
                    user_id="schema-task-proof-user-b",
                    status="uploaded",
                    storage_provider="local",
                    object_key="proof/b",
                    mime_type="image/png",
                    original_filename="proof-b.png",
                    size_bytes=256,
                    sha256="sha-proof-b",
                    uploaded_by_type="user",
                ),
                TaskSubmission(
                    id="schema-task-proof-submission-a",
                    account_id="schema-task-proof-account-a",
                    task_instance_id="schema-task-proof-instance-a",
                    submitted_by_user_id="schema-task-proof-user-a",
                    submission_no=1,
                    status="submitted",
                    payload_json={},
                ),
            ]
        )
        session.commit()

        session.add(
            TaskSubmissionProof(
                id="schema-task-proof-link-valid",
                submission_id="schema-task-proof-submission-a",
                proof_file_id="schema-task-proof-file-a",
                task_instance_id="schema-task-proof-instance-a",
                account_id="schema-task-proof-account-a",
                proof_role="evidence",
            )
        )
        session.commit()

        session.add(
            TaskSubmissionProof(
                id="schema-task-proof-link-cross-task",
                submission_id="schema-task-proof-submission-a",
                proof_file_id="schema-task-proof-file-b",
                task_instance_id="schema-task-proof-instance-a",
                account_id="schema-task-proof-account-a",
                proof_role="evidence",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            TaskSubmissionProof(
                id="schema-task-proof-link-cross-account",
                submission_id="schema-task-proof-submission-a",
                proof_file_id="schema-task-proof-file-a",
                task_instance_id="schema-task-proof-instance-a",
                account_id="schema-task-proof-account-b",
                proof_role="evidence",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_task_review_decision_and_ticket_scope_constraints_reject_mismatched_links(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        session.execute(text("PRAGMA foreign_keys = ON"))
        _seed_task_workflow_scope(
            session,
            account_id="schema-task-account-a",
            user_id="schema-task-user-a",
            template_id="schema-task-template-a",
            instance_id="schema-task-instance-a",
        )
        _seed_task_workflow_scope(
            session,
            account_id="schema-task-account-b",
            user_id="schema-task-user-b",
            template_id="schema-task-template-b",
            instance_id="schema-task-instance-b",
        )

        session.add(
            TaskSubmission(
                id="schema-task-submission-b",
                account_id="schema-task-account-b",
                task_instance_id="schema-task-instance-b",
                submitted_by_user_id="schema-task-user-b",
                submission_no=1,
                status="rejected",
                payload_json={},
            )
        )
        session.commit()

        session.add(
            TaskReviewDecision(
                id="schema-task-review-mismatch",
                account_id="schema-task-account-a",
                task_instance_id="schema-task-instance-a",
                submission_id="schema-task-submission-b",
                decision="rejected",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            TaskSubmission(
                id="schema-task-submission-a",
                account_id="schema-task-account-a",
                task_instance_id="schema-task-instance-a",
                submitted_by_user_id="schema-task-user-a",
                submission_no=1,
                status="rejected",
                payload_json={},
            )
        )
        session.commit()

        session.add(
            TaskReviewDecision(
                id="schema-task-review-a",
                account_id="schema-task-account-a",
                task_instance_id="schema-task-instance-a",
                submission_id="schema-task-submission-a",
                decision="rejected",
            )
        )
        session.commit()

        session.add(
            Ticket(
                id="schema-ticket-missing-chain",
                account_id="schema-task-account-a",
                ticket_no="TKT-SCHEMA-MISSING-CHAIN",
                user_id="schema-task-user-a",
                ticket_type="appeal",
                status="open",
                title="Missing appeal chain",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Ticket(
                id="schema-ticket-mismatched-submission",
                account_id="schema-task-account-a",
                ticket_no="TKT-SCHEMA-MISMATCHED-SUB",
                linked_task_instance_id="schema-task-instance-a",
                linked_submission_id="schema-task-submission-b",
                review_decision_id="schema-task-review-a",
                user_id="schema-task-user-a",
                ticket_type="appeal",
                status="open",
                title="Mismatched appeal chain",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def _seed_task_workflow_scope(
    session: Session,
    *,
    account_id: str,
    user_id: str,
    template_id: str,
    instance_id: str,
) -> None:
    session.add(
        Account(
            account_id=account_id,
            display_name=account_id,
            provider_type="whatsapp",
        )
    )
    session.add(
        AppUser(
            id=user_id,
            account_id=account_id,
            public_user_id=f"public-{user_id}",
            language_code="zh-CN",
        )
    )
    session.add(
        TaskTemplate(
            id=template_id,
            account_id=account_id,
            task_key=f"task-{template_id}",
            name=template_id,
            title=template_id,
        )
    )
    session.add(
        TaskInstance(
            id=instance_id,
            account_id=account_id,
            template_id=template_id,
            user_id=user_id,
            status="rejected",
        )
    )
    session.commit()


def test_meta_portfolio_account_scope_column_references_accounts() -> None:
    table = MetaBusinessPortfolio.__table__

    assert "account_id" in table.c
    assert table.c["account_id"].nullable is False
    foreign_keys = {
        (fk.parent.name, fk.column.table.name, fk.column.name)
        for fk in table.foreign_keys
        if fk.parent.name == "account_id"
    }
    assert ("account_id", "accounts", "account_id") in foreign_keys


def test_meta_portfolio_and_waba_metadata_require_account_scoped_portfolio_binding() -> None:
    portfolio_table = MetaBusinessPortfolio.__table__
    waba_table = WhatsAppBusinessAccount.__table__

    portfolio_scope_uniques = [
        constraint
        for constraint in portfolio_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_meta_business_portfolios_id_account"
    ]
    assert len(portfolio_scope_uniques) == 1
    assert [column.name for column in portfolio_scope_uniques[0].columns] == ["id", "account_id"]

    portfolio_scope_foreign_keys = [
        constraint
        for constraint in waba_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and [column.name for column in constraint.columns] == ["portfolio_id", "account_id"]
    ]
    assert len(portfolio_scope_foreign_keys) == 1
    assert [element.column.name for element in portfolio_scope_foreign_keys[0].elements] == [
        "id",
        "account_id",
    ]


def test_embedded_signup_session_webhook_pointer_column_is_indexed_and_references_subscription() -> None:
    table = EmbeddedSignupSession.__table__
    indexes = {index.name: index for index in table.indexes if isinstance(index, Index)}
    foreign_keys = {
        (fk.parent.name, fk.column.table.name, fk.column.name)
        for fk in table.foreign_keys
        if fk.parent.name == "created_webhook_subscription_id"
    }

    assert [column.name for column in indexes["ix_embedded_signup_sessions_created_webhook_subscription_id"].columns] == [
        "created_webhook_subscription_id"
    ]
    assert ("created_webhook_subscription_id", "webhook_subscriptions", "id") in foreign_keys


def test_meta_child_scope_constraints_reference_parent_account_scope() -> None:
    waba_unique_constraints = [
        constraint
        for constraint in WhatsAppBusinessAccount.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["id", "account_id"]
    ]
    assert len(waba_unique_constraints) == 1

    webhook_unique_constraints = [
        constraint
        for constraint in WebhookSubscription.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns] == ["id", "account_id"]
    ]
    assert len(webhook_unique_constraints) == 1

    phone_scope_foreign_keys = [
        constraint
        for constraint in WhatsAppPhoneNumber.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and [column.name for column in constraint.columns] == ["waba_account_id", "account_id"]
    ]
    assert len(phone_scope_foreign_keys) == 1
    assert [element.column.name for element in phone_scope_foreign_keys[0].elements] == ["id", "account_id"]

    webhook_scope_foreign_keys = [
        constraint
        for constraint in WebhookSubscription.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and [column.name for column in constraint.columns] == ["waba_account_id", "account_id"]
    ]
    assert len(webhook_scope_foreign_keys) == 1
    assert [element.column.name for element in webhook_scope_foreign_keys[0].elements] == ["id", "account_id"]

    template_scope_foreign_keys = [
        constraint
        for constraint in MessageTemplate.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and [column.name for column in constraint.columns] == ["waba_account_id", "account_id"]
    ]
    assert len(template_scope_foreign_keys) == 1
    assert [element.column.name for element in template_scope_foreign_keys[0].elements] == ["id", "account_id"]

    embedded_signup_waba_scope_foreign_keys = [
        constraint
        for constraint in EmbeddedSignupSession.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and [column.name for column in constraint.columns] == ["waba_account_id", "account_id"]
    ]
    assert len(embedded_signup_waba_scope_foreign_keys) == 1
    assert [
        element.column.name for element in embedded_signup_waba_scope_foreign_keys[0].elements
    ] == ["id", "account_id"]

    embedded_signup_webhook_scope_foreign_keys = [
        constraint
        for constraint in EmbeddedSignupSession.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        and [column.name for column in constraint.columns] == ["created_webhook_subscription_id", "account_id"]
    ]
    assert len(embedded_signup_webhook_scope_foreign_keys) == 1
    assert [
        element.column.name for element in embedded_signup_webhook_scope_foreign_keys[0].elements
    ] == ["id", "account_id"]


def test_meta_child_scope_constraints_reject_cross_account_parent_mismatches(
    db_session_factory: sessionmaker[Session],
) -> None:
    session = db_session_factory()
    try:
        session.execute(text("PRAGMA foreign_keys = ON"))

        session.add_all(
            [
                Account(
                    account_id="schema-meta-scope-account-a",
                    display_name="Schema Meta Scope Account A",
                    provider_type="whatsapp",
                ),
                Account(
                    account_id="schema-meta-scope-account-b",
                    display_name="Schema Meta Scope Account B",
                    provider_type="whatsapp",
                ),
            ]
        )
        session.commit()

        session.add(
            WhatsAppBusinessAccount(
                id="schema-meta-scope-waba-a",
                account_id="schema-meta-scope-account-a",
                waba_id="waba-schema-meta-scope-a",
                onboarding_mode="manual",
                token_source="system_user",
                access_token="token-schema-meta-scope-a",
                webhook_subscribed=False,
                is_active=True,
                ai_enabled=True,
            )
        )
        session.commit()

        session.add(
            WebhookSubscription(
                id="schema-meta-scope-webhook-a",
                account_id="schema-meta-scope-account-a",
                waba_account_id="schema-meta-scope-waba-a",
                waba_id="waba-schema-meta-scope-a",
                callback_url="https://example.com/schema-meta-scope-a",
                status="pending",
            )
        )
        session.commit()

        session.add(
            WhatsAppPhoneNumber(
                id="schema-meta-scope-phone-mismatch",
                account_id="schema-meta-scope-account-b",
                waba_account_id="schema-meta-scope-waba-a",
                waba_id="waba-schema-meta-scope-a",
                phone_number_id="pn-schema-meta-scope-mismatch",
                display_phone_number="+1 555 000 0001",
                quality_rating="UNKNOWN",
                is_registered=False,
                is_active=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            WebhookSubscription(
                id="schema-meta-scope-webhook-mismatch",
                account_id="schema-meta-scope-account-b",
                waba_account_id="schema-meta-scope-waba-a",
                waba_id="waba-schema-meta-scope-a",
                callback_url="https://example.com/schema-meta-scope-mismatch",
                status="pending",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            MessageTemplate(
                id="schema-meta-scope-template-mismatch",
                account_id="schema-meta-scope-account-b",
                waba_account_id="schema-meta-scope-waba-a",
                waba_id="waba-schema-meta-scope-a",
                name="schema_meta_scope_template",
                language="en",
                category="UTILITY",
                status="APPROVED",
                components={"body_text": "schema scope mismatch"},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            EmbeddedSignupSession(
                id="schema-meta-scope-embedded-mismatch",
                session_id="schema-meta-scope-session-mismatch",
                account_id="schema-meta-scope-account-b",
                waba_account_id="schema-meta-scope-waba-a",
                redirect_uri="https://example.com/schema-meta-scope/callback",
                provider_name="mock",
                status="created",
                completion_stage="pending_callback",
                last_event_source="operator",
                remote_confirmed=False,
                linked_phone_number_ids_json=[],
                authorization_code_present=False,
                system_user_access_token_present=False,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            EmbeddedSignupSession(
                id="schema-meta-scope-webhook-pointer-mismatch",
                session_id="schema-meta-scope-session-webhook-pointer-mismatch",
                account_id="schema-meta-scope-account-b",
                created_webhook_subscription_id="schema-meta-scope-webhook-a",
                redirect_uri="https://example.com/schema-meta-scope/webhook-pointer",
                provider_name="mock",
                status="created",
                completion_stage="pending_callback",
                last_event_source="operator",
                remote_confirmed=False,
                linked_phone_number_ids_json=[],
                authorization_code_present=False,
                system_user_access_token_present=False,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()
