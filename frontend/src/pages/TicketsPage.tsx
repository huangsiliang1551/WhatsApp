import { useCallback, useEffect, useState, type JSX } from "react";
import { Button, Card, Col, Input, Modal, Row, Select, Space, Table, Tag, Typography, message } from "antd";
import { withSorter } from "../utils/withSorter";
import { ClearOutlined, SendOutlined, TagOutlined } from "@ant-design/icons";

import { DangerButton, showError, showSuccess } from "../components/Feedback";
import { EmptyGuide, PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { usePermissions } from "../hooks/usePermissions";
import { useAppStore } from "../stores/appStore";
import { api, batchSendTemplate, batchUpdateTags } from "../services/api";
import { listSupportTickets, getSupportTicketStatusLabel, type SupportTicket, type SupportTicketStatus } from "../services/h5";
import {
  getPlatformUserMemberStatusSnapshot,
  type PlatformUserMemberStatusSnapshot,
} from "../services/operations";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";

const STATUS_COLORS: Record<string, string> = {
  open: "#ff4d4f",
  in_progress: "#1677ff",
  pending_user: "#faad14",
  resolved: "#52c41a",
  rejected: "#999",
  closed: "#d9d9d9",
  cancelled: "#d9d9d9",
};

const KANBAN_COLUMNS: { key: SupportTicketStatus; label: string; color: string }[] = [
  { key: "open", label: "待处理", color: "#fff2f0" },
  { key: "in_progress", label: "处理中", color: "#e6f4ff" },
  { key: "pending_user", label: "待用户补充", color: "#fffbe6" },
  { key: "resolved", label: "已解决", color: "#f6ffed" },
];

function getSlaText(ticket: SupportTicket): { text: string; urgent: boolean } {
  const created = new Date(ticket.created_at).getTime();
  const elapsed = Date.now() - created;
  const hours = Math.floor(elapsed / 3600000);
  if (hours > 24) {
    return { text: `${Math.floor(hours / 24)}天未处理`, urgent: true };
  }
  if (hours > 12) {
    return { text: `${hours}小时`, urgent: false };
  }
  return { text: `${hours}h`, urgent: false };
}

function renderMemberTag(status: string | null | undefined): JSX.Element {
  if (!status) {
    return <Tag>-</Tag>;
  }
  const color = status === "approved" || status === "bound" ? "green" : status === "rejected" || status === "failed" ? "red" : "blue";
  return <Tag color={color}>{status}</Tag>;
}

export function TicketsPage(): JSX.Element {
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);
  const { can } = usePermissions();

  const [viewMode, setViewMode] = useState<"kanban" | "list">("kanban");
  const [sites, setSites] = useState<H5Site[]>([]);
  const [siteFilter, setSiteFilter] = useState<string | undefined>();
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
  const [selectedTicketMemberStatus, setSelectedTicketMemberStatus] = useState<PlatformUserMemberStatusSnapshot | null>(null);

  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [batchTagsModalOpen, setBatchTagsModalOpen] = useState(false);
  const [batchTagsAdd, setBatchTagsAdd] = useState<string[]>([]);
  const [batchTagsRemove, setBatchTagsRemove] = useState<string[]>([]);
  const [batchTagsLoading, setBatchTagsLoading] = useState(false);
  const [batchTemplateModalOpen, setBatchTemplateModalOpen] = useState(false);
  const [batchTemplateId, setBatchTemplateId] = useState<string>("");
  const [batchTemplateVars, setBatchTemplateVars] = useState<string>("");
  const [batchTemplateLoading, setBatchTemplateLoading] = useState(false);

  useEffect(() => {
    listSites().then(setSites).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedTicket) {
      setSelectedTicketMemberStatus(null);
      return;
    }
    const detail = selectedTicket;
    getPlatformUserMemberStatusSnapshot({
      id: detail.public_user_id,
      account_id: detail.account_id,
      public_user_id: detail.public_user_id,
    })
      .then(setSelectedTicketMemberStatus)
      .catch(() => setSelectedTicketMemberStatus(null));
  }, [selectedTicket?.account_id, selectedTicket?.id, selectedTicket?.public_user_id]);

  const fetchData = useCallback(async () => {
    const tickets = await listSupportTickets();
    return { tickets };
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const tickets = data?.tickets ?? [];

  const handleStatusChange = async (ticketId: string, newStatus: SupportTicketStatus): Promise<void> => {
    try {
      await api.post(`/api/tickets/${encodeURIComponent(ticketId)}/status`, { status: newStatus, actor_name: "operator" });
      showSuccess("状态已更新");
      void reload();
    } catch {
      showError("操作失败");
    }
  };

  const handleBatchTagsSubmit = async (): Promise<void> => {
    setBatchTagsLoading(true);
    try {
      await batchUpdateTags({
        entity_type: "ticket",
        entity_ids: selectedRowKeys as string[],
        add_tags: batchTagsAdd,
        remove_tags: batchTagsRemove,
      });
      showSuccess("标签已更新");
      setBatchTagsModalOpen(false);
      setBatchTagsAdd([]);
      setBatchTagsRemove([]);
      setSelectedRowKeys([]);
    } catch {
      showError("更新标签失败");
    } finally {
      setBatchTagsLoading(false);
    }
  };

  const handleBatchTemplateSubmit = async (): Promise<void> => {
    if (!batchTemplateId) {
      message.warning("请选择模板");
      return;
    }
    setBatchTemplateLoading(true);
    try {
      let variables: Record<string, string> = {};
      if (batchTemplateVars.trim()) {
        try {
          variables = JSON.parse(batchTemplateVars);
        } catch {
          message.warning("变量格式错误");
          setBatchTemplateLoading(false);
          return;
        }
      }
      await batchSendTemplate({
        entity_type: "ticket",
        entity_ids: selectedRowKeys as string[],
        template_id: batchTemplateId,
        variables,
      });
      showSuccess("模板消息已发送");
      setBatchTemplateModalOpen(false);
      setBatchTemplateId("");
      setBatchTemplateVars("");
      setSelectedRowKeys([]);
    } catch {
      showError("发送失败");
    } finally {
      setBatchTemplateLoading(false);
    }
  };

  const handleOpenTicketCustomerPage = (detail: Pick<SupportTicket, "account_id" | "public_user_id">): void => {
    openCustomersPage({
      account_id: detail.account_id,
      selected_profile_id: detail.public_user_id,
      query: detail.public_user_id,
    });
  };

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      {KANBAN_COLUMNS.map((column) => (
        <span key={column.key}>
          {column.label} <Typography.Text strong style={{ color: STATUS_COLORS[column.key]}}>{tickets.filter((ticket) => ticket.status === column.key).length}</Typography.Text>
        </span>
      ))}
      <span>已解决/关闭 <Typography.Text strong style={{ color: "#52c41a" }}>{tickets.filter((ticket) => ticket.status === "resolved" || ticket.status === "closed").length}</Typography.Text></span>
    </Space>
  );

  const actions = (
    <Space>
      <Select
        placeholder="客户来源"
        allowClear
        style={{ width: 140 }}
        value={siteFilter}
        onChange={setSiteFilter}
        options={sites.map((item) => ({ label: item.brand_name || item.site_key, value: item.site_key }))}
      />
      <Button size="small" type={viewMode === "kanban" ? "primary" : "default"} onClick={() => setViewMode("kanban")}>看板</Button>
      <Button size="small" type={viewMode === "list" ? "primary" : "default"} onClick={() => setViewMode("list")}>列表</Button>
      <Button size="small" onClick={() => void reload()} loading={loading}>刷新</Button>
    </Space>
  );

  const renderActions = (ticket: SupportTicket): JSX.Element => (
    <Space size="small">
      <Button size="small" onClick={() => setSelectedTicket(ticket)}>详情</Button>
      {can("tickets.status") && ticket.status === "open" ? (
        <Button size="small" type="primary" onClick={() => void handleStatusChange(ticket.id, "in_progress")}>处理</Button>
      ) : null}
      {can("tickets.status") && ticket.status === "in_progress" ? (
        <Button size="small" onClick={() => void handleStatusChange(ticket.id, "pending_user")}>待补充</Button>
      ) : null}
      {(ticket.status === "open" || ticket.status === "in_progress") && can("tickets.close") ? (
        <DangerButton label="关闭" confirmTitle="确认关闭工单？" onConfirm={() => handleStatusChange(ticket.id, "closed")} danger type="default" />
      ) : null}
      {can("tickets.status") && ticket.status === "resolved" ? (
        <Button size="small" onClick={() => void handleStatusChange(ticket.id, "open")}>重新打开</Button>
      ) : null}
    </Space>
  );

  const columns = [
    {
      title: "主题",
      dataIndex: "subject",
      key: "subject",
      ellipsis: true,
      render: (value: string, record: SupportTicket) => (
        <>
          <Typography.Text strong>{value}</Typography.Text>
          <Typography.Paragraph ellipsis style={{ fontSize: 12, color: "#666", margin: 0 }}>
            {record.content_preview}
          </Typography.Paragraph>
        </>
      ),
    },
    { title: "状态", dataIndex: "status", key: "status", width: 100, render: (value: SupportTicketStatus) => <Tag color={STATUS_COLORS[value]}>{getSupportTicketStatusLabel(value)}</Tag> },
    { title: "分类", dataIndex: "category", key: "category", width: 100 },
    { title: "优先级", dataIndex: "priority", key: "priority", width: 100 },
    {
      title: "SLA",
      key: "sla",
      width: 100,
      render: (_: unknown, record: SupportTicket) => {
        const sla = getSlaText(record);
        return <Typography.Text type={sla.urgent ? "danger" : "secondary"} style={{ fontSize: 12 }}>{sla.text}</Typography.Text>;
      },
    },
    {
      title: "客户来源",
      dataIndex: "site_key",
      key: "site_key",
      width: 140,
      render: (siteKey: string | null) => {
        if (!siteKey) {
          return "-";
        }
        const site = sites.find((item) => item.site_key === siteKey);
        return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
      },
    },
    { title: "更新时间", dataIndex: "updated_at", key: "updated_at", width: 140, render: (value: string) => new Date(value).toLocaleDateString("zh-CN") },
    { title: "操作", key: "actions", width: 220, render: (_: unknown, record: SupportTicket) => renderActions(record) },
  ];

  if (tickets.length === 0 && !loading) {
    return (
      <PageShell title="工单管理" subtitle="查看和处理用户提交的工单" actions={actions} stats={stats}>
        <EmptyGuide icon="🎫" title="暂无工单" description="当前没有待处理的工单" />
      </PageShell>
    );
  }

  return (
    <PageShell title="工单管理" subtitle="查看和处理用户提交的工单" actions={actions} stats={stats}>
      {error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text> : null}
      <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
        当前工单已驳回并结束；如关联任务也已驳回，请转任务申诉或新建帮助工单继续处理。
      </Typography.Paragraph>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        该工单已经按当前链路驳回结束，不要引导用户直接重新提交关联任务，也不要暗示任务会恢复提交入口。
      </Typography.Paragraph>

      {viewMode === "kanban" ? (
        <div style={{ overflowX: "auto", height: "100%" }}>
          <Row gutter={12} style={{ minWidth: 900, height: "100%" }}>
            {KANBAN_COLUMNS.map((column) => {
              const columnTickets = tickets.filter((ticket) => ticket.status === column.key);
              return (
                <Col key={column.key} span={6} style={{ height: "100%" }}>
                  <div style={{ background: column.color, borderRadius: 6, padding: 8, height: "100%", display: "flex", flexDirection: "column" }}>
                    <Typography.Text strong style={{ marginBottom: 8, display: "block" }}>{column.label} ({columnTickets.length})</Typography.Text>
                    <div style={{ flex: 1, overflowY: "auto" }}>
                      {columnTickets.map((ticket) => (
                        <Card key={ticket.id} size="small" style={{ marginBottom: 6 }}>
                          <Typography.Text strong style={{ fontSize: 13 }}>{ticket.subject}</Typography.Text>
                          <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>{ticket.content_preview?.slice(0, 40)}</div>
                          <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 4 }}>
                            <Tag color={STATUS_COLORS[ticket.status]} style={{ fontSize: 10, margin: 0 }}>{getSupportTicketStatusLabel(ticket.status)}</Tag>
                            {getSlaText(ticket).urgent ? <Typography.Text type="danger" style={{ fontSize: 11 }}>{getSlaText(ticket).text}</Typography.Text> : null}
                          </div>
                          <div style={{ marginTop: 4 }}>{renderActions(ticket)}</div>
                        </Card>
                      ))}
                      {columnTickets.length === 0 ? <div style={{ textAlign: "center", color: "#bbb", padding: 16, fontSize: 12 }}>暂无</div> : null}
                    </div>
                  </div>
                </Col>
              );
            })}
          </Row>
        </div>
      ) : (
        <Table
          dataSource={tickets}
          columns={withSorter(columns)}
          rowKey="id"
          size="small"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          scroll={{ y: "calc(100vh - 320px)" }}
          rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys) }}
        />
      )}

      {selectedTicket ? (
        <div style={{ marginTop: 12, padding: 12, border: "1px solid #f0f0f0", borderRadius: 8 }}>
          <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>工单详情</Typography.Text>
          <Space direction="vertical" size={4}>
            <Typography.Text>Member Verification Status: {selectedTicketMemberStatus?.verificationRequests[0]?.status ?? "N/A"}</Typography.Text>
            <Typography.Text>WhatsApp Binding Status: {selectedTicketMemberStatus?.bindingRequests[0]?.status ?? "N/A"}</Typography.Text>
            <Typography.Text type="secondary">{selectedTicket.public_user_id} / {selectedTicket.account_id}</Typography.Text>
            <Button size="small" onClick={() => handleOpenTicketCustomerPage(selectedTicket)}>客户页</Button>
          </Space>
        </div>
      ) : null}

      {selectedRowKeys.length > 0 ? (
        <div
          style={{
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
          }}
        >
          <Typography.Text style={{ color: "#fff", fontSize: 13 }}>已选 {selectedRowKeys.length} 项</Typography.Text>
          <Space size={8}>
            <Button type="primary" ghost size="small" icon={<TagOutlined />} onClick={() => { setBatchTagsAdd([]); setBatchTagsRemove([]); setBatchTagsModalOpen(true); }}>修改标签</Button>
            <Button type="primary" ghost size="small" icon={<SendOutlined />} onClick={() => { setBatchTemplateId(""); setBatchTemplateVars(""); setBatchTemplateModalOpen(true); }}>发送模板</Button>
            <Button type="primary" ghost size="small" icon={<ClearOutlined />} onClick={() => setSelectedRowKeys([])}>取消选择</Button>
          </Space>
        </div>
      ) : null}

      <Modal title="批量修改标签" open={batchTagsModalOpen} onCancel={() => setBatchTagsModalOpen(false)} onOk={() => void handleBatchTagsSubmit()} confirmLoading={batchTagsLoading} okText="保存" cancelText="取消">
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>添加标签</Typography.Text>
            <Select mode="tags" style={{ width: "100%" }} value={batchTagsAdd} onChange={setBatchTagsAdd} tokenSeparators={[","]} />
          </div>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>移除标签</Typography.Text>
            <Select mode="tags" style={{ width: "100%" }} value={batchTagsRemove} onChange={setBatchTagsRemove} tokenSeparators={[","]} />
          </div>
        </Space>
      </Modal>

      <Modal title="批量发送模板消息" open={batchTemplateModalOpen} onCancel={() => { setBatchTemplateModalOpen(false); setBatchTemplateId(""); setBatchTemplateVars(""); }} onOk={() => void handleBatchTemplateSubmit()} confirmLoading={batchTemplateLoading} okText="发送" cancelText="取消">
        <div style={{ marginBottom: 12 }}>
          <Typography.Text>已选 {selectedRowKeys.length} 个工单</Typography.Text>
        </div>
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>选择模板</Typography.Text>
            <Select placeholder="选择模板" style={{ width: "100%" }} value={batchTemplateId || undefined} onChange={setBatchTemplateId} options={[]} />
          </div>
          <div>
            <Typography.Text style={{ display: "block", marginBottom: 4, fontSize: 13 }}>变量 (JSON 格式，可选)</Typography.Text>
            <Input.TextArea rows={3} placeholder='{"{{customer_name}}": "张三"}' value={batchTemplateVars} onChange={(event) => setBatchTemplateVars(event.target.value)} />
          </div>
        </Space>
      </Modal>
    </PageShell>
  );
}
