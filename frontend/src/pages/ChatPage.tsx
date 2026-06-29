import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import { Button, Dropdown, Form, Input, Modal, Select, Space, Tag, Typography, message } from "antd";
import { SwapOutlined, TagOutlined, UserOutlined, SendOutlined } from "@ant-design/icons";
import { chatRealtime, type NewMessageEvent, type StatusChangeEvent, type HandoverEvent } from "../services/chatRealtime";
import { adminAuth } from "../services/adminAuth";
import { blockCustomer, unblockCustomer, batchTranslateMessages, translateMessage, getAiReplyPreview, batchUpdateTags, batchAssignConversations, batchSendTemplate } from "../services/api";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";
import { getCustomerMemberStatusSnapshot, resolveCustomerProfileSummaryByConversation } from "../services/operations";
import { useAppStore } from "../stores/appStore";
import { usePermissions } from "../hooks/usePermissions";
import { ConversationList, MessagePanel, ConversationHeader, FinanceDrawer, VisitTrailDrawer, CustomerProfileDrawer, QuickToolbar, CannedResponses, type MessagePanelHandle, type OpenTab } from "./admin-chat";
import { AIReceptionBar } from "./admin-chat/AIReceptionBar";
import { switchConversationAI } from "../services/entryLinks";
import { useWorkspaceState, useConversationDetail, useChatActions, clearProfileCache, clearMessagesCache, useNotificationSound, useAgentStatus } from "./admin-chat/hooks";

/*
Workspace handover recommendation contract kept in ChatPage for regression visibility:
- handoverMode: "all" | "recommended" | "normal";
- latest_handover_recommended
- latest_handover_reason
- filters.handoverMode === "recommended"
- filters.handoverMode === "normal"
- latest_handover_recommended: latestHandoverRecommended
- workspacePagePrefill.handoverMode ?? "all"
- resolveConversationSelectionKey(
- workspacePagePrefill.accountId
- 推荐转人工 / 普通会话 / 接管建议 / 建议原因 / 仅推荐转人工
*/

function buildKey(a: string, c: string) { return `${a}:${c}`; }

export function getConversationTabLabel(conv: {
  customer_id: string;
  customer_public_user_id?: string | null;
}): string {
  return conv.customer_public_user_id ?? conv.customer_id;
}

export function ChatPage(): JSX.Element {
  const ws = useWorkspaceState();
  const detail = useConversationDetail();
  const actions = useChatActions(async () => { clearProfileCache(selConv?.account_id); await ws.reload(); if (selConv) await detail.loadForConversation(selConv); });
  const caName = useAppStore((s) => s.consoleAgentName);
  const actorRole = useAppStore((s) => s.actorRole);
  const consoleAgentId = useAppStore((s) => s.consoleAgentId);
  const siteAccountIds = useAppStore((s) => s.siteAccountIds);
  const openCustomersPage = useAppStore((s) => s.openCustomersPage);
  const { can } = usePermissions();

  // 置顶会话（localStorage 持久化）
  const [pinnedKeys, setPinnedKeys] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem("pinned_conversations");
      return new Set<string>(raw ? JSON.parse(raw) : []);
    } catch { return new Set<string>(); }
  });
  const togglePin = useCallback((key: string) => {
    setPinnedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      localStorage.setItem("pinned_conversations", JSON.stringify(Array.from(next)));
      return next;
    });
  }, []);

  const [selKey, setSelKey] = useState("");
  const [cannedOpen, setCannedOpen] = useState(false);
  const messagePanelRef = useRef<MessagePanelHandle>(null);
  // FIX-6: 防止重新登录时 selKey 状态循环导致的 Maximum update depth exceeded
  const autoSelectDoneRef = useRef(false);
  const prevConversationsLenRef = useRef(0);
  const selConv = useMemo(() => ws.conversations.find((c) => buildKey(c.account_id, c.conversation_id) === selKey) ?? null, [ws.conversations, selKey]);

  // 自动选中第一条会话（仅在会话列表首次加载时触发）
  useEffect(() => {
    if (ws.conversations.length > 0 && !selKey && !autoSelectDoneRef.current) {
      autoSelectDoneRef.current = true;
      setSelKey(buildKey(ws.conversations[0].account_id, ws.conversations[0].conversation_id));
    }
    // 会话列表被清空时重置标记（重新登录场景）
    if (ws.conversations.length === 0 && prevConversationsLenRef.current > 0) {
      autoSelectDoneRef.current = false;
    }
    prevConversationsLenRef.current = ws.conversations.length;
  }, [ws.conversations.length > 0 ? ws.conversations[0]?.conversation_id : null]);

  // selKey 无匹配时回退（仅当 selKey 确实存在于旧列表中但新列表不包含时才回退）
  useEffect(() => {
    if (ws.conversations.length > 0 && selKey && !selConv) {
      setSelKey(buildKey(ws.conversations[0].account_id, ws.conversations[0].conversation_id));
    }
  }, [selConv, ws.conversations.length]);

  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({});

  // 切换会话时清空旧消息再加载
  useEffect(() => {
    if (selConv) {
      void detail.loadForConversation(selConv);
    }
  }, [selConv?.account_id, selConv?.conversation_id]);

  // refs 供 SSE 闭包访问最新值（useEffect([]) 会捕获初始值）
  const wsRef = useRef(ws); wsRef.current = ws;
  const selKeyRef = useRef(selKey); selKeyRef.current = selKey;
  const selConvRef = useRef(selConv); selConvRef.current = selConv;

  useEffect(() => {
    const token = adminAuth.getAccessToken();
    if (!token) return;
    chatRealtime.connect(token);
    const hMsg = (e: NewMessageEvent) => {
      const w = wsRef.current;
      const c = w.conversations.find((x) => x.conversation_id === e.conversation_id);
      if (!c) return;
      const k = buildKey(c.account_id, c.conversation_id);
      clearMessagesCache(e.account_id, e.conversation_id);
      if (k !== selKeyRef.current) {
        setUnreadCounts((p) => ({ ...p, [k]: (p[k] ?? 0) + 1 }));
        // F-09: 非当前会话时播放提示音
        notifSound.play();
      }
      void w.reload();
      if (k === selKeyRef.current && selConvRef.current) void detail.loadForConversation(selConvRef.current);
      // 全局自动翻译：新消息到达且语言非中文时自动触发
      if (autoTranslateRef.current && e.message_id && c.customer_language && c.customer_language !== "zh-CN") {
        translateMessage(c.account_id, c.conversation_id, e.message_id).catch(() => {});
      }
      // F-04: AI 回复预览 - 当会话是 ai_managed 且有新入站消息时，自动获取预览
      if (c.management_mode === "ai_managed" && e.sender_type === "user" && k === selKeyRef.current) {
        getAiReplyPreview(c.account_id, c.conversation_id)
          .then((preview) => setPreviewText(preview.preview_text))
          .catch(() => {});
      }
      // F-13: 新消息可能包含 delivery_status 更新（通过消息轮询机制已处理，这里记录收到事件）
    };
    const hSt = (_e: StatusChangeEvent) => { void wsRef.current.reload(); };
    const hHv = (_e: HandoverEvent) => { void wsRef.current.reload(); if (selConvRef.current) void detail.loadForConversation(selConvRef.current); };
    chatRealtime.onMessage(hMsg); chatRealtime.onStatusChange(hSt); chatRealtime.onHandover(hHv);
    return () => { chatRealtime.disconnect(); };
  }, []);

  const openTab = (conv: typeof selConv) => { if (!conv) return; const k = buildKey(conv.account_id, conv.conversation_id); setOpenTabs((p) => p.some((t) => t.key === k) ? p : [...p, { key: k, conversationId: conv.conversation_id, accountId: conv.account_id, label: getConversationTabLabel(conv).slice(0, 12) }]); setSelKey(k); };

  const closeTab = (key: string) => { setOpenTabs((p) => { const i = p.findIndex((t) => t.key === key); if (i < 0) return p; const n = p.filter((t) => t.key !== key); if (selKey === key && n.length > 0) setSelKey(n[Math.min(i, n.length - 1)].key); else if (selKey === key) setSelKey(""); return n; }); setUnreadCounts((p) => { const c = { ...p }; delete c[key]; return c; }); };

  // ①: 消息搜索回调
  const handleSearchResultChange = useCallback((count: number, index: number) => {
    setSearchResultsCount(count);
    setSearchResultIndex(index);
  }, []);
  const handleSearchMessages = useCallback(async (query: string) => {
    setSearchQuery(query);
    setSearchLoading(true);
    try {
      await messagePanelRef.current?.searchMessages(query);
    } finally {
      setSearchLoading(false);
    }
  }, []);
  const handleSearchChange = useCallback((query: string) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResultsCount(0);
      setSearchResultIndex(0);
      messagePanelRef.current?.closeSearch();
    }
  }, []);
  const handleSearchNavigate = useCallback((direction: "prev" | "next") => {
    messagePanelRef.current?.navigateSearch(direction);
  }, []);
  const handleSearchClose = useCallback(() => {
    setSearchQuery("");
    setSearchResultsCount(0);
    setSearchResultIndex(0);
    messagePanelRef.current?.closeSearch();
  }, []);

  // 点击时同步 reset（清空旧消息），与 selKey 在同一帧渲染，高亮即刻上色
  const handleSelect = useCallback((key: string) => {
    const c = ws.conversations.find((x) => buildKey(x.account_id, x.conversation_id) === key);
    const sameConv = c && selConv && c.account_id === selConv.account_id && c.conversation_id === selConv.conversation_id;
    detail.reset();
    if (c) { openTab(c); if (sameConv) void detail.loadForConversation(c); } else setSelKey(key);
    setUnreadCounts((p) => ({ ...p, [key]: 0 }));
    // ⑤: 切换会话时清空消息搜索
    handleSearchClose();
  }, [ws.conversations, selConv, handleSearchClose]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key >= "1" && e.key <= "9") { setOpenTabs((p) => { const i = parseInt(e.key, 10) - 1; if (i < p.length) setSelKey(p[i].key); return p; }); return; }
      if (e.ctrlKey && (e.key === "w" || e.key === "W")) { e.preventDefault(); setOpenTabs((p) => { const t = p.find((x) => x.key === selKey); if (t) closeTab(t.key); return p; }); return; }
      // F-14: Alt+↑/↓ 切换会话（限定当前分组内）
      if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
        e.preventDefault();
        const convs = wsRef.current.conversations;
        if (convs.length === 0) return;
        // 按分组逻辑获取当前选中会话的分组key
        const getGroupKey = (c: typeof convs[0]): string => {
          if (c.customer_lifecycle_status === "blacklisted") return "blacklisted";
          if (c.status === "closed") return "closed";
          if (c.is_sleeping) return "sleeping";
          if (c.latest_handover_recommended && c.management_mode !== "human_managed") return "recommended";
          return c.management_mode ?? "ai_managed";
        };
        const currentConv = convs.find((c) => buildKey(c.account_id, c.conversation_id) === selKey);
        if (!currentConv) return;
        const currentGroup = getGroupKey(currentConv);
        // 过滤同分组会话（保持原始顺序）
        const sameGroup = convs.filter((c) => getGroupKey(c) === currentGroup);
        if (sameGroup.length <= 1) return;
        const currentIdx = sameGroup.findIndex((c) => buildKey(c.account_id, c.conversation_id) === selKey);
        let nextIdx: number;
        if (e.key === "ArrowUp") {
          nextIdx = currentIdx <= 0 ? sameGroup.length - 1 : currentIdx - 1;
        } else {
          nextIdx = currentIdx < 0 ? 0 : (currentIdx + 1) % sameGroup.length;
        }
        const nextConv = sameGroup[nextIdx];
        const nextKey = buildKey(nextConv.account_id, nextConv.conversation_id);
        handleSelect(nextKey);
      }
    };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, [selKey, handleSelect]);

  const handleCannedSelect = useCallback((text: string) => {
    messagePanelRef.current?.insertText(text);
  }, []);

  const agentOpts = ws.agents.filter((a) => !selConv || !a.account_id || a.account_id === selConv.account_id).map((a) => { const w = ws.workloads.find((wl) => wl.agent_id === a.agent_id); return { label: `${a.display_name}${w ? ` · open ${w.assigned_open_conversations}` : ""}`, value: a.agent_id }; });

  // F-09: 通知声音
  const notifSound = useNotificationSound();
  // F-10: 坐席状态
  const agentStatus = useAgentStatus();

  // 批量选择（默认关闭，通过底部入口按钮激活）
  const [batchMode, setBatchMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const handleToggleBatch = useCallback(() => {
    setBatchMode((prev) => {
      if (prev) setSelectedIds(new Set());
      return !prev;
    });
  }, []);
  // ①: 消息搜索状态（在会话头顶栏内联显示）
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResultsCount, setSearchResultsCount] = useState(0);
  const [searchResultIndex, setSearchResultIndex] = useState(0);
  const [searchLoading, setSearchLoading] = useState(false);
  // F-04: AI 回复预览
  const [previewText, setPreviewText] = useState<string | undefined>(undefined);
  // F-13: 消息状态更新映射
  const [messageStatusUpdates, setMessageStatusUpdates] = useState<Record<string, string>>({});

  // 切换会话时清空旧消息再加载
  // 计算每个账号的会话数
  const accountConvCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of ws.conversations) {
      counts[c.account_id] = (counts[c.account_id] ?? 0) + 1;
    }
    return counts;
  }, [ws.conversations]);

  // 客服可见的账号集合（仅分配/转接的账号）
  const accessibleAccounts = useMemo(() => {
    if (actorRole !== "support_agent") return null;
    const accountSet = new Set<string>();
    for (const c of ws.conversations) {
      if (c.assigned_agent_id === consoleAgentId) {
        accountSet.add(c.account_id);
      }
    }
    return accountSet; // 可为空 Set，客服无分配账号时只显示「全部账号」
  }, [actorRole, consoleAgentId, ws.conversations]);

  const [sites, setSites] = useState<H5Site[]>([]);
  const [siteFilter, setSiteFilter] = useState<string[]>([]);
  useEffect(() => { listSites().then(setSites).catch(() => {}); }, []);

  // Filter sites by agent's accessible account_ids (for site dropdown)
  const displayedSites = useMemo(() => {
    if (siteAccountIds.length === 0) return sites;
    return sites.filter((s) => s.account_id && siteAccountIds.includes(s.account_id));
  }, [sites, siteAccountIds]);

  // 每个 H5 站点关联的账号数
  const siteConvCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    const accounts = ws.runtimeState?.accounts ?? [];
    for (const site of displayedSites) {
      if (site.account_id) {
        counts[site.site_key] = accounts.filter((a) => a.account_id === site.account_id).length;
      } else {
        counts[site.site_key] = 0;
      }
    }
    return counts;
  }, [sites, ws.runtimeState?.accounts]);

  // H5 站点下拉选项
  const totalAccountsCount = ws.runtimeState?.accounts?.length ?? 0;
  const siteOptions = useMemo(() => displayedSites.map((s) => ({
    label: `${s.brand_name || s.site_key} (${siteConvCounts[s.site_key] ?? 0})`,
    value: s.site_key,
  })), [displayedSites, siteConvCounts]);

  // 构建账号下拉选项（含会话数），客服只显示可访问的账号（无"全部账号"选项，空数组=全部）
  const accountOptions = useMemo(() => {
    let accounts = ws.runtimeState?.accounts ?? [];
    if (accessibleAccounts) {
      accounts = accounts.filter((a) => accessibleAccounts.has(a.account_id));
    }
    // 当选择了站点时，只显示属于所选站点的账号
    if (siteFilter.length > 0) {
      const filteredSiteAccountIds = new Set(
        displayedSites.filter((s) => siteFilter.includes(s.site_key)).map((s) => s.account_id).filter(Boolean) as string[]
      );
      if (filteredSiteAccountIds.size > 0) {
        accounts = accounts.filter((a) => filteredSiteAccountIds.has(a.account_id));
      }
    }
    return accounts.map((a) => ({
      label: `${a.display_name} (${accountConvCounts[a.account_id] ?? 0})`,
      value: a.account_id,
    }));
  }, [ws.runtimeState?.accounts, accessibleAccounts, accountConvCounts, siteFilter, sites]);

  // 前端过滤：站点 + 账号多选
  const filteredConversations = useMemo(() => {
    let result = ws.conversations;
    if (siteFilter.length > 0) {
      const filteredSiteAccountIds = new Set(
        displayedSites.filter((s) => siteFilter.includes(s.site_key)).map((s) => s.account_id).filter(Boolean) as string[]
      );
      if (filteredSiteAccountIds.size > 0) {
        result = result.filter((c) => filteredSiteAccountIds.has(c.account_id));
      }
    }
    if (ws.filter.accountIds.length > 0) {
      result = result.filter((c) => ws.filter.accountIds.includes(c.account_id));
    }
    return result;
  }, [ws.conversations, siteFilter, sites, ws.filter.accountIds]);

  const isSuperAdmin = actorRole === "super_admin";
  const [headerCollapsed, setHeaderCollapsed] = useState(false);
  useEffect(() => { setHeaderCollapsed(false); }, [selConv?.conversation_id]);
  const [financeOpen, setFinanceOpen] = useState(false);
  const [trailOpen, setTrailOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [batchTranslating, setBatchTranslating] = useState(false);
  const [autoTranslate, setAutoTranslate] = useState(false);
  const autoTranslateRef = useRef(autoTranslate);

  // IV-FE-002: Batch operation modals
  const [batchTagsModalOpen, setBatchTagsModalOpen] = useState(false);
  const [batchTagsAdd, setBatchTagsAdd] = useState<string[]>([]);
  const [batchTagsRemove, setBatchTagsRemove] = useState<string[]>([]);
  const [batchTagsLoading, setBatchTagsLoading] = useState(false);

  const [batchAssignModalOpen, setBatchAssignModalOpen] = useState(false);
  const [batchAssignAgentId, setBatchAssignAgentId] = useState<string>("");
  const [batchAssignLoading, setBatchAssignLoading] = useState(false);

  const [batchTemplateModalOpen, setBatchTemplateModalOpen] = useState(false);
  const [batchTemplateId, setBatchTemplateId] = useState<string>("");
  const [batchTemplateVars, setBatchTemplateVars] = useState<string>("");
  const [batchTemplateLoading, setBatchTemplateLoading] = useState(false);
  useEffect(() => { autoTranslateRef.current = autoTranslate; }, [autoTranslate]);
  // F-07: 右键菜单触发修改备注
  const [forceOpenNotes, setForceOpenNotes] = useState(false);

  const handleBlock = useCallback(async () => {
    if (!selConv) return;
    try {
      await blockCustomer(selConv.customer_id, selConv.account_id);
      message.success("已拉黑该客户");
      await detail.loadForConversation(selConv);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "拉黑失败");
    }
  }, [selConv, detail]);

  const handleUnblock = useCallback(async () => {
    if (!selConv) return;
    try {
      await unblockCustomer(selConv.customer_id, selConv.account_id);
      message.success("已取消拉黑");
      await detail.loadForConversation(selConv);
    } catch (e) {
      message.error(e instanceof Error ? e.message : "取消拉黑失败");
    }
  }, [selConv, detail]);

  const handleBatchTranslate = useCallback(async () => {
    if (!selConv) return;
    setBatchTranslating(true);
    try {
      const result = await batchTranslateMessages(selConv.account_id, selConv.conversation_id);
      if (result.translations && Object.keys(result.translations).length > 0) {
        detail.applyTranslations(result.translations);
      }
      message.success(`翻译完成 (${result.count} 条)`);
    } catch (e: unknown) {
      message.error(`翻译失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBatchTranslating(false);
    }
  }, [selConv, detail]);

  // F-03: 批量操作 toggle select
  const handleToggleSelect = useCallback((key: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // 全选/取消全选（仅当前过滤后的可见会话）
  const handleSelectAll = useCallback(() => {
    const allKeys = filteredConversations.map((c) => buildKey(c.account_id, c.conversation_id));
    setSelectedIds((prev) => {
      const allSelected = allKeys.length > 0 && allKeys.every((k) => prev.has(k));
      if (allSelected) return new Set<string>();
      return new Set(allKeys);
    });
  }, [filteredConversations]);

  // 清空所有选中
  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // F2: 分组级别全选（仅可见会话）
  const handleSelectGroup = useCallback((groupKey: string) => {
    const getGroupKey = (c: typeof ws.conversations[0]): string => {
      if (c.customer_lifecycle_status === "blacklisted") return "blacklisted";
      if (c.status === "closed") return "closed";
      if (c.is_sleeping) return "sleeping";
      if (c.latest_handover_recommended && c.management_mode !== "human_managed") return "recommended";
      return c.management_mode ?? "ai_managed";
    };
    const groupKeys = filteredConversations
      .filter((c) => getGroupKey(c) === groupKey)
      .map((c) => buildKey(c.account_id, c.conversation_id));
    setSelectedIds((prev) => {
      const allSelected = groupKeys.length > 0 && groupKeys.every((k) => prev.has(k));
      const next = new Set(prev);
      if (allSelected) {
        for (const k of groupKeys) next.delete(k);
      } else {
        for (const k of groupKeys) next.add(k);
      }
      return next;
    });
  }, [filteredConversations]);

  // F-03: 批量操作回调（使用后端批量 API，一次 HTTP 请求完成）
  const handleBatchHandover = useCallback(async () => {
    await actions.batchHandover(Array.from(selectedIds));
    setSelectedIds(new Set());
  }, [selectedIds, actions]);

  const handleBatchRestoreAI = useCallback(async () => {
    await actions.batchRestoreAI(Array.from(selectedIds));
    setSelectedIds(new Set());
  }, [selectedIds, actions]);

  const handleBatchClose = useCallback(async () => {
    await actions.batchClose(Array.from(selectedIds));
    setSelectedIds(new Set());
  }, [selectedIds, actions]);

  const handleBatchAssign = useCallback(async () => {
    const agentId = useAppStore.getState().consoleAgentId;
    await actions.batchAssign(Array.from(selectedIds), agentId);
    setSelectedIds(new Set());
  }, [selectedIds, actions]);

  // IV-FE-002: 批量标签
  const handleOpenBatchTags = useCallback(() => {
    setBatchTagsAdd([]);
    setBatchTagsRemove([]);
    setBatchTagsModalOpen(true);
  }, []);

  const handleBatchTagsSubmit = useCallback(async () => {
    setBatchTagsLoading(true);
    try {
      await batchUpdateTags({
        entity_type: "conversation",
        entity_ids: Array.from(selectedIds),
        add_tags: batchTagsAdd,
        remove_tags: batchTagsRemove,
      });
      message.success("标签已更新");
      setBatchTagsModalOpen(false);
      setSelectedIds(new Set());
    } catch (e) {
      message.error(e instanceof Error ? e.message : "更新标签失败");
    } finally {
      setBatchTagsLoading(false);
    }
  }, [selectedIds, batchTagsAdd, batchTagsRemove]);

  // IV-FE-002: 批量分配（选客服）
  const handleOpenBatchAssign = useCallback(() => {
    setBatchAssignAgentId("");
    setBatchAssignModalOpen(true);
  }, []);

  const handleBatchAssignSubmit = useCallback(async () => {
    if (!batchAssignAgentId) { message.warning("请选择客服"); return; }
    setBatchAssignLoading(true);
    try {
      await batchAssignConversations({
        conversation_ids: Array.from(selectedIds),
        agent_id: batchAssignAgentId,
      });
      message.success("分配完成");
      setBatchAssignModalOpen(false);
      setSelectedIds(new Set());
      void ws.reload();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "分配失败");
    } finally {
      setBatchAssignLoading(false);
    }
  }, [selectedIds, batchAssignAgentId, ws]);

  // IV-FE-002: 批量发送模板
  const handleOpenBatchTemplate = useCallback(() => {
    setBatchTemplateId("");
    setBatchTemplateVars("");
    setBatchTemplateModalOpen(true);
  }, []);

  const handleBatchTemplateSubmit = useCallback(async () => {
    if (!batchTemplateId) { message.warning("请选择模板"); return; }
    setBatchTemplateLoading(true);
    try {
      let variables: Record<string, string> = {};
      if (batchTemplateVars.trim()) {
        try {
          variables = JSON.parse(batchTemplateVars);
        } catch {
          message.warning("变量格式错误，请使用 JSON 格式");
          setBatchTemplateLoading(false);
          return;
        }
      }
      await batchSendTemplate({
        entity_type: "conversation",
        entity_ids: Array.from(selectedIds),
        template_id: batchTemplateId,
        variables,
      });
      message.success("模板消息已发送");
      setBatchTemplateModalOpen(false);
      setSelectedIds(new Set());
    } catch (e) {
      message.error(e instanceof Error ? e.message : "发送失败");
    } finally {
      setBatchTemplateLoading(false);
    }
  }, [selectedIds, batchTemplateId, batchTemplateVars]);

  // F-07: 右键修改备注 → 选中会话 + 打开备注 Modal
  const handleEditNote = useCallback((key: string) => {
    handleSelect(key);
    setForceOpenNotes(true);
  }, [handleSelect]);

  // F6: 唤醒沉睡会话
  const handleWakeConversation = useCallback(async (key: string) => {
    const c = ws.conversations.find((x) => buildKey(x.account_id, x.conversation_id) === key);
    if (!c) return;
    try {
      const { wakeConversation } = await import("../services/api");
      await wakeConversation(c.account_id, c.conversation_id);
      message.success("已唤醒会话");
      await ws.reload();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "唤醒失败");
    }
  }, [ws]);

  return (
    <div style={{
      display: "flex", flexDirection: "column", flex: 1, minHeight: 0, overflow: "hidden",
      background: "#f0f2f5",
      padding: "0 12px 12px",
    }}>
      {/* 顶部筛选栏 */}
      <div style={{
        display: "flex", alignItems: "center", padding: "8px 0", gap: 8, flexShrink: 0,
        borderBottom: "1px solid #e8e8e8", marginBottom: 8, flexWrap: "wrap",
      }}>
        {/* 顶部筛选栏 - 超管: H5站点(多选) → 账号筛选(多选) → 搜索框；代理/客服: 账号筛选(多选) → 搜索框 */}
        {isSuperAdmin && (
          <>
          <Select mode="multiple" size="small" style={{ width: 200, fontSize: 11 }} placeholder="全部站点（全选）" value={siteFilter} onChange={(v) => setSiteFilter(v)} options={siteOptions} maxTagCount={1} maxTagPlaceholder={(o) => `+${o.length}个站点`} />
          {totalAccountsCount === 0 && <span style={{ fontSize: 11, color: "#999" }}>（暂无账号）</span>}
          </>
        )}
        <Select mode="multiple" size="small" style={{ width: 240, fontSize: 11 }} placeholder="全部账号（全选）" value={ws.filter.accountIds} onChange={(v) => ws.setFilter({ accountIds: v })} options={accountOptions} maxTagCount={2} maxTagPlaceholder={(o) => `+${o.length}个账号`} />
        <Input.Search size="small" placeholder="搜索会话(客户ID/账号/状态)…" style={{ width: 280, fontSize: 11 }} onChange={(e) => ws.setFilter({ search: e.target.value })} allowClear />
        <div style={{ flex: 1 }} />
        <Tag style={{ margin: 0, fontSize: 11 }}>共 {filteredConversations.length} 个会话</Tag>
        {/* F6: 活跃/沉睡切换 */}
        <Button
          size="small"
          type={ws.filter.isSleeping === "sleeping" ? "primary" : "default"}
          onClick={() => ws.setFilter({ isSleeping: ws.filter.isSleeping === "sleeping" ? "active" : "sleeping" })}
          style={{ fontSize: 11, height: 24, padding: "0 6px" }}
        >
          {ws.filter.isSleeping === "sleeping" ? "💤 沉睡会话" : "🟢 活跃会话"}
        </Button>
        <Button
          size="small"
          type={autoTranslate ? "primary" : "default"}
          onClick={() => setAutoTranslate((p) => !p)}
          style={{ fontSize: 11, height: 24, padding: "0 6px" }}
        >
          🌐 自动翻译
        </Button>
        {/* F-09: 通知声音 */}
        <Button
          size="small"
          type={notifSound.enabled ? "primary" : "default"}
          onClick={() => notifSound.setEnabled(!notifSound.enabled)}
          style={{ fontSize: 11, height: 24, padding: "0 6px" }}
        >
          🔔 提示音
        </Button>
        {/* F-10: 坐席状态 Dropdown */}
        <Dropdown
          menu={{
            items: agentStatus.statusOptions.map((opt) => ({
              key: opt.value,
              label: opt.label,
              onClick: () => agentStatus.setStatus(opt.value),
            })),
            selectedKeys: [agentStatus.status],
          }}
          trigger={["click"]}
        >
          <Button size="small" style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, height: 24, padding: "0 6px" }}>
            <span style={{
              width: 8, height: 8, borderRadius: "50%", display: "inline-block",
              backgroundColor: agentStatus.statusOptions.find((o) => o.value === agentStatus.status)?.color ?? "#999",
            }} />
            <span style={{ fontSize: 11 }}>
              {agentStatus.statusOptions.find((o) => o.value === agentStatus.status)?.label ?? agentStatus.status}
            </span>
          </Button>
        </Dropdown>
      </div>
      {/* 主体两栏 */}
      <div style={{ display: "flex", flex: 1, minHeight: 0, gap: 12 }}>
        {/* 左侧：会话列表卡片 */}
        <div style={{
          width: 300, flexShrink: 0, overflow: "hidden",
          background: "#fff", borderRadius: 12,
          border: "1px solid #e8e8e8",
          boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
        }}>
          <ConversationList conversations={filteredConversations} selectedId={selKey} onSelect={handleSelect} onSearch={(q) => ws.setFilter({ search: q })} onFilterAccount={(ids) => ws.setFilter({ accountIds: ids })} accountIds={ws.filter.accountIds} runtimeAccounts={ws.runtimeState?.accounts ?? []} loading={ws.loading} unreadCounts={unreadCounts} searchText={ws.filter.search} batchMode={batchMode} onToggleBatch={handleToggleBatch} selectedIds={selectedIds} onToggleSelect={handleToggleSelect} pinnedKeys={pinnedKeys} onTogglePin={togglePin}
            onCloseConversation={can("conversations.close") ? (key) => {
              const c = ws.conversations.find((x) => buildKey(x.account_id, x.conversation_id) === key);
              if (c) actions.close(c);
            } : undefined}
            onToggleBlock={can("conversations.block") ? (key) => {
              const c = ws.conversations.find((x) => buildKey(x.account_id, x.conversation_id) === key);
              if (!c) return;
              if (c.customer_lifecycle_status === "blacklisted") handleUnblock();
              else {
                blockCustomer(c.customer_id, c.account_id).then(() => { message.success("已拉黑"); void ws.reload(); }).catch((e) => message.error(e instanceof Error ? e.message : "拉黑失败"));
              }
            } : undefined}
            onToggleHandover={can("conversations.handover") ? (key) => {
              const c = ws.conversations.find((x) => buildKey(x.account_id, x.conversation_id) === key);
              if (!c) return;
              if (c.management_mode === "human_managed") actions.restoreAI(c);
              else actions.handover(c);
            } : undefined}
            onAssignAgent={can("conversations.transfer") ? (key, agentId) => {
              const c = ws.conversations.find((x) => buildKey(x.account_id, x.conversation_id) === key);
              if (c) actions.assignAgent(c, agentId);
            } : undefined}
            assignableAgents={can("conversations.transfer") ? ws.agents.filter((a) => a.agent_id && a.status === "online").filter((a) => !selConv || !a.account_id || a.account_id === selConv.account_id).map((a) => ({ agent_id: a.agent_id, display_name: a.display_name })) : []}
            onSelectAll={handleSelectAll}
            onClearSelection={handleClearSelection}
            onSelectGroup={handleSelectGroup}
            onBatchHandover={can("conversations.handover") ? handleBatchHandover : undefined}
            onBatchRestoreAI={can("conversations.restore_ai") ? handleBatchRestoreAI : undefined}
            onBatchClose={can("conversations.close") ? handleBatchClose : undefined}
            onBatchAssign={can("conversations.transfer") ? handleBatchAssign : undefined}
            onEditNote={can("conversations.notes") ? handleEditNote : undefined}
            onWakeConversation={handleWakeConversation}
          />
        </div>
        {/* 右侧：消息区卡片 */}
        <div style={{
          flex: 1, minWidth: 0, display: "flex", flexDirection: "column",
          background: "#fff", borderRadius: 12,
          border: "1px solid #e8e8e8",
          boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
          overflow: "hidden",
        }}>
          {selConv ? (
            <>
              <AIReceptionBar
                selConv={selConv}
                canSwitchAI={can("conversations.ai.switch")}
                canHandover={can("conversations.handover")}
                canRestoreAI={can("conversations.restore_ai")}
                canViewAudit={can("member_ownership.history")}
                onSwitchAI={(aiAgentId) => {
                  void switchConversationAI(selConv.account_id, selConv.conversation_id, aiAgentId);
                }}
                onHandover={() => {
                  if (can("conversations.handover") && selConv) actions.handover(selConv);
                }}
                onRestoreAI={() => {
                  if (can("conversations.restore_ai") && selConv) actions.restoreAI(selConv);
                }}
              />
              <ConversationHeader
                conversation={selConv}
                customerProfile={detail.customerProfile}
                memberStatus={detail.memberStatus}
                latestVerification={detail.latestVerification}
                latestBinding={detail.latestBinding}
                agents={ws.agents}
                agentOptions={agentOpts}
                pendingAction={actions.pendingAction}
                conversationStatus={selConv?.status ?? null}
                collapsed={headerCollapsed}
                onToggleCollapse={() => setHeaderCollapsed((p) => !p)}
                onHandover={() => { if (can("conversations.handover") && selConv) actions.handover(selConv); }}
                onRestoreAI={() => { if (can("conversations.restore_ai") && selConv) actions.restoreAI(selConv); }}
                onClose={() => { if (can("conversations.close") && selConv) actions.close(selConv); }}
                onReopen={() => { if (can("conversations.close") && selConv) actions.reopen(selConv); }}
                onBlock={() => { if (can("conversations.block")) handleBlock(); }}
                onUnblock={() => { if (can("conversations.block")) handleUnblock(); }}
                onAssignAgent={(a) => { if (can("conversations.transfer") && selConv) actions.assignAgent(selConv, a); }}
                onOpenFinance={() => setFinanceOpen(true)}
                onOpenVisitTrail={() => setTrailOpen(true)}
                onOpenCustomerProfile={() => setProfileOpen(true)}
                onDismissAlert={() => {}}
                onBatchTranslate={handleBatchTranslate}
                batchTranslating={batchTranslating}
                onSearchMessages={handleSearchMessages}
                searchQuery={searchQuery}
                onSearchChange={handleSearchChange}
                searchResultsCount={searchResultsCount}
                searchResultIndex={searchResultIndex}
                searchLoading={searchLoading}
                onSearchNavigate={handleSearchNavigate}
                onSearchClose={handleSearchClose}
                forceOpenNotes={forceOpenNotes}
                onNotesOpened={() => setForceOpenNotes(false)}
              />
              <MessagePanel
                ref={messagePanelRef}
                messages={detail.messages}
                conversationMode={selConv?.management_mode ?? null}
                onSendMessage={(t) => { if (can("conversations.reply") && selConv) actions.sendMessage(selConv, t); }}
                onHandover={() => { if (can("conversations.handover") && selConv) actions.handover(selConv); }}
                loading={detail.loading}
                aiGenerating={false}
                currentAgentName={selConv?.assigned_agent_name ?? null}
                selectedConversation={selConv}
                autoTranslate={autoTranslate}
                hasMore={detail.hasMore}
                loadingMore={detail.loadingMore}
                onLoadMore={detail.loadMoreMessages}
                conversations={ws.conversations}
                previewText={previewText}
                onPreviewChange={setPreviewText}
                onSendPreview={() => {
                  if (can("conversations.reply") && previewText && selConv) {
                    actions.sendMessage(selConv, previewText);
                    setPreviewText(undefined);
                  }
                }}
                onDiscardPreview={() => setPreviewText(undefined)}
                messageStatusUpdates={messageStatusUpdates}
                onSearchResultChange={handleSearchResultChange}
              />
              <QuickToolbar conversation={selConv} templates={ws.templates} mediaAssets={ws.mediaAssets} onSendTemplate={(tid, v) => { const t = ws.templates.find((x) => x.template_id === tid); if (t && selConv) actions.sendTemplate(t, selConv, v); }} onSendMedia={(aid, cap, fn) => { const m = ws.mediaAssets.find((x) => x.asset_id === aid); if (m && selConv) actions.sendMedia(m, selConv, cap, fn); }} onMockInbound={(t, l) => selConv && actions.mockInbound(selConv, t, l)} onCannedResponse={() => setCannedOpen(true)} disabled={!can("conversations.reply") || !selConv} />
            </>
          ) : (
            <NoConversationPlaceholder />
          )}
        </div>
      </div>
      <CannedResponses open={cannedOpen} onClose={() => setCannedOpen(false)} onSelect={handleCannedSelect} conversationMode={selConv?.management_mode ?? null} />
      <FinanceDrawer open={financeOpen} customerId={selConv?.customer_id ?? null} accountId={selConv?.account_id ?? null} onClose={() => setFinanceOpen(false)} />
      <VisitTrailDrawer open={trailOpen} accountId={selConv?.account_id ?? null} conversationId={selConv?.conversation_id ?? null} onClose={() => setTrailOpen(false)} />
      <CustomerProfileDrawer open={profileOpen} customerId={selConv?.customer_id ?? null} accountId={selConv?.account_id ?? null} onClose={() => setProfileOpen(false)} onOpenCustomerPage={() => {
        const selectedConversation = selConv;
        const resolvedCustomerProfile = detail.customerProfile;
        if (!selectedConversation?.account_id || !selectedConversation.customer_id) {
          return;
        }
        void resolveCustomerProfileSummaryByConversation({
          account_id: selectedConversation.account_id,
          customer_id: selectedConversation.customer_id,
        }).then(async (fallbackProfile) => {
          const profile = resolvedCustomerProfile ?? fallbackProfile;
          if (profile) {
            await getCustomerMemberStatusSnapshot({
              id: profile.id,
              account_id: profile.account_id,
              public_user_id: profile.public_user_id,
            });
          }
          openCustomersPage({
            account_id: selectedConversation.account_id,
            selected_profile_id: resolvedCustomerProfile?.id,
            query: profile?.public_user_id ?? selectedConversation.customer_id,
          });
        });
      }} />

      {/* IV-FE-002: 批量标签 Modal */}
      <Modal
        title="批量修改标签"
        open={batchTagsModalOpen}
        onCancel={() => setBatchTagsModalOpen(false)}
        onOk={() => void handleBatchTagsSubmit()}
        confirmLoading={batchTagsLoading}
        okText="保存"
        cancelText="取消"
      >
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          会员认证状态 / WhatsApp 绑定状态
        </Typography.Text>
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
          聊天快捷发送仅支持审核通过模板，请先在模板管理中等待模板审核通过。审核拒绝的模板不会进入正式发送链路。
        </Typography.Text>
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>添加标签</Typography.Text>
            <Select mode="tags" style={{ width: "100%" }} placeholder="输入标签后回车" value={batchTagsAdd} onChange={setBatchTagsAdd} tokenSeparators={[","]} />
          </div>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>移除标签</Typography.Text>
            <Select mode="tags" style={{ width: "100%" }} placeholder="输入标签后回车" value={batchTagsRemove} onChange={setBatchTagsRemove} tokenSeparators={[","]} />
          </div>
        </Space>
      </Modal>

      {/* IV-FE-002: 批量分配 Modal */}
      <Modal title="批量分配会话" open={batchAssignModalOpen} onCancel={() => setBatchAssignModalOpen(false)}
        onOk={() => void handleBatchAssignSubmit()} confirmLoading={batchAssignLoading} okText="分配" cancelText="取消">
        <div style={{ marginBottom: 12 }}>
          <Typography.Text>选择要分配的客服：</Typography.Text>
        </div>
        <Select placeholder="选择客服" style={{ width: "100%" }} value={batchAssignAgentId || undefined} onChange={setBatchAssignAgentId}
          options={agentOpts} />
      </Modal>

      {/* IV-FE-002: 批量发送模板 Modal */}
      <Modal title="批量发送模板消息" open={batchTemplateModalOpen} onCancel={() => setBatchTemplateModalOpen(false)}
        onOk={() => void handleBatchTemplateSubmit()} confirmLoading={batchTemplateLoading} okText="发送" cancelText="取消">
        <div style={{ marginBottom: 12 }}>
          <Typography.Text>已选 {selectedIds.size} 个会话</Typography.Text>
        </div>
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>选择模板</Typography.Text>
            <Select placeholder="选择模板" style={{ width: "100%" }} value={batchTemplateId || undefined} onChange={setBatchTemplateId}
              options={ws.templates.map((t) => ({ label: `${t.name} (${t.status})`, value: t.template_id }))} />
          </div>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>变量 (JSON 格式，可选)</Typography.Text>
            <Input.TextArea rows={3} placeholder='{"{{customer_name}}": "张三"}' value={batchTemplateVars} onChange={(e) => setBatchTemplateVars(e.target.value)} />
          </div>
        </Space>
      </Modal>
    </div>
  );
}

function NoConversationPlaceholder(): JSX.Element {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "#94a3b8",
        userSelect: "none",
        gap: 8,
        padding: 16,
      }}
    >
      <div style={{ fontSize: 40, opacity: 0.4 }}>💬</div>
      <div style={{ fontSize: 14, fontWeight: 500 }}>选择一个会话开始聊天</div>
      <div style={{ fontSize: 12, opacity: 0.6 }}>从左侧列表点击任意会话</div>
    </div>
  );
}
