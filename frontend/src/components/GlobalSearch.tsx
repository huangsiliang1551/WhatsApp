import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";

import { Input, List, Modal, Space, Tag, Typography } from "antd";
import type { InputRef } from "antd";

import { api } from "../services/api";

const { Text } = Typography;

// ─── Types ───────────────────────────────────────────────────────

export interface SearchResult {
  type: "conversation" | "customer" | "template" | "ticket";
  id: string;
  title: string;
  description?: string;
  url: string;
}

interface GlobalSearchProps {
  onNavigate: (url: string) => void;
}

interface SearchResponse {
  results: SearchResult[];
}

// ─── Constants ───────────────────────────────────────────────────

const GROUP_LABELS: Record<SearchResult["type"], string> = {
  conversation: "会话",
  customer: "客户",
  template: "模板",
  ticket: "工单",
};

const GROUP_COLORS: Record<SearchResult["type"], string> = {
  conversation: "blue",
  customer: "green",
  template: "purple",
  ticket: "orange",
};

const STORAGE_KEY = "global-search-recents";
const MAX_RECENTS = 10;
const DEBOUNCE_MS = 300;

// ─── Mock fallback data ──────────────────────────────────────────

const MOCK_ROUTES: Record<string, { title: string; description: string }> = {
  "/conversations": { title: "会话工作台", description: "处理 AI 托管、人工接管和多账号会话" },
  "/meta/accounts": { title: "Meta 账户管理", description: "管理 WABA、号码、Webhook 和 Embedded Signup" },
  "/templates": { title: "模板消息中心", description: "管理模板草稿、审核状态、发送日志和统计" },
  "/analytics/whatsapp": { title: "WhatsApp 统计", description: "查看消息量、计费分解和趋势分析" },
  "/assets/media": { title: "媒体库", description: "查看模板媒体资产与引用情况" },
  "/assets/tags": { title: "标签管理", description: "维护用户和会话标签" },
  "/assets/audience-rules": { title: "受众规则", description: "管理细分规则与触达条件" },
  "/ecommerce": { title: "商城数据", description: "查看最小订单与物流接口" },
  "/collaboration/tasks": { title: "任务中心", description: "查看任务模板、实例和状态" },
  "/collaboration/reviews": { title: "审核队列", description: "查看待审核和驳回事项" },
  "/collaboration/tickets": { title: "工单中心", description: "查看转人工、异常和跟进工单" },
  "/collaboration/members": { title: "坐席成员", description: "查看客服成员、状态和负载" },
  "/collaboration/assignments": { title: "会话分配", description: "查看分配队列、接管建议和处理状态" },
  "/collaboration/automation": { title: "自动化规则", description: "管理自动化触发规则和执行策略" },
  "/collaboration/customers": { title: "客户视图", description: "查看客户档案、标签和关联会话" },
  "/monitoring": { title: "监控与健康", description: "查看健康检查、队列运行态和基础指标" },
  "/system/integrations": { title: "集成管理", description: "查看 Meta、Webhook、Signup 和运行配置" },
  "/system/api-webhooks": { title: "API / Webhook", description: "查看回调订阅、签名失败、回放积压和策略" },
  "/audit": { title: "审计日志", description: "查看账户、模板、接管与回放等审计记录" },
  "/system/logs": { title: "系统日志", description: "查看审计、状态回放与队列失败日志" },
  "/evidence": { title: "证据中心", description: "查看证据条目和关联详情" },
};

const MOCK_ENTRIES: SearchResult[] = Object.entries(MOCK_ROUTES).map(([url, info], idx) => {
  const match = url.match(/^\/([^/]+)/);
  const segment = match ? match[1] : "";
  let type: SearchResult["type"] = "conversation";
  if (segment === "templates") type = "template";
  else if (segment === "collaboration") {
    const sub = url.replace("/collaboration/", "");
    if (sub === "tickets") type = "ticket";
    else if (sub === "customers") type = "customer";
  } else if (segment === "assets" && url.includes("media")) type = "ticket";
  return { type, id: `mock-${idx}`, title: info.title, description: info.description, url };
});

// ─── localStorage helpers ────────────────────────────────────────

function loadRecents(): SearchResult[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed as SearchResult[];
  } catch {
    return [];
  }
}

function saveRecents(recents: SearchResult[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(recents.slice(0, MAX_RECENTS)));
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

function addRecent(recents: SearchResult[], selected: SearchResult): SearchResult[] {
  const filtered = recents.filter((r) => r.id !== selected.id || r.type !== selected.type);
  return [selected, ...filtered].slice(0, MAX_RECENTS);
}

// ─── Mock search fallback ────────────────────────────────────────

function fallbackSearch(query: string): SearchResult[] {
  const lower = query.toLowerCase();
  return MOCK_ENTRIES.filter(
    (entry) =>
      entry.title.toLowerCase().includes(lower) ||
      (entry.description ?? "").toLowerCase().includes(lower)
  );
}

// ─── Component ───────────────────────────────────────────────────

export function GlobalSearch({ onNavigate }: GlobalSearchProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [recents, setRecents] = useState<SearchResult[]>(loadRecents);
  const [searched, setSearched] = useState(false);

  const inputRef = useRef<InputRef>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  // ── Group results ──

  const grouped = useMemo(() => {
    const groups: Record<SearchResult["type"], SearchResult[]> = {
      conversation: [],
      customer: [],
      template: [],
      ticket: [],
    };
    for (const r of results) {
      groups[r.type]?.push(r);
    }
    const entries = Object.entries(groups) as [SearchResult["type"], SearchResult[]][];
    return entries.filter(([, items]) => items.length > 0);
  }, [results]);

  // ── Flattened index for keyboard nav ──

  const flatList = useMemo(() => {
    return grouped.flatMap(([, items]) => items);
  }, [grouped]);

  const displayResults = query.trim() === "" && !searched;

  // ── Perform search ──

  const doSearch = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) {
        setResults([]);
        setSearched(false);
        setActiveIndex(-1);
        return;
      }

      setLoading(true);
      setSearched(true);

      // Cancel previous request
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      try {
        const response = await api.get<SearchResponse>("/api/search", {
          params: { q: trimmed, type: "all" },
          signal: controller.signal,
        });
        setResults(response.data.results);
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        // Fallback to mock search
        setResults(fallbackSearch(trimmed));
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    },
    []
  );

  // ── Debounce ──

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    debounceRef.current = setTimeout(() => {
      void doSearch(query);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, doSearch]);

  // ── Open / close ──

  const openSearch = useCallback(() => {
    setOpen(true);
    setQuery("");
    setResults([]);
    setSearched(false);
    setActiveIndex(-1);
    setRecents(loadRecents());
    // Focus input after modal renders
    setTimeout(() => inputRef.current?.focus(), 50);
  }, []);

  const closeSearch = useCallback(() => {
    setOpen(false);
    setQuery("");
    setResults([]);
    setSearched(false);
    setActiveIndex(-1);
    controllerRef.current?.abort();
  }, []);

  // ── Navigate ──

  const navigateTo = useCallback(
    (result: SearchResult) => {
      const updated = addRecent(loadRecents(), result);
      setRecents(updated);
      saveRecents(updated);
      closeSearch();
      onNavigate(result.url);
    },
    [closeSearch, onNavigate]
  );

  // ── Keyboard shortcut ──

  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      const isMeta = e.metaKey || e.ctrlKey;
      if (isMeta && e.key === "k") {
        e.preventDefault();
        e.stopPropagation();
        openSearch();
      }
      // Escape is handled by antd Modal's onCancel
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [openSearch]);

  // ── Modal keyboard nav ──

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>): void => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((prev) => (prev < flatList.length - 1 ? prev + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : flatList.length - 1));
      } else if (e.key === "Enter" && activeIndex >= 0 && activeIndex < flatList.length) {
        e.preventDefault();
        navigateTo(flatList[activeIndex]);
      }
    },
    [flatList, activeIndex, navigateTo]
  );

  // ── Modal props ──

  const modalWidth = 560;
  const sectionHeaderHeight = 32;
  const itemHeight = 52;
  const maxVisibleItems = 8;
  const bodyHeight = Math.min(grouped.length * sectionHeaderHeight + flatList.length * itemHeight + 16, maxVisibleItems * itemHeight + grouped.length * sectionHeaderHeight + 16);

  return (
    <>
      {/* Hidden trigger — user activates via keyboard */}
      <Modal
        afterOpenChange={(visible) => {
          if (visible) {
            setTimeout(() => inputRef.current?.focus(), 50);
          }
        }}
        centered
        closable={false}
        footer={null}
        maskClosable
        onCancel={closeSearch}
        open={open}
        styles={{ body: { padding: "20px 24px 12px" } }}
        style={{ top: 80 }}
        title={null}
        width={modalWidth}
      >
        <div onKeyDown={handleKeyDown}>
          <Input.Search
            autoFocus
            enterButton={null}
            loading={loading}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(-1);
            }}
            onSearch={(value) => {
              if (value.trim()) {
                void doSearch(value);
              }
            }}
            placeholder="输入关键词开始搜索"
            ref={inputRef}
            size="large"
            value={query}
          />

          <div
            style={{
              marginTop: 12,
              maxHeight: Math.min(bodyHeight, 480),
              overflowY: "auto",
            }}
          >
            {query.trim() === "" && !searched ? (
              <div style={{ padding: "24px 0", textAlign: "center" }}>
                <Text type="secondary">输入关键词开始搜索</Text>
              </div>
            ) : results.length === 0 && !loading ? (
              <div style={{ padding: "24px 0", textAlign: "center" }}>
                <Text type="secondary">未找到相关结果</Text>
              </div>
            ) : (
              grouped.map(([type, items]) => (
                <div key={type}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 0 4px",
                    }}
                  >
                    <Tag color={GROUP_COLORS[type]}>{GROUP_LABELS[type]}</Tag>
                    <Text style={{ fontSize: 12 }} type="secondary">
                      {items.length} 项
                    </Text>
                  </div>
                  <List
                    dataSource={items}
                    renderItem={(item, itemIdx) => {
                      const globalIdx = flatList.indexOf(item);
                      const isActive = globalIdx === activeIndex;
                      return (
                        <List.Item
                          key={`${item.type}:${item.id}`}
                          onClick={() => navigateTo(item)}
                          onMouseEnter={() => setActiveIndex(globalIdx)}
                          style={{
                            borderRadius: 6,
                            cursor: "pointer",
                            padding: "8px 12px",
                            transition: "background 0.15s",
                            ...(isActive
                              ? { background: "var(--ant-color-primary-bg, #e6f4ff)" }
                              : {}),
                          }}
                        >
                          <List.Item.Meta
                            description={
                              item.description ? (
                                <Text
                                  ellipsis
                                  style={{ fontSize: 12, maxWidth: 440 }}
                                  type="secondary"
                                >
                                  {item.description}
                                </Text>
                              ) : null
                            }
                            style={{ margin: 0 }}
                            title={
                              <Space align="center" size={4}>
                                <Tag
                                  color={GROUP_COLORS[item.type]}
                                  style={{
                                    borderRadius: 4,
                                    fontSize: 11,
                                    lineHeight: "18px",
                                    marginRight: 6,
                                    padding: "0 4px",
                                  }}
                                >
                                  {GROUP_LABELS[item.type]}
                                </Tag>
                                <Text
                                  strong={isActive}
                                  style={{ fontSize: 14 }}
                                >
                                  {item.title}
                                </Text>
                              </Space>
                            }
                          />
                        </List.Item>
                      );
                    }}
                    rowKey={(item) => `${item.type}:${item.id}`}
                    split={false}
                  />
                </div>
              ))
            )}
          </div>

          {/* Recent searches */}
          {query.trim() === "" && !searched && recents.length > 0 && (
            <div style={{ borderTop: "1px solid var(--ant-color-border-secondary, #f0f0f0)", marginTop: 8, paddingTop: 8 }}>
              <Text style={{ fontSize: 12, padding: "0 4px" }} type="secondary">
                最近搜索
              </Text>
              <Space size={[4, 4]} style={{ marginTop: 4 }} wrap>
                {recents.map((recent) => (
                  <Tag
                    key={`${recent.type}:${recent.id}`}
                    color={GROUP_COLORS[recent.type]}
                    onClick={() => navigateTo(recent)}
                    style={{ cursor: "pointer" }}
                  >
                    {recent.title}
                  </Tag>
                ))}
              </Space>
            </div>
          )}

          {/* Footer hint */}
          <div style={{ borderTop: "1px solid var(--ant-color-border-secondary, #f0f0f0)", marginTop: 8, padding: "6px 4px 0" }}>
            <Space size={16}>
              <Text style={{ fontSize: 11 }} type="secondary">
                ↑↓ 导航
              </Text>
              <Text style={{ fontSize: 11 }} type="secondary">
                Enter 选择
              </Text>
              <Text style={{ fontSize: 11 }} type="secondary">
                Esc 关闭
              </Text>
            </Space>
          </div>
        </div>
      </Modal>
    </>
  );
}

export default GlobalSearch;
