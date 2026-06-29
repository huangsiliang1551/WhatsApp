from __future__ import annotations


def test_legacy_integration_e2e_suite_moved_to_w6_directory() -> None:
    """Legacy root entry kept only as a compatibility sentinel.

    The real scenarios now live under `tests/e2e/test_w6_legacy_integration_e2e_migrated.py`
    and are exercised by the W6 smoke runner.
    """

    assert True
