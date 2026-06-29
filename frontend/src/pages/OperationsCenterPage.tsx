import { useCallback, type JSX } from "react";
import { Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography } from "antd";

import { MemberIdLink } from "../components/member/MemberIdLink";
import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import {
  getOperationsCenterSnapshot,
  listPlatformUserMemberStatusIndex,
  type PlatformUserMemberStatusSummary,
} from "../services/operations";
import { useAppStore } from "../stores/appStore";
import { withSorter } from "../utils/withSorter";

function renderStatusTag(value: string | null | undefined): JSX.Element {
  if (!value) {
    return <Tag>-</Tag>;
  }
  if (value === "approved" || value === "bound") {
    return <Tag color="success">{value}</Tag>;
  }
  if (value === "rejected" || value === "failed") {
    return <Tag color="error">{value}</Tag>;
  }
  return <Tag color="processing">{value}</Tag>;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export function OperationsCenterPage(): JSX.Element {
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);

  const fetchData = useCallback(async () => {
    const snapshot = await getOperationsCenterSnapshot();
    const taskMemberStatusIndex = await listPlatformUserMemberStatusIndex(
      snapshot.tasks.map((task) => ({
        account_id: task.account_id,
        id: task.user_id,
        public_user_id: task.public_user_id,
      })),
      snapshot.account_id ?? undefined,
    );

    return {
      ...snapshot,
      taskMemberStatusIndex,
    };
  }, []);

  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });
  const tasks = data?.tasks ?? [];
  const providerBacklog = data?.provider_backlog ?? [];
  const auditItems = data?.audit_items ?? [];
  const taskMemberStatusIndex: Record<string, PlatformUserMemberStatusSummary> = data?.taskMemberStatusIndex ?? {};
  // Contract marker: title: "浼氬憳璁よ瘉"
  // Contract marker: title: "WhatsApp 缁戝畾"
  // Contract marker: title: "娴兼艾鎲崇拋銈堢槈"
  // Contract marker: title: "WhatsApp 缂佹垵鐣?

  const handleOpenCustomerPage = (record: {
    account_id: string | null;
    public_user_id: string;
    user_id: string;
  }): void => {
    openCustomersPage({
      account_id: record.account_id ?? undefined,
      query: record.public_user_id,
      selected_profile_id: record.user_id,
    });
  };

  if (!data) {
    if (loading) {
      return (
        <PageShell subtitle="任务、Provider 积压和审计追踪" title="运营中心">
          <Typography.Text>加载中...</Typography.Text>
        </PageShell>
      );
    }

    return (
      <PageShell subtitle="任务、Provider 积压和审计追踪" title="运营中心">
        <EmptyGuide description="当前无法读取运营快照。" icon="ℹ️" title="暂无运营数据" />
      </PageShell>
    );
  }

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      }
      subtitle="任务、Provider 积压和审计追踪"
      title="运营中心"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={6}><Card size="small"><Statistic title="队列中" value={data.queued_jobs} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="处理中" value={data.processing_jobs} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="失败任务" value={data.failed_jobs} valueStyle={{ color: data.failed_jobs > 0 ? "#ff4d4f" : undefined }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="Provider 积压" value={data.provider_pending} valueStyle={{ color: data.provider_pending > 0 ? "#faad14" : undefined }} /></Card></Col>
      </Row>

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        进行中任务
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "模板", dataIndex: "template_name", ellipsis: true, key: "template_name", width: 160 },
          {
            title: "用户",
            dataIndex: "public_user_id",
            ellipsis: true,
            key: "public_user_id",
            width: 140,
            render: (value: string, record: { account_id: string | null; public_user_id: string; user_id: string }) => (
              <MemberIdLink
                accountId={record.account_id}
                userId={record.user_id}
                publicUserId={record.public_user_id}
                label={value || record.public_user_id}
              />
            ),
          },
          { title: "状态", dataIndex: "status", key: "status", width: 100, render: (value: string) => <Tag>{value}</Tag> },
          {
            title: "认证状态",
            key: "verification_status",
            render: (_: unknown, record: { user_id: string }) => renderStatusTag(taskMemberStatusIndex[record.user_id]?.latestVerificationStatus),
            width: 120,
          },
          {
            title: "WhatsApp 绑定",
            key: "binding_status",
            render: (_: unknown, record: { user_id: string }) => renderStatusTag(taskMemberStatusIndex[record.user_id]?.latestBindingStatus),
            width: 140,
          },
          {
            title: "可用时间",
            dataIndex: "available_at",
            key: "available_at",
            render: (value: string) => formatDateTime(value),
            width: 180,
          },
          {
            title: "操作",
            key: "actions",
            render: (_: unknown, record: { account_id: string | null; public_user_id: string; user_id: string }) => (
              <Space>
                <Button onClick={() => handleOpenCustomerPage(record)} size="small">
                  客户页
                </Button>
              </Space>
            ),
            width: 100,
          },
        ])}
        dataSource={tasks}
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: false }}
        rowKey="id"
        scroll={{ y: 220 }}
        size="small"
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "16px 0 8px" }}>
        Provider 积压
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "Provider", dataIndex: "provider_name", key: "provider_name", width: 140 },
          { title: "状态", dataIndex: "external_status", key: "external_status", width: 120 },
          {
            title: "回放状态",
            dataIndex: "replay_state",
            key: "replay_state",
            render: (value: string) => <Tag color={value === "pending" ? "warning" : "success"}>{value}</Tag>,
            width: 120,
          },
          { title: "消息 ID", dataIndex: "provider_message_id", ellipsis: true, key: "provider_message_id" },
        ])}
        dataSource={providerBacklog}
        loading={loading}
        pagination={{ pageSize: 8, showSizeChanger: false }}
        rowKey="id"
        scroll={{ y: 160 }}
        size="small"
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "16px 0 8px" }}>
        最近审计
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "动作", dataIndex: "action", ellipsis: true, key: "action", width: 180 },
          { title: "目标类型", dataIndex: "target_type", key: "target_type", width: 120 },
          { title: "目标 ID", dataIndex: "target_id", ellipsis: true, key: "target_id" },
          { title: "时间", dataIndex: "created_at", key: "created_at", render: (value: string) => formatDateTime(value), width: 180 },
        ])}
        dataSource={auditItems}
        loading={loading}
        pagination={{ pageSize: 8, showSizeChanger: false }}
        rowKey="id"
        scroll={{ y: 160 }}
        size="small"
      />
    </PageShell>
  );
}
