import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildTaskIssuePlanCreatePayload,
  buildTaskQuotaBatchCreatePayload,
  buildTaskQuotaBatchPreviewSummary,
  buildTaskQuotaCreatePayload,
  TASK_AMOUNT_ALLOCATION_MODE_OPTIONS,
  TASK_PLAN_AFTER_LAST_RULE_MODE_OPTIONS,
  TASK_PLAN_CLAIM_GATE_OPTIONS,
  TASK_PLAN_ISSUE_ANCHOR_OPTIONS,
  TASK_PLAN_ISSUE_MODE_OPTIONS,
  TASK_PRODUCT_COUNT_MODE_OPTIONS,
  TasksPage,
} from "./TasksPage";

const hoisted = vi.hoisted(() => ({
  storeState: {} as Record<string, unknown>,
  listTaskTemplatesMock: vi.fn(),
  listTaskInstancesMock: vi.fn(),
  listTaskPackagesMock: vi.fn(),
  listTaskGenerationRunsMock: vi.fn(),
  listTaskMonitorRowsMock: vi.fn(),
  getTaskMonitorSummaryMock: vi.fn(),
  listTaskMonitorAlertEventsMock: vi.fn(),
  acknowledgeTaskMonitorAlertEventMock: vi.fn(),
  resolveTaskMonitorAlertEventMock: vi.fn(),
  listTaskMonitorSavedViewsMock: vi.fn(),
  createTaskMonitorSavedViewMock: vi.fn(),
  updateTaskMonitorSavedViewMock: vi.fn(),
  deleteTaskMonitorSavedViewMock: vi.fn(),
  listTaskAlertRulesMock: vi.fn(),
  createTaskAlertRuleMock: vi.fn(),
  updateTaskAlertRuleMock: vi.fn(),
  deleteTaskAlertRuleMock: vi.fn(),
  listTaskIssuePlansMock: vi.fn(),
  createTaskIssuePlanMock: vi.fn(),
  enableTaskIssuePlanMock: vi.fn(),
  disableTaskIssuePlanMock: vi.fn(),
  getTaskSystemConfigMock: vi.fn(),
  patchTaskSystemConfigMock: vi.fn(),
  listTaskSystemConfigAuditLogsMock: vi.fn(),
  listTaskQuotasMock: vi.fn(),
  previewTaskQuotaAllocationMock: vi.fn(),
  createTaskQuotaMock: vi.fn(),
  batchCreateTaskQuotasMock: vi.fn(),
  previewBatchTaskQuotasMock: vi.fn(),
  generateTaskQuotaBatchMock: vi.fn(),
  listTaskProductPoolsMock: vi.fn(),
  createTaskProductPoolMock: vi.fn(),
  addTaskProductPoolItemsMock: vi.fn(),
  deleteTaskProductPoolItemMock: vi.fn(),
  getTaskPackageDetailMock: vi.fn(),
  listTaskManualAddLogsMock: vi.fn(),
  listTaskPackageManualAddCandidatesMock: vi.fn(),
  previewTaskPackageManualAddMock: vi.fn(),
  createTaskPackageManualAddMock: vi.fn(),
  pauseNextTaskPackageQuotaMock: vi.fn(),
  retryTaskGenerationRunMock: vi.fn(),
  pauseTaskPackageMock: vi.fn(),
  resumeTaskPackageMock: vi.fn(),
  cancelTaskPackageMock: vi.fn(),
  listMetaAccountsMock: vi.fn(),
  createTaskTemplateMock: vi.fn(),
  approveTaskReviewMock: vi.fn(),
  rejectTaskReviewMock: vi.fn(),
  listPlatformUserMemberStatusIndexMock: vi.fn(),
  listSitesMock: vi.fn(),
  realtimeConnectMock: vi.fn(),
  realtimeDisconnectMock: vi.fn(),
  latestRealtimeOptions: null as null | Record<string, unknown>,
  playAlertSoundMock: vi.fn(),
  showErrorMock: vi.fn(),
  showSuccessMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  listTaskTemplates: hoisted.listTaskTemplatesMock,
  listTaskInstances: hoisted.listTaskInstancesMock,
  listTaskPackages: hoisted.listTaskPackagesMock,
  listTaskGenerationRuns: hoisted.listTaskGenerationRunsMock,
  listTaskMonitorRows: hoisted.listTaskMonitorRowsMock,
  getTaskMonitorSummary: hoisted.getTaskMonitorSummaryMock,
  listTaskMonitorAlertEvents: hoisted.listTaskMonitorAlertEventsMock,
  acknowledgeTaskMonitorAlertEvent: hoisted.acknowledgeTaskMonitorAlertEventMock,
  resolveTaskMonitorAlertEvent: hoisted.resolveTaskMonitorAlertEventMock,
  listTaskMonitorSavedViews: hoisted.listTaskMonitorSavedViewsMock,
  createTaskMonitorSavedView: hoisted.createTaskMonitorSavedViewMock,
  updateTaskMonitorSavedView: hoisted.updateTaskMonitorSavedViewMock,
  deleteTaskMonitorSavedView: hoisted.deleteTaskMonitorSavedViewMock,
  listTaskAlertRules: hoisted.listTaskAlertRulesMock,
  createTaskAlertRule: hoisted.createTaskAlertRuleMock,
  updateTaskAlertRule: hoisted.updateTaskAlertRuleMock,
  deleteTaskAlertRule: hoisted.deleteTaskAlertRuleMock,
  listTaskIssuePlans: hoisted.listTaskIssuePlansMock,
  createTaskIssuePlan: hoisted.createTaskIssuePlanMock,
  enableTaskIssuePlan: hoisted.enableTaskIssuePlanMock,
  disableTaskIssuePlan: hoisted.disableTaskIssuePlanMock,
  getTaskSystemConfig: hoisted.getTaskSystemConfigMock,
  patchTaskSystemConfig: hoisted.patchTaskSystemConfigMock,
  listTaskSystemConfigAuditLogs: hoisted.listTaskSystemConfigAuditLogsMock,
  listTaskQuotas: hoisted.listTaskQuotasMock,
  previewTaskQuotaAllocation: hoisted.previewTaskQuotaAllocationMock,
  createTaskQuota: hoisted.createTaskQuotaMock,
  batchCreateTaskQuotas: hoisted.batchCreateTaskQuotasMock,
  previewBatchTaskQuotas: hoisted.previewBatchTaskQuotasMock,
  generateTaskQuotaBatch: hoisted.generateTaskQuotaBatchMock,
  listTaskProductPools: hoisted.listTaskProductPoolsMock,
  createTaskProductPool: hoisted.createTaskProductPoolMock,
  addTaskProductPoolItems: hoisted.addTaskProductPoolItemsMock,
  deleteTaskProductPoolItem: hoisted.deleteTaskProductPoolItemMock,
  getTaskPackageDetail: hoisted.getTaskPackageDetailMock,
  listTaskManualAddLogs: hoisted.listTaskManualAddLogsMock,
  listTaskPackageManualAddCandidates: hoisted.listTaskPackageManualAddCandidatesMock,
  previewTaskPackageManualAdd: hoisted.previewTaskPackageManualAddMock,
  createTaskPackageManualAdd: hoisted.createTaskPackageManualAddMock,
  pauseNextTaskPackageQuota: hoisted.pauseNextTaskPackageQuotaMock,
  retryTaskGenerationRun: hoisted.retryTaskGenerationRunMock,
  pauseTaskPackage: hoisted.pauseTaskPackageMock,
  resumeTaskPackage: hoisted.resumeTaskPackageMock,
  cancelTaskPackage: hoisted.cancelTaskPackageMock,
  listMetaAccounts: hoisted.listMetaAccountsMock,
  createTaskTemplate: hoisted.createTaskTemplateMock,
  approveTaskReview: hoisted.approveTaskReviewMock,
  rejectTaskReview: hoisted.rejectTaskReviewMock,
}));

vi.mock("../services/operations", () => ({
  listPlatformUserMemberStatusIndex: hoisted.listPlatformUserMemberStatusIndexMock,
}));

vi.mock("../services/h5MultiTenantApi", () => ({
  listSites: hoisted.listSitesMock,
}));

vi.mock("../stores/appStore", () => ({
  useAppStore: (selector: (state: Record<string, unknown>) => unknown) => selector(hoisted.storeState),
}));

vi.mock("../services/taskMonitorAlertRealtime", () => ({
  taskMonitorAlertRealtime: {
    connect: (options: Record<string, unknown>) => {
      hoisted.latestRealtimeOptions = options;
      hoisted.realtimeConnectMock(options);
    },
    disconnect: () => {
      hoisted.realtimeDisconnectMock();
    },
  },
}));

vi.mock("../services/taskMonitorAlertSound", () => ({
  playTaskMonitorAlertSound: () => {
    hoisted.playAlertSoundMock();
  },
}));

vi.mock("../components/member/MemberIdLink", async () => {
  const React = await import("react");
  return {
    MemberIdLink: ({
      accountId,
      userId,
      publicUserId,
      label,
    }: {
      accountId?: string | null;
      userId?: string | null;
      publicUserId?: string | null;
      label?: string | null;
    }) => React.createElement(
      "span",
      null,
      `member-link:${label ?? ""}:${userId ?? ""}:${publicUserId ?? ""}:${accountId ?? ""}`,
    ),
  };
});

vi.mock("antd", async () => {
  const React = await import("react");
  const Wrapper = ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children);
  const Button = ({ children, onClick, loading }: { children?: React.ReactNode; onClick?: () => void; loading?: boolean }) =>
    React.createElement("button", { type: "button", onClick, disabled: loading }, children);
  const Checkbox = ({
    children,
    checked,
    onChange,
  }: {
    children?: React.ReactNode;
    checked?: boolean;
    onChange?: (event: { target: { checked: boolean } }) => void;
  }) => React.createElement(
    "label",
    null,
    React.createElement("input", {
      type: "checkbox",
      checked,
      onChange: (event: Event) => onChange?.({ target: { checked: (event.target as HTMLInputElement).checked } }),
    }),
    children,
  );
  const Tag = ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children);
  const Typography = {
    Text: ({ children }: { children?: React.ReactNode }) => React.createElement("span", null, children),
  };
  type MockFormInstance = {
    resetFields: ReturnType<typeof vi.fn>;
    submit: ReturnType<typeof vi.fn>;
    getFieldsValue: ReturnType<typeof vi.fn>;
    __bindOnFinish: (handler?: (values: Record<string, unknown>) => unknown) => void;
  };
  const createMockFormInstance = (): MockFormInstance => {
    let onFinish: ((values: Record<string, unknown>) => unknown) | undefined;
    const instance: MockFormInstance = {
      resetFields: vi.fn(),
      submit: vi.fn(() => onFinish?.(instance.getFieldsValue())),
      getFieldsValue: vi.fn(() => ({
        account_id: "acct-1",
        user_id: "user-4",
        site_id: "site-1",
        day_no: 3,
        package_count: 3,
        day_total_amount: 300,
        product_pool_id: "pool-1",
        product_count_min: 1,
        product_count_max: 3,
        reward_ratio: 0.2,
        product_id: "prod-new",
        product_name: "New Product",
        price: 88,
        currency: "USD",
        product_description: "New description",
      })),
      __bindOnFinish: (handler) => {
        onFinish = handler;
      },
    };
    return instance;
  };
  const Form = (({
    children,
    form,
    onFinish,
  }: {
    children?: React.ReactNode;
    form?: MockFormInstance;
    onFinish?: (values: Record<string, unknown>) => unknown;
  }) => {
    form?.__bindOnFinish(onFinish);
    return React.createElement("form", null, children);
  }) as typeof Wrapper & { useForm: () => Array<MockFormInstance>; Item?: typeof Wrapper };
  Form.useForm = () => [createMockFormInstance()];
  Form.Item = Wrapper;
  const Table = ({
    dataSource = [],
    columns = [],
  }: {
    dataSource?: Array<Record<string, unknown>>;
    columns?: Array<{
      key?: string;
      dataIndex?: string;
      render?: (value: unknown, record: Record<string, unknown>, index: number) => React.ReactNode;
    }>;
  }) =>
    React.createElement(
      "div",
      null,
      [
        ...columns.map((column, columnIndex) =>
          React.createElement(
            "div",
            { key: `title-${String(column.key ?? column.dataIndex ?? columnIndex)}` },
            String(column.key === "actions" ? column.key && "Actions" : (column as { title?: string }).title ?? ""),
          ),
        ),
        ...dataSource.flatMap((record, index) =>
          columns.map((column, columnIndex) =>
            React.createElement(
              "div",
              { key: `${String(column.key ?? column.dataIndex ?? columnIndex)}-${index}` },
              column.render
                ? column.render(column.dataIndex ? record[column.dataIndex] : undefined, record, index)
                : column.dataIndex
                  ? String(record[column.dataIndex] ?? "")
                  : null,
            ),
          ),
        ),
      ],
    );
  const Select = ({
    value,
    onChange,
    options = [],
    "data-testid": dataTestId,
  }: {
    value?: string;
    onChange?: (value: string | undefined) => void;
    options?: Array<{ label: string; value: string }>;
    "data-testid"?: string;
  }) => {
    const normalizedValue = typeof value === "string" ? value : "";
    return (
    React.createElement(
      "select",
      {
        value: normalizedValue,
        onChange: (event: Event) => {
          const nextValue = (event.target as HTMLSelectElement).value;
          onChange?.(nextValue || undefined);
        },
        "data-testid": dataTestId,
      },
      [
        React.createElement("option", { key: "__empty__", value: "" }, ""),
        ...options.map((option) =>
          React.createElement("option", { key: option.value, value: option.value }, option.label),
        ),
      ],
    ));
  };

  return {
    Button,
    Checkbox,
    Empty: Wrapper,
    Form,
    Input: Object.assign(({
      addonBefore: _addonBefore,
      allowClear: _allowClear,
      ...props
    }: Record<string, unknown>) => React.createElement("input", props), {
      TextArea: (props: Record<string, unknown>) => React.createElement("textarea", props),
    }),
    InputNumber: (props: Record<string, unknown>) => React.createElement("input", props),
    Modal: ({
      children,
      title,
      open = true,
      onOk,
      onCancel,
      okText,
      cancelText,
    }: {
      children?: React.ReactNode;
      title?: React.ReactNode;
      open?: boolean;
      onOk?: () => void;
      onCancel?: () => void;
      okText?: React.ReactNode;
      cancelText?: React.ReactNode;
    }) =>
      open
        ? React.createElement(
            "div",
            null,
            title,
            children,
            cancelText ? React.createElement("button", { onClick: onCancel }, cancelText) : null,
            okText ? React.createElement("button", { onClick: onOk }, okText) : null,
          )
        : null,
    Select,
    Space: Wrapper,
    Table,
    Tabs: ({ items }: { items?: Array<{ children?: React.ReactNode }> }) =>
      React.createElement("div", null, items?.map((item, index) => React.createElement("div", { key: index }, item.children))),
    Tag,
    Typography,
  };
});

vi.mock("@ant-design/icons", () => ({
  PlusOutlined: () => null,
  ReloadOutlined: () => null,
  SearchOutlined: () => null,
}));

vi.mock("../components/PageShell", async () => {
  const React = await import("react");
  return {
    PageShell: ({ children, stats, actions }: { children?: React.ReactNode; stats?: React.ReactNode; actions?: React.ReactNode }) =>
      React.createElement("div", null, stats, actions, children),
  };
});

vi.mock("../components/Feedback", () => ({
  showError: hoisted.showErrorMock,
  showSuccess: hoisted.showSuccessMock,
}));

vi.mock("../utils/withSorter", () => ({
  withSorter: <T,>(columns: T): T => columns,
}));

const mountedContainers: HTMLDivElement[] = [];
const mountedRoots: Root[] = [];

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderPage(element: ReturnType<typeof createElement>): Promise<void> {
  const container = document.createElement("div");
  document.body.appendChild(container);
  mountedContainers.push(container);
  const root = createRoot(container);
  mountedRoots.push(root);
  await act(async () => {
    root.render(element);
  });
  await flushEffects();
}

describe("TasksPage", () => {
  beforeEach(() => {
    hoisted.storeState = {
      openCustomersPage: vi.fn(),
    };
    hoisted.listSitesMock.mockReset().mockResolvedValue([]);
    hoisted.listMetaAccountsMock.mockReset().mockResolvedValue([]);
    hoisted.listTaskTemplatesMock.mockReset().mockResolvedValue([
      { id: "tpl-1", task_key: "key-1", name: "模板 A", task_type: "daily", status: "active", reward_amount: "10", created_at: "2026-06-24T00:00:00Z" },
    ]);
    hoisted.listTaskInstancesMock.mockReset().mockImplementation(async (params?: { status?: string }) => {
      if (params?.status === "submitted") {
        return [
          { id: "task-review-1", account_id: "acct-1", template_name: "任务审核", user_id: "user-2", public_user_id: "pub-u2", status: "submitted", submitted_at: "2026-06-24T00:00:00Z" },
        ];
      }
      return [
        { id: "task-1", account_id: "acct-1", template_name: "任务 A", user_id: "user-1", public_user_id: "pub-u1", status: "claimed", available_at: "2026-06-24T00:00:00Z", site_key: null },
      ];
    });
    hoisted.listTaskPackagesMock.mockReset().mockResolvedValue([
      {
        id: "pkg-1",
        account_id: "acct-1",
        user_id: "user-3",
        public_user_id: "pub-u3",
        site_id: "site-1",
        site_key: "site-cn",
        batch_id: "batch-1",
        day_no: 1,
        batch_index: 1,
        batch_total: 5,
        progress_label: "1/5",
        status: "active",
        planned_amount: 100,
        system_generated_amount: 100,
        manual_added_amount: 50,
        effective_amount: 150,
        estimated_reward_amount: 15,
        has_manual_add: true,
        claimed_at: "2026-06-24T00:00:00Z",
        completed_at: null,
      },
    ]);
    hoisted.listTaskGenerationRunsMock.mockReset().mockResolvedValue([
      {
        id: "run-1",
        account_id: "acct-1",
        site_id: "site-1",
        site_key: "site-cn",
        user_id: "user-3",
        public_user_id: "pub-u3",
        quota_id: "quota-1",
        batch_id: "batch-1",
        product_pool_id: "pool-1",
        selection_algorithm: "weighted_random_unique_v1",
        target_day_amount: 100,
        actual_day_system_amount: 98,
        tolerance_amount: 5,
        generated_package_count: 3,
        generated_item_count: 7,
        status: "success",
        failure_reason: null,
        created_at: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.listTaskMonitorRowsMock.mockReset().mockResolvedValue([
      {
        package_id: "pkg-1",
        account_id: "acct-1",
        user_id: "user-3",
        public_user_id: "pub-u3",
        site_id: "site-1",
        site_key: "site-cn",
        batch_id: "batch-1",
        day_no: 1,
        progress_label: "1/5",
        status: "active",
        current_item_index: 2,
        planned_amount: 100,
        system_generated_amount: 100,
        manual_added_amount: 50,
        effective_amount: 150,
        has_manual_add: true,
        day_planned_amount: 300,
        day_system_generated_amount: 250,
        day_manual_added_amount: 50,
        day_effective_amount: 300,
        manual_added_item_count: 2,
        latest_manual_add_operator_id: "operator-h5-member-auth",
        latest_manual_add_at: "2026-06-24T06:00:00Z",
        current_product_amount: 30,
        current_product_origin: "system_generated",
        total_real_recharge_amount: 120,
        total_withdraw_amount: 20,
        estimated_reward_amount: 15,
        claimed_at: "2026-06-24T00:00:00Z",
        completed_at: null,
      },
    ]);
    hoisted.getTaskMonitorSummaryMock.mockReset().mockResolvedValue({
      total_count: 1,
      manual_add_count: 1,
      total_planned_amount: 100,
      total_manual_added_amount: 50,
      total_effective_amount: 150,
      total_real_recharge_amount: 120,
      total_withdraw_amount: 20,
    });
    hoisted.listTaskMonitorAlertEventsMock.mockReset().mockResolvedValue([
      {
        id: "evt-1",
        account_id: "acct-1",
        alert_rule_id: "alert-1",
        package_id: "pkg-1",
        user_id: "user-3",
        public_user_id: "pub-u3",
        status: "open",
        priority: "high",
        rule_name: "High Amount Alert",
        current_value: 150,
        threshold_value: 130,
        sound_enabled: true,
        triggered_at: "2026-06-24T00:00:00Z",
        acknowledged_at: null,
        acknowledged_by: null,
        resolved_at: null,
        resolved_by: null,
      },
    ]);
    hoisted.acknowledgeTaskMonitorAlertEventMock.mockReset().mockResolvedValue(undefined);
    hoisted.resolveTaskMonitorAlertEventMock.mockReset().mockResolvedValue(undefined);
    hoisted.listTaskMonitorSavedViewsMock.mockReset().mockResolvedValue([
      {
        id: "view-1",
        account_id: "acct-1",
        owner_staff_id: "staff-1",
        name: "High Risk Tasks",
        filter_json: { risk_tag: "high" },
        sort_json: [{ field: "actual_day_amount", order: "desc" }],
        columns_json: ["public_user_id", "task_balance"],
        refresh_seconds: 15,
        sound_enabled: true,
        is_default: true,
        created_at: "2026-06-24T00:00:00Z",
        updated_at: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.createTaskMonitorSavedViewMock.mockReset().mockResolvedValue(undefined);
    hoisted.updateTaskMonitorSavedViewMock.mockReset().mockResolvedValue(undefined);
    hoisted.deleteTaskMonitorSavedViewMock.mockReset().mockResolvedValue(undefined);
    hoisted.listTaskAlertRulesMock.mockReset().mockResolvedValue([
      {
        id: "alert-1",
        account_id: "acct-1",
        name: "High Amount Alert",
        status: "active",
        condition_json: { field: "actual_day_amount", operator: ">=", value: 2000 },
        action_json: { notify_staff: true },
        sound_enabled: true,
        priority: "high",
        created_by: "admin-1",
        metadata_json: null,
        created_at: "2026-06-24T00:00:00Z",
        updated_at: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.createTaskAlertRuleMock.mockReset().mockResolvedValue(undefined);
    hoisted.updateTaskAlertRuleMock.mockReset().mockResolvedValue(undefined);
    hoisted.deleteTaskAlertRuleMock.mockReset().mockResolvedValue(undefined);
    hoisted.listTaskIssuePlansMock.mockReset().mockResolvedValue([
      {
        id: "plan-1",
        account_id: "acct-1",
        site_id: "site-1",
        name: "Official Growth Plan",
        plan_type: "official",
        status: "active",
        claim_gate: "certified_member",
        issue_anchor: "certified_at",
        issue_mode: "calendar_day",
        require_previous_batch_completed: true,
        max_unfinished_batches: 1,
        after_last_rule_mode: "arithmetic_growth",
        growth_package_count_step: 2,
        growth_amount_step: "80.00",
        default_product_pool_id: "pool-1",
        default_tolerance_amount: "10.00",
        default_reward_ratio: "0.20",
        metadata_json: null,
        day_rules: [
          {
            id: "rule-1",
            account_id: "acct-1",
            site_id: "site-1",
            plan_id: "plan-1",
            day_no: 1,
            package_count: 3,
            day_total_amount: "300.00",
            tolerance_amount: "10.00",
            amount_allocation_mode: "average",
            package_amounts_json: ["100.00", "100.00", "100.00"],
            product_pool_id: "pool-1",
            product_count_mode: "range",
            product_count_fixed: null,
            product_count_min: 1,
            product_count_max: 3,
            reward_ratio: "0.20",
            issue_time_of_day: "10:00",
            elapsed_delay_hours: null,
            status: "active",
            metadata_json: null,
            created_at: "2026-06-24T00:00:00Z",
            updated_at: "2026-06-24T00:00:00Z",
          },
        ],
        created_at: "2026-06-24T00:00:00Z",
        updated_at: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.createTaskIssuePlanMock.mockReset().mockResolvedValue(undefined);
    hoisted.enableTaskIssuePlanMock.mockReset().mockResolvedValue(undefined);
    hoisted.disableTaskIssuePlanMock.mockReset().mockResolvedValue(undefined);
    hoisted.getTaskSystemConfigMock.mockReset().mockResolvedValue({
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
      newbiePlanId: "plan-newbie",
      newbieAutoPopup: true,
      officialPlanId: "plan-1",
      showTaskBalanceTransferPrompt: true,
      minTaskBalanceTransferPromptAmount: "0.01",
      maxActiveBatchesPerUser: 1,
      maxActivePackagesPerUser: 1,
      metadataJson: null,
      createdAt: null,
      updatedAt: null,
    });
    hoisted.patchTaskSystemConfigMock.mockReset().mockResolvedValue(undefined);
    hoisted.listTaskSystemConfigAuditLogsMock.mockReset().mockResolvedValue([
      {
        id: "audit-1",
        account_id: "acct-1",
        actor_type: "operator",
        actor_id: "operator-1",
        action: "task_system_config_updated",
        target_type: "task_system_config",
        target_id: "site-1",
        payload: { status: "active" },
        created_at: "2026-06-24T10:00:00Z",
      },
    ]);
    hoisted.listTaskQuotasMock.mockReset().mockResolvedValue([
      {
        id: "quota-1",
        account_id: "acct-1",
        site_id: "site-1",
        user_id: "user-4",
        plan_id: null,
        day_no: 3,
        package_count: 3,
        day_total_amount: "300.00",
        tolerance_amount: "10.00",
        amount_allocation_mode: "average",
        package_amounts_json: ["100.00", "100.00", "100.00"],
        product_pool_id: "pool-1",
        product_count_mode: "range",
        product_count_fixed: null,
        product_count_min: 1,
        product_count_max: 3,
        reward_ratio: "0.20",
        status: "pending",
        issued_batch_id: null,
        generated_at: null,
        generated_by: null,
        locked_at: null,
        created_by: "operator-1",
        metadata_json: null,
        created_at: "2026-06-24T00:00:00Z",
        updated_at: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.createTaskQuotaMock.mockReset().mockResolvedValue(undefined);
    hoisted.batchCreateTaskQuotasMock.mockReset().mockResolvedValue([]);
    hoisted.previewBatchTaskQuotasMock.mockReset().mockResolvedValue({
      userCount: 2,
      totalQuotaCount: 2,
      packageAmounts: ["110.00", "110.00"],
      computedTotalAmount: "220.00",
      totalBatchAmount: "440.00",
      rewardRatio: "0.10",
      productPoolId: "pool-1",
    });
    hoisted.generateTaskQuotaBatchMock.mockReset().mockResolvedValue({
      id: "run-1",
      account_id: "acct-1",
      site_id: "site-1",
      site_key: "site-cn",
      user_id: "user-3",
      public_user_id: "pub-u3",
      quota_id: "quota-1",
      batch_id: "batch-1",
      product_pool_id: "pool-1",
      selection_algorithm: "weighted_random_unique_v1",
      target_day_amount: 100,
      actual_day_system_amount: 98,
      tolerance_amount: 5,
      generated_package_count: 3,
      generated_item_count: 7,
      status: "success",
      failure_reason: null,
      created_at: "2026-06-24T00:00:00Z",
    });
    hoisted.previewTaskQuotaAllocationMock.mockReset().mockResolvedValue({
      packageAmounts: ["100.00", "100.00", "100.00"],
      computedTotalAmount: "300.00",
    });
    hoisted.listTaskProductPoolsMock.mockReset().mockResolvedValue([
      {
        id: "pool-1",
        accountId: "acct-1",
        siteId: "site-1",
        name: "Seasonal Pool",
        code: "seasonal-pool",
        poolType: "general",
        priceMode: "task_price_snapshot",
        allowRepeatInSameBatch: false,
        allowRepeatInSamePackage: false,
        status: "active",
        currency: "USD",
        metadataJson: null,
        itemCount: 2,
        items: [],
        createdAt: "2026-06-24T00:00:00Z",
        updatedAt: "2026-06-24T00:00:00Z",
      },
    ]);
    hoisted.createTaskProductPoolMock.mockReset().mockResolvedValue(undefined);
    hoisted.addTaskProductPoolItemsMock.mockReset().mockResolvedValue({
      id: "pool-1",
      accountId: "acct-1",
      siteId: "site-1",
      name: "Seasonal Pool",
      code: "seasonal-pool",
      poolType: "general",
      priceMode: "task_price_snapshot",
      allowRepeatInSameBatch: false,
      allowRepeatInSamePackage: false,
      status: "active",
      currency: "USD",
      metadataJson: null,
      itemCount: 1,
      items: [
        {
          id: "pool-item-1",
          productId: "prod-1",
          productName: "Pool Item 1",
          imageUrl: null,
          price: "19.90",
          currency: "USD",
          productDescription: null,
          status: "active",
          sortOrder: 1,
          weight: null,
          metadataJson: null,
          createdAt: "2026-06-24T00:00:00Z",
          updatedAt: "2026-06-24T00:00:00Z",
        },
      ],
      createdAt: "2026-06-24T00:00:00Z",
      updatedAt: "2026-06-24T00:00:00Z",
    });
    hoisted.deleteTaskProductPoolItemMock.mockReset().mockResolvedValue(undefined);
    hoisted.getTaskPackageDetailMock.mockReset().mockResolvedValue({
      id: "pkg-1",
      batch_id: "batch-1",
      day_no: 1,
      batch_index: 1,
      batch_total: 5,
      progress_label: "1/5",
      status: "active",
      planned_amount: 100,
      system_generated_amount: 100,
      manual_added_amount: 50,
      effective_amount: 150,
      reward_ratio: 0.1,
      estimated_reward_amount: 15,
      claimed_at: "2026-06-24T00:00:00Z",
      completed_at: null,
      items: [
        { id: "item-1", product_name: "Alpha", image_url: null, price: 100, currency: "USD", origin: "system_generated", status: "completed", completed_at: null, order_id: null },
      ],
      manual_add_logs: [
        { id: "log-1", package_id: "pkg-1", batch_id: "batch-1", operator_id: "op-1", reason_text: "manual add", notify_user: true, user_notice_text: "后台记录已通知用户", user_notified_at: "2026-06-24T00:05:00Z", added_item_count: 1, added_amount: 50, before_manual_added_amount: 0, after_manual_added_amount: 50, before_effective_amount: 100, after_effective_amount: 150, created_at: "2026-06-24T00:00:00Z" },
      ],
    });
    hoisted.listTaskManualAddLogsMock.mockReset().mockResolvedValue([
      { id: "log-1", package_id: "pkg-1", batch_id: "batch-1", operator_id: "op-1", reason_text: "manual add", notify_user: true, user_notice_text: "后台记录已通知用户", user_notified_at: "2026-06-24T00:05:00Z", added_item_count: 1, added_amount: 50, before_manual_added_amount: 0, after_manual_added_amount: 50, before_effective_amount: 100, after_effective_amount: 150, created_at: "2026-06-24T00:00:00Z" },
    ]);
    hoisted.listTaskPackageManualAddCandidatesMock.mockReset().mockResolvedValue([
      { id: "pool-1", product_id: "prod-1", product_name: "Beta", image_url: null, price: 50, currency: "USD" },
    ]);
    hoisted.previewTaskPackageManualAddMock.mockReset().mockResolvedValue({
      package_id: "pkg-1",
      candidate_count: 1,
      added_item_count: 1,
      added_amount: 50,
      package_manual_added_amount_before: 50,
      package_manual_added_amount_after: 100,
      package_effective_amount_before: 150,
      package_effective_amount_after: 200,
      estimated_reward_amount_before: 15,
      estimated_reward_amount_after: 20,
      items: [
        { pool_item_id: "pool-1", product_id: "prod-1", product_name: "Beta", image_url: null, price: 50, currency: "USD" },
      ],
    });
    hoisted.createTaskPackageManualAddMock.mockReset().mockResolvedValue({
      id: "log-2",
      package_id: "pkg-1",
      added_item_count: 1,
      added_amount: 50,
      package_manual_added_amount: 100,
      package_effective_amount: 200,
      batch_manual_added_amount: 100,
      batch_effective_day_amount: 200,
    });
    hoisted.pauseNextTaskPackageQuotaMock.mockReset().mockResolvedValue({
      id: "quota-next-1",
      account_id: "acct-1",
      site_id: "site-1",
      user_id: "user-3",
      plan_id: "plan-1",
      day_no: 2,
      package_count: 2,
      day_total_amount: "200.00",
      tolerance_amount: "5.00",
      amount_allocation_mode: "average",
      package_amounts_json: ["100.00", "100.00"],
      product_pool_id: "pool-1",
      product_count_mode: "range",
      product_count_fixed: null,
      product_count_min: 1,
      product_count_max: 2,
      reward_ratio: "0.15",
      status: "cancelled",
      issued_batch_id: null,
      generated_at: null,
      generated_by: null,
      locked_at: null,
      created_by: "operator-1",
      metadata_json: { cancel_reason: "manual_pause_next_batch_from_monitor" },
      created_at: "2026-06-24T00:00:00Z",
      updated_at: "2026-06-24T00:00:00Z",
    });
    hoisted.pauseTaskPackageMock.mockReset().mockResolvedValue(undefined);
    hoisted.retryTaskGenerationRunMock.mockReset().mockResolvedValue({
      id: "run-2",
      account_id: "acct-1",
      site_id: "site-1",
      site_key: "site-cn",
      user_id: "user-3",
      public_user_id: "pub-u3",
      quota_id: "quota-1",
      batch_id: "batch-1",
      product_pool_id: "pool-1",
      selection_algorithm: "weighted_random_unique_v1",
      target_day_amount: 100,
      actual_day_system_amount: 100,
      tolerance_amount: 5,
      generated_package_count: 3,
      generated_item_count: 7,
      status: "success",
      failure_reason: null,
      created_at: "2026-06-24T00:01:00Z",
    });
    hoisted.resumeTaskPackageMock.mockReset().mockResolvedValue(undefined);
    hoisted.cancelTaskPackageMock.mockReset().mockResolvedValue(undefined);
    hoisted.listPlatformUserMemberStatusIndexMock.mockReset().mockResolvedValue({});
    hoisted.createTaskTemplateMock.mockReset().mockResolvedValue(undefined);
    hoisted.approveTaskReviewMock.mockReset().mockResolvedValue(undefined);
    hoisted.rejectTaskReviewMock.mockReset().mockResolvedValue(undefined);
    hoisted.listMetaAccountsMock.mockReset().mockResolvedValue([
      { account_id: "acct-1", display_name: "Account 1" },
    ]);
    hoisted.listSitesMock.mockReset().mockResolvedValue([
      { id: "site-1", site_key: "site-cn", brand_name: "Site CN" },
    ]);
    hoisted.realtimeConnectMock.mockReset();
    hoisted.realtimeDisconnectMock.mockReset();
    hoisted.latestRealtimeOptions = null;
    hoisted.playAlertSoundMock.mockReset();
    hoisted.showErrorMock.mockReset();
    hoisted.showSuccessMock.mockReset();
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  afterEach(async () => {
    while (mountedRoots.length > 0) {
      const root = mountedRoots.pop();
      await act(async () => root?.unmount());
    }
    while (mountedContainers.length > 0) {
      mountedContainers.pop()?.remove();
    }
    vi.restoreAllMocks();
    vi.useRealTimers();
    delete (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT;
  });

  it("renders task instance and review user columns with MemberIdLink", async () => {
    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("member-link:pub-u1:user-1:pub-u1:acct-1");
    expect(document.body.textContent).toContain("member-link:pub-u2:user-2:pub-u2:acct-1");
  });

  it("renders task package tab data from the new package list api", async () => {
    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("member-link:pub-u3:user-3:pub-u3:acct-1");
    expect(document.body.textContent).toContain("1/5");
    expect(document.body.textContent).toContain("150");
  });

  it("loads package detail when clicking the package detail action", async () => {
    await renderPage(createElement(TasksPage));
    const detailButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Package Detail"));
    expect(detailButton).toBeTruthy();
    await act(async () => {
      detailButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(hoisted.getTaskPackageDetailMock).toHaveBeenCalledWith("pkg-1");
    expect(document.body.textContent).toContain("Alpha");
  });

  it("loads manual add candidates when clicking the package manual add action", async () => {
    await renderPage(createElement(TasksPage));
    const manualAddButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manual Add"));
    expect(manualAddButton).toBeTruthy();
    await act(async () => {
      manualAddButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(hoisted.listTaskPackageManualAddCandidatesMock).toHaveBeenCalledWith("pkg-1");
    expect(document.body.textContent).toContain("Beta");
  });

  it("only exposes add flow in the package manual add modal without replace or delete actions", async () => {
    await renderPage(createElement(TasksPage));
    const manualAddButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manual Add"));
    expect(manualAddButton).toBeTruthy();

    await act(async () => {
      manualAddButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(document.body.textContent).toContain("Preview Manual Add Impact");
    expect(document.body.textContent).toContain("Beta");
    expect(document.body.textContent).not.toContain("替换商品");
    expect(document.body.textContent).not.toContain("删除商品");
  });

  it("submits manual add without notice fields in the legacy slot", async () => {
    await renderPage(createElement(TasksPage));
    const manualAddButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manual Add"));
    expect(manualAddButton).toBeTruthy();

    await act(async () => {
      manualAddButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const reasonInput = document.querySelector('textarea[placeholder="Manual add reason"]') as HTMLTextAreaElement | null;
    const noticeInput = null as HTMLTextAreaElement | null;
    expect(reasonInput).toBeTruthy();
    expect(document.body.textContent).not.toContain("Record user notice");
    expect(
      document.querySelector('textarea[placeholder="Optional notice note kept in backend records"]'),
    ).toBeNull();

    const candidateCheckbox = Array.from(document.querySelectorAll('input[type="checkbox"]')).find((node) =>
      node.parentElement?.textContent?.includes("Beta"),
    ) as HTMLInputElement | undefined;
    expect(candidateCheckbox).toBeTruthy();

    await act(async () => {
      candidateCheckbox?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      if (reasonInput) {
        Object.defineProperty(reasonInput, "value", { value: "Need top up", configurable: true });
        reasonInput.dispatchEvent(new Event("input", { bubbles: true }));
        reasonInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (noticeInput) {
        Object.defineProperty(noticeInput, "value", { value: "后台记录已通知用户", configurable: true });
        noticeInput.dispatchEvent(new Event("input", { bubbles: true }));
        noticeInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    const submitButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Submit Manual Add"),
    );
    expect(submitButton).toBeTruthy();

    await act(async () => {
      submitButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.createTaskPackageManualAddMock).toHaveBeenCalledWith("pkg-1", {
      pool_item_ids: ["pool-1"],
      reason_text: "Need top up",
    });
  });

  it("submits manual add without user notice payload", async () => {
    await renderPage(createElement(TasksPage));
    const manualAddButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manual Add"));
    expect(manualAddButton).toBeTruthy();

    await act(async () => {
      manualAddButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const reasonInput = document.querySelector('textarea[placeholder="Manual add reason"]') as HTMLTextAreaElement | null;
    expect(reasonInput).toBeTruthy();
    expect(document.body.textContent).not.toContain("Record user notice");
    expect(
      document.querySelector('textarea[placeholder="Optional notice note kept in backend records"]'),
    ).toBeNull();

    const candidateCheckbox = Array.from(document.querySelectorAll('input[type="checkbox"]')).find((node) =>
      node.parentElement?.textContent?.includes("Beta"),
    ) as HTMLInputElement | undefined;
    expect(candidateCheckbox).toBeTruthy();

    await act(async () => {
      candidateCheckbox?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      if (reasonInput) {
        Object.defineProperty(reasonInput, "value", { value: "Need top up", configurable: true });
        reasonInput.dispatchEvent(new Event("input", { bubbles: true }));
        reasonInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    const submitButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Submit Manual Add"),
    );
    expect(submitButton).toBeTruthy();

    await act(async () => {
      submitButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.createTaskPackageManualAddMock).toHaveBeenCalledWith("pkg-1", {
      pool_item_ids: ["pool-1"],
      reason_text: "Need top up",
    });
  });

  it("submits manual add without surfacing a success toast", async () => {
    await renderPage(createElement(TasksPage));
    const manualAddButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manual Add"));
    expect(manualAddButton).toBeTruthy();

    await act(async () => {
      manualAddButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const reasonInput = document.querySelector('textarea[placeholder="Manual add reason"]') as HTMLTextAreaElement | null;
    const candidateCheckbox = Array.from(document.querySelectorAll('input[type="checkbox"]')).find((node) =>
      node.parentElement?.textContent?.includes("Beta"),
    ) as HTMLInputElement | undefined;
    expect(reasonInput).toBeTruthy();
    expect(candidateCheckbox).toBeTruthy();

    await act(async () => {
      candidateCheckbox?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      if (reasonInput) {
        Object.defineProperty(reasonInput, "value", { value: "Need top up", configurable: true });
        reasonInput.dispatchEvent(new Event("input", { bubbles: true }));
        reasonInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    const submitButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Submit Manual Add"),
    );
    expect(submitButton).toBeTruthy();

    await act(async () => {
      submitButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.showSuccessMock).not.toHaveBeenCalled();
    expect(hoisted.showErrorMock).not.toHaveBeenCalledWith("Failed to submit manual add");
  });

  it("keeps the error toast when manual add submission fails", async () => {
    hoisted.createTaskPackageManualAddMock.mockRejectedValueOnce(new Error("submit failed"));
    await renderPage(createElement(TasksPage));
    const manualAddButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manual Add"));
    expect(manualAddButton).toBeTruthy();

    await act(async () => {
      manualAddButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const reasonInput = document.querySelector('textarea[placeholder="Manual add reason"]') as HTMLTextAreaElement | null;
    const candidateCheckbox = Array.from(document.querySelectorAll('input[type="checkbox"]')).find((node) =>
      node.parentElement?.textContent?.includes("Beta"),
    ) as HTMLInputElement | undefined;
    expect(reasonInput).toBeTruthy();
    expect(candidateCheckbox).toBeTruthy();

    await act(async () => {
      candidateCheckbox?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      if (reasonInput) {
        Object.defineProperty(reasonInput, "value", { value: "Need top up", configurable: true });
        reasonInput.dispatchEvent(new Event("input", { bubbles: true }));
        reasonInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    const submitButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Submit Manual Add"),
    );
    expect(submitButton).toBeTruthy();

    await act(async () => {
      submitButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.showErrorMock).toHaveBeenCalledWith("Failed to submit manual add");
    expect(hoisted.showSuccessMock).not.toHaveBeenCalled();
  });

  it("loads manual add logs for the selected package in the standalone tab", async () => {
    await renderPage(createElement(TasksPage));
    await waitFor(() => {
      expect(hoisted.listTaskManualAddLogsMock).toHaveBeenCalledWith("pkg-1");
    });
    expect(document.body.textContent).toContain("manual add");
  });

  it("triggers pause and cancel package actions from the package list", async () => {
    await renderPage(createElement(TasksPage));

    const pauseButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Pause"),
    );
    const cancelButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Cancel"),
    );
    expect(pauseButton).toBeTruthy();
    expect(cancelButton).toBeTruthy();

    await act(async () => {
      pauseButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      cancelButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.pauseTaskPackageMock).toHaveBeenCalledWith("pkg-1", {
      reason_text: "manual_pause_from_admin",
    });
    expect(hoisted.cancelTaskPackageMock).toHaveBeenCalledWith("pkg-1", {
      reason_text: "manual_cancel_from_admin",
    });
  });

  it("triggers resume package action when the package row is paused", async () => {
    hoisted.listTaskPackagesMock.mockReset().mockResolvedValue([
      {
        id: "pkg-paused-1",
        account_id: "acct-1",
        user_id: "user-5",
        public_user_id: "pub-u5",
        site_id: "site-1",
        site_key: "site-cn",
        batch_id: "batch-2",
        day_no: 2,
        batch_index: 2,
        batch_total: 5,
        progress_label: "2/5",
        status: "paused",
        planned_amount: 120,
        system_generated_amount: 120,
        manual_added_amount: 0,
        effective_amount: 120,
        estimated_reward_amount: 12,
        has_manual_add: false,
        claimed_at: "2026-06-24T00:00:00Z",
        completed_at: null,
      },
    ]);

    await renderPage(createElement(TasksPage));

    const resumeButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Resume"),
    );
    expect(resumeButton).toBeTruthy();

    await act(async () => {
      resumeButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.resumeTaskPackageMock).toHaveBeenCalledWith("pkg-paused-1", {
      reason_text: "manual_resume_from_admin",
    });
  });

  it("renders quota and product pool data from new admin apis", async () => {
    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("quota-1");
    expect(document.body.textContent).toContain("Seasonal Pool");
  });

  it("keeps all three quota allocation modes aligned with the v3 task spec", () => {
    expect(TASK_AMOUNT_ALLOCATION_MODE_OPTIONS).toEqual([
      { label: "Average", value: "average" },
      { label: "Incremental", value: "incremental" },
      { label: "Manual", value: "manual" },
    ]);
  });

  it("keeps quota product-count modes aligned with the v3 task spec", () => {
    expect(TASK_PRODUCT_COUNT_MODE_OPTIONS).toEqual([
      { label: "Fixed", value: "fixed" },
      { label: "Range", value: "range" },
    ]);
  });

  it("keeps issue-plan rule option sets aligned with the v3 task spec", () => {
    expect(TASK_PLAN_CLAIM_GATE_OPTIONS).toEqual([
      { label: "Certified Member", value: "certified_member" },
      { label: "WhatsApp Bound", value: "whatsapp_bound" },
      { label: "None", value: "none" },
    ]);
    expect(TASK_PLAN_ISSUE_ANCHOR_OPTIONS).toEqual([
      { label: "Certified At", value: "certified_at" },
      { label: "Registered At", value: "registered_at" },
      { label: "Bound At", value: "bound_at" },
    ]);
    expect(TASK_PLAN_ISSUE_MODE_OPTIONS).toEqual([
      { label: "Calendar Day", value: "calendar_day" },
      { label: "Elapsed Delay", value: "elapsed_delay" },
    ]);
    expect(TASK_PLAN_AFTER_LAST_RULE_MODE_OPTIONS).toEqual([
      { label: "Arithmetic Growth", value: "arithmetic_growth" },
      { label: "Repeat Last", value: "repeat_last" },
      { label: "Stop", value: "stop" },
    ]);
  });

  it("builds quota payloads with manual allocation and fixed product counts", () => {
    expect(buildTaskQuotaCreatePayload({
      account_id: "acct-1",
      user_id: "user-1",
      site_id: "site-1",
      day_no: 2,
      package_count: 3,
      day_total_amount: 300,
      tolerance_amount: 8,
      amount_allocation_mode: "manual",
      package_amounts_text: "80,100,120",
      product_pool_id: "pool-1",
      product_count_mode: "fixed",
      product_count_fixed: 2,
      reward_ratio: 0.18,
    })).toEqual({
      account_id: "acct-1",
      user_id: "user-1",
      site_id: "site-1",
      day_no: 2,
      package_count: 3,
      day_total_amount: "300",
      tolerance_amount: "8",
      amount_allocation_mode: "manual",
      package_amounts: ["80", "100", "120"],
      product_pool_id: "pool-1",
      product_count_mode: "fixed",
      product_count_fixed: 2,
      product_count_min: undefined,
      product_count_max: undefined,
      reward_ratio: "0.18",
    });
  });

  it("builds batch quota payloads from a multi-user text list", () => {
    expect(buildTaskQuotaBatchCreatePayload({
      account_id: "acct-1",
      site_id: "site-1",
      user_ids_text: "user-1\nuser-2,user-1",
      owner_staff_user_id: "staff-1",
      certified_status: "certified",
      min_total_real_recharge: 50,
      max_total_real_recharge: 500,
      tag_keys_text: "vip\nhigh_value,vip",
      day_no: 5,
      package_count: 2,
      day_total_amount: 220,
      tolerance_amount: 5,
      amount_allocation_mode: "average",
      product_pool_id: "pool-1",
      product_count_mode: "range",
      product_count_min: 1,
      product_count_max: 2,
      reward_ratio: 0.1,
    })).toEqual({
      account_id: "acct-1",
      user_ids: ["user-1", "user-2"],
      site_id: "site-1",
      day_no: 5,
      package_count: 2,
      day_total_amount: "220",
      tolerance_amount: "5",
      amount_allocation_mode: "average",
      package_amounts: undefined,
      product_pool_id: "pool-1",
      product_count_mode: "range",
      product_count_fixed: undefined,
      product_count_min: 1,
      product_count_max: 2,
      reward_ratio: "0.1",
      owner_staff_user_id: "staff-1",
      certified_status: "certified",
      min_total_real_recharge: "50",
      max_total_real_recharge: "500",
      tag_keys: ["vip", "high_value"],
    });
  });

  it("builds batch quota preview summary from unique users and per-user preview amounts", () => {
    expect(buildTaskQuotaBatchPreviewSummary(
      {
        account_id: "acct-1",
        site_id: "site-1",
        user_ids_text: "user-1\nuser-2\nuser-1",
        day_no: 5,
        package_count: 2,
        day_total_amount: 220,
        tolerance_amount: 5,
        amount_allocation_mode: "average",
        product_pool_id: "pool-1",
        product_count_mode: "range",
        product_count_min: 1,
        product_count_max: 2,
        reward_ratio: 0.1,
      },
      ["110.00", "110.00"],
      "220.00",
    )).toEqual({
      user_count: 2,
      total_quota_count: 2,
      package_amounts: ["110.00", "110.00"],
      computed_total_amount: "220.00",
      total_batch_amount: "440",
      reward_ratio: "0.1",
      product_pool_id: "pool-1",
    });
  });

  it("builds issue-plan payloads with configurable first-day rules", () => {
    expect(buildTaskIssuePlanCreatePayload({
      account_id: "acct-1",
      site_id: "site-1",
      name: "Growth Plan",
      claim_gate: "whatsapp_bound",
      issue_anchor: "bound_at",
      issue_mode: "elapsed_delay",
      require_previous_batch_completed: false,
      max_unfinished_batches: 3,
      after_last_rule_mode: "repeat_last",
      growth_package_count_step: 2,
      growth_amount_step: 88,
      default_product_pool_id: "pool-1",
      first_day_package_count: 3,
      first_day_total_amount: 360,
      default_tolerance_amount: 12,
      default_reward_ratio: 0.22,
      first_day_amount_allocation_mode: "manual",
      first_day_package_amounts_text: "100,120,140",
      first_day_product_count_mode: "range",
      first_day_product_count_min: 1,
      first_day_product_count_max: 4,
      first_day_reward_ratio: 0.25,
      first_day_issue_time_of_day: "10:30",
      first_day_elapsed_delay_hours: 24,
    })).toEqual({
      account_id: "acct-1",
      site_id: "site-1",
      name: "Growth Plan",
      plan_type: "official",
      status: "active",
      claim_gate: "whatsapp_bound",
      issue_anchor: "bound_at",
      issue_mode: "elapsed_delay",
      require_previous_batch_completed: false,
      max_unfinished_batches: 3,
      after_last_rule_mode: "repeat_last",
      growth_package_count_step: 2,
      growth_amount_step: "88",
      default_product_pool_id: "pool-1",
      default_tolerance_amount: "12",
      default_reward_ratio: "0.22",
      day_rules: [
        {
          day_no: 1,
          package_count: 3,
          day_total_amount: "360",
          tolerance_amount: "12",
          amount_allocation_mode: "manual",
          package_amounts_json: ["100", "120", "140"],
          product_pool_id: "pool-1",
          product_count_mode: "range",
          product_count_fixed: undefined,
          product_count_min: 1,
          product_count_max: 4,
          reward_ratio: "0.25",
          issue_time_of_day: "10:30",
          elapsed_delay_hours: 24,
          status: "active",
        },
      ],
    });
  });

  it("renders locked quota status with a dedicated label instead of raw backend status", async () => {
    hoisted.listTaskQuotasMock.mockReset().mockResolvedValue([
      {
        id: "quota-locked-1",
        account_id: "acct-1",
        site_id: "site-1",
        user_id: "user-4",
        plan_id: null,
        day_no: 4,
        package_count: 2,
        day_total_amount: "200.00",
        tolerance_amount: "5.00",
        amount_allocation_mode: "average",
        package_amounts_json: ["100.00", "100.00"],
        product_pool_id: "pool-1",
        product_count_mode: "range",
        product_count_fixed: null,
        product_count_min: 1,
        product_count_max: 2,
        reward_ratio: "0.15",
        status: "locked",
        issued_batch_id: "batch-1",
        generated_at: "2026-06-24T00:00:00Z",
        generated_by: "operator-1",
        locked_at: "2026-06-24T00:05:00Z",
        created_by: "operator-1",
        metadata_json: null,
        created_at: "2026-06-24T00:00:00Z",
        updated_at: "2026-06-24T00:05:00Z",
      },
    ]);

    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("\u5df2\u9501\u5b9a");
  });

  it("renders task monitor row and summary data from the new admin api", async () => {
    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("Package ID");
    expect(document.body.textContent).toContain("Current Product Source");
    expect(document.body.textContent).toContain("Manual Added Items");
    expect(document.body.textContent).toContain("Latest Manual Add By");
    expect(document.body.textContent).toContain("Day Planned Amount");
    expect(document.body.textContent).toContain("Day Effective Amount");
    expect(document.body.textContent).toContain("Product Pool ID");
    expect(document.body.textContent).not.toContain("Column");
    expect(document.body.textContent).toContain("pkg-1");
    expect(document.body.textContent).toContain("150");
    expect(document.body.textContent).toContain("120");
    expect(document.body.textContent).toContain("system_generated");
    expect(document.body.textContent).toContain("2");
    expect(document.body.textContent).toContain("operator-h5-member-auth");
    expect(document.body.textContent).toContain("300");
  });

  it("applies monitor filters to both row and summary admin apis", async () => {
    await renderPage(createElement(TasksPage));

    const userQueryInput = document.querySelector('input[placeholder="Search User / Public ID"]') as HTMLInputElement | null;
    const plannedMinInput = document.querySelector('input[placeholder="Planned Amount Min"]') as HTMLInputElement | null;
    const manualMinInput = document.querySelector('input[placeholder="Manual Added Min"]') as HTMLInputElement | null;
    const dayEffectiveMinInput = document.querySelector('input[placeholder="Day Effective Min"]') as HTMLInputElement | null;
    const latestOperatorInput = document.querySelector('input[placeholder="Latest Manual Add Operator"]') as HTMLInputElement | null;
    const applyButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Apply Filters"),
    );

    expect(userQueryInput).toBeTruthy();
    expect(plannedMinInput).toBeTruthy();
    expect(manualMinInput).toBeTruthy();
    expect(dayEffectiveMinInput).toBeTruthy();
    expect(latestOperatorInput).toBeTruthy();
    expect(applyButton).toBeTruthy();

    await act(async () => {
      fireEvent.change(userQueryInput!, { target: { value: "pub-u3" } });
      fireEvent.change(plannedMinInput!, { target: { value: "100" } });
      fireEvent.change(manualMinInput!, { target: { value: "50" } });
      fireEvent.change(dayEffectiveMinInput!, { target: { value: "280" } });
      fireEvent.change(latestOperatorInput!, { target: { value: "operator-h5-member-auth" } });
      fireEvent.click(applyButton!);
    });

    await waitFor(() => {
      expect(hoisted.listTaskMonitorRowsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          user_query: "pub-u3",
          planned_amount_min: "100",
          manual_added_amount_min: "50",
          day_effective_amount_min: "280",
          latest_manual_add_operator_id: "operator-h5-member-auth",
        }),
      );
      expect(hoisted.getTaskMonitorSummaryMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          user_query: "pub-u3",
          planned_amount_min: "100",
          manual_added_amount_min: "50",
          day_effective_amount_min: "280",
          latest_manual_add_operator_id: "operator-h5-member-auth",
        }),
      );
    });
  });

  it("loads generation runs from the dedicated admin api instead of reusing monitor rows", async () => {
    await renderPage(createElement(TasksPage));
    expect(hoisted.listTaskGenerationRunsMock).toHaveBeenCalledWith({
      account_id: undefined,
    });
    expect(document.body.textContent).toContain("weighted_random_unique_v1");
  });

  it("generates a quota batch from the quota list action", async () => {
    await renderPage(createElement(TasksPage));

    const generateButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Generate Batch"),
    );
    expect(generateButton).toBeTruthy();

    await act(async () => {
      generateButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.generateTaskQuotaBatchMock).toHaveBeenCalledWith("quota-1");
  });

  it("retries a failed generation run from the monitoring panel", async () => {
    hoisted.listTaskGenerationRunsMock.mockReset().mockResolvedValue([
      {
        id: "run-failed-1",
        account_id: "acct-1",
        site_id: "site-1",
        site_key: "site-cn",
        user_id: "user-3",
        public_user_id: "pub-u3",
        quota_id: "quota-1",
        batch_id: null,
        product_pool_id: "pool-1",
        selection_algorithm: "weighted_random_unique_v1",
        target_day_amount: 100,
        actual_day_system_amount: 0,
        tolerance_amount: 5,
        generated_package_count: 0,
        generated_item_count: 0,
        status: "failed",
        failure_reason: "PRODUCT_POOL_NOT_ENOUGH_UNIQUE_ITEMS",
        created_at: "2026-06-24T00:00:00Z",
      },
    ]);

    await renderPage(createElement(TasksPage));

    const retryButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Retry Run"),
    );
    expect(retryButton).toBeTruthy();

    await act(async () => {
      retryButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.retryTaskGenerationRunMock).toHaveBeenCalledWith("run-failed-1");
  });

  it("renders saved views and alert rules from monitor config apis", async () => {
    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("High Risk Tasks");
    expect(document.body.textContent).toContain("High Amount Alert");
    expect(document.body.textContent).toContain("Alert Events");
    expect(document.body.textContent).toContain("open");
  });

  it("acknowledges and resolves monitor alert events from the monitoring tab", async () => {
    await renderPage(createElement(TasksPage));
    const ackButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Ack"));
    const resolveButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Resolve"));
    expect(ackButton).toBeTruthy();
    expect(resolveButton).toBeTruthy();

    await act(async () => {
      ackButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      resolveButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.acknowledgeTaskMonitorAlertEventMock).toHaveBeenCalledWith("evt-1");
    expect(hoisted.resolveTaskMonitorAlertEventMock).toHaveBeenCalledWith("evt-1");
  });

  it("auto refreshes monitor data using the default saved view refresh interval", async () => {
    vi.useFakeTimers();

    await renderPage(createElement(TasksPage));

    const initialMonitorRowCalls = hoisted.listTaskMonitorRowsMock.mock.calls.length;
    const initialAlertEventCalls = hoisted.listTaskMonitorAlertEventsMock.mock.calls.length;

    await act(async () => {
      vi.advanceTimersByTime(15_000);
    });
    await flushEffects();

    expect(hoisted.listTaskMonitorRowsMock.mock.calls.length).toBeGreaterThan(initialMonitorRowCalls);
    expect(hoisted.listTaskMonitorAlertEventsMock.mock.calls.length).toBeGreaterThan(initialAlertEventCalls);
  });

  it("subscribes to monitor alert realtime snapshots and applies incoming updates", async () => {
    await renderPage(createElement(TasksPage));

    expect(hoisted.realtimeConnectMock).toHaveBeenCalledWith(
      expect.objectContaining({
        accountId: undefined,
        onSnapshot: expect.any(Function),
      }),
    );

    await act(async () => {
      (hoisted.latestRealtimeOptions?.onSnapshot as ((events: Array<Record<string, unknown>>) => void))?.([
        {
          id: "evt-2",
          account_id: "acct-1",
          alert_rule_id: "alert-2",
          package_id: "pkg-2",
          user_id: "user-4",
          public_user_id: "pub-u4",
          status: "acknowledged",
          priority: "normal",
          rule_name: "Realtime Alert",
          current_value: 88,
          threshold_value: 80,
          sound_enabled: false,
          triggered_at: "2026-06-25T00:00:00Z",
          acknowledged_at: "2026-06-25T00:00:05Z",
          acknowledged_by: "admin-1",
          resolved_at: null,
          resolved_by: null,
        },
      ]);
    });

    expect(document.body.textContent).toContain("Realtime Alert");
    expect(document.body.textContent).toContain("acknowledged");
  });

  it("plays a sound when realtime snapshots introduce a new sound-enabled open alert", async () => {
    await renderPage(createElement(TasksPage));

    await act(async () => {
      (hoisted.latestRealtimeOptions?.onSnapshot as ((events: Array<Record<string, unknown>>) => void))?.([
        {
          id: "evt-initial",
          account_id: "acct-1",
          alert_rule_id: "alert-1",
          package_id: "pkg-1",
          user_id: "user-1",
          public_user_id: "pub-u1",
          status: "open",
          priority: "high",
          rule_name: "Existing Alert",
          current_value: 100,
          threshold_value: 80,
          sound_enabled: true,
          triggered_at: "2026-06-24T00:00:00Z",
          acknowledged_at: null,
          acknowledged_by: null,
          resolved_at: null,
          resolved_by: null,
        },
      ]);
    });
    expect(hoisted.playAlertSoundMock).not.toHaveBeenCalled();

    await act(async () => {
      (hoisted.latestRealtimeOptions?.onSnapshot as ((events: Array<Record<string, unknown>>) => void))?.([
        {
          id: "evt-initial",
          account_id: "acct-1",
          alert_rule_id: "alert-1",
          package_id: "pkg-1",
          user_id: "user-1",
          public_user_id: "pub-u1",
          status: "open",
          priority: "high",
          rule_name: "Existing Alert",
          current_value: 100,
          threshold_value: 80,
          sound_enabled: true,
          triggered_at: "2026-06-24T00:00:00Z",
          acknowledged_at: null,
          acknowledged_by: null,
          resolved_at: null,
          resolved_by: null,
        },
        {
          id: "evt-new-sound",
          account_id: "acct-1",
          alert_rule_id: "alert-2",
          package_id: "pkg-2",
          user_id: "user-2",
          public_user_id: "pub-u2",
          status: "open",
          priority: "high",
          rule_name: "New Sound Alert",
          current_value: 200,
          threshold_value: 150,
          sound_enabled: true,
          triggered_at: "2026-06-24T00:01:00Z",
          acknowledged_at: null,
          acknowledged_by: null,
          resolved_at: null,
          resolved_by: null,
        },
      ]);
    });

    expect(hoisted.playAlertSoundMock).toHaveBeenCalledTimes(1);
  });

  it("opens package detail, manual add, and customer actions from the monitoring table", async () => {
    const openCustomersPageMock = vi.fn();
    hoisted.storeState = {
      openCustomersPage: openCustomersPageMock,
    };

    await renderPage(createElement(TasksPage));

    const detailButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Package Detail"),
    );
    const manualAddButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Manual Add"),
    );
    const customerButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Customer Detail"),
    );
    const walletButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Customer Wallet"),
    );
    const pauseNextBatchButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Pause Next Batch"),
    );
    expect(detailButton).toBeTruthy();
    expect(manualAddButton).toBeTruthy();
    expect(customerButton).toBeTruthy();
    expect(walletButton).toBeTruthy();
    expect(pauseNextBatchButton).toBeTruthy();

    await act(async () => {
      detailButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      manualAddButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      customerButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      walletButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      pauseNextBatchButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.getTaskPackageDetailMock).toHaveBeenCalledWith("pkg-1");
    expect(hoisted.listTaskPackageManualAddCandidatesMock).toHaveBeenCalledWith("pkg-1");
    expect(hoisted.pauseNextTaskPackageQuotaMock).toHaveBeenCalledWith("pkg-1", {
      reason: "manual_pause_next_batch_from_monitor",
    });
    expect(openCustomersPageMock).toHaveBeenCalledWith({
      account_id: "acct-1",
      selected_profile_id: "user-3",
      query: "pub-u3",
    });
    expect(openCustomersPageMock).toHaveBeenLastCalledWith({
      account_id: "acct-1",
      selected_profile_id: "user-3",
      query: "pub-u3",
      detail_tab: "finance",
    });
  });

  it("updates and deletes saved views from the monitoring tab", async () => {
    await renderPage(createElement(TasksPage));

    const setDefaultButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Set Default"),
    );
    const deleteViewButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Delete View"),
    );
    expect(setDefaultButton).toBeTruthy();
    expect(deleteViewButton).toBeTruthy();

    await act(async () => {
      setDefaultButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      deleteViewButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.updateTaskMonitorSavedViewMock).toHaveBeenCalledWith(
      "view-1",
      expect.objectContaining({
        name: "High Risk Tasks",
        is_default: true,
        refresh_seconds: 15,
      }),
    );
    expect(hoisted.deleteTaskMonitorSavedViewMock).toHaveBeenCalledWith("view-1");
  });

  it("toggles and deletes alert rules from the monitoring tab", async () => {
    await renderPage(createElement(TasksPage));

    const toggleRuleButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Pause Rule"),
    );
    const deleteRuleButton = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Delete Rule"),
    );
    expect(toggleRuleButton).toBeTruthy();
    expect(deleteRuleButton).toBeTruthy();

    await act(async () => {
      toggleRuleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {
      deleteRuleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.updateTaskAlertRuleMock).toHaveBeenCalledWith(
      "alert-1",
      expect.objectContaining({
        name: "High Amount Alert",
        status: "paused",
        priority: "high",
      }),
    );
    expect(hoisted.deleteTaskAlertRuleMock).toHaveBeenCalledWith("alert-1");
  });

  it("renders issue plan data from the new admin api", async () => {
    await renderPage(createElement(TasksPage));
    expect(document.body.textContent).toContain("Official Growth Plan");
    expect(document.body.textContent).toContain("arithmetic_growth");
  });

  it("toggles issue plan status from the plans tab", async () => {
    await renderPage(createElement(TasksPage));
    const toggleButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Disable"));
    expect(toggleButton).toBeTruthy();
    await act(async () => {
      toggleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(hoisted.disableTaskIssuePlanMock).toHaveBeenCalledWith("plan-1");
  });

  it("opens product pool item manager from the pool list", async () => {
    await renderPage(createElement(TasksPage));
    const managePoolButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manage Items"));
    expect(managePoolButton).toBeTruthy();
    await act(async () => {
      managePoolButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(document.body.textContent).toContain("Seasonal Pool");
  });

  it("adds a pool item without surfacing a success toast", async () => {
    await renderPage(createElement(TasksPage));
    const managePoolButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manage Items"));
    expect(managePoolButton).toBeTruthy();

    await act(async () => {
      managePoolButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const addItemButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Add Item"));
    expect(addItemButton).toBeTruthy();

    await act(async () => {
      addItemButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.addTaskProductPoolItemsMock).toHaveBeenCalledWith("pool-1", {
      items: [
        {
          productId: "prod-new",
          productName: "New Product",
          price: "88",
          currency: "USD",
          productDescription: "New description",
        },
      ],
    });
    expect(hoisted.showSuccessMock).not.toHaveBeenCalled();
    expect(hoisted.showErrorMock).not.toHaveBeenCalledWith("Failed to add pool item");
  });

  it("keeps the error toast when adding a pool item fails", async () => {
    hoisted.addTaskProductPoolItemsMock.mockRejectedValueOnce(new Error("add failed"));
    await renderPage(createElement(TasksPage));
    const managePoolButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Manage Items"));
    expect(managePoolButton).toBeTruthy();

    await act(async () => {
      managePoolButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const addItemButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Add Item"));
    expect(addItemButton).toBeTruthy();

    await act(async () => {
      addItemButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.showErrorMock).toHaveBeenCalledWith("Failed to add pool item");
    expect(hoisted.showSuccessMock).not.toHaveBeenCalled();
  });

  it("previews quota amount allocation before creating a quota", async () => {
    await renderPage(createElement(TasksPage));
    const previewButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("Preview Amount Allocation"));
    expect(previewButton).toBeTruthy();
    await act(async () => {
      previewButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(hoisted.previewTaskQuotaAllocationMock).toHaveBeenCalled();
    expect(document.body.textContent).toContain("100.00");
  });

  it("loads and saves task system config through the real settings api", async () => {
    await renderPage(createElement(TasksPage));
    expect(hoisted.getTaskSystemConfigMock).toHaveBeenCalledWith({
      account_id: "acct-1",
      site_id: "site-1",
    });
    expect(hoisted.listTaskSystemConfigAuditLogsMock).toHaveBeenCalledWith({
      account_id: "acct-1",
      site_id: "site-1",
    });
    expect(document.body.textContent).toContain("系统设置");

    const saveButton = Array.from(document.querySelectorAll("button")).find((node) => node.textContent?.includes("保存设置"));
    expect(saveButton).toBeTruthy();
    await act(async () => {
      saveButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(hoisted.patchTaskSystemConfigMock).toHaveBeenCalledWith(
      expect.objectContaining({
        account_id: "acct-1",
        site_id: "site-1",
        whatsapp_binding_reward_amount: "20.00",
        certified_recharge_threshold: "50.00",
        max_active_batches_per_user: 1,
        max_active_packages_per_user: 1,
      }),
    );
  });

  it("re-scopes the settings site selector when the account changes", async () => {
    hoisted.listMetaAccountsMock.mockResolvedValue([
      { account_id: "acct-1", display_name: "Account 1" },
      { account_id: "acct-2", display_name: "Account 2" },
    ]);
    hoisted.listSitesMock.mockResolvedValue([
      {
        id: "site-1",
        site_key: "site-cn",
        brand_name: "Site CN",
        account_id: "acct-1",
        name: "Site CN",
        site_type: "h5",
        status: "active",
        created_at: "2026-06-24T00:00:00Z",
      },
      {
        id: "site-2",
        site_key: "site-us",
        brand_name: "Site US",
        account_id: "acct-2",
        name: "Site US",
        site_type: "h5",
        status: "active",
        created_at: "2026-06-24T00:00:00Z",
      },
    ]);

    await renderPage(createElement(TasksPage));

    const accountSelect = document.querySelector('[data-testid="task-settings-account-select"]') as HTMLSelectElement | null;
    const siteSelect = document.querySelector('[data-testid="task-settings-site-select"]') as HTMLSelectElement | null;

    await waitFor(() => {
      expect(accountSelect?.value).toBe("acct-1");
      expect(siteSelect?.value).toBe("site-1");
    });
    expect(Array.from(siteSelect?.options ?? []).map((option) => option.value)).toContain("site-1");
    expect(Array.from(siteSelect?.options ?? []).map((option) => option.value)).not.toContain("site-2");

    await act(async () => {
      accountSelect!.value = "acct-2";
      accountSelect!.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flushEffects();

    expect(siteSelect?.value).toBe("site-2");
    expect(hoisted.getTaskSystemConfigMock).toHaveBeenLastCalledWith({
      account_id: "acct-2",
      site_id: "site-2",
    });
    expect(hoisted.listTaskSystemConfigAuditLogsMock).toHaveBeenLastCalledWith({
      account_id: "acct-2",
      site_id: "site-2",
    });
    expect(Array.from(siteSelect?.options ?? []).map((option) => option.value)).toContain("site-2");
    expect(Array.from(siteSelect?.options ?? []).map((option) => option.value)).not.toContain("site-1");
  });
});
