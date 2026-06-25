import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemberIdLink } from "./MemberIdLink";
import { useAppStore } from "../../stores/appStore";

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

describe("MemberIdLink", () => {
  beforeEach(() => {
    useAppStore.setState({
      activePage: "dashboard",
      customersPagePrefill: null,
    });
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    vi.stubGlobal(
      "getComputedStyle",
      vi.fn().mockImplementation(() => ({
        getPropertyValue: () => "",
      })),
    );
    hoisted.getCustomerSummaryMock.mockReset().mockResolvedValue({
      customer: {
        id: "user-100",
        public_user_id: "pub-100",
        display_name: "Alice",
        language: "en",
        created_at: "2026-06-24T10:00:00Z",
        lifecycle_status: "active",
        registration_ip: "1.1.1.1",
        registration_ips: ["1.1.1.1"],
        multi_ip: false,
      },
      wallet: {
        balance: 188,
        total_recharged: 300,
        total_withdrawn: 112,
        recent_transactions: [],
      },
      member_status: {
        verification: { status: "approved", request_type: "kyc" },
        whatsapp_binding: { status: "bound", phone_number: "+123456" },
      },
      member_profile: null,
      conversations: { total: 5, open: 1, items: [] },
      tickets: { total: 2, open: 1, items: [] },
      tags: ["vip"],
    });
    hoisted.usePermissionsMock.mockReset().mockReturnValue({
      can: (code: string) => ["member.popover.view", "member.finance_breakdown.view", "customers.detail"].includes(code),
      canSeePage: () => true,
      perms: null,
      loading: false,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads and shows a member summary popover before navigating", async () => {
    render(<MemberIdLink accountId="acct-1" publicUserId="pub-100" userId="user-100" />);

    const trigger = screen.getByRole("button", { name: "pub-100" });
    fireEvent.mouseEnter(trigger);

    await waitFor(() => {
      expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-100", "acct-1");
    });

    expect(await screen.findByText("Alice")).toBeTruthy();
    expect(screen.getAllByText("pub-100").length).toBeGreaterThan(0);
    expect(screen.getByText("VIP")).toBeTruthy();
    expect(screen.getByText("300.00")).toBeTruthy();
    expect(screen.getByText("112.00")).toBeTruthy();

    fireEvent.click(trigger);

    expect(useAppStore.getState().activePage).toBe("customers");
    expect(useAppStore.getState().customersPagePrefill).toMatchObject({
      account_id: "acct-1",
      query: "pub-100",
      selected_profile_id: "user-100",
    });
  });

  it("hides finance totals in the popover without finance breakdown permission", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: (code: string) => ["member.popover.view", "customers.detail"].includes(code),
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(<MemberIdLink accountId="acct-1" publicUserId="pub-100" userId="user-100" />);

    const trigger = screen.getByRole("button", { name: "pub-100" });
    fireEvent.mouseEnter(trigger);

    await waitFor(() => {
      expect(hoisted.getCustomerSummaryMock).toHaveBeenCalledWith("user-100", "acct-1");
    });

    expect(await screen.findAllByText("需财务权限")).toHaveLength(3);
  });

  it("falls back to a plain member link when popover permission is missing", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: () => false,
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(<MemberIdLink accountId="acct-1" publicUserId="pub-100" userId="user-100" />);

    const trigger = screen.getByRole("button", { name: "pub-100" });
    fireEvent.mouseEnter(trigger);

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(hoisted.getCustomerSummaryMock).not.toHaveBeenCalled();
  });

  it("opens the customer page with public user id only when no internal user id is available", () => {
    render(<MemberIdLink accountId="acct-1" publicUserId="pub-200" />);

    fireEvent.click(screen.getByRole("button", { name: "pub-200" }));

    expect(useAppStore.getState().activePage).toBe("customers");
    expect(useAppStore.getState().customersPagePrefill).toMatchObject({
      account_id: "acct-1",
      query: "pub-200",
    });
    expect(useAppStore.getState().customersPagePrefill?.selected_profile_id).toBeUndefined();
    expect(hoisted.getCustomerSummaryMock).not.toHaveBeenCalled();
  });
});
