import { useCallback, type JSX } from "react";
import { Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography } from "antd";

import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { getMemberAccessSnapshot } from "../services/memberAccess";
import { withSorter } from "../utils/withSorter";

const ACCESS_RESULT_COLORS: Record<string, string> = {
  active: "success",
  restricted: "error",
  review: "warning",
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export function MemberAccessPage(): JSX.Element {
  const fetchData = useCallback(async () => getMemberAccessSnapshot(), []);
  const { data, error, loading, reload } = usePageData({ fetcher: fetchData });

  const bindings = data?.bindings ?? [];
  const activities = data?.activities ?? [];
  const warnings = data?.warnings ?? [];

  if (!data) {
    if (loading) {
      return (
        <PageShell subtitle="成员角色授权与访问权限概览" title="成员授权">
          <Typography.Text>加载中...</Typography.Text>
        </PageShell>
      );
    }

    return (
      <PageShell subtitle="成员角色授权与访问权限概览" title="成员授权">
        <EmptyGuide description="当前无法读取成员授权数据。" icon="👤" title="暂无成员数据" />
      </PageShell>
    );
  }

  const stats = (
    <span style={{ fontSize: 13 }}>
      授权记录 <Typography.Text strong>{bindings.length}</Typography.Text>
      {" | "}
      活动记录 <Typography.Text strong>{activities.length}</Typography.Text>
    </span>
  );

  return (
    <PageShell
      actions={
        <Button loading={loading} onClick={() => void reload()} size="small">
          刷新
        </Button>
      }
      stats={stats}
      subtitle="成员角色授权与访问权限概览"
      title="成员授权"
    >
      {error ? (
        <Typography.Text style={{ display: "block", marginBottom: 12 }} type="danger">
          {error}
        </Typography.Text>
      ) : null}

      {warnings.length ? (
        <Card size="small" style={{ marginBottom: 16 }} title="数据告警">
          {warnings.map((item) => (
            <Typography.Text key={item} style={{ display: "block", marginBottom: 4 }} type="warning">
              {item}
            </Typography.Text>
          ))}
        </Card>
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={6}><Card size="small"><Statistic title="成员数" value={bindings.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="授权账号" value={data.account_ids.length} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="复核中" value={bindings.filter((item) => item.access_result === "review").length} valueStyle={{ color: "#faad14" }} /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="受限成员" value={bindings.filter((item) => item.access_result === "restricted").length} valueStyle={{ color: "#ff4d4f" }} /></Card></Col>
      </Row>

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        授权列表
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "成员", dataIndex: "display_name", key: "display_name", width: 120 },
          { title: "邮箱", dataIndex: "email", ellipsis: true, key: "email", width: 180, render: (value: string | null) => value || "-" },
          { title: "角色", dataIndex: "role_name", key: "role_name", width: 120, render: (value: string | null) => value || "-" },
          { title: "范围", dataIndex: "scope", key: "scope", render: (value: string) => <Tag>{value}</Tag>, width: 90 },
          { title: "账号范围", dataIndex: "account_scope", ellipsis: true, key: "account_scope", render: (value: string[]) => value.join(", "), width: 160 },
          {
            title: "访问结果",
            dataIndex: "access_result",
            key: "access_result",
            render: (value: string) => <Tag color={ACCESS_RESULT_COLORS[value] ?? "default"}>{value}</Tag>,
            width: 100,
          },
          { title: "会话状态", dataIndex: "session_status", key: "session_status", width: 100 },
          { title: "派发会话", dataIndex: "assigned_open_conversations", key: "assigned_open_conversations", width: 100 },
          { title: "更新时间", dataIndex: "updated_at", key: "updated_at", render: (value: string) => formatDateTime(value), width: 180 },
        ])}
        dataSource={bindings}
        loading={loading}
        pagination={{ pageSize: 15, showSizeChanger: false }}
        rowKey={(row) => row.binding_id}
        scroll={{ y: 320 }}
        size="small"
        style={{ marginBottom: 16 }}
      />

      <Typography.Title level={5} style={{ fontSize: 14, margin: "0 0 8px" }}>
        最近活动
      </Typography.Title>
      <Table
        columns={withSorter([
          { title: "标题", dataIndex: "title", ellipsis: true, key: "title", width: 160 },
          { title: "摘要", dataIndex: "summary", ellipsis: true, key: "summary" },
          {
            title: "级别",
            dataIndex: "level",
            key: "level",
            render: (value: string) => <Tag color={value === "warning" ? "warning" : "processing"}>{value}</Tag>,
            width: 100,
          },
          { title: "时间", dataIndex: "occurred_at", key: "occurred_at", render: (value: string) => formatDateTime(value), width: 180 },
        ])}
        dataSource={activities}
        loading={loading}
        pagination={{ pageSize: 8, showSizeChanger: false }}
        rowKey={(row) => row.activity_id}
        scroll={{ y: 220 }}
        size="small"
      />
    </PageShell>
  );
}
