import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CustomerTab } from "./CustomerTab";

const hoisted = vi.hoisted(() => ({
  listMessagesMock: vi.fn(),
  useMemberStatusMock: vi.fn(),
}));

vi.mock("../../services/api", () => ({
  listMessages: hoisted.listMessagesMock,
}));

vi.mock("../../hooks/useMemberStatus", () => ({
  useMemberStatus: () => hoisted.useMemberStatusMock(),
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

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Descriptions = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  Descriptions.Item = ({
    label,
    children,
  }: {
    label?: React.ReactNode;
    children?: React.ReactNode;
  }) => React.createElement("div", null, label, children);
  const Collapse = ({
    items,
  }: {
    items?: Array<{ key: string; label: React.ReactNode; children?: React.ReactNode }>;
  }) => React.createElement("div", null, items?.map((item) => React.createElement("div", { key: item.key }, item.label, item.children)));
  return {
    Alert: Wrapper,
    Button: Wrapper,
    Collapse,
    Descriptions,
    Tag: Wrapper,
    Typography: { Text: Wrapper },
    Spin: Wrapper,
  };
});

describe("CustomerTab", () => {
  beforeEach(() => {
    hoisted.listMessagesMock.mockReset().mockResolvedValue([]);
    hoisted.useMemberStatusMock.mockReset().mockReturnValue({
      memberStatus: null,
      memberStatusLoading: false,
      memberStatusError: null,
      latestVerification: null,
      latestBinding: null,
      verificationCount: 0,
      bindingCount: 0,
      loadMemberStatus: vi.fn(),
      resetMemberStatus: vi.fn(),
    });
  });

  it("renders user id via MemberIdLink", () => {
    render(
      <CustomerTab
        conversation={{
          account_id: "acct-1",
          conversation_id: "conv-1",
        } as never}
        customerProfile={{
          id: "user-1",
          public_user_id: "pub-u1",
          display_name: "Alice",
          language_code: "zh-CN",
          last_active_at: "2026-06-24T00:00:00Z",
          registration_ip: "127.0.0.1",
          lifecycle_status: "active",
        } as never}
        onOpenCustomerPage={() => undefined}
      />,
    );

    expect(screen.getByText("member-link:pub-u1:user-1:pub-u1:acct-1")).toBeTruthy();
  });
});
