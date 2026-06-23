from pathlib import Path
import codecs


ROOT = Path(__file__).resolve().parents[1]


def u(value: str) -> str:
    return codecs.decode(value, "unicode_escape")


def test_chat_page_keeps_handover_recommendation_visible_in_workspace() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "ChatPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "latest_handover_recommended",
        "latest_handover_reason",
        'handoverMode: "all" | "recommended" | "normal";',
        u(r"\u63a8\u8350\u8f6c\u4eba\u5de5"),
        u(r"\u666e\u901a\u4f1a\u8bdd"),
        u(r"\u63a5\u7ba1\u5efa\u8bae"),
        u(r"\u5efa\u8bae\u539f\u56e0"),
        u(r"\u4ec5\u63a8\u8350\u8f6c\u4eba\u5de5"),
    )

    for snippet in required_snippets:
        assert snippet in source


def test_chat_page_keeps_handover_filter_mapping_and_workspace_prefill_contract() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "ChatPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        'filters.handoverMode === "recommended"',
        'filters.handoverMode === "normal"',
        "latest_handover_recommended: latestHandoverRecommended",
        "workspacePagePrefill.handoverMode ?? \"all\"",
        "resolveConversationSelectionKey(",
        "workspacePagePrefill.accountId",
    )

    for snippet in required_snippets:
        assert snippet in source
