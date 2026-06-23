import { type JSX } from "react";



import { Space, Tag, Timeline, Typography } from "antd";



import type { ConversationTimelineItem, TemplateSendLogView, CustomerConversationBrief } from "../../services/api";



export interface HistoryTabProps {

  timeline: ConversationTimelineItem[];

  templateLogs: TemplateSendLogView[];

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



export function HistoryTab({ timeline, templateLogs }: HistoryTabProps): JSX.Element {

  const handoverItems = timeline.filter((t) => t.item_type === "handover").slice(0, 10);



  return (

    <div style={{ padding: "0 4px" }}>

      {/* 接管时间线 */}

      {handoverItems.length > 0 && (

        <div style={{ marginBottom: 12 }}>

          <Typography.Text style={{ fontSize: 12, fontWeight: 500 }}>接管记录</Typography.Text>

          <Timeline

            style={{ marginTop: 8 }}

            items={handoverItems.map((item) => ({

              children: (

                <Space direction="vertical" size={2}>

                  <Space size={4}>

                    <Tag color="warning" style={{ fontSize: 10 }}>接管</Tag>

                    {item.actor_id && (

                      <Typography.Text style={{ fontSize: 11 }} type="secondary">

                        {item.actor_id}

                      </Typography.Text>

                    )}

                  </Space>

                  <Typography.Text style={{ fontSize: 12 }}>{item.summary}</Typography.Text>

                  <Typography.Text style={{ fontSize: 11 }} type="secondary">

                    {fmt(item.created_at)}

                  </Typography.Text>

                </Space>

              ),

            }))}

          />

        </div>

      )}



      {/* 全量时间线 */}

      {timeline.length > 0 && (

        <div style={{ marginBottom: 12 }}>

          <Typography.Text style={{ fontSize: 12, fontWeight: 500 }}>

            全量时间线(最近 {Math.min(timeline.length, 20)} 条)

          </Typography.Text>

          <Timeline

            style={{ marginTop: 8 }}

            items={timeline.slice(0, 20).map((item) => ({

              children: (

                <Space direction="vertical" size={2}>

                  <Typography.Text style={{ fontSize: 12, fontWeight: 500 }}>

                    {formatTimelineTitle(item)}

                  </Typography.Text>

                  <Typography.Text style={{ fontSize: 12 }}>{item.summary}</Typography.Text>

                  <Typography.Text style={{ fontSize: 11 }} type="secondary">

                    {fmt(item.created_at)}

                  </Typography.Text>

                </Space>

              ),

            }))}

          />

        </div>

      )}



      {/* 模板发送日志 */}

      {templateLogs.length > 0 && (

        <div>

          <Typography.Text style={{ fontSize: 12, fontWeight: 500 }}>

            模板发送记录（最近 {Math.min(templateLogs.length, 10)} 条）

          </Typography.Text>

          <div style={{ marginTop: 8 }}>

            {templateLogs.slice(0, 10).map((log) => (

              <div

                key={log.id}

                style={{

                  fontSize: 12,

                  padding: "6px 8px",

                  borderBottom: "1px solid #f0f0f0",

                }}

              >

                <Space size={4}>

                  <Tag color={log.status === "SENT" ? "success" : log.status === "FAILED" ? "error" : "default"} style={{ fontSize: 10 }}>

                    {log.status}

                  </Tag>

                  <Typography.Text>{log.template_name}</Typography.Text>

                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>

                    {fmt(log.created_at)}

                  </Typography.Text>

                </Space>

              </div>

            ))}

          </div>

        </div>

      )}



      {handoverItems.length === 0 && timeline.length === 0 && templateLogs.length === 0 && (

        <Typography.Text type="secondary" style={{ fontSize: 12 }}>暂无操作记录</Typography.Text>

      )}

    </div>

  );

}

/** F-05: 客户历史会话列表组件，供 Drawer 使用 */
export interface CustomerHistoryListProps {
  items: CustomerConversationBrief[];
  loading?: boolean;
  onSelect?: (item: CustomerConversationBrief) => void;
}

function fmtFull(v: string): string {
  return new Date(v).toLocaleString("zh-CN");
}

export function CustomerHistoryList({ items, loading, onSelect }: CustomerHistoryListProps): JSX.Element {
  if (loading) {
    return <div style={{ textAlign: "center", padding: 24, color: "#999" }}>加载中...</div>;
  }
  if (items.length === 0) {
    return <div style={{ textAlign: "center", padding: 24, color: "#999" }}>暂无历史会话</div>;
  }
  return (
    <Space direction="vertical" size={8} style={{ width: "100%" }}>
      {items.map((h) => (
        <div
          key={h.conversation_id}
          onClick={() => onSelect?.(h)}
          style={{
            padding: "10px 12px",
            borderRadius: 6,
            border: "1px solid #f0f0f0",
            cursor: onSelect ? "pointer" : "default",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "#f5f5f5"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <Typography.Text style={{ fontSize: 12 }}>
              {h.last_message_at ? fmtFull(h.last_message_at) : "未知日期"}
            </Typography.Text>
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
          <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
            {h.last_message_preview ?? "暂无消息预览"}
          </Typography.Text>
        </div>
      ))}
    </Space>
  );
}

