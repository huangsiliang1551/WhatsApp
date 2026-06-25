import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Button, Space, Table, Tag, Typography, message } from "antd";
import { withSorter } from "../utils/withSorter";

import { PageShell, EmptyGuide } from "../components/PageShell";
import { DangerButton, showError, showSuccess } from "../components/Feedback";
import { MemberIdLink } from "../components/member/MemberIdLink";
import { usePageData } from "../hooks/usePageData";
import { useAppStore } from "../stores/appStore";
import {
  listTaskInstances,
  updateReviewStatus,
  type TaskInstance,
} from "../services/api";
import {
  listPlatformMemberVerifications,
  listPlatformMemberWhatsAppBindings,
  updatePlatformMemberVerificationStatus,
  updatePlatformMemberWhatsAppBindingStatus,
  type PlatformMemberVerificationRequest,
  type PlatformMemberWhatsAppBindingRequest,
} from "../services/h5";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";

const STATUS_COLORS: Record<string, string> = {
  available: "#1677ff",
  claimed: "#faad14",
  submitted: "#722ed1",
  under_review: "#fa8c16",
  approved: "#52c41a",
  rejected: "#ff4d4f",
  expired: "#d9d9d9",
  completed: "#52c41a",
};

const STATUS_LABELS: Record<string, string> = {
  available: "待认领",
  claimed: "已认领",
  submitted: "已提交",
  under_review: "审核中",
  approved: "已通过",
  rejected: "已驳回",
  expired: "已过期",
  completed: "已完成",
};

function renderReviewTag(status: string): JSX.Element {
  return <Tag color={STATUS_COLORS[status] ?? "default"}>{STATUS_LABELS[status] ?? status}</Tag>;
}

export function ReviewsPage(): JSX.Element {
  const openUsersPage = useAppStore((state) => state.openUsersPage);
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);

  const [sites, setSites] = useState<H5Site[]>([]);
  const [selectedVerificationItem, setSelectedVerificationItem] =
    useState<PlatformMemberVerificationRequest | null>(null);
  const [selectedBindingItem, setSelectedBindingItem] =
    useState<PlatformMemberWhatsAppBindingRequest | null>(null);

  useEffect(() => {
    listSites().then(setSites).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    const [instances, verificationRequests, bindingRequests] = await Promise.all([
      listTaskInstances(),
      listPlatformMemberVerifications(),
      listPlatformMemberWhatsAppBindings(),
    ]);
    return { instances, verificationRequests, bindingRequests };
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const instances = data?.instances ?? [];
  const verificationRequests = data?.verificationRequests ?? [];
  const bindingRequests = data?.bindingRequests ?? [];

  const pendingReview = instances.filter((item) => item.status === "submitted" || item.status === "under_review");
  const approved = instances.filter((item) => item.status === "approved" || item.status === "completed");
  const rejected = instances.filter((item) => item.status === "rejected");

  const pendingVerifications = verificationRequests.filter((item) => item.status !== "approved" && item.status !== "rejected");
  const pendingBindings = bindingRequests.filter((item) => item.status === "pending");

  const selectedVerificationSummary = useMemo(
    () => selectedVerificationItem ?? pendingVerifications[0] ?? null,
    [pendingVerifications, selectedVerificationItem],
  );
  const selectedBindingSummary = useMemo(
    () => selectedBindingItem ?? pendingBindings[0] ?? null,
    [pendingBindings, selectedBindingItem],
  );

  const handleReview = async (instanceId: string, decision: "approve" | "reject"): Promise<void> => {
    try {
      await updateReviewStatus(instanceId, decision);
      showSuccess(decision === "approve" ? "审核通过" : "审核驳回");
      void reload();
    } catch {
      showError("操作失败");
    }
  };

  const handleBatchReview = async (decision: "approve" | "reject"): Promise<void> => {
    for (const item of pendingReview) {
      try {
        await updateReviewStatus(item.id, decision);
      } catch {
        // keep best effort for queue cleanup
      }
    }
    showSuccess(`已批量${decision === "approve" ? "通过" : "驳回"} ${pendingReview.length} 项`);
    void reload();
  };

  const handleVerificationDecision = async (
    requestId: string,
    status: "under_review" | "approved" | "rejected",
  ): Promise<void> => {
    try {
      await updatePlatformMemberVerificationStatus(requestId, { status });
      message.success("会员认证状态已更新");
      void reload();
    } catch (loadError) {
      message.error(loadError instanceof Error ? loadError.message : "会员认证审核失败");
    }
  };

  const handleBindingDecision = async (
    requestId: string,
    status: "pending" | "bound" | "failed",
  ): Promise<void> => {
    try {
      await updatePlatformMemberWhatsAppBindingStatus(requestId, { status });
      message.success("WhatsApp 绑定状态已更新");
      void reload();
    } catch (loadError) {
      message.error(loadError instanceof Error ? loadError.message : "WhatsApp 绑定审核失败");
    }
  };

  const handleOpenVerificationUserPage = (): void => {
    if (!selectedVerificationSummary) {
      return;
    }
    const selectedVerificationItem = selectedVerificationSummary;
    openUsersPage({
      account_id: selectedVerificationItem.accountId,
      selected_user_id: selectedVerificationItem.userId,
      search: selectedVerificationItem.publicUserId,
      // query: selectedVerificationItem.publicUserId
    });
  };

  const handleOpenVerificationCustomerPage = (): void => {
    if (!selectedVerificationSummary) {
      return;
    }
    const selectedVerificationItem = selectedVerificationSummary;
    openCustomersPage({
      account_id: selectedVerificationItem.accountId,
      selected_profile_id: selectedVerificationItem.userId,
      query: selectedVerificationItem.publicUserId,
    });
  };

  const handleOpenBindingUserPage = (): void => {
    if (!selectedBindingSummary) {
      return;
    }
    const selectedBindingItem = selectedBindingSummary;
    openUsersPage({
      account_id: selectedBindingItem.accountId,
      selected_user_id: selectedBindingItem.userId,
      search: selectedBindingItem.publicUserId,
      // query: selectedBindingItem.publicUserId
    });
  };

  const handleOpenBindingCustomerPage = (): void => {
    if (!selectedBindingSummary) {
      return;
    }
    const selectedBindingItem = selectedBindingSummary;
    openCustomersPage({
      account_id: selectedBindingItem.accountId,
      selected_profile_id: selectedBindingItem.userId,
      query: selectedBindingItem.publicUserId,
    });
  };

  const stats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>任务审核 <Typography.Text strong style={{ color: "#fa8c16" }}>{pendingReview.length}</Typography.Text></span>
      <span>会员认证 <Typography.Text strong style={{ color: "#1677ff" }}>{pendingVerifications.length}</Typography.Text></span>
      <span>WhatsApp 绑定 <Typography.Text strong style={{ color: "#52c41a" }}>{pendingBindings.length}</Typography.Text></span>
      <span>已驳回 <Typography.Text strong style={{ color: "#ff4d4f" }}>{rejected.length}</Typography.Text></span>
    </Space>
  );

  const actions = (
    <Space>
      {pendingReview.length > 1 ? (
        <Button type="primary" onClick={() => void handleBatchReview("approve")}>
          批量通过 ({pendingReview.length})
        </Button>
      ) : null}
      {pendingReview.length > 1 ? (
        <DangerButton
          label={`批量驳回 (${pendingReview.length})`}
          confirmTitle={`确认驳回全部 ${pendingReview.length} 项`}
          onConfirm={() => handleBatchReview("reject")}
          danger
          type="default"
        />
      ) : null}
      <Button onClick={() => void reload()} loading={loading}>刷新</Button>
    </Space>
  );

  const taskColumns = [
    { title: "任务", dataIndex: "template_name", key: "template_name", ellipsis: true },
    {
      title: "用户",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 140,
      ellipsis: true,
      render: (value: string, record: TaskInstance) => (
        <MemberIdLink
          accountId={record.account_id}
          userId={record.user_id}
          publicUserId={record.public_user_id}
          label={value || record.public_user_id}
        />
      ),
    },
    {
      title: "用户来源",
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
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => renderReviewTag(value),
    },
    {
      title: "提交时间",
      dataIndex: "submitted_at",
      key: "submitted_at",
      width: 180,
      render: (value: string | null) => (value ? new Date(value).toLocaleString("zh-CN") : "-"),
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      render: (_: unknown, record: TaskInstance) => {
        if (record.status !== "submitted" && record.status !== "under_review") {
          return null;
        }
        return (
          <Space size="small">
            <Button size="small" type="primary" onClick={() => void handleReview(record.id, "approve")}>通过</Button>
            <DangerButton
              label="驳回"
              confirmTitle="确认驳回该任务提交？"
              onConfirm={() => handleReview(record.id, "reject")}
              danger
              type="default"
            />
          </Space>
        );
      },
    },
  ];

  const verificationColumns = [
    { title: "会员号", dataIndex: "memberNo", key: "memberNo", width: 120 },
    {
      title: "用户",
      dataIndex: "publicUserId",
      key: "publicUserId",
      width: 160,
      render: (value: string, record: PlatformMemberVerificationRequest) => (
        <MemberIdLink
          accountId={record.accountId}
          userId={record.userId}
          publicUserId={record.publicUserId}
          label={value || record.publicUserId}
        />
      ),
    },
    { title: "状态", dataIndex: "status", key: "status", width: 120, render: (value: string) => <Tag color="blue">{value}</Tag> },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: PlatformMemberVerificationRequest) => (
        <Space size="small">
          <Button size="small" onClick={() => setSelectedVerificationItem(record)}>详情</Button>
          <Button size="small" type="primary" onClick={() => void handleVerificationDecision(record.id, "approved")}>通过</Button>
          <DangerButton
            label="驳回"
            confirmTitle="确认驳回该会员认证申请？"
            onConfirm={() => handleVerificationDecision(record.id, "rejected")}
            danger
            type="default"
          />
        </Space>
      ),
    },
  ];

  const bindingColumns = [
    { title: "会员号", dataIndex: "memberNo", key: "memberNo", width: 120 },
    {
      title: "用户",
      dataIndex: "publicUserId",
      key: "publicUserId",
      width: 160,
      render: (value: string, record: PlatformMemberWhatsAppBindingRequest) => (
        <MemberIdLink
          accountId={record.accountId}
          userId={record.userId}
          publicUserId={record.publicUserId}
          label={value || record.publicUserId}
        />
      ),
    },
    { title: "请求号码", dataIndex: "requestedPhoneNumber", key: "requestedPhoneNumber", width: 160, render: (value: string | null) => value || "-" },
    { title: "状态", dataIndex: "status", key: "status", width: 120, render: (value: string) => <Tag color="green">{value}</Tag> },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: PlatformMemberWhatsAppBindingRequest) => (
        <Space size="small">
          <Button size="small" onClick={() => setSelectedBindingItem(record)}>详情</Button>
          <Button size="small" type="primary" onClick={() => void handleBindingDecision(record.id, "bound")}>通过</Button>
          <DangerButton
            label="失败"
            confirmTitle="确认将该 WhatsApp 绑定申请标记为失败？"
            onConfirm={() => handleBindingDecision(record.id, "failed")}
            danger
            type="default"
          />
        </Space>
      ),
    },
  ];

  const isEmpty = instances.length === 0 && verificationRequests.length === 0 && bindingRequests.length === 0 && !loading;

  if (isEmpty) {
    return (
      <PageShell title="审核队列" subtitle="任务审核、会员认证、WhatsApp 绑定共用队列" actions={actions} stats={stats}>
        <EmptyGuide icon="📝" title="暂无审核项" description="当前没有待处理的审核请求" />
      </PageShell>
    );
  }

  return (
    <PageShell title="审核队列" subtitle="任务审核、会员认证、WhatsApp 绑定共用队列" actions={actions} stats={stats}>
      {error ? (
        <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>
      ) : null}

      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        该提交已驳回；后续应转任务申诉或帮助工单，不应再次直接审核。
      </Typography.Paragraph>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        请基于最近一次提交和审核备注给出结论；驳回后不要暗示用户可直接重新提交，而应引导至任务申诉或帮助工单。
      </Typography.Paragraph>

      <Typography.Title level={5}>任务审核</Typography.Title>
      <Table
        dataSource={instances}
        columns={withSorter(taskColumns)}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: true }}
        scroll={{ y: 280 }}
      />

      <div style={{ marginTop: 20 }}>
        <Typography.Title level={5}>会员认证</Typography.Title>
        <Table
          dataSource={verificationRequests}
          columns={withSorter(verificationColumns)}
          rowKey="id"
          size="small"
          loading={loading}
          pagination={{ pageSize: 6, showSizeChanger: false }}
        />
        {selectedVerificationSummary ? (
          <Space style={{ marginTop: 8 }}>
            <Button onClick={handleOpenVerificationUserPage}>用户页</Button>
            <Button onClick={handleOpenVerificationCustomerPage}>客户页</Button>
          </Space>
        ) : null}
      </div>

      <div style={{ marginTop: 20 }}>
        <Typography.Title level={5}>WhatsApp 绑定</Typography.Title>
        <Table
          dataSource={bindingRequests}
          columns={withSorter(bindingColumns)}
          rowKey="id"
          size="small"
          loading={loading}
          pagination={{ pageSize: 6, showSizeChanger: false }}
        />
        {selectedBindingSummary ? (
          <Space style={{ marginTop: 8 }}>
            <Button onClick={handleOpenBindingUserPage}>用户页</Button>
            <Button onClick={handleOpenBindingCustomerPage}>客户页</Button>
          </Space>
        ) : null}
      </div>
    </PageShell>
  );
}
