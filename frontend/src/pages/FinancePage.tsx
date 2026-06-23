import { useCallback, useMemo, useState, type JSX } from "react";
import { Alert, Button, Checkbox, DatePicker, Input, Modal, Select, Space, Table, Tag, Tabs, Typography, message } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined } from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { showSuccess, showError } from "../components/Feedback";
import { usePermissions } from "../hooks/usePermissions";

// ── Mock Data ──
const MOCK_DEPOSITS = Array.from({ length: 25 }, (_, i) => ({
  id: `d${i + 1}`,
  time: `2026-06-${String(11 - Math.floor(i / 3)).padStart(2, "0")} ${String(8 + i % 10).padStart(2, "0")}:${String(i * 3 % 60).padStart(2, "0")}`,
  member: ["张三", "李四", "王五", "赵六", "钱七"][i % 5],
  site: ["站点A", "站点B", "站点C"][i % 3],
  channel: ["USDT", "银行转账", "支付宝"][i % 3],
  currency: i % 2 === 0 ? "USDT" : "CNY",
  amount: [100, 200, 500, 1000, 2000][i % 5] + Math.floor(i * 10),
  rate: i % 2 === 0 ? 7.25 : 1,
  converted: i % 2 === 0 ? ([100, 200, 500, 1000, 2000][i % 5] + Math.floor(i * 10)) * 7.25 : [100, 200, 500, 1000, 2000][i % 5] + Math.floor(i * 10),
  status: ["success", "pending", "success", "success", "failed"][i % 5],
  is_first_deposit: i % 4 === 0,
}));

const MOCK_WITHDRAWALS = Array.from({ length: 22 }, (_, i) => ({
  id: `w${i + 1}`,
  time: `2026-06-${String(11 - Math.floor(i / 3)).padStart(2, "0")} ${String(8 + i % 10).padStart(2, "0")}:${String(i * 5 % 60).padStart(2, "0")}`,
  member: ["王五", "赵六", "钱七", "孙八", "周九"][i % 5],
  amount: [50, 100, 200, 500, 1000][i % 5] + Math.floor(i * 5),
  fee: [0.5, 1, 2, 5, 10][i % 5] + i * 0.1,
  actual: 0,
  status: ["pending", "approved", "frozen", "rejected", "pending"][i % 5],
}));
MOCK_WITHDRAWALS.forEach((w) => { w.actual = w.amount - w.fee; });

const MOCK_DAILY = [
  { date: "2026-06-09", deposit: 1500, deposit_cnt: 3, withdraw: 500, withdraw_cnt: 2, net: 1000, fee: 5 },
  { date: "2026-06-10", deposit: 3000, deposit_cnt: 5, withdraw: 1200, withdraw_cnt: 3, net: 1800, fee: 12 },
  { date: "2026-06-11", deposit: 500, deposit_cnt: 1, withdraw: 0, withdraw_cnt: 0, net: 500, fee: 0 },
];

const MOCK_CHANNEL_REPORT = [
  { channel: "USDT", deposit_count: 12, deposit_amount: 8500, withdraw_count: 5, withdraw_amount: 2000, success_rate: 98.5, avg_fee: 0.5 },
  { channel: "银行转账", deposit_count: 8, deposit_amount: 3500, withdraw_count: 3, withdraw_amount: 800, success_rate: 100, avg_fee: 1.0 },
  { channel: "支付宝", deposit_count: 5, deposit_amount: 1200, withdraw_count: 2, withdraw_amount: 300, success_rate: 95.0, avg_fee: 0.3 },
];

const MOCK_SYSTEM_USAGE = [
  { month: "2026-06", ai_msgs: 1860, ai_cost: 18.3, translate_count: 200, translate_cost: 0.6, total_cost: 18.9 },
  { month: "2026-05", ai_msgs: 1520, ai_cost: 15.2, translate_count: 180, translate_cost: 0.54, total_cost: 15.74 },
];

const MOCK_ALERTS = [
  { id: "a1", time: "2026-06-11 10:00", type: "large_deposit", member: "张三", detail: "单笔充值 ¥7,250（超过阈值 ¥5,000）", amount: 7250 },
  { id: "a2", time: "2026-06-11 09:30", type: "frequent_withdraw", member: "王五", detail: "24小时内提现 3 次", amount: 0 },
];

const MOCK_CALLBACKS = [
  { id: "c1", time: "2026-06-11 10:00", channel: "USDT", sig_ok: true, handled: true, retry: 0 },
  { id: "c2", time: "2026-06-11 09:00", channel: "银行转账", sig_ok: false, handled: false, retry: 3 },
];

type DepositRow = (typeof MOCK_DEPOSITS)[number];
type ChannelReportRow = (typeof MOCK_CHANNEL_REPORT)[number];
type SystemUsageRow = (typeof MOCK_SYSTEM_USAGE)[number];
type CallbackRow = (typeof MOCK_CALLBACKS)[number];

const statusMap: Record<string, { label: string; color: string }> = {
  success: { label: "成功", color: "green" }, pending: { label: "待处理", color: "orange" },
  frozen: { label: "已冻结", color: "blue" }, approved: { label: "已审批", color: "green" },
  rejected: { label: "已拒绝", color: "red" }, failed: { label: "失败", color: "red" },
};
const alertTypeMap: Record<string, string> = { large_deposit: "大额充值", frequent_withdraw: "频繁提现", abnormal_amount: "异常金额" };

// ── Simulated API call ──
async function mockApi(action: string): Promise<void> {
  await new Promise((r) => setTimeout(r, 600));
  if (Math.random() > 0.9) throw new Error("操作失败，请重试");
}

export function FinancePage(): JSX.Element {
  const { can } = usePermissions();
  const canViewRecharge = can("finance.view_recharge");
  const canViewWithdrawal = can("finance.view_withdrawal") || can("finance.approve_withdrawal");
  const canViewFinanceReports = can("reports.finance");
  const canViewChannels = can("finance.view_channels") || can("finance.edit_channels");
  const canViewCallbacks = can("finance.edit_channels");
  // ── Deposit state ──
  const [depositSearch, setDepositSearch] = useState("");
  const [depositSite, setDepositSite] = useState<string | undefined>();
  const [depositChannel, setDepositChannel] = useState<string | undefined>();
  const [depositStatus, setDepositStatus] = useState<string | undefined>();
  const [depositFirstOnly, setDepositFirstOnly] = useState(false);
  const [depositPage, setDepositPage] = useState(1);
  const [depositPageSize, setDepositPageSize] = useState(10);

  // ── Withdrawal state ──
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [withdrawSearch, setWithdrawSearch] = useState("");
  const [withdrawStatus, setWithdrawStatus] = useState<string | undefined>();
  const [withdrawPage, setWithdrawPage] = useState(1);
  const [withdrawPageSize, setWithdrawPageSize] = useState(10);
  const [actionLoading, setActionLoading] = useState(false);

  // ── Withdrawal action handlers ──
  const handleSingleAction = useCallback(async (action: string, id: string, member: string) => {
    const titles: Record<string, string> = { approve: "审批", reject: "拒绝", unfreeze: "解除冻结" };
    Modal.confirm({
      title: `确认${titles[action]})`,
      content: `确认${titles[action]}) ${member} 的提现申请？`,
      okButtonProps: action === "reject" ? { danger: true } : undefined,
      onOk: async () => {
        setActionLoading(true);
        try {
          await mockApi(action);
          showSuccess(`${titles[action]})成功`);
        } catch (e) { showError(e instanceof Error ? e.message : "操作失败"); }
        finally { setActionLoading(false); }
      },
    });
  }, []);

  const handleBatchAction = useCallback(async (action: "approve" | "reject") => {
    const titles: Record<string, string> = { approve: "审批", reject: "拒绝" };
    Modal.confirm({
      title: `批量${titles[action]})`,
      content: `确认批量${titles[action]}) ${selectedIds.length} 条提现申请？`,
      okButtonProps: action === "reject" ? { danger: true } : undefined,
      onOk: async () => {
        setActionLoading(true);
        try {
          await mockApi(action);
          showSuccess(`批量${titles[action]})成功`);
          setSelectedIds([]);
        } catch (e) { showError(e instanceof Error ? e.message : "操作失败"); }
        finally { setActionLoading(false); }
      },
    });
  }, [selectedIds]);

  // ── Filtered data ──
  const filteredDeposits = useMemo(() => {
    let data = MOCK_DEPOSITS;
    if (depositSearch) data = data.filter((r) => r.member.includes(depositSearch));
    if (depositSite) data = data.filter((r) => r.site === depositSite);
    if (depositChannel) data = data.filter((r) => r.channel === depositChannel);
    if (depositStatus) data = data.filter((r) => r.status === depositStatus);
    if (depositFirstOnly) data = data.filter((r) => r.is_first_deposit);
    return data;
  }, [depositSearch, depositSite, depositChannel, depositStatus, depositFirstOnly]);

  const filteredWithdrawals = useMemo(() => {
    let data = MOCK_WITHDRAWALS;
    if (withdrawSearch) data = data.filter((r) => r.member.includes(withdrawSearch));
    if (withdrawStatus) data = data.filter((r) => r.status === withdrawStatus);
    return data;
  }, [withdrawSearch, withdrawStatus]);

  const uniqueSites = useMemo(() => [...new Set(MOCK_DEPOSITS.map((r) => r.site))], []);
  const uniqueChannels = useMemo(() => [...new Set(MOCK_DEPOSITS.map((r) => r.channel))], []);

  // Deposit summary
  const depositSummary = useMemo(() => {
    const total = MOCK_DEPOSITS.reduce((s, r) => s + r.converted, 0);
    const count = MOCK_DEPOSITS.length;
    const firstCount = MOCK_DEPOSITS.filter((r) => r.is_first_deposit).length;
    return { total, count, firstCount };
  }, []);

  // Withdrawal summary
  const withdrawSummary = useMemo(() => {
    const total = MOCK_WITHDRAWALS.reduce((s, r) => s + r.amount, 0);
    const totalFee = MOCK_WITHDRAWALS.reduce((s, r) => s + r.fee, 0);
    const pendingCount = MOCK_WITHDRAWALS.filter((r) => r.status === "pending").length;
    const frozenCount = MOCK_WITHDRAWALS.filter((r) => r.status === "frozen").length;
    return { total, totalFee, pendingCount, frozenCount };
  }, []);

  // ── Columns ──
  const depositColumns = [
    { title: "时间", dataIndex: "time", key: "time", width: 140,
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.time ?? "").localeCompare(b.time ?? ""),
      defaultSortOrder: "descend" as const,
    },
    { title: "会员", dataIndex: "member", key: "member",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.member ?? "").localeCompare(b.member ?? ""),
    },
    { title: "站点", dataIndex: "site", key: "site",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.site ?? "").localeCompare(b.site ?? ""),
    },
    { title: "渠道", dataIndex: "channel", key: "channel",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.channel ?? "").localeCompare(b.channel ?? ""),
    },
    { title: "充值币种", dataIndex: "currency", key: "currency",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.currency ?? "").localeCompare(b.currency ?? ""),
    },
    { title: "金额", dataIndex: "amount", key: "amount",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.amount ?? 0) - (b.amount ?? 0),
    },
    { title: "汇率", dataIndex: "rate", key: "rate",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.rate ?? 0) - (b.rate ?? 0),
    },
    { title: "转换金额", dataIndex: "converted", key: "converted",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.converted ?? 0) - (b.converted ?? 0),
    },
    { title: "首充", key: "first", width: 60, sorter: (a: DepositRow, b: DepositRow) => (a.is_first_deposit ? 1 : 0) - (b.is_first_deposit ? 1 : 0),
      render: (_: unknown, r: typeof MOCK_DEPOSITS[0]) => r.is_first_deposit ? <Tag color="green">首充</Tag> : null,
    },
    { title: "状态", dataIndex: "status", key: "status",
      sorter: (a: typeof MOCK_DEPOSITS[0], b: typeof MOCK_DEPOSITS[0]) => (a.status ?? "").localeCompare(b.status ?? ""),
      render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.label || s}</Tag>,
    },
    { title: "操作", key: "actions", width: 80, render: () => <Button size="small">详情</Button> },
  ];

  // Withdrawal rowSelection
  const rowSelection = useMemo(() => ({
    selectedRowKeys: selectedIds,
    onChange: (keys: React.Key[]) => setSelectedIds(keys.map(String)),
    columnTitle: <Checkbox
      checked={filteredWithdrawals.length > 0 && filteredWithdrawals.every((r) => selectedIds.includes(r.id))}
      indeterminate={selectedIds.length > 0 && selectedIds.length < filteredWithdrawals.length}
      onChange={() => {
        const allIds = filteredWithdrawals.map((r) => r.id);
        if (selectedIds.length === filteredWithdrawals.length) setSelectedIds([]);
        else setSelectedIds(allIds);
      }}
    />,
  }), [selectedIds, filteredWithdrawals]);

  const withdrawColumns = [
    { title: "时间", dataIndex: "time", key: "time", width: 140,
      sorter: (a: typeof MOCK_WITHDRAWALS[0], b: typeof MOCK_WITHDRAWALS[0]) => (a.time ?? "").localeCompare(b.time ?? ""),
      defaultSortOrder: "descend" as const,
    },
    { title: "会员", dataIndex: "member", key: "member",
      sorter: (a: typeof MOCK_WITHDRAWALS[0], b: typeof MOCK_WITHDRAWALS[0]) => (a.member ?? "").localeCompare(b.member ?? ""),
    },
    { title: "金额", dataIndex: "amount", key: "amount",
      sorter: (a: typeof MOCK_WITHDRAWALS[0], b: typeof MOCK_WITHDRAWALS[0]) => (a.amount ?? 0) - (b.amount ?? 0),
    },
    { title: "手续费", dataIndex: "fee", key: "fee",
      sorter: (a: typeof MOCK_WITHDRAWALS[0], b: typeof MOCK_WITHDRAWALS[0]) => (a.fee ?? 0) - (b.fee ?? 0),
    },
    { title: "实到", dataIndex: "actual", key: "actual",
      sorter: (a: typeof MOCK_WITHDRAWALS[0], b: typeof MOCK_WITHDRAWALS[0]) => (a.actual ?? 0) - (b.actual ?? 0),
    },
    { title: "状态", dataIndex: "status", key: "status",
      sorter: (a: typeof MOCK_WITHDRAWALS[0], b: typeof MOCK_WITHDRAWALS[0]) => (a.status ?? "").localeCompare(b.status ?? ""),
      render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.label || s}</Tag>,
    },
    { title: "操作", key: "actions", width: 260, render: (_: unknown, r: typeof MOCK_WITHDRAWALS[0]) => (
      <Space>
        {r.status === "pending" && <><Button size="small" type="primary" loading={actionLoading} onClick={() => handleSingleAction("approve", r.id, r.member)}>审批</Button><Button size="small" danger loading={actionLoading} onClick={() => handleSingleAction("reject", r.id, r.member)}>拒绝</Button></>}
        {r.status === "frozen" && <Button size="small" loading={actionLoading} onClick={() => handleSingleAction("unfreeze", r.id, r.member)}>解除冻结</Button>}
      </Space>
    )},
  ];

  const dailyColumns = [
    { title: "日期", dataIndex: "date", key: "date",
      sorter: (a: typeof MOCK_DAILY[0], b: typeof MOCK_DAILY[0]) => (a.date ?? "").localeCompare(b.date ?? ""),
      defaultSortOrder: "descend" as const,
    },
    { title: "充值金额", dataIndex: "deposit", key: "deposit",
      sorter: (a: typeof MOCK_DAILY[0], b: typeof MOCK_DAILY[0]) => (a.deposit ?? 0) - (b.deposit ?? 0),
    },
    { title: "充值笔数", dataIndex: "deposit_cnt", key: "deposit_cnt",
      sorter: (a: typeof MOCK_DAILY[0], b: typeof MOCK_DAILY[0]) => (a.deposit_cnt ?? 0) - (b.deposit_cnt ?? 0),
    },
    { title: "提现金额", dataIndex: "withdraw", key: "withdraw",
      sorter: (a: typeof MOCK_DAILY[0], b: typeof MOCK_DAILY[0]) => (a.withdraw ?? 0) - (b.withdraw ?? 0),
    },
    { title: "提现笔数", dataIndex: "withdraw_cnt", key: "withdraw_cnt",
      sorter: (a: typeof MOCK_DAILY[0], b: typeof MOCK_DAILY[0]) => (a.withdraw_cnt ?? 0) - (b.withdraw_cnt ?? 0),
    },
    { title: "净充值", dataIndex: "net", key: "net",
      sorter: (a: typeof MOCK_DAILY[0], b: typeof MOCK_DAILY[0]) => (a.net ?? 0) - (b.net ?? 0),
      render: (v: number) => <Typography.Text strong>{v}</Typography.Text>,
    },
    { title: "手续费", dataIndex: "fee", key: "fee",
      sorter: (a: typeof MOCK_DAILY[0], b: typeof MOCK_DAILY[0]) => (a.fee ?? 0) - (b.fee ?? 0),
    },
  ];

  const channelColumns = [
    { title: "渠道", dataIndex: "channel", key: "channel",
      sorter: (a: typeof MOCK_CHANNEL_REPORT[0], b: typeof MOCK_CHANNEL_REPORT[0]) => (a.channel ?? "").localeCompare(b.channel ?? ""),
    },
    { title: "充值笔数", dataIndex: "deposit_count", key: "deposit_count", sorter: (a: ChannelReportRow, b: ChannelReportRow) => (a.deposit_count ?? 0) - (b.deposit_count ?? 0) },
    { title: "充值金额", dataIndex: "deposit_amount", key: "deposit_amount", sorter: (a: ChannelReportRow, b: ChannelReportRow) => (a.deposit_amount ?? 0) - (b.deposit_amount ?? 0) },
    { title: "提现笔数", dataIndex: "withdraw_count", key: "withdraw_count", sorter: (a: ChannelReportRow, b: ChannelReportRow) => (a.withdraw_count ?? 0) - (b.withdraw_count ?? 0) },
    { title: "提现金额", dataIndex: "withdraw_amount", key: "withdraw_amount", sorter: (a: ChannelReportRow, b: ChannelReportRow) => (a.withdraw_amount ?? 0) - (b.withdraw_amount ?? 0) },
    { title: "成功率", dataIndex: "success_rate", key: "success_rate", sorter: (a: ChannelReportRow, b: ChannelReportRow) => (a.success_rate ?? 0) - (b.success_rate ?? 0),
      render: (v: number) => `${v}%` },
    { title: "平均手续费", dataIndex: "avg_fee", key: "avg_fee", sorter: (a: ChannelReportRow, b: ChannelReportRow) => (a.avg_fee ?? 0) - (b.avg_fee ?? 0),
      render: (v: number) => `¥${v.toFixed(2)}` },
  ];

  const usageColumns = [
    { title: "月份", dataIndex: "month", key: "month",
      sorter: (a: typeof MOCK_SYSTEM_USAGE[0], b: typeof MOCK_SYSTEM_USAGE[0]) => (a.month ?? "").localeCompare(b.month ?? ""),
      defaultSortOrder: "descend" as const,
    },
    { title: "AI消息数", dataIndex: "ai_msgs", key: "ai_msgs", sorter: (a: SystemUsageRow, b: SystemUsageRow) => (a.ai_msgs ?? 0) - (b.ai_msgs ?? 0) },
    { title: "AI费用", dataIndex: "ai_cost", key: "ai_cost", sorter: (a: SystemUsageRow, b: SystemUsageRow) => (a.ai_cost ?? 0) - (b.ai_cost ?? 0),
      render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "翻译次数", dataIndex: "translate_count", key: "translate_count", sorter: (a: SystemUsageRow, b: SystemUsageRow) => (a.translate_count ?? 0) - (b.translate_count ?? 0) },
    { title: "翻译费用", dataIndex: "translate_cost", key: "translate_cost", sorter: (a: SystemUsageRow, b: SystemUsageRow) => (a.translate_cost ?? 0) - (b.translate_cost ?? 0),
      render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "总费用", dataIndex: "total_cost", key: "total_cost", sorter: (a: SystemUsageRow, b: SystemUsageRow) => (a.total_cost ?? 0) - (b.total_cost ?? 0),
      render: (v: number) => <Typography.Text strong>¥{v.toFixed(2)}</Typography.Text> },
  ];

  const alertColumns = [
    { title: "时间", dataIndex: "time", key: "time",
      sorter: (a: typeof MOCK_ALERTS[0], b: typeof MOCK_ALERTS[0]) => (a.time ?? "").localeCompare(b.time ?? ""),
      defaultSortOrder: "descend" as const,
    },
    { title: "类型", dataIndex: "type", key: "type",
      sorter: (a: typeof MOCK_ALERTS[0], b: typeof MOCK_ALERTS[0]) => (a.type ?? "").localeCompare(b.type ?? ""),
      render: (t: string) => <Tag color="red">{alertTypeMap[t] || t}</Tag>,
    },
    { title: "会员", dataIndex: "member", key: "member",
      sorter: (a: typeof MOCK_ALERTS[0], b: typeof MOCK_ALERTS[0]) => (a.member ?? "").localeCompare(b.member ?? ""),
    },
    { title: "详情", dataIndex: "detail", key: "detail" },
    { title: "金额", dataIndex: "amount", key: "amount",
      sorter: (a: typeof MOCK_ALERTS[0], b: typeof MOCK_ALERTS[0]) => (a.amount ?? 0) - (b.amount ?? 0),
    },
  ];

  const callbackColumns = [
    { title: "时间", dataIndex: "time", key: "time",
      sorter: (a: typeof MOCK_CALLBACKS[0], b: typeof MOCK_CALLBACKS[0]) => (a.time ?? "").localeCompare(b.time ?? ""),
      defaultSortOrder: "descend" as const,
    },
    { title: "渠道", dataIndex: "channel", key: "channel",
      sorter: (a: typeof MOCK_CALLBACKS[0], b: typeof MOCK_CALLBACKS[0]) => (a.channel ?? "").localeCompare(b.channel ?? ""),
    },
    { title: "签名验证", dataIndex: "sig_ok", key: "sig_ok", sorter: (a: CallbackRow, b: CallbackRow) => (a.sig_ok === b.sig_ok ? 0 : a.sig_ok ? 1 : -1),
      render: (v: boolean) => v ? <Tag icon={<CheckCircleOutlined />} color="success">✓</Tag> : <Tag icon={<CloseCircleOutlined />} color="error">✗</Tag>,
    },
    { title: "已处理", dataIndex: "handled", key: "handled", sorter: (a: CallbackRow, b: CallbackRow) => (a.handled === b.handled ? 0 : a.handled ? 1 : -1),
      render: (v: boolean) => v ? <Tag color="green">✓</Tag> : <Tag color="orange">✗</Tag>,
    },
    { title: "重试次数", dataIndex: "retry", key: "retry", sorter: (a: CallbackRow, b: CallbackRow) => (a.retry ?? 0) - (b.retry ?? 0) },
    { title: "操作", key: "actions", width: 100, render: () => <Button size="small" icon={<ReloadOutlined />}>重试</Button> },
  ];

  const statCardStyle: React.CSSProperties = { background: "#fafafa", borderRadius: 8, padding: "12px 20px", textAlign: "center", minWidth: 130 };

  const tabItems = [
    ...(canViewRecharge ? [{ key: "deposits", label: "充值记录", children: (
      <>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input.Search placeholder="搜索会员" style={{ width: 160 }} value={depositSearch} onSearch={(v) => setDepositSearch(v)} onChange={(e) => { if (!e.target.value) setDepositSearch(""); }} />
          <Select placeholder="站点" allowClear style={{ width: 120 }} value={depositSite} onChange={setDepositSite} options={uniqueSites.map((s) => ({ label: s, value: s }))} />
          <Select placeholder="渠道" allowClear style={{ width: 120 }} value={depositChannel} onChange={setDepositChannel} options={uniqueChannels.map((c) => ({ label: c, value: c }))} />
          <Select placeholder="状态" allowClear style={{ width: 120 }} value={depositStatus} onChange={setDepositStatus} options={Object.entries(statusMap).map(([k, v]) => ({ label: v.label, value: k }))} />
          <DatePicker placeholder="开始日期" />
          <DatePicker placeholder="结束日期" />
          <Checkbox checked={depositFirstOnly} onChange={(e) => setDepositFirstOnly(e.target.checked)}>首充用户</Checkbox>
        </Space>
        <Table rowKey="id" dataSource={filteredDeposits} columns={depositColumns}
          pagination={{ current: depositPage, onChange: setDepositPage, pageSize: depositPageSize, onShowSizeChange: (_c, s) => { setDepositPageSize(s); setDepositPage(1); }, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        />
        <Space style={{ marginTop: 16 }} wrap>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>充值总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥{depositSummary.total.toFixed(2)}</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>总笔数</div><div style={{ fontSize: 22, fontWeight: 600 }}>{depositSummary.count}</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>首充用户</div><div style={{ fontSize: 22, fontWeight: 600, color: "#52c41a" }}>{depositSummary.firstCount}</div></div>
        </Space>
      </>
    )}] : []),
    ...(canViewWithdrawal ? [{ key: "withdrawals", label: "提现记录", children: (
      <>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input.Search placeholder="搜索会员" style={{ width: 160 }} value={withdrawSearch} onSearch={(v) => setWithdrawSearch(v)} onChange={(e) => { if (!e.target.value) setWithdrawSearch(""); }} />
          <Select placeholder="状态" allowClear style={{ width: 120 }} value={withdrawStatus} onChange={setWithdrawStatus} options={Object.entries(statusMap).map(([k, v]) => ({ label: v.label, value: k }))} />
          <DatePicker placeholder="开始日期" />
          <DatePicker placeholder="结束日期" />
          {selectedIds.length > 0 && <><Button type="primary" loading={actionLoading} onClick={() => handleBatchAction("approve")}>批量审批</Button><Button danger loading={actionLoading} onClick={() => handleBatchAction("reject")}>批量拒绝</Button></>}
        </Space>
        <Table rowKey="id" dataSource={filteredWithdrawals} columns={withdrawColumns}
          rowSelection={rowSelection}
          pagination={{ current: withdrawPage, onChange: setWithdrawPage, pageSize: withdrawPageSize, onShowSizeChange: (_c, s) => { setWithdrawPageSize(s); setWithdrawPage(1); }, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        />
        <Space style={{ marginTop: 16 }} wrap>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>提现总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥{withdrawSummary.total.toFixed(2)}</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>手续费收入</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥{withdrawSummary.totalFee.toFixed(2)}</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>待审批</div><div style={{ fontSize: 22, fontWeight: 600, color: "#faad14" }}>{withdrawSummary.pendingCount}</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>冻结</div><div style={{ fontSize: 22, fontWeight: 600, color: "#1677ff" }}>{withdrawSummary.frozenCount}</div></div>
        </Space>
      </>
    )}] : []),
    ...(canViewFinanceReports ? [{ key: "reports", label: "财务报表", children: (
      <>
        <Space style={{ marginBottom: 16 }} wrap>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>充值总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥5,000</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>充值笔数</div><div style={{ fontSize: 22, fontWeight: 600 }}>9</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>提现总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥1,700</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>提现笔数</div><div style={{ fontSize: 22, fontWeight: 600 }}>5</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>净充值</div><div style={{ fontSize: 22, fontWeight: 600, color: "#52c41a" }}>¥3,300</div></div>
          <div style={statCardStyle}><div style={{ fontSize: 13, color: "#8c8c8c" }}>手续费收入</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥17</div></div>
        </Space>
        <Table rowKey="date" dataSource={MOCK_DAILY} columns={dailyColumns} pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }} />
      </>
    )}] : []),
    ...(canViewChannels ? [{
      key: "channels", label: "渠道报表", children: (
        <>
          <Typography.Title level={5}>各渠道充提统计</Typography.Title>
          <Table rowKey="channel" dataSource={MOCK_CHANNEL_REPORT} columns={channelColumns} pagination={false} style={{ marginBottom: 24 }} />
          <Typography.Title level={5}>系统使用费用（AI / 翻译）</Typography.Title>
          <Table rowKey="month" dataSource={MOCK_SYSTEM_USAGE} columns={usageColumns} pagination={false} />
        </>
      )
    }] : []),
    ...((canViewFinanceReports || canViewWithdrawal) ? [{ key: "alerts", label: "异常告警", children: (
      <><Alert message="系统自动监控异常交易。大额充值、频繁提现、异常金额会在这里显示。" type="info" showIcon style={{ marginBottom: 16 }} /><Table rowKey="id" dataSource={MOCK_ALERTS} columns={alertColumns} pagination={false} /></>
    )}] : []),
    ...(canViewCallbacks ? [{
      key: "callbacks", label: "回调管理", children: (
        <><Table rowKey="id" dataSource={MOCK_CALLBACKS} columns={callbackColumns} pagination={false} /></>
      )
    }] : []),
  ];

  return (
    <PageShell title="财务管理" subtitle="查看充值提现记录和财务报表">
      <Tabs items={tabItems} />
    </PageShell>
  );
}
