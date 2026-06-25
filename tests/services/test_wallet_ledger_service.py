"""Plan-aligned alias for wallet ledger coverage.

Canonical tests currently live in the top-level `tests/` modules.
This file exists so the documented `tests/services/...` path is real.
"""

from tests.test_finance_report_service import *  # noqa: F401,F403
from tests.test_h5_withdrawals import *  # noqa: F401,F403
from tests.test_payment_callback_wallet_credit import *  # noqa: F401,F403
