import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CustomersPage, getCustomerSummaryMemberLinkProps } from "./CustomersPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  listMetaAccountsMock: vi.fn(),
  listPlatformUsersPaginatedMock: vi.fn(),
  batchUpdateCustomerLifecycleMock: vi.fn(),
  listPlatformUserMemberStatusIndexMock: vi.fn(),
  getCustomerMemberStatusSnapshotMock: vi.fn(),
  customerDetailDrawerMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  listMetaAccounts: hoisted.listMetaAccountsMock,
  listPlatformUsersPaginated: hoisted.listPlatformUsersPaginatedMock,
  batchUpdateCustomerLifecycle: hoisted.batchUpdateCustomerLifecycleMock,
}));

vi.mock("../services/operations", () => ({
  listPlatformUserMemberStatusIndex: hoisted.listPlatformUserMemberStatusIndexMock,
  getCustomerMemberStatusSnapshot: hoisted.getCustomerMemberStatusSnapshotMock,
}));

vi.mock("../hooks/usePermissions", () => ({
  usePermissions: () => ({ can: () => true }),
}));

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (state: Record<string, unknown>) => unknown) => selector(hoisted.storeState),
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
  it("passes the requested detail tab into the customer detail drawer prefill flow", async () => {
    hoisted.storeState = {
      customersPagePrefill: {
        nonce: 1,
        account_id: "acct-1",
        query: "pub-u1",
        selected_profile_id: "user-1",
        detail_tab: "finance",
      },
      clearCustomersPagePrefill: vi.fn(),
      openWorkspacePage: vi.fn(),
    };

    await renderPage(createElement(CustomersPage));

    expect(hoisted.customerDetailDrawerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        open: true,
        customerId: "user-1",
        accountId: "acct-1",
        initialTab: "finance",
      }),
    );
  });
});

vi.mock("./CustomerDetailDrawer", () => ({
  CustomerDetailDrawer: (props: Record<string, unknown>) => {
    hoisted.customerDetailDrawerMock(props);
    return null;
  },
}));

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Button = ({
    children,
    onClick,
    loading,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    loading?: boolean;
  }) => React.createElement("button", { onClick, disabled: loading }, children);
  const Tag = ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children);
  const Typography = {
    Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
  };
  const Table = ({
    dataSource,
    columns,
  }: {
    dataSource?: Array<Record<string, unknown>>;
    columns?: Array<Record<string, unknown>>;
  }) =>
    React.createElement(
      "div",
      null,
      (dataSource ?? []).flatMap((record, rowIndex) =>
        (columns ?? []).map((column, columnIndex) => {
          const dataIndex = typeof column.dataIndex === "string" ? column.dataIndex : undefined;
          const value = dataIndex ? record[dataIndex] : undefined;
          const rendered = typeof column.render === "function" ? column.render(value, record, rowIndex) : value;
          return React.createElement("div", { key: `${rowIndex}-${columnIndex}` }, rendered ?? null);
        }),
      ),
    );
  const Input = ({ ...props }: Record<string, unknown>) => React.createElement("input", props);
  const Select = Wrapper;
  const Space = Wrapper;
  const Popconfirm = Wrapper;
  return { Button, Input, Popconfirm, Select, Space, Table, Tag, Typography };
});

vi.mock("../components/PageShell", async () => {
  const React = await import("react");
  return {
    PageShell: ({
      children,
      stats,
      actions,
    }: {
      children?: React.ReactNode;
      stats?: React.ReactNode;
      actions?: React.ReactNode;
    }) => React.createElement("div", null, stats, actions, children),
    EmptyGuide: ({ title, description }: { title?: string; description?: string }) =>
      React.createElement("div", null, title, description),
  };
});

vi.mock("../components/Feedback", () => ({
  showSuccess: vi.fn(),
  showError: vi.fn(),
}));

const mountedContainers: HTMLDivElement[] = [];
const mountedRoots: Root[] = [];

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderPage(element: ReturnType<typeof createElement>): Promise<void> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  mountedContainers.push(container);
  const root = createRoot(container);
  mountedRoots.push(root);
  await act(async () => {
    root.render(element);
  });
  await flushEffects();
}

describe("CustomersPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      customersPagePrefill: null,
      clearCustomersPagePrefill: vi.fn(),
      openWorkspacePage: vi.fn(),
    };
    hoisted.listMetaAccountsMock.mockReset().mockResolvedValue([]);
    hoisted.listPlatformUsersPaginatedMock.mockReset().mockResolvedValue({
      items: [
        {
          id: "user-1",
          public_user_id: "pub-u1",
          display_name: "Alice",
          lifecycle_status: "active",
          account_id: "acct-1",
          has_whatsapp: true,
          is_new_user: false,
        },
        {
          id: "user-2",
          public_user_id: "pub-u2",
          display_name: null,
          lifecycle_status: "new",
          account_id: null,
          has_whatsapp: false,
          is_new_user: true,
        },
      ],
      total: 2,
      page: 1,
      size: 20,
    });
    hoisted.batchUpdateCustomerLifecycleMock.mockReset().mockResolvedValue({});
    hoisted.listPlatformUserMemberStatusIndexMock.mockReset().mockResolvedValue({});
    hoisted.getCustomerMemberStatusSnapshotMock.mockReset().mockResolvedValue({
      verificationRequests: [],
      bindingRequests: [],
    });
    hoisted.customerDetailDrawerMock.mockReset();
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  afterEach(async () => {
    while (mountedRoots.length > 0) {
      const root = mountedRoots.pop();
      await act(async () => root?.unmount());
    }
    while (mountedContainers.length > 0) {
      mountedContainers.pop()?.remove();
    }
    vi.restoreAllMocks();
    delete (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT;
  });

  it("loads paginated customers on mount", async () => {
    await renderPage(createElement(CustomersPage));
    expect(hoisted.listPlatformUsersPaginatedMock).toHaveBeenCalled();
  });

  it("renders the user id column with MemberIdLink", async () => {
    await renderPage(createElement(CustomersPage));
    expect(document.body.textContent).toContain("member-link:pub-u1:user-1:pub-u1:acct-1");
    expect(document.body.textContent).toContain("member-link:pub-u2:user-2:pub-u2:");
  });

  it("builds selected customer summary member link props", async () => {
    expect(
      getCustomerSummaryMemberLinkProps({
        id: "user-1",
        account_id: "acct-1",
        public_user_id: "pub-u1",
      } as never),
    ).toEqual({
      accountId: "acct-1",
      userId: "user-1",
      publicUserId: "pub-u1",
      label: "pub-u1",
    });
  });

  it("shows expanded search placeholder for id, name, ip, and whatsapp", async () => {
    await renderPage(createElement(CustomersPage));
    const input = document.querySelector("input");
    expect(input?.getAttribute("placeholder")).toBe("搜索 ID / 名称 / IP / WhatsApp");
  });
});
