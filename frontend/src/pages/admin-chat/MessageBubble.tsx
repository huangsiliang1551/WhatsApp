import { type JSX } from "react";
import { Typography } from "antd";
import {
  TranslationOutlined,
  LoadingOutlined,
  ForwardOutlined,
} from "@ant-design/icons";

import type { ConversationMessage } from "../../services/api";
import {
  getMessagePrimaryText,
  getMessageTranslationAssistText,
} from "../../services/api";

/** 从payload中提取媒体URL */
function getMediaUrl(msg: ConversationMessage): string | null {
  const p = msg.payload as Record<string, unknown> | null;
  if (!p) return null;
  return (p.media_url as string) ?? (p.url as string) ?? (p.media_asset_url as string) ?? null;
}

/** 媒体消息预览组件 */
function MediaPreview({ msg }: { msg: ConversationMessage }): JSX.Element {
  const mtype = msg.message_type;
  const mediaUrl = getMediaUrl(msg);
  const caption = getMessagePrimaryText(msg) ?? "";

  if (mtype === "image") {
    if (mediaUrl) {
      return (
        <div style={{ maxWidth: 260 }}>
          <img
            src={mediaUrl}
            alt={caption || "图片"}
            style={{
              width: "100%",
              maxHeight: 240,
              objectFit: "cover",
              borderRadius: 8,
              cursor: "pointer",
            }}
            onClick={() => window.open(mediaUrl, "_blank")}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
          {caption && (
            <div style={{ fontSize: 12, color: "#999", marginTop: 4, wordBreak: "break-word" }}>
              {caption}
            </div>
          )}
        </div>
      );
    }
    return (
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px", background: "#f0f7ff", borderRadius: 8,
          cursor: "default",
        }}
      >
        <span style={{ fontSize: 24 }}>🖼️</span>
        <div>
          <div style={{ fontSize: 13, color: "#1677ff", fontWeight: 500 }}>图片消息</div>
          {caption && <div style={{ fontSize: 12, color: "#999" }}>{caption}</div>}
        </div>
      </div>
    );
  }

  if (mtype === "video") {
    if (mediaUrl) {
      return (
        <div style={{ maxWidth: 260 }}>
          <video
            src={mediaUrl}
            controls
            style={{ width: "100%", maxHeight: 240, borderRadius: 8 }}
            preload="metadata"
          />
          {caption && (
            <div style={{ fontSize: 12, color: "#999", marginTop: 4, wordBreak: "break-word" }}>
              {caption}
            </div>
          )}
        </div>
      );
    }
    return (
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px", background: "#fff0f6", borderRadius: 8,
          cursor: "default",
        }}
      >
        <span style={{ fontSize: 24 }}>🎬</span>
        <div>
          <div style={{ fontSize: 13, color: "#eb2f96", fontWeight: 500 }}>视频消息</div>
          {caption && <div style={{ fontSize: 12, color: "#999" }}>{caption}</div>}
        </div>
      </div>
    );
  }

  if (mtype === "audio") {
    if (mediaUrl) {
      return (
        <div style={{ minWidth: 200, maxWidth: 300 }}>
          <audio src={mediaUrl} controls style={{ width: "100%" }} preload="metadata" />
          {caption && (
            <div style={{ fontSize: 12, color: "#999", marginTop: 4, wordBreak: "break-word" }}>
              {caption}
            </div>
          )}
        </div>
      );
    }
    return (
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px", background: "#f6ffed", borderRadius: 8,
          cursor: "default",
        }}
      >
        <span style={{ fontSize: 24 }}>🎵</span>
        <div>
          <div style={{ fontSize: 13, color: "#52c41a", fontWeight: 500 }}>语音消息</div>
          {caption && <div style={{ fontSize: 12, color: "#999" }}>{caption}</div>}
        </div>
      </div>
    );
  }

  if (mtype === "document") {
    const fileName = caption || "文档";
    if (mediaUrl) {
      return (
        <a
          href={mediaUrl}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "8px 12px", background: "#f5f5f5", borderRadius: 8,
            textDecoration: "none", color: "inherit",
          }}
        >
          <span style={{ fontSize: 22 }}>📄</span>
          <div style={{ fontSize: 13, color: "#1677ff" }}>{fileName}</div>
        </a>
      );
    }
    return (
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px", background: "#f5f5f5", borderRadius: 8,
          cursor: "default",
        }}
      >
        <span style={{ fontSize: 22 }}>📄</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>文件消息</div>
          <div style={{ fontSize: 12, color: "#999" }}>{fileName}</div>
        </div>
      </div>
    );
  }

  // 其他非文本类型
  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "8px 12px", background: "#fafafa", borderRadius: 8,
        cursor: "default",
      }}
    >
      <span style={{ fontSize: 20 }}>📎</span>
      <div style={{ fontSize: 13, color: "#666" }}>[{mtype.toUpperCase()}] 媒体消息</div>
    </div>
  );
}

/** 消息状态回执图标 */
export function DeliveryStatusIcon({ status, ts }: { status?: string; ts?: string }): JSX.Element | null {
  if (!status) return null;
  const isFailed = status === "failed";
  const isRead = status === "read";
  const isDelivered = status === "delivered";

  const color = isFailed ? "#ff4d4f" : isRead ? "#1677ff" : "#999";
  const icon = isFailed ? "✕" : isRead ? "✓✓" : isDelivered ? "✓✓" : "✓";
  const label = isFailed ? "发送失败" : isRead ? "已读" : isDelivered ? "已送达" : "已发送";

  return (
    <span style={{ color, fontSize: 11, marginLeft: 4, cursor: "default" }}
      title={`${label}${ts ? " " + new Date(ts).toLocaleTimeString("zh-CN") : ""}`}>
      {icon}
    </span>
  );
}

export function formatTime(ts: string): string {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function isInternalNote(msg: ConversationMessage): boolean {
  return msg.message_type === "internal_note";
}

export function isNonTextType(msg: ConversationMessage): boolean {
  return ["image", "audio", "video", "document"].includes(msg.message_type);
}

export interface MessageBubbleProps {
  msg: ConversationMessage;
  currentAgentName: string | null;
  freshTranslations: Record<string, string>;
  translatingIds: Set<string>;
  messageStatusUpdates?: Record<string, string>;
  isHighlight: boolean;
  onTranslate: (msg: ConversationMessage) => void;
  onForward: (msg: ConversationMessage) => void;
}

export function MessageBubble({
  msg,
  currentAgentName,
  freshTranslations,
  translatingIds,
  messageStatusUpdates,
  isHighlight,
  onTranslate,
  onForward,
}: MessageBubbleProps): JSX.Element {
  const isInbound = msg.direction === "inbound";
  const isAi = msg.ai_generated;
  const isSystem = msg.message_type === "system";
  const isNote = isInternalNote(msg);
  const primaryText = getMessagePrimaryText(msg) ?? "";
  const assistText = freshTranslations[msg.message_id || ""] ?? getMessageTranslationAssistText(msg);
  const isTranslating = translatingIds.has(msg.message_id || "");
  const showTranslateBtn =
    !isSystem && !isNote && !assistText &&
    msg.language_code && msg.language_code !== "zh-CN" &&
    primaryText;
  const showIcon = !isSystem && !isNote;

  const bubbleStyle: React.CSSProperties = isSystem
    ? { textAlign: "center", margin: "4px auto", padding: "4px 12px", borderRadius: 8, background: "#fafafa", maxWidth: "75%" }
    : isNote
    ? { maxWidth: "85%", marginLeft: 0, padding: "8px 12px", borderRadius: 8, background: "#fffbe6", borderLeft: "3px solid #fadb14", marginBottom: 4 }
    : { maxWidth: "75%", marginLeft: isInbound ? 0 : "auto", padding: "8px 12px", borderRadius: isInbound ? "0 12px 12px 12px" : "12px 0 12px 12px", background: isInbound ? "#f5f5f5" : isAi ? "#e6f4ff" : "#d4edda", marginBottom: 4 };

  return (
    <div
      data-message-id={msg.message_id}
      style={{
        display: "flex", flexDirection: "column",
        alignItems: isSystem || isNote ? "flex-start" : isInbound ? "flex-start" : "flex-end",
        marginBottom: 4, padding: "4px 16px",
        transition: "background-color 0.3s",
        ...(isHighlight ? { backgroundColor: "#fff3cd", borderRadius: 6, padding: "4px 10px" } : {}),
      }}
    >
      {isNote && (
        <div style={{ fontSize: 10, color: "#fadb14", marginBottom: 2, marginLeft: 4 }}>🔒 内部备注</div>
      )}
      {showIcon && !isInbound && (
        <div style={{ fontSize: 10, color: "#999", marginBottom: 2, marginRight: 8 }}>
          {isAi ? "🤖 AI" : currentAgentName ?? "坐席"}
        </div>
      )}
      <div style={bubbleStyle}>
        {isNonTextType(msg) ? (
          <MediaPreview msg={msg} />
        ) : (
          <>
            {isSystem ? (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>{primaryText}</Typography.Text>
            ) : (
              <>
                <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 13, lineHeight: 1.5, fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans','Helvetica Neue',Arial,sans-serif,'Apple Color Emoji','Segoe UI Emoji'" }}>{primaryText}</div>
                {assistText && (
                  <div style={{ fontSize: 12, color: "#999", fontStyle: "italic", marginTop: 4, borderTop: "1px dashed #ddd", paddingTop: 4 }}>{assistText}</div>
                )}
              </>
            )}
            <div style={{ textAlign: "right", fontSize: 11, color: "#bbb", marginTop: 4, display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 4 }}>
              {showTranslateBtn && (
                isTranslating ? (
                  <span style={{ fontSize: 11, color: "#1677ff", display: "inline-flex", alignItems: "center", gap: 3 }}><LoadingOutlined /> 翻译中…</span>
                ) : (
                  <span title="翻译" onClick={(e) => { e.stopPropagation(); onTranslate(msg); }} style={{ fontSize: 11, color: "#1677ff", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 3, userSelect: "none" }}><TranslationOutlined /> 翻译</span>
                )
              )}
              {!isSystem && !isNote && msg.message_type === "text" && (
                <span title="转发" onClick={(e) => { e.stopPropagation(); onForward(msg); }} style={{ fontSize: 11, color: "#1677ff", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 3, userSelect: "none" }}><ForwardOutlined /> 转发</span>
              )}
              {formatTime(msg.created_at)}
              {!isInbound && !isSystem && !isNote && (
                <DeliveryStatusIcon status={messageStatusUpdates?.[msg.message_id] ?? msg.delivery_status} ts={msg.delivery_status_updated_at} />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
