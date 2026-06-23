import { type JSX } from "react";
import { Button, Space, Typography } from "antd";
import { ClearOutlined } from "@ant-design/icons";

export interface BatchAction {
  key: string;
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  danger?: boolean;
  confirmTitle?: string;
  show?: boolean;
  loading?: boolean;
}

export interface BatchActionBarProps {
  selectedCount: number;
  selectedKeys: string[];
  onClear: () => void;
  actions: BatchAction[];
  /** Original ChatPage-specific props kept for backward compatibility */
  onBatchHandover?: () => void;
  onBatchRestoreAI?: () => void;
  onBatchClose?: () => void;
  onBatchAssign?: () => void;
}

const barStyle: React.CSSProperties = {
  position: "fixed",
  bottom: 0,
  left: 0,
  right: 0,
  zIndex: 1000,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 24px",
  background: "#1677ff",
  boxShadow: "0 -2px 8px rgba(0,0,0,0.15)",
};

export function BatchActionBar(props: BatchActionBarProps): JSX.Element | null {
  const { selectedCount, selectedKeys, onClear, actions } = props;

  if (selectedCount === 0) {
    return null;
  }

  return (
    <div style={barStyle}>
      <Typography.Text style={{ color: "#fff", fontSize: 13 }}>
        已选 {selectedCount} 项
      </Typography.Text>
      <Space size={8}>
        {actions
          .filter((a) => a.show !== false)
          .map((action) => (
            <Button
              key={action.key}
              icon={action.icon}
              type="primary"
              ghost
              size="small"
              onClick={action.onClick}
              danger={action.danger}
              loading={action.loading}
            >
              {action.label}
            </Button>
          ))}
        <Button
          icon={<ClearOutlined />}
          type="primary"
          ghost
          size="small"
          onClick={onClear}
        >
          取消选择
        </Button>
      </Space>
    </div>
  );
}

export default BatchActionBar;
