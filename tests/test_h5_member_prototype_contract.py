from pathlib import Path
import codecs


ROOT = Path(__file__).resolve().parents[1]


def u(value: str) -> str:
    return codecs.decode(value, "unicode_escape")


def test_h5_member_app_exposes_primary_navigation_and_entry_points() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "H5App.tsx").read_text(encoding="utf-8")

    required = (
        u(r"\u9996\u9875"),
        u(r"\u4efb\u52a1"),
        u(r"\u6d88\u606f"),
        u(r"\u6211\u7684"),
        u(r"\u767b\u5f55"),
        u(r"\u6ce8\u518c"),
        u(r"\u65b0\u5efa\u5de5\u5355"),
        u(r"\u63d0\u73b0\u6392\u884c\u699c"),
        u(r"\u7a8e\u7247\u80cc\u5305"),
        "WhatsApp",
    )

    for snippet in required:
        assert snippet in source


def test_h5_member_app_uses_native_app_shell_contract() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "H5App.tsx").read_text(encoding="utf-8")

    required = (
        "h5-member-app-shell",
        "h5-member-topbar",
        "h5-member-content",
        "h5-member-tabbar",
        "h5-member-safe-bottom",
        "h5-member-segmented",
        "h5-member-segmented-chip",
        "h5-member-segmented-chip-active",
        "h5-member-topbar-pill",
        "h5-member-topbar-account",
        "h5-member-tabbar-item-active",
        "h5-member-auth-switch",
        "h5-member-auth-tab-active",
        "h5-member-auth-benefits",
        "h5-member-password-field",
        "h5-member-password-toggle",
        "EyeOutlined",
        "EyeInvisibleOutlined",
        "h5-member-toast-stack",
        "h5-member-toast",
        "h5-member-toast-progress",
        "h5-member-profile-menu",
        "h5-member-profile-group-title",
        "h5-member-profile-avatar",
        "h5-member-profile-balance-strip",
        "h5-member-profile-balance-card",
        "h5-member-home-primary",
    )

    for snippet in required:
        assert snippet in source


def test_h5_member_styles_define_native_app_shell_classes() -> None:
    source = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

    required = (
        ".h5-member-app-shell",
        ".h5-member-topbar",
        ".h5-member-content",
        ".h5-member-tabbar",
        ".h5-member-safe-bottom",
        ".h5-member-segmented",
        ".h5-member-segmented-chip",
        ".h5-member-segmented-chip-active",
        ".h5-member-topbar-pill",
        ".h5-member-topbar-account",
        ".h5-member-tabbar-item-active",
        ".h5-member-auth-switch",
        ".h5-member-auth-tab-active",
        ".h5-member-auth-benefits",
        ".h5-member-password-field",
        ".h5-member-password-toggle",
        ".h5-member-toast-stack",
        ".h5-member-toast",
        ".h5-member-toast-progress",
        ".h5-member-profile-menu",
        ".h5-member-profile-group-title",
        ".h5-member-profile-avatar",
        ".h5-member-profile-balance-strip",
        ".h5-member-profile-balance-card",
        ".h5-member-home-primary",
    )

    for snippet in required:
        assert snippet in source


def test_h5_member_app_keeps_v5_experience_contract() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "H5App.tsx").read_text(encoding="utf-8")

    required = (
        u(r"\u7ee7\u7eed\u4efb\u52a1"),
        u(r"\u7acb\u5373\u9886\u53d6"),
        u(r"\u8fdb\u884c\u4e2d\u4efb\u52a1"),
        u(r"\u4eca\u5929"),
        u(r"\u6628\u5929"),
        u(r"\u66f4\u65e9"),
        u(r"\u91cd\u8981\u901a\u77e5"),
        u(r"\u5176\u4ed6\u6d88\u606f"),
        u(r"\u786e\u8ba4\u9886\u53d6\u4efb\u52a1\u5305"),
        u(r"\u5f53\u524d\u72b6\u6001"),
        "h5-member-home-task-focus",
        "h5-member-task-summary",
        "h5-member-task-media",
        "h5-member-message-group",
        "h5-member-tabbar-badge",
        "h5-member-profile-group",
        "h5-member-fragment-progress",
        "h5-member-home-focus-metrics",
        "h5-member-purchase-flow",
        "h5-member-wallet-action-card",
        "h5-member-fragment-steps",
        "h5-member-amount-chip-active",
        "h5-member-message-section",
        u(r"\u7b2c 3 \u6b65\uff1a\u586b\u5199\u6536\u8d27\u4fe1\u606f"),
        u(r"\u7b2c 4 \u6b65\uff1a\u7b49\u5f85\u90ae\u5bc4"),
    )

    for snippet in required:
        assert snippet in source


def test_h5_member_styles_define_v5_experience_classes() -> None:
    source = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

    required = (
        ".h5-member-home-task-focus",
        ".h5-member-task-summary",
        ".h5-member-task-media",
        ".h5-member-message-group",
        ".h5-member-tabbar-badge",
        ".h5-member-profile-group",
        ".h5-member-fragment-progress",
        ".h5-member-home-focus-metrics",
        ".h5-member-purchase-flow",
        ".h5-member-wallet-action-card",
        ".h5-member-fragment-steps",
        ".h5-member-amount-chip-active",
        ".h5-member-message-section",
    )

    for snippet in required:
        assert snippet in source


def test_h5_member_app_keeps_v5_information_architecture_labels() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "H5App.tsx").read_text(encoding="utf-8")

    required = (
        'label: "首页"',
        'label: "任务"',
        'label: "消息"',
        'label: "我的"',
        u(r"\u8d44\u91d1\u670d\u52a1"),
        u(r"\u8bb0\u5f55\u4e0e\u5de5\u5177"),
        u(r"\u5e73\u53f0\u670d\u52a1"),
        "h5-member-message-card-unread",
        "h5-member-message-group-title",
        u(r"\u6253\u5f00\u7ed1\u5b9a\u5165\u53e3"),
        "Meta / WhatsApp",
        u(r"\u5df2\u6253\u5f00 WhatsApp \u7ed1\u5b9a\u539f\u578b\u5165\u53e3"),
        u(r"\u767b\u5f55\u4f1a\u5458\u7aef"),
        u(r"\u521b\u5efa\u4f1a\u5458\u8d26\u53f7"),
    )

    for snippet in required:
        assert snippet in source


def test_h5_member_mock_service_keeps_package_wallet_and_fragment_contracts() -> None:
    source = (ROOT / "frontend" / "src" / "services" / "h5Member.ts").read_text(encoding="utf-8")

    required = (
        'export type H5TaskPackageStatus = "pending_claim" | "active" | "completed" | "expired";',
        'export type H5PromotionMetric = "invited_registrations" | "recharged_invitees";',
        'export type H5WithdrawStatus = "submitted" | "reviewing" | "approved" | "rejected" | "paid";',
        'export type H5RewardShippingStatus =',
        '"pending_address"',
        '"submitted"',
        '"packing"',
        '"shipped"',
        '"delivered"',
        '"completed"',
        'const ACCOUNT_ID_LENGTH = 8;',
        'function generateUniqueNumericAccountId()',
        'export async function claimTaskPackage(',
        'export async function completeTaskPackagePurchase(',
        'export async function createRechargeOrder(',
        'export async function transferTaskBalanceToSystem(',
        'export async function createWithdrawRequest(',
        'export async function performDailyCheckIn(',
        'export async function createFragmentExchange(',
    )

    for snippet in required:
        assert snippet in source


def test_h5_backend_gap_report_lists_missing_capabilities_for_backend_thread() -> None:
    source = (ROOT / "docs" / "h5-backend-gap-report.md").read_text(encoding="utf-8")

    required = (
        "task_package_templates",
        "wallet_accounts",
        "wallet_withdraw_requests",
        "message_center_items",
        "promotion_task_templates",
        "fragment_definitions",
        "reward_shipping_orders",
        "/api/h5/task-packages/*",
        "/api/h5/wallet/*",
        "/api/h5/withdraw-leaderboard",
        "/api/h5/fragments/*",
    )

    for snippet in required:
        assert snippet in source
