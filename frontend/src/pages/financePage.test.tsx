import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FinancePage } from "./FinancePage";
import { useAppStore } from "../stores/appStore";

const hoisted = vi.hoisted(() => ({
  usePermissionsMock: vi.fn(),
  listRechargeRecordsMock: vi.fn(),
  listWithdrawalRecordsMock: vi.fn(),
  getFinanceSummaryMock: vi.fn(),
  listAnomalyAlertsMock: vi.fn(),
  listBonusGrantsMock: vi.fn(),
  listRechargeRepairsMock: vi.fn(),
  listWalletLedgersMock: vi.fn(),
  createBonusGrantMock: vi.fn(),
  approveBonusGrantMock: vi.fn(),
  rejectBonusGrantMock: vi.fn(),
  createRechargeRepairMock: vi.fn(),
  approveRechargeRepairMock: vi.fn(),
  rejectRechargeRepairMock: vi.fn(),
  showSuccessMock: vi.fn(),
  showErrorMock: vi.fn(),
}));

vi.mock("../hooks/usePermissions", () => ({
  usePermissions: hoisted.usePermissionsMock,
}));

vi.mock("../services/financeApi", () => ({
  listRechargeRecords: hoisted.listRechargeRecordsMock,
  listWithdrawalRecords: hoisted.listWithdrawalRecordsMock,
  getFinanceSummary: hoisted.getFinanceSummaryMock,
  listAnomalyAlerts: hoisted.listAnomalyAlertsMock,
  listBonusGrants: hoisted.listBonusGrantsMock,
  listRechargeRepairs: hoisted.listRechargeRepairsMock,
  listWalletLedgers: hoisted.listWalletLedgersMock,
  createBonusGrant: hoisted.createBonusGrantMock,
  approveBonusGrant: hoisted.approveBonusGrantMock,
  rejectBonusGrant: hoisted.rejectBonusGrantMock,
  createRechargeRepair: hoisted.createRechargeRepairMock,
  approveRechargeRepair: hoisted.approveRechargeRepairMock,
  rejectRechargeRepair: hoisted.rejectRechargeRepairMock,
}));

vi.mock("../components/Feedback", () => ({
  showError: hoisted.showErrorMock,
  showSuccess: hoisted.showSuccessMock,
}));

vi.mock("../components/DataExporter", () => ({
  DataExporter: ({ filename }: { filename: string }) => <div>{`export:${filename}`}</div>,
}));

describe("FinancePage", () => {
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
    hoisted.listRechargeRecordsMock.mockReset().mockResolvedValue([
      {
        id: "dep-1",
        user_id: "user-100",
        public_user_id: "h5-user-100",
        amount: 100,
        cash_amount: 100,
        bonus_amount: 0,
        currency: "USD",
        status: "paid",
        source_type: "manual_real_recharge",
        transaction_type: "manual_recharge",
        fund_type: "cash",
        is_bonus: false,
        is_real_recharge: true,
        created_at: "2026-06-24T10:00:00Z",
      },
      {
        id: "dep-2",
        user_id: "user-200",
        public_user_id: "h5-user-200",
        amount: 200,
        cash_amount: 0,
        bonus_amount: 200,
        currency: "USD",
        status: "paid",
        source_type: "admin_bonus",
        transaction_type: "bonus_grant",
        fund_type: "bonus",
        is_bonus: true,
        is_real_recharge: false,
        created_at: "2026-06-24T10:05:00Z",
      },
    ]);
    hoisted.listWithdrawalRecordsMock.mockReset().mockResolvedValue([
      {
        id: "wd-1",
        account_id: "acct-1",
        user_id: "user-100",
        public_user_id: "h5-user-100",
        amount: 250,
        cash_amount: 100,
        bonus_amount: 150,
        actual_payout_amount: 250,
        account_no_masked: "************5678",
        duplicate_account_count: 1,
        duplicate_member_ids: ["h5-user-200"],
        risk_level: "low",
        risk_flags: ["duplicate_withdraw_account"],
        currency: "USD",
        status: "paid",
        created_at: "2026-06-24T11:00:00Z",
      },
    ]);
    hoisted.getFinanceSummaryMock.mockReset().mockResolvedValue({
      recharge_amount: 100,
      recharge_count: 1,
      bonus_amount: 200,
      withdrawal_amount: 250,
      withdrawal_cash_amount: 100,
      withdrawal_bonus_amount: 150,
      withdrawal_fee: 0,
      withdrawal_count: 1,
      net_recharge: 0,
    });
    hoisted.listAnomalyAlertsMock.mockReset().mockResolvedValue([
      {
        type: "large_recharge",
        record_id: "dep-2",
        account_id: "acct-1",
        user_id: "user-200",
        public_user_id: "h5-user-200",
        amount: 200,
        time: "2026-06-24T10:05:00Z",
        message: "Large recharge detected: 200.",
      },
    ]);
    hoisted.listBonusGrantsMock.mockReset().mockResolvedValue([
      {
        id: "grant-1",
        account_id: "acct-1",
        grant_no: "BG-001",
        user_id: "user-300",
        public_user_id: "h5-user-300",
        amount: 88,
        currency: "USD",
        source_type: "admin_bonus",
        reason: "Campaign reward",
        remark: "June campaign",
        status: "pending",
        operator_id: "admin-1",
        approved_by: null,
        approved_at: null,
        credited_at: null,
        rejected_at: null,
        ledger_id: null,
        created_at: "2026-06-24T08:59:00Z",
      },
    ]);
    hoisted.listRechargeRepairsMock.mockReset().mockResolvedValue([
      {
        id: "repair-1",
        account_id: "acct-1",
        repair_no: "RR-001",
        user_id: "user-400",
        public_user_id: "h5-user-400",
        amount: 66,
        currency: "USD",
        repair_type: "callback_missing",
        reason: "Callback lost",
        remark: "Order missing callback",
        status: "pending",
        channel_id: "channel-1",
        platform_order_no: "PO-001",
        channel_order_no: "CO-001",
        operator_id: "admin-1",
        approved_by: null,
        approved_at: null,
        credited_at: null,
        rejected_at: null,
        recharge_record_id: null,
        ledger_id: null,
        created_at: "2026-06-24T11:59:00Z",
      },
    ]);
    hoisted.createBonusGrantMock.mockReset().mockResolvedValue({
      id: "grant-2",
      account_id: "acct-1",
      grant_no: "BG-002",
      user_id: "user-301",
      public_user_id: "h5-user-301",
      amount: 50,
      currency: "USD",
      source_type: "admin_bonus",
      reason: "Manual bonus",
      remark: "Ops",
      status: "pending",
      operator_id: "admin-1",
      approved_by: null,
      approved_at: null,
      credited_at: null,
      rejected_at: null,
      ledger_id: null,
      created_at: "2026-06-24T10:30:00Z",
    });
    hoisted.approveBonusGrantMock.mockReset().mockResolvedValue({
      id: "grant-1",
      status: "approved",
    });
    hoisted.rejectBonusGrantMock.mockReset().mockResolvedValue({
      id: "grant-1",
      status: "rejected",
    });
    hoisted.createRechargeRepairMock.mockReset().mockResolvedValue({
      id: "repair-2",
      account_id: "acct-1",
      repair_no: "RR-002",
      user_id: "user-401",
      public_user_id: "h5-user-401",
      amount: 77,
      currency: "USD",
      repair_type: "manual_real_recharge",
      reason: "Manual repair",
      remark: "Ops",
      status: "pending",
      channel_id: null,
      platform_order_no: "PO-002",
      channel_order_no: "CO-002",
      operator_id: "admin-1",
      approved_by: null,
      approved_at: null,
      credited_at: null,
      rejected_at: null,
      recharge_record_id: null,
      ledger_id: null,
      created_at: "2026-06-24T12:30:00Z",
    });
    hoisted.approveRechargeRepairMock.mockReset().mockResolvedValue({
      id: "repair-1",
      status: "approved",
    });
    hoisted.rejectRechargeRepairMock.mockReset().mockResolvedValue({
      id: "repair-1",
      status: "rejected",
    });
    hoisted.showSuccessMock.mockReset();
    hoisted.showErrorMock.mockReset();
    hoisted.listWalletLedgersMock.mockReset().mockResolvedValue([
      {
        id: "ledger-1",
        account_id: "acct-1",
        user_id: "user-500",
        public_user_id: "h5-user-500",
        amount: 120,
        cash_amount: 120,
        bonus_amount: 0,
        task_amount: 0,
        currency: "USD",
        status: "paid",
        source_type: "manual_real_recharge",
        transaction_type: "manual_recharge",
        fund_type: "cash",
        ledger_type: "system",
        direction: "credit",
        balance_after: 120,
        cash_balance_after: 120,
        bonus_balance_after: 0,
        task_balance_after: 0,
        display_category: "wallet_credit",
        display_title: "Manual recharge credited",
        note: "Manual recharge credited",
        created_at: "2026-06-24T13:00:00Z",
      },
      {
        id: "ledger-2",
        account_id: "acct-1",
        user_id: "user-500",
        public_user_id: "h5-user-500",
        amount: 50,
        cash_amount: 50,
        bonus_amount: 0,
        task_amount: 0,
        currency: "USD",
        status: "submitted",
        source_type: "withdrawal",
        transaction_type: "withdraw_request",
        fund_type: "cash",
        ledger_type: "system",
        direction: "debit",
        balance_after: 70,
        cash_balance_after: 70,
        bonus_balance_after: 0,
        task_balance_after: 0,
        display_category: "withdrawal",
        display_title: "Withdrawal submitted",
        note: "Withdrawal submitted",
        created_at: "2026-06-24T13:05:00Z",
      },
    ]);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("loads real finance data instead of rendering built-in mock summaries", async () => {
    render(<FinancePage />);

    await waitFor(() => {
      expect(hoisted.listRechargeRecordsMock).toHaveBeenCalled();
      expect(hoisted.listWithdrawalRecordsMock).toHaveBeenCalled();
      expect(hoisted.getFinanceSummaryMock).toHaveBeenCalled();
      expect(hoisted.listAnomalyAlertsMock).toHaveBeenCalled();
    });

    expect(await screen.findByText("h5-user-100")).toBeTruthy();
    expect(screen.getByText("h5-user-200")).toBeTruthy();
    expect(screen.getByText("manual_real_recharge")).toBeTruthy();
    expect(screen.getByText("admin_bonus")).toBeTruthy();
    expect(screen.getByText("************5678")).toBeTruthy();
    expect(screen.getByText("重复账户 1人")).toBeTruthy();
    expect(screen.queryByText("张三")).toBeNull();
    expect(screen.queryByText("¥5,000")).toBeNull();
    expect(screen.getByText(/export:finance-recharges-/)).toBeTruthy();
    expect(screen.queryByText("user-100")).toBeNull();
  });

  it("renders readable chinese finance copy and table pagination totals with sortable headers", async () => {
    render(<FinancePage />);

    expect(await screen.findByText("财务管理")).toBeTruthy();
    expect(screen.getByText("真实充值、提现、赠金与异常告警统一汇总")).toBeTruthy();
    expect(screen.getByText("共 2 条")).toBeTruthy();

    const sortableHeader = screen.getByText("时间").closest("th");
    expect(sortableHeader?.className).toContain("ant-table-column-has-sorters");
  });

  it("loads bonus grants and recharge repairs from real finance endpoints", async () => {
    render(<FinancePage />);

    await waitFor(() => {
      expect(hoisted.listBonusGrantsMock).toHaveBeenCalled();
      expect(hoisted.listRechargeRepairsMock).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole("tab", { name: "赠金管理" }));
    expect(await screen.findByText("BG-001")).toBeTruthy();
    expect(screen.getByText("h5-user-300")).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "补单中心" }));
    expect(await screen.findByText("RR-001")).toBeTruthy();
    expect(screen.getByText("h5-user-300")).toBeTruthy();
    expect(screen.getByText("h5-user-400")).toBeTruthy();
  });

  it("hides finance export actions without reports.export permission", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: (code: string) => code !== "reports.export",
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(<FinancePage />);

    await waitFor(() => {
      expect(hoisted.listRechargeRecordsMock).toHaveBeenCalled();
    });

    expect(screen.queryByText(/export:finance-recharges-/)).toBeNull();
    expect(screen.queryByText(/export:finance-withdrawals-/)).toBeNull();
  });

  it("shows a clear empty-permission state when the page is reachable but no finance tabs are available", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: () => false,
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(<FinancePage />);

    expect(await screen.findByText("暂无可用财务能力")).toBeTruthy();
    expect(screen.queryByRole("tab")).toBeNull();
    expect(hoisted.listRechargeRecordsMock).not.toHaveBeenCalled();
    expect(hoisted.listAnomalyAlertsMock).not.toHaveBeenCalled();
  });

  it("does not render the anomaly alerts tab for withdrawal-only roles", async () => {
    hoisted.usePermissionsMock.mockReturnValue({
      can: (code: string) => code === "finance.view_withdrawal",
      canSeePage: () => true,
      perms: null,
      loading: false,
    });

    render(<FinancePage />);

    await waitFor(() => {
      expect(hoisted.listWithdrawalRecordsMock).toHaveBeenCalled();
    });

    expect(screen.queryByRole("tab", { name: "异常告警" })).toBeNull();
    expect(hoisted.listAnomalyAlertsMock).not.toHaveBeenCalled();
  });

  it("loads wallet ledgers from the real finance endpoint", async () => {
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("tab", { name: "钱包流水" }));

    await waitFor(() => {
      expect(hoisted.listWalletLedgersMock).toHaveBeenCalled();
    });

    expect(await screen.findByText("ledger-1")).toBeTruthy();
    expect(screen.getAllByText("h5-user-500")).toHaveLength(2);
    expect(screen.getByText("manual_recharge")).toBeTruthy();
    expect(screen.getByText("withdraw_request")).toBeTruthy();
    expect(screen.getByText("Manual recharge credited")).toBeTruthy();
    expect(screen.getByText("流水 ID")).toBeTruthy();
    expect(screen.getAllByText("用户ID").length).toBeGreaterThan(0);
    expect(screen.getAllByText("交易类型").length).toBeGreaterThan(0);
    expect(screen.queryByText("娴佹按 ID")).toBeNull();
  });

  it("opens the customer detail page when a finance member id is clicked", async () => {
    render(<FinancePage />);

    const rechargeUserLink = await screen.findByRole("button", { name: "h5-user-100" });
    fireEvent.click(rechargeUserLink);

    expect(useAppStore.getState().activePage).toBe("customers");
    expect(useAppStore.getState().customersPagePrefill).toMatchObject({
      account_id: undefined,
      query: "h5-user-100",
      selected_profile_id: "user-100",
    });

    fireEvent.click(screen.getByRole("tab", { name: "钱包流水" }));
    const walletUserLinks = await screen.findAllByRole("button", { name: "h5-user-500" });
    fireEvent.click(walletUserLinks[0]);

    expect(useAppStore.getState().customersPagePrefill).toMatchObject({
      account_id: "acct-1",
      query: "h5-user-500",
      selected_profile_id: "user-500",
    });

    fireEvent.click(screen.getByRole("tab", { name: "异常告警" }));
    const anomalyUserLink = await screen.findByRole("button", { name: "h5-user-200" });
    fireEvent.click(anomalyUserLink);

    expect(useAppStore.getState().customersPagePrefill).toMatchObject({
      account_id: "acct-1",
      query: "h5-user-200",
      selected_profile_id: "user-200",
    });
  });

  it("passes wallet ledger sort params to the real finance endpoint", async () => {
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("tab", { name: "钱包流水" }));
    await waitFor(() => {
      expect(hoisted.listWalletLedgersMock).toHaveBeenCalled();
    });

    const initialLastCall = hoisted.listWalletLedgersMock.mock.calls.at(-1)?.[0];
    expect(initialLastCall).toMatchObject({
      sortField: "created_at",
      sortOrder: "desc",
    });

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "wallet-ledger-sort-field" }));
    fireEvent.click(await screen.findByText("按金额"));

    await waitFor(() => {
      const lastCall = hoisted.listWalletLedgersMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        sortField: "amount",
        sortOrder: "desc",
      });
    });

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "wallet-ledger-sort-order" }));
    fireEvent.click(await screen.findByText("升序"));

    await waitFor(() => {
      const lastCall = hoisted.listWalletLedgersMock.mock.calls.at(-1)?.[0];
      expect(lastCall).toMatchObject({
        sortField: "amount",
        sortOrder: "asc",
      });
    });
  });

  it("creates and approves bonus grants from the finance page", async () => {
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("tab", { name: "赠金管理" }));
    expect(await screen.findByText("BG-001")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("create-bonus-grant"));
    fireEvent.change(screen.getByLabelText("bonus-grant-account-id"), { target: { value: "acct-1" } });
    fireEvent.change(screen.getByLabelText("bonus-grant-user-id"), { target: { value: "user-301" } });
    fireEvent.change(screen.getByLabelText("bonus-grant-amount"), { target: { value: "50" } });
    fireEvent.change(screen.getByLabelText("bonus-grant-reason"), { target: { value: "Manual bonus" } });
    fireEvent.change(screen.getByLabelText("bonus-grant-remark"), { target: { value: "Ops" } });
    fireEvent.click(screen.getByLabelText("submit-bonus-grant"));

    await waitFor(() => {
      expect(hoisted.createBonusGrantMock).toHaveBeenCalledWith({
        accountId: "acct-1",
        userId: "user-301",
        amount: 50,
        currency: "USD",
        sourceType: "admin_bonus",
        reason: "Manual bonus",
        remark: "Ops",
      });
    });

    fireEvent.click(screen.getByLabelText("approve-bonus-grant-grant-1"));

    await waitFor(() => {
      expect(hoisted.approveBonusGrantMock).toHaveBeenCalledWith("grant-1");
    });

    expect(hoisted.showSuccessMock).toHaveBeenCalled();
    expect(hoisted.listBonusGrantsMock).toHaveBeenCalledTimes(3);
  });

  it("creates and rejects recharge repairs from the finance page", async () => {
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("tab", { name: "补单中心" }));
    expect(await screen.findByText("RR-001")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("create-recharge-repair"));
    fireEvent.change(screen.getByLabelText("recharge-repair-account-id"), { target: { value: "acct-1" } });
    fireEvent.change(screen.getByLabelText("recharge-repair-user-id"), { target: { value: "user-401" } });
    fireEvent.change(screen.getByLabelText("recharge-repair-amount"), { target: { value: "77" } });
    fireEvent.change(screen.getByLabelText("recharge-repair-platform-order-no"), { target: { value: "PO-002" } });
    fireEvent.change(screen.getByLabelText("recharge-repair-channel-order-no"), { target: { value: "CO-002" } });
    fireEvent.change(screen.getByLabelText("recharge-repair-reason"), { target: { value: "Manual repair" } });
    fireEvent.change(screen.getByLabelText("recharge-repair-remark"), { target: { value: "Ops" } });
    fireEvent.click(screen.getByLabelText("submit-recharge-repair"));

    await waitFor(() => {
      expect(hoisted.createRechargeRepairMock).toHaveBeenCalledWith({
        accountId: "acct-1",
        userId: "user-401",
        amount: 77,
        currency: "USD",
        repairType: "manual_real_recharge",
        reason: "Manual repair",
        remark: "Ops",
        channelId: "",
        platformOrderNo: "PO-002",
        channelOrderNo: "CO-002",
      });
    });

    fireEvent.click(screen.getByLabelText("reject-recharge-repair-repair-1"));
    fireEvent.change(screen.getByLabelText("decision-reason"), { target: { value: "Duplicate order" } });
    fireEvent.click(screen.getByLabelText("submit-decision"));

    await waitFor(() => {
      expect(hoisted.rejectRechargeRepairMock).toHaveBeenCalledWith("repair-1", { reason: "Duplicate order" });
    });

    expect(hoisted.showSuccessMock).toHaveBeenCalled();
    expect(hoisted.listRechargeRepairsMock).toHaveBeenCalledTimes(3);
  });
});
