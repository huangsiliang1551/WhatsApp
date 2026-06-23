import logging
import re

import structlog
from structlog.contextvars import merge_contextvars

SENSITIVE_FIELD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"access_token", re.IGNORECASE), "access_token"),
    (re.compile(r"app_secret", re.IGNORECASE), "app_secret"),
    (re.compile(r"verify_token", re.IGNORECASE), "verify_token"),
    (re.compile(r"password", re.IGNORECASE), "password"),
    (re.compile(r"secret", re.IGNORECASE), "secret"),
    (re.compile(r"token", re.IGNORECASE), "token"),
    (re.compile(r"api_key", re.IGNORECASE), "api_key"),
    (re.compile(r"phone_number", re.IGNORECASE), "phone_number"),
    (re.compile(r"whatsapp_token", re.IGNORECASE), "whatsapp_token"),
]


def _mask_sensitive_value(field_name: str, value: str) -> str:
    """Mask a sensitive value based on the field name pattern."""
    value_str = str(value) if value is not None else ""
    if not value_str:
        return value_str

    fname_lower = field_name.lower()
    if "phone" in fname_lower or "phone_number" in fname_lower:
        # Phone: 138****1234
        stripped = value_str.strip()
        if len(stripped) >= 7:
            return stripped[:3] + "****" + stripped[-4:]
        return stripped[:2] + "****" if len(stripped) >= 2 else "****"

    if "password" in fname_lower:
        return "***"

    # Token / Secret / Key: ***...abc (last 3 chars)
    stripped = value_str.strip()
    if len(stripped) >= 3:
        return "***..." + stripped[-3:]
    return "***..." + stripped if stripped else "***"


def sanitize_log_processor(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, object],
) -> dict[str, object]:
    """Structlog processor that masks sensitive fields in log events."""
    processed: dict[str, object] = {}
    for key, value in event_dict.items():
        if isinstance(value, str):
            matched = False
            for pattern, field_type in SENSITIVE_FIELD_PATTERNS:
                if pattern.search(key):
                    processed[key] = _mask_sensitive_value(field_type, value)
                    matched = True
                    break
            if not matched:
                processed[key] = value
        elif isinstance(value, dict):
            processed[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            processed[key] = [
                _sanitize_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            processed[key] = value
    return processed


def _sanitize_dict(d: dict[str, object]) -> dict[str, object]:
    """Recursively sanitize a dictionary."""
    result: dict[str, object] = {}
    for key, value in d.items():
        if isinstance(value, str):
            matched = False
            for pattern, field_type in SENSITIVE_FIELD_PATTERNS:
                if pattern.search(key):
                    result[key] = _mask_sensitive_value(field_type, value)
                    matched = True
                    break
            if not matched:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _sanitize_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            sanitize_log_processor,
            structlog.processors.JSONRenderer(),
        ],
    )
