import { type JSX } from "react";
import { Button, message, Popconfirm } from "antd";

// 操作成功提示
export function showSuccess(msg: string): void {
  void message.success(msg);
}

// 操作失败提示
export function showError(msg: string): void {
  void message.error(msg);
}

// 危险操作按钮（自动带 Popconfirm）
export interface DangerButtonProps {
  label: string;
  confirmTitle: string;
  confirmDescription?: string;
  onConfirm: () => Promise<void>;
  disabled?: boolean;
  loading?: boolean;
  type?: "primary" | "default" | "dashed" | "text" | "link";
  danger?: boolean;
}

export function DangerButton({
  label,
  confirmTitle,
  confirmDescription,
  onConfirm,
  disabled,
  loading,
  type = "primary",
  danger = true,
}: DangerButtonProps): JSX.Element {
  return (
    <Popconfirm
      title={confirmTitle}
      description={confirmDescription}
      onConfirm={onConfirm}
      okText="确认"
      cancelText="取消"
      okButtonProps={{ danger: true }}
    >
      <Button type={type} danger={danger} disabled={disabled} loading={loading}>
        {label}
      </Button>
    </Popconfirm>
  );
}
