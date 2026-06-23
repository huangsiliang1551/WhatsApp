import { useCallback, useMemo, useState, type JSX } from "react";
import { Button, Select, Spin, Typography, Space, Tag, Dropdown } from "antd";
import { PlusOutlined, UserAddOutlined } from "@ant-design/icons";
import { usePageData } from "../../hooks/usePageData";
import { EmptyGuide } from "../../components/PageShell";
import { listMetaAccounts } from "../../services/api";
import type { MetaWabaAccount } from "../../services/api";
import { AccountListTab } from "./AccountListTab";
import { AccountDetailPanel } from "./AccountDetailPanel";
import { CreateManualModal } from "./CreateManualModal";
import { CreateSignupModal } from "./CreateSignupModal";

interface PageData {
  accounts: MetaWabaAccount[];
}

export function MetaAccountsPage(): JSX.Element {
  const [selectedWabaKey, setSelectedWabaKey] = useState<string | null>(null);
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [signupModalOpen, setSignupModalOpen] = useState(false);
  const [editingAccount, setEditingAccount] = useState<MetaWabaAccount | null>(null);
  const [filterMode, setFilterMode] = useState<string>("");
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const fetchData = useCallback(async (): Promise<PageData> => {
    const accs = await listMetaAccounts().catch(() => [] as MetaWabaAccount[]);
    return { accounts: accs };
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const accounts = data?.accounts ?? [];

  const selectedAccount = useMemo(() => {
    if (!selectedWabaKey) return null;
    return accounts.find((a) => `${a.account_id}:${a.waba_id}` === selectedWabaKey) ?? null;
  }, [accounts, selectedWabaKey]);

  const filtered = useMemo(() => {
    let result = accounts;
    if (filterMode) result = result.filter((a) => a.onboarding_mode === filterMode);
    if (statusFilter !== "all") {
      result = result.filter((a) => {
        const allOk = a.has_access_token && a.webhook_runtime_status === "healthy" && a.is_active && a.account_is_active;
        const disabled = !a.is_active || !a.account_is_active;
        const hasBlock = a.blocking_reasons.length > 0;
        const noToken = !a.has_access_token;
        if (statusFilter === "green") return allOk && !disabled && !hasBlock && !noToken;
        if (statusFilter === "yellow") return !disabled && !hasBlock && (!a.has_access_token || a.webhook_runtime_status !== "healthy" || a.registered_phone_number_count < a.phone_number_count);
        if (statusFilter === "red") return disabled || hasBlock;
        if (statusFilter === "gray") return noToken;
        return true;
      });
    }
    return result;
  }, [accounts, filterMode, statusFilter]);

  /* ---- stats ---- */
  const stats = useMemo(() => {
    let green = 0, yellow = 0, red = 0, gray = 0;
    for (const a of accounts) {
      const allOk = a.has_access_token && a.webhook_runtime_status === "healthy" && a.is_active && a.account_is_active;
      const disabled = !a.is_active || !a.account_is_active;
      const hasBlock = a.blocking_reasons.length > 0;
      const noToken = !a.has_access_token;
      if (disabled || hasBlock) red++;
      else if (noToken) gray++;
      else if (allOk && a.registered_phone_number_count === a.phone_number_count) green++;
      else yellow++;
    }
    return { green, yellow, red, gray };
  }, [accounts]);

  const handleRefresh = useCallback(() => { void reload(); }, [reload]);
  const handleSignupCreated = useCallback(() => { setSignupModalOpen(false); void reload(); }, [reload]);
  const handleAccountEditSaved = useCallback(() => { setManualModalOpen(false); setEditingAccount(null); void reload(); }, [reload]);
  const openEditModal = useCallback((account: MetaWabaAccount) => { setEditingAccount(account); setManualModalOpen(true); }, []);
  const handleDeleted = useCallback(() => { setSelectedWabaKey(null); void reload(); }, [reload]);

  const isEmpty = accounts.length === 0 && !loading;

  const statClick = (key: string) => {
    setStatusFilter((prev) => prev === key ? "all" : key);
  };

  const addMenuItems = [
    { key: "manual", icon: <PlusOutlined />, label: "手动添加 — 填写 WABA ID + Access Token", onClick: () => setManualModalOpen(true) },
    { key: "signup", icon: <UserAddOutlined />, label: "Embedded Signup — 一键授权接入", onClick: () => setSignupModalOpen(true) },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", padding: 12 }}>
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 8, fontSize: 12 }}>{error}</Typography.Text>}
      {loading && !data && <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}><Spin /></div>}

      {/* Empty state */}
      {isEmpty && (
        <EmptyGuide
          icon="📡"
          title="尚未接入 WhatsApp Business 账户"
          description="接入后可管理 WABA、号码、Webhook，支持多账户并存和 AI 托管"
          actions={[
            { label: "📋 手动添加", onClick: () => setManualModalOpen(true) },
            { label: "🔗 Embedded Signup", onClick: () => setSignupModalOpen(true) },
          ]}
        />
      )}

      {!isEmpty && data && (
        <>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
            本地已就绪 / 本地就绪 / 可正式激活 / 根路由冲突
          </Typography.Paragraph>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
            本地前置条件已齐，但根 Webhook 路由冲突仍阻塞正式激活。
          </Typography.Paragraph>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
            当前仅表示本地 Webhook 和出站前置条件已齐；正式激活仍以 Launch Readiness 为准。
          </Typography.Paragraph>

          {/* Status bar */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexShrink: 0, fontSize: 12, flexWrap: "wrap" }}>
            <Tag color="success" style={{ cursor: "pointer", opacity: statusFilter === "green" ? 1 : 0.6, margin: 0 }}
              onClick={() => statClick("green")}>🟢 正常 {stats.green}</Tag>
            <Tag color="warning" style={{ cursor: "pointer", opacity: statusFilter === "yellow" ? 1 : 0.6, margin: 0 }}
              onClick={() => statClick("yellow")}>🟡 需关注 {stats.yellow}</Tag>
            <Tag color="error" style={{ cursor: "pointer", opacity: statusFilter === "red" ? 1 : 0.6, margin: 0 }}
              onClick={() => statClick("red")}>🔴 异常 {stats.red}</Tag>
            <Tag color="default" style={{ cursor: "pointer", opacity: statusFilter === "gray" ? 1 : 0.6, margin: 0 }}
              onClick={() => statClick("gray")}>⚪ 未对接 {stats.gray}</Tag>
            {statusFilter !== "all" && (
              <Button size="small" type="link" style={{ fontSize: 10, padding: 0 }} onClick={() => setStatusFilter("all")}>清除筛选</Button>
            )}
          </div>

          {/* Main layout */}
          <div style={{ display: "flex", gap: 12, flex: 1, minHeight: 0 }}>
            <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
              <AccountListTab
                accounts={filtered}
                selectedWabaKey={selectedWabaKey}
                onSelect={setSelectedWabaKey}
                filterMode={filterMode}
                onFilterModeChange={setFilterMode}
                searchText={searchText}
                onSearchChange={setSearchText}
                onManualAdd={() => setManualModalOpen(true)}
                onSignup={() => setSignupModalOpen(true)}
                onRefresh={handleRefresh}
                loading={loading}
              />
            </div>
            {selectedAccount && (
              <div style={{ width: 380, flexShrink: 0, borderLeft: "1px solid #f0f0f0" }}>
                <AccountDetailPanel
                  account={selectedAccount}
                  onRefresh={handleRefresh}
                  onEdit={openEditModal}
                  onDeleted={handleDeleted}
                />
              </div>
            )}
          </div>
        </>
      )}

      <CreateManualModal
        open={manualModalOpen}
        onClose={() => { setManualModalOpen(false); setEditingAccount(null); }}
        onCreated={handleRefresh}
        editingAccount={editingAccount}
        onSaved={handleAccountEditSaved}
      />
      <CreateSignupModal open={signupModalOpen} onClose={() => setSignupModalOpen(false)} onCreated={handleSignupCreated} />
    </div>
  );
}
