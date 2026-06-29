import { useCallback, useEffect, useMemo, useState, type CSSProperties, type JSX } from "react";
import {
  Alert,
  Button,
  Descriptions,
  Empty,
  List,
  Modal,
  Pagination,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tabs,
  Typography,
  message,
} from "antd";
import {
  CopyOutlined,
  ReloadOutlined,
  StopOutlined,
  UnlockOutlined,
  UserOutlined,
} from "@ant-design/icons";

import {
  batchUpdateCustomerLifecycle,
  getCustomerProfile,
  getCustomerTimeline,
  listCustomerConversations,
  listWalletLedgers,
} from "../services/api";
import { MemberIdLink } from "../components/member/MemberIdLink";
import { showError, showSuccess } from "../components/Feedback";
import { usePermissions } from "../hooks/usePermissions";
import { getMemberSummary } from "../services/memberApi";
import { useAppStore } from "../stores/appStore";
import type {
  CustomerConversationBrief,
  CustomerProfile,
  FinanceWalletLedger,
  PlatformUser,
  TimelineEvent,
} from "../services/api";
import type { CustomerSummaryResponse } from "../types/member";

const { Text, Title } = Typography;

type TabKey =
  | "overview"
  | "attribution"
  | "conversations"
  | "tickets"
  | "finance"
  | "timeline"
  | "profile";

const TAB_ITEMS: Array<{ key: TabKey; label: string }> = [
  { key: "overview", label: "概览" },
  { key: "attribution", label: "归属" },
  { key: "conversations", label: "会话" },
  { key: "tickets", label: "工单" },
  { key: "finance", label: "财务" },
  { key: "timeline", label: "时间线" },
  { key: "profile", label: "画像" },
];

const FIXED_CARD_HEIGHT = 96;
const CONTENT_HEIGHT = 520;
const CONVERSATION_PAGE_SIZE = 5;
const TICKET_PAGE_SIZE = 5;
const TIMELINE_PAGE_SIZE = 7;
const LEDGER_PAGE_SIZE = 8;
const OVERVIEW_TIMELINE_LIMIT = 5;

const statCardStyle: CSSProperties = {
  background: "#fff",
  border: "1px solid #efe7db",
  borderRadius: 14,
  minHeight: FIXED_CARD_HEIGHT,
  padding: 12,
  alignContent: "center",
};

const sectionCardStyle: CSSProperties = {
  background: "#fff",
  border: "1px solid #efe7db",
  borderRadius: 16,
  padding: 16,
};

const compactDescriptionContentStyle: CSSProperties = {
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
};

const profileIdWrapStyle: CSSProperties = {
  display: "inline-block",
  maxWidth: "100%",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
};

const scrollPaneStyle: CSSProperties = {
  overflowY: "auto",
  paddingRight: 4,
};

const LIFECYCLE_META: Record<string, { color: string; label: string }> = {
  active: { color: "success", label: "活跃" },
  frozen: { color: "processing", label: "冻结" },
  blacklisted: { color: "error", label: "黑名单" },
  dormant: { color: "warning", label: "休眠" },
  new: { color: "processing", label: "新用户" },
  churned: { color: "default", label: "流失" },
  inactive: { color: "default", label: "不活跃" },
};

const VERIFICATION_META: Record<string, { color: string; label: string }> = {
  pending: { color: "warning", label: "待审核" },
  approved: { color: "success", label: "已通过" },
  rejected: { color: "error", label: "已拒绝" },
  not_submitted: { color: "default", label: "未提交" },
};

const BINDING_META: Record<string, { color: string; label: string }> = {
  pending: { color: "warning", label: "待绑定" },
  bound: { color: "success", label: "已绑定" },
  approved: { color: "success", label: "已绑定" },
  unbound: { color: "default", label: "未绑定" },
  rejected: { color: "error", label: "已拒绝" },
};

const MANAGEMENT_MODE_META: Record<string, { color: string; label: string }> = {
  ai_managed: { color: "success", label: "AI 托管" },
  human_managed: { color: "processing", label: "人工接管" },
  paused: { color: "warning", label: "暂停" },
};

const TICKET_STATUS_META: Record<string, { color: string; label: string }> = {
  open: { color: "error", label: "待处理" },
  in_progress: { color: "processing", label: "处理中" },
  pending_user: { color: "warning", label: "待补充" },
  resolved: { color: "success", label: "已解决" },
  closed: { color: "default", label: "已关闭" },
  rejected: { color: "default", label: "已拒绝" },
};

const LEDGER_TYPE_LABELS: Record<string, string> = {
  system_credit: "系统入账",
  system_debit: "系统扣减",
  recharge: "充值",
  reward: "奖励",
  task: "任务",
  withdrawal: "提现",
  sign_in_completion: "签到奖励",
  admin_bonus: "后台赠金",
  manual_real_recharge: "人工补单",
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  admin_bonus: "后台赠金",
  invite_bonus: "邀请奖励",
  activity_bonus: "活动奖励",
  recharge: "充值",
  task_reward: "任务奖励",
  withdraw: "提现",
};

export interface CustomerDetailDrawerProps {
  open: boolean;
  customerId: string | null;
  accountId?: string | null;
  initialTab?: TabKey;
  onClose: () => void;
  onViewConversations: (user: PlatformUser) => void;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("zh-CN");
}

function formatMoney(value: number): string {
  return `¥${value.toFixed(2)}`;
}

function renderStatusTag(meta: { color: string; label: string } | undefined, fallback: string): JSX.Element {
  return <Tag color={meta?.color ?? "default"}>{meta?.label ?? fallback}</Tag>;
}

async function copyText(value: string, successText: string): Promise<void> {
  if (!value) return;
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    message.success(successText);
    return;
  }
  message.info("当前环境不支持复制");
}

function getLedgerTitle(row: FinanceWalletLedger): string {
  if (row.display_title) return row.display_title;
  if (row.source_type && SOURCE_TYPE_LABELS[row.source_type]) return SOURCE_TYPE_LABELS[row.source_type];
  if (row.ledger_type && LEDGER_TYPE_LABELS[row.ledger_type]) return LEDGER_TYPE_LABELS[row.ledger_type];
  return row.ledger_type || "钱包流水";
}

function renderMemberIdBlock(
  accountId: string | null | undefined,
  userId: string,
  publicUserId: string,
): JSX.Element {
  return (
    <span style={profileIdWrapStyle}>
      <MemberIdLink
        accountId={accountId ?? undefined}
        userId={userId}
        publicUserId={publicUserId}
        label={publicUserId}
      />
    </span>
  );
}

function InlineTimelineList({ events }: { events: TimelineEvent[] }): JSX.Element {
  return (
    <List
      size="small"
      dataSource={events}
      renderItem={(event) => (
        <List.Item>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, width: "100%", alignItems: "center" }}>
            <Text ellipsis>{event.summary}</Text>
            <Text type="secondary">{formatDateTime(event.time)}</Text>
          </div>
        </List.Item>
      )}
    />
  );
}

function getRegistrationLocationLabel(ip: string | null | undefined): string {
  if (!ip) return "-";
  if (ip === "127.0.0.1" || ip === "::1" || ip.toLowerCase() === "localhost") {
    return "本机";
  }
  return "-";
}

function getSameIpUserLabel(count: number | null | undefined): string {
  const normalized = typeof count === "number" && count > 0 ? count : 1;
  return `同IP ${normalized}个用户`;
}

export function CustomerDetailDrawer({
  open,
  customerId,
  accountId,
  initialTab,
  onClose,
  onViewConversations,
}: CustomerDetailDrawerProps): JSX.Element {
  const { can } = usePermissions();
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);
  const canViewFinance = can("customers.finance");
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab ?? "overview");
  const [summary, setSummary] = useState<CustomerSummaryResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [conversations, setConversations] = useState<CustomerConversationBrief[]>([]);
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [ledgerRows, setLedgerRows] = useState<FinanceWalletLedger[]>([]);
  const [ledgerPage, setLedgerPage] = useState(1);
  const [conversationPage, setConversationPage] = useState(1);
  const [ticketPage, setTicketPage] = useState(1);
  const [timelinePage, setTimelinePage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [conversationsLoading, setConversationsLoading] = useState(false);
  const [profileLoading, setProfileLoading] = useState(false);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback(async (id: string, currentAccountId?: string | null) => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await getMemberSummary(id, currentAccountId ?? undefined));
    } catch (loadError: unknown) {
      setError(loadError instanceof Error ? loadError.message : "加载客户详情失败");
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTimeline = useCallback(async (id: string, currentAccountId?: string | null) => {
    setTimelineLoading(true);
    try {
      const data = await getCustomerTimeline(id, { account_id: currentAccountId ?? undefined, limit: 120 });
      setTimeline(data.events);
    } catch {
      setTimeline([]);
    } finally {
      setTimelineLoading(false);
    }
  }, []);

  const loadConversations = useCallback(async (id: string, currentAccountId?: string | null) => {
    if (!currentAccountId) {
      setConversations([]);
      return;
    }
    setConversationsLoading(true);
    try {
      const data = await listCustomerConversations(currentAccountId, id, undefined, 50);
      setConversations(data);
    } catch {
      setConversations([]);
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  const loadProfile = useCallback(async (id: string, currentAccountId?: string | null) => {
    setProfileLoading(true);
    try {
      setProfile(await getCustomerProfile(id, currentAccountId ?? undefined));
    } catch {
      setProfile(null);
    } finally {
      setProfileLoading(false);
    }
  }, []);

  const loadLedgers = useCallback(async (id: string) => {
    if (!canViewFinance) {
      setLedgerRows([]);
      return;
    }
    setLedgerLoading(true);
    try {
      setLedgerRows(await listWalletLedgers({ userId: id }));
    } catch {
      setLedgerRows([]);
    } finally {
      setLedgerLoading(false);
    }
  }, [canViewFinance]);

  const reloadAll = useCallback(async () => {
    if (!open || !customerId) return;
    await Promise.all([
      loadSummary(customerId, accountId),
      loadTimeline(customerId, accountId),
      loadConversations(customerId, accountId),
      loadProfile(customerId, accountId),
      loadLedgers(customerId),
    ]);
  }, [accountId, customerId, loadConversations, loadLedgers, loadProfile, loadSummary, loadTimeline, open]);

  useEffect(() => {
    if (!open || !customerId) {
      setSummary(null);
      setTimeline([]);
      setConversations([]);
      setProfile(null);
      setLedgerRows([]);
      setError(null);
      setActiveTab(initialTab ?? "overview");
      setLedgerPage(1);
      setConversationPage(1);
      setTicketPage(1);
      setTimelinePage(1);
      return;
    }
    setActiveTab(initialTab ?? "overview");
    void reloadAll();
  }, [customerId, initialTab, open, reloadAll]);

  const runLifecycleUpdate = useCallback(async (nextStatus: "active" | "blacklisted") => {
    if (!customerId) return;
    setActionLoading(true);
    try {
      await batchUpdateCustomerLifecycle({
        customer_ids: [customerId],
        lifecycle_status: nextStatus,
        account_id: accountId ?? undefined,
      });
      showSuccess(nextStatus === "blacklisted" ? "已拉黑该客户" : "已解除黑名单");
      await loadSummary(customerId, accountId);
    } catch {
      showError(nextStatus === "blacklisted" ? "拉黑失败" : "解封失败");
    } finally {
      setActionLoading(false);
    }
  }, [accountId, customerId, loadSummary]);

  const handleToggleBlacklist = useCallback(() => {
    if (!summary) return;
    const isBlacklisted = summary.customer.lifecycle_status === "blacklisted";
    Modal.confirm({
      title: isBlacklisted ? "解除黑名单" : "拉黑客户",
      content: isBlacklisted ? "解除后客户会恢复正常状态。" : "拉黑后客户将被标记为黑名单。",
      okText: isBlacklisted ? "确认解封" : "确认拉黑",
      cancelText: "取消",
      okButtonProps: isBlacklisted ? undefined : { danger: true },
      onOk: () => runLifecycleUpdate(isBlacklisted ? "active" : "blacklisted"),
    });
  }, [runLifecycleUpdate, summary]);

  const handleViewConversations = useCallback(() => {
    if (!summary) return;
    onViewConversations({
      public_user_id: summary.customer.public_user_id,
      account_id: accountId ?? null,
    } as PlatformUser);
  }, [accountId, onViewConversations, summary]);

  const pagedLedgers = useMemo(() => {
    const start = (ledgerPage - 1) * LEDGER_PAGE_SIZE;
    return ledgerRows.slice(start, start + LEDGER_PAGE_SIZE);
  }, [ledgerPage, ledgerRows]);

  const pagedConversations = useMemo(() => {
    const start = (conversationPage - 1) * CONVERSATION_PAGE_SIZE;
    return conversations.slice(start, start + CONVERSATION_PAGE_SIZE);
  }, [conversationPage, conversations]);

  const pagedTickets = useMemo(() => {
    const items = summary?.tickets.items ?? [];
    const start = (ticketPage - 1) * TICKET_PAGE_SIZE;
    return items.slice(start, start + TICKET_PAGE_SIZE);
  }, [summary?.tickets.items, ticketPage]);

  const pagedTimeline = useMemo(() => {
    const start = (timelinePage - 1) * TIMELINE_PAGE_SIZE;
    return timeline.slice(start, start + TIMELINE_PAGE_SIZE);
  }, [timeline, timelinePage]);

  const renderOverview = (): JSX.Element | null => {
    if (!summary) return null;
    const { customer, wallet, member_status, conversations: conversationStats, tickets, tags } = summary;
    const registrationLocation = customer.registration_location || getRegistrationLocationLabel(customer.registration_ip);
    const sameIpUserCount = customer.same_ip_user_count ?? 0;

    return (
      <div style={{ height: CONTENT_HEIGHT, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 360px", gap: 16 }}>
        <div style={{ display: "grid", gridTemplateRows: "auto auto", gap: 16, minWidth: 0 }}>
          <section style={{ ...sectionCardStyle, background: "#faf7f0", borderColor: "#efe3cd" }}>
            <Title level={5} style={{ marginTop: 0, marginBottom: 10 }}>基础资料</Title>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="客户 ID" span={2}>
                <div style={compactDescriptionContentStyle}>
                  {renderMemberIdBlock(accountId, customer.id, customer.public_user_id)}
                </div>
              </Descriptions.Item>
              <Descriptions.Item label="语言">{customer.language || "-"}</Descriptions.Item>
              <Descriptions.Item label="验证类型">{member_status.verification.request_type || "-"}</Descriptions.Item>
              <Descriptions.Item label="注册 IP" span={2}>
                <Space wrap size={[8, 8]}>
                  <Text>{customer.registration_ip || "-"}</Text>
                  <Text type="secondary">{registrationLocation}</Text>
                  {customer.registration_ip ? (
                    <Button
                      type="link"
                      size="small"
                      style={{ paddingInline: 0 }}
                      onClick={() =>
                        openCustomersPage({
                          account_id: accountId ?? undefined,
                          query: customer.registration_ip ?? undefined,
                          selected_profile_id: customer.id,
                        })
                      }
                    >
                      {getSameIpUserLabel(sameIpUserCount)}
                    </Button>
                  ) : null}
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="标签" span={2}>
                <Space wrap>{tags.length > 0 ? tags.map((tag) => <Tag key={tag}>{tag}</Tag>) : <span>-</span>}</Space>
              </Descriptions.Item>
            </Descriptions>
          </section>

          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
            <div style={statCardStyle}>
              <Statistic title="总会话" value={conversationStats.total} />
            </div>
            <div style={statCardStyle}>
              <Statistic title="进行中会话" value={conversationStats.open} />
            </div>
            <div style={statCardStyle}>
              <Statistic title="工单总数" value={tickets.total} />
            </div>
            <div style={statCardStyle}>
              <Statistic title="总余额" value={canViewFinance ? wallet.balance : "需财务权限"} precision={canViewFinance ? 2 : undefined} prefix={canViewFinance ? "¥" : undefined} />
            </div>
            <div style={statCardStyle}>
              <Statistic title="累计充值" value={canViewFinance ? wallet.total_recharged : "需财务权限"} precision={canViewFinance ? 2 : undefined} prefix={canViewFinance ? "¥" : undefined} />
            </div>
            <div style={statCardStyle}>
              <Statistic title="累计提现" value={canViewFinance ? wallet.total_withdrawn : "需财务权限"} precision={canViewFinance ? 2 : undefined} prefix={canViewFinance ? "¥" : undefined} />
            </div>
          </div>
        </div>

        <section style={sectionCardStyle}>
          <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>最近动态</Title>
          {timeline.length > 0 ? (
            <div style={{ ...scrollPaneStyle, height: CONTENT_HEIGHT - 60 }}>
              <InlineTimelineList events={timeline.slice(0, OVERVIEW_TIMELINE_LIMIT)} />
            </div>
          ) : (
            <Empty description="暂无时间线事件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </section>
      </div>
    );
  };

  const renderAttribution = (): JSX.Element | null => {
    if (!summary) return null;
    const member = summary.member_profile;
    if (!member) {
      return <Empty description="暂无归属信息" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <div style={{ height: CONTENT_HEIGHT, overflowY: "auto", display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", alignItems: "start" }}>
        <section style={sectionCardStyle}>
          <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>当前归属</Title>
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="代理商">{member.current_owner_agency_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="员工">{member.current_owner_staff_user_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="归属记录">{member.current_owner_assignment_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="归属时间">{formatDateTime(member.owner_assigned_at)}</Descriptions.Item>
            <Descriptions.Item label="归属状态">{member.attribution_status || "-"}</Descriptions.Item>
          </Descriptions>
        </section>
        <section style={sectionCardStyle}>
          <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>AI 归属</Title>
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="AI Agent">{member.current_ai_agent_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="AI 分配记录">{member.current_ai_assignment_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="分配时间">{formatDateTime(member.ai_assigned_at)}</Descriptions.Item>
          </Descriptions>
        </section>
        <section style={sectionCardStyle}>
          <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>注册来源</Title>
          <Descriptions size="small" column={1}>
            <Descriptions.Item label="入口链接">{member.registration_entry_link_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="注册时 AI">{member.registration_ai_agent_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="注册时员工">{member.registration_staff_user_id || "-"}</Descriptions.Item>
            <Descriptions.Item label="渠道">{member.registration_channel || "-"}</Descriptions.Item>
            <Descriptions.Item label="来源类型">{member.registration_source_type || "-"}</Descriptions.Item>
          </Descriptions>
        </section>
      </div>
    );
  };

  const renderConversations = (): JSX.Element => {
    if (conversationsLoading) return <Spin style={{ display: "block", margin: "48px auto" }} />;
    if (conversations.length === 0) {
      return <Empty description="暂无会话记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <div style={{ height: CONTENT_HEIGHT, display: "grid", gridTemplateRows: "1fr auto", gap: 12 }}>
        <div style={{ ...scrollPaneStyle, height: CONTENT_HEIGHT - 44 }}>
          <List
            size="small"
            dataSource={pagedConversations}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button
                    key="view"
                    type="link"
                    size="small"
                    onClick={() => onViewConversations({
                      public_user_id: summary?.customer.public_user_id ?? "",
                      account_id: item.account_id ?? null,
                    } as PlatformUser)}
                  >
                    打开工作台
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={(
                    <Space wrap>
                      <Text code>{item.conversation_id.slice(0, 12)}...</Text>
                      {renderStatusTag(MANAGEMENT_MODE_META[item.management_mode], item.management_mode)}
                      <Tag color={item.status === "active" ? "success" : "default"}>
                        {item.status === "active" ? "进行中" : "已关闭"}
                      </Tag>
                    </Space>
                  )}
                  description={(
                    <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12 }}>
                      <Text type="secondary" ellipsis>{item.last_message_preview || "暂无消息"}</Text>
                      <Text type="secondary">{formatDateTime(item.last_message_at)}</Text>
                    </div>
                  )}
                />
              </List.Item>
            )}
          />
        </div>
        <Pagination align="end" current={conversationPage} pageSize={CONVERSATION_PAGE_SIZE} total={conversations.length} onChange={(page) => setConversationPage(page)} showSizeChanger={false} />
      </div>
    );
  };

  const renderTickets = (): JSX.Element | null => {
    if (!summary) return null;
    if (summary.tickets.items.length === 0) {
      return <Empty description="暂无工单记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <div style={{ height: CONTENT_HEIGHT, display: "grid", gridTemplateRows: "1fr auto", gap: 12 }}>
        <div style={{ ...scrollPaneStyle, height: CONTENT_HEIGHT - 44 }}>
          <List
            size="small"
            dataSource={pagedTickets}
            renderItem={(item: Record<string, unknown>) => {
              const status = (item.status as string) || "";
              return (
                <List.Item>
                  <List.Item.Meta
                    title={(
                      <Space wrap>
                        <Text>{(item.subject as string) || (item.title as string) || "工单"}</Text>
                        {renderStatusTag(TICKET_STATUS_META[status], status)}
                      </Space>
                    )}
                    description={<Text type="secondary">{formatDate((item.updated_at as string | null) ?? (item.created_at as string | null))}{item.category ? ` / ${item.category as string}` : ""}</Text>}
                  />
                </List.Item>
              );
            }}
          />
        </div>
        <Pagination align="end" current={ticketPage} pageSize={TICKET_PAGE_SIZE} total={summary.tickets.items.length} onChange={(page) => setTicketPage(page)} showSizeChanger={false} />
      </div>
    );
  };

  const renderFinance = (): JSX.Element | null => {
    if (!summary) return null;
    if (!canViewFinance) {
      return <Alert type="info" showIcon message="需财务权限" description="当前账号没有查看客户财务信息的权限。" />;
    }

    return (
      <div style={{ height: CONTENT_HEIGHT, display: "grid", gridTemplateColumns: "320px minmax(0, 1fr)", gap: 16 }}>
        <div style={{ display: "grid", gap: 12, alignContent: "start", gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
          <div style={statCardStyle}>
            <Statistic title="总余额" value={summary.wallet.balance} prefix="¥" precision={2} />
          </div>
          <div style={statCardStyle}>
            <Statistic title="系统余额" value={summary.wallet.system_balance} prefix="¥" precision={2} />
          </div>
          <div style={statCardStyle}>
            <Statistic title="任务余额" value={summary.wallet.task_balance} prefix="¥" precision={2} />
          </div>
          <div style={statCardStyle}>
            <Statistic title="累计充值" value={summary.wallet.total_recharged} prefix="¥" precision={2} />
          </div>
          <div style={statCardStyle}>
            <Statistic title="累计提现" value={summary.wallet.total_withdrawn} prefix="¥" precision={2} />
          </div>
        </div>

        <section style={sectionCardStyle}>
          <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>流水记录</Title>
          {ledgerLoading ? (
            <Spin style={{ display: "block", margin: "40px auto" }} />
          ) : ledgerRows.length > 0 ? (
            <div style={{ height: CONTENT_HEIGHT - 60, display: "grid", gridTemplateRows: "1fr auto", gap: 12 }}>
              <div style={{ ...scrollPaneStyle, height: CONTENT_HEIGHT - 116 }}>
                <List
                  size="small"
                  dataSource={pagedLedgers}
                  renderItem={(row) => (
                    <List.Item>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 12, width: "100%", alignItems: "center" }}>
                        <Space wrap size={[8, 8]}>
                          <Text ellipsis>{getLedgerTitle(row)}</Text>
                          <Tag>{row.transaction_type === "credit" ? "入账" : row.transaction_type === "debit" ? "扣减" : row.transaction_type}</Tag>
                        </Space>
                        <Text type="secondary">{row.direction === "in" ? "+" : "-"}{formatMoney(Math.abs(row.amount))}</Text>
                        <Text type="secondary">{formatDateTime(row.created_at)}</Text>
                      </div>
                    </List.Item>
                  )}
                />
              </div>
              <Pagination align="end" current={ledgerPage} pageSize={LEDGER_PAGE_SIZE} total={ledgerRows.length} onChange={(page) => setLedgerPage(page)} showSizeChanger={false} />
            </div>
          ) : (
            <Empty description="暂无交易记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </section>
      </div>
    );
  };

  const renderTimeline = (): JSX.Element => {
    if (timelineLoading) return <Spin style={{ display: "block", margin: "48px auto" }} />;
    if (timeline.length === 0) {
      return <Empty description="暂无时间线事件" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <div style={{ height: CONTENT_HEIGHT, display: "grid", gridTemplateRows: "1fr auto", gap: 12 }}>
        <div style={{ ...scrollPaneStyle, height: CONTENT_HEIGHT - 44 }}>
          <Table
            size="small"
            rowKey={(row) => `${row.type}-${row.time}-${row.summary}`}
            pagination={false}
            dataSource={pagedTimeline}
            columns={[
              {
                title: "类型",
                dataIndex: "type",
                key: "type",
                width: 120,
                render: (value: string) => value || "-",
              },
              {
                title: "内容",
                dataIndex: "summary",
                key: "summary",
                render: (value: string) => <Text>{value}</Text>,
              },
              {
                title: "时间",
                dataIndex: "time",
                key: "time",
                width: 220,
                render: (value: string) => <Text type="secondary">{formatDateTime(value)}</Text>,
              },
            ]}
          />
        </div>
        <Pagination align="end" current={timelinePage} pageSize={TIMELINE_PAGE_SIZE} total={timeline.length} onChange={(page) => setTimelinePage(page)} showSizeChanger={false} />
      </div>
    );
  };

  const renderProfile = (): JSX.Element => {
    if (profileLoading && !profile) return <Spin style={{ display: "block", margin: "48px auto" }} />;
    if (!profile) return <Empty description="暂无画像数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    return (
      <div style={{ height: CONTENT_HEIGHT, overflowY: "auto", display: "grid", gap: 16 }}>
        {!canViewFinance ? (
          <Alert type="info" showIcon message="需财务权限" description="画像中的充值和提现金额已按权限隐藏。" />
        ) : null}
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
          <div style={statCardStyle}>
            <Statistic title="签到次数" value={profile.behavior.sign_in_count} />
          </div>
          <div style={statCardStyle}>
            <Statistic title="连续签到" value={profile.behavior.sign_in_streak} suffix="天" />
          </div>
          <div style={statCardStyle}>
            <Statistic title="充值次数" value={profile.behavior.recharge_count} />
          </div>
          <div style={statCardStyle}>
            <Statistic title="会话次数" value={profile.behavior.conversation_count} />
          </div>
          {canViewFinance ? (
            <>
              <div style={statCardStyle}>
                <Statistic title="累计充值" value={profile.behavior.recharge_total} prefix="¥" precision={2} />
              </div>
              <div style={statCardStyle}>
                <Statistic title="累计提现" value={profile.behavior.withdraw_total} prefix="¥" precision={2} />
              </div>
            </>
          ) : null}
        </div>
        <Descriptions size="small" column={1}>
          <Descriptions.Item label="最后活跃时间">{formatDateTime(profile.behavior.last_active_at)}</Descriptions.Item>
          <Descriptions.Item label="自动标签">
            <Space wrap>{profile.auto_tags.length > 0 ? profile.auto_tags.map((tag) => <Tag key={tag} color="blue">{tag}</Tag>) : <span>-</span>}</Space>
          </Descriptions.Item>
          <Descriptions.Item label="手动标签">
            <Space wrap>{profile.manual_tags.length > 0 ? profile.manual_tags.map((tag) => <Tag key={tag}>{tag}</Tag>) : <span>-</span>}</Space>
          </Descriptions.Item>
        </Descriptions>
      </div>
    );
  };

  const renderBody = (): JSX.Element => {
    if (loading && !summary) {
      return <Spin style={{ display: "block", margin: "80px auto" }} />;
    }
    if (error && !summary) {
      return (
        <div style={{ padding: 32 }}>
          <Alert type="error" showIcon message="加载失败" description={error} action={<Button size="small" onClick={() => void reloadAll()}>重试</Button>} />
        </div>
      );
    }
    return (
      <div style={{ display: "grid", gap: 20, gridTemplateColumns: "320px minmax(0, 1fr)", minHeight: CONTENT_HEIGHT, maxHeight: CONTENT_HEIGHT, overflow: "hidden" }}>
        <aside style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <section style={{ background: "#fff", border: "1px solid #e8e1d4", borderRadius: 18, padding: 18 }}>
            <Title level={4} style={{ marginTop: 0, marginBottom: 8 }}>
              {summary?.customer.display_name || summary?.customer.public_user_id || "客户详情"}
            </Title>
            {summary ? (
              <Space wrap size={[8, 8]} style={{ marginBottom: 12 }}>
                {renderStatusTag(LIFECYCLE_META[summary.customer.lifecycle_status], summary.customer.lifecycle_status)}
                {renderStatusTag(VERIFICATION_META[summary.member_status.verification.status], summary.member_status.verification.status)}
                {renderStatusTag(BINDING_META[summary.member_status.whatsapp_binding.status], summary.member_status.whatsapp_binding.status)}
              </Space>
            ) : null}
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="公开用户 ID">
                {summary ? renderMemberIdBlock(accountId, summary.customer.id, summary.customer.public_user_id) : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="账号">{accountId || "-"}</Descriptions.Item>
              <Descriptions.Item label="注册时间">{formatDateTime(summary?.customer.created_at)}</Descriptions.Item>
            </Descriptions>
          </section>

          <section style={{ background: "#fff", border: "1px solid #e8e1d4", borderRadius: 18, padding: 18 }}>
            <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>快捷操作</Title>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Button block type="primary" onClick={handleViewConversations}>查看会话</Button>
              <Button block icon={<ReloadOutlined />} loading={loading || timelineLoading || profileLoading || ledgerLoading} onClick={() => void reloadAll()}>刷新资料</Button>
              <Button block icon={<CopyOutlined />} onClick={() => void copyText(summary?.customer.id ?? "", "已复制客户ID")}>复制客户 ID</Button>
              <Button block icon={<CopyOutlined />} onClick={() => void copyText(summary?.customer.public_user_id ?? "", "已复制公开用户ID")}>复制公开用户 ID</Button>
              <Button
                block
                danger={summary?.customer.lifecycle_status !== "blacklisted"}
                icon={summary?.customer.lifecycle_status === "blacklisted" ? <UnlockOutlined /> : <StopOutlined />}
                loading={actionLoading}
                onClick={handleToggleBlacklist}
              >
                {summary?.customer.lifecycle_status === "blacklisted" ? "解除黑名单" : "拉黑客户"}
              </Button>
            </Space>
          </section>
        </aside>

        <section style={{ minWidth: 0, overflow: "hidden" }}>
          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as TabKey)}
            items={TAB_ITEMS.map((item) => ({
              key: item.key,
              label: item.label,
              children:
                item.key === "overview"
                  ? renderOverview()
                  : item.key === "attribution"
                    ? renderAttribution()
                    : item.key === "conversations"
                      ? renderConversations()
                      : item.key === "tickets"
                        ? renderTickets()
                        : item.key === "finance"
                          ? renderFinance()
                          : item.key === "timeline"
                            ? renderTimeline()
                            : renderProfile(),
            }))}
          />
        </section>
      </div>
    );
  };

  return (
    <Modal
      title={(
        <Space size={12}>
          <UserOutlined />
          <span>客户详情</span>
        </Space>
      )}
      open={open}
      onCancel={onClose}
      footer={null}
      width={1120}
      centered
      destroyOnClose={false}
      styles={{
        body: {
          background: "linear-gradient(180deg, #fcfaf6 0%, #f7f1e7 100%)",
          maxHeight: "calc(100dvh - 120px)",
          overflow: "auto",
          padding: 20,
        },
      }}
    >
      {renderBody()}
    </Modal>
  );
}

export default CustomerDetailDrawer;
