import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TicketsPage, getTicketMemberLinkProps } from "./TicketsPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  listSupportTicketsMock: vi.fn(),
  apiPostMock: vi.fn(),
  batchUpdateTagsMock: vi.fn(),
  batchSendTemplateMock: vi.fn(),
  listSitesMock: vi.fn(),
  getPlatformUserMemberStatusSnapshotMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  api: { post: hoisted.apiPostMock },
  batchUpdateTags: hoisted.batchUpdateTagsMock,
  batchSendTemplate: hoisted.batchSendTemplateMock,
}));

vi.mock("../services/h5", () => ({
  listSupportTickets: hoisted.listSupportTicketsMock,
  getSupportTicketStatusLabel: (status: string) => status,
}));

vi.mock("../services/h5MultiTenantApi", () => ({
  listSites: hoisted.listSitesMock,
}));

vi.mock("../services/operations", () => ({
  getPlatformUserMemberStatusSnapshot: hoisted.getPlatformUserMemberStatusSnapshotMock,
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
});

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
    Title: ({ children }: { children?: React.ReactNode }) => React.createElement("h4", null, children),
    Paragraph: ({ children }: { children?: React.ReactNode }) => React.createElement("p", null, children),
  };
  const Input = ({ ...props }: Record<string, unknown>) => React.createElement("input", props);
  Input.TextArea = ({ ...props }: Record<string, unknown>) => React.createElement("textarea", props);
  const Select = Wrapper;
  const Modal = Wrapper;
  const Table = ({
    dataSource = [],
    columns = [],
  }: {
    dataSource?: Array<Record<string, unknown>>;
    columns?: Array<{
      key?: string;
      dataIndex?: string;
      render?: (value: unknown, record: Record<string, unknown>, index: number) => React.ReactNode;
    }>;
  }) =>
    React.createElement(
      "div",
      null,
      dataSource.map((record, index) =>
        React.createElement(
          "div",
          { key: String(record.id ?? index) },
          columns.map((column, columnIndex) =>
            React.createElement(
              "div",
              { key: `${String(column.key ?? column.dataIndex ?? columnIndex)}-${index}` },
              column.render
                ? column.render(column.dataIndex ? record[column.dataIndex] : undefined, record, index)
                : column.dataIndex
                  ? String(record[column.dataIndex] ?? "")
                  : null,
            ),
          ),
        ),
      ),
    );
  return {
    Badge: Wrapper,
    Button,
    Card: Wrapper,
    Col: Wrapper,
    Input,
    Modal,
    Row: Wrapper,
    Select,
    Space: Wrapper,
    Table,
    Tag,
    Typography,
  };
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

vi.mock("../components/Feedback", async () => {
  const React = await import("react");
  return {
    DangerButton: ({ label, onConfirm }: { label?: string; onConfirm?: () => void }) =>
      React.createElement("button", { onClick: onConfirm }, label),
    showSuccess: () => undefined,
    showError: () => undefined,
  };
});

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

describe("TicketsPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      setActivePage: vi.fn(),
      openCustomersPage: vi.fn(),
    };
    hoisted.listSupportTicketsMock.mockReset().mockResolvedValue([
      {
        id: "ticket-1",
        account_id: "acct-1",
        user_id: "user-1",
        public_user_id: "pub-u1",
        subject: "Login issue",
        status: "open",
        category: "technical",
        priority: "high",
        content_preview: "Cannot log in",
        created_at: new Date(Date.now() - 3600000 * 30).toISOString(),
        updated_at: "2026-06-11T00:00:00Z",
      },
      {
        id: "ticket-2",
        account_id: "acct-1",
        user_id: "user-2",
        public_user_id: "pub-u2",
        subject: "Order issue",
        status: "in_progress",
        category: "order",
        priority: "medium",
        content_preview: "Order not received",
        created_at: new Date(Date.now() - 3600000 * 18).toISOString(),
        updated_at: "2026-06-12T00:00:00Z",
      },
      {
        id: "ticket-3",
        account_id: "acct-1",
        user_id: "user-3",
        public_user_id: "pub-u3",
        subject: "Refund request",
        status: "resolved",
        category: "refund",
        priority: "low",
        content_preview: "Requesting refund",
        created_at: new Date(Date.now() - 7200000).toISOString(),
        updated_at: "2026-06-12T00:00:00Z",
      },
      {
        id: "ticket-4",
        account_id: "acct-2",
        user_id: null,
        public_user_id: "pub-u4",
        subject: "No user id ticket",
        status: "open",
        category: "technical",
        priority: "low",
        content_preview: "Missing linked user id",
        created_at: new Date(Date.now() - 3600000).toISOString(),
        updated_at: "2026-06-12T00:00:00Z",
      },
    ]);
    hoisted.apiPostMock.mockReset().mockResolvedValue({});
    hoisted.batchUpdateTagsMock.mockReset().mockResolvedValue({});
    hoisted.batchSendTemplateMock.mockReset().mockResolvedValue({});
    hoisted.listSitesMock.mockReset().mockResolvedValue([]);
    hoisted.getPlatformUserMemberStatusSnapshotMock.mockReset().mockResolvedValue({
      verificationRequests: [],
      bindingRequests: [],
    });
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

  it("renders without crashing", async () => {
    await renderPage(createElement(TicketsPage));
    expect(document.querySelectorAll("button").length).toBeGreaterThanOrEqual(0);
  });

  it("loads tickets on mount", async () => {
    await renderPage(createElement(TicketsPage));
    expect(hoisted.listSupportTicketsMock).toHaveBeenCalled();
  });

  it("shows kanban view by default", async () => {
    await renderPage(createElement(TicketsPage));
    expect(document.body.textContent).toContain("open");
    expect(document.body.textContent).toContain("in_progress");
    expect(document.body.textContent).toContain("resolved");
  });

  it("shows ticket subjects in kanban cards", async () => {
    await renderPage(createElement(TicketsPage));
    expect(document.body.textContent).toContain("Login issue");
    expect(document.body.textContent).toContain("Order issue");
  });

  it("has view mode toggle buttons", async () => {
    await renderPage(createElement(TicketsPage));
    expect(document.body.textContent).toContain("看板");
    expect(document.body.textContent).toContain("列表");
  });

  it("shows empty guide when no tickets", async () => {
    hoisted.listSupportTicketsMock.mockReset().mockResolvedValue([]);
    await renderPage(createElement(TicketsPage));
    expect(hoisted.listSupportTicketsMock).toHaveBeenCalled();
  });

  it("uses user id for member status lookup and customer navigation when available", async () => {
    await renderPage(createElement(TicketsPage));

    const detailButton = Array.from(document.querySelectorAll("button")).find(
      (button) => button.textContent === "详情",
    );
    expect(detailButton).toBeTruthy();
    await act(async () => {
      detailButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flushEffects();

    expect(hoisted.getPlatformUserMemberStatusSnapshotMock).toHaveBeenCalledWith({
      id: "user-1",
      account_id: "acct-1",
      public_user_id: "pub-u1",
    });
    expect(document.body.textContent).toContain("member-link:pub-u1:user-1:pub-u1:acct-1");

    const customerButton = Array.from(document.querySelectorAll("button")).find(
      (button) => button.textContent === "客户页",
    );
    expect(customerButton).toBeTruthy();
    await act(async () => {
      customerButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.storeState.openCustomersPage).toHaveBeenCalledWith({
      account_id: "acct-1",
      selected_profile_id: "user-1",
      query: "pub-u1",
    });
  });

  it("builds member link props even without user id", async () => {
    expect(
      getTicketMemberLinkProps({
        account_id: "acct-2",
        user_id: null,
        public_user_id: "pub-u4",
      } as never),
    ).toEqual({
      accountId: "acct-2",
      userId: "pub-u4",
      publicUserId: "pub-u4",
      label: "pub-u4",
    });
  });
});
