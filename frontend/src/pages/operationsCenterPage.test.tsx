import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OperationsCenterPage } from "./OperationsCenterPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  getOperationsCenterSnapshotMock: vi.fn(),
  listPlatformUserMemberStatusIndexMock: vi.fn(),
}));

vi.mock("../services/operations", () => ({
  getOperationsCenterSnapshot: hoisted.getOperationsCenterSnapshotMock,
  listPlatformUserMemberStatusIndex: hoisted.listPlatformUserMemberStatusIndexMock,
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
  };
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
    Card: Wrapper,
    Col: Wrapper,
    Row: Wrapper,
    Space: Wrapper,
    Statistic: ({ title, value }: { title?: React.ReactNode; value?: React.ReactNode }) => React.createElement("div", null, title, value),
    Table,
    Tag,
    Typography,
  };
});

vi.mock("../components/PageShell", async () => {
  const React = await import("react");
  return {
    PageShell: ({ children, actions }: { children?: React.ReactNode; actions?: React.ReactNode }) =>
      React.createElement("div", null, actions, children),
    EmptyGuide: ({ title, description }: { title?: string; description?: string }) =>
      React.createElement("div", null, title, description),
  };
});

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

describe("OperationsCenterPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      openCustomersPage: vi.fn(),
    };
    hoisted.getOperationsCenterSnapshotMock.mockReset().mockResolvedValue({
      account_id: null,
      queued_jobs: 1,
      processing_jobs: 2,
      failed_jobs: 0,
      provider_pending: 0,
      tasks: [
        { id: "task-1", account_id: "acct-1", template_name: "任务 A", user_id: "user-1", public_user_id: "pub-u1", status: "claimed", available_at: "2026-06-24T00:00:00Z" },
      ],
      provider_backlog: [],
      audit_items: [],
    });
    hoisted.listPlatformUserMemberStatusIndexMock.mockReset().mockResolvedValue({});
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

  it("renders the task user column with MemberIdLink", async () => {
    await renderPage(createElement(OperationsCenterPage));
    expect(document.body.textContent).toContain("member-link:pub-u1:user-1:pub-u1:acct-1");
  });
});
