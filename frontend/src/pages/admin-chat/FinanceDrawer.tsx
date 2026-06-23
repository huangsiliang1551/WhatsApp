import { type JSX, useEffect, useState } from "react";
import { Descriptions, Drawer, Spin, Tabs, Typography } from "antd";
import { getCustomerSummary, type CustomerSummaryResponse } from "../../services/api";

const { Text } = Typography;

export interface FinanceDrawerProps {
  open: boolean;
  customerId: string | null;
  accountId: string | null;
  onClose: () => void;
}

function fmt(v: string | null | undefined): string {
  if (!v) return "-";
  return new Date(v).toLocaleString("zh-CN");
}

function fmtAmt(n: number): string {
  return n.toFixed(2);
}

const DIR_MAP: Record<string, string> = { credit: "+", debit: "-" };
const DIR_COLOR: Record<string, string> = { credit: "#52c41a", debit: "#ff4d4f" };
const TYPE_LABEL: Record<string, string> = {
  recharge: "充值", reward: "奖励", task: "任务", withdrawal: "提现",
  system: "系统", order: "订单",
};

export function FinanceDrawer({ open, customerId, accountId, onClose }: FinanceDrawerProps): JSX.Element {
  const [data, setData] = useState<CustomerSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"balance" | "recharge">("balance");

  useEffect(() => {
    if (!open || !customerId) return;
    setLoading(true);
    getCustomerSummary(customerId, accountId ?? undefined)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [open, customerId, accountId]);

  return (
    <Drawer
      title="财务明细"
      open={open}
      onClose={onClose}
      width={400}
      destroyOnClose
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
      ) : !data ? (
        <Text type="secondary">加载失败</Text>
      ) : (
        <Tabs
          activeKey={tab}
          onChange={(k) => setTab(k as "balance" | "recharge")}
          size="small"
          items={[
            {
              key: "balance",
              label: "余额",
              children: (
                <div>
                  <Descriptions column={1} size="small" bordered style={{ marginBottom: 12 }}>
                    <Descriptions.Item label="总余额">
                      <Text strong style={{ fontSize: 16 }}>¥{fmtAmt(data.wallet.balance)}</Text>
                    </Descriptions.Item>
                    <Descriptions.Item label="累计充值">
                      ¥{fmtAmt(data.wallet.total_recharged)}
                    </Descriptions.Item>
                    <Descriptions.Item label="累计提现">
                      ¥{fmtAmt(data.wallet.total_withdrawn)}
                    </Descriptions.Item>
                    <Descriptions.Item label="客户状态">
                      {data.customer.lifecycle_status === "active" ? "活跃" :
                       data.customer.lifecycle_status === "blacklisted" ? "已拉黑" :
                       data.customer.lifecycle_status === "frozen" ? "已冻结" : data.customer.lifecycle_status}
                    </Descriptions.Item>
                    <Descriptions.Item label="注册时间">
                      {fmt(data.customer.created_at)}
                    </Descriptions.Item>
                  </Descriptions>
                </div>
              ),
            },
            {
              key: "recharge",
              label: "流水",
              children: (
                <div>
                  {data.wallet.recent_transactions.length === 0 ? (
                    <Text type="secondary">暂无交易记录</Text>
                  ) : (
                    data.wallet.recent_transactions.map((tx, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          padding: "6px 0",
                          borderBottom: "1px solid #f0f0f0",
                          fontSize: 12,
                        }}
                      >
                        <div>
                          <Text>{TYPE_LABEL[tx.type] ?? tx.type}</Text>
                          <Text type="secondary" style={{ marginLeft: 8, fontSize: 11 }}>
                            {fmt(tx.created_at)}
                          </Text>
                        </div>
                        <Text style={{ color: DIR_COLOR[tx.direction] ?? "#333", fontWeight: 500 }}>
                          {DIR_MAP[tx.direction] ?? ""}¥{fmtAmt(tx.amount)}
                        </Text>
                      </div>
                    ))
                  )}
                </div>
              ),
            },
          ]}
        />
      )}
    </Drawer>
  );
}
