import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UsersPage } from "./UsersPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  listPlatformUsersMock: vi.fn(),
  apiPostMock: vi.fn(),
  updatePlatformUserMock: vi.fn(),
  deletePlatformUserMock: vi.fn(),
  listSitesMock: vi.fn(),
  listPlatformUserMemberStatusIndexMock: vi.fn(),
  getPlatformUserMemberStatusSnapshotMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  listPlatformUsers: hoisted.listPlatformUsersMock,
  api: { post: hoisted.apiPostMock },
  updatePlatformUser: hoisted.updatePlatformUserMock,
  deletePlatformUser: hoisted.deletePlatformUserMock,
}));

vi.mock("../services/operations", () => ({
  listPlatformUserMemberStatusIndex: hoisted.listPlatformUserMemberStatusIndexMock,
  getPlatformUserMemberStatusSnapshot: hoisted.getPlatformUserMemberStatusSnapshotMock,
}));

vi.mock("../services/h5MultiTenantApi", () => ({
  listSites: hoisted.listSitesMock,
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
    }) => React.createElement(
      "span",
      null,
      `member-link:${label ?? ""}:${userId ?? ""}:${publicUserId ?? ""}:${accountId ?? ""}`,
    ),
  };
});

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Button = ({ children, onClick, loading }: { children?: React.ReactNode; onClick?: () => void; loading?: boolean }) =>
    React.createElement("button", { onClick, disabled: loading }, children);
  const Tag = ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children);
  const Typography = {
    Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
    Title: ({ children }: { children?: React.ReactNode }) => React.createElement("h4", null, children),
    Paragraph: ({ children }: { children?: React.ReactNode }) => React.createElement("p", null, children),
  };
  const Table = ({
    dataSource,
    columns,
  }: {
    dataSource?: Array<Record<string, unknown>>;
    columns?: Array<Record<string, unknown>>;
  }) => React.createElement(
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
  const Space = Wrapper;
  const Input = ({ ...props }: Record<string, unknown>) => React.createElement("input", props);
  const Select = Wrapper;
  const Modal = Wrapper;
  const Form = Wrapper as typeof Wrapper & { useForm: () => Array<Record<string, unknown>>; Item?: typeof Wrapper };
  Form.useForm = () => [{ resetFields: vi.fn(), setFieldsValue: vi.fn(), submit: vi.fn() }];
  Form.Item = Wrapper;
  return { Button, Form, Input, Modal, Select, Space, Table, Tag, Typography };
});

vi.mock("../components/PageShell", async () => {
  const React = await import("react");
  return {
    PageShell: ({ children, stats, actions }: { children?: React.ReactNode; stats?: React.ReactNode; actions?: React.ReactNode }) =>
      React.createElement("div", null, stats, actions, children),
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

describe("UsersPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      setActivePage: vi.fn(),
      openCustomersPage: vi.fn(),
    };
    hoisted.listPlatformUsersMock.mockReset().mockResolvedValue([
      { id: "user-1", public_user_id: "pub-u1", display_name: "张三", lifecycle_status: "active", account_id: "acct-1", language_code: "zh", has_whatsapp: true, has_email: true, has_phone: false, is_anonymous: false, is_new_user: false, created_at: "2026-01-01T00:00:00Z" },
      { id: "user-2", public_user_id: "pub-u2", display_name: null, lifecycle_status: "new", account_id: null, language_code: "en", has_whatsapp: false, has_email: false, has_phone: true, is_anonymous: true, is_new_user: true, created_at: "2026-06-10T00:00:00Z" },
      { id: "user-3", public_user_id: "pub-u3", display_name: "李四", lifecycle_status: "dormant", account_id: "acct-1", language_code: "zh", has_whatsapp: true, has_email: true, has_phone: true, is_anonymous: false, is_new_user: false, created_at: "2026-03-15T00:00:00Z" },
    ]);
    hoisted.apiPostMock.mockReset().mockResolvedValue({});
    hoisted.updatePlatformUserMock.mockReset().mockResolvedValue({});
    hoisted.deletePlatformUserMock.mockReset().mockResolvedValue({});
    hoisted.listSitesMock.mockReset().mockResolvedValue([]);
    hoisted.listPlatformUserMemberStatusIndexMock.mockReset().mockResolvedValue({});
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
    await renderPage(createElement(UsersPage));
    expect(document.querySelectorAll("button").length).toBeGreaterThanOrEqual(0);
  });

  it("loads users on mount", async () => {
    await renderPage(createElement(UsersPage));
    expect(hoisted.listPlatformUsersMock).toHaveBeenCalled();
  });

  it("displays user count in stats", async () => {
    await renderPage(createElement(UsersPage));
    expect(document.body.textContent).toContain("3");
  });

  it("shows user lifecycle statuses in stats", async () => {
    await renderPage(createElement(UsersPage));
    expect(document.body.textContent).toContain("活跃");
    expect(document.body.textContent).toContain("新用户");
  });

  it("has a refresh button", async () => {
    await renderPage(createElement(UsersPage));
    expect(document.body.textContent).toContain("刷新");
  });

  it("renders the user id column with MemberIdLink", async () => {
    await renderPage(createElement(UsersPage));
    expect(document.body.textContent).toContain("member-link:pub-u1:user-1:pub-u1:acct-1");
    expect(document.body.textContent).toContain("member-link:pub-u2:user-2:pub-u2:");
  });

  it("renders selected user detail with MemberIdLink", async () => {
    await renderPage(createElement(UsersPage));

    const before = (document.body.textContent?.match(/member-link:pub-u2:user-2:pub-u2:/g) ?? []).length;
    const userButton = Array.from(document.querySelectorAll("button")).find(
      (button) => button.textContent === "pub-u2",
    );
    expect(userButton).toBeTruthy();

    await act(async () => {
      userButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await flushEffects();

    const after = (document.body.textContent?.match(/member-link:pub-u2:user-2:pub-u2:/g) ?? []).length;
    expect(after).toBe(before + 1);
  });
});
