import { useEffect, useMemo, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Popover,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  type TableProps,
  Tabs,
  Tag,
  Typography,
} from "antd";

import { DataExporter, type ExportColumn } from "../components/DataExporter";
import { showError, showSuccess } from "../components/Feedback";
import { MemberIdLink } from "../components/member/MemberIdLink";
import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePermissions } from "../hooks/usePermissions";
import {
  approveBonusGrant,
  approveRechargeRepair,
  createBonusGrant,
  createRechargeRepair,
  getFinanceSummary,
  listAnomalyAlerts,
  listBonusGrants,
  listRechargeRecords,
  listRechargeRepairs,
  listWalletLedgers,
  listWithdrawalRecords,
  rejectBonusGrant,
  rejectRechargeRepair,
  type FinanceAnomalyAlert,
  type FinanceBonusGrant,
  type FinanceRechargeRecord,
  type FinanceRechargeRepair,
  type FinanceSummary,
  type FinanceWalletLedger,
  type FinanceWithdrawalRecord,
} from "../services/financeApi";

type FundScope = "cash" | "bonus" | undefined;
type SortOrder = "asc" | "desc";
type DecisionTarget =
  | { kind: "bonus"; id: string }
  | { kind: "repair"; id: string }
  | null;

interface BonusGrantFormValues {
  accountId: string;
  userId: string;
  amount: string;
  currency: string;
  sourceType: string;
  reason: string;
  remark: string;
}

interface RechargeRepairFormValues {
  accountId: string;
  userId: string;
  amount: string;
  currency: string;
  repairType: string;
  reason: string;
  remark: string;
  channelId: string;
  platformOrderNo: string;
  channelOrderNo: string;
}

interface DecisionFormValues {
  reason: string;
}

function formatMoney(value: number | undefined | null): string {
  return Number(value ?? 0).toFixed(2);
}

function formatDateTime(value: string | undefined | null): string {
  if (!value) return "-";
  return value.replace("T", " ").replace("Z", "").slice(0, 19);
}

function buildExportColumns(columns: Array<{ key: string; label: string }>): ExportColumn[] {
  return columns.map((column) => ({ key: column.key, label: column.label }));
}

function exportFilename(prefix: string): string {
  const stamp = new Date().toISOString().replace(/[:T]/g, "-").slice(0, 19);
  return `${prefix}-${stamp}.csv`;
}

function renderStatusTag(status: string): JSX.Element {
  const tone =
    status === "paid" || status === "approved"
      ? "green"
      : status === "pending"
        ? "orange"
        : status === "rejected" || status === "failed"
          ? "red"
          : "default";
  return <Tag color={tone}>{status}</Tag>;
}

function renderMemberLink(
  userId: string | undefined,
  accountId?: string | null,
  publicUserId?: string | null,
): JSX.Element {
  return <MemberIdLink accountId={accountId} publicUserId={publicUserId} userId={userId} />;
}

function renderDuplicateAccountSummary(record: FinanceWithdrawalRecord): JSX.Element {
  const duplicateCount = record.duplicate_account_count ?? 0;
  const duplicateIds = record.duplicate_member_ids ?? [];
  if (duplicateCount <= 0) {
    return <Tag>无重复</Tag>;
  }
  const label = record.risk_level === "high" ? `重复账户 ${duplicateCount}人，高风险` : `重复账户 ${duplicateCount}人`;
  return (
    <Popover
      content={(
        <Space direction="vertical" size={4}>
          <Typography.Text strong>重合会员ID</Typography.Text>
          {duplicateIds.length > 0 ? (
            duplicateIds.map((item) => (
              <MemberIdLink key={item} accountId={record.account_id} publicUserId={item} label={item} />
            ))
          ) : (
            <Typography.Text type="secondary">暂无明细</Typography.Text>
          )}
        </Space>
      )}
      title={record.account_no_masked ? `提现账户 ${record.account_no_masked}` : "重复账户"}
      trigger="hover"
    >
      <Tag color={record.risk_level === "high" ? "red" : "orange"}>{label}</Tag>
    </Popover>
  );
}

const sortOrderOptions: Array<{ label: string; value: SortOrder }> = [
  { label: "最新优先", value: "desc" },
  { label: "升序", value: "asc" },
];

const rechargeSortFieldOptions = [
  { label: "按创建时间", value: "created_at" },
  { label: "按金额", value: "amount" },
  { label: "按现金金额", value: "cash_amount" },
  { label: "按赠金金额", value: "bonus_amount" },
  { label: "按用户ID", value: "user_id" },
];

const withdrawalSortFieldOptions = [
  { label: "按创建时间", value: "created_at" },
  { label: "按提现总额", value: "amount" },
  { label: "按现金部分", value: "cash_amount" },
  { label: "按赠金部分", value: "bonus_amount" },
  { label: "按用户ID", value: "user_id" },
];

const walletLedgerSortFieldOptions = [
  { label: "按创建时间", value: "created_at" },
  { label: "按金额", value: "amount" },
  { label: "按现金金额", value: "cash_amount" },
  { label: "按赠金金额", value: "bonus_amount" },
  { label: "按用户ID", value: "user_id" },
  { label: "按流水后余额", value: "balance_after" },
];

export function FinancePage(): JSX.Element {
  const { can } = usePermissions();
  const canViewRecharge = can("finance.view_recharge");
  const canViewWithdrawal = can("finance.view_withdrawal") || can("finance.approve_withdrawal");
  const canViewFinanceReports = can("reports.finance");
  const canExportReports = can("reports.export");
  const canManageFinance = can("finance.edit_channels");
  const hasPrimaryFinanceAccess = canViewRecharge || canViewWithdrawal || canViewFinanceReports;

  const [rechargeRows, setRechargeRows] = useState<FinanceRechargeRecord[]>([]);
  const [withdrawalRows, setWithdrawalRows] = useState<FinanceWithdrawalRecord[]>([]);
  const [summary, setSummary] = useState<FinanceSummary | null>(null);
  const [alerts, setAlerts] = useState<FinanceAnomalyAlert[]>([]);
  const [bonusGrantRows, setBonusGrantRows] = useState<FinanceBonusGrant[]>([]);
  const [rechargeRepairRows, setRechargeRepairRows] = useState<FinanceRechargeRepair[]>([]);
  const [walletLedgerRows, setWalletLedgerRows] = useState<FinanceWalletLedger[]>([]);

  const [rechargeLoading, setRechargeLoading] = useState(false);
  const [withdrawalLoading, setWithdrawalLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [bonusGrantLoading, setBonusGrantLoading] = useState(false);
  const [rechargeRepairLoading, setRechargeRepairLoading] = useState(false);
  const [walletLedgerLoading, setWalletLedgerLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const [rechargeStatus, setRechargeStatus] = useState<string | undefined>();
  const [rechargeSourceType, setRechargeSourceType] = useState<string | undefined>();
  const [rechargeFundScope, setRechargeFundScope] = useState<FundScope>();
  const [rechargeIncludeBonus, setRechargeIncludeBonus] = useState(true);
  const [rechargeSortField, setRechargeSortField] = useState("created_at");
  const [rechargeSortOrder, setRechargeSortOrder] = useState<SortOrder>("desc");

  const [withdrawalStatus, setWithdrawalStatus] = useState<string | undefined>();
  const [withdrawalFundScope, setWithdrawalFundScope] = useState<FundScope>();
  const [withdrawalIncludeBonus, setWithdrawalIncludeBonus] = useState(true);
  const [withdrawalSortField, setWithdrawalSortField] = useState("created_at");
  const [withdrawalSortOrder, setWithdrawalSortOrder] = useState<SortOrder>("desc");

  const [summaryIncludeBonus, setSummaryIncludeBonus] = useState(true);
  const [walletLedgerStatus, setWalletLedgerStatus] = useState<string | undefined>();
  const [walletLedgerSourceType, setWalletLedgerSourceType] = useState<string | undefined>();
  const [walletLedgerTransactionType, setWalletLedgerTransactionType] = useState<string | undefined>();
  const [walletLedgerFundScope, setWalletLedgerFundScope] = useState<FundScope>();
  const [walletLedgerSortField, setWalletLedgerSortField] = useState("created_at");
  const [walletLedgerSortOrder, setWalletLedgerSortOrder] = useState<SortOrder>("desc");
  const [pageError, setPageError] = useState<string | null>(null);

  const [bonusGrantModalOpen, setBonusGrantModalOpen] = useState(false);
  const [rechargeRepairModalOpen, setRechargeRepairModalOpen] = useState(false);
  const [decisionTarget, setDecisionTarget] = useState<DecisionTarget>(null);

  const [bonusGrantForm] = Form.useForm<BonusGrantFormValues>();
  const [rechargeRepairForm] = Form.useForm<RechargeRepairFormValues>();
  const [decisionForm] = Form.useForm<DecisionFormValues>();

  const loadRechargeRows = async (): Promise<void> => {
    if (!canViewRecharge) return;
    setRechargeLoading(true);
    try {
      const rows = await listRechargeRecords({
        status: rechargeStatus,
        sourceType: rechargeSourceType,
        fundScope: rechargeFundScope,
        includeBonus: rechargeIncludeBonus,
        sortField: rechargeSortField,
        sortOrder: rechargeSortOrder,
      });
      setRechargeRows(rows);
    } catch (error) {
      setPageError("充值记录加载失败");
      showError(error instanceof Error ? error.message : "充值记录加载失败");
    } finally {
      setRechargeLoading(false);
    }
  };

  const loadWithdrawalRows = async (): Promise<void> => {
    if (!canViewWithdrawal) return;
    setWithdrawalLoading(true);
    try {
      const rows = await listWithdrawalRecords({
        status: withdrawalStatus,
        fundScope: withdrawalFundScope,
        includeBonus: withdrawalIncludeBonus,
        sortField: withdrawalSortField,
        sortOrder: withdrawalSortOrder,
      });
      setWithdrawalRows(rows);
    } catch (error) {
      setPageError("提现记录加载失败");
      showError(error instanceof Error ? error.message : "提现记录加载失败");
    } finally {
      setWithdrawalLoading(false);
    }
  };

  const loadSummary = async (): Promise<void> => {
    if (!canViewFinanceReports) return;
    setSummaryLoading(true);
    try {
      const nextSummary = await getFinanceSummary({ includeBonus: summaryIncludeBonus });
      setSummary(nextSummary);
    } catch (error) {
      setPageError("财务汇总加载失败");
      showError(error instanceof Error ? error.message : "财务汇总加载失败");
    } finally {
      setSummaryLoading(false);
    }
  };

  const loadAlerts = async (): Promise<void> => {
    if (!canViewFinanceReports) return;
    setAlertsLoading(true);
    try {
      setAlerts(await listAnomalyAlerts());
    } catch (error) {
      setPageError("异常告警加载失败");
      showError(error instanceof Error ? error.message : "异常告警加载失败");
    } finally {
      setAlertsLoading(false);
    }
  };

  const loadBonusGrants = async (): Promise<void> => {
    if (!canViewFinanceReports) return;
    setBonusGrantLoading(true);
    try {
      setBonusGrantRows(await listBonusGrants());
    } catch (error) {
      setPageError("赠金记录加载失败");
      showError(error instanceof Error ? error.message : "赠金记录加载失败");
    } finally {
      setBonusGrantLoading(false);
    }
  };

  const loadRechargeRepairs = async (): Promise<void> => {
    if (!canViewFinanceReports) return;
    setRechargeRepairLoading(true);
    try {
      setRechargeRepairRows(await listRechargeRepairs());
    } catch (error) {
      setPageError("补单记录加载失败");
      showError(error instanceof Error ? error.message : "补单记录加载失败");
    } finally {
      setRechargeRepairLoading(false);
    }
  };

  const loadWalletLedgers = async (): Promise<void> => {
    if (!canViewFinanceReports) return;
    setWalletLedgerLoading(true);
    try {
      const rows = await listWalletLedgers({
        status: walletLedgerStatus,
        sourceType: walletLedgerSourceType,
        transactionType: walletLedgerTransactionType,
        fundScope: walletLedgerFundScope,
        sortField: walletLedgerSortField,
        sortOrder: walletLedgerSortOrder,
      });
      setWalletLedgerRows(rows);
    } catch (error) {
      setPageError("钱包流水加载失败");
      showError(error instanceof Error ? error.message : "钱包流水加载失败");
    } finally {
      setWalletLedgerLoading(false);
    }
  };

  useEffect(() => {
    setPageError(null);
    void loadRechargeRows();
  }, [canViewRecharge, rechargeStatus, rechargeSourceType, rechargeFundScope, rechargeIncludeBonus, rechargeSortField, rechargeSortOrder]);

  useEffect(() => {
    setPageError(null);
    void loadWithdrawalRows();
  }, [canViewWithdrawal, withdrawalStatus, withdrawalFundScope, withdrawalIncludeBonus, withdrawalSortField, withdrawalSortOrder]);

  useEffect(() => {
    setPageError(null);
    void loadSummary();
  }, [canViewFinanceReports, summaryIncludeBonus]);

  useEffect(() => {
    setPageError(null);
    void loadAlerts();
  }, [canViewFinanceReports, canViewWithdrawal]);

  useEffect(() => {
    setPageError(null);
    void loadBonusGrants();
    void loadRechargeRepairs();
  }, [canViewFinanceReports]);

  useEffect(() => {
    setPageError(null);
    void loadWalletLedgers();
  }, [canViewFinanceReports, walletLedgerStatus, walletLedgerSourceType, walletLedgerTransactionType, walletLedgerFundScope, walletLedgerSortField, walletLedgerSortOrder]);

  const summaryCards = useMemo(() => {
    if (!summary) return null;
    return (
      <Space wrap size={16}>
        <Card size="small"><Statistic title="真实充值" value={summary.recharge_amount} precision={2} /></Card>
        <Card size="small"><Statistic title="赠金发放" value={summary.bonus_amount} precision={2} /></Card>
        <Card size="small"><Statistic title="提现总额" value={summary.withdrawal_amount} precision={2} /></Card>
        <Card size="small"><Statistic title="提现现金部分" value={summary.withdrawal_cash_amount} precision={2} /></Card>
        <Card size="small"><Statistic title="提现赠金部分" value={summary.withdrawal_bonus_amount} precision={2} /></Card>
        <Card size="small"><Statistic title="净充值" value={summary.net_recharge} precision={2} /></Card>
      </Space>
    );
  }, [summary]);

  const duplicateWithdrawalAlerts = useMemo(
    () => withdrawalRows.filter((item) => (item.duplicate_account_count ?? 0) > 0),
    [withdrawalRows],
  );

  const openBonusGrantModal = (): void => {
    bonusGrantForm.setFieldsValue({
      accountId: "",
      userId: "",
      amount: "",
      currency: "USD",
      sourceType: "admin_bonus",
      reason: "",
      remark: "",
    });
    setBonusGrantModalOpen(true);
  };

  const openRechargeRepairModal = (): void => {
    rechargeRepairForm.setFieldsValue({
      accountId: "",
      userId: "",
      amount: "",
      currency: "USD",
      repairType: "manual_real_recharge",
      reason: "",
      remark: "",
      channelId: "",
      platformOrderNo: "",
      channelOrderNo: "",
    });
    setRechargeRepairModalOpen(true);
  };

  const handleCreateBonusGrant = async (): Promise<void> => {
    try {
      const values = await bonusGrantForm.validateFields();
      setActionLoading(true);
      await createBonusGrant({
        accountId: values.accountId,
        userId: values.userId,
        amount: Number(values.amount),
        currency: values.currency,
        sourceType: values.sourceType,
        reason: values.reason,
        remark: values.remark,
      });
      showSuccess("赠金申请已创建");
      setBonusGrantModalOpen(false);
      bonusGrantForm.resetFields();
      await loadBonusGrants();
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateRechargeRepair = async (): Promise<void> => {
    try {
      const values = await rechargeRepairForm.validateFields();
      setActionLoading(true);
      await createRechargeRepair({
        accountId: values.accountId,
        userId: values.userId,
        amount: Number(values.amount),
        currency: values.currency,
        repairType: values.repairType,
        reason: values.reason,
        remark: values.remark,
        channelId: values.channelId,
        platformOrderNo: values.platformOrderNo,
        channelOrderNo: values.channelOrderNo,
      });
      showSuccess("补单申请已创建");
      setRechargeRepairModalOpen(false);
      rechargeRepairForm.resetFields();
      await loadRechargeRepairs();
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveBonusGrant = async (grantId: string): Promise<void> => {
    try {
      setActionLoading(true);
      await approveBonusGrant(grantId);
      showSuccess("赠金已审核通过");
      await loadBonusGrants();
    } catch (error) {
      showError(error instanceof Error ? error.message : "赠金审核失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveRechargeRepair = async (repairId: string): Promise<void> => {
    try {
      setActionLoading(true);
      await approveRechargeRepair(repairId);
      showSuccess("补单已审核通过");
      await loadRechargeRepairs();
    } catch (error) {
      showError(error instanceof Error ? error.message : "补单审核失败");
    } finally {
      setActionLoading(false);
    }
  };

  const openDecisionModal = (target: DecisionTarget): void => {
    decisionForm.setFieldsValue({ reason: "" });
    setDecisionTarget(target);
  };

  const handleSubmitDecision = async (): Promise<void> => {
    if (!decisionTarget) return;
    try {
      const values = await decisionForm.validateFields();
      setActionLoading(true);
      if (decisionTarget.kind === "bonus") {
        await rejectBonusGrant(decisionTarget.id, { reason: values.reason || undefined });
        showSuccess("赠金已驳回");
        await loadBonusGrants();
      } else {
        await rejectRechargeRepair(decisionTarget.id, { reason: values.reason || undefined });
        showSuccess("补单已驳回");
        await loadRechargeRepairs();
      }
      setDecisionTarget(null);
      decisionForm.resetFields();
    } catch (error) {
      if (error instanceof Error) {
        showError(error.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const rechargeColumns = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (value: string | null | undefined) => formatDateTime(value),
    },
    {
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
      render: (value: string | undefined, record: FinanceRechargeRecord) =>
        renderMemberLink(value, record.account_id, record.public_user_id ?? value),
    },
    { title: "来源", dataIndex: "source_type", key: "source_type", render: (value: string | null | undefined) => value || "-" },
    { title: "总额", dataIndex: "amount", key: "amount", render: (value: number) => formatMoney(value) },
    { title: "现金", dataIndex: "cash_amount", key: "cash_amount", render: (value: number) => formatMoney(value) },
    { title: "赠金", dataIndex: "bonus_amount", key: "bonus_amount", render: (value: number) => formatMoney(value) },
    { title: "资金口径", dataIndex: "fund_type", key: "fund_type", render: (value: string | null | undefined) => value || "-" },
    { title: "状态", dataIndex: "status", key: "status", render: (value: string) => renderStatusTag(value) },
  ];

  const withdrawalColumns: TableProps<FinanceWithdrawalRecord>["columns"] = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (value: string | null | undefined) => formatDateTime(value),
    },
    {
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
      render: (value: string | undefined, record: FinanceWithdrawalRecord) =>
        renderMemberLink(value, record.account_id, record.public_user_id ?? value),
    },
    { title: "提现总额", dataIndex: "amount", key: "amount", render: (value: number) => formatMoney(value) },
    { title: "现金部分", dataIndex: "cash_amount", key: "cash_amount", render: (value: number) => formatMoney(value) },
    { title: "赠金部分", dataIndex: "bonus_amount", key: "bonus_amount", render: (value: number) => formatMoney(value) },
    {
      title: "实际打款",
      dataIndex: "actual_payout_amount",
      key: "actual_payout_amount",
      render: (value: number | undefined) => formatMoney(value),
    },
    { title: "状态", dataIndex: "status", key: "status", render: (value: string) => renderStatusTag(value) },
  ];

  withdrawalColumns.splice(withdrawalColumns.length - 1, 0,
    {
      title: "鎻愮幇璐︽埛",
      dataIndex: "account_no_masked",
      key: "account_no_masked",
      render: (value: string | null | undefined) => value || "-",
    },
    {
      title: "閲嶅璐︽埛",
      key: "duplicate_account_count",
      render: (_: unknown, record: FinanceWithdrawalRecord) => renderDuplicateAccountSummary(record),
    },
  );

  const alertColumns = [
    { title: "类型", dataIndex: "type", key: "type", render: (value: string) => <Tag color="red">{value}</Tag> },
    {
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
      render: (value: string | undefined, record: FinanceAnomalyAlert) =>
        record.user_id ? renderMemberLink(value, record.account_id, record.public_user_id ?? value) : value || "-",
    },
    { title: "金额", dataIndex: "amount", key: "amount", render: (value: number | undefined) => formatMoney(value) },
    { title: "时间", dataIndex: "time", key: "time", render: (value: string | undefined) => formatDateTime(value) },
    { title: "说明", dataIndex: "message", key: "message" },
  ];

  const bonusGrantColumns = [
    { title: "单号", dataIndex: "grant_no", key: "grant_no" },
    {
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
      render: (value: string | undefined, record: FinanceBonusGrant) =>
        renderMemberLink(value, record.account_id, record.public_user_id ?? value),
    },
    { title: "来源", dataIndex: "source_type", key: "source_type" },
    { title: "金额", dataIndex: "amount", key: "amount", render: (value: number) => formatMoney(value) },
    { title: "原因", dataIndex: "reason", key: "reason" },
    { title: "状态", dataIndex: "status", key: "status", render: (value: string) => renderStatusTag(value) },
    { title: "创建时间", dataIndex: "created_at", key: "created_at", render: (value: string | null | undefined) => formatDateTime(value) },
    ...(canManageFinance
      ? [{
          title: "操作",
          key: "actions",
          render: (_: unknown, record: FinanceBonusGrant) =>
            record.status === "pending" ? (
              <Space>
                <Button
                  size="small"
                  aria-label={`approve-bonus-grant-${record.id}`}
                  loading={actionLoading}
                  onClick={() => { void handleApproveBonusGrant(record.id); }}
                >
                  通过
                </Button>
                <Button
                  size="small"
                  danger
                  aria-label={`reject-bonus-grant-${record.id}`}
                  onClick={() => openDecisionModal({ kind: "bonus", id: record.id })}
                >
                  驳回
                </Button>
              </Space>
            ) : (
              <Typography.Text type="secondary">-</Typography.Text>
            ),
        }]
      : []),
  ];

  const rechargeRepairColumns = [
    { title: "单号", dataIndex: "repair_no", key: "repair_no" },
    {
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
      render: (value: string | undefined, record: FinanceRechargeRepair) =>
        renderMemberLink(value, record.account_id, record.public_user_id ?? value),
    },
    { title: "补单类型", dataIndex: "repair_type", key: "repair_type" },
    { title: "金额", dataIndex: "amount", key: "amount", render: (value: number) => formatMoney(value) },
    { title: "平台订单号", dataIndex: "platform_order_no", key: "platform_order_no", render: (value: string | null | undefined) => value || "-" },
    { title: "渠道订单号", dataIndex: "channel_order_no", key: "channel_order_no", render: (value: string | null | undefined) => value || "-" },
    { title: "状态", dataIndex: "status", key: "status", render: (value: string) => renderStatusTag(value) },
    { title: "创建时间", dataIndex: "created_at", key: "created_at", render: (value: string | null | undefined) => formatDateTime(value) },
    ...(canManageFinance
      ? [{
          title: "操作",
          key: "actions",
          render: (_: unknown, record: FinanceRechargeRepair) =>
            record.status === "pending" ? (
              <Space>
                <Button
                  size="small"
                  aria-label={`approve-recharge-repair-${record.id}`}
                  loading={actionLoading}
                  onClick={() => { void handleApproveRechargeRepair(record.id); }}
                >
                  通过
                </Button>
                <Button
                  size="small"
                  danger
                  aria-label={`reject-recharge-repair-${record.id}`}
                  onClick={() => openDecisionModal({ kind: "repair", id: record.id })}
                >
                  驳回
                </Button>
              </Space>
            ) : (
              <Typography.Text type="secondary">-</Typography.Text>
            ),
        }]
      : []),
  ];

  const walletLedgerColumns = [
    { title: "流水 ID", dataIndex: "id", key: "id" },
    {
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
      render: (value: string | undefined, record: FinanceWalletLedger) =>
        renderMemberLink(value, record.account_id, record.public_user_id ?? value),
    },
    { title: "方向", dataIndex: "direction", key: "direction", render: (value: string) => renderStatusTag(value) },
    { title: "交易类型", dataIndex: "transaction_type", key: "transaction_type" },
    { title: "来源", dataIndex: "source_type", key: "source_type", render: (value: string | null | undefined) => value || "-" },
    { title: "展示标题", dataIndex: "display_title", key: "display_title", render: (value: string | null | undefined) => value || "-" },
    { title: "金额", dataIndex: "amount", key: "amount", render: (value: number) => formatMoney(value) },
    { title: "现金", dataIndex: "cash_amount", key: "cash_amount", render: (value: number) => formatMoney(value) },
    { title: "赠金", dataIndex: "bonus_amount", key: "bonus_amount", render: (value: number) => formatMoney(value) },
    { title: "状态", dataIndex: "status", key: "status", render: (value: string) => renderStatusTag(value) },
    { title: "入账后余额", dataIndex: "balance_after", key: "balance_after", render: (value: number | null | undefined) => formatMoney(value) },
    { title: "创建时间", dataIndex: "created_at", key: "created_at", render: (value: string | null | undefined) => formatDateTime(value) },
  ];

  const rechargeExportColumns = buildExportColumns([
    { key: "created_at", label: "created_at" },
    { key: "account_id", label: "account_id" },
    { key: "user_id", label: "user_id" },
    { key: "public_user_id", label: "public_user_id" },
    { key: "source_type", label: "source_type" },
    { key: "amount", label: "amount" },
    { key: "cash_amount", label: "cash_amount" },
    { key: "bonus_amount", label: "bonus_amount" },
    { key: "fund_type", label: "fund_type" },
    { key: "status", label: "status" },
  ]);
  const withdrawalExportColumns = buildExportColumns([
    { key: "created_at", label: "created_at" },
    { key: "account_id", label: "account_id" },
    { key: "user_id", label: "user_id" },
    { key: "public_user_id", label: "public_user_id" },
    { key: "amount", label: "amount" },
    { key: "cash_amount", label: "cash_amount" },
    { key: "bonus_amount", label: "bonus_amount" },
    { key: "actual_payout_amount", label: "actual_payout_amount" },
    { key: "account_no_masked", label: "account_no_masked" },
    { key: "duplicate_account_count", label: "duplicate_account_count" },
    { key: "duplicate_member_ids", label: "duplicate_member_ids" },
    { key: "risk_level", label: "risk_level" },
    { key: "status", label: "status" },
  ]);
  const bonusGrantExportColumns = buildExportColumns([
    { key: "grant_no", label: "grant_no" },
    { key: "account_id", label: "account_id" },
    { key: "user_id", label: "user_id" },
    { key: "public_user_id", label: "public_user_id" },
    { key: "source_type", label: "source_type" },
    { key: "amount", label: "amount" },
    { key: "reason", label: "reason" },
    { key: "status", label: "status" },
    { key: "created_at", label: "created_at" },
  ]);
  const rechargeRepairExportColumns = buildExportColumns([
    { key: "repair_no", label: "repair_no" },
    { key: "account_id", label: "account_id" },
    { key: "user_id", label: "user_id" },
    { key: "public_user_id", label: "public_user_id" },
    { key: "repair_type", label: "repair_type" },
    { key: "amount", label: "amount" },
    { key: "platform_order_no", label: "platform_order_no" },
    { key: "channel_order_no", label: "channel_order_no" },
    { key: "status", label: "status" },
    { key: "created_at", label: "created_at" },
  ]);
  const walletLedgerExportColumns = buildExportColumns([
    { key: "id", label: "id" },
    { key: "account_id", label: "account_id" },
    { key: "user_id", label: "user_id" },
    { key: "public_user_id", label: "public_user_id" },
    { key: "direction", label: "direction" },
    { key: "transaction_type", label: "transaction_type" },
    { key: "source_type", label: "source_type" },
    { key: "display_title", label: "display_title" },
    { key: "amount", label: "amount" },
    { key: "cash_amount", label: "cash_amount" },
    { key: "bonus_amount", label: "bonus_amount" },
    { key: "status", label: "status" },
    { key: "balance_after", label: "balance_after" },
    { key: "created_at", label: "created_at" },
  ]);
  const alertsExportColumns = buildExportColumns([
    { key: "type", label: "type" },
    { key: "account_id", label: "account_id" },
    { key: "user_id", label: "user_id" },
    { key: "public_user_id", label: "public_user_id" },
    { key: "amount", label: "amount" },
    { key: "time", label: "time" },
    { key: "message", label: "message" },
  ]);
  const summaryExportColumns = buildExportColumns([
    { key: "recharge_amount", label: "recharge_amount" },
    { key: "recharge_count", label: "recharge_count" },
    { key: "bonus_amount", label: "bonus_amount" },
    { key: "withdrawal_amount", label: "withdrawal_amount" },
    { key: "withdrawal_cash_amount", label: "withdrawal_cash_amount" },
    { key: "withdrawal_bonus_amount", label: "withdrawal_bonus_amount" },
    { key: "withdrawal_fee", label: "withdrawal_fee" },
    { key: "withdrawal_count", label: "withdrawal_count" },
    { key: "net_recharge", label: "net_recharge" },
    { key: "include_bonus", label: "include_bonus" },
  ]);

  function renderExportAction(
    exportKey: string,
    columns: ExportColumn[],
    rows: Record<string, unknown>[],
  ): JSX.Element | null {
    if (!canExportReports) {
      return null;
    }
    return (
      <DataExporter
        columns={columns}
        filename={exportFilename(exportKey)}
        fetchData={async () => ({ data: rows, total: rows.length })}
        maxRows={10000}
      />
    );
  }

  /*
    <EmptyGuide
      title="该模块已移除 mock 数据"
      description="当前后端尚未提供正式接口，因此这里不再展示伪造统计。待接口接通后再恢复。"
    />
  */

  const refreshAll = (): void => {
    void loadRechargeRows();
    void loadWithdrawalRows();
    void loadSummary();
    void loadAlerts();
    void loadBonusGrants();
    void loadRechargeRepairs();
    void loadWalletLedgers();
  };

  if (!hasPrimaryFinanceAccess) {
    return (
      <PageShell
        title="璐㈠姟绠＄悊"
        subtitle="鐪熷疄鍏呭€笺€佹彁鐜般€佽禒閲戜笌寮傚父鍛婅缁熶竴姹囨€?"
      >
        <EmptyGuide
          title="鏆傛棤鍙敤璐㈠姟鑳藉姏"
          description="褰撳墠瑙掕壊灏氭湭寮€閫氬厖鍊笺€佹彁鐜版垨璐㈠姟鎶ヨ〃鏉冮檺锛岃鑱旂郴绠＄悊鍛樿皟鏁存潈闄愰厤缃€?"
        />
      </PageShell>
    );
  }

  const tabs = [
    ...(canViewRecharge
      ? [{
          key: "recharges",
          label: "充值记录",
          children: (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Space wrap>
                <Select
                  allowClear
                  placeholder="状态"
                  style={{ width: 140 }}
                  value={rechargeStatus}
                  onChange={(value) => setRechargeStatus(value)}
                  options={[
                    { label: "paid", value: "paid" },
                    { label: "pending", value: "pending" },
                    { label: "failed", value: "failed" },
                  ]}
                />
                <Select
                  allowClear
                  placeholder="来源"
                  style={{ width: 180 }}
                  value={rechargeSourceType}
                  onChange={(value) => setRechargeSourceType(value)}
                  options={[
                    { label: "manual_real_recharge", value: "manual_real_recharge" },
                    { label: "admin_bonus", value: "admin_bonus" },
                    { label: "payment_callback", value: "payment_callback" },
                    { label: "callback_repair", value: "callback_repair" },
                  ]}
                />
                <Select
                  allowClear
                  placeholder="资金口径"
                  style={{ width: 160 }}
                  value={rechargeFundScope}
                  onChange={(value) => setRechargeFundScope(value)}
                  options={[
                    { label: "只看现金", value: "cash" },
                    { label: "只看赠金", value: "bonus" },
                  ]}
                />
                <Space>
                  <Typography.Text>包含赠金</Typography.Text>
                  <Switch checked={rechargeIncludeBonus} onChange={setRechargeIncludeBonus} />
                </Space>
                <Select
                  aria-label="recharge-sort-field"
                  style={{ width: 160 }}
                  value={rechargeSortField}
                  onChange={setRechargeSortField}
                  options={rechargeSortFieldOptions}
                />
                <Select
                  aria-label="recharge-sort-order"
                  style={{ width: 140 }}
                  value={rechargeSortOrder}
                  onChange={(value) => setRechargeSortOrder(value as SortOrder)}
                  options={sortOrderOptions}
                />
                <Button onClick={() => void loadRechargeRows()}>刷新</Button>
                {renderExportAction("finance-recharges", rechargeExportColumns, rechargeRows.map((row) => ({
                  created_at: formatDateTime(row.created_at),
                  account_id: row.account_id ?? "",
                  user_id: row.user_id,
                  public_user_id: row.public_user_id ?? "",
                  source_type: row.source_type ?? "",
                  amount: row.amount,
                  cash_amount: row.cash_amount,
                  bonus_amount: row.bonus_amount,
                  fund_type: row.fund_type ?? "",
                  status: row.status,
                })))}
              </Space>
              <Table
                rowKey="id"
                loading={rechargeLoading}
                dataSource={rechargeRows}
                columns={rechargeColumns}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: rechargeLoading ? <Spin size="small" /> : <Empty description="暂无充值记录" /> }}
              />
            </Space>
          ),
        }]
      : []),
    ...(canViewWithdrawal
      ? [{
          key: "withdrawals",
          label: "提现记录",
          children: (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Space wrap>
                <Select
                  allowClear
                  placeholder="状态"
                  style={{ width: 140 }}
                  value={withdrawalStatus}
                  onChange={(value) => setWithdrawalStatus(value)}
                  options={[
                    { label: "pending", value: "pending" },
                    { label: "approved", value: "approved" },
                    { label: "paid", value: "paid" },
                    { label: "rejected", value: "rejected" },
                  ]}
                />
                <Select
                  allowClear
                  placeholder="资金口径"
                  style={{ width: 160 }}
                  value={withdrawalFundScope}
                  onChange={(value) => setWithdrawalFundScope(value)}
                  options={[
                    { label: "只看现金", value: "cash" },
                    { label: "只看赠金", value: "bonus" },
                  ]}
                />
                <Space>
                  <Typography.Text>包含赠金</Typography.Text>
                  <Switch checked={withdrawalIncludeBonus} onChange={setWithdrawalIncludeBonus} />
                </Space>
                <Select
                  aria-label="withdrawal-sort-field"
                  style={{ width: 160 }}
                  value={withdrawalSortField}
                  onChange={setWithdrawalSortField}
                  options={withdrawalSortFieldOptions}
                />
                <Select
                  aria-label="withdrawal-sort-order"
                  style={{ width: 140 }}
                  value={withdrawalSortOrder}
                  onChange={(value) => setWithdrawalSortOrder(value as SortOrder)}
                  options={sortOrderOptions}
                />
                <Button onClick={() => void loadWithdrawalRows()}>刷新</Button>
                {renderExportAction("finance-withdrawals", withdrawalExportColumns, withdrawalRows.map((row) => ({
                  created_at: formatDateTime(row.created_at),
                  account_id: row.account_id ?? "",
                  user_id: row.user_id,
                  public_user_id: row.public_user_id ?? "",
                  amount: row.amount,
                  cash_amount: row.cash_amount,
                  bonus_amount: row.bonus_amount,
                  actual_payout_amount: row.actual_payout_amount ?? 0,
                  account_no_masked: row.account_no_masked ?? "",
                  duplicate_account_count: row.duplicate_account_count ?? 0,
                  duplicate_member_ids: (row.duplicate_member_ids ?? []).join("|"),
                  risk_level: row.risk_level ?? "",
                  status: row.status,
                })))}
              </Space>
              <Alert
                type="info"
                showIcon
                message="当前页面已接真实提现列表。审批与驳回按钮后续会继续接入正式审核流，这里不再保留假成功动作。"
              />
              <Table
                rowKey="id"
                loading={withdrawalLoading}
                dataSource={withdrawalRows}
                columns={withdrawalColumns}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: withdrawalLoading ? <Spin size="small" /> : <Empty description="暂无提现记录" /> }}
              />
            </Space>
          ),
        }]
      : []),
    ...(canViewFinanceReports
      ? [{
          key: "summary",
          label: "财务报表",
          children: (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Space>
                <Typography.Text>报表包含赠金</Typography.Text>
                <Switch checked={summaryIncludeBonus} onChange={setSummaryIncludeBonus} />
                <Button onClick={() => void loadSummary()}>刷新</Button>
                {summary ? renderExportAction("finance-summary", summaryExportColumns, [{
                  recharge_amount: summary.recharge_amount,
                  recharge_count: summary.recharge_count,
                  bonus_amount: summary.bonus_amount,
                  withdrawal_amount: summary.withdrawal_amount,
                  withdrawal_cash_amount: summary.withdrawal_cash_amount,
                  withdrawal_bonus_amount: summary.withdrawal_bonus_amount,
                  withdrawal_fee: summary.withdrawal_fee,
                  withdrawal_count: summary.withdrawal_count,
                  net_recharge: summary.net_recharge,
                  include_bonus: summaryIncludeBonus,
                }]) : null}
              </Space>
              {summaryLoading ? <Spin /> : summaryCards}
            </Space>
          ),
        }]
      : []),
    ...(canViewFinanceReports
      ? [{
          key: "bonus-grants",
          label: "赠金管理",
          children: (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Alert
                type="info"
                showIcon
                message="赠金列表已经接入真实接口。本轮补齐创建、通过、驳回动作，便于财务后台直接闭环处理。"
              />
              <Space>
                {canManageFinance ? (
                  <Button type="primary" aria-label="create-bonus-grant" onClick={openBonusGrantModal}>
                    新建赠金
                  </Button>
                ) : null}
                <Button onClick={() => void loadBonusGrants()}>刷新</Button>
                {renderExportAction("finance-bonus-grants", bonusGrantExportColumns, bonusGrantRows.map((row) => ({
                  grant_no: row.grant_no,
                  account_id: row.account_id,
                  user_id: row.user_id,
                  public_user_id: row.public_user_id ?? "",
                  source_type: row.source_type,
                  amount: row.amount,
                  reason: row.reason,
                  status: row.status,
                  created_at: formatDateTime(row.created_at),
                })))}
              </Space>
              <Table
                rowKey="id"
                loading={bonusGrantLoading}
                dataSource={bonusGrantRows}
                columns={bonusGrantColumns}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: bonusGrantLoading ? <Spin size="small" /> : <Empty description="暂无赠金记录" /> }}
              />
            </Space>
          ),
        }]
      : []),
    ...(canViewFinanceReports
      ? [{
          key: "recharge-repairs",
          label: "补单中心",
          children: (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Alert
                type="info"
                showIcon
                message="补单列表已经接入真实接口。本轮补齐创建、通过、驳回动作，避免继续停留在只读状态。"
              />
              <Space>
                {canManageFinance ? (
                  <Button type="primary" aria-label="create-recharge-repair" onClick={openRechargeRepairModal}>
                    新建补单
                  </Button>
                ) : null}
                <Button onClick={() => void loadRechargeRepairs()}>刷新</Button>
                {renderExportAction("finance-recharge-repairs", rechargeRepairExportColumns, rechargeRepairRows.map((row) => ({
                  repair_no: row.repair_no,
                  account_id: row.account_id,
                  user_id: row.user_id,
                  public_user_id: row.public_user_id ?? "",
                  repair_type: row.repair_type,
                  amount: row.amount,
                  platform_order_no: row.platform_order_no ?? "",
                  channel_order_no: row.channel_order_no ?? "",
                  status: row.status,
                  created_at: formatDateTime(row.created_at),
                })))}
              </Space>
              <Table
                rowKey="id"
                loading={rechargeRepairLoading}
                dataSource={rechargeRepairRows}
                columns={rechargeRepairColumns}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: rechargeRepairLoading ? <Spin size="small" /> : <Empty description="暂无补单记录" /> }}
              />
            </Space>
          ),
        }]
      : []),
    ...(canViewFinanceReports
      ? [{
          key: "wallet-ledgers",
          label: "钱包流水",
          children: (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Space wrap>
                <Select
                  allowClear
                  placeholder="状态"
                  style={{ width: 140 }}
                  value={walletLedgerStatus}
                  onChange={(value) => setWalletLedgerStatus(value)}
                  options={[
                    { label: "paid", value: "paid" },
                    { label: "submitted", value: "submitted" },
                    { label: "approved", value: "approved" },
                    { label: "rejected", value: "rejected" },
                  ]}
                />
                <Select
                  allowClear
                  placeholder="来源"
                  style={{ width: 180 }}
                  value={walletLedgerSourceType}
                  onChange={(value) => setWalletLedgerSourceType(value)}
                  options={[
                    { label: "manual_real_recharge", value: "manual_real_recharge" },
                    { label: "admin_bonus", value: "admin_bonus" },
                    { label: "withdrawal", value: "withdrawal" },
                    { label: "withdrawal_reject_refund", value: "withdrawal_reject_refund" },
                    { label: "callback_repair", value: "callback_repair" },
                  ]}
                />
                <Select
                  allowClear
                  placeholder="交易类型"
                  style={{ width: 180 }}
                  value={walletLedgerTransactionType}
                  onChange={(value) => setWalletLedgerTransactionType(value)}
                  options={[
                    { label: "manual_recharge", value: "manual_recharge" },
                    { label: "bonus_grant", value: "bonus_grant" },
                    { label: "withdraw_request", value: "withdraw_request" },
                    { label: "withdraw_reject_refund", value: "withdraw_reject_refund" },
                    { label: "recharge_repair", value: "recharge_repair" },
                  ]}
                />
                <Select
                  allowClear
                  placeholder="资金口径"
                  style={{ width: 160 }}
                  value={walletLedgerFundScope}
                  onChange={(value) => setWalletLedgerFundScope(value)}
                  options={[
                    { label: "只看现金", value: "cash" },
                    { label: "只看赠金", value: "bonus" },
                  ]}
                />
                <Select
                  aria-label="wallet-ledger-sort-field"
                  style={{ width: 160 }}
                  value={walletLedgerSortField}
                  onChange={setWalletLedgerSortField}
                  options={walletLedgerSortFieldOptions}
                />
                <Select
                  aria-label="wallet-ledger-sort-order"
                  style={{ width: 140 }}
                  value={walletLedgerSortOrder}
                  onChange={(value) => setWalletLedgerSortOrder(value as SortOrder)}
                  options={sortOrderOptions}
                />
                <Button onClick={() => void loadWalletLedgers()}>刷新</Button>
                {renderExportAction("finance-wallet-ledgers", walletLedgerExportColumns, walletLedgerRows.map((row) => ({
                  id: row.id,
                  account_id: row.account_id ?? "",
                  user_id: row.user_id,
                  public_user_id: row.public_user_id ?? "",
                  direction: row.direction,
                  transaction_type: row.transaction_type,
                  source_type: row.source_type ?? "",
                  display_title: row.display_title ?? "",
                  amount: row.amount,
                  cash_amount: row.cash_amount,
                  bonus_amount: row.bonus_amount,
                  status: row.status,
                  balance_after: row.balance_after ?? "",
                  created_at: formatDateTime(row.created_at),
                })))}
              </Space>
              <Table
                rowKey="id"
                loading={walletLedgerLoading}
                dataSource={walletLedgerRows}
                columns={walletLedgerColumns}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: walletLedgerLoading ? <Spin size="small" /> : <Empty description="暂无钱包流水" /> }}
              />
            </Space>
          ),
        }]
      : []),
    ...(canViewFinanceReports
      ? [{
          key: "alerts",
          label: "异常告警",
          children: (
            <Space direction="vertical" size={16} style={{ width: "100%" }}>
              <Space>
                {renderExportAction("finance-anomaly-alerts", alertsExportColumns, alerts.map((row) => ({
                  type: row.type,
                  account_id: row.account_id ?? "",
                  user_id: row.user_id ?? "",
                  public_user_id: row.public_user_id ?? "",
                  amount: row.amount ?? "",
                  time: formatDateTime(row.time),
                  message: row.message,
                })))}
              </Space>
              <Table
                rowKey={(record) => record.record_id || `${record.type}-${record.user_id || "none"}-${record.time || "none"}`}
                loading={alertsLoading}
                dataSource={alerts}
                columns={alertColumns}
                pagination={{ pageSize: 10 }}
                locale={{ emptyText: alertsLoading ? <Spin size="small" /> : <Empty description="暂无异常告警" /> }}
              />
            </Space>
          ),
        }]
      : []),
  ];

  return (
    <PageShell
      title="财务管理"
      subtitle="真实充值、提现、赠金与异常告警统一汇总"
      actions={<Button onClick={refreshAll}>全部刷新</Button>}
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {pageError ? <Alert type="error" showIcon message={pageError} /> : null}
        {duplicateWithdrawalAlerts.length > 0 ? (
          <Alert
            type="warning"
            showIcon
            message={`检测到 ${duplicateWithdrawalAlerts.length} 条重复提现账户风险`}
            description={(
              <Space wrap>
                {duplicateWithdrawalAlerts.map((item) => (
                  <Space key={item.id} size={8}>
                    <Tag color="default">{item.account_no_masked || "未配置账户"}</Tag>
                    <Tag color="orange">{`重复账户 ${String(item.duplicate_account_count ?? 0)}人`}</Tag>
                  </Space>
                ))}
              </Space>
            )}
          />
        ) : null}
        <Tabs items={tabs} />

        <Modal
          title="新建赠金"
          open={bonusGrantModalOpen}
          onCancel={() => setBonusGrantModalOpen(false)}
          footer={null}
          destroyOnHidden
        >
          <Form form={bonusGrantForm} layout="vertical" initialValues={{ currency: "USD", sourceType: "admin_bonus" }}>
            <Form.Item label="账号 ID" name="accountId" rules={[{ required: true, message: "请输入账号 ID" }]}>
              <Input aria-label="bonus-grant-account-id" />
            </Form.Item>
            <Form.Item label="用户 ID" name="userId" rules={[{ required: true, message: "请输入用户 ID" }]}>
              <Input aria-label="bonus-grant-user-id" />
            </Form.Item>
            <Form.Item label="金额" name="amount" rules={[{ required: true, message: "请输入金额" }]}>
              <Input aria-label="bonus-grant-amount" inputMode="decimal" />
            </Form.Item>
            <Form.Item label="币种" name="currency">
              <Input aria-label="bonus-grant-currency" />
            </Form.Item>
            <Form.Item label="来源类型" name="sourceType">
              <Input aria-label="bonus-grant-source-type" />
            </Form.Item>
            <Form.Item label="原因" name="reason" rules={[{ required: true, message: "请输入原因" }]}>
              <Input aria-label="bonus-grant-reason" />
            </Form.Item>
            <Form.Item label="备注" name="remark">
              <Input.TextArea aria-label="bonus-grant-remark" rows={3} />
            </Form.Item>
            <Space style={{ width: "100%", justifyContent: "flex-end" }}>
              <Button onClick={() => setBonusGrantModalOpen(false)}>取消</Button>
              <Button type="primary" aria-label="submit-bonus-grant" loading={actionLoading} onClick={() => { void handleCreateBonusGrant(); }}>
                提交
              </Button>
            </Space>
          </Form>
        </Modal>

        <Modal
          title="新建补单"
          open={rechargeRepairModalOpen}
          onCancel={() => setRechargeRepairModalOpen(false)}
          footer={null}
          destroyOnHidden
        >
          <Form
            form={rechargeRepairForm}
            layout="vertical"
            initialValues={{ currency: "USD", repairType: "manual_real_recharge" }}
          >
            <Form.Item label="账号 ID" name="accountId" rules={[{ required: true, message: "请输入账号 ID" }]}>
              <Input aria-label="recharge-repair-account-id" />
            </Form.Item>
            <Form.Item label="用户 ID" name="userId" rules={[{ required: true, message: "请输入用户 ID" }]}>
              <Input aria-label="recharge-repair-user-id" />
            </Form.Item>
            <Form.Item label="金额" name="amount" rules={[{ required: true, message: "请输入金额" }]}>
              <Input aria-label="recharge-repair-amount" inputMode="decimal" />
            </Form.Item>
            <Form.Item label="币种" name="currency">
              <Input aria-label="recharge-repair-currency" />
            </Form.Item>
            <Form.Item label="补单类型" name="repairType">
              <Input aria-label="recharge-repair-type" />
            </Form.Item>
            <Form.Item label="平台订单号" name="platformOrderNo">
              <Input aria-label="recharge-repair-platform-order-no" />
            </Form.Item>
            <Form.Item label="渠道订单号" name="channelOrderNo">
              <Input aria-label="recharge-repair-channel-order-no" />
            </Form.Item>
            <Form.Item label="渠道 ID" name="channelId">
              <Input aria-label="recharge-repair-channel-id" />
            </Form.Item>
            <Form.Item label="原因" name="reason" rules={[{ required: true, message: "请输入原因" }]}>
              <Input aria-label="recharge-repair-reason" />
            </Form.Item>
            <Form.Item label="备注" name="remark">
              <Input.TextArea aria-label="recharge-repair-remark" rows={3} />
            </Form.Item>
            <Space style={{ width: "100%", justifyContent: "flex-end" }}>
              <Button onClick={() => setRechargeRepairModalOpen(false)}>取消</Button>
              <Button
                type="primary"
                aria-label="submit-recharge-repair"
                loading={actionLoading}
                onClick={() => { void handleCreateRechargeRepair(); }}
              >
                提交
              </Button>
            </Space>
          </Form>
        </Modal>

        <Modal
          title={decisionTarget?.kind === "bonus" ? "驳回赠金" : "驳回补单"}
          open={decisionTarget !== null}
          onCancel={() => setDecisionTarget(null)}
          footer={null}
          destroyOnHidden
        >
          <Form form={decisionForm} layout="vertical">
            <Form.Item label="驳回原因" name="reason">
              <Input.TextArea aria-label="decision-reason" rows={4} />
            </Form.Item>
            <Space style={{ width: "100%", justifyContent: "flex-end" }}>
              <Button onClick={() => setDecisionTarget(null)}>取消</Button>
              <Button type="primary" danger aria-label="submit-decision" loading={actionLoading} onClick={() => { void handleSubmitDecision(); }}>
                确认驳回
              </Button>
            </Space>
          </Form>
        </Modal>
      </Space>
    </PageShell>
  );
}
