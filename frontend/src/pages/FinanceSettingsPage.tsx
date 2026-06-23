import { type JSX } from "react";
import { Tabs } from "antd";
import { PaymentChannelPage } from "./PaymentChannelPage";
import { ExchangeRatePage } from "./ExchangeRatePage";
import { AIBillingPage } from "./AIBillingPage";
import { PageShell } from "../components/PageShell";
import { usePermissions } from "../hooks/usePermissions";

export function FinanceSettingsPage(): JSX.Element {
  const { can } = usePermissions();
  const canViewChannels = can("finance.view_channels") || can("finance.edit_channels");
  const canViewRates = can("exchange_rate.view") || can("exchange_rate.edit");
  const canViewAIBilling =
    can("ai_billing.view_rates") ||
    can("ai_billing.view_usage") ||
    can("ai_billing.view_bills") ||
    can("ai_billing.view_quotas");
  const tabItems = [
    ...(canViewChannels ? [{ key: "channels", label: "支付渠道", children: <PaymentChannelPage embedded /> }] : []),
    ...(canViewRates ? [{ key: "rates", label: "汇率管理", children: <ExchangeRatePage embedded /> }] : []),
    ...(canViewAIBilling ? [{ key: "ai-billing", label: "AI & 翻译费用", children: <AIBillingPage embedded /> }] : []),
  ].filter(Boolean);

  return (
    <PageShell title="财务设置" subtitle="管理支付渠道、汇率和 AI 费用">
      <Tabs defaultActiveKey={tabItems[0]?.key ?? "rates"} items={tabItems} />
    </PageShell>
  );
}
