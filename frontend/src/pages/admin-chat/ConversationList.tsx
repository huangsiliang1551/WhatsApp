import { type JSX, memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button, Checkbox, Dropdown, Popconfirm, Select, Tag, Tooltip, Typography } from "antd";
import { CaretRightOutlined, CaretDownOutlined } from "@ant-design/icons";

import { MemberIdLink } from "../../components/member/MemberIdLink";
import type { ConversationSummary } from "../../services/api";
import { getConversationPrimaryPreview, getConversationsMetadataBatch } from "../../services/api";
import { prefetchConversation } from "./hooks";

const MODE_ORDER: string[] = ["recommended", "human_managed", "ai_managed", "sleeping", "paused", "closed", "blacklisted"];
const MODE_LABELS: Record<string, string> = {
  recommended: "⚡ 待处理",
  human_managed: "🟡 人工接管",
  ai_managed: "🟢 AI 托管",
  sleeping: "💤 沉睡",
  paused: "⏸ 暂停",
  closed: "🔒 已关闭",
  blacklisted: "🚫 已拉黑",
};
const MODE_COLORS: Record<string, string> = {
  recommended: "#ff4d4f",
  human_managed: "#faad14",
  ai_managed: "#52c41a",
  paused: "#d9d9d9",
  closed: "#bfbfbf",
  blacklisted: "#ff4d4f",
};
const MODE_BG: Record<string, string> = {
  recommended: "#fff2f0",
  blacklisted: "#fff2f0",
};

const SENTIMENT_EMOJI: Record<string, string> = {
  angry: "😡",
  anxious: "😰",
  satisfied: "😊",
  neutral: "😐",
};

function buildConvKey(conv: ConversationSummary): string {
  return `${conv.account_id}:${conv.conversation_id}`;
}

function getConversationPublicUserId(conv: ConversationSummary): string {
  return (conv as ConversationSummary & { customer_public_user_id?: string | null }).customer_public_user_id ?? conv.customer_id;
}

function formatTime(v: string | null | undefined): string {
  if (!v) return "";
  const d = new Date(v);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  if (diffMs < 60000) return "刚刚";
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}分钟前`;
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}小时前`;
  return d.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function getGroupKey(c: ConversationSummary): string {
  if (c.customer_lifecycle_status === "blacklisted") return "blacklisted";
  if (c.status === "closed") return "closed";
  if (c.is_sleeping) return "sleeping";
  if (c.latest_handover_recommended && c.management_mode !== "human_managed")
    return "recommended";
  return c.management_mode ?? "ai_managed";
}

function matchesSearch(c: ConversationSummary, q: string): boolean {
  if (!q) return true;
  const lq = q.toLowerCase();
  const fields = [
    c.account_id,
    c.conversation_id,
    c.customer_id,
    c.customer_language,
    getConversationPrimaryPreview(c) ?? "",
    c.latest_intent_name ?? "",
    c.latest_handover_reason ?? "",
    c.assigned_agent_name ?? "",
  ];
  return fields.some((f) => f.toLowerCase().includes(lq));
}

export interface ConversationListProps {
  conversations: ConversationSummary[];
  selectedId: string;
  onSelect: (key: string) => void;
  onSearch: (query: string) => void;
  onFilterAccount: (accountIds: string[]) => void;
  accountIds: string[];
  runtimeAccounts: { account_id: string; display_name: string }[];
  loading: boolean;
  unreadCounts: Record<string, number>;
  /** 搜索文本，从顶部搜索栏传入 */
  searchText?: string;
  /** 批量模式开关（默认关闭，复选框隐藏） */
  batchMode?: boolean;
  /** 切换批量模式 */
  onToggleBatch?: () => void;
  /** 已选中的会话 key（仅在批量模式下有意义） */
  selectedIds?: Set<string>;
  /** 切换选中回调 */
  onToggleSelect?: (key: string) => void;
  /** 置顶会话 keys */
  pinnedKeys?: Set<string>;
  /** 切换置顶 */
  onTogglePin?: (key: string) => void;
  /** 右键菜单：关闭会话 */
  onCloseConversation?: (key: string) => void;
  /** 右键菜单：拉黑/取消拉黑 */
  onToggleBlock?: (key: string) => void;
  /** 右键菜单：AI托管/人工接管 */
  onToggleHandover?: (key: string) => void;
  /** 右键菜单：转接会话（agent_id） */
  onAssignAgent?: (key: string, agentId: string) => void;
  /** 可转接的坐席列表 */
  assignableAgents?: { agent_id: string; display_name: string }[];
  /** 全选/取消全选 */
  onSelectAll?: () => void;
  /** 清空所有选中 */
  onClearSelection?: () => void;
  /** F2: 选中某个分组下的所有会话 */
  onSelectGroup?: (groupKey: string) => void;
  /** 批量操作：接管 */
  onBatchHandover?: () => void;
  /** 批量操作：恢复AI */
  onBatchRestoreAI?: () => void;
  /** 批量操作：关闭 */
  onBatchClose?: () => void;
  /** 批量操作：分配坐席 */
  onBatchAssign?: () => void;
  /** 右键菜单：修改备注 */
  onEditNote?: (key: string) => void;
  /** F6: 右键菜单：唤醒沉睡会话 */
  onWakeConversation?: (key: string) => void;
}

function buildKey(a: string, c: string): string {
  return `${a}:${c}`;
}

export const ConversationList = memo(function ConversationList({
  conversations,
  selectedId,
  onSelect,
  onSearch,
  onFilterAccount,
  accountIds,
  runtimeAccounts,
  loading,
  unreadCounts,
  searchText,
  batchMode,
  onToggleBatch,
  selectedIds,
  onToggleSelect,
  pinnedKeys,
  onTogglePin,
  onCloseConversation,
  onToggleBlock,
  onToggleHandover,
  onAssignAgent,
  assignableAgents,
  onSelectAll,
  onClearSelection,
  onSelectGroup,
  onBatchHandover,
  onBatchRestoreAI,
  onBatchClose,
  onBatchAssign,
  onEditNote,
  onWakeConversation,
}: ConversationListProps): JSX.Element {
  const [tagFilter, setTagFilter] = useState<string>("");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const prefetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // F1: 回到顶部按钮
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showBackToTop, setShowBackToTop] = useState(false);
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => setShowBackToTop(el.scrollTop > 300);
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // ---- 右键菜单 ----
  const [ctxMenu, setCtxMenu] = useState<{ key: string; x: number; y: number } | null>(null);
  const ctxMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ctxMenu) return;
    const close = (e: MouseEvent) => {
      if (ctxMenuRef.current && !ctxMenuRef.current.contains(e.target as Node)) {
        setCtxMenu(null);
      }
    };
    const closeOnScroll = () => setCtxMenu(null);
    document.addEventListener("mousedown", close);
    document.addEventListener("scroll", closeOnScroll, true);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("scroll", closeOnScroll, true);
    };
  }, [ctxMenu]);
  const ctxMenuConv = useMemo(() => {
    if (!ctxMenu) return null;
    return conversations.find((c) => buildKey(c.account_id, c.conversation_id) === ctxMenu.key) ?? null;
  }, [ctxMenu, conversations]);
  const ctxMenuPinned = ctxMenu ? (pinnedKeys?.has(ctxMenu.key) ?? false) : false;
  const ctxMenuIsBlacklisted = ctxMenuConv?.customer_lifecycle_status === "blacklisted";
  const ctxMenuIsHuman = ctxMenuConv?.management_mode === "human_managed";

  // ---- 批量元数据（tags + sentiment + SLA）= 单次 HTTP 请求 ----
  const [tagsMap, setTagsMap] = useState<Record<string, string[]>>({});
  const [sentimentMap, setSentimentMap] = useState<Record<string, string>>({});
  const [slaMap, setSlaMap] = useState<Record<string, boolean>>({});
  const [tagsVersion, setTagsVersion] = useState(0);
  const metadataFetchingRef = useRef<Set<string>>(new Set());

  // 监听标签变更事件
  useEffect(() => {
    const onTagsChanged = () => setTagsVersion((v) => v + 1);
    window.addEventListener("fx-tags-changed", onTagsChanged);
    return () => window.removeEventListener("fx-tags-changed", onTagsChanged);
  }, []);

  // 批量拉取所有新会话的元数据（tags + sentiment + SLA）
  useEffect(() => {
    let cancelled = false;
    const toFetch = new Set<string>();
    for (const conv of conversations) {
      const key = buildConvKey(conv);
      // 只有三个缓存都缺失时才拉取
      const needsFetch = !tagsMap[key] || !sentimentMap[key] || !(key in slaMap);
      if (needsFetch && !metadataFetchingRef.current.has(key)) {
        toFetch.add(key);
      }
    }
    if (toFetch.size === 0) return;

    const fetchBatch = async () => {
      const ids = Array.from(toFetch);
      ids.forEach((id) => metadataFetchingRef.current.add(id));
      try {
        const result = await getConversationsMetadataBatch(ids);
        if (cancelled) return;
        const tUpdates: Record<string, string[]> = {};
        const sUpdates: Record<string, string> = {};
        const slaUpdates: Record<string, boolean> = {};
        for (const item of result.items) {
          const key = `${item.account_id}:${item.conversation_id}`;
          if (item.error) continue;
          tUpdates[key] = item.tags ?? [];
          sUpdates[key] = item.sentiment ?? "neutral";
          slaUpdates[key] = item.sla_overdue;
        }
        // Fill missing keys with defaults
        for (const key of toFetch) {
          if (!(key in tUpdates)) tUpdates[key] = [];
          if (!(key in sUpdates)) sUpdates[key] = "neutral";
          if (!(key in slaUpdates)) slaUpdates[key] = false;
        }
        setTagsMap((prev) => ({ ...prev, ...tUpdates }));
        setSentimentMap((prev) => ({ ...prev, ...sUpdates }));
        setSlaMap((prev) => ({ ...prev, ...slaUpdates }));
      } catch {
        if (cancelled) return;
        // On error, fill with defaults so we don't retry infinitely
        const tUpdates: Record<string, string[]> = {};
        const sUpdates: Record<string, string> = {};
        const slaUpdates: Record<string, boolean> = {};
        for (const key of toFetch) {
          tUpdates[key] = [];
          sUpdates[key] = "neutral";
          slaUpdates[key] = false;
        }
        setTagsMap((prev) => ({ ...prev, ...tUpdates }));
        setSentimentMap((prev) => ({ ...prev, ...sUpdates }));
        setSlaMap((prev) => ({ ...prev, ...slaUpdates }));
      }
    };
    void fetchBatch();
    return () => { cancelled = true; };
  }, [conversations, tagsVersion]);

  // hover 预加载
  const handleItemHover = useCallback((conv: ConversationSummary) => {
    if (prefetchTimerRef.current) clearTimeout(prefetchTimerRef.current);
    prefetchTimerRef.current = setTimeout(() => { prefetchConversation(conv); }, 150);
  }, []);

  const handleItemLeave = useCallback(() => {
    if (prefetchTimerRef.current) {
      clearTimeout(prefetchTimerRef.current);
      prefetchTimerRef.current = null;
    }
  }, []);

  // ---- 渲染单个会话项（置顶/普通共用） ----
  const renderConvItem = useCallback((
    c: ConversationSummary,
    key: string,
    active: boolean,
    unread: number,
    preview: string,
    convTags: string[] | undefined,
    sentimentVal: string | undefined,
    slaOverdue: boolean,
    isPinned: boolean,
  ) => {
    const sentimentEmoji = sentimentVal && sentimentVal !== "neutral" ? (SENTIMENT_EMOJI[sentimentVal] ?? "") : "";
    const modeColor = MODE_COLORS[getGroupKey(c)] ?? "#999";
    return (
      <div
        key={key}
        onMouseEnter={() => handleItemHover(c)}
        onMouseLeave={handleItemLeave}
        onContextMenu={(e) => {
          e.preventDefault();
          setCtxMenu({ key, x: e.clientX, y: e.clientY });
        }}
        style={{
          padding: "6px 8px",
          cursor: "pointer",
          background: active ? "#e6f4ff" : undefined,
          borderRadius: 6,
          marginBottom: 2,
          display: "flex",
          flexDirection: "column",
          gap: 2,
          borderLeft: active ? `3px solid ${modeColor}` : "3px solid transparent",
          position: "relative",
        }}
        onClick={() => onSelect(key)}
      >
        {/* 第一行：情绪 + 客户名 + 未读 + 时间 */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <Checkbox
            checked={selectedIds?.has(key) ?? false}
            onChange={() => onToggleSelect?.(key)}
            onClick={(e) => e.stopPropagation()}
            style={{ marginRight: 2, display: batchMode ? undefined : "none" }}
          />
          {sentimentEmoji && <span style={{ fontSize: 13, flexShrink: 0 }}>{sentimentEmoji}</span>}
          <Typography.Text
            style={{
              fontSize: 13, fontWeight: active ? 600 : 400, flex: 1,
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              color: active ? modeColor : undefined,
            }}
          >
            <MemberIdLink
              accountId={c.account_id}
              userId={c.customer_id}
              publicUserId={getConversationPublicUserId(c)}
              label={getConversationPublicUserId(c)}
            />
          </Typography.Text>
          {c.is_sleeping && (
            <span style={{ fontSize: 10, opacity: 0.6, flexShrink: 0 }} title="沉睡中">💤</span>
          )}
          {slaOverdue && (
            <span
              style={{
                width: 7, height: 7, borderRadius: "50%", backgroundColor: "#ff4d4f",
                animation: "sla-pulse-dot 1.5s infinite", flexShrink: 0,
              }}
              title="SLA 超时"
            />
          )}
          {unread > 0 && (
            <span style={{
              background: "#ff4d4f", color: "#fff", borderRadius: 10,
              padding: "0 6px", fontSize: 10, lineHeight: "17px", minWidth: 17, textAlign: "center",
              fontWeight: 500, flexShrink: 0,
            }}>
              {unread > 99 ? "99+" : unread}
            </span>
          )}
          <Typography.Text style={{ fontSize: 10, color: "#bbb", whiteSpace: "nowrap", flexShrink: 0 }}>
            {formatTime(c.last_message_at)}
          </Typography.Text>
        </div>

        {/* 第二行：标签 */}
        {convTags && convTags.length > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
            {convTags.slice(0, 3).map((t) => (
              <Tag key={t} style={{ fontSize: 10, margin: 0, padding: "0 4px", lineHeight: "16px" }}>{t}</Tag>
            ))}
            {convTags.length > 3 && (
              <Typography.Text style={{ fontSize: 10, color: "#999" }}>+{convTags.length - 3}</Typography.Text>
            )}
          </div>
        )}

        {/* 第三行：预览 + 置顶按钮（仅置顶时显示，或hover时显示） */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}
          className="conv-preview-row"
        >
          <Typography.Text
            type="secondary"
            style={{
              fontSize: 12, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}
          >
            {preview || "无消息"}
          </Typography.Text>
          <span
            onClick={(e) => { e.stopPropagation(); onTogglePin?.(key); }}
            style={{
              fontSize: 12, cursor: "pointer", color: isPinned ? "#1677ff" : "transparent",
              userSelect: "none", flexShrink: 0, padding: "0 2px",
              transition: "color 0.15s",
            }}
            className="conv-pin-btn"
            title={isPinned ? "取消置顶" : "置顶"}
          >
            📌
          </span>
        </div>

        {/* 第四行：坐席 */}
        {c.assigned_agent_name && (
          <div style={{ fontSize: 10, color: "#999" }}>
            👤 {c.assigned_agent_name}
          </div>
        )}
      </div>
    );
  }, [handleItemHover, handleItemLeave, onSelect, onTogglePin, batchMode, selectedIds, onToggleSelect]);

  // Collect all unique tags for filter dropdown
  const allTags = useMemo(() => {
    const set = new Set<string>();
    for (const conv of conversations) {
      const convTags = tagsMap[buildConvKey(conv)];
      if (convTags) convTags.forEach((t) => set.add(t));
    }
    return Array.from(set).sort();
  }, [conversations, tagsMap]);

  // Filter conversations by tag AND search text
  const filteredConversations = useMemo(() => {
    let result = conversations;
    if (tagFilter) {
      result = result.filter((conv) => {
        const convTags = tagsMap[buildConvKey(conv)];
        return convTags?.includes(tagFilter) ?? false;
      });
    }
    if (searchText && searchText.trim()) {
      result = result.filter((c) => matchesSearch(c, searchText.trim()));
    }
    return result;
  }, [conversations, tagFilter, tagsMap, searchText]);

  const groups = useMemo(() => {
    const grouped: Record<string, ConversationSummary[]> = {};
    for (const c of filteredConversations) {
      const gk = getGroupKey(c);
      if (!grouped[gk]) grouped[gk] = [];
      grouped[gk].push(c);
    }
    return MODE_ORDER.filter((k) => (grouped[k]?.length ?? 0) > 0).map((k) => ({
      key: k,
      label: MODE_LABELS[k] ?? k,
      conversations: grouped[k],
    }));
  }, [filteredConversations]);

  // ---- 置顶分组 ----
  const { pinnedConvs, unpinnedGroups } = useMemo(() => {
    const pinned: ConversationSummary[] = [];
    const groupedNew: Record<string, ConversationSummary[]> = {};
    for (const g of groups) {
      const p: ConversationSummary[] = [];
      const u: ConversationSummary[] = [];
      for (const c of g.conversations) {
        const key = buildKey(c.account_id, c.conversation_id);
        if (pinnedKeys?.has(key)) p.push(c); else u.push(c);
      }
      pinned.push(...p);
      if (u.length > 0) groupedNew[g.key] = u;
    }
    const unpinnedGroupsNew = MODE_ORDER.filter((k) => (groupedNew[k]?.length ?? 0) > 0).map((k) => ({
      key: k,
      label: MODE_LABELS[k] ?? k,
      conversations: groupedNew[k],
    }));
    return { pinnedConvs: pinned, unpinnedGroups: unpinnedGroupsNew };
  }, [groups, pinnedKeys]);


  return (
    <div className="session-list-container" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* 按标签筛选 */}
      <div style={{ padding: "8px 8px 0", flexShrink: 0, display: "flex", gap: 6, alignItems: "center" }}>
        {allTags.length > 0 && (
          <Select
            size="small"
            allowClear
            placeholder="按标签筛选"
            value={tagFilter || undefined}
            onChange={(v) => setTagFilter(v ?? "")}
            style={{ flex: 1 }}
            options={allTags.map((t) => ({ label: t, value: t }))}
          />
        )}
      </div>
      <div className="session-list-scroll" ref={scrollContainerRef} style={{ flex: 1, overflowY: "auto", padding: "4px 8px 8px", position: "relative" }}>
        {loading && conversations.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", color: "#999" }}>加载中...</div>
        ) : groups.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", color: "#999" }}>暂无会话</div>
        ) : (
          <>
            {/* 置顶分组 */}
            {pinnedConvs.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "4px 8px" }}>
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                    📌 置顶 ({pinnedConvs.length})
                  </Typography.Text>
                </div>
                {pinnedConvs.map((c) => {
                  const key = buildKey(c.account_id, c.conversation_id);
                  const active = selectedId === key;
                  const unread = unreadCounts[key] ?? 0;
                  const preview = getConversationPrimaryPreview(c) ?? "";
                  const convTags = tagsMap[key];
                  const sentimentVal = sentimentMap[key];
                  const slaOverdue = slaMap[key];
                  return renderConvItem(c, key, active, unread, preview, convTags, sentimentVal, slaOverdue, true);
                })}
              </div>
            )}
            {/* 正常分组 */}
            {unpinnedGroups.map((g) => {
            const isCollapsed = collapsedGroups[g.key] === true;
            const canCollapse = g.key !== "recommended" && g.key !== "human_managed";
            return (
            <div key={g.key} style={{ marginBottom: 8 }}>
              <div
                style={{
                  display: "flex", alignItems: "center", gap: 4,
                  padding: "4px 8px", cursor: canCollapse ? "pointer" : "default",
                  position: "sticky", top: 0, zIndex: 10,
                  background: "#fff",
                }}
                onClick={() => {
                  if (canCollapse) {
                    setCollapsedGroups((p) => ({ ...p, [g.key]: !p[g.key] }));
                  }
                }}
              >
                {canCollapse && (
                  isCollapsed
                    ? <CaretRightOutlined style={{ fontSize: 10, color: "#999" }} />
                    : <CaretDownOutlined style={{ fontSize: 10, color: "#999" }} />
                )}
                {/* F2: 分组全选复选框（仅批量模式） */}
                {batchMode && (
                <Checkbox
                  checked={(() => {
                    const groupKeys = g.conversations.map((c) => buildKey(c.account_id, c.conversation_id));
                    return groupKeys.length > 0 && groupKeys.every((k) => selectedIds?.has(k));
                  })()}
                  onChange={() => onSelectGroup?.(g.key)}
                  onClick={(e) => e.stopPropagation()}
                  style={{ marginRight: 2 }}
                />
                )}
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  {g.label} ({g.conversations.length})
                </Typography.Text>
              </div>
              {!isCollapsed && g.conversations.map((c) => {
                const key = buildKey(c.account_id, c.conversation_id);
                const active = selectedId === key;
                const unread = unreadCounts[key] ?? 0;
                const preview = getConversationPrimaryPreview(c) ?? "";
                const convTags = tagsMap[key];
                const sentimentVal = sentimentMap[key];
                const slaOverdue = slaMap[key];
                const isPinned = pinnedKeys?.has(key) ?? false;
                return renderConvItem(c, key, active, unread, preview, convTags, sentimentVal, slaOverdue, isPinned);
              })}
            </div>
            );
          })}
          </>
        )}
        {/* F1: 回到顶部按钮 */}
        {showBackToTop && (
          <Button
            size="small"
            shape="circle"
            icon={<span style={{ fontSize: 16 }}>↑</span>}
            onClick={() => { scrollContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" }); }}
            style={{
              position: "sticky", bottom: 12, float: "right",
              zIndex: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
            }}
            title="回到顶部"
          />
        )}
      </div>
      {/* 底部操作栏 */}
      <div style={{
        padding: "4px 6px", borderTop: "1px solid #f0f0f0", flexShrink: 0,
        display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap",
      }}>
        {batchMode ? (
          <>
            <Button size="small" style={{ fontSize: 11, height: 24, padding: "0 6px" }} onClick={() => onSelectAll?.()}>
              全选
            </Button>
            <Button size="small" style={{ fontSize: 11, height: 24, padding: "0 6px" }} onClick={() => onClearSelection?.()}>
              取消全选
            </Button>
            <Typography.Text style={{ fontSize: 11, color: "#1677ff", fontWeight: 500, whiteSpace: "nowrap" }}>
              已选 {selectedIds?.size ?? 0} 个
            </Typography.Text>
            {(() => {
              const batchItems = [
                ...(onBatchHandover ? [{ key: "handover", label: "人工接管", onClick: () => onBatchHandover(), disabled: !selectedIds?.size }] : []),
                ...(onBatchRestoreAI ? [{ key: "restore-ai", label: "AI托管", onClick: () => onBatchRestoreAI(), disabled: !selectedIds?.size }] : []),
                ...(onBatchClose ? [{ key: "close", label: "关闭会话", danger: true as const, onClick: () => onBatchClose(), disabled: !selectedIds?.size }] : []),
                ...(onBatchAssign ? [{ key: "assign", label: "转接会话", onClick: () => onBatchAssign(), disabled: !selectedIds?.size }] : []),
              ];
              if (batchItems.length === 0) return null;
              return (
                <Dropdown
                  menu={{ items: batchItems }}
                  trigger={["click"]}
                  disabled={!selectedIds?.size}
                >
                  <Button size="small" style={{ fontSize: 11, height: 24, padding: "0 6px" }} disabled={!selectedIds?.size}>
                    操作
                  </Button>
                </Dropdown>
              );
            })()}
            <div style={{ flex: 1 }} />
            <Button size="small" type="primary" style={{ fontSize: 11, height: 24, padding: "0 6px" }} onClick={() => { onClearSelection?.(); onToggleBatch?.(); }}>
              ✓ 完成
            </Button>
          </>
        ) : (
          <>
            <div style={{ flex: 1 }} />
            <Button size="small" type="dashed" style={{ fontSize: 11, height: 24, padding: "0 6px" }} onClick={() => onToggleBatch?.()}>
              ☐ 批量选择
            </Button>
          </>
        )}
      </div>
      {/* 右键菜单 */}
      {ctxMenu && ctxMenuConv && (
        <div
          ref={ctxMenuRef}
          className="conv-context-menu"
          style={{ left: ctxMenu.x, top: ctxMenu.y }}
        >
          <div
            className="conv-context-menu-item"
            onClick={() => { onTogglePin?.(ctxMenu.key); setCtxMenu(null); }}
          >
            📌 {ctxMenuPinned ? "取消置顶" : "置顶"}
          </div>
          {onEditNote && (
            <div
              className="conv-context-menu-item"
              onClick={() => { onEditNote(ctxMenu.key); setCtxMenu(null); }}
            >
              📝 修改备注
            </div>
          )}
          {onCloseConversation && (
            <div
              className="conv-context-menu-item"
              onClick={() => { onCloseConversation(ctxMenu.key); setCtxMenu(null); }}
            >
              🔒 关闭会话
            </div>
          )}
          {onToggleBlock && (
            <div
              className={`conv-context-menu-item${ctxMenuIsBlacklisted ? "" : " danger"}`}
              onClick={() => { onToggleBlock(ctxMenu.key); setCtxMenu(null); }}
            >
              {ctxMenuIsBlacklisted ? "✅ 取消黑名单" : "🚫 设为黑名单"}
            </div>
          )}
          {onToggleHandover && (
            <div
              className="conv-context-menu-item"
              onClick={() => { onToggleHandover(ctxMenu.key); setCtxMenu(null); }}
            >
              {ctxMenuIsHuman ? "🤖 恢复AI托管" : "🖐 人工接管"}
            </div>
          )}
          {/* F6: 唤醒沉睡会话 */}
          {onWakeConversation && ctxMenuConv?.is_sleeping && (
            <div
              className="conv-context-menu-item"
              onClick={() => { onWakeConversation(ctxMenu.key); setCtxMenu(null); }}
            >
              ☀️ 唤醒会话
            </div>
          )}
          {onAssignAgent && assignableAgents && assignableAgents.length > 0 && (
            <>
              <div style={{ borderTop: "1px solid #f0f0f0", margin: "4px 0" }} />
              <div className="conv-context-menu-item" style={{ color: "#999", fontSize: 11, cursor: "default" }}>
                转接给…
              </div>
              {assignableAgents.map((a) => (
                <div
                  key={a.agent_id}
                  className="conv-context-menu-item"
                  onClick={() => { onAssignAgent(ctxMenu.key, a.agent_id); setCtxMenu(null); }}
                >
                  👤 {a.display_name}
                </div>
              ))}
            </>
          )}
        </div>
      )}
      <style>{`
        @keyframes sla-pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        .conv-preview-row:hover .conv-pin-btn {
          color: #d9d9d9 !important;
        }
        .conv-preview-row:hover .conv-pin-btn:hover {
          color: #1677ff !important;
        }
        .conv-context-menu {
          position: fixed;
          z-index: 9999;
          background: #fff;
          border: 1px solid #e8e8e8;
          border-radius: 8px;
          box-shadow: 0 6px 16px rgba(0,0,0,0.12);
          padding: 4px 0;
          min-width: 140px;
        }
        .conv-context-menu-item {
          padding: 6px 12px;
          cursor: pointer;
          font-size: 13px;
          user-select: none;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .conv-context-menu-item:hover {
          background: #f5f5f5;
        }
        .conv-context-menu-item.danger {
          color: #ff4d4f;
        }
      `}</style>
    </div>
  );
});
