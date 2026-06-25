import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TasksPage } from "./TasksPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  listTaskTemplatesMock: vi.fn(),
  listTaskInstancesMock: vi.fn(),
  listMetaAccountsMock: vi.fn(),
  createTaskTemplateMock: vi.fn(),
  approveTaskReviewMock: vi.fn(),
  rejectTaskReviewMock: vi.fn(),
  listPlatformUserMemberStatusIndexMock: vi.fn(),
  listSitesMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  listTaskTemplates: hoisted.listTaskTemplatesMock,
  listTaskInstances: hoisted.listTaskInstancesMock,
  listMetaAccounts: hoisted.listMetaAccountsMock,
  createTaskTemplate: hoisted.createTaskTemplateMock,
  approveTaskReview: hoisted.approveTaskReviewMock,
  rejectTaskReview: hoisted.rejectTaskReviewMock,
}));

vi.mock("../services/operations", () => ({
  listPlatformUserMemberStatusIndex: hoisted.listPlatformUserMemberStatusIndexMock,
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
  };
  const Form = Wrapper as typeof Wrapper & { useForm: () => Array<Record<string, unknown>>; Item?: typeof Wrapper };
  Form.useForm = () => [{ resetFields: vi.fn(), submit: vi.fn() }];
  Form.Item = Wrapper;
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
      dataSource.flatMap((record, index) =>
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
    );
  return {
    Button,
    Empty: Wrapper,
    Form,
    Input: Object.assign((props: Record<string, unknown>) => React.createElement("input", props), {
      TextArea: (props: Record<string, unknown>) => React.createElement("textarea", props),
    }),
    InputNumber: (props: Record<string, unknown>) => React.createElement("input", props),
    Modal: Wrapper,
    Select: Wrapper,
    Space: Wrapper,
    Table,
    Tabs: ({ items }: { items?: Array<{ children?: React.ReactNode }> }) =>
      React.createElement("div", null, items?.map((item, index) => React.createElement("div", { key: index }, item.children))),
    Tag,
    Typography,
  };
});

vi.mock("@ant-design/icons", () => ({
  PlusOutlined: () => null,
  ReloadOutlined: () => null,
  SearchOutlined: () => null,
}));

vi.mock("../components/PageShell", async () => {
  const React = await import("react");
  return {
    PageShell: ({ children, stats, actions }: { children?: React.ReactNode; stats?: React.ReactNode; actions?: React.ReactNode }) =>
      React.createElement("div", null, stats, actions, children),
  };
});

vi.mock("../components/Feedback", () => ({
  showError: () => undefined,
  showSuccess: () => undefined,
}));

vi.mock("../utils/withSorter", () => ({
  withSorter: <T,>(columns: T): T => columns,
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

describe("TasksPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      openCustomersPage: vi.fn(),
    };
    hoisted.listSitesMock.mockReset().mockResolvedValue([]);
    hoisted.listMetaAccountsMock.mockReset().mockResolvedValue([]);
    hoisted.listTaskTemplatesMock.mockReset().mockResolvedValue([
      { id: "tpl-1", task_key: "key-1", name: "模板 A", task_type: "daily", status: "active", reward_amount: "10", created_at: "2026-06-24T00:00:00Z" },
    ]);
    hoisted.listTaskInstancesMock.mockReset().mockImplementation(async (params?: { status?: string }) => {
      if (params?.status === "submitted") {
        return [
          { id: "task-review-1", account_id: "acct-1", template_name: "任务审核", user_id: "user-2", public_user_id: "pub-u2", status: "submitted", submitted_at: "2026-06-24T00:00:00Z" },
        ];
      }
      return [
        { id: "task-1", account_id: "acct-1", template_name: "任务 A", user_id: "user-1", public_user_id: "pub-u1", status: "claimed", available_at: "2026-06-24T00:00:00Z", site_key: null },
      ];
    });
    hoisted.listPlatformUserMemberStatusIndexMock.mockReset().mockResolvedValue({});
    hoisted.createTaskTemplateMock.mockReset().mockResolvedValue(undefined);
    hoisted.approveTaskReviewMock.mockReset().mockResolvedValue(undefined);
    hoisted.rejectTaskReviewMock.mockReset().mockResolvedValue(undefined);
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

  it("renders task instance and review user columns with MemberIdLink", async () => {
    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("member-link:pub-u1:user-1:pub-u1:acct-1");
    expect(document.body.textContent).toContain("member-link:pub-u2:user-2:pub-u2:acct-1");
  });
});
