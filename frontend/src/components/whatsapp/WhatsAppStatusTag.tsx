import { Tag, type TagProps } from "antd";
import type { JSX } from "react";
import type { WhatsAppBindingReviewStatus } from "../../types/whatsapp";

const STATUS_META: Record<WhatsAppBindingReviewStatus, { color: TagProps["color"]; label: string }> = {
  pending: { color: "processing", label: "待审核" },
  bound: { color: "success", label: "已绑定" },
  failed: { color: "error", label: "失败" },
};

export function WhatsAppStatusTag({
  status,
}: {
  status: WhatsAppBindingReviewStatus;
}): JSX.Element {
  const meta = STATUS_META[status] ?? { color: "default", label: status };
  return <Tag color={meta.color}>{meta.label}</Tag>;
}
