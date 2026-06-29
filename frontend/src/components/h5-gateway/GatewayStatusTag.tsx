import { Tag, type TagProps } from "antd";
import type { JSX } from "react";
import type { GatewayJobStatus, GatewayNodeStatus } from "../../types/gateway";

type SupportedStatus = GatewayNodeStatus | GatewayJobStatus;

const STATUS_META: Record<string, { color: TagProps["color"]; label: string }> = {
  online: { color: "success", label: "在线" },
  offline: { color: "default", label: "离线" },
  degraded: { color: "warning", label: "降级" },
  pending: { color: "processing", label: "待执行" },
  running: { color: "processing", label: "执行中" },
  succeeded: { color: "success", label: "成功" },
  failed: { color: "error", label: "失败" },
  cancelled: { color: "default", label: "已取消" },
  unknown: { color: "default", label: "未知" },
};

export function GatewayStatusTag({ status }: { status: SupportedStatus }): JSX.Element {
  const meta = STATUS_META[status] ?? STATUS_META.unknown;
  return <Tag color={meta.color}>{meta.label}</Tag>;
}
