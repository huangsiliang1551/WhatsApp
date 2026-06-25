import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationHeader, getConversationTitleLabel } from "./ConversationHeader";

const hoisted = vi.hoisted(() => ({
  getCustomerSummaryMock: vi.fn(),
  getConversationTagsMock: vi.fn(),
  updateConversationTagsMock: vi.fn(),
  getConversationSentimentMock: vi.fn(),
  getConversationSlaMock: vi.fn(),
  listCustomerConversationsMock: vi.fn(),
  listConversationTimelineMock: vi.fn(),
  useConversationNotesMock: vi.fn(),
}));

vi.mock("../../services/api", () => ({
  getConversationTags: hoisted.getConversationTagsMock,
  updateConversationTags: hoisted.updateConversationTagsMock,
  getConversationSentiment: hoisted.getConversationSentimentMock,
  getConversationSla: hoisted.getConversationSlaMock,
  listCustomerConversations: hoisted.listCustomerConversationsMock,
  listConversationTimeline: hoisted.listConversationTimelineMock,
}));

vi.mock("../../services/memberApi", () => ({
  getMemberSummary: hoisted.getCustomerSummaryMock,
}));

vi.mock("./hooks/useConversationNotes", () => ({
  useConversationNotes: () => hoisted.useConversationNotesMock(),
}));

vi.mock("../../stores/appStore", () => ({
  useAppStore: { getState: () => ({ openWorkspacePage: vi.fn() }) },
}));

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
      React.createElement(
        "span",
        null,
        `member-link:${label ?? ""}:${userId ?? ""}:${publicUserId ?? ""}:${accountId ?? ""}`,
      ),
  };
});

describe("ConversationHeader", () => {
  beforeEach(() => {
    hoisted.getCustomerSummaryMock.mockReset().mockResolvedValue({
      customer: { multi_ip: false, registration_ips: [] },
      wallet: { balance: 0, total_recharged: 0, total_withdrawn: 0 },
      tickets: { total: 0 },
    });
    hoisted.getConversationTagsMock.mockReset().mockResolvedValue({ tags: [] });
    hoisted.updateConversationTagsMock.mockReset().mockResolvedValue(undefined);
    hoisted.getConversationSentimentMock.mockReset().mockRejectedValue(new Error("skip"));
    hoisted.getConversationSlaMock.mockReset().mockRejectedValue(new Error("skip"));
    hoisted.listCustomerConversationsMock.mockReset().mockResolvedValue([]);
    hoisted.listConversationTimelineMock.mockReset().mockResolvedValue([]);
    hoisted.useConversationNotesMock.mockReset().mockReturnValue({
      notes: [],
      error: null,
      loading: false,
      addNote: vi.fn(),
      updateNote: vi.fn(),
      removeNote: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("prefers display name, then public user id, then customer id for title label", () => {
    expect(
      getConversationTitleLabel({
        customerId: "user-1",
        displayName: "Alice",
        publicUserId: "pub-u1",
      }),
    ).toBe("Alice");
    expect(
      getConversationTitleLabel({
        customerId: "user-1",
        displayName: null,
        publicUserId: "pub-u1",
      }),
    ).toBe("pub-u1");
    expect(
      getConversationTitleLabel({
        customerId: "user-1",
        displayName: null,
        publicUserId: null,
      }),
    ).toBe("user-1");
  });

  it("renders public user id via MemberIdLink", async () => {
    render(
      <ConversationHeader
        conversation={{
          account_id: "acct-1",
          conversation_id: "conv-1",
          customer_id: "user-1",
          customer_language: "zh-CN",
          management_mode: "ai_managed",
          latest_handover_recommended: false,
          latest_handover_reason: null,
          assigned_agent_id: null,
          status: "open",
        } as never}
        customerProfile={{
          id: "user-1",
          account_id: "acct-1",
          public_user_id: "pub-u1",
          display_name: "Alice",
          language_code: "zh-CN",
          lifecycle_status: "active",
          last_active_at: null,
        } as never}
        memberStatus={null}
        latestVerification={null}
        latestBinding={null}
        agents={[]}
        agentOptions={[]}
        pendingAction={null}
        conversationStatus="open"
        collapsed={false}
        onToggleCollapse={() => undefined}
        onHandover={() => undefined}
        onRestoreAI={() => undefined}
        onClose={() => undefined}
        onReopen={() => undefined}
        onBlock={() => undefined}
        onUnblock={() => undefined}
        onAssignAgent={() => undefined}
        onOpenFinance={() => undefined}
        onOpenVisitTrail={() => undefined}
        onOpenCustomerProfile={() => undefined}
        onDismissAlert={() => undefined}
      />,
    );

    expect(await screen.findByText("member-link:pub-u1:user-1:pub-u1:acct-1")).toBeTruthy();
  });
});
