import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TaskAmountAllocationPreview } from "./TaskAmountAllocationPreview";
import { TaskInstanceDetailDrawer } from "./TaskInstanceDetailDrawer";
import { TaskIssuePlanEditor } from "./TaskIssuePlanEditor";
import { TaskManualAddDrawer } from "./TaskManualAddDrawer";
import { TaskProductPoolEditor } from "./TaskProductPoolEditor";
import { TaskSystemConfigPanel } from "./TaskSystemConfigPanel";

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Button = ({
    children,
    onClick,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
  }) => React.createElement("button", { onClick }, children);
  const Input = ({ addonBefore: _addonBefore, ...props }: Record<string, unknown>) => React.createElement("input", props);
  Input.TextArea = (props: Record<string, unknown>) => React.createElement("textarea", props);
  const InputNumber = (props: Record<string, unknown>) => React.createElement("input", props);
  const Select = ({ allowClear: _allowClear, ...props }: Record<string, unknown>) => React.createElement("select", props);
  const Table = ({ dataSource = [] }: { dataSource?: Array<Record<string, unknown>> }) =>
    React.createElement("div", null, dataSource.map((row) => React.createElement("div", { key: String(row.id) }, JSON.stringify(row))));
  const Typography = {
    Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
  };
  const Modal = ({ children, title, open }: { children?: React.ReactNode; title?: React.ReactNode; open?: boolean }) =>
    open ? React.createElement("div", null, title, children) : null;
  return { Button, Empty: Wrapper, Input, InputNumber, Modal, Select, Space: Wrapper, Table, Typography };
});

describe("task support components", () => {
  it("renders quota amount allocation preview items and total", () => {
    render(<TaskAmountAllocationPreview amounts={["100.00", "120.00"]} total="220.00" />);

    expect(screen.getByText("1/2: 100.00")).toBeTruthy();
    expect(screen.getByText("2/2: 120.00")).toBeTruthy();
    expect(screen.getByText("Total: 220.00")).toBeTruthy();
  });

  it("renders task system config panel with settings and audit logs", () => {
    render(
      <TaskSystemConfigPanel
        accountOptions={[{ label: "Account 1", value: "acct-1" }]}
        settingsAccountId="acct-1"
        settingsSiteId="site-1"
        settingsSiteOptions={[{ label: "Site 1", value: "site-1" }]}
        taskSystemConfig={{
          accountId: "acct-1",
          siteId: "site-1",
          status: "active",
          whatsappBindingRewardEnabled: true,
          whatsappBindingRewardAmount: "20.00",
          whatsappBindingRewardWalletType: "task_balance",
          whatsappBindingRewardCurrency: "USD",
          certifiedMemberEnabled: true,
          certifiedRechargeThreshold: "50.00",
          certifiedRechargeScope: "real_recharge",
          autoCertifyOnRecharge: true,
          newbieTaskEnabled: true,
          newbiePlanId: "plan-1",
          newbieAutoPopup: true,
          officialPlanId: "plan-2",
          showTaskBalanceTransferPrompt: true,
          minTaskBalanceTransferPromptAmount: "5.00",
          maxActiveBatchesPerUser: 1,
          maxActivePackagesPerUser: 1,
          metadataJson: null,
          createdAt: null,
          updatedAt: null,
        }}
        taskSystemConfigAuditLogs={[
          {
            id: "audit-1",
            account_id: "acct-1",
            actor_type: "staff",
            actor_id: "staff-1",
            action: "task_config_saved",
            target_type: "task_config",
            target_id: "site-1",
            payload: {},
            created_at: "2026-06-28T00:00:00Z",
          },
        ]}
        issuePlanOptions={[
          { label: "Plan 1", value: "plan-1" },
          { label: "Plan 2", value: "plan-2" },
        ]}
        error={null}
        saving={false}
        onAccountChange={() => undefined}
        onSiteChange={() => undefined}
        onSave={() => undefined}
        onUpdateConfig={() => undefined}
        formatDate={(value) => value ?? "-"}
      />,
    );

    expect(screen.getByText("系统设置")).toBeTruthy();
    expect(screen.getByText("Recent Audit Logs")).toBeTruthy();
    expect(screen.getByText("保存设置")).toBeTruthy();
  });

  it("renders extracted task editors and drawers", () => {
    render(
      <>
        <TaskIssuePlanEditor
          accountOptions={[{ label: "Account 1", value: "acct-1" }]}
          filterAccount="acct-1"
          onFilterAccountChange={() => undefined}
          onCreate={() => undefined}
          error={null}
          plans={[{
            id: "plan-1",
            account_id: "acct-1",
            site_id: "site-1",
            name: "Plan 1",
            plan_type: "official",
            claim_gate: "certified_member",
            issue_anchor: "certified_at",
            issue_mode: "calendar_day",
            require_previous_batch_completed: true,
            max_unfinished_batches: 1,
            after_last_rule_mode: "stop",
            growth_package_count_step: 0,
            growth_amount_step: null,
            default_product_pool_id: "pool-1",
            default_tolerance_amount: "0.00",
            default_reward_ratio: "0.20",
            day_rules: [],
            status: "active",
            metadata_json: null,
            created_at: "2026-06-28T00:00:00Z",
            updated_at: "2026-06-28T00:00:00Z",
          }]}
          columns={[{ title: "Name", dataIndex: "name", key: "name" }]}
          loading={false}
        />
        <TaskProductPoolEditor
          accountOptions={[{ label: "Account 1", value: "acct-1" }]}
          filterAccount="acct-1"
          onFilterAccountChange={() => undefined}
          onCreate={() => undefined}
          error={null}
          productPools={[{
            id: "pool-1",
            accountId: "acct-1",
            siteId: "site-1",
            name: "Pool 1",
            code: "pool-1",
            poolType: "default",
            priceMode: "task_price_snapshot",
            allowRepeatInSameBatch: false,
            allowRepeatInSamePackage: false,
            status: "active",
            currency: "USD",
            itemCount: 1,
            items: [],
            metadataJson: null,
            createdAt: "2026-06-28T00:00:00Z",
            updatedAt: "2026-06-28T00:00:00Z",
          }]}
          columns={[{ title: "Name", dataIndex: "name", key: "name" }]}
          loading={false}
        />
        <TaskInstanceDetailDrawer
          open
          loading={false}
          detail={{
            id: "pkg-1",
            batch_id: "batch-1",
            day_no: 1,
            batch_index: 1,
            batch_total: 5,
            progress_label: "1/5",
            day_planned_amount: 300,
            day_system_generated_amount: 260,
            day_manual_added_amount: 40,
            day_effective_amount: 300,
            planned_amount: 100,
            system_generated_amount: 100,
            manual_added_amount: 20,
            effective_amount: 120,
            reward_ratio: 0.2,
            estimated_reward_amount: 24,
            status: "active",
            claimed_at: null,
            completed_at: null,
            items: [{
              id: "item-1",
              product_name: "Item 1",
              image_url: null,
              price: 100,
              currency: "USD",
              origin: "system_generated",
              status: "pending",
              completed_at: null,
              order_id: null,
            }],
            manual_add_logs: [{
              id: "log-1",
              package_id: "pkg-1",
              batch_id: "batch-1",
              operator_id: "staff-1",
              reason_text: "top up",
              notify_user: true,
              user_notice_text: "已记录后台通知",
              user_notified_at: "2026-06-28T00:05:00Z",
              added_item_count: 1,
              added_amount: 20,
              before_manual_added_amount: 0,
              after_manual_added_amount: 20,
              before_effective_amount: 100,
              after_effective_amount: 120,
              created_at: "2026-06-28T00:00:00Z",
            }],
          }}
          onClose={() => undefined}
          formatMoney={(value) => String(value ?? "-")}
          itemColumns={[{ title: "Product Name", dataIndex: "product_name", key: "product_name" }]}
          logColumns={[{ title: "Reason", dataIndex: "reason_text", key: "reason_text" }]}
        />
        <TaskManualAddDrawer
          open
          loading={false}
          submitting={false}
          previewLoading={false}
          candidates={[{ id: "cand-1", product_id: "p-1", product_name: "Candidate 1", image_url: null, price: 30, currency: "USD" }]}
          selectedIds={["cand-1"]}
          reason="Need top up"
          userNoticeText="后台记录已通知用户"
          preview={{
            package_id: "pkg-1",
            candidate_count: 1,
            added_item_count: 1,
            added_amount: 30,
            package_planned_amount: 100,
            package_system_generated_amount: 100,
            package_manual_added_amount_before: 20,
            package_manual_added_amount_after: 50,
            package_effective_amount_before: 120,
            package_effective_amount_after: 150,
            reward_ratio: 0.2,
            estimated_reward_amount_before: 24,
            estimated_reward_amount_after: 30,
            items: [],
          }}
          onClose={() => undefined}
          onSubmit={() => undefined}
          onReasonChange={() => undefined}
          onNotifyUserChange={() => undefined}
          onUserNoticeTextChange={() => undefined}
          onToggleCandidate={() => undefined}
          onPreview={() => undefined}
          formatMoney={(value) => String(value ?? "-")}
          columns={[{ title: "Product Name", dataIndex: "product_name", key: "product_name" }]}
        />
      </>,
    );

    expect(screen.getByText("New Issue Plan")).toBeTruthy();
    expect(screen.getByText("New Product Pool")).toBeTruthy();
    expect(screen.getByText("Package Detail")).toBeTruthy();
    expect(screen.getAllByText("Preview Manual Add Impact").length).toBeGreaterThan(0);
    expect(screen.getByText("Day Planned Amount: 300")).toBeTruthy();
    expect(screen.getByText("Day Effective Amount: 300")).toBeTruthy();
    expect(screen.getAllByText("Package Planned Amount: 100")).toHaveLength(2);
    expect(screen.getAllByText("Reward Ratio: 0.2")).toHaveLength(2);
    expect(screen.queryByText("Record user notice")).toBeNull();
    expect(screen.queryByPlaceholderText("Optional notice note kept in backend records")).toBeNull();
  });
});
