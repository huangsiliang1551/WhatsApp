import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReportsPage } from "./ReportsPage";
import { useAppStore } from "../stores/appStore";

const hoisted = vi.hoisted(() => ({
  usePermissionsMock: vi.fn(),
  getWhatsAppStatsSummaryMock: vi.fn(),
  listSitesMock: vi.fn(),
  getReportCenterSnapshotMock: vi.fn(),
  fetchOwnershipReportMock: vi.fn(),
  getFinanceSummaryMock: vi.fn(),
}));

vi.mock("../hooks/usePermissions", () => ({
  usePermissions: hoisted.usePermissionsMock,
}));

vi.mock("../services/api", () => ({
  getWhatsAppStatsSummary: hoisted.getWhatsAppStatsSummaryMock,
}));

vi.mock("../services/h5MultiTenantApi", () => ({
  listSites: hoisted.listSitesMock,
}));

vi.mock("../services/operations", () => ({
  getReportCenterSnapshot: hoisted.getReportCenterSnapshotMock,
}));

vi.mock("../services/ownershipReports", () => ({
  fetchOwnershipReport: hoisted.fetchOwnershipReportMock,
}));

vi.mock("../services/financeApi", () => ({
  getFinanceSummary: hoisted.getFinanceSummaryMock,
}));

describe("ReportsPage", () => {
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

    hoisted.usePermissionsMock.mockReset().mockReturnValue({
      can: () => true,
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    hoisted.getWhatsAppStatsSummaryMock.mockReset().mockResolvedValue({
      inbound_message_count: 0,
      outbound_message_count: 0,
      delivered_count: 0,
      read_count: 0,
      failed_count: 0,
      conversation_count: 0,
      unique_customer_count: 0,
      billable_count: 0,
      estimated_cost: 0,
    });
    hoisted.listSitesMock.mockReset().mockResolvedValue([]);
    hoisted.getReportCenterSnapshotMock.mockReset().mockResolvedValue({
      kpis: [],
      daily_rows: [],
    });
    hoisted.fetchOwnershipReportMock.mockReset().mockResolvedValue({
      current: {
        owner: { unattributed: 0, by_owner: [] },
        ai: { no_ai_assignment: 0, by_ai_agent: [] },
      },
      ai_reception: {
        ai_message_count: 0,
        failover_event_count: 0,
      },
      entry_links: [],
      anomalies: {
        no_owner_member_count: 0,
        no_ai_member_count: 0,
        entry_link_pointing_disabled_ai: 0,
        ai_without_fallback_staff: 0,
      },
    });
    hoisted.getFinanceSummaryMock.mockReset().mockResolvedValue({
      recharge_amount: 321,
      recharge_count: 3,
      bonus_amount: 12,
      withdrawal_amount: 111,
      withdrawal_cash_amount: 90,
      withdrawal_bonus_amount: 21,
      withdrawal_fee: 0,
      withdrawal_count: 2,
      net_recharge: 210,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("uses the real finance summary chain and jumps into FinancePage", async () => {
    render(<ReportsPage />);

    fireEvent.click(screen.getByRole("tab", { name: "\u8d22\u52a1\u62a5\u8868" }));

    await waitFor(() => {
      expect(hoisted.getFinanceSummaryMock).toHaveBeenCalled();
    });

    expect(await screen.findByText("321")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "\u8fdb\u5165\u8d22\u52a1\u5de5\u4f5c\u53f0" }));

    expect(useAppStore.getState().activePage).toBe("finance");
  });

  it("hides the finance tab when reports.finance permission is missing", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: (code: string) => code !== "reports.finance",
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(<ReportsPage />);

    expect(screen.queryByRole("tab", { name: "\u8d22\u52a1\u62a5\u8868" })).toBeNull();

    await waitFor(() => {
      expect(hoisted.getWhatsAppStatsSummaryMock).toHaveBeenCalled();
    });

    expect(hoisted.getFinanceSummaryMock).not.toHaveBeenCalled();
  });

  it("keeps the finance summary but hides the workbench jump when the finance page is not accessible", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: () => true,
      canSeePage: (pageId: string) => pageId !== "finance",
      perms: null,
      loading: false,
    });

    render(<ReportsPage />);

    fireEvent.click(screen.getByRole("tab", { name: "\u8d22\u52a1\u62a5\u8868" }));

    await waitFor(() => {
      expect(hoisted.getFinanceSummaryMock).toHaveBeenCalled();
    });

    expect(screen.queryByRole("button", { name: "\u8fdb\u5165\u8d22\u52a1\u5de5\u4f5c\u53f0" })).toBeNull();
  });
});

