import { useCallback, useMemo, useState, type JSX } from "react";
import { Alert, Button, Checkbox, DatePicker, Input, Modal, Select, Space, Table, Tag, Tabs, Typography, message } from "antd";
import { withSorter } from "../../utils/withSorter";
import { PageShell } from "../../components/PageShell";
import { showSuccess, showError } from "../../components/Feedback";

// ── Mock Data ──
const MOCK_DEPOSITS = Array.from({ length: 28 }, (_, i) => ({
  id: `d${i + 1}`,
  time: `2026-06-${String(12 - Math.floor(i / 3)).padStart(2, "0")} ${String(8 + i % 10).padStart(2, "0")}:${String(i * 3 % 60).padStart(2, "0")}`,
  member: ["张三", "李四", "王五", "赵六", "钱七"][i % 5],
  site: ["站点A", "站点B", "站点C"][i % 3],
  channel: ["USDT", "银行转账", "支付宝"][i % 3],
  currency: i % 2 === 0 ? "USDT" : "CNY",
  amount: [100, 200, 500, 1000, 2000][i % 5] + Math.floor(i * 10),
  converted: 0,
  status: ["success", "pending", "success", "success", "failed"][i % 5],
  is_first_deposit: i % 4 === 0,
}));
MOCK_DEPOSITS.forEach((r) => { r.converted = r.currency === "USDT" ? r.amount * 7.25 : r.amount; });

const MOCK_WITHDRAWALS = Array.from({ length: 24 }, (_, i) => ({
  id: `w${i + 1}`,
  time: `2026-06-${String(12 - Math.floor(i / 3)).padStart(2, "0")} ${String(8 + i % 10).padStart(2, "0")}:${String(i * 5 % 60).padStart(2, "0")}`,
  member: ["王五", "赵六", "钱七", "孙八", "周九"][i % 5],
  amount: [50, 100, 200, 500, 1000][i % 5] + Math.floor(i * 5),
  fee: [0.5, 1, 2, 5, 10][i % 5] + i * 0.1,
  actual: 0,
  status: ["pending", "approved", "frozen", "rejected", "pending", "pending"][i % 6],
}));
MOCK_WITHDRAWALS.forEach((w) => { w.actual = w.amount - w.fee; });

const MOCK_DAILY = [
  { date: "2026-06-09", deposit: 1500, deposit_cnt: 3, withdraw: 500, withdraw_cnt: 2, net: 1000, fee: 5 },
  { date: "2026-06-10", deposit: 3000, deposit_cnt: 5, withdraw: 1200, withdraw_cnt: 3, net: 1800, fee: 12 },
  { date: "2026-06-11", deposit: 500, deposit_cnt: 1, withdraw: 0, withdraw_cnt: 0, net: 500, fee: 0 },
  { date: "2026-06-12", deposit: 2000, deposit_cnt: 4, withdraw: 800, withdraw_cnt: 2, net: 1200, fee: 8 },
];

const MOCK_CHANNEL_REPORT = [
  { channel: "USDT", deposit_count: 12, deposit_amount: 8500, withdraw_count: 5, withdraw_amount: 2000, success_rate: 98.5, avg_fee: 0.5 },
  { channel: "银行转账", deposit_count: 8, deposit_amount: 3500, withdraw_count: 3, withdraw_amount: 800, success_rate: 100, avg_fee: 1.0 },
  { channel: "支付宝", deposit_count: 5, deposit_amount: 1200, withdraw_count: 2, withdraw_amount: 300, success_rate: 95.0, avg_fee: 0.3 },
];

const statusMap: Record<string, { label: string; color: string }> = {
  success: { label: "成功", color: "green" }, pending: { label: "待处理", color: "orange" },
  frozen: { label: "已冻结", color: "blue" }, approved: { label: "已审批", color: "green" },
  rejected: { label: "已拒绝", color: "red" }, failed: { label: "失败", color: "red" },
};

async function mockApi(_action: string): Promise<void> {
  await new Promise((r) => setTimeout(r, 600));
  if (Math.random() > 0.9) throw new Error("操作失败，请重试");
}

export function AgentFinancePage(): JSX.Element {
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

  // ── Handlers ──
  const handleSingleAction = useCallback(async (action: string, id: string, member: string) => {
    const titles: Record<string, string> = { approve: "审批", reject: "拒绝", unfreeze: "解除冻结" };
    Modal.confirm({
      title: `确认${titles[action]}`,
      content: `确认${titles[action]} ${member} 的提现申请？`,
      okButtonProps: action === "reject" ? { danger: true } : undefined,
      onOk: async () => {
        setActionLoading(true);
        try { await mockApi(action); showSuccess(`${titles[action]}成功`); }
        catch (e) { showError(e instanceof Error ? e.message : "操作失败"); }
        finally { setActionLoading(false); }
      },
    });
  }, []);

  const handleBatchAction = useCallback(async (action: "approve" | "reject") => {
    const titles: Record<string, string> = { approve: "审批", reject: "拒绝" };
    Modal.confirm({
      title: `批量${titles[action]}`,
      content: `确认批量${titles[action]} ${selectedIds.length} 条提现申请？`,
      okButtonProps: action === "reject" ? { danger: true } : undefined,
      onOk: async () => {
        setActionLoading(true);
        try { await mockApi(action); showSuccess(`批量${titles[action]}成功`); setSelectedIds([]); }
        catch (e) { showError(e instanceof Error ? e.message : "操作失败"); }
        finally { setActionLoading(false); }
      },
    });
  }, [selectedIds]);

  // ── Filters ──
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

  // ── Summaries ──
  const depositSummary = useMemo(() => {
    const total = MOCK_DEPOSITS.reduce((s, r) => s + r.converted, 0);
    const count = MOCK_DEPOSITS.length;
    const firstCount = MOCK_DEPOSITS.filter((r) => r.is_first_deposit).length;
    return { total, count, firstCount };
  }, []);

  const withdrawSummary = useMemo(() => {
    const total = MOCK_WITHDRAWALS.reduce((s, r) => s + r.amount, 0);
    const totalFee = MOCK_WITHDRAWALS.reduce((s, r) => s + r.fee, 0);
    const pendingCount = MOCK_WITHDRAWALS.filter((r) => r.status === "pending").length;
    const frozenCount = MOCK_WITHDRAWALS.filter((r) => r.status === "frozen").length;
    return { total, totalFee, pendingCount, frozenCount };
  }, []);

  // ── Row selection ──
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

  const sCard: React.CSSProperties = { background: "#fafafa", borderRadius: 8, padding: "12px 20px", textAlign: "center", minWidth: 130 };

  return (
    <PageShell title="财务管理" subtitle="站点充值提现管理">
      <Tabs items={[
        { key: "deposits", label: "充值记录", children: (
          <>
            <Alert message="查看您站点下所有会员的充值记录。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Space style={{ marginBottom: 16 }} wrap>
              <Input.Search placeholder="搜索会员" style={{ width: 160 }} value={depositSearch} onSearch={(v) => setDepositSearch(v)} onChange={(e) => { if (!e.target.value) setDepositSearch(""); }} />
              <Select placeholder="站点" allowClear style={{ width: 120 }} value={depositSite} onChange={setDepositSite} options={uniqueSites.map((s) => ({ label: s, value: s }))} />
              <Select placeholder="渠道" allowClear style={{ width: 120 }} value={depositChannel} onChange={setDepositChannel} options={uniqueChannels.map((c) => ({ label: c, value: c }))} />
              <Select placeholder="状态" allowClear style={{ width: 120 }} value={depositStatus} onChange={setDepositStatus} options={Object.entries(statusMap).map(([k, v]) => ({ label: v.label, value: k }))} />
              <DatePicker placeholder="开始日期" />
              <DatePicker placeholder="结束日期" />
              <Checkbox checked={depositFirstOnly} onChange={(e) => setDepositFirstOnly(e.target.checked)}>首充用户</Checkbox>
            </Space>
            <Table rowKey="id" dataSource={filteredDeposits} columns={[
              { title: "时间", dataIndex: "time", key: "time", width: 140 },
              { title: "会员", dataIndex: "member", key: "member" },
              { title: "站点", dataIndex: "site", key: "site" },
              { title: "渠道", dataIndex: "channel", key: "channel" },
              { title: "充值币种", dataIndex: "currency", key: "currency" },
              { title: "金额", dataIndex: "amount", key: "amount" },
              { title: "转换金额", dataIndex: "converted", key: "converted" },
              { title: "首充", key: "first", width: 60, render: (_: unknown, r: typeof MOCK_DEPOSITS[0]) => r.is_first_deposit ? <Tag color="green">首充</Tag> : null },
              { title: "状态", dataIndex: "status", key: "status", render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.label || s}</Tag> },
            ]} pagination={{ current: depositPage, onChange: setDepositPage, pageSize: depositPageSize, onShowSizeChange: (_c, s) => { setDepositPageSize(s); setDepositPage(1); }, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }} />
            <Space style={{ marginTop: 16 }} wrap>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>充值总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥{depositSummary.total.toFixed(2)}</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>总笔数</div><div style={{ fontSize: 22, fontWeight: 600 }}>{depositSummary.count}</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>首充用户</div><div style={{ fontSize: 22, fontWeight: 600, color: "#52c41a" }}>{depositSummary.firstCount}</div></div>
            </Space>
          </>
        )},
        { key: "withdrawals", label: "提现审批", children: (
          <>
            <Alert message="审批您站点下会员的提现申请。小额提现系统会自动审批，大额需要您手动处理。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Space style={{ marginBottom: 16 }} wrap>
              <Input.Search placeholder="搜索会员" style={{ width: 160 }} value={withdrawSearch} onSearch={(v) => setWithdrawSearch(v)} onChange={(e) => { if (!e.target.value) setWithdrawSearch(""); }} />
              <Select placeholder="状态" allowClear style={{ width: 120 }} value={withdrawStatus} onChange={setWithdrawStatus} options={Object.entries(statusMap).map(([k, v]) => ({ label: v.label, value: k }))} />
              <DatePicker placeholder="开始日期" />
              <DatePicker placeholder="结束日期" />
              {selectedIds.length > 0 && <><Button type="primary" loading={actionLoading} onClick={() => handleBatchAction("approve")}>批量审批</Button><Button danger loading={actionLoading} onClick={() => handleBatchAction("reject")}>批量拒绝</Button></>}
            </Space>
            <Table rowKey="id" dataSource={filteredWithdrawals} rowSelection={rowSelection}
              columns={[
                { title: "时间", dataIndex: "time", key: "time", width: 140 },
                { title: "会员", dataIndex: "member", key: "member" },
                { title: "金额", dataIndex: "amount", key: "amount" },
                { title: "手续费", dataIndex: "fee", key: "fee" },
                { title: "实到", dataIndex: "actual", key: "actual" },
                { title: "状态", dataIndex: "status", key: "status", render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.label || s}</Tag> },
                { title: "操作", key: "actions", width: 260, render: (_: unknown, r: typeof MOCK_WITHDRAWALS[0]) => (
                  <Space>
                    {r.status === "pending" && <><Button size="small" type="primary" loading={actionLoading} onClick={() => handleSingleAction("approve", r.id, r.member)}>审批</Button><Button size="small" danger loading={actionLoading} onClick={() => handleSingleAction("reject", r.id, r.member)}>拒绝</Button></>}
                    {r.status === "frozen" && <Button size="small" loading={actionLoading} onClick={() => handleSingleAction("unfreeze", r.id, r.member)}>解除冻结</Button>}
                  </Space>
                )},
              ]}
              pagination={{ current: withdrawPage, onChange: setWithdrawPage, pageSize: withdrawPageSize, onShowSizeChange: (_c, s) => { setWithdrawPageSize(s); setWithdrawPage(1); }, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }} />
            <Space style={{ marginTop: 16 }} wrap>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>提现总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥{withdrawSummary.total.toFixed(2)}</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>手续费收入</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥{withdrawSummary.totalFee.toFixed(2)}</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>待审批</div><div style={{ fontSize: 22, fontWeight: 600, color: "#faad14" }}>{withdrawSummary.pendingCount}</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>冻结</div><div style={{ fontSize: 22, fontWeight: 600, color: "#1677ff" }}>{withdrawSummary.frozenCount}</div></div>
            </Space>
          </>
        )},
        { key: "reports", label: "财务报表", children: (
          <>
            <Alert message="查看您站点的充值和提现汇总数据。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Space style={{ marginBottom: 16 }} wrap>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>充值总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥7,000</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>提现总额</div><div style={{ fontSize: 22, fontWeight: 600 }}>¥2,500</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>净充值</div><div style={{ fontSize: 22, fontWeight: 600, color: "#52c41a" }}>¥4,500</div></div>
              <div style={sCard}><div style={{ fontSize: 13, color: "#8c8c8c" }}>待审批提现</div><div style={{ fontSize: 22, fontWeight: 600, color: "#faad14" }}>{withdrawSummary.pendingCount} 笔</div></div>
            </Space>
            <Table rowKey="date" dataSource={MOCK_DAILY} pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }} columns={[
              { title: "日期", dataIndex: "date", key: "date" }, { title: "充值金额", dataIndex: "deposit", key: "deposit" },
              { title: "充值笔数", dataIndex: "deposit_cnt", key: "deposit_cnt" }, { title: "提现金额", dataIndex: "withdraw", key: "withdraw" },
              { title: "提现笔数", dataIndex: "withdraw_cnt", key: "withdraw_cnt" }, { title: "净充值", dataIndex: "net", key: "net", render: (v: number) => <Typography.Text strong>{v}</Typography.Text> },
              { title: "手续费", dataIndex: "fee", key: "fee" },
            ]} />
          </>
        )},
        { key: "channels", label: "渠道报表", children: (
          <>
            <Alert message="各支付渠道的充提统计概览。" type="info" showIcon style={{ marginBottom: 16 }} />
            <Table rowKey="channel" dataSource={MOCK_CHANNEL_REPORT} columns={[
              { title: "渠道", dataIndex: "channel", key: "channel" },
              { title: "充值笔数", dataIndex: "deposit_count", key: "deposit_count" },
              { title: "充值金额", dataIndex: "deposit_amount", key: "deposit_amount" },
              { title: "提现笔数", dataIndex: "withdraw_count", key: "withdraw_count" },
              { title: "提现金额", dataIndex: "withdraw_amount", key: "withdraw_amount" },
              { title: "成功率", dataIndex: "success_rate", key: "success_rate", render: (v: number) => `${v}%` },
              { title: "平均手续费", dataIndex: "avg_fee", key: "avg_fee", render: (v: number) => `¥${v.toFixed(2)}` },
            ]} pagination={false} />
          </>
        )},
      ]} />
    </PageShell>
  );
}
