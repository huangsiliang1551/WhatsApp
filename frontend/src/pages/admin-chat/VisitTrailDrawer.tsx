import { type JSX, useEffect, useRef, useState, useCallback } from "react";
import { Drawer, Spin, Tag, Typography } from "antd";
import { listConversationTimeline, listTemplateSendLogs, type ConversationTimelineItem, type TemplateSendLogView } from "../../services/api";

const { Text } = Typography;

export interface VisitTrailDrawerProps {
  open: boolean;
  accountId: string | null;
  conversationId: string | null;
  onClose: () => void;
}

function fmt(v: string): string {
  return new Date(v).toLocaleString("zh-CN");
}

function formatTimelineTitle(item: ConversationTimelineItem): string {
  if (item.item_type === "handover") return "接管事件";
  if (item.item_type === "audit") return "审计事件";
  if (item.item_type === "message_event") return "消息事件";
  return item.label || item.item_type;
}

export function VisitTrailDrawer({ open, accountId, conversationId, onClose }: VisitTrailDrawerProps): JSX.Element {
  const [timeline, setTimeline] = useState<ConversationTimelineItem[]>([]);
  const [tmplLogs, setTmplLogs] = useState<TemplateSendLogView[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !accountId || !conversationId) return;
    setLoading(true);
    Promise.all([
      listConversationTimeline(accountId, conversationId, 30),
      listTemplateSendLogs({ account_id: accountId, external_conversation_id: conversationId, limit: 20 }).catch(() => [] as TemplateSendLogView[]),
    ])
      .then(([tl, logs]) => {
        setTimeline(tl);
        setTmplLogs(logs);
      })
      .catch(() => { setTimeline([]); setTmplLogs([]); })
      .finally(() => setLoading(false));
  }, [open, accountId, conversationId]);

  // ⑥: 瀑布流翻页
  const PAGE_SIZE = 50;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) setVisibleCount(PAGE_SIZE);
  }, [open]);

  useEffect(() => {
    const el = loadMoreRef.current;
    if (!el || visibleCount >= timeline.length) return;
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) setVisibleCount((p) => Math.min(p + PAGE_SIZE, timeline.length));
    }, { rootMargin: "100px" });
    obs.observe(el);
    return () => obs.disconnect();
  }, [visibleCount, timeline.length]);

  const visibleTimeline = timeline.slice(0, visibleCount);

  return (
    <Drawer
      title="访问轨迹"
      open={open}
      onClose={onClose}
      width={420}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
      ) : (
        <div style={{ maxHeight: "calc(100vh - 120px)", overflowY: "auto" }}>
          {/* ⑥: 瀑布流时间线 — 防几千条卡顿 */}
          {visibleTimeline.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ fontSize: 13 }}>全部时间线（{timeline.length} 条，已加载 {visibleCount} 条）</Text>
              <div style={{ marginTop: 8 }}>
                {visibleTimeline.map((item, idx) => (
                  <div
                    key={item.id ?? idx}
                    style={{
                      display: "flex", gap: 10, padding: "8px 0",
                      borderBottom: "1px solid #f5f5f5",
                      fontSize: 12,
                    }}
                  >
                    {/* 时间线竖线 + 圆点 */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 16 }}>
                      <span style={{
                        width: 8, height: 8, borderRadius: "50%", flexShrink: 0, marginTop: 3,
                        backgroundColor: item.item_type === "handover" ? "#fa8c16" : item.item_type === "audit" ? "#ff4d4f" : "#1677ff",
                      }} />
                      {idx < visibleTimeline.length - 1 && (
                        <div style={{ width: 1, flex: 1, minHeight: 8, background: "#e8e8e8", marginTop: 2 }} />
                      )}
                    </div>
                    {/* 内容 */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 2 }}>
                        <Tag
                          color={item.item_type === "handover" ? "warning" : item.item_type === "audit" ? "error" : "processing"}
                          style={{ fontSize: 10, margin: 0, lineHeight: "16px" }}
                        >
                          {formatTimelineTitle(item)}
                        </Tag>
                        {item.actor_id && (
                          <Text type="secondary" style={{ fontSize: 10 }}>{item.actor_id}</Text>
                        )}
                        <Text type="secondary" style={{ fontSize: 10, marginLeft: "auto" }}>{fmt(item.created_at)}</Text>
                      </div>
                      <Text style={{ fontSize: 12 }}>{item.summary}</Text>
                    </div>
                  </div>
                ))}
              </div>
              {/* 加载更多触发器 */}
              {visibleCount < timeline.length && (
                <div ref={loadMoreRef} style={{ textAlign: "center", padding: 12, color: "#999", fontSize: 12 }}>
                  滚动加载更多…
                </div>
              )}
            </div>
          )}

          {/* 模板发送记录 */}
          {tmplLogs.length > 0 && (
            <div>
              <Text strong style={{ fontSize: 13 }}>模板发送记录（最近 {Math.min(tmplLogs.length, 20)} 条）</Text>
              <div style={{ marginTop: 8 }}>
                {tmplLogs.slice(0, 20).map((log) => (
                  <div
                    key={log.id}
                    style={{ fontSize: 12, padding: "6px 8px", borderBottom: "1px solid #f0f0f0" }}
                  >
                    <Tag
                      color={log.status === "SENT" ? "success" : log.status === "FAILED" ? "error" : "default"}
                      style={{ fontSize: 10 }}
                    >
                      {log.status}
                    </Tag>
                    <Text>{log.template_name}</Text>
                    <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>{fmt(log.created_at)}</Text>
                  </div>
                ))}
              </div>
            </div>
          )}

          {timeline.length === 0 && tmplLogs.length === 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>暂无访问记录</Text>
          )}
        </div>
      )}
    </Drawer>
  );
}
