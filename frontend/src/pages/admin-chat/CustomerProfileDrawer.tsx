import { type CSSProperties, type JSX, useEffect, useState } from "react";
import { Button, Descriptions, Modal, Spin, Tag, Typography } from "antd";

import { MemberIdLink } from "../../components/member/MemberIdLink";
import { usePermissions } from "../../hooks/usePermissions";
import { getMemberSummary } from "../../services/memberApi";
import type { CustomerSummaryResponse } from "../../types/member";

const { Text, Title } = Typography;

const memberIdWrapStyle: CSSProperties = {
  display: "inline-block",
  maxWidth: "100%",
  overflowWrap: "anywhere",
  wordBreak: "break-word",
};

export interface CustomerProfileDrawerProps {
  open: boolean;
  customerId: string | null;
  accountId: string | null;
  onClose: () => void;
  onOpenCustomerPage: () => void;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function renderLifecycleTag(status: string): JSX.Element {
  if (status === "active") return <Tag color="success">活跃</Tag>;
  if (status === "blacklisted") return <Tag color="error">黑名单</Tag>;
  if (status === "frozen") return <Tag color="processing">冻结</Tag>;
  return <Tag>{status}</Tag>;
}

function renderVerificationTag(status: string | null): JSX.Element {
  if (status === "approved") return <Tag color="success">已通过</Tag>;
  if (status === "pending") return <Tag color="warning">待审核</Tag>;
  if (status === "rejected") return <Tag color="error">已拒绝</Tag>;
  return <Tag>{status || "未提交"}</Tag>;
}

function renderBindingTag(status: string | null): JSX.Element {
  if (status === "bound" || status === "approved") return <Tag color="success">已绑定</Tag>;
  if (status === "pending") return <Tag color="warning">待绑定</Tag>;
  return <Tag>{status || "未绑定"}</Tag>;
}

export function CustomerProfileDrawer({
  open,
  customerId,
  accountId,
  onClose,
  onOpenCustomerPage,
}: CustomerProfileDrawerProps): JSX.Element {
  const { can } = usePermissions();
  const canViewFinance = can("customers.finance");
  const [data, setData] = useState<CustomerSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !customerId) {
      setData(null);
      return;
    }
    setLoading(true);
    getMemberSummary(customerId, accountId ?? undefined)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [accountId, customerId, open]);

  return (
    <Modal
      title="客户资料"
      open={open}
      onCancel={onClose}
      footer={null}
      width={760}
      centered
      destroyOnClose={false}
      styles={{
        body: {
          maxHeight: "calc(100dvh - 180px)",
          overflow: "auto",
          padding: 20,
        },
      }}
    >
      {loading ? (
        <div style={{ padding: 48, textAlign: "center" }}>
          <Spin />
        </div>
      ) : !data ? (
        <Text type="secondary">加载失败</Text>
      ) : (
        <div style={{ display: "grid", gap: 16 }}>
          <section style={{ background: "#faf7f0", border: "1px solid #efe3cd", borderRadius: 16, padding: 16 }}>
            <Title level={5} style={{ marginTop: 0, marginBottom: 12 }}>
              {data.customer.display_name || data.customer.public_user_id}
            </Title>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="用户 ID">
                <span style={memberIdWrapStyle}>
                  <MemberIdLink
                    accountId={accountId}
                    userId={data.customer.id}
                    publicUserId={data.customer.public_user_id}
                    label={data.customer.public_user_id}
                  />
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="语言">{data.customer.language}</Descriptions.Item>
              <Descriptions.Item label="注册时间">{formatDateTime(data.customer.created_at)}</Descriptions.Item>
              <Descriptions.Item label="注册 IP">{data.customer.registration_ip ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="状态">{renderLifecycleTag(data.customer.lifecycle_status)}</Descriptions.Item>
              <Descriptions.Item label="会员认证">
                {renderVerificationTag(data.member_status?.verification?.status ?? null)}
              </Descriptions.Item>
              <Descriptions.Item label="WhatsApp 绑定">
                {renderBindingTag(data.member_status?.whatsapp_binding?.status ?? null)}
              </Descriptions.Item>
              <Descriptions.Item label="余额">
                {canViewFinance ? `¥${data.wallet.balance.toFixed(2)}` : "需财务权限"}
              </Descriptions.Item>
              <Descriptions.Item label="累计充值">
                {canViewFinance ? `¥${data.wallet.total_recharged.toFixed(2)}` : "需财务权限"}
              </Descriptions.Item>
              <Descriptions.Item label="累计提现">
                {canViewFinance ? `¥${data.wallet.total_withdrawn.toFixed(2)}` : "需财务权限"}
              </Descriptions.Item>
              <Descriptions.Item label="会话统计">
                {data.conversations.total}，进行中 {data.conversations.open}
              </Descriptions.Item>
              <Descriptions.Item label="工单统计">
                {data.tickets.total}，处理中 {data.tickets.open}
              </Descriptions.Item>
            </Descriptions>
          </section>

          <Button block type="primary" onClick={onOpenCustomerPage}>
            查看用户资料
          </Button>
        </div>
      )}
    </Modal>
  );
}
