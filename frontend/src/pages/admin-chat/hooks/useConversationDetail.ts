import { useCallback, useEffect, useRef, useState } from "react";

import {
  getConversationAiStatus,
  listMessages,
  type ConversationAiStatus,
  type ConversationMessage,
  type ConversationSummary,
} from "../../../services/api";
import {
  listCustomerProfiles,
  selectCustomerProfileForConversation,
} from "../../../services/operations";
import { useMemberStatus } from "../../../hooks/useMemberStatus";
import type { CustomerProfileSummary } from "../../../types/operations";

const PAGE_SIZE = 30;

// ── 客户档案缓存：按 account_id 缓存 ──
// 同一账号下切换对话时无需重复拉取全量用户/会话/工单
const profileCache = new Map<string, CustomerProfileSummary[]>();

/** 清除指定账号（或全部）的客户档案缓存 */
export function clearProfileCache(accountId?: string): void {
  if (accountId) {
    profileCache.delete(accountId);
  } else {
    profileCache.clear();
  }
}

// ── 消息预取缓存：hover 时预热 ──
const prefetchCache = new Map<string, { messages: ConversationMessage[]; hasMore: boolean }>();
const PREFETCH_TTL = 30_000; // 30s 过期

// ── 消息长期缓存：切换回已访问对话时即时展示 ──
const MESSAGE_CACHE_TTL = 5 * 60_000; // 5 分钟
const MESSAGE_CACHE_MAX = 50; // 最多缓存 50 个对话
const messagesCache = new Map<string, { messages: ConversationMessage[]; hasMore: boolean; ts: number }>();

/** 清除指定对话的消息缓存（SSE 新消息到达时调用） */
export function clearMessagesCache(accountId?: string, conversationId?: string): void {
  if (accountId && conversationId) {
    messagesCache.delete(`${accountId}:${conversationId}`);
  } else {
    messagesCache.clear();
  }
}

function evictOldestFromMessagesCache(): void {
  if (messagesCache.size <= MESSAGE_CACHE_MAX) return;
  let oldestKey = "";
  let oldestTs = Infinity;
  for (const [k, v] of messagesCache) {
    if (v.ts < oldestTs) { oldestTs = v.ts; oldestKey = k; }
  }
  if (oldestKey) messagesCache.delete(oldestKey);
}

/** hover 对话列表项时预加载消息，点击即可瞬时展示 */
export function prefetchConversation(conv: ConversationSummary): void {
  const key = `${conv.account_id}:${conv.conversation_id}`;
  if (prefetchCache.has(key)) return;
  listMessages(conv.account_id, conv.conversation_id, true, 0, PAGE_SIZE)
    .then((msgs) => {
      prefetchCache.set(key, { messages: msgs, hasMore: msgs.length >= PAGE_SIZE });
      // TTL 过期清理
      setTimeout(() => { prefetchCache.delete(key); }, PREFETCH_TTL);
    })
    .catch(() => {});
}

export interface ConversationDetail {
  messages: ConversationMessage[];
  aiStatus: ConversationAiStatus | null;
  customerProfile: CustomerProfileSummary | null;
  memberStatus: ReturnType<typeof useMemberStatus>["memberStatus"];
  latestVerification: ReturnType<typeof useMemberStatus>["latestVerification"];
  latestBinding: ReturnType<typeof useMemberStatus>["latestBinding"];
  loading: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  loadForConversation: (conv: ConversationSummary) => Promise<void>;
  loadMoreMessages: () => Promise<void>;
  /** 批量翻译后直接应用译文到已加载消息，无需重新请求 */
  applyTranslations: (translations: Record<string, string>) => void;
  reset: () => void;
}

export function useConversationDetail(): ConversationDetail {
  const [messages, setMsgs] = useState<ConversationMessage[]>([]);
  const [aiStatus, setAiSt] = useState<ConversationAiStatus | null>(null);
  const [customerProfile, setProfile] = useState<CustomerProfileSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const currentConvRef = useRef<ConversationSummary | null>(null);
  const offsetRef = useRef(0);
  const loadIdRef = useRef(0); // 竞态保护：每次 loadForConversation 递增，完成后比对
  const lastAccountRef = useRef<string | null>(null);
  const {
    memberStatus,
    latestVerification,
    latestBinding,
    loadMemberStatus,
    resetMemberStatus,
  } = useMemberStatus();

  // Keep latest member-status functions via refs (avoids stale closures in useCallback([]))
  const loadMemberStatusRef = useRef(loadMemberStatus);
  const resetMemberStatusRef = useRef(resetMemberStatus);
  useEffect(() => { loadMemberStatusRef.current = loadMemberStatus; });
  useEffect(() => { resetMemberStatusRef.current = resetMemberStatus; });

  const loadForConversation = useCallback(async (conv: ConversationSummary) => {
    const loadId = ++loadIdRef.current;
    currentConvRef.current = conv;
    offsetRef.current = 0;
    setLoading(true);

    const prefetchKey = `${conv.account_id}:${conv.conversation_id}`;
    const prefetched = prefetchCache.get(prefetchKey);

    // ── 消息加载优先级：长期缓存 > 预取缓存 > 网络请求 ──
    const cached = messagesCache.get(prefetchKey);
    let msgPromise: Promise<ConversationMessage[]>;
    if (cached && (Date.now() - cached.ts) < MESSAGE_CACHE_TTL) {
      msgPromise = Promise.resolve(cached.messages);
    } else if (prefetched) {
      msgPromise = Promise.resolve(prefetched.messages);
    } else {
      msgPromise = listMessages(conv.account_id, conv.conversation_id, true, 0, PAGE_SIZE);
    }

    // ── 客户档案：优先使用账号级缓存 ──
    const accountChanged = lastAccountRef.current !== conv.account_id;
    lastAccountRef.current = conv.account_id;

    let profilePromise: Promise<CustomerProfileSummary | null>;
    if (accountChanged || !profileCache.has(conv.account_id)) {
      // 账号变更或缓存未命中 → 并行拉取
      profilePromise = (async () => {
        const profiles = await listCustomerProfiles(conv.account_id);
        profileCache.set(conv.account_id, profiles);
        return selectCustomerProfileForConversation(profiles, conv);
      })();
    } else {
      // 缓存命中 → 同步查找
      profilePromise = Promise.resolve(
        selectCustomerProfileForConversation(profileCache.get(conv.account_id)!, conv)
      );
    }

    // ── 三路并行：消息 + AI状态 + 客户档案 ──
    const results = await Promise.allSettled([
      msgPromise,
      getConversationAiStatus(conv.account_id, conv.conversation_id),
      profilePromise,
    ]);

    // 竞态保护：如果在此期间触发了新的加载，放弃本次结果
    if (loadId !== loadIdRef.current) return;

    // 消息
    if (results[0].status === "fulfilled") {
      const m = results[0].value;
      setMsgs(m);
      setHasMore(m.length >= PAGE_SIZE);
      offsetRef.current = m.length;
      // 写入长期缓存（仅当来自网络请求时）
      if (!cached || (Date.now() - cached.ts) >= MESSAGE_CACHE_TTL) {
        evictOldestFromMessagesCache();
        messagesCache.set(prefetchKey, { messages: m, hasMore: m.length >= PAGE_SIZE, ts: Date.now() });
      }
      // 消耗预取缓存
      prefetchCache.delete(prefetchKey);
    } else {
      console.error("loadForConversation listMessages failed", results[0].reason);
      setMsgs([]);
      setHasMore(false);
    }

    // AI 状态
    if (results[1].status === "fulfilled") {
      setAiSt(results[1].value);
    } else {
      console.error("loadForConversation aiStatus failed", results[1].reason);
      setAiSt(null);
    }

    // 客户档案（消息已渲染后才加载，不阻塞主内容展示）
    if (results[2].status === "fulfilled") {
      const p = results[2].value;
      setProfile(p);
      if (p) {
        // 异步加载会员状态，不阻塞 loading 结束
        loadMemberStatusRef.current(p).catch(() => {});
      } else {
        resetMemberStatusRef.current();
      }
    } else {
      console.error("loadForConversation customerProfile failed", results[2].reason);
      setProfile(null);
      resetMemberStatusRef.current();
    }

    if (loadId !== loadIdRef.current) return;
    setLoading(false);
  }, []);

  const loadMoreMessages = useCallback(async () => {
    const conv = currentConvRef.current;
    if (!conv || !hasMore || loadingMore) return;
    setLoadingMore(true);
    try {
      const older = await listMessages(
        conv.account_id,
        conv.conversation_id,
        true,
        offsetRef.current,
        PAGE_SIZE,
      );
      if (older.length > 0) {
        setMsgs((prev) => [...older, ...prev]);
        offsetRef.current += older.length;
        setHasMore(older.length >= PAGE_SIZE);
      } else {
        setHasMore(false);
      }
    } catch {
      // silent
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, loadingMore]);

  const applyTranslations = useCallback((translations: Record<string, string>) => {
    setMsgs((prev) =>
      prev.map((m) =>
        m.message_id && translations[m.message_id]
          ? { ...m, translated_text: translations[m.message_id] }
          : m
      )
    );
  }, []);

  const reset = useCallback(() => {
    setMsgs([]);
    setAiSt(null);
    setProfile(null);
    setHasMore(false);
    setLoading(true);
    currentConvRef.current = null;
    offsetRef.current = 0;
    resetMemberStatusRef.current();
  }, []);

  return {
    messages,
    aiStatus,
    customerProfile,
    memberStatus,
    latestVerification,
    latestBinding,
    loading,
    hasMore,
    loadingMore,
    loadForConversation,
    loadMoreMessages,
    applyTranslations,
    reset,
  };
}
