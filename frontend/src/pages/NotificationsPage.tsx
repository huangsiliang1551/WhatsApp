import { useCallback, useMemo, useState, type JSX } from "react";

import { CheckCircleOutlined, CloseCircleOutlined, InfoCircleOutlined, ReloadOutlined, WarningOutlined } from "@ant-design/icons";
import { Button, Segmented, Select, Space, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";

import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import {
  getCategoryColor,
  getSeverityColor,
  listNotifications,
  markAllNotificationsRead,
  markNotificationsRead,
  type NotificationItem,
} from "../services/notificationApi";

function getSeverityIcon(severity: string): JSX.Element {
  const style = { fontSize: 16 };
  if (severity === "error" || severity === "critical") {
    return <CloseCircleOutlined style={{ ...style, color: getSeverityColor(severity) }} />;
  }
  if (severity === "warning") {
    return <WarningOutlined style={{ ...style, color: getSeverityColor(severity) }} />;
  }
  if (severity === "success") {
    return <CheckCircleOutlined style={{ ...style, color: getSeverityColor(severity) }} />;
  }
  return <InfoCircleOutlined style={{ ...style, color: getSeverityColor(severity) }} />;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export function NotificationsPage(): JSX.Element {
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  const fetcher = useCallback(async () => {
    return listNotifications({
      unread: filter === "unread" ? true : undefined,
      category: categoryFilter ?? undefined,
    });
  }, [categoryFilter, filter]);

  const { data, loading, reload } = usePageData({ fetcher });
  const notifications = data?.items ?? [];
  const totalCount = data?.total ?? 0;

  const filteredNotifications = useMemo(() => {
    let items = notifications;
    if (filter === "unread") {
      items = items.filter((item) => !item.is_read);
    }
    if (categoryFilter) {
      items = items.filter((item) => item.category === categoryFilter);
    }
    return items;
  }, [categoryFilter, filter, notifications]);

  const unreadCount = filteredNotifications.filter((item) => !item.is_read).length;

  const handleMarkRead = useCallback(
    async (id: string) => {
      try {
        const count = await markNotificationsRead([id]);
        if (count > 0) {
          message.success("已标记为已读");
        }
        void reload();
      } catch {
        message.error("操作失败");
      }
    },
    [reload],
  );

  const handleMarkAllRead = useCallback(async () => {
    try {
      const count = await markAllNotificationsRead();
      if (count > 0) {
        message.success(`已批量标记 ${count} 条通知`);
      }
      void reload();
    } catch {
      message.error("操作失败");
    }
  }, [reload]);

  const columns: ColumnsType<NotificationItem> = [
    {
      title: "类型",
      dataIndex: "severity",
      key: "severity",
      width: 120,
      render: (_: string, record: NotificationItem) => (
        <Space size={6}>
          {getSeverityIcon(record.severity)}
          <Tag color={getCategoryColor(record.category)} style={{ margin: 0 }}>
            {record.category.toUpperCase()}
          </Tag>
        </Space>
      ),
    },
    {
      title: "通知内容",
      key: "content",
      render: (_: unknown, record: NotificationItem) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong={!record.is_read} style={{ fontSize: 14 }}>
            {record.title}
          </Typography.Text>
          {record.message ? (
            <Typography.Text style={{ fontSize: 12 }} type="secondary">
              {record.message}
            </Typography.Text>
          ) : null}
        </Space>
      ),
    },
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (value: string) => (
        <Typography.Text style={{ fontSize: 12 }} type="secondary">
          {formatDateTime(value)}
        </Typography.Text>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 120,
      render: (_: unknown, record: NotificationItem) =>
        !record.is_read ? (
          <Button onClick={() => void handleMarkRead(record.id)} size="small" type="link">
            标记已读
          </Button>
        ) : (
          <Typography.Text style={{ fontSize: 12 }} type="secondary">
            已读
          </Typography.Text>
        ),
    },
  ];

  return (
    <PageShell
      actions={
        <div style={{ alignItems: "center", display: "flex", justifyContent: "space-between", width: "100%" }}>
          <Space wrap>
            <Segmented
              onChange={(value) => setFilter(value as "all" | "unread")}
              options={[
                { label: "全部", value: "all" },
                { label: "未读", value: "unread" },
              ]}
              value={filter}
            />
            <Select
              allowClear
              onChange={(value) => setCategoryFilter(value ?? null)}
              options={[
                { label: "AI", value: "ai" },
                { label: "队列", value: "queue" },
                { label: "模板", value: "template" },
                { label: "Meta", value: "meta" },
                { label: "系统", value: "system" },
              ]}
              placeholder="分类筛选"
              style={{ width: 160 }}
              value={categoryFilter}
            />
          </Space>
          <Space wrap>
            <Button onClick={() => void handleMarkAllRead()} size="small">
              全部已读
            </Button>
            <Button icon={<ReloadOutlined />} loading={loading} onClick={() => void reload()} size="small">
              刷新
            </Button>
          </Space>
        </div>
      }
      subtitle={`共 ${totalCount} 条通知，当前筛选下 ${unreadCount} 条未读`}
      title="通知中心"
    >
      <Table<NotificationItem>
        columns={columns}
        dataSource={filteredNotifications}
        loading={loading}
        locale={{ emptyText: "暂无通知" }}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
        rowClassName={(record) => (record.is_read ? "" : "ant-table-row-unread")}
        rowKey="id"
        size="middle"
      />
    </PageShell>
  );
}
