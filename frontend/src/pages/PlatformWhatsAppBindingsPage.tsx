import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Typography,
} from "antd";
import { EmptyGuide, PageShell } from "../components/PageShell";
import { showError, showSuccess } from "../components/Feedback";
import { usePermissions } from "../hooks/usePermissions";
import { WhatsAppStatusTag } from "../components/whatsapp/WhatsAppStatusTag";
import {
  listWhatsAppAccountOptions,
  listWhatsAppBindingReviews,
  reviewWhatsAppBinding,
} from "../services/whatsappAdmin";
import type {
  PlatformWhatsAppBindingRecord,
  WhatsAppBindingReviewStatus,
  WhatsAppAccountOption,
} from "../types/whatsapp";

type ReviewFormValues = {
  status: WhatsAppBindingReviewStatus;
  note?: string;
};

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN");
}

export function PlatformWhatsAppBindingsPage(): JSX.Element {
  const { can, loading: permissionLoading } = usePermissions();
  const canView = can("users.view");
  const canEdit = can("users.edit");

  const [accountOptions, setAccountOptions] = useState<WhatsAppAccountOption[]>([]);
  const [rows, setRows] = useState<PlatformWhatsAppBindingRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string | undefined>();
  const [status, setStatus] = useState<WhatsAppBindingReviewStatus | undefined>();
  const [selectedRecord, setSelectedRecord] = useState<PlatformWhatsAppBindingRecord | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<ReviewFormValues>();

  const loadPage = useCallback(async (): Promise<void> => {
    if (!canView) {
      return;
    }
    setLoading(true);
    setPageError(null);
    try {
      const [accounts, bindings] = await Promise.all([
        listWhatsAppAccountOptions(),
        listWhatsAppBindingReviews({ accountId, status }),
      ]);
      setAccountOptions(accounts);
      setRows(bindings);
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载 WhatsApp 绑定列表失败";
      setPageError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [accountId, canView, status]);

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  const summary = useMemo(() => {
    return rows.reduce(
      (accumulator, record) => {
        accumulator.total += 1;
        accumulator[record.status] += 1;
        return accumulator;
      },
      { total: 0, pending: 0, bound: 0, failed: 0 },
    );
  }, [rows]);

  const handleOpenReview = useCallback((record: PlatformWhatsAppBindingRecord): void => {
    setSelectedRecord(record);
    form.setFieldsValue({
      status: record.status,
      note: record.lastError ?? undefined,
    });
    setModalOpen(true);
  }, [form]);

  const handleSubmit = useCallback(async (): Promise<void> => {
    if (!selectedRecord) {
      return;
    }
    const values = await form.validateFields();
    if (values.status === "failed" && !values.note?.trim()) {
      form.setFields([{ name: "note", errors: ["失败状态必须填写备注"] }]);
      return;
    }
    setSubmitting(true);
    try {
      const updated = await reviewWhatsAppBinding(selectedRecord.id, {
        status: values.status,
        note: values.note?.trim() || undefined,
      });
      setRows((currentRows) =>
        currentRows.map((row) => (row.id === updated.id ? updated : row)),
      );
      setSelectedRecord(updated);
      setModalOpen(false);
      showSuccess("WhatsApp 绑定状态已更新");
    } catch (error) {
      showError(error instanceof Error ? error.message : "更新绑定状态失败");
    } finally {
      setSubmitting(false);
    }
  }, [form, selectedRecord]);

  if (!permissionLoading && !canView) {
    return (
      <PageShell title="WhatsApp 绑定审核" subtitle="平台成员绑定申请与运营审核">
        <EmptyGuide
          icon="馃敀"
          title="缺少 users.view 权限"
          description="当前账号可以看到菜单，但没有读取成员绑定申请的接口权限，需要由主控或权限中心补齐。"
        />
      </PageShell>
    );
  }

  return (
    <PageShell
      title="WhatsApp 绑定审核"
      subtitle="只接真实平台绑定接口，不做假成功，用于审核 H5 会员发起的绑定申请。"
      actions={(
        <Space wrap>
          <Select
            allowClear
            style={{ width: 220 }}
            placeholder="筛选账户"
            value={accountId}
            onChange={(value) => setAccountId(value)}
            options={accountOptions.map((option) => ({
              label: `${option.displayName} (${option.accountId})`,
              value: option.accountId,
            }))}
          />
          <Select
            allowClear
            style={{ width: 160 }}
            placeholder="筛选状态"
            value={status}
            onChange={(value) => setStatus(value)}
            options={[
              { label: "待审核", value: "pending" },
              { label: "已绑定", value: "bound" },
              { label: "失败", value: "failed" },
            ]}
          />
          <Button loading={loading} onClick={() => void loadPage()}>
            刷新
          </Button>
        </Space>
      )}
      stats={(
        <Row gutter={[12, 12]}>
          <Col span={6}><Card size="small"><Statistic title="总申请数" value={summary.total} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="待审核" value={summary.pending} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="已绑定" value={summary.bound} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="失败" value={summary.failed} /></Card></Col>
        </Row>
      )}
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {pageError ? <Alert type="error" showIcon message={pageError} /> : null}
        <Alert
          type="info"
          showIcon
          message="审核说明"
          description="失败状态必须携带备注；绑定成功后，后端会同步更新 H5 绑定状态并触发后续奖励或消息链路。"
        />
        <Table
          rowKey="id"
          loading={loading}
          dataSource={rows}
          locale={{ emptyText: <Empty description="当前筛选下没有绑定申请" /> }}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          onRow={(record) => ({
            onClick: () => setSelectedRecord(record),
          })}
          columns={[
            {
              title: "状态",
              dataIndex: "status",
              width: 100,
              render: (value: WhatsAppBindingReviewStatus) => <WhatsAppStatusTag status={value} />,
            },
            { title: "账户", dataIndex: "accountId", width: 160 },
            { title: "会员号", dataIndex: "memberNo", width: 140 },
            {
              title: "显示名",
              dataIndex: "displayName",
              render: (value: string | null, record: PlatformWhatsAppBindingRecord) => value || record.publicUserId,
            },
            {
              title: "申请号码",
              dataIndex: "requestedPhoneNumber",
              render: (value: string | null) => value || "-",
            },
            { title: "站点", dataIndex: "siteKey", render: (value: string | null) => value || "-" },
            { title: "发起次数", dataIndex: "startCount", width: 90 },
            {
              title: "最近发起",
              dataIndex: "lastStartedAt",
              render: (value: string | null) => formatDateTime(value),
            },
            {
              title: "操作",
              width: 120,
              render: (_: unknown, record: PlatformWhatsAppBindingRecord) => (
                <Button
                  type="link"
                  disabled={!canEdit}
                  onClick={(event) => {
                    event.stopPropagation();
                    handleOpenReview(record);
                  }}
                >
                  审核
                </Button>
              ),
            },
          ]}
        />

        <Card size="small" title="申请详情">
          {!selectedRecord ? (
            <Empty description="选择一条绑定申请以查看详情" />
          ) : (
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="申请 ID">{selectedRecord.id}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <WhatsAppStatusTag status={selectedRecord.status} />
              </Descriptions.Item>
              <Descriptions.Item label="账户">{selectedRecord.accountId}</Descriptions.Item>
              <Descriptions.Item label="用户 ID">{selectedRecord.userId}</Descriptions.Item>
              <Descriptions.Item label="Member Profile">{selectedRecord.memberProfileId}</Descriptions.Item>
              <Descriptions.Item label="Public User ID">{selectedRecord.publicUserId}</Descriptions.Item>
              <Descriptions.Item label="站点">{selectedRecord.siteKey || "-"}</Descriptions.Item>
              <Descriptions.Item label="申请号码">{selectedRecord.requestedPhoneNumber || "-"}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDateTime(selectedRecord.createdAt)}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{formatDateTime(selectedRecord.updatedAt)}</Descriptions.Item>
              <Descriptions.Item label="绑定时间">{formatDateTime(selectedRecord.boundAt)}</Descriptions.Item>
              <Descriptions.Item label="失败说明" span={2}>
                <Typography.Text type={selectedRecord.lastError ? "danger" : undefined}>
                  {selectedRecord.lastError || "-"}
                </Typography.Text>
              </Descriptions.Item>
            </Descriptions>
          )}
        </Card>

        <Modal
          title="审核 WhatsApp 绑定"
          open={modalOpen}
          onCancel={() => setModalOpen(false)}
          onOk={() => void handleSubmit()}
          okText="提交审核"
          confirmLoading={submitting}
          okButtonProps={{ disabled: !canEdit }}
        >
          <Form form={form} layout="vertical">
            <Form.Item label="目标状态" name="status" rules={[{ required: true, message: "请选择审核状态" }]}>
              <Select
                options={[
                  { label: "待审核", value: "pending" },
                  { label: "已绑定", value: "bound" },
                  { label: "失败", value: "failed" },
                ]}
              />
            </Form.Item>
            <Form.Item label="审核备注" name="note">
              <Input.TextArea
                rows={4}
                placeholder="失败时必须填写原因；成功时可填写执行说明。"
              />
            </Form.Item>
          </Form>
        </Modal>
      </Space>
    </PageShell>
  );
}
