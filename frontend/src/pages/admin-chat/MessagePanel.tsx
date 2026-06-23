import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import type { JSX } from "react";

import { AutoComplete, Button, Checkbox, Input, message, Modal, Popconfirm, Popover, Select, Spin, Tabs, Typography } from "antd";
import {
  SmileOutlined,
  TranslationOutlined,
  LoadingOutlined,
  ForwardOutlined,
  SearchOutlined,
  UpOutlined,
  DownOutlined,
  CloseOutlined,
  SendOutlined,
  EditOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { Virtuoso, VirtuosoHandle } from "react-virtuoso";

import {
  getMessagePrimaryText,
  getMessageTranslationAssistText,
  translateMessage,
  translateOutboundPreview,
  searchConversationMessages,
  forwardMessage,
  uploadMediaAsset,
  sendConversationMediaMessage,
} from "../../services/api";
import type { ConversationMessage, ConversationSummary } from "../../services/api";
import { MessageBubble, DeliveryStatusIcon, formatTime, isInternalNote, isNonTextType } from "./MessageBubble";

/** 12×12 = 144 精选表情 */
const EMOJI_144 = [
  "😀","😃","😄","😁","😆","😅","🤣","😂","🙂","😊","😇","🥰",
  "😍","🤩","😘","😗","😚","😋","😛","😜","🤪","😝","🤑","🤗",
  "🤭","🤫","🤔","🤐","🤨","😐","😑","😶","😏","😒","🙄","😬",
  "😮","😯","😲","😳","🥺","😢","😭","😤","😡","😠","🤬","😈",
  "👋","🤚","🖐","✋","🖖","👌","🤏","✌️","🤞","🤟","🤘","🤙",
  "👈","👉","👆","👇","☝️","👍","👎","✊","👊","🤛","🤜","👏",
  "❤️","🧡","💛","💚","💙","💜","🖤","🤍","🤎","💔","❣️","💕",
  "💞","💓","💗","💖","💘","💝","💟","☮️","✝️","☪️","🕉","☸️",
  "🐶","🐱","🐭","🐹","🐰","🦊","🐻","🐼","🐨","🐯","🦁","🐮",
  "🐷","🐸","🐵","🐔","🐧","🐦","🐤","🦄","🐝","🐞","🦋","🐙",
  "🍎","🍊","🍋","🍉","🍇","🍓","🍒","🍑","🥝","🍕","🍔","🍟",
  "🎂","🍩","🍿","☕","🍵","🍺","🎉","🎊","🎈","🎁","🏆","⚽",
];

function Emoji144Grid({ onPick }: { onPick: (e: string) => void }): JSX.Element {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(12, 26px)",
      gap: 2,
      padding: 4,
      maxHeight: 280,
      overflowY: "auto",
    }}>
      {EMOJI_144.map((e) => (
        <button
          key={e}
          onClick={() => onPick(e)}
          style={{
            width: 26, height: 26,
            border: "none",
            background: "transparent",
            cursor: "pointer",
            fontSize: 17,
            lineHeight: "26px",
            textAlign: "center",
            padding: 0,
            borderRadius: 3,
          }}
          onMouseEnter={(ev) => { (ev.target as HTMLElement).style.background = "#e6f4ff"; }}
          onMouseLeave={(ev) => { (ev.target as HTMLElement).style.background = "transparent"; }}
        >
          {e}
        </button>
      ))}
    </div>
  );
}

const { TextArea } = Input;

function formatDate(ts: string): string {
  const d = new Date(ts);
  const now = new Date();
  const isToday =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday =
    d.getFullYear() === yesterday.getFullYear() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getDate() === yesterday.getDate();
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  if (isToday) return "今天";
  if (isYesterday) return "昨天";
  return `${d.getMonth() + 1}月${d.getDate()}日 ${weekdays[d.getDay()]})`;
}


function fmtLangLabel(code: string): string {
  const map: Record<string, string> = { "zh-CN": "中文", en: "英文", ja: "日文", es: "西班牙文", fr: "法文", de: "德文", pt: "葡萄牙文", ko: "韩文", ar: "阿拉伯文", ru: "俄文" };
  return map[code] ?? code;
}

export interface MessagePanelHandle {
  insertText: (text: string) => void;
  /** ①: 搜索消息 */
  searchMessages: (query: string) => Promise<void>;
  /** ①: 导航搜索结果 */
  navigateSearch: (direction: "prev" | "next") => void;
  /** ①: 关闭搜索 */
  closeSearch: () => void;
}

export interface MessagePanelProps {
  messages: ConversationMessage[];
  conversationMode: "ai_managed" | "human_managed" | "paused" | null;
  onSendMessage: (text: string) => void;
  onSendNote?: (text: string) => void;
  /** AI托管时点击发送按钮 → 确认切换到人工接管 */
  onHandover?: () => void;
  loading: boolean;
  aiGenerating: boolean;
  currentAgentName: string | null;
  selectedConversation: ConversationSummary | null;
  // Infinite scroll
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  /** 自动翻译开关，勾选后新消息自动翻译 */
  autoTranslate?: boolean;
  // F-01: 消息搜索
  searchVisible?: boolean;
  onToggleSearch?: () => void;
  /** ①: 搜索结果变化回调，向父组件上报 count 和当前 index */
  onSearchResultChange?: (count: number, index: number) => void;
  // F-04: AI 回复预览
  previewText?: string;
  onPreviewChange?: (text: string) => void;
  onSendPreview?: () => void;
  onDiscardPreview?: () => void;
  // F-08: 转发
  conversations?: ConversationSummary[];
  // F-13: 消息已读回执实时更新
  messageStatusUpdates?: Record<string, string>;
}

export const MessagePanel = forwardRef<MessagePanelHandle, MessagePanelProps>(function MessagePanel({
  messages,
  conversationMode,
  onSendMessage,
  onSendNote,
  onHandover,
  loading,
  aiGenerating,
  currentAgentName,
  selectedConversation,
  hasMore,
  loadingMore,
  onLoadMore,
  autoTranslate,
  previewText,
  onPreviewChange,
  onSendPreview,
  onDiscardPreview,
  conversations = [],
  messageStatusUpdates,
  onSearchResultChange,
}, ref) {
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [newMsgCount, setNewMsgCount] = useState(0);
  const prevMsgLenRef = useRef(messages.length);
  const [messageText, setMessageText] = useState("");
  const [noteText, setNoteText] = useState("");
  const [inputTab, setInputTab] = useState<"message" | "note">("message");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [emojiOpen, setEmojiOpen] = useState(false);

  // F-01: 搜索状态
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ConversationMessage[]>([]);
  const [searchResultIndex, setSearchResultIndex] = useState(0);
  const [searching, setSearching] = useState(false);
  const searchHighlightRef = useRef<Record<string, boolean>>({});

  // F-08: 转发状态
  const [forwardModalOpen, setForwardModalOpen] = useState(false);
  const [forwardMsg, setForwardMsg] = useState<ConversationMessage | null>(null);
  const [forwardTargetConvId, setForwardTargetConvId] = useState<string>("");
  const [forwardIncludeCtx, setForwardIncludeCtx] = useState(false);
  const [forwarding, setForwarding] = useState(false);

  // 图片粘贴上传状态
  const [pastingImages, setPastingImages] = useState<
    Array<{ id: string; file: File; previewUrl: string; uploading: boolean; error: string | null }>
  >([]);
  const pasteIdRef = useRef(0);

  // F-04: AI 预览编辑
  const [previewEditText, setPreviewEditText] = useState("");
  // Sync external preview text into local editable state
  useEffect(() => {
    if (previewText !== undefined) {
      setPreviewEditText(previewText);
    }
  }, [previewText]);

  // 翻译状态
  const [translatingIds, setTranslatingIds] = useState<Set<string>>(new Set());
  const [freshTranslations, setFreshTranslations] = useState<Record<string, string>>({});
  const [sendLang, setSendLang] = useState<string>("original");
  const [outboundTranslating, setOutboundTranslating] = useState(false);

  // 草稿保存
  const [sendError, setSendError] = useState<string | null>(null);
  const draftKey = useMemo(() => {
    if (!selectedConversation) return null;
    return `draft:${selectedConversation.account_id}:${selectedConversation.conversation_id}`;
  }, [selectedConversation?.account_id, selectedConversation?.conversation_id]);

  // 切换会话时：保存当前草稿、恢复新会话草稿
  useEffect(() => {
    const prevDraftKey = sessionStorage.getItem("_active_draft_key");
    // Save current draft
    if (prevDraftKey && messageText.trim()) {
      sessionStorage.setItem(prevDraftKey, messageText);
    }
    // Restore draft for new conversation
    if (draftKey) {
      const saved = sessionStorage.getItem(draftKey);
      setMessageText(saved || "");
      sessionStorage.setItem("_active_draft_key", draftKey);
    }
    setSendError(null);
  }, [draftKey]);

  // 发送成功后清除草稿
  const handleSendSuccess = useCallback(() => {
    setMessageText("");
    setSendError(null);
    if (draftKey) sessionStorage.removeItem(draftKey);
  }, [draftKey]);

  // 自动翻译：记录已触发的消息 ID，避免重复翻译
  const autoTranslatedRef = useRef<Set<string>>(new Set());
  // 自动翻译：仅处理该索引之后的新消息，避免勾选时翻译已有历史
  const autoTranslateIndexRef = useRef<number>(0);

  // FX-007: 备注模式
  const isNoteMode = inputTab === "note";
  const textareaBg = isNoteMode ? "#fffbe6" : undefined;

  const handleEmojiClick = useCallback((emoji: string) => {
    setEmojiOpen(false);
    if (isNoteMode) {
      setNoteText((p) => {
        const ta = textareaRef.current;
        if (!ta) return p + emoji;
        const start = ta.selectionStart ?? p.length;
        return p.slice(0, start) + emoji + p.slice(start);
      });
    } else {
      setMessageText((p) => {
        const ta = textareaRef.current;
        if (!ta) return p + emoji;
        const start = ta.selectionStart ?? p.length;
        return p.slice(0, start) + emoji + p.slice(start);
      });
    }
    // 选中表情后关闭选择器
  }, [isNoteMode]);

  const closeEmoji = useCallback(() => setEmojiOpen(false), []);

  // 图片粘贴处理：检测剪贴板中的图片，上传后自动发送
  const handlePaste = useCallback(
    (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      if (!selectedConversation) return;
      const items = e.clipboardData?.items;
      if (!items || items.length === 0) return;

      const imageFiles: File[] = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === "file" && item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) imageFiles.push(file);
        }
      }
      if (imageFiles.length === 0) return; // 无图片，让默认粘贴行为处理文本

      e.preventDefault(); // 阻止默认粘贴（避免粘贴图片二进制到文本框）

      const newItems = imageFiles.map((file) => {
        const id = `paste-${++pasteIdRef.current}`;
        const previewUrl = URL.createObjectURL(file);
        return { id, file, previewUrl, uploading: true, error: null as string | null };
      });

      setPastingImages((prev) => [...prev, ...newItems]);

      // 逐个上传并发送
      for (const item of newItems) {
        const uploadAndSend = async () => {
          try {
            const asset = await uploadMediaAsset({
              account_id: selectedConversation.account_id,
              file: item.file,
              waba_id: selectedConversation.waba_id ?? undefined,
              phone_number_id: selectedConversation.phone_number_id ?? undefined,
              asset_type: "image",
              mime_type: item.file.type,
              source: "chat_paste",
            });
            await sendConversationMediaMessage(
              selectedConversation.account_id,
              selectedConversation.conversation_id,
              { asset_id: asset.asset_id },
            );
            // 上传+发送成功，移除预览
            setPastingImages((prev) => prev.filter((p) => p.id !== item.id));
            URL.revokeObjectURL(item.previewUrl);
          } catch (err) {
            setPastingImages((prev) =>
              prev.map((p) =>
                p.id === item.id
                  ? { ...p, uploading: false, error: err instanceof Error ? err.message : "发送失败" }
                  : p,
              ),
            );
          }
        };
        void uploadAndSend();
      }
    },
    [selectedConversation],
  );

  const datedMessages = useMemo(() => {
    const result: Array<{ type: "date"; date: string } | { type: "msg"; msg: ConversationMessage }> = [];
    let lastDate = "";
    for (const msg of messages) {
      const d = new Date(msg.created_at);
      const dateStr = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
      if (dateStr !== lastDate) {
        result.push({ type: "date", date: msg.created_at });
        lastDate = dateStr;
      }
      result.push({ type: "msg", msg });
    }
    return result;
  }, [messages]);

  // 自动滚动 — 使用 Virtuoso followOutput（无滚动动画，默认到底部）
  const followOutput = useCallback(() => isAtBottom ? "auto" : false, [isAtBottom]);

  // 新消息计数
  useEffect(() => {
    if (messages.length > prevMsgLenRef.current && !isAtBottom) {
      setNewMsgCount((c) => c + (messages.length - prevMsgLenRef.current));
    }
    prevMsgLenRef.current = messages.length;
  }, [messages.length, isAtBottom]);

  // 自动翻译：autoTranslate 开启时，新到未翻译消息（入站 + AI外文回复）自动触发翻译
  useEffect(() => {
    if (!autoTranslate || !selectedConversation) {
      // 关闭自动翻译时记录当前游标，下次开启仅处理之后的新消息
      autoTranslateIndexRef.current = messages.length;
      return;
    }
    const startIdx = autoTranslateIndexRef.current;
    const candidates = messages.slice(startIdx).filter((m) => {
      const mid = m.message_id;
      if (!mid) return false;
      // 已触发过
      if (autoTranslatedRef.current.has(mid)) return false;
      // 仅入站 + AI 外文回复，非系统、非备注
      const translatable = m.direction === "inbound" || (m.direction === "outbound" && m.ai_generated);
      if (!translatable || m.message_type === "system" || m.message_type === "note") return false;
      // 语言非中文才需要翻译
      if (!m.language_code || m.language_code === "zh-CN") return false;
      // 已有预存翻译
      if (getMessageTranslationAssistText(m)) return false;
      return true;
    });
    // 推进游标，下次从新尾部开始
    autoTranslateIndexRef.current = messages.length;
    if (candidates.length === 0) return;
    // 标记为已触发，避免重复
    for (const m of candidates) {
      if (m.message_id) autoTranslatedRef.current.add(m.message_id);
    }
    // 逐个触发翻译（顺序执行避免并发风暴）
    const run = async () => {
      for (const m of candidates) {
        try {
          await handleTranslateMessage(m);
        } catch {
          // 单条失败不影响其他
        }
      }
    };
    run();
  }, [messages, autoTranslate, selectedConversation]);

  const handleScroll = () => {
    // Scroll handling is now managed by Virtuoso's atBottomStateChange
  };

  const scrollToBottom = () => {
    virtuosoRef.current?.scrollToIndex({ index: "LAST", behavior: "auto" });
    setNewMsgCount(0);
    setIsAtBottom(true);
  };

  // Virtuoso atBottomState change handler
  const handleAtBottomStateChange = useCallback((atBottom: boolean) => {
    setIsAtBottom(atBottom);
    if (atBottom) setNewMsgCount(0);
  }, []);

  // Virtuoso startReached: trigger load-more of older messages
  const handleStartReached = useCallback(() => {
    if (hasMore && !loadingMore) {
      onLoadMore();
    }
  }, [hasMore, loadingMore, onLoadMore]);

  const handleSendMessage = async () => {
    const text = messageText.trim();
    if (!text) return;
    setEmojiOpen(false);

    const doSend = (finalText: string) => {
      onSendMessage(finalText);
      handleSendSuccess();
      setSendLang("original");
      setSendError(null);
    };

    if (sendLang !== "original") {
      const conv = selectedConversation;
      if (!conv) return;
      setOutboundTranslating(true);
      try {
        const result = await translateOutboundPreview(conv.account_id, conv.conversation_id, text, sendLang);
        setOutboundTranslating(false);
        doSend(result.translated_text);
      } catch {
        setOutboundTranslating(false);
        doSend(text);
      }
    } else {
      doSend(text);
    }
  };

  const handleTranslateMessage = async (msg: ConversationMessage) => {
    const conv = selectedConversation;
    if (!conv || !msg.message_id) return;

    setTranslatingIds((prev) => {
      const next = new Set(prev);
      next.add(msg.message_id!);
      return next;
    });
    try {
      const result = await translateMessage(conv.account_id, conv.conversation_id, msg.message_id!);
      if (result.translated_text) {
        setFreshTranslations((prev) => ({
          ...prev,
          [msg.message_id!]: result.translated_text!,
        }));
      }
    } finally {
      setTranslatingIds((prev) => {
        const next = new Set(prev);
        next.delete(msg.message_id!);
        return next;
      });
    }
  };

  // F-01: 搜索消息 — 滚动到指定消息
  const scrollToMessage = useCallback((msgId: string) => {
    // Find index in datedMessages
    const idx = datedMessages.findIndex((item) => item.type === "msg" && item.msg.message_id === msgId);
    if (idx >= 0) {
      virtuosoRef.current?.scrollToIndex({ index: idx, align: "center", behavior: "smooth" });
    }
    // Yellow highlight animation
    setTimeout(() => {
      const el = document.querySelector(`[data-message-id="${msgId}"]`);
      if (el) {
        el.classList.add("fx-search-highlight");
        setTimeout(() => el.classList.remove("fx-search-highlight"), 1500);
      }
    }, 100);
  }, [datedMessages]);

  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);
    if (!query.trim() || !selectedConversation) {
      setSearchResults([]);
      setSearchResultIndex(0);
      searchHighlightRef.current = {};
      return;
    }
    setSearching(true);
    try {
      const results = await searchConversationMessages(
        selectedConversation.account_id,
        selectedConversation.conversation_id,
        query.trim(),
      );
      setSearchResults(results);
      setSearchResultIndex(results.length > 0 ? 0 : -1);
      onSearchResultChange?.(results.length, results.length > 0 ? 0 : -1);
      // Mark IDs for highlighting
      const map: Record<string, boolean> = {};
      for (const r of results) {
        if (r.message_id) map[r.message_id] = true;
      }
      searchHighlightRef.current = map;
      // Scroll to first result
      if (results.length > 0 && results[0].message_id) {
        scrollToMessage(results[0].message_id);
      }
    } catch {
      message.error("搜索失败");
    } finally {
      setSearching(false);
    }
  }, [selectedConversation, scrollToMessage]);

  const navigateSearchResult = useCallback((direction: "prev" | "next") => {
    if (searchResults.length === 0) return;
    let newIdx = searchResultIndex;
    if (direction === "next") {
      newIdx = (searchResultIndex + 1) % searchResults.length;
    } else {
      newIdx = (searchResultIndex - 1 + searchResults.length) % searchResults.length;
    }
    setSearchResultIndex(newIdx);
    onSearchResultChange?.(searchResults.length, newIdx);
    const msg = searchResults[newIdx];
    if (msg?.message_id) {
      scrollToMessage(msg.message_id);
    }
  }, [searchResults, searchResultIndex, scrollToMessage, onSearchResultChange]);

  const closeSearch = useCallback(() => {
    setSearchQuery("");
    setSearchResults([]);
    setSearchResultIndex(0);
    onSearchResultChange?.(0, 0);
    searchHighlightRef.current = {};
  }, [onSearchResultChange]);

  // ①: 暴露 insertText + 搜索方法给父组件
  useImperativeHandle(ref, () => ({
    insertText(text: string) {
      if (!isNoteMode) {
        setMessageText((p) => {
          const ta = textareaRef.current;
          if (!ta) return p + text;
          const start = ta.selectionStart ?? p.length;
          return p.slice(0, start) + text + p.slice(start);
        });
      }
    },
    searchMessages: handleSearch,
    navigateSearch: navigateSearchResult,
    closeSearch: () => {
      setSearchQuery("");
      setSearchResults([]);
      setSearchResultIndex(0);
      onSearchResultChange?.(0, 0);
      searchHighlightRef.current = {};
    },
  }), [isNoteMode, handleSearch, navigateSearchResult]);

  // F-08: 转发消息
  const openForwardModal = useCallback((msg: ConversationMessage) => {
    setForwardMsg(msg);
    setForwardTargetConvId("");
    setForwardIncludeCtx(false);
    setForwardModalOpen(true);
  }, []);

  const handleForward = useCallback(async () => {
    if (!forwardMsg || !forwardTargetConvId || !selectedConversation) return;
    setForwarding(true);
    try {
      await forwardMessage(
        selectedConversation.account_id,
        selectedConversation.conversation_id,
        forwardMsg.message_id,
        forwardTargetConvId,
        forwardIncludeCtx,
      );
      message.success("消息已转发");
      setForwardModalOpen(false);
    } catch (e: unknown) {
      message.error(`转发失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setForwarding(false);
    }
  }, [forwardMsg, forwardTargetConvId, forwardIncludeCtx, selectedConversation]);

  // F-14: ~ 跳到最新消息（仅人工会话）
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      // ~ (Backquote): 跳转到最新消息（仅人工会话生效）
      if (e.key === "`" && !e.ctrlKey && !e.altKey && !e.metaKey && conversationMode === "human_managed") {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") {
          e.preventDefault();
          scrollToBottom();
        }
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [conversationMode, scrollToBottom]);

  // F-04: 处理发送 AI 预览
  const handleSendPreviewLocal = useCallback(() => {
    if (previewEditText.trim()) {
      onSendMessage(previewEditText.trim());
      onDiscardPreview?.();
    }
  }, [previewEditText, onSendMessage, onDiscardPreview]);

  const handleSendNote = () => {
    const text = noteText.trim();
    if (text && onSendNote) {
      onSendNote(text);
      setNoteText("");
    }
  };

  // 切换会话时清理输入态（sendLang 仅在不适用时重置，减少重复设置）
  useEffect(() => {
    setMessageText("");
    setNoteText("");
    // sendLang：仅在当前值对新对话不适用时才回退为 original
    const customerLang = selectedConversation?.customer_language;
    const validLangs = ["original", ...(customerLang && customerLang !== "zh-CN" ? [customerLang] : [])];
    setSendLang((prev) => validLangs.includes(prev) ? prev : "original");
    setFreshTranslations({});
    setTranslatingIds(new Set());
    setInputTab("message");
    setEmojiOpen(false);
    setNewMsgCount(0);
    setIsAtBottom(true);
    prevMsgLenRef.current = 0;
    autoTranslatedRef.current = new Set();
    autoTranslateIndexRef.current = 0;
    // F-09: 延迟滚动到底部，确保 Virtuoso 已渲染新消息
    const timer = setTimeout(() => {
      virtuosoRef.current?.scrollToIndex({ index: "LAST", behavior: "auto" });
    }, 80);
    return () => clearTimeout(timer);
  }, [selectedConversation?.conversation_id]);

  const isPaused = conversationMode === "paused";
  const isAiManaged = conversationMode === "ai_managed";
  const isHumanManaged = conversationMode === "human_managed";

  // 空状态
  if (!selectedConversation) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "#999",
          userSelect: "none",
          padding: 16,
        }}
      >
        <div style={{ fontSize: 28, marginBottom: 6 }}>💬</div>
        <div style={{ fontSize: 12, marginBottom: 3 }}>选择一个会话开始聊天</div>
        <div style={{ fontSize: 11, color: "#ccc", lineHeight: 1.6, textAlign: "center" }}>
          <div>Enter 发送 · Shift+Enter 换行</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      {/* ①: 搜索栏已移至会话头，此处不再渲染 */}
      {/* 消息区 — 虚拟滚动 */}
      <Virtuoso
        ref={virtuosoRef}
        style={{ flex: 1, minHeight: 0 }}
        totalCount={datedMessages.length}
        data={datedMessages}
        followOutput={followOutput}
        atBottomStateChange={handleAtBottomStateChange}
        startReached={handleStartReached}
        overscan={200}
        components={{
          Header: () => (
            <>
              {loadingMore && (
                <div style={{ textAlign: "center", padding: 8, fontSize: 12, color: "#999" }}>
                  加载更早消息...
                </div>
              )}
              {loading && messages.length === 0 && (
                <div style={{
                  display: "flex", flexDirection: "column", alignItems: "center",
                  justifyContent: "center", height: "100%", gap: 16, padding: 40,
                }}>
                  <Spin size="large" />
                  <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                    加载消息中…
                  </Typography.Text>
                </div>
              )}
            </>
          ),
          Footer: () => (
            <>
              {aiGenerating && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "8px 12px", margin: "4px 0",
                  background: "#f0f7ff", borderRadius: 8,
                  border: "1px dashed #b3d8ff",
                }}>
                  <span style={{ fontSize: 18, lineHeight: 1 }}>🤖</span>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <span style={{ fontSize: 12, color: "#1677ff", fontWeight: 500 }}>
                      AI 正在回复…
                    </span>
                    <span style={{ display: "flex", gap: 3 }}>
                      {[0, 1, 2].map((i) => (
                        <span
                          key={i}
                          style={{
                            width: 5, height: 5, borderRadius: "50%",
                            backgroundColor: "#1677ff", display: "inline-block",
                            animation: `aiBounce 1.4s ${i * 0.2}s infinite ease-in-out`,
                          }}
                        />
                      ))}
                    </span>
                  </div>
                </div>
              )}
              {newMsgCount > 0 && (
                <div
                  onClick={scrollToBottom}
                  style={{
                    textAlign: "center", cursor: "pointer", color: "#1677ff",
                    fontSize: 12, background: "rgba(255,255,255,0.9)",
                    padding: "4px 12px", borderRadius: 12,
                    border: "1px solid #e6f4ff",
                  }}
                >
                  ↑ {newMsgCount} 条新消息
                </div>
              )}
            </>
          ),
        }}
        itemContent={(_index: number, item: typeof datedMessages[number]) => {
          if (item.type === "date") {
            return (
              <div
                style={{
                  textAlign: "center", margin: "16px 0 8px",
                  position: "relative", color: "#bbb", fontSize: 12,
                }}
              >
                <span style={{ background: "#fff", padding: "0 12px", position: "relative", zIndex: 1 }}>
                  {formatDate(item.date)}
                </span>
              </div>
            );
          }
          const msg = item.msg;
          return (
            <MessageBubble
              msg={msg}
              currentAgentName={currentAgentName}
              freshTranslations={freshTranslations}
              translatingIds={translatingIds}
              messageStatusUpdates={messageStatusUpdates}
              isHighlight={searchHighlightRef.current[msg.message_id || ""] || false}
              onTranslate={handleTranslateMessage}
              onForward={openForwardModal}
            />
          );
        }}
      />

      {/* F-04: AI 回复预览条 */}
      {isAiManaged && previewText !== undefined && (
        <div
          style={{
            borderTop: "1px solid #b3d8ff",
            borderBottom: "1px solid #e8e8e8",
            padding: "8px 12px",
            background: "#f0f7ff",
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 18 }}>🤖</span>
            <Typography.Text style={{ fontSize: 12, color: "#1677ff", fontWeight: 500 }}>
              AI 回复预览
            </Typography.Text>
          </div>
          <TextArea
            value={previewEditText}
            onChange={(e) => {
              setPreviewEditText(e.target.value);
              onPreviewChange?.(e.target.value);
            }}
            autoSize={{ minRows: 2, maxRows: 4 }}
            style={{ fontSize: 13 }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <Button
              size="small"
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSendPreviewLocal}
              disabled={!previewEditText.trim()}
            >
              发送
            </Button>
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                setMessageText(previewEditText);
                onDiscardPreview?.();
              }}
            >
              编辑后发送
            </Button>
            <Button
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => onDiscardPreview?.()}
            >
              丢弃
            </Button>
          </div>
        </div>
      )}

      {/* AI 回复动画 keyframes */}
      <style>{`
        @keyframes aiBounce {
          0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
          40% { opacity: 1; transform: scale(1.2); }
        }
        @keyframes loadingBar {
          from { opacity: 0.15; }
          to { opacity: 0.6; }
        }
        @keyframes fxSearchHighlight {
          0% { box-shadow: 0 0 0 0 rgba(250, 173, 20, 0.6); }
          50% { box-shadow: 0 0 0 6px rgba(250, 173, 20, 0); }
          100% { box-shadow: 0 0 0 0 rgba(250, 173, 20, 0); }
        }
        .fx-search-highlight {
          animation: fxSearchHighlight 1.5s ease-out;
        }
        .fx-search-highlight-msg {
          background-color: #fff3cd !important;
        }
      `}</style>

      {/* 底部输入区 */}
      <div
        style={{
          borderTop: "1px solid #f0f0f0",
          padding: "8px 12px",
          flexShrink: 0,
        }}
      >
        {/* FX-007: 消息/备注 Tab 切换 */}
        {onSendNote && (
          <div style={{ marginBottom: 6 }}>
            <Tabs
              activeKey={inputTab}
              onChange={(k) => setInputTab(k as "message" | "note")}
              size="small"
              items={[
                { key: "message", label: "消息" },
                { key: "note", label: "备注" },
              ]}
              style={{ marginBottom: 0 }}
              tabBarStyle={{ marginBottom: 0 }}
            />
          </div>
        )}
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <div style={{ flex: 1, position: "relative" }}>
            <TextArea
              ref={textareaRef}
              value={isNoteMode ? noteText : messageText}
              onChange={(e) => {
                if (isNoteMode) setNoteText(e.target.value);
                else setMessageText(e.target.value);
              }}
              onPaste={handlePaste}
              placeholder={
                isPaused
                  ? "聊天已暂停"
                  : isNoteMode
                    ? "输入内部备注（仅团队可见）"
                    : isHumanManaged
                      ? "输入消息发送... (Enter发送)"
                      : isAiManaged
                        ? "AI 托管中，点击右侧按钮切换人工接管"
                        : "输入消息... (Enter发送)"
              }
              disabled={isPaused || isAiManaged}
              autoSize={{ minRows: 3, maxRows: 6 }}
              onKeyDown={(e) => {
                // F-14: Enter 发送（非中文输入法组合态），Esc 清空，Ctrl+Enter 换行（默认行为）
                if (e.key === "Escape") {
                  if (isNoteMode) setNoteText("");
                  else setMessageText("");
                  e.preventDefault();
                  return;
                }
                if (isAiManaged) return;
                if (e.key === "Enter") {
                  // Ctrl+Enter 换行：让默认行为处理
                  if (e.ctrlKey) return;
                  // 中文输入法组合态时不发送
                  if (e.nativeEvent.isComposing) return;
                  e.preventDefault();
                  if (isNoteMode) handleSendNote();
                  else handleSendMessage();
                }
              }}
              style={{ width: "100%", background: textareaBg, fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans','Helvetica Neue',Arial,sans-serif,'Apple Color Emoji','Segoe UI Emoji'" }}
            />
            <Popover
              content={<Emoji144Grid onPick={handleEmojiClick} />}
              trigger="click"
              open={emojiOpen}
              onOpenChange={setEmojiOpen}
              placement="topLeft"
            >
              <Button
                icon={<SmileOutlined />}
                size="small"
                type="text"
                style={{ position: "absolute", right: 4, bottom: 6, color: "#999" }}
                title="表情"
              />
            </Popover>
          </div>
          {/* 图片粘贴预览 */}
          {pastingImages.length > 0 && (
            <div style={{
              display: "flex", gap: 8, flexWrap: "wrap", padding: "4px 0",
              alignItems: "flex-end",
            }}>
              {pastingImages.map((img) => (
                <div
                  key={img.id}
                  style={{
                    position: "relative", width: 56, height: 56,
                    borderRadius: 6, overflow: "hidden",
                    border: img.error ? "2px solid #ff4d4f" : "1px solid #d9d9d9",
                    flexShrink: 0,
                  }}
                >
                  <img
                    src={img.previewUrl}
                    alt="粘贴预览"
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                  {img.uploading && (
                    <div style={{
                      position: "absolute", inset: 0,
                      background: "rgba(0,0,0,0.35)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <LoadingOutlined style={{ color: "#fff", fontSize: 18 }} />
                    </div>
                  )}
                  {img.error && (
                    <div
                      style={{
                        position: "absolute", bottom: 0, left: 0, right: 0,
                        background: "#ff4d4f", color: "#fff", fontSize: 9,
                        textAlign: "center", padding: "1px 2px",
                        cursor: "pointer",
                      }}
                      onClick={() => {
                        URL.revokeObjectURL(img.previewUrl);
                        setPastingImages((prev) => prev.filter((p) => p.id !== img.id));
                      }}
                      title={img.error}
                    >
                      ✕ 失败
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {/* 右侧：原文发送下拉 + 发送消息按钮，纵向排列 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "stretch", flexShrink: 0 }}>
            {!isNoteMode && !isAiManaged && (
              <Select
                size="small"
                value={sendLang}
                onChange={setSendLang}
                style={{ width: 140 }}
                options={[
                  { value: "original", label: "原文发送" },
                  ...(selectedConversation?.customer_language &&
                    selectedConversation.customer_language !== "zh-CN"
                    ? [
                        {
                          value: selectedConversation.customer_language,
                          label: `翻译为${fmtLangLabel(selectedConversation.customer_language)}发送`,
                        },
                      ]
                    : []),
                ]}
              />
            )}
            {isAiManaged && onHandover ? (
              <Popconfirm
                title="切换到人工接管？"
                description="接管后 AI 将停止自动回复，由您手动处理"
                onConfirm={onHandover}
                okText="确认接管"
                cancelText="取消"
              >
                <Button type="default" disabled={isPaused} block>
                  AI托管中
                </Button>
              </Popconfirm>
            ) : (
              <>
                {sendError && (
                  <Button
                    type="primary"
                    danger
                    onClick={() => {
                      setMessageText(sendError);
                      setSendError(null);
                      // Focus the textarea so user can edit before resending
                      setTimeout(() => textareaRef.current?.focus(), 0);
                    }}
                    block
                    icon={<span>🔄</span>}
                  >
                    重试发送（已恢复文本）
                  </Button>
                )}
                <Button
                  type="primary"
                  disabled={isPaused || (!isNoteMode && !messageText.trim())}
                  loading={loading || aiGenerating || outboundTranslating}
                  onClick={() => {
                    if (isNoteMode) handleSendNote();
                    else handleSendMessage();
                  }}
                  block
                >
                  发送消息
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* F-08: 转发消息 Modal */}
      <Modal
        title="转发消息"
        open={forwardModalOpen}
        onCancel={() => setForwardModalOpen(false)}
        onOk={handleForward}
        confirmLoading={forwarding}
        okText="确认转发"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>目标会话</Typography.Text>
            <AutoComplete
              style={{ width: "100%", marginTop: 4 }}
              placeholder="搜索并选择目标会话..."
              value={forwardTargetConvId}
              onChange={(v) => setForwardTargetConvId(v)}
              options={conversations
                .filter((c) => c.conversation_id !== selectedConversation?.conversation_id)
                .map((c) => ({
                  value: c.conversation_id,
                  label: `${c.customer_id.slice(0, 16)} | ${c.last_message_preview?.slice(0, 20) ?? "无预览"}`,
                }))}
              filterOption={(inputValue, option) =>
                (option?.label as string)?.toLowerCase().includes(inputValue.toLowerCase()) ?? false
              }
            />
          </div>
          <Checkbox
            checked={forwardIncludeCtx}
            onChange={(e) => setForwardIncludeCtx(e.target.checked)}
          >
            附带上下文
          </Checkbox>
        </div>
      </Modal>
    </div>
  );
});
