import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConversationList } from "./ConversationList";

vi.mock("../../components/member/MemberIdLink", async () => {
  const React = await import("react");
  return {
    MemberIdLink: ({
      accountId,
      userId,
      publicUserId,
      label,
    }: {
      accountId?: string | null;
      userId?: string | null;
      publicUserId?: string | null;
      label?: string | null;
    }) =>
      React.createElement("span", null, `member-link:${label ?? ""}:${userId ?? ""}:${publicUserId ?? ""}:${accountId ?? ""}`),
  };
});

vi.mock("../../services/api", async () => {
  const actual = await vi.importActual("../../services/api");
  return {
    ...actual,
    getConversationsMetadataBatch: vi.fn().mockResolvedValue({ items: [] }),
    getConversationPrimaryPreview: (conversation: { last_message_preview?: string | null }) => conversation.last_message_preview ?? "",
  };
});

describe("ConversationList", () => {
  it("renders conversation member id via MemberIdLink", () => {
    render(
      <ConversationList
        conversations={[
          {
            account_id: "acct-1",
            conversation_id: "conv-1",
            customer_id: "user-1",
            customer_public_user_id: "pub-u1",
            customer_language: "zh-CN",
            customer_language_source: "profile",
            status: "open",
            management_mode: "ai_managed",
            ai_enabled: true,
            assigned_agent_id: null,
            assigned_agent_name: null,
            last_message_at: "2026-06-24T00:00:00Z",
            last_message_preview: "hello",
            latest_intent_name: null,
            latest_handover_recommended: false,
            latest_handover_reason: null,
            customer_lifecycle_status: "active",
            is_sleeping: false,
            last_customer_message_at: "2026-06-24T00:00:00Z",
          } as never,
        ]}
        selectedId=""
        onSelect={() => undefined}
        onSearch={() => undefined}
        onFilterAccount={() => undefined}
        accountIds={[]}
        runtimeAccounts={[]}
        loading={false}
        unreadCounts={{}}
      />,
    );

    expect(screen.getByText("member-link:pub-u1:user-1:pub-u1:acct-1")).toBeTruthy();
  });
});
