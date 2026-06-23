import { type JSX } from "react";
import { Button, Space, Typography } from "antd";

export interface PageShellProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  stats?: React.ReactNode;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export function PageShell({
  title,
  subtitle,
  actions,
  stats,
  children,
  style,
}: PageShellProps): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", ...style }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px 0",
          flexShrink: 0,
        }}
      >
        <div>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {title}
          </Typography.Title>
          {subtitle && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {subtitle}
            </Typography.Text>
          )}
        </div>
        {actions && <Space>{actions}</Space>}
      </div>
      {stats && (
        <div style={{ padding: "8px 16px 0", flexShrink: 0 }}>{stats}</div>
      )}
      <div style={{ flex: 1, minHeight: 0, padding: 12 }}>{children}</div>
    </div>
  );
}

export interface EmptyGuideProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actions?: {
    label: string;
    onClick: () => void;
    type?: "primary" | "default";
  }[];
}

export function EmptyGuide({
  icon,
  title,
  description,
  actions,
}: EmptyGuideProps): JSX.Element {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 48,
        color: "#999",
        userSelect: "none",
      }}
    >
      {icon && <div style={{ fontSize: 48, marginBottom: 16 }}>{icon}</div>}
      <div style={{ fontSize: 14, marginBottom: 8 }}>{title}</div>
      {description && (
        <div style={{ fontSize: 12, color: "#bbb", marginBottom: 16, textAlign: "center" }}>
          {description}
        </div>
      )}
      {actions && actions.length > 0 && (
        <Space>
          {actions.map((a, i) => (
            <Button key={i} type={a.type ?? "primary"} onClick={a.onClick}>
              {a.label}
            </Button>
          ))}
        </Space>
      )}
    </div>
  );
}
