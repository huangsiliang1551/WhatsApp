import { type JSX, useEffect, useState } from "react";
import { Button, Descriptions, Drawer, Spin, Tag, Typography } from "antd";
import { getMemberSummary } from "../../services/memberApi";
import { MemberIdLink } from "../../components/member/MemberIdLink";
import { usePermissions } from "../../hooks/usePermissions";
import type { CustomerSummaryResponse } from "../../types/member";

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
  const { can } = usePermissions();
  const canViewFinance = can("customers.finance");
  const [data, setData] = useState<CustomerSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !customerId) return;
    setLoading(true);
    getMemberSummary(customerId, accountId ?? undefined)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [open, customerId, accountId]);

  const verifStatus = data?.member_status?.verification?.status ?? null;
  const bindStatus = data?.member_status?.whatsapp_binding?.status ?? null;

  if (open && data && !canViewFinance) {
    return (
      <Drawer
        title="瀹㈡埛璧勬枡"
        open={open}
        onClose={onClose}
        width={420}
        destroyOnClose
      >
        <div>
          <Descriptions column={1} size="small" bordered style={{ marginBottom: 12 }}>
            <Descriptions.Item label="鍚嶇О">
              {data.customer.display_name ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="鐢ㄦ埛 ID">
              <MemberIdLink
                accountId={accountId}
                userId={data.customer.id}
                publicUserId={data.customer.public_user_id}
                label={data.customer.public_user_id}
              />
            </Descriptions.Item>
            <Descriptions.Item label="璇█">
              {data.customer.language}
            </Descriptions.Item>
            <Descriptions.Item label="娉ㄥ唽鏃堕棿">
              {fmt(data.customer.created_at)}
            </Descriptions.Item>
            <Descriptions.Item label="娉ㄥ唽IP">
              {data.customer.registration_ip ?? "-"}
            </Descriptions.Item>
            <Descriptions.Item label="鐘舵€?">
              <Tag color={getLifecycleColor(data.customer.lifecycle_status)}>
                {fmtLifecycle(data.customer.lifecycle_status)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="浼氬憳楠岃瘉">
              <Tag color={verifStatus === "approved" ? "success" : "default"}>
                {verifStatus === "approved" ? "宸茶璇?" : verifStatus ?? "鏈璇?"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="WhatsApp缁戝畾">
              <Tag color={bindStatus === "bound" || bindStatus === "approved" ? "success" : "default"}>
                {bindStatus === "bound" || bindStatus === "approved" ? "宸茬粦瀹?" : bindStatus ?? "鏈粦瀹?"}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="璐㈠姟淇℃伅">
              需财务权限
            </Descriptions.Item>
            <Descriptions.Item label="浼氳瘽鏁?">
              {data.conversations.total}锛堣繘琛屼腑 {data.conversations.open}锛?
            </Descriptions.Item>
            <Descriptions.Item label="宸ュ崟鏁?">
              {data.tickets.total}锛堝鐞嗕腑 {data.tickets.open}锛?
            </Descriptions.Item>
          </Descriptions>
          <Button block size="small" onClick={onOpenCustomerPage}>
            鏌ョ湅瀹屾暣瀹㈡埛绠＄悊椤?
          </Button>
        </div>
      </Drawer>
    );
  }

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
              <MemberIdLink
                accountId={accountId}
                userId={data.customer.id}
                publicUserId={data.customer.public_user_id}
                label={data.customer.public_user_id}
              />
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
