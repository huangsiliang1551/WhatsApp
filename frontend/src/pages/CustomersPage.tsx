import { ClearOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Input, message, Popconfirm, Select, Space, Table, Tag, Typography, type TableColumnsType } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { showError, showSuccess } from "../components/Feedback";
import { MemberIdLink } from "../components/member/MemberIdLink";
import { usePageData } from "../hooks/usePageData";
import { usePermissions } from "../hooks/usePermissions";
import {
  batchUpdateCustomerLifecycle,
  listMetaAccounts,
  listPlatformUsersPaginated,
  type PaginatedUserListResponse,
  type PlatformUser,
  type PlatformUserListParams,
} from "../services/api";
import {
  getCustomerMemberStatusSnapshot,
  listPlatformUserMemberStatusIndex,
  type CustomerMemberStatusSnapshot,
  type PlatformUserMemberStatusSummary,
} from "../services/operations";
import { useAppStore } from "../stores/appStore";
import { CustomerDetailDrawer } from "./CustomerDetailDrawer";

export function getCustomerSummaryMemberLinkProps(summary: Pick<PlatformUser, "id" | "account_id" | "public_user_id">): {
  accountId: string | null;
  userId: string;
  publicUserId: string;
  label: string;
} {
  return {
    accountId: summary.account_id,
    userId: summary.id,
    publicUserId: summary.public_user_id,
    label: summary.public_user_id,
  };
}

const LC_COLORS: Record<string, string> = {
  active: "#52c41a",
  frozen: "#1677ff",
  blacklisted: "#ff4d4f",
  dormant: "#faad14",
  new: "#1677ff",
  churned: "#999",
  inactive: "#d9d9d9",
};

const LC_LABELS: Record<string, string> = {
  active: "活跃",
  frozen: "冻结",
  blacklisted: "黑名单",
  dormant: "休眠",
  new: "新用户",
  churned: "流失",
  inactive: "不活跃",
};

const IDENTITY_TYPE_MAP: Record<string, string> = {
  whatsapp: "WhatsApp",
  phone: "手机",
  email: "邮箱",
};

type LifecycleFilter = "" | "active" | "frozen" | "blacklisted" | "dormant" | "new" | "churned";
type IdentityFilter = "" | "whatsapp" | "phone" | "email";

const batchBarStyle: React.CSSProperties = {
  position: "fixed",
  bottom: 0,
  left: 0,
  right: 0,
  zIndex: 1000,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 24px",
  background: "#1677ff",
  boxShadow: "0 -2px 8px rgba(0,0,0,0.15)",
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("zh-CN");
}

export function CustomersPage(): JSX.Element {
  const prefill = useAppStore((state) => state.customersPagePrefill);
  const clearPrefill = useAppStore((state) => state.clearCustomersPagePrefill);
  const openWorkspacePage = useAppStore((state) => state.openWorkspacePage);
  const { can } = usePermissions();

  const [search, setSearch] = useState(prefill?.query ?? "");
  const [searchDraft, setSearchDraft] = useState(prefill?.query ?? "");
  const [filterAccount, setFilterAccount] = useState<string | undefined>(prefill?.account_id);
  const [filterLifecycle, setFilterLifecycle] = useState<LifecycleFilter>("");
  const [filterIdentity, setFilterIdentity] = useState<IdentityFilter>("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [accounts, setAccounts] = useState<Array<{ account_id: string; display_name: string }>>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [detailCustomerId, setDetailCustomerId] = useState<string | null>(prefill?.selected_profile_id ?? null);
  const [detailOpen, setDetailOpen] = useState(Boolean(prefill?.selected_profile_id));
  const [detailMemberStatus, setDetailMemberStatus] = useState<CustomerMemberStatusSnapshot | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    listMetaAccounts({})
      .then((items) => setAccounts(items))
      .catch(() => {
        setAccounts([]);
      });
  }, []);

  useEffect(() => {
    if (!prefill) return;
    setSearch(prefill.query ?? "");
    setSearchDraft(prefill.query ?? "");
    setFilterAccount(prefill.account_id);
    setDetailCustomerId(prefill.selected_profile_id ?? null);
    setDetailOpen(Boolean(prefill.selected_profile_id));
    clearPrefill();
  }, [clearPrefill, prefill]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearch(searchDraft);
      setPage(1);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchDraft]);

  const fetchParams: PlatformUserListParams = useMemo(
    () => ({
      page,
      size: pageSize,
      search: search || undefined,
      account_id: filterAccount || undefined,
      lifecycle_status: filterLifecycle || undefined,
      identity_type: filterIdentity || undefined,
      sort: "created_at:desc",
    }),
    [filterAccount, filterIdentity, filterLifecycle, page, pageSize, search]
  );

  const fetcher = useCallback(async () => {
    const result = await listPlatformUsersPaginated(fetchParams);
    const customerMemberStatusIndex = await listPlatformUserMemberStatusIndex(
      result.items.map((item) => ({
        id: item.id,
        account_id: item.account_id,
        public_user_id: item.public_user_id,
      })),
      fetchParams.account_id
    );
    return { result, customerMemberStatusIndex };
  }, [fetchParams]);

  const { data, error, loading, reload } = usePageData({ fetcher });
  const pageData: PaginatedUserListResponse | null = data?.result ?? null;
  const users = pageData?.items ?? [];
  const total = pageData?.total ?? 0;
  const customerMemberStatusIndex: Record<string, PlatformUserMemberStatusSummary> = data?.customerMemberStatusIndex ?? {};
  const selectedCustomerSummary = useMemo(
    () => users.find((item) => item.id === detailCustomerId) ?? null,
    [detailCustomerId, users]
  );

  useEffect(() => {
    if (!selectedCustomerSummary) {
      setDetailMemberStatus(null);
      return;
    }

    getCustomerMemberStatusSnapshot({
      id: selectedCustomerSummary.id,
      public_user_id: selectedCustomerSummary.public_user_id,
      account_id: selectedCustomerSummary.account_id,
    })
      .then(setDetailMemberStatus)
      .catch(() => setDetailMemberStatus(null));
  }, [selectedCustomerSummary]);

  const activeCount = users.filter((item) => item.lifecycle_status === "active").length;
  const newUserCount = users.filter((item) => item.is_new_user).length;
  const blacklistedCount = users.filter((item) => item.lifecycle_status === "blacklisted").length;
  const frozenCount = users.filter((item) => item.lifecycle_status === "frozen").length;
  const whatsappCount = users.filter((item) => item.has_whatsapp).length;

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }} wrap>
      <span>
        总数 <Typography.Text strong>{total}</Typography.Text>
      </span>
      <span>
        活跃 <Typography.Text strong style={{ color: "#52c41a" }}>{activeCount}</Typography.Text>
      </span>
      <span>
        新用户 <Typography.Text strong style={{ color: "#1677ff" }}>{newUserCount}</Typography.Text>
      </span>
      <span>
        黑名单 <Typography.Text strong style={{ color: "#ff4d4f" }}>{blacklistedCount}</Typography.Text>
      </span>
      <span>
        冻结 <Typography.Text strong style={{ color: "#1677ff" }}>{frozenCount}</Typography.Text>
      </span>
      <span>
        有 WhatsApp <Typography.Text strong style={{ color: "#52c41a" }}>{whatsappCount}</Typography.Text>
      </span>
    </Space>
  );

  const actions = (
    <Space>
      <Button loading={loading} onClick={() => void reload()} size="small">
        刷新
      </Button>
    </Space>
  );

  const handleBlockUser = useCallback(
    async (user: PlatformUser) => {
      try {
        await batchUpdateCustomerLifecycle({
          customer_ids: [user.id],
          lifecycle_status: "blacklisted",
          account_id: user.account_id ?? undefined,
        });
        showSuccess(`${user.public_user_id} 已拉黑`);
        await reload();
      } catch {
        showError("拉黑失败");
      }
    },
    [reload]
  );

  const handleUnblockUser = useCallback(
    async (user: PlatformUser) => {
      try {
        await batchUpdateCustomerLifecycle({
          customer_ids: [user.id],
          lifecycle_status: "active",
          account_id: user.account_id ?? undefined,
        });
        showSuccess(`${user.public_user_id} 已解封`);
        await reload();
      } catch {
        showError("解封失败");
      }
    },
    [reload]
  );

  const handleBatchLifecycle = useCallback(
    async (status: string, label: string) => {
      if (selectedRowKeys.length === 0) return;
      setBatchLoading(true);
      try {
        await batchUpdateCustomerLifecycle({
          customer_ids: selectedRowKeys as string[],
          lifecycle_status: status,
          account_id: filterAccount,
        });
        showSuccess(`已${label} ${selectedRowKeys.length} 个客户`);
        setSelectedRowKeys([]);
        await reload();
      } catch {
        showError(`${label}失败`);
      } finally {
        setBatchLoading(false);
      }
    },
    [filterAccount, reload, selectedRowKeys]
  );

  const handleOpenDetail = useCallback((user: PlatformUser) => {
    setDetailCustomerId(user.id);
    setDetailOpen(true);
  }, []);

  const handleViewConversations = useCallback(
    (user: PlatformUser) => {
      openWorkspacePage({
        accountId: user.account_id ?? undefined,
        search: user.public_user_id,
      });
    },
    [openWorkspacePage]
  );

  const clearFilters = useCallback(() => {
    setSearchDraft("");
    setSearch("");
    setFilterAccount(undefined);
    setFilterLifecycle("");
    setFilterIdentity("");
    setPage(1);
  }, []);

  const columns: TableColumnsType<PlatformUser> = [
    {
      title: "用户 ID",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 140,
      ellipsis: true,
      sorter: (left, right) => (left.public_user_id ?? "").localeCompare(right.public_user_id ?? ""),
      render: (value: string, record: PlatformUser) => (
        <MemberIdLink
          accountId={record.account_id}
          userId={record.id}
          publicUserId={record.public_user_id}
          label={value || record.public_user_id}
        />
      ),
    },
    {
      title: "名称",
      dataIndex: "display_name",
      key: "display_name",
      width: 130,
      ellipsis: true,
      sorter: (left, right) => (left.display_name ?? "").localeCompare(right.display_name ?? ""),
      render: (value: string | null, record: PlatformUser) => (
        <a onClick={() => handleOpenDetail(record)}>{value || record.public_user_id.slice(0, 12)}</a>
      ),
    },
    {
      title: "状态",
      dataIndex: "lifecycle_status",
      key: "lifecycle_status",
      width: 90,
      sorter: (left, right) => (left.lifecycle_status ?? "").localeCompare(right.lifecycle_status ?? ""),
      render: (value: string) => (
        <Tag color={LC_COLORS[value] ?? "default"} style={{ fontSize: 10, margin: 0 }}>
          {LC_LABELS[value] ?? value}
        </Tag>
      ),
    },
    {
      title: "会员认证",
      key: "member_verification",
      width: 120,
      render: (_: unknown, record: PlatformUser) => (
        <Tag color={customerMemberStatusIndex[record.id]?.latestVerificationStatus === "approved" ? "green" : "blue"}>
          {customerMemberStatusIndex[record.id]?.latestVerificationStatus ?? "-"}
        </Tag>
      ),
    },
    {
      title: "WhatsApp 绑定",
      key: "member_binding",
      width: 130,
      render: (_: unknown, record: PlatformUser) => (
        <Tag color={customerMemberStatusIndex[record.id]?.latestBindingStatus === "bound" ? "green" : "blue"}>
          {customerMemberStatusIndex[record.id]?.latestBindingStatus ?? "-"}
        </Tag>
      ),
    },
    {
      title: "会话",
      dataIndex: "conversation_count",
      key: "conversation_count",
      width: 80,
      render: (value: number | undefined) => value ?? "-",
      sorter: (left, right) => (left.conversation_count ?? 0) - (right.conversation_count ?? 0),
    },
    {
      title: "工单",
      dataIndex: "ticket_count",
      key: "ticket_count",
      width: 80,
      render: (value: number | undefined) => value ?? "-",
      sorter: (left, right) => (left.ticket_count ?? 0) - (right.ticket_count ?? 0),
    },
    {
      title: "余额",
      dataIndex: "wallet_balance",
      key: "wallet_balance",
      width: 100,
      render: (value: number | undefined) => (value != null ? `¥${value.toFixed(2)}` : "-"),
      sorter: (left, right) => (left.wallet_balance ?? 0) - (right.wallet_balance ?? 0),
    },
    {
      title: "最后活跃",
      dataIndex: "last_active_at",
      key: "last_active_at",
      width: 120,
      render: (value: string | null) => formatDate(value),
      sorter: (left, right) => new Date(left.last_active_at ?? 0).getTime() - new Date(right.last_active_at ?? 0).getTime(),
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      fixed: "right",
      render: (_: unknown, record: PlatformUser) => (
        <Space size={4} style={{ display: "flex", flexWrap: "nowrap" }}>
          <Button onClick={() => handleOpenDetail(record)} size="small" style={{ fontSize: 11, padding: 0 }} type="link">
            详情
          </Button>
          {record.lifecycle_status === "blacklisted" ? (
            <Button onClick={() => void handleUnblockUser(record)} size="small" style={{ color: "#52c41a", fontSize: 11, padding: 0 }} type="link">
              解封
            </Button>
          ) : (
            <Button onClick={() => void handleBlockUser(record)} size="small" style={{ color: "#ff4d4f", fontSize: 11, padding: 0 }} type="link">
              拉黑
            </Button>
          )}
          <Button onClick={() => handleViewConversations(record)} size="small" style={{ fontSize: 11, padding: 0 }} type="link">
            会话
          </Button>
        </Space>
      ),
    },
  ];

  const showClearFilters = Boolean(search || filterAccount || filterLifecycle || filterIdentity);

  if (total === 0 && !loading) {
    return (
      <PageShell actions={actions} stats={stats} subtitle="查看和管理注册用户" title="客户管理">
        <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
          <Input
            allowClear
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder="搜索 ID / 名称"
            prefix={<SearchOutlined />}
            style={{ width: 240 }}
            value={searchDraft}
          />
          <Select
            allowClear
            onChange={(value) => {
              setFilterAccount(value);
              setPage(1);
            }}
            options={accounts.map((account) => ({ label: account.display_name, value: account.account_id }))}
            placeholder="全部账号"
            style={{ width: 180 }}
            value={filterAccount}
          />
          <Select
            allowClear
            onChange={(value) => {
              setFilterLifecycle((value ?? "") as LifecycleFilter);
              setPage(1);
            }}
            options={Object.entries(LC_LABELS).map(([key, value]) => ({ label: value, value: key }))}
            placeholder="生命周期"
            style={{ width: 140 }}
            value={filterLifecycle || undefined}
          />
          <Select
            allowClear
            onChange={(value) => {
              setFilterIdentity((value ?? "") as IdentityFilter);
              setPage(1);
            }}
            options={Object.entries(IDENTITY_TYPE_MAP).map(([key, value]) => ({ label: value, value: key }))}
            placeholder="身份类型"
            style={{ width: 140 }}
            value={filterIdentity || undefined}
          />
          {showClearFilters ? (
            <Button icon={<ClearOutlined />} onClick={clearFilters} size="small">
              清除
            </Button>
          ) : null}
        </div>
        <EmptyGuide description="当前没有客户数据，或者筛选条件没有命中任何结果。" icon="👤" title="暂无客户" />
      </PageShell>
    );
  }

  return (
    <PageShell actions={actions} stats={stats} subtitle="查看和管理注册用户" title="客户管理">
      <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        <Input
          allowClear
          onChange={(event) => setSearchDraft(event.target.value)}
          placeholder="搜索 ID / 名称"
          prefix={<SearchOutlined />}
          style={{ width: 240 }}
          value={searchDraft}
        />
        <Select
          allowClear
          onChange={(value) => {
            setFilterAccount(value);
            setPage(1);
          }}
          options={accounts.map((account) => ({ label: account.display_name, value: account.account_id }))}
          placeholder="全部账号"
          style={{ width: 180 }}
          value={filterAccount}
        />
        <Select
          allowClear
          onChange={(value) => {
            setFilterLifecycle((value ?? "") as LifecycleFilter);
            setPage(1);
          }}
          options={Object.entries(LC_LABELS).map(([key, value]) => ({ label: value, value: key }))}
          placeholder="生命周期"
          style={{ width: 140 }}
          value={filterLifecycle || undefined}
        />
        <Select
          allowClear
          onChange={(value) => {
            setFilterIdentity((value ?? "") as IdentityFilter);
            setPage(1);
          }}
          options={Object.entries(IDENTITY_TYPE_MAP).map(([key, value]) => ({ label: value, value: key }))}
          placeholder="身份类型"
          style={{ width: 140 }}
          value={filterIdentity || undefined}
        />
        {showClearFilters ? (
          <Button icon={<ClearOutlined />} onClick={clearFilters} size="small">
            清除
          </Button>
        ) : null}
      </div>

      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 8 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Table
        columns={columns}
        dataSource={users}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: ["20", "50", "100"],
          showTotal: (value) => `共 ${value} 条`,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage);
            setPageSize(nextPageSize);
          },
        }}
        rowKey="id"
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
        }}
        scroll={{ x: 1180, y: "calc(100vh - 380px)" }}
        size="small"
      />

      {selectedRowKeys.length > 0 ? (
        <div style={batchBarStyle}>
          <Typography.Text style={{ color: "#fff", fontSize: 13 }}>
            已选 {selectedRowKeys.length} 项
          </Typography.Text>
          <Space size={8}>
            {can("customers.edit_tags") ? (
              <Popconfirm
                cancelText="取消"
                okButtonProps={{ danger: true }}
                okText="确认"
                onConfirm={() => void handleBatchLifecycle("blacklisted", "拉黑")}
                title={`确认拉黑 ${selectedRowKeys.length} 个客户？`}
              >
                <Button ghost loading={batchLoading} size="small" type="primary">
                  批量拉黑
                </Button>
              </Popconfirm>
            ) : null}
            {can("customers.edit_tags") ? (
              <Popconfirm
                cancelText="取消"
                okText="确认"
                onConfirm={() => void handleBatchLifecycle("active", "解封")}
                title={`确认解封 ${selectedRowKeys.length} 个客户？`}
              >
                <Button ghost loading={batchLoading} size="small" type="primary">
                  批量解封
                </Button>
              </Popconfirm>
            ) : null}
            <Button ghost icon={<ClearOutlined />} onClick={() => setSelectedRowKeys([])} size="small" type="primary">
              取消选择
            </Button>
          </Space>
        </div>
      ) : null}

      {selectedCustomerSummary ? (
        <div style={{ border: "1px solid #f0f0f0", borderRadius: 8, marginBottom: 12, marginTop: 12, padding: 12 }}>
          <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
            会员状态概览
          </Typography.Text>
          <Space direction="vertical" size={4}>
            <Typography.Text>会员认证状态：{detailMemberStatus?.verificationRequests[0]?.status ?? "暂无"}</Typography.Text>
            <Typography.Text>WhatsApp 绑定状态：{detailMemberStatus?.bindingRequests[0]?.status ?? "暂无"}</Typography.Text>
            <span style={{ display: "flex", alignItems: "center", gap: 6, color: "#8c8c8c", fontSize: 14 }}>
              <span>当前档案：</span>
              <MemberIdLink {...getCustomerSummaryMemberLinkProps(selectedCustomerSummary)} />
              <span>/ {selectedCustomerSummary.account_id ?? "-"}</span>
            </span>
          </Space>
        </div>
      ) : null}

      <CustomerDetailDrawer
        accountId={filterAccount}
        customerId={detailCustomerId}
        onClose={() => {
          setDetailOpen(false);
          setDetailCustomerId(null);
        }}
        onViewConversations={handleViewConversations}
        open={detailOpen}
      />
    </PageShell>
  );
}
