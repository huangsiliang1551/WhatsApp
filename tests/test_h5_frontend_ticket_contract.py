from pathlib import Path
import codecs
import re


ROOT = Path(__file__).resolve().parents[1]


def u(value: str) -> str:
    return codecs.decode(value, "unicode_escape")


def test_h5_frontend_keeps_task_appeal_alias_mapping_for_backend_contract() -> None:
    source = (ROOT / "frontend" / "src" / "services" / "h5.ts").read_text(encoding="utf-8")

    assert 'export type SupportTicketCategory = "task_appeal" | "help" | "complaint";' in source
    assert 'if (category === "appeal") {' in source
    assert 'return "task_appeal";' in source
    assert 'ticket_type: payload.category === "task_appeal" ? "appeal" : payload.category,' in source
    assert 'query.set("ticket_type", params.category === "task_appeal" ? "appeal" : params.category);' in source


def test_h5_frontend_keeps_pending_user_as_the_only_public_waiting_status() -> None:
    source = (ROOT / "frontend" / "src" / "services" / "h5.ts").read_text(encoding="utf-8")

    assert re.search(r'if \(status === "waiting_user"\) \{\s*return "pending_user";\s*\}', source)
    assert re.search(
        r'export type SupportTicketStatus =\s*\|\s*"open"\s*\|\s*"in_progress"\s*\|\s*"pending_user"',
        source,
    )
    assert '"waiting_user"' not in source.split("export type SupportTicketStatus =", 1)[1].split(
        ";", 1
    )[0]


def test_review_and_ticket_pages_keep_rejected_follow_up_guidance() -> None:
    reviews_source = (ROOT / "frontend" / "src" / "pages" / "ReviewsPage.tsx").read_text(
        encoding="utf-8"
    )
    tickets_source = (ROOT / "frontend" / "src" / "pages" / "TicketsPage.tsx").read_text(
        encoding="utf-8"
    )

    assert u(
        r"\u8be5\u63d0\u4ea4\u5df2\u9a73\u56de\uff1b\u540e\u7eed\u5e94\u8f6c\u4efb\u52a1\u7533\u8bc9\u6216\u5e2e\u52a9\u5de5\u5355\uff0c\u4e0d\u5e94\u518d\u6b21\u76f4\u63a5\u5ba1\u6838\u3002"
    ) in reviews_source
    assert u(
        r"\u8bf7\u57fa\u4e8e\u6700\u8fd1\u4e00\u6b21\u63d0\u4ea4\u548c\u5ba1\u6838\u5907\u6ce8\u7ed9\u51fa\u7ed3\u8bba\uff1b\u9a73\u56de\u540e\u4e0d\u8981\u6697\u793a\u7528\u6237\u53ef\u76f4\u63a5\u91cd\u65b0\u63d0\u4ea4\uff0c\u800c\u5e94\u5f15\u5bfc\u81f3\u4efb\u52a1\u7533\u8bc9\u6216\u5e2e\u52a9\u5de5\u5355\u3002"
    ) in reviews_source
    assert u(
        r"\u5f53\u524d\u5de5\u5355\u5df2\u9a73\u56de\u5e76\u7ed3\u675f\uff1b\u5982\u5173\u8054\u4efb\u52a1\u4e5f\u5df2\u9a73\u56de\uff0c\u8bf7\u8f6c\u4efb\u52a1\u7533\u8bc9\u6216\u65b0\u5efa\u5e2e\u52a9\u5de5\u5355\u7ee7\u7eed\u5904\u7406\u3002"
    ) in tickets_source
    assert u(
        r"\u8be5\u5de5\u5355\u5df2\u7ecf\u6309\u5f53\u524d\u94fe\u8def\u9a73\u56de\u7ed3\u675f\uff0c\u4e0d\u8981\u5f15\u5bfc\u7528\u6237\u76f4\u63a5\u91cd\u65b0\u63d0\u4ea4\u5173\u8054\u4efb\u52a1\uff0c\u4e5f\u4e0d\u8981\u6697\u793a\u4efb\u52a1\u4f1a\u6062\u590d\u63d0\u4ea4\u5165\u53e3\u3002"
    ) in tickets_source


def test_reviews_page_exposes_member_verification_and_whatsapp_binding_queues() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "ReviewsPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "listPlatformMemberVerifications",
        "updatePlatformMemberVerificationStatus",
        "listPlatformMemberWhatsAppBindings",
        "updatePlatformMemberWhatsAppBindingStatus",
        u(r"\u4f1a\u5458\u8ba4\u8bc1"),
        u(r"WhatsApp \u7ed1\u5b9a"),
        u(r"\u5ba1\u6838\u961f\u5217"),
    )

    for snippet in required_snippets:
        assert snippet in source


def test_reviews_page_links_member_review_detail_to_users_and_customers_pages() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "ReviewsPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "openUsersPage",
        "openCustomersPage",
        'selected_user_id: selectedVerificationItem.userId',
        'selected_user_id: selectedBindingItem.userId',
        'selected_profile_id: selectedVerificationItem.userId',
        'selected_profile_id: selectedBindingItem.userId',
        'query: selectedVerificationItem.publicUserId',
        'query: selectedBindingItem.publicUserId',
        u(r"\u7528\u6237\u9875"),
        u(r"\u5ba2\u6237\u9875"),
    )

    for snippet in required_snippets:
        assert snippet in source


def test_users_page_links_to_customers_page_with_selected_profile_id() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "UsersPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "openCustomersPage",
        'selected_profile_id: record.id',
        'selected_profile_id: selectedUser.id',
        'query: record.public_user_id',
        'query: selectedUser.public_user_id',
    )

    for snippet in required_snippets:
        assert snippet in source


def test_customers_page_surfaces_member_verification_and_whatsapp_binding_status() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "CustomersPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "getCustomerMemberStatusSnapshot",
        "listPlatformUserMemberStatusIndex",
        "detail.profile.public_user_id",
        "detail.profile.account_id",
        u(r"\u4f1a\u5458\u8ba4\u8bc1\u72b6\u6001"),
        u(r"WhatsApp \u7ed1\u5b9a\u72b6\u6001"),
    )

    for snippet in required_snippets:
        assert snippet in source

    assert "listPlatformMemberVerifications" not in source
    assert "listPlatformMemberWhatsAppBindings" not in source


def test_customers_page_lists_member_verification_and_binding_status_summaries() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "CustomersPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "customerMemberStatusIndex",
        'title: "会员认证"',
        'title: "WhatsApp 绑定"',
        "latestVerificationStatus",
        "latestBindingStatus",
    )

    for snippet in required_snippets:
        assert snippet in source


def test_users_page_surfaces_member_verification_and_whatsapp_binding_status() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "UsersPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "getPlatformUserMemberStatusSnapshot",
        "listPlatformUserMemberStatusIndex",
        "selectedUser.public_user_id",
        "selectedUser.account_id",
        u(r"\u4f1a\u5458\u8ba4\u8bc1\u72b6\u6001"),
        u(r"WhatsApp \u7ed1\u5b9a\u72b6\u6001"),
    )

    for snippet in required_snippets:
        assert snippet in source

    assert "listPlatformMemberVerifications" not in source
    assert "listPlatformMemberWhatsAppBindings" not in source


def test_users_page_lists_member_verification_and_binding_status_summaries() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "UsersPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "userMemberStatusIndex",
        'title: "会员认证"',
        'title: "WhatsApp 绑定"',
        "latestVerificationStatus",
        "latestBindingStatus",
    )

    for snippet in required_snippets:
        assert snippet in source


def test_tickets_page_surfaces_member_verification_and_whatsapp_binding_status() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "TicketsPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "getPlatformUserMemberStatusSnapshot",
        "openCustomersPage",
        "detail.public_user_id",
        "detail.account_id",
        "Member Verification Status",
        "WhatsApp Binding Status",
        'query: detail.public_user_id',
    )

    for snippet in required_snippets:
        assert snippet in source

    assert "listPlatformMemberVerifications" not in source
    assert "listPlatformMemberWhatsAppBindings" not in source
    assert "listPlatformUserMemberStatusIndex" not in source


def test_tasks_page_lists_member_verification_and_binding_status_summaries() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "TasksPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "listPlatformUserMemberStatusIndex",
        "taskInstanceMemberStatusIndex",
        'title: "浼氬憳璁よ瘉"',
        'title: "WhatsApp 缁戝畾"',
        "latestVerificationStatus",
        "latestBindingStatus",
        "record.user_id",
    )

    for snippet in required_snippets:
        assert snippet in source


def test_operations_center_page_lists_member_verification_and_binding_status_summaries() -> None:
    page_source = (ROOT / "frontend" / "src" / "pages" / "OperationsCenterPage.tsx").read_text(
        encoding="utf-8"
    )
    service_source = (ROOT / "frontend" / "src" / "services" / "operations.ts").read_text(
        encoding="utf-8"
    )
    type_source = (ROOT / "frontend" / "src" / "types" / "operations.ts").read_text(
        encoding="utf-8"
    )

    required_page_snippets = (
        "listPlatformUserMemberStatusIndex",
        "taskMemberStatusIndex",
        'title: "浼氬憳璁よ瘉"',
        'title: "WhatsApp 缁戝畾"',
        "latestVerificationStatus",
        "latestBindingStatus",
        "record.user_id",
    )

    for snippet in required_page_snippets:
        assert snippet in page_source

    assert "user_id: task.user_id" in service_source
    assert "user_id: string;" in type_source


def test_operations_center_page_exposes_customer_page_jump_for_member_status_rows() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "OperationsCenterPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "openCustomersPage",
        "selected_profile_id: record.user_id",
        'query: record.public_user_id',
    )

    for snippet in required_snippets:
        assert snippet in source


def test_tasks_page_exposes_customer_page_jump_for_member_status_rows() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "TasksPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "openCustomersPage",
        "selected_profile_id: record.user_id",
        'query: record.public_user_id',
    )

    for snippet in required_snippets:
        assert snippet in source


def test_h5_task_page_keeps_rejected_submission_blocked_copy() -> None:
    source = (ROOT / "frontend" / "src" / "services" / "h5.ts").read_text(encoding="utf-8")

    assert u(
        r"\u4efb\u52a1\u5df2\u88ab\u9a73\u56de\uff0c\u8bf7\u6839\u636e\u5ba1\u6838\u5907\u6ce8\u53d1\u8d77\u4efb\u52a1\u7533\u8bc9\u6216\u5e2e\u52a9\u5de5\u5355\uff0c\u5f53\u524d\u4efb\u52a1\u4e0d\u80fd\u76f4\u63a5\u91cd\u65b0\u63d0\u4ea4\u3002"
    ) in source
    assert u(
        r"\u53ea\u6709\u5df2\u9a73\u56de\u4e14\u5b58\u5728\u6700\u8fd1\u4e00\u6b21\u63d0\u4ea4\u6d41\u6c34\u7684\u4efb\u52a1\uff0c\u624d\u80fd\u53d1\u8d77\u4efb\u52a1\u7533\u8bc9\uff1b\u5426\u5219\u53ea\u80fd\u5148\u53d1\u8d77\u5e2e\u52a9\u5de5\u5355\u3002"
    ) in source


def test_template_page_keeps_core_labels_and_send_verification_copy() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "TemplatePage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        '{ value: "UTILITY", label: "' + u(r"\u901a\u77e5\u670d\u52a1") + '" },',
        '{ value: "PENDING", label: "' + u(r"\u5f85\u5ba1\u6838") + '" },',
        '{ value: "APPROVED", label: "' + u(r"\u5ba1\u6838\u901a\u8fc7") + '" },',
        '{ value: "REJECTED", label: "' + u(r"\u5ba1\u6838\u62d2\u7edd") + '" },',
        '{ value: "SENT", label: "' + u(r"\u5df2\u53d1\u9001") + '" },',
        u(r"\u9875\u9762\u4ec5\u5c55\u793a\u5f53\u524d\u6b63\u5f0f\u72b6\u6001\uff0c\u4e0d\u518d\u663e\u793a\u65e7\u72b6\u6001\u522b\u540d\u3002"),
        u(r"\u6a21\u677f\u8be6\u60c5"),
        u(r"\u6a21\u677f\u72b6\u6001\u7ef4\u62a4"),
        u(r"\u6a21\u677f\u540c\u6b65"),
        u(r"\u6a21\u677f\u53d1\u9001\u9a8c\u8bc1"),
        u(r"\u6a21\u677f\u7edf\u8ba1"),
        u(r"\u53d1\u9001\u65e5\u5fd7"),
        u(
            r"\u4ec5\u5ba1\u6838\u901a\u8fc7\u7684\u6a21\u677f\u5141\u8bb8\u76f4\u63a5\u53d1\u9001\u3002\u586b\u5199\u5916\u90e8\u4f1a\u8bdd ID \u540e\uff0c\u7ed3\u679c\u4f1a\u540c\u65f6\u5c55\u793a\u5916\u90e8\u4f1a\u8bdd ID \u548c\u5185\u90e8\u4f1a\u8bdd ID\u3002"
        ),
        u(r"\u53d1\u9001\u65e5\u5fd7\u6309\u8d26\u53f7\u3001\u6a21\u677f\u548c\u53f7\u7801\u7ef4\u5ea6\u4fdd\u7559\u3002"),
        "`conversation_id` " + u(r"\u4ec5\u7528\u4e8e\u517c\u5bb9\u56de\u586b\u3002"),
    )

    for snippet in required_snippets:
        assert snippet in source

    assert "waiting_user" not in source
    assert u(r"\u91cd\u65b0\u63d0\u4ea4") not in source


def test_dashboard_page_accepts_formal_activation_readiness_copy() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "DashboardPage.tsx").read_text(
        encoding="utf-8"
    )

    assert "ready for (formal )?activation" in source
    assert "fully ready for (formal )?activation" in source
    assert u(r"\u6b63\u5f0f\u6fc0\u6d3b\u5c31\u7eea\u72b6\u6001") in source


def test_chat_page_surfaces_member_verification_and_whatsapp_binding_status() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "ChatPage.tsx").read_text(
        encoding="utf-8"
    )

    required_snippets = (
        "resolveCustomerProfileSummaryByConversation",
        "getCustomerMemberStatusSnapshot",
        "selectedConversation.account_id",
        "selectedConversation.customer_id",
        "openCustomersPage",
        'selected_profile_id: resolvedCustomerProfile?.id',
        u(r"\u4f1a\u5458\u8ba4\u8bc1\u72b6\u6001"),
        u(r"WhatsApp \u7ed1\u5b9a\u72b6\u6001"),
    )

    for snippet in required_snippets:
        assert snippet in source

    assert "listPlatformMemberVerifications" not in source
    assert "listPlatformMemberWhatsAppBindings" not in source
    assert "listPlatformUserMemberStatusIndex" not in source


def test_chat_page_keeps_template_status_copy_aligned_with_template_page() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "ChatPage.tsx").read_text(
        encoding="utf-8"
    )

    assert u(r"\u5ba1\u6838\u901a\u8fc7") in source
    assert u(r"\u5ba1\u6838\u62d2\u7edd") in source
    assert u(
        r"\u804a\u5929\u5feb\u6377\u53d1\u9001\u4ec5\u652f\u6301\u5ba1\u6838\u901a\u8fc7\u6a21\u677f\uff0c\u8bf7\u5148\u5728\u6a21\u677f\u7ba1\u7406\u4e2d\u7b49\u5f85\u6a21\u677f\u5ba1\u6838\u901a\u8fc7\u3002"
    ) in source
    assert u(r"\u5df2\u6279\u51c6") not in source
    assert u(r"\u5df2\u62d2\u7edd") not in source


def test_meta_accounts_page_distinguishes_local_ready_from_formal_activation() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "MetaAccountsPage.tsx").read_text(
        encoding="utf-8"
    )

    assert u(r"\u53ef\u6b63\u5f0f\u6fc0\u6d3b") in source
    assert u(r"\u6839\u8def\u7531\u51b2\u7a81") in source
    assert u(r"\u672c\u5730\u5df2\u5c31\u7eea") in source
    assert u(r"\u672c\u5730\u5c31\u7eea") in source
    assert (
        u(r"\u672c\u5730\u524d\u7f6e\u6761\u4ef6\u5df2\u9f50\uff0c\u4f46\u6839 Webhook \u8def\u7531\u51b2\u7a81\u4ecd\u963b\u585e\u6b63\u5f0f\u6fc0\u6d3b\u3002")
        in source
    )
    assert (
        u(r"\u5f53\u524d\u4ec5\u8868\u793a\u672c\u5730 Webhook \u548c\u51fa\u7ad9\u524d\u7f6e\u6761\u4ef6\u5df2\u9f50\uff1b\u6b63\u5f0f\u6fc0\u6d3b\u4ecd\u4ee5 Launch Readiness \u4e3a\u51c6\u3002")
        in source
    )
    assert u(r"\u53ef\u6fc0\u6d3b") not in source
