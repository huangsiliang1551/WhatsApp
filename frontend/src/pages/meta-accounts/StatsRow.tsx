import { Card, Col, Row, Typography } from "antd";
import type { MetaWabaAccount } from "../../services/api";

interface StatsRowProps {
  accounts: MetaWabaAccount[];
}

export function StatsRow({ accounts }: StatsRowProps) {
  const totalWabas = accounts.length;
  const totalPhones = accounts.reduce((s, a) => s + a.phone_number_count, 0);
  const readyCount = accounts.filter((a) => a.ready_for_outbound_messages).length;
  const whAbnormal = accounts.filter(
    (a) => a.webhook_runtime_status && a.webhook_runtime_status !== "healthy"
  ).length;

  const cards = [
    { label: "WABA 总数", value: totalWabas, color: "#1677ff" },
    { label: "号码总数", value: totalPhones, color: "#722ed1" },
    { label: "出站就绪", value: readyCount, color: "#52c41a" },
    { label: "Webhook 异常", value: whAbnormal, color: whAbnormal > 0 ? "#ff4d4f" : "#52c41a" },
  ];

  return (
    <Row gutter={8} style={{ marginBottom: 8 }}>
      {cards.map((c) => (
        <Col key={c.label} span={6}>
          <Card size="small" bodyStyle={{ padding: "8px 12px" }}>
            <div style={{ fontSize: 11, color: "#999" }}>{c.label}</div>
            <Typography.Text strong style={{ fontSize: 18, color: c.color }}>
              {c.value}
            </Typography.Text>
          </Card>
        </Col>
      ))}
    </Row>
  );
}
