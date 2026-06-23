import { type JSX } from "react";

import { Badge, Tabs, Typography } from "antd";

export interface OpenTab {
  key: string;
  conversationId: string;
  accountId: string;
  label: string;
}

export interface ChatTabsProps {
  tabs: OpenTab[];
  activeKey: string;
  onSelect: (key: string) => void;
  onClose: (key: string) => void;
  unreadCounts: Record<string, number>;
}

export function ChatTabs({
  tabs,
  activeKey,
  onSelect,
  onClose,
  unreadCounts,
}: ChatTabsProps): JSX.Element {
  if (tabs.length === 0) {
    return (
      <div style={{ flexShrink: 0, borderTop: "1px solid #f0f0f0", padding: "4px 12px", textAlign: "right" }}>
        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
          Ctrl+1~9 切换 · Ctrl+W 关闭
        </Typography.Text>
      </div>
    );
  }

  return (
    <div style={{ flexShrink: 0, borderTop: "1px solid #f0f0f0" }}>
      <Tabs
        type="editable-card"
        hideAdd
        size="small"
        activeKey={activeKey}
        onChange={onSelect}
        onEdit={(key) => onClose(key as string)}
        tabBarExtraContent={
          <Typography.Text type="secondary" style={{ fontSize: 11, paddingRight: 8 }}>
            Ctrl+1~9 切换 · Ctrl+W 关闭
          </Typography.Text>
        }
        items={tabs.map((tab, i) => ({
          key: tab.key,
          label: (
            <Badge count={unreadCounts[tab.key] ?? 0} size="small" offset={[4, -4]}>
              <span style={{ fontSize: 12 }}>
                #{i + 1} {tab.label}
              </span>
            </Badge>
          ),
          closable: true,
        }))}
        style={{ marginBottom: 0 }}
      />
    </div>
  );
}
