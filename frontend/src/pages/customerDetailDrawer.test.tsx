import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CustomerDetailDrawer } from "./CustomerDetailDrawer";

const hoisted = vi.hoisted(() => ({
  getCustomerSummaryMock: vi.fn(),
  getCustomerTimelineMock: vi.fn(),
  batchUpdateCustomerLifecycleMock: vi.fn(),
  listCustomerConversationsMock: vi.fn(),
  getCustomerProfileMock: vi.fn(),
  usePermissionsMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  getCustomerTimeline: hoisted.getCustomerTimelineMock,
  batchUpdateCustomerLifecycle: hoisted.batchUpdateCustomerLifecycleMock,
  listCustomerConversations: hoisted.listCustomerConversationsMock,
  getCustomerProfile: hoisted.getCustomerProfileMock,
}));

vi.mock("../services/memberApi", () => ({
  getMemberSummary: hoisted.getCustomerSummaryMock,
}));

vi.mock("../components/Feedback", () => ({
  showSuccess: vi.fn(),
  showError: vi.fn(),
}));

vi.mock("../hooks/usePermissions", () => ({
  usePermissions: hoisted.usePermissionsMock,
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
      React.createElement(
        "span",
        null,
        `member-link:${label ?? ""}:${userId ?? ""}:${publicUserId ?? ""}:${accountId ?? ""}`,
      ),
  };
});

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) =>
    React.createElement("div", null, children);
  const Button = ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => React.createElement("button", { onClick }, children);
  const Tag = ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children);
  const Typography = {
    Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
  };
  const Descriptions = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  Descriptions.Item = ({
    label,
    children,
  }: {
    label?: React.ReactNode;
    children?: React.ReactNode;
  }) => React.createElement("div", null, label, children);
  const Drawer = ({
    open,
    title,
    children,
  }: {
    open?: boolean;
    title?: React.ReactNode;
    children?: React.ReactNode;
  }) => (open ? React.createElement("div", null, title, children) : null);
  const Tabs = ({
    items,
  }: {
    items?: Array<{ key: string; label: React.ReactNode; children?: React.ReactNode }>;
  }) =>
    React.createElement(
      "div",
      null,
      items?.map((item) =>
        React.createElement("div", { key: item.key }, item.label, item.children),
      ),
    );
  const List = ({
    dataSource = [],
    renderItem,
  }: {
    dataSource?: Array<unknown>;
    renderItem?: (item: unknown) => React.ReactNode;
  }) => React.createElement("div", null, dataSource.map((item, index) => React.createElement("div", { key: index }, renderItem ? renderItem(item) : null)));
  const Statistic = ({ title, value }: { title?: React.ReactNode; value?: React.ReactNode }) =>
    React.createElement("div", null, title, value);
  return {
    Alert: Wrapper,
    Button,
    Descriptions,
    Divider: Wrapper,
    Drawer,
    Empty: Wrapper,
    List,
    Space: Wrapper,
    Spin: Wrapper,
    Statistic,
    Tag,
    Tabs,
    Typography,
    message: { success: vi.fn(), error: vi.fn() },
  };
});

describe("CustomerDetailDrawer", () => {
  beforeEach(() => {
    hoisted.usePermissionsMock.mockReset().mockReturnValue({
      can: (code: string) => code === "customers.finance",
      canSeePage: () => true,
      perms: null,
      loading: false,
    });
    hoisted.getCustomerSummaryMock.mockReset().mockResolvedValue({
      customer: {
        id: "user-1",
        public_user_id: "pub-u1",
        display_name: "Alice",
        language: "zh-CN",
        created_at: "2026-06-24T00:00:00Z",
        lifecycle_status: "active",
        registration_ip: "127.0.0.1",
        registration_ips: ["127.0.0.1"],
        multi_ip: false,
      },
      wallet: {
        balance: 100,
        total_recharged: 80,
        total_withdrawn: 20,
        recent_transactions: [],
      },
      member_status: {
        verification: { status: "approved" },
        whatsapp_binding: { status: "bound" },
      },
      member_profile: null,
      conversations: { total: 0, open: 0, items: [] },
      tickets: { total: 0, open: 0, items: [] },
      tags: [],
    });
    hoisted.getCustomerTimelineMock.mockReset().mockResolvedValue({ events: [] });
    hoisted.batchUpdateCustomerLifecycleMock.mockReset().mockResolvedValue(undefined);
    hoisted.listCustomerConversationsMock.mockReset().mockResolvedValue([]);
    hoisted.getCustomerProfileMock.mockReset().mockResolvedValue(null);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders member link in title and overview user id block", async () => {
    render(
      <CustomerDetailDrawer
        open
        customerId="user-1"
        accountId="acct-1"
        onClose={() => undefined}
        onViewConversations={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-1", "acct-1");
    });

    expect(screen.getAllByText("member-link:pub-u1:user-1:pub-u1:acct-1")).toHaveLength(2);
    expect(screen.getAllByText("Alice").length).toBeGreaterThan(0);
  });

  it("masks finance metrics without customers.finance permission", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: () => false,
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(
      <CustomerDetailDrawer
        open
        customerId="user-1"
        accountId="acct-1"
        onClose={() => undefined}
        onViewConversations={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-1", "acct-1");
    });

    expect(screen.queryByText("100")).toBeNull();
    expect(screen.queryByText("80")).toBeNull();
    expect(screen.queryByText("20")).toBeNull();
  });
});
