import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.permission_defs import DEFAULT_TEMPLATES

META_STATUS_INVALID_INSERTS: tuple[str, ...] = (
    """
    INSERT INTO meta_business_portfolios (
        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
    ) VALUES (
        'portfolio-meta-status-invalid', 'acct-meta-status-constraints', 'biz-meta-status-invalid',
        'Meta Status Invalid', 'archived', '2026-06-10 00:00:00', '2026-06-10 00:00:00'
    )
    """,
    """
    INSERT INTO whatsapp_business_accounts (
        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source, access_token,
        webhook_subscribed, webhook_verification_status, webhook_runtime_status, is_active, ai_enabled,
        created_at, updated_at
    ) VALUES (
        'waba-meta-status-invalid-verification', 'acct-meta-status-constraints', 'portfolio-meta-status-valid',
        'waba-meta-status-invalid-verification', 'manual', 'system_user', 'token-meta-status-invalid-verification',
        1, 'invalid_verification', 'pending', 1, 1, '2026-06-10 00:00:00', '2026-06-10 00:00:00'
    )
    """,
    """
    INSERT INTO whatsapp_business_accounts (
        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source, access_token,
        webhook_subscribed, webhook_verification_status, webhook_runtime_status, is_active, ai_enabled,
        created_at, updated_at
    ) VALUES (
        'waba-meta-status-invalid-runtime', 'acct-meta-status-constraints', 'portfolio-meta-status-valid',
        'waba-meta-status-invalid-runtime', 'manual', 'system_user', 'token-meta-status-invalid-runtime',
        1, 'pending', 'invalid_runtime', 1, 1, '2026-06-10 00:00:00', '2026-06-10 00:00:00'
    )
    """,
    """
    INSERT INTO webhook_subscriptions (
        id, account_id, waba_account_id, waba_id, callback_url, verify_token, app_id, status,
        subscribed_at, created_at, updated_at
    ) VALUES (
        'subscription-meta-status-invalid', 'acct-meta-status-constraints', 'waba-meta-status-valid',
        'waba-meta-status-valid', 'https://example.com/meta-status/invalid', 'verify-meta-status-invalid',
        'app-meta-status-invalid', 'invalid_subscription',
        '2026-06-10 00:00:00', '2026-06-10 00:00:00', '2026-06-10 00:00:00'
    )
    """,
    """
    INSERT INTO embedded_signup_sessions (
        id, session_id, account_id, redirect_uri, provider_name, status, completion_stage, last_event_source,
        remote_confirmed, linked_phone_number_ids_json, authorization_code_present,
        system_user_access_token_present, created_at, updated_at
    ) VALUES (
        'embedded-meta-status-invalid-status', 'embedded-meta-status-invalid-status',
        'acct-meta-status-constraints', 'https://example.com/meta-status/embedded-invalid-status', 'mock',
        'invalid_status', 'pending_callback', 'operator', 0, '[]', 0, 0,
        '2026-06-10 00:00:00', '2026-06-10 00:00:00'
    )
    """,
    """
    INSERT INTO embedded_signup_sessions (
        id, session_id, account_id, redirect_uri, provider_name, status, completion_stage, last_event_source,
        remote_confirmed, linked_phone_number_ids_json, authorization_code_present,
        system_user_access_token_present, created_at, updated_at
    ) VALUES (
        'embedded-meta-status-invalid-stage', 'embedded-meta-status-invalid-stage',
        'acct-meta-status-constraints', 'https://example.com/meta-status/embedded-invalid-stage', 'mock',
        'created', 'invalid_stage', 'operator', 0, '[]', 0, 0,
        '2026-06-10 00:00:00', '2026-06-10 00:00:00'
    )
    """,
    """
    INSERT INTO embedded_signup_sessions (
        id, session_id, account_id, redirect_uri, provider_name, status, completion_stage, last_event_source,
        remote_confirmed, linked_phone_number_ids_json, authorization_code_present,
        system_user_access_token_present, created_at, updated_at
    ) VALUES (
        'embedded-meta-status-invalid-source', 'embedded-meta-status-invalid-source',
        'acct-meta-status-constraints', 'https://example.com/meta-status/embedded-invalid-source', 'mock',
        'completed', 'remote_confirmed', 'invalid_source', 1, '[]', 0, 0,
        '2026-06-10 00:00:00', '2026-06-10 00:00:00'
    )
    """,
)


def _seed_meta_status_constraint_scope(connection: object) -> None:
    connection.execute(
        text(
            """
            INSERT INTO accounts (
                account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
            ) VALUES (
                'acct-meta-status-constraints', 'Meta Status Constraints', 'whatsapp', 1, 1,
                '2026-06-10 00:00:00', '2026-06-10 00:00:00'
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO meta_business_portfolios (
                id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
            ) VALUES (
                'portfolio-meta-status-valid', 'acct-meta-status-constraints', 'biz-meta-status-valid',
                'Meta Status Valid', 'active', '2026-06-10 00:00:00', '2026-06-10 00:00:00'
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO whatsapp_business_accounts (
                id, account_id, portfolio_id, waba_id, onboarding_mode, token_source, access_token,
                webhook_subscribed, webhook_verification_status, webhook_runtime_status, is_active, ai_enabled,
                created_at, updated_at
            ) VALUES (
                'waba-meta-status-valid', 'acct-meta-status-constraints', 'portfolio-meta-status-valid',
                'waba-meta-status-valid', 'manual', 'system_user', 'token-meta-status-valid',
                1, 'pending', 'pending', 1, 1, '2026-06-10 00:00:00', '2026-06-10 00:00:00'
            )
            """
        )
    )


def test_alembic_upgrade_head_on_sqlite() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_test.db"
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{database_path.as_posix()}")
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            template_send_log_columns = {
                column["name"] for column in inspector.get_columns("template_send_logs")
            }
            template_send_log_column_map = {
                column["name"]: column for column in inspector.get_columns("template_send_logs")
            }
            media_asset_event_columns = {
                column["name"] for column in inspector.get_columns("media_asset_events")
            }
            media_asset_provider_sync_columns = {
                column["name"] for column in inspector.get_columns("media_asset_provider_syncs")
            }
            meta_business_portfolio_columns = {
                column["name"] for column in inspector.get_columns("meta_business_portfolios")
            }
            whatsapp_business_account_columns = {
                column["name"] for column in inspector.get_columns("whatsapp_business_accounts")
            }
            template_hourly_stat_columns = {
                column["name"] for column in inspector.get_columns("template_hourly_stats")
            }
            template_failure_stat_columns = {
                column["name"] for column in inspector.get_columns("template_failure_stats")
            }
            app_user_columns = {
                column["name"] for column in inspector.get_columns("app_users")
            }
            member_profile_columns = {
                column["name"] for column in inspector.get_columns("member_profiles")
            }
            member_auth_session_columns = {
                column["name"] for column in inspector.get_columns("member_auth_sessions")
            }
            member_whatsapp_binding_request_columns = {
                column["name"] for column in inspector.get_columns("member_whatsapp_binding_requests")
            }
            member_verification_request_columns = {
                column["name"] for column in inspector.get_columns("member_verification_requests")
            }
            member_verification_document_columns = {
                column["name"] for column in inspector.get_columns("member_verification_documents")
            }
            task_package_template_columns = {
                column["name"] for column in inspector.get_columns("task_package_templates")
            }
            task_package_template_item_columns = {
                column["name"] for column in inspector.get_columns("task_package_template_items")
            }
            task_package_instance_columns = {
                column["name"] for column in inspector.get_columns("task_package_instances")
            }
            task_package_instance_item_columns = {
                column["name"] for column in inspector.get_columns("task_package_instance_items")
            }
            wallet_account_columns = {
                column["name"] for column in inspector.get_columns("wallet_accounts")
            }
            wallet_ledger_entry_columns = {
                column["name"] for column in inspector.get_columns("wallet_ledger_entries")
            }
            wallet_transfer_request_columns = {
                column["name"] for column in inspector.get_columns("wallet_transfer_requests")
            }
            wallet_recharge_order_columns = {
                column["name"] for column in inspector.get_columns("wallet_recharge_orders")
            }
            withdrawal_request_columns = {
                column["name"] for column in inspector.get_columns("withdrawal_requests")
            }
            withdrawal_audit_log_columns = {
                column["name"] for column in inspector.get_columns("withdrawal_audit_logs")
            }
            fragment_definition_columns = {
                column["name"] for column in inspector.get_columns("fragment_definitions")
            }
            fragment_inventory_columns = {
                column["name"] for column in inspector.get_columns("fragment_inventory")
            }
            fragment_ledger_entry_columns = {
                column["name"] for column in inspector.get_columns("fragment_ledger_entries")
            }
            fragment_drop_log_columns = {
                column["name"] for column in inspector.get_columns("fragment_drop_logs")
            }
            fragment_exchange_request_columns = {
                column["name"] for column in inspector.get_columns("fragment_exchange_requests")
            }
            member_order_columns = {
                column["name"] for column in inspector.get_columns("member_orders")
            }
            member_notification_columns = {
                column["name"] for column in inspector.get_columns("member_notifications")
            }
            mailing_request_columns = {
                column["name"] for column in inspector.get_columns("mailing_requests")
            }
            promotion_task_template_columns = {
                column["name"] for column in inspector.get_columns("promotion_task_templates")
            }
            promotion_task_instance_columns = {
                column["name"] for column in inspector.get_columns("promotion_task_instances")
            }
            user_referral_columns = {
                column["name"] for column in inspector.get_columns("user_referrals")
            }
            h5_site_unique_constraints = inspector.get_unique_constraints("h5_sites")
            app_user_unique_constraints = inspector.get_unique_constraints("app_users")
            task_template_unique_constraints = inspector.get_unique_constraints("task_templates")
            audience_rule_columns = {
                column["name"] for column in inspector.get_columns("audience_rule_sets")
            }
            task_template_columns = {
                column["name"] for column in inspector.get_columns("task_templates")
            }
            task_instance_columns = {
                column["name"] for column in inspector.get_columns("task_instances")
            }
            task_instance_column_map = {
                column["name"]: column for column in inspector.get_columns("task_instances")
            }
            h5_site_columns = {
                column["name"] for column in inspector.get_columns("h5_sites")
            }
            task_proof_file_columns = {
                column["name"] for column in inspector.get_columns("task_proof_files")
            }
            task_proof_file_column_map = {
                column["name"]: column for column in inspector.get_columns("task_proof_files")
            }
            task_submission_proof_columns = {
                column["name"] for column in inspector.get_columns("task_submission_proofs")
            }
            task_submission_proof_column_map = {
                column["name"]: column for column in inspector.get_columns("task_submission_proofs")
            }
            task_review_decision_columns = {
                column["name"] for column in inspector.get_columns("task_review_decisions")
            }
            task_review_decision_column_map = {
                column["name"]: column for column in inspector.get_columns("task_review_decisions")
            }
            task_submission_column_map = {
                column["name"]: column for column in inspector.get_columns("task_submissions")
            }
            ticket_columns = {
                column["name"] for column in inspector.get_columns("tickets")
            }
            ticket_column_map = {
                column["name"]: column for column in inspector.get_columns("tickets")
            }
            whatsapp_phone_number_columns = {
                column["name"] for column in inspector.get_columns("whatsapp_phone_numbers")
            }
            webhook_subscription_columns = {
                column["name"] for column in inspector.get_columns("webhook_subscriptions")
            }
            embedded_signup_session_columns = {
                column["name"] for column in inspector.get_columns("embedded_signup_sessions")
            }
            message_template_columns = {
                column["name"] for column in inspector.get_columns("message_templates")
            }
            whatsapp_business_account_unique_constraints = inspector.get_unique_constraints(
                "whatsapp_business_accounts"
            )
            webhook_subscription_unique_constraints = inspector.get_unique_constraints(
                "webhook_subscriptions"
            )
            whatsapp_phone_number_indexes = {
                index["name"]: index for index in inspector.get_indexes("whatsapp_phone_numbers")
            }
            task_submission_indexes = {index["name"]: index for index in inspector.get_indexes("task_submissions")}
            ticket_indexes = {index["name"]: index for index in inspector.get_indexes("tickets")}
            task_instance_checks = {
                constraint["name"]: constraint for constraint in inspector.get_check_constraints("task_instances")
            }
            task_submission_checks = {
                constraint["name"]: constraint for constraint in inspector.get_check_constraints("task_submissions")
            }
            task_review_decision_checks = {
                constraint["name"]: constraint for constraint in inspector.get_check_constraints("task_review_decisions")
            }
            ticket_checks = {
                constraint["name"]: constraint for constraint in inspector.get_check_constraints("tickets")
            }
            h5_site_indexes = {index["name"]: index for index in inspector.get_indexes("h5_sites")}
            meta_business_portfolio_indexes = {
                index["name"]: index for index in inspector.get_indexes("meta_business_portfolios")
            }
            task_template_indexes = {index["name"]: index for index in inspector.get_indexes("task_templates")}
            task_instance_indexes = {index["name"]: index for index in inspector.get_indexes("task_instances")}
            task_proof_file_indexes = {index["name"]: index for index in inspector.get_indexes("task_proof_files")}
            task_submission_proof_indexes = {
                index["name"]: index for index in inspector.get_indexes("task_submission_proofs")
            }
            task_review_decision_indexes = {
                index["name"]: index for index in inspector.get_indexes("task_review_decisions")
            }
            task_proof_file_foreign_keys = inspector.get_foreign_keys("task_proof_files")
            task_submission_foreign_keys = inspector.get_foreign_keys("task_submissions")
            task_submission_proof_foreign_keys = inspector.get_foreign_keys("task_submission_proofs")
            task_review_decision_foreign_keys = inspector.get_foreign_keys("task_review_decisions")
            ticket_foreign_keys = inspector.get_foreign_keys("tickets")
            template_send_log_foreign_keys = inspector.get_foreign_keys("template_send_logs")
            whatsapp_phone_number_foreign_keys = inspector.get_foreign_keys("whatsapp_phone_numbers")
            app_user_indexes = {index["name"]: index for index in inspector.get_indexes("app_users")}
            webhook_subscription_foreign_keys = inspector.get_foreign_keys("webhook_subscriptions")
            webhook_subscription_indexes = {
                index["name"]: index for index in inspector.get_indexes("webhook_subscriptions")
            }
            embedded_signup_session_indexes = {
                index["name"]: index for index in inspector.get_indexes("embedded_signup_sessions")
            }
            embedded_signup_session_foreign_keys = inspector.get_foreign_keys("embedded_signup_sessions")
            message_template_foreign_keys = inspector.get_foreign_keys("message_templates")
            message_template_indexes = {
                index["name"]: index for index in inspector.get_indexes("message_templates")
            }
            message_template_unique_constraints = inspector.get_unique_constraints("message_templates")
            template_send_log_indexes = {
                index["name"]: index for index in inspector.get_indexes("template_send_logs")
            }

            assert "accounts" in table_names
            assert "system_settings" in table_names
            assert "whatsapp_business_accounts" in table_names
            assert "conversations" in table_names
            assert "support_knowledge_entries" in table_names
            assert "whatsapp_conversation_stats" in table_names
            assert "template_hourly_stats" in table_names
            assert "template_failure_stats" in table_names
            assert "h5_sites" in table_names
            assert "app_users" in table_names
            assert "member_profiles" in table_names
            assert "member_auth_sessions" in table_names
            assert "member_whatsapp_binding_requests" in table_names
            assert "member_verification_requests" in table_names
            assert "member_verification_documents" in table_names
            assert "task_package_templates" in table_names
            assert "task_package_template_items" in table_names
            assert "task_package_instances" in table_names
            assert "task_package_instance_items" in table_names
            assert "user_identities" in table_names
            assert "invite_codes" in table_names
            assert "user_tags" in table_names
            assert "user_tag_assignments" in table_names
            assert "audience_rule_sets" in table_names
            assert "task_templates" in table_names
            assert "task_instances" in table_names
            assert "task_proof_files" in table_names
            assert "task_submissions" in table_names
            assert "task_submission_proofs" in table_names
            assert "task_review_decisions" in table_names
            assert "tickets" in table_names
            assert "ticket_messages" in table_names
            assert "wallet_accounts" in table_names
            assert "wallet_ledger_entries" in table_names
            assert "wallet_transfer_requests" in table_names
            assert "wallet_recharge_orders" in table_names
            assert "withdrawal_requests" in table_names
            assert "withdrawal_audit_logs" in table_names
            assert "fragment_definitions" in table_names
            assert "fragment_inventory" in table_names
            assert "fragment_ledger_entries" in table_names
            assert "fragment_drop_logs" in table_names
            assert "fragment_exchange_requests" in table_names
            assert "member_orders" in table_names
            assert "member_notifications" in table_names
            assert "mailing_requests" in table_names
            assert "promotion_task_templates" in table_names
            assert "promotion_task_instances" in table_names
            assert "user_referrals" in table_names
            assert "account_id" in meta_business_portfolio_columns
            assert "webhook_last_management_event_at" in whatsapp_business_account_columns
            assert "header_media_provider_media_id" in template_send_log_columns
            assert "header_media_meta_media_id" in template_send_log_columns
            assert "header_media_sync_status" in template_send_log_columns
            assert "estimated_cost" in template_send_log_columns
            assert getattr(template_send_log_column_map["phone_number_id"]["type"], "length", None) == 128
            assert "provider_media_id" in media_asset_event_columns
            assert "provider_media_id" in media_asset_provider_sync_columns
            assert "hour_bucket" in template_hourly_stat_columns
            assert "estimated_cost" in template_hourly_stat_columns
            assert "error_code" in template_failure_stat_columns
            assert "account_id" in app_user_columns
            assert "registration_invite_code" in app_user_columns
            assert "member_no" in member_profile_columns
            assert "password_hash" in member_profile_columns
            assert "session_token_hash" in member_auth_session_columns
            assert "refresh_token_hash" in member_auth_session_columns
            assert "requested_phone_number" in member_whatsapp_binding_request_columns
            assert "start_count" in member_whatsapp_binding_request_columns
            assert "bound_at" in member_whatsapp_binding_request_columns
            assert "member_profile_id" in member_verification_request_columns
            assert "review_note" in member_verification_request_columns
            assert "reviewer_actor_id" in member_verification_request_columns
            assert "verification_request_id" in member_verification_document_columns
            assert "reward_ratio" in task_package_template_columns
            assert "product_name" in task_package_template_item_columns
            assert "status" in task_package_instance_columns
            assert "order_id" in task_package_instance_item_columns
            assert "system_balance" in wallet_account_columns
            assert "transaction_type" in wallet_ledger_entry_columns
            assert "wallet_account_id" in wallet_transfer_request_columns
            assert "credited_at" in wallet_recharge_order_columns
            assert "request_no" in withdrawal_request_columns
            assert "withdrawal_request_id" in withdrawal_audit_log_columns
            assert "fragment_key" in fragment_definition_columns
            assert "owned_count" in fragment_inventory_columns
            assert "fragment_definition_id" in fragment_ledger_entry_columns
            assert "source" in fragment_drop_log_columns
            assert "reward_name" in fragment_exchange_request_columns
            assert "order_no" in member_order_columns
            assert "body_text" in member_notification_columns
            assert "is_read" in member_notification_columns
            assert "read_at" in member_notification_columns
            assert "site_id" in member_notification_columns
            assert "reference_id" in member_notification_columns
            assert "receiver" in mailing_request_columns
            assert "fragment_exchange_request_id" in mailing_request_columns
            assert "task_package_template_id" in promotion_task_template_columns
            assert "promotion_task_template_id" in promotion_task_instance_columns
            assert "invite_code" in user_referral_columns
            assert "first_recharged_at" in user_referral_columns
            assert any(
                constraint["name"] == "uq_h5_sites_id_account_scope"
                and constraint["column_names"] == ["id", "account_id"]
                for constraint in h5_site_unique_constraints
            )
            assert any(
                constraint["name"] == "uq_app_users_id_account_scope"
                and constraint["column_names"] == ["id", "account_id"]
                for constraint in app_user_unique_constraints
            )
            assert "rules_json" in audience_rule_columns
            assert "account_id" in h5_site_columns
            assert "claim_timeout_seconds" in task_template_columns
            assert "account_id" in task_template_columns
            assert any(
                constraint["name"] == "uq_task_templates_id_account_scope"
                and constraint["column_names"] == ["id", "account_id"]
                for constraint in task_template_unique_constraints
            )
            assert "claim_deadline_at" in task_instance_columns
            assert "account_id" in task_instance_columns
            assert "account_id" in task_proof_file_columns
            assert "task_instance_id" in task_submission_proof_columns
            assert "account_id" in task_submission_proof_columns
            assert "account_id" in task_review_decision_columns
            assert "account_id" in ticket_columns
            assert task_instance_column_map["account_id"]["nullable"] is False
            assert task_proof_file_column_map["account_id"]["nullable"] is False
            assert task_submission_column_map["account_id"]["nullable"] is False
            assert task_submission_proof_column_map["task_instance_id"]["nullable"] is False
            assert task_submission_proof_column_map["account_id"]["nullable"] is False
            assert task_review_decision_column_map["account_id"]["nullable"] is False
            assert ticket_column_map["account_id"]["nullable"] is False
            assert "quality_event" in whatsapp_phone_number_columns
            assert "waba_id" in whatsapp_phone_number_columns
            assert "previous_quality_rating" in whatsapp_phone_number_columns
            assert "messaging_limit_tier" in whatsapp_phone_number_columns
            assert "max_daily_conversations_per_business" in whatsapp_phone_number_columns
            assert "last_quality_event_at" in whatsapp_phone_number_columns
            assert "last_status_payload" in whatsapp_phone_number_columns
            assert "waba_id" in webhook_subscription_columns
            assert "app_secret" in webhook_subscription_columns
            assert "created_webhook_subscription_id" in embedded_signup_session_columns
            assert "waba_id" in message_template_columns
            assert "ix_h5_sites_account_id" in h5_site_indexes
            assert "ix_task_templates_account_id" in task_template_indexes
            assert "ix_task_instances_account_id" in task_instance_indexes
            assert "ix_task_proof_files_account_id" in task_proof_file_indexes
            assert "ix_task_submission_proofs_account_id" in task_submission_proof_indexes
            assert "ix_task_review_decisions_account_id" in task_review_decision_indexes
            assert any(
                fk["constrained_columns"] == ["registration_site_id", "account_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in inspector.get_foreign_keys("app_users")
            )
            assert not any(
                fk["constrained_columns"] == ["registration_site_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id"]
                for fk in inspector.get_foreign_keys("app_users")
            )
            assert any(
                fk["constrained_columns"] == ["template_id", "account_id"]
                and fk["referred_table"] == "task_templates"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in inspector.get_foreign_keys("task_instances")
            )
            assert any(
                fk["constrained_columns"] == ["user_id", "account_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in inspector.get_foreign_keys("task_instances")
            )
            assert any(
                fk["constrained_columns"] == ["site_id", "account_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in inspector.get_foreign_keys("task_instances")
            )
            assert not any(
                fk["constrained_columns"] == ["template_id"]
                and fk["referred_table"] == "task_templates"
                and fk["referred_columns"] == ["id"]
                for fk in inspector.get_foreign_keys("task_instances")
            )
            assert not any(
                fk["constrained_columns"] == ["user_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id"]
                for fk in inspector.get_foreign_keys("task_instances")
            )
            assert not any(
                fk["constrained_columns"] == ["site_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id"]
                for fk in inspector.get_foreign_keys("task_instances")
            )
            assert any(
                fk["constrained_columns"] == ["task_instance_id", "account_id"]
                and fk["referred_table"] == "task_instances"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in task_proof_file_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["user_id", "account_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in task_proof_file_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["site_id", "account_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in task_proof_file_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["user_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id"]
                for fk in task_proof_file_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["site_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id"]
                for fk in task_proof_file_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["task_instance_id", "account_id"]
                and fk["referred_table"] == "task_instances"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in task_submission_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["submitted_by_user_id", "account_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in task_submission_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["site_id", "account_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in task_submission_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["submitted_by_user_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id"]
                for fk in task_submission_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["site_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id"]
                for fk in task_submission_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["submission_id", "task_instance_id", "account_id"]
                and fk["referred_table"] == "task_submissions"
                and fk["referred_columns"] == ["id", "task_instance_id", "account_id"]
                for fk in task_submission_proof_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["proof_file_id", "task_instance_id", "account_id"]
                and fk["referred_table"] == "task_proof_files"
                and fk["referred_columns"] == ["id", "task_instance_id", "account_id"]
                for fk in task_submission_proof_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["submission_id", "task_instance_id", "account_id"]
                and fk["referred_table"] == "task_submissions"
                and fk["referred_columns"] == ["id", "task_instance_id", "account_id"]
                for fk in task_review_decision_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["task_instance_id", "account_id"]
                and fk["referred_table"] == "task_instances"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in task_review_decision_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["task_instance_id"]
                and fk["referred_table"] == "task_instances"
                and fk["referred_columns"] == ["id"]
                for fk in task_review_decision_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["linked_submission_id", "linked_task_instance_id", "account_id"]
                and fk["referred_table"] == "task_submissions"
                and fk["referred_columns"] == ["id", "task_instance_id", "account_id"]
                for fk in ticket_foreign_keys
            )
            assert any(
                fk["constrained_columns"]
                == ["review_decision_id", "linked_task_instance_id", "linked_submission_id", "account_id"]
                and fk["referred_table"] == "task_review_decisions"
                and fk["referred_columns"] == ["id", "task_instance_id", "submission_id", "account_id"]
                for fk in ticket_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["linked_task_instance_id", "account_id"]
                and fk["referred_table"] == "task_instances"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in ticket_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["user_id", "account_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in ticket_foreign_keys
            )
            assert any(
                fk["constrained_columns"] == ["site_id", "account_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in ticket_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["linked_task_instance_id"]
                and fk["referred_table"] == "task_instances"
                and fk["referred_columns"] == ["id"]
                for fk in ticket_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["user_id"]
                and fk["referred_table"] == "app_users"
                and fk["referred_columns"] == ["id"]
                for fk in ticket_foreign_keys
            )
            assert not any(
                fk["constrained_columns"] == ["site_id"]
                and fk["referred_table"] == "h5_sites"
                and fk["referred_columns"] == ["id"]
                for fk in ticket_foreign_keys
            )
            assert "ix_app_users_account_id" in app_user_indexes
            assert "uq_task_submissions_active_per_task_instance" in task_submission_indexes
            assert task_submission_indexes["uq_task_submissions_active_per_task_instance"]["unique"] == 1
            assert "ix_task_submissions_account_id" in task_submission_indexes
            assert "uq_tickets_active_appeal_per_task_instance" in ticket_indexes
            assert ticket_indexes["uq_tickets_active_appeal_per_task_instance"]["unique"] == 1
            assert "ix_tickets_account_id" in ticket_indexes
            assert any(name.endswith("ck_task_instances_status") for name in task_instance_checks)
            assert any(name.endswith("ck_task_submissions_status") for name in task_submission_checks)
            assert any(name.endswith("ck_task_review_decisions_decision") for name in task_review_decision_checks)
            assert any(name.endswith("ck_tickets_ticket_type") for name in ticket_checks)
            ticket_status_checks = [
                constraint["sqltext"]
                for name, constraint in ticket_checks.items()
                if isinstance(name, str) and name.endswith("ck_tickets_status")
            ]
            assert len(ticket_status_checks) == 1
            assert "'waiting_user'" in ticket_status_checks[0]
            assert "'pending_user'" in ticket_status_checks[0]
            assert any(name.endswith("ck_tickets_linked_submission_requires_task") for name in ticket_checks)
            assert any(name.endswith("ck_tickets_review_decision_requires_submission") for name in ticket_checks)
            assert any(name.endswith("ck_tickets_appeal_requires_review_chain") for name in ticket_checks)
            assert "ix_meta_business_portfolios_account_id" in meta_business_portfolio_indexes
            assert any(
                constraint["name"] == "uq_whatsapp_business_accounts_id_account"
                and constraint["column_names"] == ["id", "account_id"]
                for constraint in whatsapp_business_account_unique_constraints
            )
            assert any(
                constraint["name"] == "uq_webhook_subscriptions_id_account"
                and constraint["column_names"] == ["id", "account_id"]
                for constraint in webhook_subscription_unique_constraints
            )
            assert "uq_webhook_subscriptions_waba_callback" in webhook_subscription_indexes
            assert webhook_subscription_indexes["uq_webhook_subscriptions_waba_callback"]["unique"] == 1
            assert webhook_subscription_indexes["uq_webhook_subscriptions_waba_callback"][
                "column_names"
            ] == ["account_id", "waba_id", "callback_url"]
            assert "ix_webhook_subscriptions_waba_id" in webhook_subscription_indexes
            assert any(
                fk["name"] == "fk_whatsapp_phone_numbers_waba_account_scope"
                and fk["constrained_columns"] == ["waba_account_id", "account_id"]
                and fk["referred_table"] == "whatsapp_business_accounts"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in whatsapp_phone_number_foreign_keys
            )
            assert any(
                fk["name"] == "fk_webhook_subscriptions_waba_account_scope"
                and fk["constrained_columns"] == ["waba_account_id", "account_id"]
                and fk["referred_table"] == "whatsapp_business_accounts"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in webhook_subscription_foreign_keys
            )
            assert (
                "ix_embedded_signup_sessions_created_webhook_subscription_id"
                in embedded_signup_session_indexes
            )
            assert any(
                fk["referred_table"] == "webhook_subscriptions"
                and fk["constrained_columns"] == ["created_webhook_subscription_id"]
                and fk["referred_columns"] == ["id"]
                for fk in embedded_signup_session_foreign_keys
            )
            assert any(
                fk["name"] == "fk_embedded_signup_sessions_waba_account_scope"
                and fk["constrained_columns"] == ["waba_account_id", "account_id"]
                and fk["referred_table"] == "whatsapp_business_accounts"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in embedded_signup_session_foreign_keys
            )
            assert any(
                fk["name"] == "fk_embedded_signup_sessions_created_webhook_subscription_scope"
                and fk["constrained_columns"] == ["created_webhook_subscription_id", "account_id"]
                and fk["referred_table"] == "webhook_subscriptions"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in embedded_signup_session_foreign_keys
            )
            assert "ix_whatsapp_phone_numbers_waba_id" in whatsapp_phone_number_indexes
            assert "uq_message_templates_account_waba_meta_template_id" in message_template_indexes
            assert message_template_indexes["uq_message_templates_account_waba_meta_template_id"]["unique"] == 1
            assert message_template_indexes["uq_message_templates_account_waba_meta_template_id"][
                "column_names"
            ] == ["account_id", "waba_id", "meta_template_id"]
            assert "uq_message_templates_account_waba_name_language" in message_template_indexes
            assert message_template_indexes["uq_message_templates_account_waba_name_language"]["unique"] == 1
            assert message_template_indexes["uq_message_templates_account_waba_name_language"][
                "column_names"
            ] == ["account_id", "waba_id", "name", "language"]
            assert "ix_message_templates_waba_id" in message_template_indexes
            assert any(
                fk["name"] == "fk_message_templates_waba_account_scope"
                and fk["constrained_columns"] == ["waba_account_id", "account_id"]
                and fk["referred_table"] == "whatsapp_business_accounts"
                and fk["referred_columns"] == ["id", "account_id"]
                for fk in message_template_foreign_keys
            )
            assert not any(
                constraint["column_names"] == ["meta_template_id"]
                for constraint in message_template_unique_constraints
            )
            assert "uq_template_send_logs_account_message_id" in template_send_log_indexes
            assert template_send_log_indexes["uq_template_send_logs_account_message_id"]["unique"] == 1
            assert "uq_template_send_logs_account_idempotency_key" in template_send_log_indexes
            assert template_send_log_indexes["uq_template_send_logs_account_idempotency_key"]["unique"] == 1
            assert not any(
                fk["constrained_columns"] == ["phone_number_id"]
                and fk["referred_table"] == "whatsapp_phone_numbers"
                for fk in template_send_log_foreign_keys
            )
        finally:
            engine.dispose()


def test_alembic_backfills_meta_portfolio_account_scope() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_meta_portfolio_scope.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260608_0032")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-meta-portfolio', 'Meta Portfolio Account', 'whatsapp', 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-meta-scope-1', 'biz-meta-scope-1', 'Scoped Portfolio', 'active',
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-meta-scope-1', 'acct-meta-portfolio', 'portfolio-meta-scope-1',
                        'waba-meta-scope-1', 'manual', 'system_user', 0, 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT account_id FROM meta_business_portfolios WHERE id = 'portfolio-meta-scope-1'")
            ).scalar() == "acct-meta-portfolio"

        engine.dispose()


def test_alembic_backfills_h5_task_workflow_account_ids() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_backfill.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260608_0022")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-h5-scope', 'Scoped Account', 'whatsapp', 1, 1, '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO h5_sites (
                        id, site_key, domain, brand_name, default_language, status, metadata_json, created_at, updated_at
                    ) VALUES (
                        'site-1', 'scope-site', 'scope.example.com', 'Scope Site', 'zh-CN', 'active',
                        '{"account_id":"acct-h5-scope"}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO app_users (
                        id, public_user_id, registration_site_id, language_code, is_anonymous, lifecycle_status,
                        has_phone, has_email, has_whatsapp, is_invited_user, is_new_user, restrict_task_claim,
                        created_at, updated_at
                    ) VALUES (
                        'user-1', 'scope-user', 'site-1', 'zh-CN', 0, 'active',
                        0, 0, 0, 0, 1, 0, '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_templates (
                        id, task_key, name, title, task_type, status, reward_points, claim_timeout_seconds,
                        auto_review_enabled, metadata_json, created_at, updated_at
                    ) VALUES (
                        'tmpl-1', 'scope-task', 'Scope Task', 'Scope Title', 'shopping', 'active', 0, 86400, 1,
                        '{"account_id":"acct-h5-scope"}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_instances (
                        id, template_id, user_id, site_id, status, claim_timeout_seconds_snapshot, review_required,
                        available_at, metadata_json, created_at, updated_at
                    ) VALUES (
                        'inst-1', 'tmpl-1', 'user-1', 'site-1', 'under_review', 86400, 1,
                        '2026-06-08 00:00:00', '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_proof_files (
                        id, task_instance_id, user_id, site_id, status, storage_provider, object_key, mime_type,
                        original_filename, size_bytes, sha256, uploaded_by_type, metadata_json, created_at, updated_at
                    ) VALUES (
                        'proof-1', 'inst-1', 'user-1', 'site-1', 'uploaded', 'local', 'proof/object-1', 'image/png',
                        'proof.png', 123, 'sha-proof-1', 'user', '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_submissions (
                        id, task_instance_id, submitted_by_user_id, site_id, submission_no, status, source_channel,
                        submitted_at, review_started_at, review_required_snapshot, payload_json, created_at, updated_at
                    ) VALUES (
                        'sub-1', 'inst-1', 'user-1', 'site-1', 1, 'under_review', 'h5',
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00', 1, '{}',
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_review_decisions (
                        id, task_instance_id, submission_id, decision, decision_source, evidence_json, created_at
                    ) VALUES (
                        'rev-1', 'inst-1', 'sub-1', 'pending', 'manual', '{}', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO tickets (
                        id, ticket_no, linked_task_instance_id, linked_submission_id, review_decision_id, user_id,
                        site_id, ticket_type, status, priority, title, latest_reply_at, is_active, metadata_json,
                        created_at, updated_at
                    ) VALUES (
                        'ticket-1', 'TKT-SCOPE-1', 'inst-1', 'sub-1', 'rev-1', 'user-1', 'site-1',
                        'appeal', 'open', 'normal', 'Scope Ticket', '2026-06-08 00:00:00', 1, '{}',
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(text("SELECT account_id FROM h5_sites WHERE id = 'site-1'")).scalar() == (
                "acct-h5-scope"
            )
            assert connection.execute(text("SELECT account_id FROM app_users WHERE id = 'user-1'")).scalar() == (
                "acct-h5-scope"
            )
            assert connection.execute(text("SELECT account_id FROM task_templates WHERE id = 'tmpl-1'")).scalar() == (
                "acct-h5-scope"
            )
            assert connection.execute(text("SELECT account_id FROM task_instances WHERE id = 'inst-1'")).scalar() == (
                "acct-h5-scope"
            )
            assert connection.execute(
                text("SELECT account_id FROM task_proof_files WHERE id = 'proof-1'")
            ).scalar() == "acct-h5-scope"
            assert connection.execute(
                text("SELECT account_id FROM task_submissions WHERE id = 'sub-1'")
            ).scalar() == "acct-h5-scope"
            proof_link_count = connection.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'task_submission_proofs'")
            ).scalar()
            assert proof_link_count == 1
            assert connection.execute(
                text("SELECT account_id FROM task_review_decisions WHERE id = 'rev-1'")
            ).scalar() == "acct-h5-scope"
            assert connection.execute(text("SELECT account_id FROM tickets WHERE id = 'ticket-1'")).scalar() == (
                "acct-h5-scope"
            )

        engine.dispose()


def test_alembic_backfills_task_submission_proof_task_and_account_scope() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_task_submission_proof_scope.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260608_0022")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-proof-scope', 'Proof Scope Account', 'whatsapp', 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO h5_sites (
                        id, site_key, domain, brand_name, default_language, status, metadata_json, created_at, updated_at
                    ) VALUES (
                        'site-proof-scope', 'proof-scope-site', 'proof-scope.example.com', 'Proof Scope', 'zh-CN', 'active',
                        '{"account_id":"acct-proof-scope"}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO app_users (
                        id, public_user_id, registration_site_id, language_code, is_anonymous, lifecycle_status,
                        has_phone, has_email, has_whatsapp, is_invited_user, is_new_user, restrict_task_claim,
                        created_at, updated_at
                    ) VALUES (
                        'user-proof-scope', 'proof-scope-user', 'site-proof-scope', 'zh-CN', 0, 'active',
                        0, 0, 0, 0, 1, 0, '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_templates (
                        id, task_key, name, title, task_type, status, reward_points, claim_timeout_seconds,
                        auto_review_enabled, metadata_json, created_at, updated_at
                    ) VALUES (
                        'tmpl-proof-scope', 'proof-scope-task', 'Proof Scope Task', 'Proof Scope Task', 'shopping',
                        'active', 0, 86400, 1, '{"account_id":"acct-proof-scope"}',
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_instances (
                        id, template_id, user_id, site_id, status, claim_timeout_seconds_snapshot, review_required,
                        available_at, metadata_json, created_at, updated_at
                    ) VALUES (
                        'inst-proof-scope', 'tmpl-proof-scope', 'user-proof-scope', 'site-proof-scope', 'under_review',
                        86400, 1, '2026-06-08 00:00:00', '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_proof_files (
                        id, task_instance_id, user_id, site_id, status, storage_provider, object_key, mime_type,
                        original_filename, size_bytes, sha256, uploaded_by_type, metadata_json, created_at, updated_at
                    ) VALUES (
                        'proof-file-scope', 'inst-proof-scope', 'user-proof-scope', 'site-proof-scope', 'uploaded',
                        'local', 'proof/scope-file', 'image/png', 'scope.png', 321, 'sha-proof-scope', 'user', '{}',
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_submissions (
                        id, task_instance_id, submitted_by_user_id, site_id, submission_no, status, source_channel,
                        submitted_at, review_started_at, review_required_snapshot, payload_json, created_at, updated_at
                    ) VALUES (
                        'submission-proof-scope', 'inst-proof-scope', 'user-proof-scope', 'site-proof-scope', 1,
                        'under_review', 'h5', '2026-06-08 00:00:00', '2026-06-08 00:00:00', 1, '{}',
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_submission_proofs (
                        id, submission_id, proof_file_id, proof_role, sort_order, created_at
                    ) VALUES (
                        'submission-proof-link-scope', 'submission-proof-scope', 'proof-file-scope',
                        'evidence', 0, '2026-06-08 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT submission_id, proof_file_id, task_instance_id, account_id
                    FROM task_submission_proofs
                    WHERE id = 'submission-proof-link-scope'
                    """
                )
            ).mappings().one()
            assert row == {
                "submission_id": "submission-proof-scope",
                "proof_file_id": "proof-file-scope",
                "task_instance_id": "inst-proof-scope",
                "account_id": "acct-proof-scope",
            }

        engine.dispose()


def test_alembic_rejects_task_submission_proof_rows_with_mismatched_task_scope() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_task_submission_proof_scope_mismatch.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260608_0022")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES
                        ('acct-proof-mismatch-a', 'Proof Mismatch A', 'whatsapp', 1, 1, '2026-06-08 00:00:00', '2026-06-08 00:00:00'),
                        ('acct-proof-mismatch-b', 'Proof Mismatch B', 'whatsapp', 1, 1, '2026-06-08 00:00:00', '2026-06-08 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO h5_sites (
                        id, site_key, domain, brand_name, default_language, status, metadata_json, created_at, updated_at
                    ) VALUES
                        ('site-proof-mismatch-a', 'proof-mismatch-a', 'proof-a.example.com', 'Proof A', 'zh-CN', 'active',
                         '{"account_id":"acct-proof-mismatch-a"}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'),
                        ('site-proof-mismatch-b', 'proof-mismatch-b', 'proof-b.example.com', 'Proof B', 'zh-CN', 'active',
                         '{"account_id":"acct-proof-mismatch-b"}', '2026-06-08 00:00:00', '2026-06-08 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO app_users (
                        id, public_user_id, registration_site_id, language_code, is_anonymous, lifecycle_status,
                        has_phone, has_email, has_whatsapp, is_invited_user, is_new_user, restrict_task_claim,
                        created_at, updated_at
                    ) VALUES
                        ('user-proof-mismatch-a', 'proof-user-a', 'site-proof-mismatch-a', 'zh-CN', 0, 'active',
                         0, 0, 0, 0, 1, 0, '2026-06-08 00:00:00', '2026-06-08 00:00:00'),
                        ('user-proof-mismatch-b', 'proof-user-b', 'site-proof-mismatch-b', 'zh-CN', 0, 'active',
                         0, 0, 0, 0, 1, 0, '2026-06-08 00:00:00', '2026-06-08 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_templates (
                        id, task_key, name, title, task_type, status, reward_points, claim_timeout_seconds,
                        auto_review_enabled, metadata_json, created_at, updated_at
                    ) VALUES
                        ('tmpl-proof-mismatch-a', 'proof-mismatch-task-a', 'Proof Task A', 'Proof Task A', 'shopping',
                         'active', 0, 86400, 1, '{"account_id":"acct-proof-mismatch-a"}',
                         '2026-06-08 00:00:00', '2026-06-08 00:00:00'),
                        ('tmpl-proof-mismatch-b', 'proof-mismatch-task-b', 'Proof Task B', 'Proof Task B', 'shopping',
                         'active', 0, 86400, 1, '{"account_id":"acct-proof-mismatch-b"}',
                         '2026-06-08 00:00:00', '2026-06-08 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_instances (
                        id, template_id, user_id, site_id, status, claim_timeout_seconds_snapshot, review_required,
                        available_at, metadata_json, created_at, updated_at
                    ) VALUES
                        ('inst-proof-mismatch-a', 'tmpl-proof-mismatch-a', 'user-proof-mismatch-a', 'site-proof-mismatch-a',
                         'under_review', 86400, 1, '2026-06-08 00:00:00', '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'),
                        ('inst-proof-mismatch-b', 'tmpl-proof-mismatch-b', 'user-proof-mismatch-b', 'site-proof-mismatch-b',
                         'under_review', 86400, 1, '2026-06-08 00:00:00', '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_proof_files (
                        id, task_instance_id, user_id, site_id, status, storage_provider, object_key, mime_type,
                        original_filename, size_bytes, sha256, uploaded_by_type, metadata_json, created_at, updated_at
                    ) VALUES
                        ('proof-file-mismatch-a', 'inst-proof-mismatch-a', 'user-proof-mismatch-a', 'site-proof-mismatch-a',
                         'uploaded', 'local', 'proof/mismatch-a', 'image/png', 'mismatch-a.png', 111, 'sha-mismatch-a',
                         'user', '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'),
                        ('proof-file-mismatch-b', 'inst-proof-mismatch-b', 'user-proof-mismatch-b', 'site-proof-mismatch-b',
                         'uploaded', 'local', 'proof/mismatch-b', 'image/png', 'mismatch-b.png', 222, 'sha-mismatch-b',
                         'user', '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_submissions (
                        id, task_instance_id, submitted_by_user_id, site_id, submission_no, status, source_channel,
                        submitted_at, review_started_at, review_required_snapshot, payload_json, created_at, updated_at
                    ) VALUES (
                        'submission-proof-mismatch-a', 'inst-proof-mismatch-a', 'user-proof-mismatch-a',
                        'site-proof-mismatch-a', 1, 'under_review', 'h5', '2026-06-08 00:00:00',
                        '2026-06-08 00:00:00', 1, '{}', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO task_submission_proofs (
                        id, submission_id, proof_file_id, proof_role, sort_order, created_at
                    ) VALUES (
                        'submission-proof-link-mismatch', 'submission-proof-mismatch-a', 'proof-file-mismatch-b',
                        'evidence', 0, '2026-06-08 00:00:00'
                    )
                    """
                    )
                )

        engine.dispose()

        with pytest.raises(RuntimeError, match="task_submission_proofs"):
            command.upgrade(config, "head")


def test_alembic_backfills_app_user_account_id_from_registration_site_scope() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_app_user_account_scope.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260609_0041")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-app-user-scope', 'App User Scope', 'whatsapp', 1, 1,
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO h5_sites (
                        id, account_id, site_key, domain, brand_name, default_language, status,
                        metadata_json, created_at, updated_at
                    ) VALUES (
                        'site-app-user-scope', 'acct-app-user-scope', 'app-user-scope-site',
                        'app-user-scope.example.com', 'App User Scope Site', 'zh-CN', 'active',
                        '{}', '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO app_users (
                        id, public_user_id, registration_site_id, language_code, is_anonymous, lifecycle_status,
                        has_phone, has_email, has_whatsapp, is_invited_user, is_new_user, restrict_task_claim,
                        created_at, updated_at
                    ) VALUES (
                        'user-app-user-scope', 'public-app-user-scope', 'site-app-user-scope', 'zh-CN', 0, 'active',
                        0, 0, 0, 0, 1, 0, '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT account_id FROM app_users WHERE id = 'user-app-user-scope'")
            ).scalar() == "acct-app-user-scope"

        engine.dispose()


def test_alembic_backfills_meta_phone_and_webhook_waba_scope() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_meta_waba_scope.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260608_0037")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-meta-waba-scope', 'Meta WABA Scope', 'whatsapp', 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-meta-waba-scope', 'acct-meta-waba-scope', 'biz-meta-waba-scope',
                        'Meta WABA Scope', 'active', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-meta-waba-scope', 'acct-meta-waba-scope', 'portfolio-meta-waba-scope',
                        'waba-meta-waba-scope', 'manual', 'system_user', 1, 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_phone_numbers (
                        id, account_id, waba_account_id, phone_number_id, display_phone_number,
                        verified_name, quality_rating, is_registered, is_active, created_at, updated_at
                    ) VALUES (
                        'phone-meta-waba-scope', 'acct-meta-waba-scope', 'waba-meta-waba-scope',
                        'pn-meta-waba-scope', '+1 555 000 3999', 'Meta WABA Scope', 'GREEN', 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO webhook_subscriptions (
                        id, account_id, waba_account_id, callback_url, verify_token, app_id, status,
                        subscribed_at, created_at, updated_at
                    ) VALUES (
                        'subscription-meta-waba-scope', 'acct-meta-waba-scope', 'waba-meta-waba-scope',
                        'https://example.com/meta-waba-scope', 'verify-meta-waba-scope', 'app-meta-waba-scope',
                        'mock_subscribed', '2026-06-08 00:00:00', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT waba_id FROM whatsapp_phone_numbers WHERE id = 'phone-meta-waba-scope'")
            ).scalar() == "waba-meta-waba-scope"
            assert connection.execute(
                text("SELECT waba_id FROM webhook_subscriptions WHERE id = 'subscription-meta-waba-scope'")
            ).scalar() == "waba-meta-waba-scope"

        engine.dispose()


def test_alembic_backfills_webhook_subscription_app_secret_snapshot() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_webhook_app_secret_snapshot.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260610_0055")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-webhook-app-secret-snapshot', 'Webhook App Secret Snapshot', 'whatsapp', 1, 1,
                        '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-webhook-app-secret-snapshot', 'acct-webhook-app-secret-snapshot',
                        'biz-webhook-app-secret-snapshot', 'Webhook App Secret Snapshot', 'active',
                        '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source, access_token,
                        verify_token, app_secret, webhook_subscribed, webhook_verification_status,
                        webhook_runtime_status, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-webhook-app-secret-snapshot', 'acct-webhook-app-secret-snapshot',
                        'portfolio-webhook-app-secret-snapshot', 'waba-webhook-app-secret-snapshot',
                        'manual', 'system_user', 'token-webhook-app-secret-snapshot',
                        'verify-webhook-app-secret-snapshot', 'secret-webhook-app-secret-snapshot',
                        1, 'verified', 'healthy', 1, 1,
                        '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO webhook_subscriptions (
                        id, account_id, waba_account_id, waba_id, callback_url, verify_token, app_id, status,
                        subscribed_at, created_at, updated_at
                    ) VALUES (
                        'subscription-webhook-app-secret-snapshot', 'acct-webhook-app-secret-snapshot',
                        'waba-webhook-app-secret-snapshot', 'waba-webhook-app-secret-snapshot',
                        'https://example.com/webhook/app-secret-snapshot',
                        'verify-webhook-app-secret-snapshot', 'app-webhook-app-secret-snapshot',
                        'remote_subscribed', '2026-06-10 00:00:00',
                        '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                text(
                    """
                    SELECT app_secret
                    FROM webhook_subscriptions
                    WHERE id = 'subscription-webhook-app-secret-snapshot'
                    """
                )
            ).scalar() == "secret-webhook-app-secret-snapshot"

        engine.dispose()


def test_alembic_backfills_message_template_waba_scope() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_template_waba_scope.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260608_0038")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-template-waba-scope', 'Template WABA Scope', 'whatsapp', 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-template-waba-scope', 'acct-template-waba-scope', 'biz-template-waba-scope',
                        'Template WABA Scope', 'active', '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-template-waba-scope', 'acct-template-waba-scope', 'portfolio-template-waba-scope',
                        'waba-template-waba-scope', 'manual', 'system_user', 1, 1, 1,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO message_templates (
                        id, account_id, waba_account_id, meta_template_id, name, language, category, status,
                        components, rejected_reason, submitted_at, last_synced_at, provider_template_payload,
                        created_at, updated_at
                    ) VALUES (
                        'template-waba-scope', 'acct-template-waba-scope', 'waba-template-waba-scope',
                        'meta-template-waba-scope', 'template_scope', 'en', 'UTILITY', 'APPROVED',
                        '{"body_text":"Hello {{first_name}}"}', NULL, NULL, NULL, NULL,
                        '2026-06-08 00:00:00', '2026-06-08 00:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT waba_id FROM message_templates WHERE id = 'template-waba-scope'")
            ).scalar() == "waba-template-waba-scope"

        engine.dispose()


def test_alembic_waba_snapshot_uniqueness_alignment_deduplicates_recreated_waba_rows() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_template_waba_uniqueness_alignment.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260609_0044")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-template-waba-alignment', 'Template WABA Alignment', 'whatsapp', 1, 1,
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-template-waba-alignment', 'acct-template-waba-alignment',
                        'biz-template-waba-alignment', 'Template WABA Alignment', 'active',
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-local-legacy-alignment', 'acct-template-waba-alignment',
                        'portfolio-template-waba-alignment', 'waba-template-alignment-legacy',
                        'manual', 'system_user', 1, 1, 1, '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-local-current-alignment', 'acct-template-waba-alignment',
                        'portfolio-template-waba-alignment', 'waba-template-alignment-official',
                        'manual', 'system_user', 1, 1, 1, '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO message_templates (
                        id, account_id, waba_account_id, waba_id, meta_template_id, name, language, category, status,
                        components, rejected_reason, submitted_at, last_synced_at, provider_template_payload,
                        created_at, updated_at
                    ) VALUES (
                        'template-alignment-stale', 'acct-template-waba-alignment',
                        'waba-local-legacy-alignment', 'waba-template-alignment-official',
                        'meta-template-alignment', 'shipping_update', 'en', 'UTILITY', 'APPROVED',
                        '{"body_text":"Legacy duplicate"}', NULL, NULL, NULL, NULL,
                        '2026-06-09 04:00:00', '2026-06-09 04:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO message_templates (
                        id, account_id, waba_account_id, waba_id, meta_template_id, name, language, category, status,
                        components, rejected_reason, submitted_at, last_synced_at, provider_template_payload,
                        created_at, updated_at
                    ) VALUES (
                        'template-alignment-current', 'acct-template-waba-alignment',
                        'waba-local-current-alignment', 'waba-template-alignment-official',
                        'meta-template-alignment', 'shipping_update', 'en', 'UTILITY', 'APPROVED',
                        '{"body_text":"Current duplicate"}', NULL, NULL, NULL, NULL,
                        '2026-06-09 05:00:00', '2026-06-09 05:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, waba_account_id, waba_id, meta_template_id, name, language
                    FROM message_templates
                    WHERE account_id = 'acct-template-waba-alignment'
                    ORDER BY created_at ASC, id ASC
                    """
                )
            ).mappings().all()

            assert rows == [
                {
                    "id": "template-alignment-current",
                    "waba_account_id": "waba-local-current-alignment",
                    "waba_id": "waba-template-alignment-official",
                    "meta_template_id": "meta-template-alignment",
                    "name": "shipping_update",
                    "language": "en",
                }
            ]

        engine.dispose()


def test_alembic_waba_snapshot_uniqueness_alignment_deduplicates_recreated_webhook_rows() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_webhook_waba_uniqueness_alignment.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260609_0044")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-webhook-waba-alignment', 'Webhook WABA Alignment', 'whatsapp', 1, 1,
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-webhook-waba-alignment', 'acct-webhook-waba-alignment',
                        'biz-webhook-waba-alignment', 'Webhook WABA Alignment', 'active',
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source, app_secret,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-webhook-legacy-alignment', 'acct-webhook-waba-alignment',
                        'portfolio-webhook-waba-alignment', 'waba-webhook-alignment-legacy',
                        'manual', 'system_user', 'secret-webhook-legacy-alignment',
                        1, 1, 1, '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source, app_secret,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-webhook-current-alignment', 'acct-webhook-waba-alignment',
                        'portfolio-webhook-waba-alignment', 'waba-webhook-alignment-official',
                        'manual', 'system_user', 'secret-webhook-current-alignment',
                        1, 1, 1, '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO webhook_subscriptions (
                        id, account_id, waba_account_id, waba_id, callback_url, verify_token, app_id, status,
                        subscribed_at, created_at, updated_at
                    ) VALUES (
                        'webhook-alignment-stale', 'acct-webhook-waba-alignment',
                        'waba-webhook-legacy-alignment', 'waba-webhook-alignment-official',
                        'https://example.com/webhook/recreated', 'verify-stale', 'app-stale', 'mock_subscribed',
                        '2026-06-09 04:00:00', '2026-06-09 04:00:00', '2026-06-09 04:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO webhook_subscriptions (
                        id, account_id, waba_account_id, waba_id, callback_url, verify_token, app_id, status,
                        subscribed_at, created_at, updated_at
                    ) VALUES (
                        'webhook-alignment-current', 'acct-webhook-waba-alignment',
                        'waba-webhook-current-alignment', 'waba-webhook-alignment-official',
                        'https://example.com/webhook/recreated', 'verify-current', 'app-current', 'mock_subscribed',
                        '2026-06-09 05:00:00', '2026-06-09 05:00:00', '2026-06-09 05:00:00'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, waba_account_id, waba_id, callback_url, verify_token, app_secret, app_id
                    FROM webhook_subscriptions
                    WHERE account_id = 'acct-webhook-waba-alignment'
                    ORDER BY created_at ASC, id ASC
                    """
                )
            ).mappings().all()

            assert rows == [
                {
                    "id": "webhook-alignment-current",
                    "waba_account_id": "waba-webhook-current-alignment",
                    "waba_id": "waba-webhook-alignment-official",
                    "callback_url": "https://example.com/webhook/recreated",
                    "verify_token": "verify-current",
                    "app_secret": "secret-webhook-current-alignment",
                    "app_id": "app-current",
                }
            ]

        engine.dispose()


def test_alembic_template_send_log_provider_phone_snapshot_preserves_legacy_values_and_allows_new_rows() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_template_send_log_provider_phone_snapshot.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "20260609_0048")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-template-send-log-snapshot', 'Template Send Log Snapshot', 'whatsapp', 1, 1,
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-template-send-log-snapshot', 'acct-template-send-log-snapshot',
                        'biz-template-send-log-snapshot', 'Template Send Log Snapshot', 'active',
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-template-send-log-snapshot-row', 'acct-template-send-log-snapshot',
                        'portfolio-template-send-log-snapshot', 'waba-template-send-log-snapshot',
                        'manual', 'system_user', 1, 1, 1,
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_phone_numbers (
                        id, account_id, waba_account_id, waba_id, phone_number_id, display_phone_number,
                        verified_name, quality_rating, is_registered, is_active, created_at, updated_at
                    ) VALUES (
                        'phone-local-template-send-log-snapshot', 'acct-template-send-log-snapshot',
                        'waba-template-send-log-snapshot-row', 'waba-template-send-log-snapshot',
                        'pn-template-send-log-snapshot', '+1 555 000 4999', 'Template Send Log Snapshot',
                        'GREEN', 1, 1, '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO message_templates (
                        id, account_id, waba_account_id, waba_id, meta_template_id, name, language, category,
                        status, components, created_at, updated_at
                    ) VALUES (
                        'template-send-log-snapshot', 'acct-template-send-log-snapshot',
                        'waba-template-send-log-snapshot-row', 'waba-template-send-log-snapshot',
                        'meta-template-send-log-snapshot', 'send_log_snapshot', 'en', 'UTILITY',
                        'APPROVED', '{"body_text":"Hello {{first_name}}"}',
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO template_send_logs (
                        id, account_id, template_id, wa_id, message_id, status, created_at, waba_id,
                        template_name, template_language, template_category, sent_at, last_status_at,
                        phone_number_id
                    ) VALUES (
                        'send-log-snapshot-legacy', 'acct-template-send-log-snapshot',
                        'template-send-log-snapshot', 'wa-send-log-snapshot-legacy',
                        'msg-send-log-snapshot-legacy', 'SENT', '2026-06-09 00:00:00',
                        'waba-template-send-log-snapshot', 'send_log_snapshot', 'en', 'UTILITY',
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00',
                        'phone-local-template-send-log-snapshot'
                    )
                    """
                )
            )

        command.upgrade(config, "head")

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO template_send_logs (
                        id, account_id, template_id, wa_id, message_id, status, created_at, waba_id,
                        template_name, template_language, template_category, sent_at, last_status_at,
                        phone_number_id
                    ) VALUES (
                        'send-log-snapshot-provider', 'acct-template-send-log-snapshot',
                        'template-send-log-snapshot', 'wa-send-log-snapshot-provider',
                        'msg-send-log-snapshot-provider', 'SENT', '2026-06-09 00:05:00',
                        'waba-template-send-log-snapshot', 'send_log_snapshot', 'en', 'UTILITY',
                        '2026-06-09 00:05:00', '2026-06-09 00:05:00',
                        'pn-template-send-log-snapshot'
                    )
                    """
                )
            )

        with engine.connect() as connection:
            phone_scopes = connection.execute(
                text(
                    """
                    SELECT phone_number_id
                    FROM template_send_logs
                    WHERE account_id = 'acct-template-send-log-snapshot'
                    ORDER BY id
                    """
                )
            ).scalars().all()
            assert phone_scopes == [
                "phone-local-template-send-log-snapshot",
                "pn-template-send-log-snapshot",
            ]

        engine.dispose()


def test_alembic_template_send_log_provider_phone_snapshot_blocks_incompatible_downgrade() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_template_send_log_provider_phone_snapshot_downgrade.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'acct-template-send-log-downgrade', 'Template Send Log Downgrade', 'whatsapp', 1, 1,
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_business_portfolios (
                        id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                    ) VALUES (
                        'portfolio-template-send-log-downgrade', 'acct-template-send-log-downgrade',
                        'biz-template-send-log-downgrade', 'Template Send Log Downgrade', 'active',
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_business_accounts (
                        id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                        webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                    ) VALUES (
                        'waba-template-send-log-downgrade-row', 'acct-template-send-log-downgrade',
                        'portfolio-template-send-log-downgrade', 'waba-template-send-log-downgrade',
                        'manual', 'system_user', 1, 1, 1,
                        '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO whatsapp_phone_numbers (
                        id, account_id, waba_account_id, waba_id, phone_number_id, display_phone_number,
                        verified_name, quality_rating, is_registered, is_active, created_at, updated_at
                    ) VALUES (
                        'phone-local-template-send-log-downgrade', 'acct-template-send-log-downgrade',
                        'waba-template-send-log-downgrade-row', 'waba-template-send-log-downgrade',
                        'pn-template-send-log-downgrade', '+1 555 000 4888', 'Template Send Log Downgrade',
                        'GREEN', 1, 1, '2026-06-09 00:00:00', '2026-06-09 00:00:00'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO template_send_logs (
                        id, account_id, wa_id, message_id, status, created_at, waba_id,
                        template_name, template_language, template_category, sent_at, last_status_at,
                        phone_number_id
                    ) VALUES (
                        'send-log-snapshot-downgrade-provider', 'acct-template-send-log-downgrade',
                        'wa-send-log-snapshot-downgrade-provider',
                        'msg-send-log-snapshot-downgrade-provider', 'SENT', '2026-06-09 00:05:00',
                        'waba-template-send-log-downgrade', 'send_log_snapshot', 'en', 'UTILITY',
                        '2026-06-09 00:05:00', '2026-06-09 00:05:00',
                        'pn-template-send-log-downgrade'
                    )
                    """
                )
            )
        engine.dispose()

        with pytest.raises(RuntimeError, match="Cannot downgrade 20260609_0049"):
            command.downgrade(config, "20260609_0048")


def test_alembic_meta_portfolio_account_scope_constraints_block_cross_account_waba_binding() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_meta_portfolio_scope_constraint.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text("PRAGMA foreign_keys = ON"))
                connection.execute(
                    text(
                        """
                        INSERT INTO accounts (
                            account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                        ) VALUES
                            ('acct-portfolio-scope-a', 'Portfolio Scope A', 'whatsapp', 1, 1,
                             '2026-06-10 00:00:00', '2026-06-10 00:00:00'),
                            ('acct-portfolio-scope-b', 'Portfolio Scope B', 'whatsapp', 1, 1,
                             '2026-06-10 00:00:00', '2026-06-10 00:00:00')
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO meta_business_portfolios (
                            id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                        ) VALUES (
                            'portfolio-scope-a', 'acct-portfolio-scope-a', 'biz-portfolio-scope-a',
                            'Portfolio Scope A', 'active', '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )

                with pytest.raises(IntegrityError):
                    connection.execute(
                        text(
                            """
                            INSERT INTO whatsapp_business_accounts (
                                id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                                access_token, webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                            ) VALUES (
                                'waba-portfolio-cross-account', 'acct-portfolio-scope-b', 'portfolio-scope-a',
                                'waba-portfolio-cross-account', 'manual', 'system_user',
                                'token-portfolio-cross-account', 0, 1, 1,
                                '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                            )
                            """
                        )
                    )
        finally:
            engine.dispose()


def test_alembic_fragment_and_mailing_schema_contract() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_fragment_and_mailing.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            assert "fragment_definitions" in table_names
            assert "fragment_inventory" in table_names
            assert "fragment_ledger_entries" in table_names
            assert "fragment_drop_logs" in table_names
            assert "fragment_exchange_requests" in table_names
            assert "mailing_requests" in table_names

            fragment_definition_uniques = inspector.get_unique_constraints("fragment_definitions")
            assert any(
                constraint["name"] == "uq_fragment_definitions_account_key"
                and constraint["column_names"] == ["account_id", "fragment_key"]
                for constraint in fragment_definition_uniques
            )

            fragment_definition_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_definitions")
            }
            assert "ix_fragment_definitions_account_id" in fragment_definition_indexes
            assert "ix_fragment_definitions_fragment_key" in fragment_definition_indexes

            fragment_inventory_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_inventory")
            }
            assert "ix_fragment_inventory_account_id" in fragment_inventory_indexes
            assert "ix_fragment_inventory_user_id" in fragment_inventory_indexes
            assert "ix_fragment_inventory_member_profile_id" in fragment_inventory_indexes
            assert "ix_fragment_inventory_fragment_definition_id" in fragment_inventory_indexes

            fragment_ledger_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_ledger_entries")
            }
            assert "ix_fragment_ledger_entries_account_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_fragment_definition_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_member_profile_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_user_id" in fragment_ledger_indexes
            assert "ix_fragment_ledger_entries_source_id" in fragment_ledger_indexes

            fragment_ledger_foreign_keys = inspector.get_foreign_keys("fragment_ledger_entries")
            assert any(
                fk["constrained_columns"] == ["fragment_definition_id"]
                and fk["referred_table"] == "fragment_definitions"
                and fk["referred_columns"] == ["id"]
                for fk in fragment_ledger_foreign_keys
            )

            fragment_drop_log_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_drop_logs")
            }
            assert "ix_fragment_drop_logs_account_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_user_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_member_profile_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_fragment_definition_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_fragment_ledger_entry_id" in fragment_drop_log_indexes
            assert "ix_fragment_drop_logs_source_id" in fragment_drop_log_indexes

            fragment_exchange_indexes = {
                index["name"]: index for index in inspector.get_indexes("fragment_exchange_requests")
            }
            assert "ix_fragment_exchange_requests_account_id" in fragment_exchange_indexes
            assert "ix_fragment_exchange_requests_user_id" in fragment_exchange_indexes
            assert "ix_fragment_exchange_requests_member_profile_id" in fragment_exchange_indexes
            assert "ix_fragment_exchange_requests_mailing_request_id" in fragment_exchange_indexes

            mailing_request_indexes = {
                index["name"]: index for index in inspector.get_indexes("mailing_requests")
            }
            assert "ix_mailing_requests_account_id" in mailing_request_indexes
            assert "ix_mailing_requests_user_id" in mailing_request_indexes
            assert "ix_mailing_requests_member_profile_id" in mailing_request_indexes
            assert "ix_mailing_requests_fragment_exchange_request_id" in mailing_request_indexes

            mailing_request_foreign_keys = inspector.get_foreign_keys("mailing_requests")
            assert any(
                fk["constrained_columns"] == ["fragment_exchange_request_id"]
                and fk["referred_table"] == "fragment_exchange_requests"
                and fk["referred_columns"] == ["id"]
                for fk in mailing_request_foreign_keys
            )
        finally:
            engine.dispose()


def test_alembic_wallet_ledger_entries_keep_idempotent_reward_unique_constraint() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_wallet_ledger_idempotent_reward.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        try:
            inspector = inspect(engine)
            wallet_ledger_uniques = inspector.get_unique_constraints("wallet_ledger_entries")
            assert any(
                constraint["name"] == "uq_wallet_ledger_entries_reference_scope"
                and constraint["column_names"]
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
                for constraint in wallet_ledger_uniques
            )
        finally:
            engine.dispose()


def test_alembic_meta_portfolio_account_scope_constraints_allow_same_account_waba_binding() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_meta_portfolio_scope_same_account.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text("PRAGMA foreign_keys = ON"))
                connection.execute(
                    text(
                        """
                        INSERT INTO accounts (
                            account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                        ) VALUES (
                            'acct-portfolio-scope-valid', 'Portfolio Scope Valid', 'whatsapp', 1, 1,
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO meta_business_portfolios (
                            id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                        ) VALUES (
                            'portfolio-scope-valid', 'acct-portfolio-scope-valid', 'biz-portfolio-scope-valid',
                            'Portfolio Scope Valid', 'active', '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO whatsapp_business_accounts (
                            id, account_id, portfolio_id, waba_id, onboarding_mode, token_source,
                            access_token, webhook_subscribed, is_active, ai_enabled, created_at, updated_at
                        ) VALUES (
                            'waba-portfolio-scope-valid', 'acct-portfolio-scope-valid', 'portfolio-scope-valid',
                            'waba-portfolio-scope-valid', 'manual', 'system_user',
                            'token-portfolio-scope-valid', 0, 1, 1,
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )

            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT account_id, portfolio_id, waba_id
                        FROM whatsapp_business_accounts
                        WHERE id = 'waba-portfolio-scope-valid'
                        """
                    )
                ).mappings().all()
                assert rows == [
                    {
                        "account_id": "acct-portfolio-scope-valid",
                        "portfolio_id": "portfolio-scope-valid",
                        "waba_id": "waba-portfolio-scope-valid",
                    }
                ]
        finally:
            engine.dispose()


def test_alembic_meta_status_constraints_reject_invalid_status_values() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_meta_status_constraints_invalid.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text("PRAGMA foreign_keys = ON"))
                _seed_meta_status_constraint_scope(connection)

            for insert_sql in META_STATUS_INVALID_INSERTS:
                with pytest.raises(IntegrityError):
                    with engine.begin() as connection:
                        connection.execute(text("PRAGMA foreign_keys = ON"))
                        connection.execute(text(insert_sql))
        finally:
            engine.dispose()


def test_alembic_meta_status_constraints_allow_valid_status_samples() -> None:
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "alembic_meta_status_constraints_valid.db"
        config = Config("alembic.ini")
        database_url = f"sqlite:///{database_path.as_posix()}"
        config.set_main_option("sqlalchemy.url", database_url)

        command.upgrade(config, "head")

        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                connection.execute(text("PRAGMA foreign_keys = ON"))
                connection.execute(
                    text(
                        """
                        INSERT INTO accounts (
                            account_id, display_name, provider_type, is_active, ai_enabled, created_at, updated_at
                        ) VALUES (
                            'acct-meta-status-valid-samples', 'Meta Status Valid Samples', 'whatsapp', 1, 1,
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO meta_business_portfolios (
                            id, account_id, meta_business_portfolio_id, display_name, status, created_at, updated_at
                        ) VALUES (
                            'portfolio-meta-status-valid-samples', 'acct-meta-status-valid-samples',
                            'biz-meta-status-valid-samples', 'Meta Status Valid Samples', 'active',
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO whatsapp_business_accounts (
                            id, account_id, portfolio_id, waba_id, onboarding_mode, token_source, access_token,
                            webhook_subscribed, webhook_verification_status, webhook_runtime_status, is_active,
                            ai_enabled, created_at, updated_at
                        ) VALUES (
                            'waba-meta-status-valid-samples', 'acct-meta-status-valid-samples',
                            'portfolio-meta-status-valid-samples', 'waba-meta-status-valid-samples',
                            'manual', 'system_user', 'token-meta-status-valid-samples',
                            1, 'failed', 'payload_invalid', 1, 1,
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO webhook_subscriptions (
                            id, account_id, waba_account_id, waba_id, callback_url, verify_token, app_id, status,
                            subscribed_at, created_at, updated_at
                        ) VALUES (
                            'subscription-meta-status-valid-samples', 'acct-meta-status-valid-samples',
                            'waba-meta-status-valid-samples', 'waba-meta-status-valid-samples',
                            'https://example.com/meta-status/valid', 'verify-meta-status-valid', 'app-meta-status-valid',
                            'remote_pending', '2026-06-10 00:00:00',
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO embedded_signup_sessions (
                            id, session_id, account_id, waba_account_id, redirect_uri, provider_name, status,
                            completion_stage, last_event_source, remote_confirmed, linked_phone_number_ids_json,
                            authorization_code_present, system_user_access_token_present, created_at, updated_at
                        ) VALUES (
                            'embedded-meta-status-valid-samples', 'embedded-meta-status-valid-samples',
                            'acct-meta-status-valid-samples', 'waba-meta-status-valid-samples',
                            'https://example.com/meta-status/embedded-valid', 'mock', 'completed',
                            'webhook_verification_pending', 'provider_callback', 0, '[]', 0, 0,
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO embedded_signup_sessions (
                            id, session_id, account_id, waba_account_id, redirect_uri, provider_name, status,
                            completion_stage, last_event_source, remote_confirmed, linked_phone_number_ids_json,
                            authorization_code_present, system_user_access_token_present, created_at, updated_at
                        ) VALUES (
                            'embedded-meta-status-valid-remote-confirmed',
                            'embedded-meta-status-valid-remote-confirmed',
                            'acct-meta-status-valid-samples', 'waba-meta-status-valid-samples',
                            'https://example.com/meta-status/embedded-remote-confirmed', 'mock', 'completed',
                            'remote_confirmed', 'system_sync', 1, '[]', 0, 0,
                            '2026-06-10 00:00:00', '2026-06-10 00:00:00'
                        )
                        """
                    )
                )

            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT
                            portfolio.status AS portfolio_status,
                            waba.webhook_verification_status,
                            waba.webhook_runtime_status,
                            subscription.status AS subscription_status,
                            session.status AS session_status,
                            session.completion_stage,
                            session.last_event_source,
                            session.remote_confirmed
                        FROM meta_business_portfolios AS portfolio
                        JOIN whatsapp_business_accounts AS waba
                            ON waba.portfolio_id = portfolio.id
                        JOIN webhook_subscriptions AS subscription
                            ON subscription.waba_account_id = waba.id
                        JOIN embedded_signup_sessions AS session
                            ON session.waba_account_id = waba.id
                        WHERE portfolio.account_id = 'acct-meta-status-valid-samples'
                        ORDER BY session.session_id
                        """
                    )
                ).mappings().all()

                assert rows == [
                    {
                        "portfolio_status": "active",
                        "webhook_verification_status": "failed",
                        "webhook_runtime_status": "payload_invalid",
                        "subscription_status": "remote_pending",
                        "session_status": "completed",
                        "completion_stage": "remote_confirmed",
                        "last_event_source": "system_sync",
                        "remote_confirmed": 1,
                    },
                    {
                        "portfolio_status": "active",
                        "webhook_verification_status": "failed",
                        "webhook_runtime_status": "payload_invalid",
                        "subscription_status": "remote_pending",
                        "session_status": "completed",
                        "completion_stage": "webhook_verification_pending",
                        "last_event_source": "provider_callback",
                        "remote_confirmed": 0,
                    }
                ]
        finally:
            engine.dispose()


def test_alembic_role_permission_templates_seed_canonical_permissions() -> None:
    migration_path = Path("alembic/versions/20260619_0101_role_permissions.py")
    module_spec = importlib.util.spec_from_file_location(
        "test_role_permissions_migration",
        migration_path,
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    migration = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    original_op = migration.op
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE agencies (id VARCHAR(36) PRIMARY KEY)"))
            context = MigrationContext.configure(connection)
            migration.op = Operations(context)
            migration.upgrade()

        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT role_name, permissions, is_template, created_by
                    FROM role_permissions
                    WHERE agency_id IS NULL
                    ORDER BY role_name
                    """
                )
            ).mappings().all()

        assert rows == [
            {
                "role_name": role_name,
                "permissions": json.dumps(DEFAULT_TEMPLATES[role_name]["permissions"]),
                "is_template": 1,
                "created_by": "system",
            }
            for role_name in sorted(DEFAULT_TEMPLATES)
        ]
    finally:
        migration.op = original_op
        engine.dispose()
