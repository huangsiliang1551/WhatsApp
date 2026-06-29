import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CustomerProfileDrawer } from "./CustomerProfileDrawer";

const hoisted = vi.hoisted(() => ({
  getCustomerSummaryMock: vi.fn(),
  usePermissionsMock: vi.fn(),
}));

vi.mock("../../services/memberApi", () => ({
  getMemberSummary: hoisted.getCustomerSummaryMock,
}));

vi.mock("../../hooks/usePermissions", () => ({
  usePermissions: hoisted.usePermissionsMock,
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
  const Modal = ({
    open,
    children,
    title,
  }: {
    open?: boolean;
    children?: React.ReactNode;
    title?: React.ReactNode;
  }) => (open ? React.createElement("div", { "data-testid": "customer-profile-modal" }, title, children) : null);
  Modal.confirm = vi.fn();
  return {
    Button: Wrapper,
    Descriptions,
    Modal,
    Spin: Wrapper,
    Tag: Wrapper,
    Typography: { Text: Wrapper, Title: Wrapper },
  };
});

describe("CustomerProfileDrawer", () => {
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
      conversations: { total: 0, open: 0, items: [] },
      tickets: { total: 0, open: 0, items: [] },
      tags: [],
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders user id via MemberIdLink", async () => {
    render(
      <CustomerProfileDrawer
        open
        customerId="user-1"
        accountId="acct-1"
        onClose={() => undefined}
        onOpenCustomerPage={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-1", "acct-1");
    });

    expect(screen.getByTestId("customer-profile-modal")).toBeTruthy();
    expect(screen.getByText("客户资料")).toBeTruthy();
    expect(screen.getByText("member-link:pub-u1:user-1:pub-u1:acct-1")).toBeTruthy();
  });

  it("hides wallet totals without customers.finance permission", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: () => false,
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(
      <CustomerProfileDrawer
        open
        customerId="user-1"
        accountId="acct-1"
        onClose={() => undefined}
        onOpenCustomerPage={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-1", "acct-1");
    });

    expect(screen.getAllByText((content) => content.includes("需财务权限")).length).toBeGreaterThan(0);
    expect(screen.queryByText("100")).toBeNull();
    expect(screen.queryByText("80")).toBeNull();
    expect(screen.queryByText("20")).toBeNull();
  });

  it("shows the explicit user profile button copy", async () => {
    render(
      <CustomerProfileDrawer
        open
        customerId="user-1"
        accountId="acct-1"
        onClose={() => undefined}
        onOpenCustomerPage={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-1", "acct-1");
    });

    expect(screen.getByText("查看用户资料")).toBeTruthy();
  });
});
