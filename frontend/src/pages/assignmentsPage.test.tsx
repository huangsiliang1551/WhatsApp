import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssignmentsPage } from "./AssignmentsPage";

const hoisted = vi.hoisted(() => ({
  listConversationsMock: vi.fn(),
  listRuntimeAgentsMock: vi.fn(),
  openWorkspacePageMock: vi.fn(),
}));

vi.mock("../services/api", async () => {
  const actual = await vi.importActual("../services/api");
  return {
    ...actual,
    api: { post: vi.fn() },
    listConversations: hoisted.listConversationsMock,
    listRuntimeAgents: hoisted.listRuntimeAgentsMock,
  };
});

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (state: { openWorkspacePage: typeof hoisted.openWorkspacePageMock }) => unknown) =>
    selector({ openWorkspacePage: hoisted.openWorkspacePageMock }),
}));

vi.mock("../components/member/MemberIdLink", async () => {
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

describe("AssignmentsPage", () => {
  beforeEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        media: "",
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    hoisted.listConversationsMock.mockReset().mockResolvedValue([
      {
        account_id: "acct-1",
        conversation_id: "conv-1",
        customer_id: "user-1",
        customer_public_user_id: "pub-u1",
        customer_language: "zh-CN",
        management_mode: "ai_managed",
        latest_handover_recommended: true,
        latest_handover_reason: null,
        last_message_preview: "hello",
        last_message_at: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.listRuntimeAgentsMock.mockReset().mockResolvedValue([]);
    hoisted.openWorkspacePageMock.mockReset();
  });

  it("renders queue member id via MemberIdLink", async () => {
    render(<AssignmentsPage />);

    await waitFor(() => {
      expect(hoisted.listConversationsMock).toHaveBeenCalled();
    });

    expect(screen.getByText("member-link:pub-u1:user-1:pub-u1:acct-1")).toBeTruthy();
  });
});
