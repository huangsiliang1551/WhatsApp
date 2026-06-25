import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewsPage } from "./ReviewsPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  listTaskInstancesMock: vi.fn(),
  updateReviewStatusMock: vi.fn(),
  listPlatformMemberVerificationsMock: vi.fn(),
  listPlatformMemberWhatsAppBindingsMock: vi.fn(),
  updatePlatformMemberVerificationStatusMock: vi.fn(),
  updatePlatformMemberWhatsAppBindingStatusMock: vi.fn(),
  listSitesMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  listTaskInstances: hoisted.listTaskInstancesMock,
  updateReviewStatus: hoisted.updateReviewStatusMock,
}));

vi.mock("../services/h5", () => ({
  listPlatformMemberVerifications: hoisted.listPlatformMemberVerificationsMock,
  listPlatformMemberWhatsAppBindings: hoisted.listPlatformMemberWhatsAppBindingsMock,
  updatePlatformMemberVerificationStatus: hoisted.updatePlatformMemberVerificationStatusMock,
  updatePlatformMemberWhatsAppBindingStatus: hoisted.updatePlatformMemberWhatsAppBindingStatusMock,
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
  const Space = Wrapper;
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
  return { Button, Space, Table, Tag, Typography, message: { success: vi.fn(), error: vi.fn() } };
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

describe("ReviewsPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      openUsersPage: vi.fn(),
      openCustomersPage: vi.fn(),
    };
    hoisted.listTaskInstancesMock.mockReset().mockResolvedValue([
      {
        id: "task-1",
        account_id: "acct-1",
        template_name: "任务 A",
        user_id: "user-1",
        public_user_id: "pub-u1",
        site_key: "site-a",
        status: "submitted",
        submitted_at: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.updateReviewStatusMock.mockReset().mockResolvedValue(undefined);
    hoisted.listPlatformMemberVerificationsMock.mockReset().mockResolvedValue([
      {
        id: "verify-1",
        accountId: "acct-1",
        userId: "user-2",
        publicUserId: "pub-u2",
        memberNo: "M001",
        status: "pending",
      },
    ]);
    hoisted.listPlatformMemberWhatsAppBindingsMock.mockReset().mockResolvedValue([
      {
        id: "bind-1",
        accountId: "acct-1",
        userId: "user-3",
        publicUserId: "pub-u3",
        memberNo: "M002",
        requestedPhoneNumber: "123",
        status: "pending",
      },
    ]);
    hoisted.updatePlatformMemberVerificationStatusMock.mockReset().mockResolvedValue(undefined);
    hoisted.updatePlatformMemberWhatsAppBindingStatusMock.mockReset().mockResolvedValue(undefined);
    hoisted.listSitesMock.mockReset().mockResolvedValue([]);
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

  it("renders review-related user columns with MemberIdLink", async () => {
    await renderPage(createElement(ReviewsPage));
    expect(document.body.textContent).toContain("member-link:pub-u1:user-1:pub-u1:acct-1");
    expect(document.body.textContent).toContain("member-link:pub-u2:user-2:pub-u2:acct-1");
    expect(document.body.textContent).toContain("member-link:pub-u3:user-3:pub-u3:acct-1");
  });
});
