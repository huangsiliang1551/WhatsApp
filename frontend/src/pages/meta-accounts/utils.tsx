import type { JSX } from "react";

/** Webhook runtime 状态色 */
export function whColor(status: string | null | undefined): string {
  const map: Record<string, string> = {
    healthy: "#52c41a",
    verification_pending: "#faad14",
    signature_failed: "#ff4d4f",
    pending: "#d9d9d9",
    payload_invalid: "#ff4d4f",
    unavailable: "#999",
  };
  return map[status ?? "pending"] ?? "#d9d9d9";
}

/** Webhook runtime 状态文案 */
export function whLabel(status: string | null | undefined): string {
  const map: Record<string, string> = {
    healthy: "健康",
    verification_pending: "待验证",
    signature_failed: "签名失败",
    pending: "待处理",
    payload_invalid: "无效载荷",
    unavailable: "不可用",
  };
  return map[status ?? "pending"] ?? status ?? "未知";
}

/** Webhook 订阅状态色 */
export function whSubColor(status: string | null | undefined): string {
  const map: Record<string, string> = {
    subscribed: "#52c41a",
    mock_subscribed: "#52c41a",
    remote_subscribed: "#52c41a",
    remote_pending: "#faad14",
    pending: "#d9d9d9",
  };
  return map[status ?? "pending"] ?? "#d9d9d9";
}

/** Webhook 订阅状态文案 */
export function whSubLabel(status: string | null | undefined): string {
  const map: Record<string, string> = {
    subscribed: "已订阅",
    mock_subscribed: "模拟订阅",
    remote_subscribed: "远程订阅",
    remote_pending: "远程待处理",
    pending: "待处理",
  };
  return map[status ?? "pending"] ?? status ?? "未知";
}

/** 号码质量评分色 */
export function qualityColor(rating: string | null | undefined): string {
  if (rating === "GREEN") return "#52c41a";
  if (rating === "YELLOW") return "#faad14";
  if (rating === "RED") return "#ff4d4f";
  return "#999";
}

/** Signup completion_stage 文案 */
export function stageLabel(stage: string | null | undefined): string {
  const map: Record<string, string> = {
    pending_callback: "等待回调",
    callback_recorded: "已记录回调",
    remote_confirmed: "已远程确认",
    local_waba_linked: "已关联本地WABA",
    webhook_verification_pending: "待Webhook验证",
    failed: "失败",
  };
  return map[stage ?? ""] ?? stage ?? "未知";
}

/** Signup event_source 文案 */
export function sourceLabel(source: string | null | undefined): string {
  const map: Record<string, string> = {
    operator: "运营手动",
    provider_callback: "Provider回调",
    system_sync: "系统同步",
  };
  return map[source ?? ""] ?? source ?? "未知";
}

/** 简短时间格式化 */
export function shortTs(ts: string | null | undefined): string {
  if (!ts) return "-";
  const d = new Date(ts);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

/** 就绪指示灯 + 文案 */
export function readyDot(ready: boolean, label: string, trueColor = "#52c41a", falseColor = "#d9d9d9"): JSX.Element {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11 }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: ready ? trueColor : falseColor, flexShrink: 0 }} />
      <span style={{ color: "#666" }}>{ready ? label : "未" + label}</span>
    </span>
  );
}
