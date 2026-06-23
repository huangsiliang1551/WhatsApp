import type { ReactNode } from "react";

import { Empty, Skeleton, Spin } from "antd";

// Full page loading spinner
export function PageLoading({ tip }: { tip?: string }): React.JSX.Element {
  return (
    <div
      style={{
        alignItems: "center",
        display: "flex",
        justifyContent: "center",
        minHeight: "60vh",
      }}
    >
      <Spin tip={tip ?? "加载中..."} />
    </div>
  );
}

// Table row skeleton loading
export function TableLoading({ rows }: { rows?: number }): React.JSX.Element {
  const count = rows ?? 5;
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 8,
        padding: 24,
      }}
    >
      {Array.from({ length: count }, (_, i) => (
        <Skeleton active key={i} paragraph={{ rows: 3 }} />
      ))}
    </div>
  );
}

// Empty state with custom message
interface EmptyStateProps {
  message?: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState(props: EmptyStateProps): React.JSX.Element {
  const { action, description, message } = props;
  return (
    <div style={{ padding: 48, textAlign: "center" }}>
      <Empty description={description ?? message ?? "暂无数据"} />
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}
