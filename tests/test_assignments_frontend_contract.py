from pathlib import Path
import codecs


ROOT = Path(__file__).resolve().parents[1]


def u(value: str) -> str:
    return codecs.decode(value, "unicode_escape")


def test_assignments_page_surfaces_handover_recommendation_filters_and_workspace_context() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "AssignmentsPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        'type HandoverRecommendationFilter = "all" | "recommended" | "normal";',
        "latest_handover_recommended:",
        u(r"\u5168\u90e8\u63a5\u7ba1\u5efa\u8bae"),
        u(r"\u4ec5\u63a8\u8350\u8f6c\u4eba\u5de5"),
        u(r"\u4ec5\u666e\u901a\u4f1a\u8bdd"),
        u(r"\u63a8\u8350\u8f6c\u4eba\u5de5"),
        "handoverMode:",
        "search:",
    )

    for snippet in required_snippets:
        assert snippet in source


def test_assignments_page_uses_shared_customer_member_status_context() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "AssignmentsPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "resolveCustomerProfileSummaryByConversation",
        "useMemberStatus",
        "selectedConversation.account_id",
        "selectedConversation.customer_id",
        u(r"\u4f1a\u5458\u8ba4\u8bc1\u72b6\u6001"),
        u(r"WhatsApp \u7ed1\u5b9a\u72b6\u6001"),
    )

    for snippet in required_snippets:
        assert snippet in source

    forbidden_snippets = (
        "listPlatformMemberVerifications",
        "listPlatformMemberWhatsAppBindings",
    )

    for snippet in forbidden_snippets:
        assert snippet not in source
