import { type JSX, useEffect, useState } from "react";
import { Button, Descriptions, Drawer, Spin, Tag, Typography } from "antd";
import { getCustomerSummary, type CustomerSummaryResponse } from "../../services/api";

const { Text } = Typography;

export interface CustomerProfileDrawerProps {
  open: boolean;
  customerId: string | null;
  accountId: string | null;
  onClose: () => void;
  onOpenCustomerPage: () => void;
}

function fmt(v: string | null | undefined): string {
  if (!v) return "-";
  return new Date(v).toLocaleString("zh-CN");
}

function getLifecycleColor(s: string): string {
  if (s === "active") return "success";
  if (s === "blacklisted") return "error";
  if (s === "frozen") return "warning";
  return "default";
}

function fmtLifecycle(s: string): string {
  if (s === "active") return "活跃";
  if (s === "blacklisted") return "已拉黑";
  if (s === "frozen") return "已冻结";
  return s;
}

export function CustomerProfileDrawer({ open, customerId, accountId, onClose, onOpenCustomerPage }: CustomerProfileDrawerProps): JSX.Element {
  const [data, setData] = useState<CustomerSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !customerId) return;
    setLoading(true);
    getCustomerSummary(customerId, accountId ?? undefined)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [open, customerId, accountId]);

  const verifStatus = data?.member_status?.verification?.status ?? null;
  const bindStatus = data?.member_status?.whatsapp_binding?.status ?? null;

  return (
    <Drawer
      title="客户资料"
      open={open}
      onClose={onClose}
      width={420}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
      ) : !data ? (
        <Text type="secondary">加载失败</Text>
      ) : (
        <div>
          <Descriptions column={1} size="small" bordered style={{ marginBottom: 12 }}>
            <Descriptions.Item label="名称">
              {data.customer.display_name ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="用户 ID">
              {data.customer.public_user_id}
            </Descriptions.Item>
            <Descriptions.Item label="语言">
              {data.customer.language}
            </Descriptions.Item>
            <Descriptions.Item label="注册时间">
              {fmt(data.customer.created_at)}
            </Descriptions.Item>
            <Descriptions.Item label="注册IP">
              {data.customer.registration_ip ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={getLifecycleColor(data.customer.lifecycle_status)}>
                {fmtLifecycle(data.customer.lifecycle_status)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="会员验证">
              <Tag color={verifStatus === "approved" ? "success" : "default"}>
                {verifStatus === "approved" ? "已认证" : verifStatus ?? "未认证"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="WhatsApp绑定">
              <Tag color={bindStatus === "bound" || bindStatus === "approved" ? "success" : "default"}>
                {bindStatus === "bound" || bindStatus === "approved" ? "已绑定" : bindStatus ?? "未绑定"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="余额">
              ¥{data.wallet.balance.toFixed(2)}
            </Descriptions.Item>
            <Descriptions.Item label="累计充值">
              ¥{data.wallet.total_recharged.toFixed(2)}
            </Descriptions.Item>
            <Descriptions.Item label="累计提现">
              ¥{data.wallet.total_withdrawn.toFixed(2)}
            </Descriptions.Item>
            <Descriptions.Item label="会话数">
              {data.conversations.total}（进行中 {data.conversations.open}）
            </Descriptions.Item>
            <Descriptions.Item label="工单数">
              {data.tickets.total}（处理中 {data.tickets.open}）
            </Descriptions.Item>
          </Descriptions>
          <Button block size="small" onClick={onOpenCustomerPage}>
            查看完整客户管理页
          </Button>
        </div>
      )}
    </Drawer>
  );
}
