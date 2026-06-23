import { type JSX, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Alert, AutoComplete, Badge, Button, Drawer, Dropdown, Input, message, Modal, Popconfirm,
  Select, Space, Tag, Timeline, Tooltip, Typography
} from "antd";
import {
  CaretUpOutlined,
  CaretDownOutlined,
  CaretRightOutlined,
  UserOutlined,
  WalletOutlined,
  HistoryOutlined,
  ProfileOutlined,
  LockOutlined,
  StopOutlined,
  CheckCircleOutlined,
  SwapOutlined,
  TranslationOutlined,
  CloseOutlined,
  UnorderedListOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import type { ConversationSummary, RuntimeAgent, ConversationNote } from "../../services/api";
import {
  getCustomerSummary,
  getConversationTags,
  updateConversationTags,
  getConversationSentiment,
  getConversationSla,
  listCustomerConversations,
  listConversationTimeline,
} from "../../services/api";
import type { ConversationSentiment, ConversationSla, CustomerConversationBrief, ConversationTimelineItem } from "../../services/api";
import type { CustomerProfileSummary } from "../../types/operations";
import type { PlatformUserMemberStatusSnapshot } from "../../services/operations";
import type { UseMemberStatusReturn } from "../../hooks/useMemberStatus";
import { useConversationNotes } from "./hooks/useConversationNotes";
import { useAppStore } from "../../stores/appStore";

const { Text } = Typography;
const { TextArea } = Input;

export interface ConversationHeaderProps {
  conversation: ConversationSummary | null;
  customerProfile: CustomerProfileSummary | null;
  memberStatus: PlatformUserMemberStatusSnapshot | null;
  latestVerification: UseMemberStatusReturn["latestVerification"];
  latestBinding: UseMemberStatusReturn["latestBinding"];
  agents: RuntimeAgent[];
  agentOptions: { label: string; value: string }[];
  pendingAction: string | null;
  conversationStatus: string | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onHandover: () => void;
  onRestoreAI: () => void;
  onClose: () => void;
  onReopen: () => void;
  onBlock: () => void;
  onUnblock: () => void;
  onAssignAgent: (agentId: string) => void;
  onOpenFinance: () => void;
  onOpenVisitTrail: () => void;
  onOpenCustomerProfile: () => void;
  onDismissAlert: () => void;
  onBatchTranslate?: () => void;
  batchTranslating?: boolean;
  /** F-05: 打开历史会话 Drawer 回调（可选，由 ChatPage 控制导航） */
  onOpenHistory?: () => void;
  /** F-05: 点击某条历史会话，跳转到该会话 */
  onNavigateToConversation?: (accountId: string, conversationId: string) => void;
  /** F-01: 切换消息搜索栏 */
  onToggleSearch?: () => void;
  searchVisible?: boolean;
  /** F5: 内联搜索消息内容 */
  onSearchMessages?: (query: string) => void;
  /** ①a: 搜索输入文本（受控） */
  searchQuery?: string;
  /** ①a: 搜索输入变化回调 */
  onSearchChange?: (query: string) => void;
  /** ①: 搜索结果计数 */
  searchResultsCount?: number;
  /** ①: 当前搜索结果索引 */
  searchResultIndex?: number;
  /** ①: 搜索加载中 */
  searchLoading?: boolean;
  /** ①: 导航搜索结果 */
  onSearchNavigate?: (direction: "prev" | "next") => void;
  /** ①: 关闭搜索 */
  onSearchClose?: () => void;
  /** F-07: 外部强制打开备注Modal */
  forceOpenNotes?: boolean;
  onNotesOpened?: () => void;
}

function fmtTs(v: string | null | undefined): string {
  if (!v) return "-";
  const d = new Date(v);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtFull(v: string): string {
  return new Date(v).toLocaleString("zh-CN");
}

function getVerifColor(s: string | null | undefined): string {
  if (s === "approved") return "#52c41a";
  if (s === "under_review") return "#faad14";
  if (s === "rejected") return "#ff4d4f";
  return "#d9d9d9";
}

function getBindColor(s: string | null | undefined): string {
  if (s === "bound") return "#52c41a";
  if (s === "pending") return "#faad14";
  if (s === "failed") return "#ff4d4f";
  return "#d9d9d9";
}

function verifLabel(s: string | null | undefined): string {
  if (s === "approved") return "已认证";
  if (s === "under_review") return "审核中";
  if (s === "rejected") return "已拒绝";
  if (s === "pending") return "待审核";
  return "未认证";
}

function bindLabel(s: string | null | undefined): string {
  if (s === "bound") return "已绑定";
  if (s === "pending") return "待绑定";
  if (s === "failed") return "绑定失败";
  return "未绑定";
}

function getLifecycleColor(s: string): string {
  if (s === "active") return "success";
  if (s === "blacklisted") return "error";
  if (s === "frozen") return "warning";
  return "default";
}

function fmtLifecycle(s: string): string {
  if (s === "active") return "活跃";
  if (s === "blacklisted") return "已拉黑";
  if (s === "frozen") return "已冻结";
  return s;
}

function fmtLang(code: string): string {
  const map: Record<string, string> = { "zh-CN": "中文", "cn": "中文", "zh": "中文", en: "English", ja: "日本語", es: "Español" };
  return map[code] ?? code;
}

/** 国旗映射 */
const LANG_FLAG: Record<string, string> = {
  "zh-CN": "🇨🇳", "cn": "🇨🇳", "zh": "🇨🇳", en: "🇬🇧", ja: "🇯🇵", es: "🇪🇸", fr: "🇫🇷",
  de: "🇩🇪", pt: "🇧🇷", ko: "🇰🇷", ar: "🇸🇦", ru: "🇷🇺",
};

function getLangFlag(code: string): string {
  return LANG_FLAG[code] ?? "🌐";
}

/** F-12: 情绪表情 + 颜色映射 */
const SENTIMENT_CONFIG: Record<string, { emoji: string; label: string; color: string }> = {
  angry: { emoji: "😡", label: "愤怒", color: "#ff4d4f" },
  anxious: { emoji: "😰", label: "焦虑", color: "#faad14" },
  satisfied: { emoji: "😊", label: "满意", color: "#52c41a" },
  neutral: { emoji: "😐", label: "中性", color: "#999" },
};

export function ConversationHeader({
  conversation,
  customerProfile,
  memberStatus,
  latestVerification,
  latestBinding,
  agents,
  agentOptions,
  pendingAction,
  conversationStatus,
  collapsed,
  onToggleCollapse,
  onHandover,
  onRestoreAI,
  onClose,
  onReopen,
  onBlock,
  onUnblock,
  onAssignAgent,
  onOpenFinance,
  onOpenVisitTrail,
  onOpenCustomerProfile,
  onDismissAlert,
  onBatchTranslate,
  batchTranslating,
  onOpenHistory,
  onNavigateToConversation,
  onToggleSearch,
  searchVisible,
  onSearchMessages,
  searchQuery,
  onSearchChange,
  searchResultsCount,
  searchResultIndex,
  searchLoading,
  onSearchNavigate,
  onSearchClose,
  forceOpenNotes,
  onNotesOpened,
}: ConversationHeaderProps): JSX.Element | null {
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [multiIpWarning, setMultiIpWarning] = useState<string[] | null>(null);
  // F-13: 钱包余额
  const [walletInfo, setWalletInfo] = useState<{ balance: number; total_recharged: number; total_withdrawn: number } | null>(null);
  // F4: 工单计数
  const [ticketCount, setTicketCount] = useState(0);

  // ---- F-06: 会话标签 (API) ----
  const [sessionTags, setSessionTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [tagOptions, setTagOptions] = useState<{ value: string }[]>([]);

  const accountId = conversation?.account_id ?? "";
  const convId = conversation?.conversation_id ?? "";

  useEffect(() => {
    if (!accountId || !convId) { setSessionTags([]); return; }
    getConversationTags(accountId, convId)
      .then((res) => setSessionTags(res.tags ?? []))
      .catch(() => setSessionTags([]));
  }, [accountId, convId]);

  const saveTags = useCallback(async (tags: string[]) => {
    if (!accountId || !convId) return;
    setSessionTags(tags);
    try {
      await updateConversationTags(accountId, convId, tags);
      window.dispatchEvent(new CustomEvent("fx-tags-changed"));
    } catch { /* ignore */ }
  }, [accountId, convId]);

  const addTag = useCallback((v: string) => {
    const t = v.trim();
    if (t && !sessionTags.includes(t)) saveTags([...sessionTags, t]);
    setTagInput("");
  }, [sessionTags, saveTags]);

  const removeTag = useCallback((t: string) => saveTags(sessionTags.filter((x) => x !== t)), [sessionTags, saveTags]);

  // ---- F-12: 情绪 ----
  const [sentiment, setSentiment] = useState<ConversationSentiment | null>(null);
  const sentCacheRef = useRef<{ key: string; ts: number }>({ key: "", ts: 0 });

  useEffect(() => {
    if (!accountId || !convId) return;
    const cacheKey = `${accountId}:${convId}`;
    const now = Date.now();
    if (sentCacheRef.current.key === cacheKey && now - sentCacheRef.current.ts < 120_000) return;
    getConversationSentiment(accountId, convId)
      .then((s) => {
        setSentiment(s);
        sentCacheRef.current = { key: cacheKey, ts: now };
      })
      .catch(() => setSentiment(null));
  }, [accountId, convId]);

  const sentCfg = sentiment ? SENTIMENT_CONFIG[sentiment.sentiment] : null;

  // ---- F-15: SLA 计时器 ----
  const [sla, setSla] = useState<ConversationSla | null>(null);
  const [slaSeconds, setSlaSeconds] = useState(0);
  const slaTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const slaSyncRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!accountId || !convId) { setSla(null); setSlaSeconds(0); return; }
    getConversationSla(accountId, convId)
      .then((s) => {
        setSla(s);
        if (s.last_inbound_at) {
          setSlaSeconds(Math.floor((Date.now() - new Date(s.last_inbound_at).getTime()) / 1000));
        }
      })
      .catch(() => { setSla(null); setSlaSeconds(0); });
    // 每秒本地更新
    slaTimerRef.current = setInterval(() => {
      setSlaSeconds((prev) => prev + 1);
    }, 1000);
    // 每 30 秒后端同步
    slaSyncRef.current = setInterval(() => {
      if (!accountId || !convId) return;
      getConversationSla(accountId, convId)
        .then((s) => {
          setSla(s);
          if (s.last_inbound_at) {
            setSlaSeconds(Math.floor((Date.now() - new Date(s.last_inbound_at).getTime()) / 1000));
          }
        })
        .catch(() => {});
    }, 30_000);
    return () => {
      if (slaTimerRef.current) clearInterval(slaTimerRef.current);
      if (slaSyncRef.current) clearInterval(slaSyncRef.current);
    };
  }, [accountId, convId]);

  const slaColor = sla
    ? slaSeconds >= sla.threshold_critical
      ? "#ff4d4f"
      : slaSeconds >= sla.threshold_warning
        ? "#faad14"
        : "#52c41a"
    : "#999";
  const slaIsCritical = sla ? slaSeconds >= sla.threshold_critical : false;
  const slaDisplay = sla ? (() => {
    const totalSecs = slaSeconds;
    const d = Math.floor(totalSecs / 86400);
    const h = Math.floor((totalSecs % 86400) / 3600);
    const m = Math.floor((totalSecs % 3600) / 60);
    const s = totalSecs % 60;
    const parts: string[] = [];
    if (d > 0) parts.push(`${d}天`);
    if (h > 0 || parts.length > 0) parts.push(`${String(h).padStart(2, "0")}时`);
    parts.push(`${String(m).padStart(2, "0")}分`);
    parts.push(`${String(s).padStart(2, "0")}秒`);
    return parts.join("");
  })() : "--:--";

  // ---- F-02: 内部备注 (Modal) ----
  const notesHook = useConversationNotes(accountId, convId);
  const [noteText, setNoteText] = useState("");
  const [notesModalOpen, setNotesModalOpen] = useState(false);
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteContent, setEditingNoteContent] = useState("");

  const handleAddNote = useCallback(async () => {
    if (!noteText.trim()) return;
    await notesHook.addNote(noteText);
    setNoteText("");
  }, [noteText, notesHook]);

  const handleEditNote = useCallback((noteId: string, content: string) => {
    setEditingNoteId(noteId);
    setEditingNoteContent(content);
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!editingNoteId || !editingNoteContent.trim()) return;
    await notesHook.updateNote(editingNoteId, editingNoteContent);
    setEditingNoteId(null);
    setEditingNoteContent("");
  }, [editingNoteId, editingNoteContent, notesHook]);

  const handleCancelEdit = useCallback(() => {
    setEditingNoteId(null);
    setEditingNoteContent("");
  }, []);

  // F-07: 外部强制打开备注 Modal
  useEffect(() => {
    if (forceOpenNotes) {
      setNotesModalOpen(true);
      onNotesOpened?.();
    }
  }, [forceOpenNotes]);

  // ---- F-05: 历史会话 Drawer ----
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyList, setHistoryList] = useState<CustomerConversationBrief[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // F-05: 访问轨迹计数
  const [visitTrailCount, setVisitTrailCount] = useState(0);

  useEffect(() => {
    if (!accountId || !convId) { setVisitTrailCount(0); return; }
    listConversationTimeline(accountId, convId, 100).then((items: ConversationTimelineItem[]) => {
      setVisitTrailCount(items.length);
    }).catch(() => setVisitTrailCount(0));
  }, [accountId, convId]);

  useEffect(() => {
    if (!historyOpen || !accountId || !conversation?.customer_id) return;
    setHistoryLoading(true);
    listCustomerConversations(accountId, conversation.customer_id, convId, 20)
      .then(setHistoryList)
      .catch(() => setHistoryList([]))
      .finally(() => setHistoryLoading(false));
  }, [historyOpen, accountId, conversation?.customer_id, convId]);

  // ---- 多IP注册 ----
  useEffect(() => {
    if (!customerProfile?.id) {
      setMultiIpWarning(null);
      return;
    }
    getCustomerSummary(customerProfile.id, customerProfile.account_id ?? undefined)
      .then((summary) => {
        if (summary.customer.multi_ip && summary.customer.registration_ips.length > 1) {
          setMultiIpWarning(summary.customer.registration_ips);
        } else {
          setMultiIpWarning(null);
        }
        // F-13: 提取钱包信息
        setWalletInfo({
          balance: summary.wallet.balance,
          total_recharged: summary.wallet.total_recharged,
          total_withdrawn: summary.wallet.total_withdrawn,
        });
        // F4: 提取工单计数
        setTicketCount(summary.tickets?.total ?? 0);
      })
      .catch(() => { setMultiIpWarning(null); setWalletInfo(null); setTicketCount(0); });
  }, [customerProfile?.id, customerProfile?.account_id]);

  // ④: 30s 轮询刷新客户摘要（工单/轨迹/余额/认证/改名/情绪实时推送）
  useEffect(() => {
    if (!customerProfile?.id) return;
    const timer = setInterval(() => {
      // 客户摘要（余额/工单/多IP）
      getCustomerSummary(customerProfile.id, customerProfile.account_id ?? undefined)
        .then((summary) => {
          if (summary.customer.multi_ip && summary.customer.registration_ips.length > 1) {
            setMultiIpWarning(summary.customer.registration_ips);
          }
          setWalletInfo({
            balance: summary.wallet.balance,
            total_recharged: summary.wallet.total_recharged,
            total_withdrawn: summary.wallet.total_withdrawn,
          });
          setTicketCount(summary.tickets?.total ?? 0);
        })
        .catch(() => {});
      // 情绪推送
      if (accountId && convId) {
        getConversationSentiment(accountId, convId)
          .then((s) => {
            setSentiment(s);
            sentCacheRef.current = { key: `${accountId}:${convId}`, ts: Date.now() };
          })
          .catch(() => {});
      }
      // 访问轨迹计数推送
      if (accountId && convId) {
        listConversationTimeline(accountId, convId, 100)
          .then((items) => setVisitTrailCount(items.length))
          .catch(() => {});
      }
    }, 30_000);
    return () => clearInterval(timer);
  }, [customerProfile?.id, customerProfile?.account_id, accountId, convId]);

  const handleDismiss = useCallback(() => {
    setAlertDismissed(true);
    onDismissAlert();
  }, [onDismissAlert]);

  if (!conversation) return null;

  const isBlacklisted = customerProfile?.lifecycle_status === "blacklisted";
  const isHuman = conversation.management_mode === "human_managed";
  const isAiManaged = conversation.management_mode === "ai_managed";
  const isPaused = conversation.management_mode === "paused";
  const isClosed = conversationStatus === "closed";
  const recommended = conversation.latest_handover_recommended;
  const showAlert = recommended && !isHuman && !alertDismissed;

  const verifStatus = latestVerification?.status ?? null;
  const bindStatus = latestBinding?.status ?? null;

  return (
    <div
      style={{
        borderBottom: "1px solid #f0f0f0",
        background: isBlacklisted ? "#fff2f0" : "#fafafa",
        flexShrink: 0,
        transition: "max-height 0.2s",
        overflow: collapsed ? "hidden" : "hidden auto",
        maxHeight: collapsed ? 40 : "none",
      }}
    >
      {/* 折叠栏：左侧信息 + 右侧操作 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          padding: "6px 12px",
          userSelect: "none",
          gap: 8,
        }}
      >
        {/* 左侧：客户信息区 — 点击折叠 */}
        <div
          style={{ display: "flex", alignItems: "center", cursor: "pointer", flex: 1, minWidth: 0, overflow: "hidden" }}
          onClick={onToggleCollapse}
        >
          {/* 折叠箭头 */}
          {collapsed
            ? <CaretRightOutlined style={{ fontSize: 10, marginRight: 4, flexShrink: 0 }} />
            : <CaretDownOutlined style={{ fontSize: 10, marginRight: 4, flexShrink: 0 }} />
          }
          {/* 国旗图标 */}
          <Tooltip title={fmtLang(customerProfile?.language_code ?? conversation.customer_language)}>
            <span style={{ fontSize: 14, flexShrink: 0, marginRight: 2 }}>{getLangFlag(customerProfile?.language_code ?? conversation.customer_language)}</span>
          </Tooltip>
          <Text strong style={{ fontSize: 13, whiteSpace: "nowrap", cursor: "pointer", userSelect: "text" }}
            title="点击复制"
            onClick={(e) => { e.stopPropagation(); const v = customerProfile?.display_name ?? conversation.customer_id.slice(0, 12); navigator.clipboard.writeText(v).then(() => message.success("已复制")).catch(() => {}); }}
          >
            {customerProfile?.display_name ?? conversation.customer_id.slice(0, 12)}
          </Text>
          <Text type="secondary" style={{ fontSize: 11, whiteSpace: "nowrap", cursor: "pointer", userSelect: "text" }}
            title="点击复制"
            onClick={(e) => { e.stopPropagation(); const v = customerProfile?.public_user_id ?? conversation.customer_id.slice(0, 16); navigator.clipboard.writeText(v).then(() => message.success("已复制")).catch(() => {}); }}
          >
            · {customerProfile?.public_user_id ?? conversation.customer_id.slice(0, 16)}
          </Text>
          {/* 认证状态圆点 */}
          <Tooltip title={verifLabel(verifStatus)}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", backgroundColor: getVerifColor(verifStatus), display: "inline-block", flexShrink: 0, marginLeft: 2 }} />
          </Tooltip>
          {/* WhatsApp绑定状态圆点 */}
          <Tooltip title={bindLabel(bindStatus)}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", backgroundColor: getBindColor(bindStatus), display: "inline-block", flexShrink: 0 }} />
          </Tooltip>
          {/* F-12: 情绪指示器 */}
          {sentCfg && (
            <Tooltip title={`${sentCfg.label} · 置信度 ${Math.round((sentiment?.confidence ?? 0) * 100)}% · ${sentiment?.summary ?? ""}`}>
              <span style={{ fontSize: 14, flexShrink: 0, cursor: "default" }}>{sentCfg.emoji}</span>
            </Tooltip>
          )}
          {/* F-15: SLA 计时器（精简：仅超时显示秒） */}
          {sla && (
            <Tooltip title={`等待 ${slaSeconds}s / 预警 ${sla.threshold_warning}s / 超时 ${sla.threshold_critical}s`}>
              <Text
                style={{
                  fontSize: 11,
                  fontFamily: "monospace",
                  color: slaColor,
                  flexShrink: 0,
                  ...(slaIsCritical ? { animation: "sla-pulse 1s ease-in-out infinite" } : {}),
                }}
              >
                ⏱{slaIsCritical ? slaDisplay : (() => { const m = Math.floor(slaSeconds / 60); const h = Math.floor(m / 60); return h > 0 ? `${h}时${m % 60}分` : `${m}分`; })()}
              </Text>
            </Tooltip>
          )}
        </div>
        {/* 右侧：操作按钮 */}
        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 4 }} onClick={(e) => e.stopPropagation()}>
          <Select
            size="small"
            options={agentOptions}
            placeholder="转接"
            value={conversation.assigned_agent_id || undefined}
            onChange={(v) => onAssignAgent(v)}
            style={{ width: 100 }}
          />
          {isClosed ? (
            <Popconfirm title="确认重新打开" description="打开后恢复为 AI 托管" onConfirm={onReopen} okText="确认" cancelText="取消">
              <Button size="small" icon={<CheckCircleOutlined />} loading={pendingAction === "reopen"}>打开会话</Button>
            </Popconfirm>
          ) : (
            <>
              {isHuman && (
                <Popconfirm title="确认恢复 AI 托管" description="AI 将重新接管自动回复" onConfirm={onRestoreAI} okText="确认" cancelText="取消">
                  <Button size="small" icon={<SwapOutlined />} loading={pendingAction === "mode:ai_managed"}>
                    恢复AI
                  </Button>
                </Popconfirm>
              )}
              <Popconfirm title="确认关闭会话" description="关闭后该会话将归档" onConfirm={onClose} okText="确认" cancelText="取消">
                <Button size="small" icon={<LockOutlined />} loading={pendingAction === "close"}>
                  关闭
                </Button>
              </Popconfirm>
            </>
          )}
          {/* 更多▼下拉菜单 */}
          <Dropdown menu={{
            items: [
              { key: "notes", label: `📝 备注${notesHook.notes.length > 0 ? ` (${notesHook.notes.length})` : ""}`, onClick: () => setNotesModalOpen(true) },
              { key: "history", label: "📋 历史会话", onClick: () => { if (onOpenHistory) onOpenHistory(); else setHistoryOpen(true); } },
              ...(onBatchTranslate && conversation.customer_language !== "zh-CN"
                ? [{ key: "translate", label: "🌐 翻译全部", onClick: () => onBatchTranslate?.() }]
                : []),
              ...(isBlacklisted
                ? [{ key: "unblock", label: "✅ 取消黑名单", onClick: onUnblock }]
                : [{ key: "block", label: "🚫 设为黑名单", onClick: onBlock }]
              ),
            ],
          }} trigger={["click"]}>
            <Button size="small">更多</Button>
          </Dropdown>
          {/* F5: 内联消息搜索框 + ①: 导航控件 */}
          {onSearchMessages && (
            <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Input.Search
                size="small"
                placeholder="搜索消息…"
                value={searchQuery ?? ""}
                onChange={(e) => onSearchChange?.(e.target.value)}
                onSearch={(v) => { if (v.trim()) onSearchMessages(v.trim()); }}
                loading={searchLoading}
                style={{ width: 130 }}
                allowClear
                onClear={() => onSearchClose?.()}
              />
              {searchResultsCount != null && searchResultsCount > 0 && (
                <>
                  <Typography.Text style={{ fontSize: 10, color: "#666", whiteSpace: "nowrap", marginLeft: 2 }}>
                    {(searchResultIndex ?? 0) + 1}/{searchResultsCount}
                  </Typography.Text>
                  <Button
                    size="small"
                    type="text"
                    icon={<CaretUpOutlined />}
                    onClick={() => onSearchNavigate?.("prev")}
                    disabled={searchResultsCount <= 1}
                    style={{ padding: "0 2px", minWidth: 20, height: 22 }}
                  />
                  <Button
                    size="small"
                    type="text"
                    icon={<CaretDownOutlined />}
                    onClick={() => onSearchNavigate?.("next")}
                    disabled={searchResultsCount <= 1}
                    style={{ padding: "0 2px", minWidth: 20, height: 22 }}
                  />
                </>
              )}
              {onSearchClose && searchResultsCount != null && (
                <Button size="small" type="text" icon={<CloseOutlined />} onClick={onSearchClose} style={{ padding: "0 2px", minWidth: 20, height: 22 }} />
              )}
            </div>
          )}
        </div>
      </div>

      {!collapsed && (
        <div style={{ padding: "0 12px 8px" }}>
          {/* 主信息行 */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 4 }}>
            <Text style={{ fontSize: 12 }}>{fmtLang(customerProfile?.language_code ?? "zh-CN")}</Text>
            {customerProfile?.last_active_at && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                {fmtTs(customerProfile.last_active_at)} 注册
              </Text>
            )}
            {/* F-13: 余额信息 */}
            {walletInfo && (
              <span style={{ fontSize: 11, color: "#666", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 8 }}>
                <span>总余额:<b style={{ color: "#1677ff" }}>¥{walletInfo.balance.toFixed(2)}</b></span>
                <span>累计充值:<b>¥{walletInfo.total_recharged.toFixed(2)}</b></span>
                <span>累计提现:<b>¥{walletInfo.total_withdrawn.toFixed(2)}</b></span>
              </span>
            )}
            <Button size="small" type="link" icon={<WalletOutlined />} onClick={onOpenFinance} style={{ padding: 0, height: 22, fontSize: 11 }}>
              财务明细
            </Button>
            {/* F-05: 访问轨迹（有数据才显示） */}
            {visitTrailCount > 0 && (
              <Button size="small" type="link" icon={<HistoryOutlined />} onClick={onOpenVisitTrail} style={{ padding: 0, height: 22, fontSize: 11 }}>
                访问轨迹({visitTrailCount}条)
              </Button>
            )}
            {/* F4: 工单计数（有数据才显示） */}
            {ticketCount > 0 && (
              <span style={{ fontSize: 11, color: "#1677ff", whiteSpace: "nowrap" }}>
                📋 工单({ticketCount}条)
              </span>
            )}
            <Button size="small" type="link" icon={<ProfileOutlined />} onClick={onOpenCustomerProfile} style={{ padding: 0, height: 22, fontSize: 11 }}>
              资料
            </Button>
            {/* F-06: 会话标签 (API) */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, alignItems: "center" }}>
              {sessionTags.map((t) => (
                <Tag key={t} closable onClose={() => removeTag(t)} style={{ fontSize: 10, margin: 0, lineHeight: "16px" }}>
                  {t}
                </Tag>
              ))}
              <AutoComplete
                value={tagInput}
                onChange={(v) => setTagInput(v)}
                onSelect={(v) => addTag(v)}
                options={tagOptions}
                onSearch={(text) => {
                  setTagOptions(
                    text
                      ? [{ value: text }]
                      : []
                  );
                }}
                style={{ width: 80 }}
              >
                <input
                  placeholder="+ 标签"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); addTag(tagInput); }
                  }}
                  style={{
                    border: "1px dashed #d9d9d9",
                    borderRadius: 4,
                    padding: "0 4px",
                    fontSize: 10,
                    height: 22,
                    width: 72,
                    outline: "none",
                    background: "transparent",
                  }}
                />
              </AutoComplete>
            </div>
          </div>

          {/* 建议转人工警告 */}
          {showAlert && (
            <Alert
              type="warning"
              showIcon
              closable
              message="建议转人工"
              description={conversation.latest_handover_reason ?? "系统建议转人工处理"}
              style={{ marginBottom: 6, fontSize: 12 }}
              onClose={handleDismiss}
            />
          )}

          {/* 多IP注册警告 */}
          {multiIpWarning && multiIpWarning.length > 1 && (
            <Alert
              type="error"
              showIcon
              message="⚠️ 多IP注册风险"
              description={`该手机号已从以下IP注册：${multiIpWarning.join(", ")}`}
              style={{ marginBottom: 6, fontSize: 12 }}
            />
          )}

          {/* F-02: 内部备注 — 改为 Modal 浮动层 */}
        </div>
      )}

      {/* F-05: 历史会话 Drawer */}
      <Drawer
        title="📋 历史会话"
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        width={380}
      >
        {historyLoading ? (
          <div style={{ textAlign: "center", padding: 24, color: "#999" }}>加载中...</div>
        ) : historyList.length === 0 ? (
          <div style={{ textAlign: "center", padding: 24, color: "#999" }}>暂无历史会话</div>
        ) : (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            {historyList.map((h) => (
              <div
                key={h.conversation_id}
                onClick={() => {
                  if (onNavigateToConversation) {
                    onNavigateToConversation(h.account_id, h.conversation_id);
                  } else {
                    const store = useAppStore.getState();
                    store.openWorkspacePage({ accountId: h.account_id, conversationKey: `${h.account_id}:${h.conversation_id}` });
                  }
                  setHistoryOpen(false);
                }}
                style={{
                  padding: "10px 12px",
                  borderRadius: 6,
                  border: "1px solid #f0f0f0",
                  cursor: "pointer",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#f5f5f5"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <Text style={{ fontSize: 12 }}>
                    {h.last_message_at ? fmtFull(h.last_message_at) : "未知日期"}
                  </Text>
                  <Space size={4}>
                    <Tag
                      color={h.status === "closed" ? "default" : "processing"}
                      style={{ fontSize: 10, margin: 0 }}
                    >
                      {h.status === "closed" ? "已关闭" : "活跃"}
                    </Tag>
                    <Tag
                      color={
                        h.management_mode === "human_managed" ? "warning"
                        : h.management_mode === "ai_managed" ? "processing"
                        : "default"
                      }
                      style={{ fontSize: 10, margin: 0 }}
                    >
                      {h.management_mode === "human_managed" ? "人工"
                       : h.management_mode === "ai_managed" ? "AI"
                       : h.management_mode}
                    </Tag>
                  </Space>
                </div>
                <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                  {h.last_message_preview ?? "暂无消息预览"}
                </Text>
              </div>
            ))}
          </Space>
        )}
      </Drawer>

      {/* F-15: SLA 脉冲动画 style */}
      <style>{`
        @keyframes sla-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>

      {/* F-02: 内部备注 Modal */}
      <Modal
        title={"📝 内部备注"}
        open={notesModalOpen}
        onCancel={() => { setNotesModalOpen(false); handleCancelEdit(); }}
        footer={null}
        width={520}
      >
        {notesHook.error && (
          <Text type="danger" style={{ fontSize: 11, display: "block", marginBottom: 8 }}>{notesHook.error}</Text>
        )}
        {/* 已有备注列表 */}
        {notesHook.notes.length > 0 ? (
          <div style={{ maxHeight: 320, overflowY: "auto", marginBottom: 12 }}>
            {notesHook.notes.map((note) => (
              <div
                key={note.id}
                style={{
                  padding: "8px 0",
                  borderBottom: "1px solid #f0f0f0",
                }}
              >
                {editingNoteId === note.id ? (
                  /* 编辑模式 */
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <TextArea
                      size="small"
                      rows={2}
                      value={editingNoteContent}
                      onChange={(e) => setEditingNoteContent(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          void handleSaveEdit();
                        }
                      }}
                      style={{ fontSize: 12 }}
                    />
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <Button size="small" onClick={handleCancelEdit}>取消</Button>
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => void handleSaveEdit()}
                        disabled={!editingNoteContent.trim()}
                      >
                        保存
                      </Button>
                    </div>
                  </div>
                ) : (
                  /* 展示模式：内容左，作者+时间+操作右同行 */
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                        {note.content}
                      </div>
                    </div>
                    {/* 右侧：作者 + 时间 + 修改/删除按钮 */}
                    <div style={{ flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#999", whiteSpace: "nowrap" }}>
                        <span>{note.agent_name ?? note.agent_id}</span>
                        <span>{fmtFull(note.created_at)}</span>
                      </div>
                      {note.updated_at && (
                        <div style={{ fontSize: 10, color: "#bbb", whiteSpace: "nowrap" }}>
                          修改于 {fmtFull(note.updated_at)}
                        </div>
                      )}
                      <div style={{ display: "flex", gap: 2 }}>
                        <Button
                          size="small"
                          type="text"
                          icon={<EditOutlined />}
                          onClick={() => handleEditNote(note.id, note.content)}
                          style={{ fontSize: 11, color: "#1677ff" }}
                        />
                        <Popconfirm
                          title="确认删除这条备注？"
                          onConfirm={() => notesHook.removeNote(note.id)}
                          okText="确认"
                          cancelText="取消"
                        >
                          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: "16px 0", textAlign: "center", color: "#999", fontSize: 12 }}>
            暂无内部备注
          </div>
        )}
        {/* 新增备注输入 */}
        <Space.Compact style={{ width: "100%" }}>
          <TextArea
            size="small"
            rows={2}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void handleAddNote(); }
            }}
            placeholder="添加内部备注..."
            style={{ fontSize: 12 }}
          />
          <Button
            size="small"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => void handleAddNote()}
            loading={notesHook.loading}
            disabled={!noteText.trim()}
          >
            添加
          </Button>
        </Space.Compact>
      </Modal>
    </div>
  );
}
