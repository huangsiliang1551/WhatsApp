import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CustomerDetailDrawer } from "./CustomerDetailDrawer";

const hoisted = vi.hoisted(() => ({
  getCustomerSummaryMock: vi.fn(),
  getCustomerTimelineMock: vi.fn(),
  batchUpdateCustomerLifecycleMock: vi.fn(),
  listCustomerConversationsMock: vi.fn(),
  listWalletLedgersMock: vi.fn(),
  getCustomerProfileMock: vi.fn(),
  usePermissionsMock: vi.fn(),
  openCustomersPageMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  getCustomerTimeline: hoisted.getCustomerTimelineMock,
  batchUpdateCustomerLifecycle: hoisted.batchUpdateCustomerLifecycleMock,
  listCustomerConversations: hoisted.listCustomerConversationsMock,
  listWalletLedgers: hoisted.listWalletLedgersMock,
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

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      openCustomersPage: hoisted.openCustomersPageMock,
    }),
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
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Alert = ({
    message,
    description,
    children,
  }: {
    message?: React.ReactNode;
    description?: React.ReactNode;
    children?: React.ReactNode;
  }) => React.createElement("div", null, message, description, children);
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
    Title: ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children),
  };
  const Descriptions = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  Descriptions.Item = ({
    label,
    children,
  }: {
    label?: React.ReactNode;
    children?: React.ReactNode;
  }) => React.createElement("div", null, label, children);
  const Modal = ({
    open,
    title,
    children,
  }: {
    open?: boolean;
    title?: React.ReactNode;
    children?: React.ReactNode;
  }) => (open ? React.createElement("div", { "data-testid": "customer-detail-modal" }, title, children) : null);
  Modal.confirm = vi.fn();
  const Tabs = ({
    items,
  }: {
    items?: Array<{ key: string; label: React.ReactNode; children?: React.ReactNode }>;
  }) => React.createElement("div", null, items?.map((item) => React.createElement("div", { key: item.key }, item.label, item.children)));
  type ListComponent = ((props: {
    dataSource?: Array<unknown>;
    renderItem?: (item: unknown) => React.ReactNode;
  }) => React.ReactElement) & {
    Item: ((props: {
      children?: React.ReactNode;
      actions?: React.ReactNode[];
    }) => React.ReactElement) & {
      Meta: (props: {
        title?: React.ReactNode;
        description?: React.ReactNode;
      }) => React.ReactElement;
    };
  };
  const List = (({
    dataSource = [],
    renderItem,
  }: {
    dataSource?: Array<unknown>;
    renderItem?: (item: unknown) => React.ReactNode;
  }) => React.createElement("div", null, dataSource.map((item, index) => React.createElement("div", { key: index }, renderItem ? renderItem(item) : null)))) as unknown as ListComponent;
  const listItem = ({
    children,
    actions,
  }: {
    children?: React.ReactNode;
    actions?: React.ReactNode[];
  }) => React.createElement("div", null, children, actions);
  listItem.Meta = ({
    title,
    description,
  }: {
    title?: React.ReactNode;
    description?: React.ReactNode;
  }) => React.createElement("div", null, title, description);
  List.Item = listItem as ListComponent["Item"];
  const Statistic = ({
    title,
    value,
  }: {
    title?: React.ReactNode;
    value?: React.ReactNode;
  }) => React.createElement(
    "div",
    null,
    React.createElement("span", null, title),
    React.createElement("span", null, value),
  );
  const Pagination = ({ current, total }: { current?: number; total?: number }) => React.createElement("div", null, `pagination:${current ?? 1}:${total ?? 0}`);
  const Table = ({
    dataSource = [],
    columns = [],
  }: {
    dataSource?: Array<Record<string, unknown>>;
    columns?: Array<{ key?: string; dataIndex?: string; render?: (value: unknown, row: Record<string, unknown>) => React.ReactNode }>;
  }) => React.createElement(
    "div",
    null,
    dataSource.map((row, rowIndex) => React.createElement(
      "div",
      { key: rowIndex },
      columns.map((column, columnIndex) => {
        const rawValue = column.dataIndex ? row[column.dataIndex] : undefined;
        return React.createElement(
          "span",
          { key: `${rowIndex}-${column.key ?? columnIndex}` },
          column.render ? column.render(rawValue, row) : (rawValue as React.ReactNode),
        );
      }),
    )),
  );
  const Empty = Object.assign(Wrapper, { PRESENTED_IMAGE_SIMPLE: null });
  return {
    Alert,
    Button,
    Descriptions,
    Empty,
    List,
    Modal,
    Pagination,
    Space: Wrapper,
    Spin: Wrapper,
    Statistic,
    Table,
    Tag,
    Tabs,
    Typography,
    message: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
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
        public_user_id: "very-long-public-user-id-for-wrap-check-000001",
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
        system_balance: 70,
        task_balance: 30,
        total_recharged: 80,
        total_withdrawn: 20,
        recent_transactions: [],
      },
      member_status: {
        verification: { status: "approved" },
        whatsapp_binding: { status: "bound" },
      },
      member_profile: null,
      conversations: { total: 6, open: 4, items: Array.from({ length: 6 }, (_, index) => ({ id: `conv-${index}` })) },
      tickets: {
        total: 6,
        open: 3,
        items: Array.from({ length: 6 }, (_, index) => ({
          title: `工单 ${index + 1}`,
          status: index % 2 === 0 ? "open" : "resolved",
          created_at: "2026-06-24T00:00:00Z",
        })),
      },
      tags: [],
    });
    hoisted.getCustomerTimelineMock.mockReset().mockResolvedValue({
      events: Array.from({ length: 7 }, (_, index) => ({
        type: "message",
        time: `2026-06-2${index}T10:00:00Z`,
        summary: `动态 ${index + 1}`,
      })),
    });
    hoisted.batchUpdateCustomerLifecycleMock.mockReset().mockResolvedValue(undefined);
    hoisted.listCustomerConversationsMock.mockReset().mockResolvedValue(
      Array.from({ length: 6 }, (_, index) => ({
        conversation_id: `conversation-${index + 1}`,
        account_id: "acct-1",
        customer_id: "user-1",
        status: index % 2 === 0 ? "active" : "closed",
        management_mode: index % 2 === 0 ? "ai_managed" : "human_managed",
        last_message_at: "2026-06-24T10:00:00Z",
        last_message_preview: `消息 ${index + 1}`,
      })),
    );
    hoisted.listWalletLedgersMock.mockReset().mockResolvedValue([
      ...Array.from({ length: 9 }, (_, index) => ({
        id: `ledger-${index + 1}`,
        user_id: "user-1",
        public_user_id: "very-long-public-user-id-for-wrap-check-000001",
        ledger_type: "system_credit",
        transaction_type: "credit",
        direction: "in",
        amount: 12.5 + index,
        currency: "CNY",
        status: "success",
        source_type: "admin_bonus",
        cash_amount: 10,
        bonus_amount: 2.5,
        task_amount: 0,
        created_at: "2026-06-24T10:00:00Z",
      })),
    ]);
    hoisted.getCustomerProfileMock.mockReset().mockResolvedValue(null);
    hoisted.openCustomersPageMock.mockReset();
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

    expect(screen.getByTestId("customer-detail-modal")).toBeTruthy();
    expect(screen.getAllByText("member-link:very-long-public-user-id-for-wrap-check-000001:user-1:very-long-public-user-id-for-wrap-check-000001:acct-1")).toHaveLength(2);
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

    expect(screen.queryAllByText("¥100.00")).toHaveLength(0);
    expect(screen.queryAllByText("¥80.00")).toHaveLength(0);
    expect(screen.queryAllByText("¥20.00")).toHaveLength(0);
    expect(screen.getAllByText("需财务权限").length).toBeGreaterThan(0);
  });

  it("removes placeholder business blocks from customer overview", async () => {
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

    expect(screen.queryAllByText("状态摘要")).toHaveLength(0);
    expect(screen.getAllByText("最近动态").length).toBeGreaterThan(0);
    expect(screen.getAllByText("动态 1").length).toBeGreaterThan(0);
  });

  it("shows finance tab in localized balance buckets with paginated ledger rows", async () => {
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
      expect(hoisted.listWalletLedgersMock).toHaveBeenCalledWith({ userId: "user-1" });
    });

    expect(screen.getAllByText("总余额").length).toBeGreaterThan(0);
    expect(screen.getAllByText("系统余额").length).toBeGreaterThan(0);
    expect(screen.getAllByText("任务余额").length).toBeGreaterThan(0);
    expect(screen.getAllByText("流水记录").length).toBeGreaterThan(0);
    expect(screen.getAllByText("pagination:1:9").length).toBeGreaterThan(0);
  });

  it("removes overview account, nickname, and registration time rows while exposing same-ip jump", async () => {
    hoisted.getCustomerSummaryMock.mockResolvedValue({
      customer: {
        id: "user-1",
        public_user_id: "very-long-public-user-id-for-wrap-check-000001",
        display_name: "Alice",
        language: "zh-CN",
        created_at: "2026-06-24T00:00:00Z",
        lifecycle_status: "active",
        registration_ip: "172.18.0.1",
        registration_ips: ["172.18.0.1"],
        registration_location: "中国上海市",
        same_ip_user_count: 5,
        multi_ip: false,
      },
      wallet: {
        balance: 100,
        system_balance: 70,
        task_balance: 30,
        total_recharged: 80,
        total_withdrawn: 20,
        recent_transactions: [],
      },
      member_status: {
        verification: { status: "approved", request_type: "whatsapp" },
        whatsapp_binding: { status: "bound" },
      },
      member_profile: null,
      conversations: { total: 6, open: 4, items: [] },
      tickets: { total: 0, open: 0, items: [] },
      tags: [],
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

    expect(screen.queryAllByText("昵称")).toHaveLength(0);
    expect(document.body.textContent?.includes("账号acct-1")).toBe(true);
    expect(document.body.textContent?.includes("注册时间2026/6/24 08:00:00")).toBe(true);
    const sameIpButton = screen.getByText("同IP 5个用户");
    fireEvent.click(sameIpButton);
    expect(hoisted.openCustomersPageMock).toHaveBeenCalledWith({
      account_id: "acct-1",
      query: "172.18.0.1",
      selected_profile_id: "user-1",
    });
  });
});
