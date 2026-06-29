from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import scripts.ci_collect_core_tests as ci_collect_core_tests


def _completed_process(stdout: str, returncode: int = 0, stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_ci_collect_core_tests_passes_when_all_required_groups_are_present(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        ci_collect_core_tests.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process(
            "\n".join(
                [
                        "tests/api/test_h5_gateway_api.py::test_h5_gateway_node_crud_and_test_ssh",
                        "tests/api/test_payment_callback_idempotency.py::test_payment_callback_route_is_idempotent",
                        "tests/api/test_finance_reports.py::test_finance_summary_supports_excluding_bonus_via_query_flag",
                        "tests/api/test_permissions_funnel_api.py::test_effective_access_endpoint_returns_permission_and_scope_summary",
                        "tests/services/test_wallet_idempotency.py::test_credit_system_balance_is_idempotent_by_key",
                        "tests/services/test_platform_withdrawal_service.py::test_platform_reject_withdrawal_restores_wallet_and_writes_refund_ledger",
                    "tests/services/test_whatsapp_inbound_command_router.py::test_bind_command_is_handled_before_ai",
                    "tests/test_webhook_dedup_idempotent.py::test_duplicate_inbound_message_creates_only_one_row",
                ]
            )
        ),
    )

    exit_code = ci_collect_core_tests.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["missing_groups"] == []
    assert payload["collected_count"] == 8


def test_ci_collect_core_tests_fails_when_core_groups_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        ci_collect_core_tests.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process(
            "\n".join(
                [
                    "tests/test_auth.py::test_account_scope_blocks_cross_account_read",
                    "tests/test_h5_member_auth.py::test_h5_login_with_valid_user",
                ]
            )
        ),
    )

    exit_code = ci_collect_core_tests.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert "tests/api" in payload["missing_groups"]
    assert "tests/services" in payload["missing_groups"]
    assert "payment" in payload["missing_groups"]
    assert "permission" in payload["missing_groups"]


def test_ci_collect_core_tests_fails_when_pytest_collection_command_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        ci_collect_core_tests.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process("", returncode=2, stderr="collection exploded"),
    )

    exit_code = ci_collect_core_tests.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["ok"] is False
    assert payload["error"] == "pytest collection failed"
    assert "collection exploded" in payload["stderr"]


def test_check_production_readiness_main_returns_zero_for_safe_development_settings(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import scripts.check_production_readiness as check_production_readiness

    monkeypatch.setattr(
        check_production_readiness,
        "get_settings",
        lambda: SimpleNamespace(app_env="development", test_mode=False),
    )
    monkeypatch.setattr(check_production_readiness, "collect_production_issues", lambda settings: [])

    exit_code = check_production_readiness.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["issue_count"] == 0


def test_check_production_readiness_main_returns_one_for_blocking_issues(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import scripts.check_production_readiness as check_production_readiness
    from app.core.production_guard import ProductionGuardIssue

    monkeypatch.setattr(
        check_production_readiness,
        "get_settings",
        lambda: SimpleNamespace(app_env="production", test_mode=False),
    )
    monkeypatch.setattr(
        check_production_readiness,
        "collect_production_issues",
        lambda settings: [
            ProductionGuardIssue(code="UNSAFE_ADMIN_JWT_SECRET", message="bad"),
            ProductionGuardIssue(code="MOCK_AI_PROVIDER", message="warn", severity="A"),
        ],
    )

    exit_code = check_production_readiness.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["blocking_issue_count"] == 1
    assert payload["advisory_issue_count"] == 1
