"""Tests for log sanitization and audit log hardening."""

from app.core.logging import sanitize_log_processor, _mask_sensitive_value


def test_mask_phone_number() -> None:
    """Phone numbers should be masked as 138****1234."""
    assert _mask_sensitive_value("phone_number", "13812341234") == "138****1234"
    assert _mask_sensitive_value("phone_number", "8613812341234") == "861****1234"
    assert _mask_sensitive_value("phone_number", "12") == "12****"
    assert _mask_sensitive_value("phone_number", "") == ""


def test_mask_token() -> None:
    """Tokens should be masked as ***...abc (last 3 chars)."""
    assert _mask_sensitive_value("access_token", "abc123xyz") == "***...xyz"
    assert _mask_sensitive_value("access_token", "ab") == "***...ab"
    assert _mask_sensitive_value("access_token", "") == ""


def test_mask_password() -> None:
    """Passwords should be masked as ***."""
    assert _mask_sensitive_value("password", "my_secret_pwd") == "***"
    assert _mask_sensitive_value("password", "") == ""


def test_mask_secret() -> None:
    """Secrets should be masked as ***...last3."""
    assert _mask_sensitive_value("app_secret", "my_app_secret_key") == "***...key"
    assert _mask_sensitive_value("whatsapp_token", "EAAxExample") == "***...ple"


def test_sanitize_processor_masks_sensitive_keys() -> None:
    """The structlog processor should mask sensitive field values."""
    event = {
        "event": "Sending message",
        "access_token": "EAAxSecret123",
        "phone_number": "13812341234",
        "account_id": "acc-001",
    }
    result = sanitize_log_processor(None, "info", event)  # type: ignore[arg-type]
    assert result["access_token"] == "***...123"
    assert result["phone_number"] == "138****1234"
    assert result["account_id"] == "acc-001"
    assert result["event"] == "Sending message"


def test_sanitize_processor_recursive_dict() -> None:
    """The processor should recursively sanitize nested dicts."""
    event = {
        "event": "Processing",
        "config": {
            "phone_number": "13812341234",
            "tokens": {
                "access_token": "EAAxSuperSecret",
            },
            "display_name": "Test Account",
        },
    }
    result = sanitize_log_processor(None, "info", event)  # type: ignore[arg-type]
    assert result["config"]["phone_number"] == "138****1234"
    assert result["config"]["tokens"]["access_token"] == "***...ret"
    assert result["config"]["display_name"] == "Test Account"
    assert result["event"] == "Processing"


def test_sanitize_processor_list_of_dicts() -> None:
    """The processor should sanitize dict items inside lists."""
    event = {
        "accounts": [
            {"account_id": "acc-001", "access_token": "tok123"},
            {"account_id": "acc-002", "phone_number": "13912341234"},
        ],
    }
    result = sanitize_log_processor(None, "info", event)  # type: ignore[arg-type]
    assert result["accounts"][0]["access_token"] == "***...123"
    assert result["accounts"][0]["account_id"] == "acc-001"
    assert result["accounts"][1]["phone_number"] == "139****1234"


def test_sanitize_processor_preserves_non_sensitive() -> None:
    """Non-sensitive fields should be preserved as-is."""
    event = {
        "event": "Test",
        "conversation_id": "conv-123",
        "message": "Hello world",
        "count": 42,
        "active": True,
    }
    result = sanitize_log_processor(None, "info", event)  # type: ignore[arg-type]
    assert result["event"] == "Test"
    assert result["conversation_id"] == "conv-123"
    assert result["message"] == "Hello world"
    assert result["count"] == 42
    assert result["active"] is True
