import { useCallback, useEffect, useState, type JSX } from "react";
import { Alert, Button, Descriptions, Divider, Drawer, Empty, List, Space, Spin, Statistic, Tag, Tabs, Typography, message } from "antd";
import {
  BlockOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  DollarOutlined,
  ExclamationCircleOutlined,
  FieldTimeOutlined,
  LoadingOutlined,
  MessageOutlined,
  PhoneOutlined,
  SafetyOutlined,
  ShoppingCartOutlined,
  StopOutlined,
  UserOutlined,
  WhatsAppOutlined,
} from "@ant-design/icons";
import {
  getCustomerSummary,
  getCustomerTimeline,
  batchUpdateCustomerLifecycle,
  listCustomerConversations,
  getCustomerProfile,
} from "../services/api";
import { showSuccess, showError } from "../components/Feedback";
import type {
  CustomerSummaryResponse,
  TimelineEvent,
  PlatformUser,
  CustomerConversationBrief,
  CustomerProfile,
} from "../services/api";

// ── Constants ──

const TAB_KEYS = [
  "overview",
  "attribution",
  "conversations",
  "tickets",
  "finance",
  "timeline",
  "profile",
] as const;
type TabKey = (typeof TAB_KEYS)[number];

const TAB_LABELS: Record<TabKey, string> = {
  overview: "概览",
  attribution: "归属",
  conversations: "会话列表",
  tickets: "工单列表",
  finance: "财务",
  timeline: "时间线",
  profile: "客户画像",
};

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

const VERIFY_LABELS: Record<string, string> = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
  not_submitted: "未提交",
};
const VERIFY_COLORS: Record<string, string> = {
  pending: "orange",
  approved: "green",
  rejected: "red",
  not_submitted: "default",
};

const BINDING_LABELS: Record<string, string> = {
  pending: "待绑定",
  bound: "已绑定",
  unbound: "未绑定",
  rejected: "已拒绝",
};
const BINDING_COLORS: Record<string, string> = {
  pending: "orange",
  bound: "green",
  unbound: "default",
  rejected: "red",
};

const TIMELINE_ICONS: Record<string, React.ReactNode> = {
  conversation: <MessageOutlined style={{ color: "#1677ff" }} />,
  message: <MessageOutlined style={{ color: "#52c41a" }} />,
  ticket: <ShoppingCartOutlined style={{ color: "#faad14" }} />,
  verification: <SafetyOutlined style={{ color: "#722ed1" }} />,
  whatsapp_binding: <WhatsAppOutlined style={{ color: "#25D366" }} />,
  wallet: <DollarOutlined style={{ color: "#52c41a" }} />,
  withdrawal: <DollarOutlined style={{ color: "#ff4d4f" }} />,
};

const MANAGEMENT_LABELS: Record<string, string> = {
  ai_managed: "AI 托管",
  human_managed: "人工接管",
  paused: "暂停",
};

// ── Props ──

export interface CustomerDetailDrawerProps {
  open: boolean;
  customerId: string | null;
  accountId?: string;
  onClose: () => void;
  onViewConversations: (user: PlatformUser) => void;
}

// ── Component ──

export function CustomerDetailDrawer({
  open,
  customerId,
  accountId,
  onClose,
  onViewConversations,
}: CustomerDetailDrawerProps): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [summary, setSummary] = useState<CustomerSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineLimit, setTimelineLimit] = useState(20);
  const [conversations, setConversations] = useState<CustomerConversationBrief[]>([]);
  const [convLoading, setConvLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // IV-FE-004: 客户画像
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // ── Data loaders ──

  const loadSummary = useCallback(async (id: string, accId?: string) => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await getCustomerSummary(id, accId);
      setSummary(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "加载客户详情失败";
      setSummaryError(msg);
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const loadTimeline = useCallback(
    async (id: string, accId?: string, limit?: number) => {
      setTimelineLoading(true);
      try {
        const data = await getCustomerTimeline(id, {
          account_id: accId,
          limit: limit ?? timelineLimit,
        });
        setTimeline(data.events);
      } catch {
        // silently ignore
      } finally {
        setTimelineLoading(false);
      }
    },
    [timelineLimit],
  );

  const loadProfile = useCallback(async (id: string, accId?: string) => {
    setProfileLoading(true);
    try {
      const data = await getCustomerProfile(id, accId);
      setProfile(data);
    } catch { /* ignore */ }
    finally { setProfileLoading(false); }
  }, []);

  const loadConversations = useCallback(
    async (id: string, accId: string) => {
      setConvLoading(true);
      try {
        const data = await listCustomerConversations(accId, id, undefined, 50);
        setConversations(data);
      } catch {
        // silently ignore
      } finally {
        setConvLoading(false);
      }
    },
    [],
  );

  // ── Effects ──

  useEffect(() => {
    if (open && customerId) {
      setActiveTab("overview");
      void loadSummary(customerId, accountId);
      void loadTimeline(customerId, accountId);
      void loadProfile(customerId, accountId);
      if (accountId) {
        void loadConversations(customerId, accountId);
      }
    } else {
      setSummary(null);
      setTimeline([]);
      setConversations([]);
      setProfile(null);
      setTimelineLimit(20);
    }
  }, [open, customerId, accountId, loadSummary, loadTimeline, loadConversations]);

  // ── Handlers ──

  const handleBlock = async () => {
    if (!customerId) return;
    setActionLoading(true);
    try {
      await batchUpdateCustomerLifecycle({
        customer_ids: [customerId],
        lifecycle_status: "blacklisted",
        account_id: accountId,
      });
      showSuccess("已拉黑该客户");
      void loadSummary(customerId, accountId);
    } catch {
      showError("拉黑失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnblock = async () => {
    if (!customerId) return;
    setActionLoading(true);
    try {
      await batchUpdateCustomerLifecycle({
        customer_ids: [customerId],
        lifecycle_status: "active",
        account_id: accountId,
      });
      showSuccess("已解封该客户");
      void loadSummary(customerId, accountId);
    } catch {
      showError("解封失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleViewConversations = () => {
    if (!summary) return;
    onViewConversations({
      public_user_id: summary.customer.public_user_id,
      account_id: accountId ?? null,
    } as PlatformUser);
  };

  // ── Tab renderers ──

  const renderOverview = () => {
    if (!summary) return null;
    const { customer, member_status, wallet, conversations: convs, tickets: tcks, tags } = summary;

    return (
      <div style={{ padding: "0 4px" }}>
        {/* Basic info */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          <UserOutlined style={{ marginRight: 4 }} />基本信息
        </Typography.Text>
        <Descriptions size="small" column={1} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="用户ID">{customer.public_user_id}</Descriptions.Item>
          <Descriptions.Item label="名称">{customer.display_name || "-"}</Descriptions.Item>
          <Descriptions.Item label="语言">{customer.language || "-"}</Descriptions.Item>
          <Descriptions.Item label="注册时间">
            {customer.created_at
              ? new Date(customer.created_at).toLocaleString("zh-CN")
              : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="注册IP">
            {customer.registration_ip || "-"}
            {customer.multi_ip && (
              <Tag color="warning" style={{ marginLeft: 6, fontSize: 10 }}>
                ⚠️ {customer.registration_ips?.length ?? 2}个不同IP
              </Tag>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="标签">
            {tags.length > 0
              ? tags.map((t) => <Tag key={t} style={{ fontSize: 10 }}>{t}</Tag>)
              : "-"}
          </Descriptions.Item>
        </Descriptions>

        <Divider style={{ margin: "8px 0" }} />

        {/* Verification status */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          <SafetyOutlined style={{ marginRight: 4 }} />认证状态
        </Typography.Text>
        <Descriptions size="small" column={1} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="实名认证">
            <Tag
              color={VERIFY_COLORS[member_status.verification.status] ?? "default"}
              style={{ fontSize: 10 }}
            >
              {member_status.verification.request_type ?? ""}{" "}
              {VERIFY_LABELS[member_status.verification.status] ?? member_status.verification.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {member_status.verification.updated_at
              ? new Date(member_status.verification.updated_at).toLocaleDateString("zh-CN")
              : "-"}
          </Descriptions.Item>
        </Descriptions>

        <Divider style={{ margin: "8px 0" }} />

        {/* WhatsApp binding */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          <WhatsAppOutlined style={{ marginRight: 4 }} />WhatsApp 绑定
        </Typography.Text>
        <Descriptions size="small" column={1} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="绑定状态">
            <Tag
              color={BINDING_COLORS[member_status.whatsapp_binding.status] ?? "default"}
              style={{ fontSize: 10 }}
            >
              {BINDING_LABELS[member_status.whatsapp_binding.status] ??
                member_status.whatsapp_binding.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="手机号">
            {member_status.whatsapp_binding.phone_number || "-"}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {member_status.whatsapp_binding.updated_at
              ? new Date(member_status.whatsapp_binding.updated_at).toLocaleDateString("zh-CN")
              : "-"}
          </Descriptions.Item>
        </Descriptions>

        <Divider style={{ margin: "8px 0" }} />

        {/* Stats summary */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          <FieldTimeOutlined style={{ marginRight: 4 }} />统计摘要
        </Typography.Text>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 8,
            marginBottom: 12,
          }}
        >
          <Statistic
            title="总会话"
            value={convs.total}
            prefix={<MessageOutlined />}
            valueStyle={{ fontSize: 18 }}
          />
          <Statistic
            title="进行中"
            value={convs.open}
            prefix={<LoadingOutlined />}
            valueStyle={{ fontSize: 18, color: "#1677ff" }}
          />
          <Statistic
            title="工单"
            value={tcks.total}
            prefix={<ShoppingCartOutlined />}
            valueStyle={{ fontSize: 18 }}
          />
          <Statistic
            title="余额"
            value={wallet.balance}
            prefix="¥"
            precision={2}
            valueStyle={{ fontSize: 18, color: wallet.balance > 0 ? "#52c41a" : "#999" }}
          />
          <Statistic
            title="累计充值"
            value={wallet.total_recharged}
            prefix="¥"
            precision={2}
            valueStyle={{ fontSize: 18, color: "#52c41a" }}
          />
          <Statistic
            title="累计提现"
            value={wallet.total_withdrawn}
            prefix="¥"
            precision={2}
            valueStyle={{ fontSize: 18, color: "#ff4d4f" }}
          />
        </div>

        <Divider style={{ margin: "8px 0" }} />

        {/* Action buttons */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          <BlockOutlined style={{ marginRight: 4 }} />操作区
        </Typography.Text>
        <Space wrap>
          {customer.lifecycle_status === "blacklisted" ? (
            <Button
              size="small"
              icon={<CheckCircleOutlined />}
              onClick={() => void handleUnblock()}
              loading={actionLoading}
            >
              解封
            </Button>
          ) : (
            <Button
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => void handleBlock()}
              loading={actionLoading}
            >
              拉黑
            </Button>
          )}
          <Button
            size="small"
            icon={<MessageOutlined />}
            onClick={handleViewConversations}
          >
            查看会话
          </Button>
          <Button
            size="small"
            icon={<PhoneOutlined />}
            onClick={() => {
              void message.info("发消息功能即将上线");
            }}
          >
            发消息
          </Button>
        </Space>

      {/* ── 任务概览 ── */}
      <Divider style={{ margin: "8px 0" }} />
      <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
        <ShoppingCartOutlined style={{ marginRight: 4 }} />任务概览
      </Typography.Text>
      <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
        <Typography.Text style={{ fontSize: 12 }}>进行中: <span style={{ color: "#1677ff", fontWeight: 600 }}>2</span> 个</Typography.Text>
        <Typography.Text style={{ fontSize: 12 }}>已完成: <span style={{ color: "#52c41a", fontWeight: 600 }}>15</span> 个</Typography.Text>
        <Typography.Text style={{ fontSize: 12 }}>失败: <span style={{ color: "#ff4d4f", fontWeight: 600 }}>3</span> 个</Typography.Text>
      </div>
      <div style={{ fontSize: 12, lineHeight: 2 }}>
        <div>📦 新人大礼包  进度 3/5  started 6/15</div>
        <div>📦 充值奖励包  进度 1/3  started 6/14</div>
      </div>
      <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>最近完成</Typography.Text>
      <div style={{ fontSize: 12, color: "#52c41a" }}>✅ 每日精选包  6/12 完成</div>

      {/* ── 签到信息 ── */}
      <Divider style={{ margin: "8px 0" }} />
      <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
        <FieldTimeOutlined style={{ marginRight: 4 }} />签到信息
      </Typography.Text>
      <div style={{ fontSize: 12, lineHeight: 2 }}>
        <div>今日: ✅ 已签到</div>
        <div>连续天数: 5 天</div>
        <div>累计签到: 30 天</div>
        <div>签到任务: 进行中 (目标 7 天)</div>
      </div>

      {/* ── 邀请信息 ── */}
      <Divider style={{ margin: "8px 0" }} />
      <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
        <UserOutlined style={{ marginRight: 4 }} />邀请信息
      </Typography.Text>
      <div style={{ fontSize: 12, lineHeight: 2 }}>
        <div>成功邀请: 8 人</div>
        <div>邀请链接: https://h5.example.com/register?ref=ABC123</div>
      </div>
      <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 4 }}>邀请明细</Typography.Text>
      <div style={{ fontSize: 12, lineHeight: 2 }}>
        <div>U12345 注册 6/10 +¥2.00</div>
        <div>U12346 注册+充值 6/8 +¥5.00</div>
      </div>

      {/* ── 商品包记录 ── */}
      <Divider style={{ margin: "8px 0" }} />
      <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
        <ShoppingCartOutlined style={{ marginRight: 4 }} />商品包记录
      </Typography.Text>
      <div style={{ fontSize: 12, lineHeight: 2 }}>
        <div>📦 新人大礼包  进度 3/5  <Tag color="blue" style={{ fontSize: 10 }}>进行中</Tag></div>
        <div>📦 每日精选    5/5  <Tag color="green" style={{ fontSize: 10 }}>已完成</Tag></div>
        <div>📦 充值奖励    0/3  <Tag color="red" style={{ fontSize: 10 }}>已过期</Tag></div>
      </div>
      </div>
    );
  };

  const renderAttribution = () => {
    // summary 来自 /api/customers/{id}/summary，含 member_profile 字段（spec 5.7）。
    const member = summary?.member_profile ?? null;
    const ownerId = member?.current_owner_staff_user_id ?? null;
    const ownerAgencyId = member?.current_owner_agency_id ?? null;
    const ownerAssignmentId = member?.current_owner_assignment_id ?? null;
    const aiId = member?.current_ai_agent_id ?? null;
    const aiAssignmentId = member?.current_ai_assignment_id ?? null;
    const entryLinkId = member?.registration_entry_link_id ?? null;
    const registrationAiId = member?.registration_ai_agent_id ?? null;
    const registrationStaffId = member?.registration_staff_user_id ?? null;
    const channel = member?.registration_channel ?? null;
    const sourceType = member?.registration_source_type ?? null;
    const status = member?.attribution_status ?? null;
    const ownerAssignedAt = member?.owner_assigned_at ?? null;
    const aiAssignedAt = member?.ai_assigned_at ?? null;
    const memberNo = member?.member_no ?? null;
    const memberProfileId = member?.member_profile_id ?? null;
    if (!member || !memberProfileId) {
      return (
        <Empty
          description="该客户尚未生成 MemberProfile（未走 H5 注册流 / 未绑定 AI / 未分配客服）"
          style={{ marginTop: 48 }}
        />
      );
    }
    return (
      <Space direction="vertical" size="middle" style={{ width: "100%" }}>
        <Descriptions
          size="small"
          column={1}
          title="当前人力归属"
          bordered
          items={[
            { key: "member_no", label: "会员号", children: memberNo ?? "—" },
            {
              key: "owner",
              label: "客服",
              children: ownerId ? <Tag color="geekblue">{ownerId}</Tag> : <Tag>未归属</Tag>,
            },
            { key: "owner_agency", label: "代理商", children: ownerAgencyId ?? "—" },
            {
              key: "owner_assignment",
              label: "Assignment ID",
              children: ownerAssignmentId ?? "—",
            },
            {
              key: "owner_assigned_at",
              label: "开始时间",
              children: ownerAssignedAt ?? "—",
            },
            {
              key: "status",
              label: "归属状态",
              children: status ? <Tag color="blue">{status}</Tag> : "—",
            },
          ]}
        />
        <Descriptions
          size="small"
          column={1}
          title="当前 AI 归属"
          bordered
          items={[
            { key: "ai", label: "AI Agent", children: aiId ?? "未绑定" },
            { key: "ai_asg", label: "AI Assignment", children: aiAssignmentId ?? "—" },
            { key: "ai_assigned_at", label: "绑定时间", children: aiAssignedAt ?? "—" },
          ]}
        />
        <Descriptions
          size="small"
          column={1}
          title="注册入口（首单归因）"
          bordered
          items={[
            { key: "entry_link", label: "EntryLink", children: entryLinkId ?? "无入口" },
            { key: "reg_ai", label: "注册时 AI", children: registrationAiId ?? "—" },
            { key: "reg_staff", label: "注册时 Staff", children: registrationStaffId ?? "—" },
            { key: "channel", label: "渠道", children: channel ?? "—" },
            { key: "source_type", label: "来源类型", children: sourceType ?? "—" },
          ]}
        />
        <Alert
          type="info"
          showIcon
          message="归属说明"
          description={
            <ul style={{ marginBottom: 0, paddingLeft: 18 }}>
              <li>当前列表看 current_*（实时状态）。</li>
              <li>历史消息和报表看 *_snapshot（划转不会回填历史）。</li>
              <li>未归属 / 未绑定 AI / 无入口 都不阻塞主消息链路，但部分 AI 自动能力受限。</li>
            </ul>
          }
        />
      </Space>
    );
  };

  const renderConversations = () => {
    if (convLoading) return <Spin style={{ display: "block", margin: "48px auto" }} />;
    if (conversations.length === 0) {
      return <Empty description="暂无会话记录" />;
    }
    return (
      <List
        size="small"
        dataSource={conversations}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button
                key="view"
                size="small"
                type="link"
                onClick={() =>
                  onViewConversations({
                    public_user_id: customerId ?? "",
                    account_id: item.account_id ?? null,
                  } as PlatformUser)
                }
              >
                跳转到工作台 →
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={
                <Space size={4}>
                  <Typography.Text copyable style={{ fontSize: 12 }}>
                    {item.conversation_id.slice(0, 12)}...
                  </Typography.Text>
                  <Tag
                    color={
                      item.management_mode === "human_managed"
                        ? "blue"
                        : item.management_mode === "paused"
                          ? "orange"
                          : "green"
                    }
                    style={{ fontSize: 10, margin: 0 }}
                  >
                    {MANAGEMENT_LABELS[item.management_mode] ?? item.management_mode}
                  </Tag>
                  <Tag color={item.status === "active" ? "green" : "default"} style={{ fontSize: 10, margin: 0 }}>
                    {item.status === "active" ? "进行中" : "已关闭"}
                  </Tag>
                </Space>
              }
              description={
                <div style={{ fontSize: 12, color: "#999" }}>
                  {item.last_message_preview
                    ? item.last_message_preview.slice(0, 60)
                    : "暂无消息"}
                  {item.last_message_at && (
                    <span style={{ marginLeft: 8 }}>
                      {new Date(item.last_message_at).toLocaleDateString("zh-CN")}
                    </span>
                  )}
                </div>
              }
            />
          </List.Item>
        )}
      />
    );
  };

  const renderTickets = () => {
    if (!summary) return null;
    const tickets = summary.tickets.items;
    if (tickets.length === 0) {
      return (
        <div style={{ padding: 24, textAlign: "center", color: "#999" }}>
          <ShoppingCartOutlined style={{ fontSize: 32, display: "block", marginBottom: 8 }} />
          <Typography.Text type="secondary">暂无工单记录</Typography.Text>
        </div>
      );
    }
    return (
      <List
        size="small"
        dataSource={tickets}
        renderItem={(item: Record<string, unknown>) => {
          const status = (item.status as string) ?? "";
          const subject = (item.subject as string) ?? "工单";
          const updatedAt = (item.updated_at as string) ?? "";
          const statusColor: Record<string, string> = {
            open: "#ff4d4f",
            in_progress: "#1677ff",
            pending_user: "#faad14",
            resolved: "#52c41a",
            closed: "#d9d9d9",
            rejected: "#999",
          };
          const statusLabel: Record<string, string> = {
            open: "待处理",
            in_progress: "处理中",
            pending_user: "待补充",
            resolved: "已解决",
            closed: "已关闭",
            rejected: "已拒绝",
          };
          return (
            <List.Item>
              <List.Item.Meta
                title={
                  <Space size={4}>
                    <Typography.Text style={{ fontSize: 13 }}>{subject}</Typography.Text>
                    <Tag color={statusColor[status] ?? "default"} style={{ fontSize: 10, margin: 0 }}>
                      {statusLabel[status] ?? status}
                    </Tag>
                  </Space>
                }
                description={
                  <Typography.Text style={{ fontSize: 12, color: "#999" }}>
                    {updatedAt ? new Date(updatedAt).toLocaleDateString("zh-CN") : ""}
                    {item.category ? ` · ${item.category as string}` : ""}
                  </Typography.Text>
                }
              />
            </List.Item>
          );
        }}
      />
    );
  };

  const renderFinance = () => {
    if (!summary) return null;
    const { wallet } = summary;
    return (
      <div style={{ padding: "0 4px" }}>
        {/* Balance */}
        <div
          style={{
            textAlign: "center",
            padding: "24px 0",
            background: "#f5f5f5",
            borderRadius: 8,
            marginBottom: 16,
          }}
        >
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            当前余额
          </Typography.Text>
          <div style={{ fontSize: 36, fontWeight: 700, color: wallet.balance > 0 ? "#52c41a" : "#333" }}>
            ¥{wallet.balance.toFixed(2)}
          </div>
        </div>

        {/* Summary */}
        <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="累计充值">
            <Typography.Text style={{ color: "#52c41a" }}>
              +¥{wallet.total_recharged.toFixed(2)}
            </Typography.Text>
          </Descriptions.Item>
          <Descriptions.Item label="累计提现">
            <Typography.Text style={{ color: "#ff4d4f" }}>
              -¥{wallet.total_withdrawn.toFixed(2)}
            </Typography.Text>
          </Descriptions.Item>
        </Descriptions>

        <Divider style={{ margin: "8px 0" }} />

        {/* Recent transactions */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />最近交易
        </Typography.Text>
        {wallet.recent_transactions.length === 0 ? (
          <Empty description="暂无交易记录" />
        ) : (
          <List
            size="small"
            dataSource={wallet.recent_transactions}
            renderItem={(tx) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space size={4}>
                      <Typography.Text
                        style={{
                          color: tx.direction === "in" ? "#52c41a" : "#ff4d4f",
                          fontWeight: 600,
                        }}
                      >
                        {tx.direction === "in" ? "+" : "-"}¥{Math.abs(tx.amount).toFixed(2)}
                      </Typography.Text>
                      <Tag style={{ fontSize: 10, margin: 0 }}>{tx.type}</Tag>
                    </Space>
                  }
                  description={
                    <Typography.Text style={{ fontSize: 11, color: "#999" }}>
                      {tx.created_at
                        ? new Date(tx.created_at).toLocaleDateString("zh-CN")
                        : ""}
                    </Typography.Text>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>
    );
  };

  const renderTimeline = () => {
    if (timelineLoading && timeline.length === 0) {
      return <Spin style={{ display: "block", margin: "48px auto" }} />;
    }
    if (timeline.length === 0) {
      return (
        <div style={{ padding: 24, textAlign: "center", color: "#999" }}>
          <FieldTimeOutlined style={{ fontSize: 32, display: "block", marginBottom: 8 }} />
          <Typography.Text type="secondary">暂无时间线事件</Typography.Text>
        </div>
      );
    }
    return (
      <div>
        <List
          size="small"
          dataSource={timeline}
          renderItem={(event) => (
            <List.Item>
              <List.Item.Meta
                avatar={
                  <div style={{ fontSize: 18, lineHeight: "36px" }}>
                    {TIMELINE_ICONS[event.type] ?? (
                      <ExclamationCircleOutlined style={{ color: "#999" }} />
                    )}
                  </div>
                }
                title={
                  <Space size={4}>
                    <Typography.Text style={{ fontSize: 12 }}>{event.summary}</Typography.Text>
                  </Space>
                }
                description={
                  <Typography.Text style={{ fontSize: 11, color: "#999" }}>
                    {event.time ? new Date(event.time).toLocaleString("zh-CN") : ""}
                  </Typography.Text>
                }
              />
            </List.Item>
          )}
        />
        {timeline.length >= timelineLimit && (
          <div style={{ textAlign: "center", padding: 12 }}>
            <Button
              size="small"
              type="link"
              loading={timelineLoading}
              onClick={() => {
                const newLimit = timelineLimit + 20;
                setTimelineLimit(newLimit);
                if (customerId) {
                  void loadTimeline(customerId, accountId, newLimit);
                }
              }}
            >
              加载更多...
            </Button>
          </div>
        )}
      </div>
    );
  };

  // IV-FE-004: 客户画像 Tab
  const renderProfile = () => {
    if (profileLoading && !profile) {
      return <Spin style={{ display: "block", margin: "48px auto" }} />;
    }
    if (!profile) {
      return (
        <div style={{ padding: 24, textAlign: "center", color: "#999" }}>
          <UserOutlined style={{ fontSize: 32, display: "block", marginBottom: 8 }} />
          <Typography.Text type="secondary">暂无画像数据</Typography.Text>
        </div>
      );
    }
    return (
      <div style={{ padding: "0 4px" }}>
        {/* 行为数据 */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          📊 行为数据
        </Typography.Text>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
          <Statistic title="签到次数" value={profile.behavior.sign_in_count} valueStyle={{ fontSize: 18 }} />
          <Statistic title="连续签到" value={profile.behavior.sign_in_streak} suffix="天" valueStyle={{ fontSize: 18 }} />
          <Statistic title="累计充值" value={profile.behavior.recharge_total} prefix="¥" precision={2} valueStyle={{ fontSize: 18, color: "#52c41a" }} />
          <Statistic title="充值次数" value={profile.behavior.recharge_count} valueStyle={{ fontSize: 18 }} />
          <Statistic title="累计提现" value={profile.behavior.withdraw_total} prefix="¥" precision={2} valueStyle={{ fontSize: 18, color: "#ff4d4f" }} />
          <Statistic title="会话次数" value={profile.behavior.conversation_count} valueStyle={{ fontSize: 18 }} />
        </div>
        <div style={{ marginBottom: 16 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>最后活跃：</Typography.Text>
          <Typography.Text style={{ fontSize: 12 }}>
            {profile.behavior.last_active_at
              ? new Date(profile.behavior.last_active_at).toLocaleString("zh-CN")
              : "-"}
          </Typography.Text>
        </div>

        <Divider style={{ margin: "8px 0" }} />

        {/* 标签区域 */}
        <Typography.Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          🏷️ 标签
        </Typography.Text>
        <div style={{ marginBottom: 12 }}>
          {profile.auto_tags.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>自动标签</Typography.Text>
              <Space wrap>
                {profile.auto_tags.map((t) => (
                  <Tag key={t} color="blue" style={{ fontSize: 11 }}>{t}</Tag>
                ))}
              </Space>
            </div>
          )}
          {profile.manual_tags.length > 0 && (
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginBottom: 4 }}>手动标签</Typography.Text>
              <Space wrap>
                {profile.manual_tags.map((t) => (
                  <Tag key={t} style={{ fontSize: 11 }}>{t}</Tag>
                ))}
              </Space>
            </div>
          )}
          {profile.auto_tags.length === 0 && profile.manual_tags.length === 0 && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>暂无标签</Typography.Text>
          )}
        </div>
      </div>
    );
  };

  // ── Main render ──

  const renderTabContent = (tabKey: TabKey) => {
    if (summaryLoading && !summary) {
      return <Spin style={{ display: "block", margin: "64px auto" }} />;
    }
    if (summaryError && !summary) {
      return (
        <div style={{ padding: 24, textAlign: "center" }}>
          <CloseCircleOutlined style={{ fontSize: 32, color: "#ff4d4f", display: "block", marginBottom: 8 }} />
          <Typography.Text type="danger">{summaryError}</Typography.Text>
          <div style={{ marginTop: 8 }}>
            <Button size="small" onClick={() => customerId && void loadSummary(customerId, accountId)}>
              重试
            </Button>
          </div>
        </div>
      );
    }

    switch (tabKey) {
      case "overview":
        return renderOverview();
      case "attribution":
        return renderAttribution();
      case "conversations":
        return renderConversations();
      case "tickets":
        return renderTickets();
      case "finance":
        return renderFinance();
      case "timeline":
        return renderTimeline();
      case "profile":
        return renderProfile();
      default:
        return null;
    }
  };

  return (
    <Drawer
      title={
        summary ? (
          <Space>
            <span>{summary.customer.display_name || summary.customer.public_user_id}</span>
            <Tag color={LC_COLORS[summary.customer.lifecycle_status] ?? "default"} style={{ fontSize: 10 }}>
              {LC_LABELS[summary.customer.lifecycle_status] ?? summary.customer.lifecycle_status}
            </Tag>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {summary.customer.public_user_id}
            </Typography.Text>
            {summary.customer.created_at && (
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                注册: {new Date(summary.customer.created_at).toLocaleDateString("zh-CN")}
              </Typography.Text>
            )}
          </Space>
        ) : (
          "客户详情"
        )
      }
      open={open}
      onClose={onClose}
      width={480}
      styles={{ body: { padding: 12, overflow: "auto" } }}
    >
      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key as TabKey);
          // Load additional data on tab switch if summary is available
          if (customerId && summary) {
            if (key === "conversations" && accountId && conversations.length === 0) {
              void loadConversations(customerId, accountId);
            }
            if (key === "timeline" && timeline.length === 0) {
              void loadTimeline(customerId, accountId);
            }
          }
        }}
        items={TAB_KEYS.map((key) => ({
          key,
          label: TAB_LABELS[key],
          children: renderTabContent(key),
        }))}
        size="small"
        style={{ minHeight: 300 }}
      />
    </Drawer>
  );
}

export default CustomerDetailDrawer;
