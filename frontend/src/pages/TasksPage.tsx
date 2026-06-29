import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import {
  Button,
  Checkbox,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { PlusOutlined, ReloadOutlined, SearchOutlined } from "@ant-design/icons";

import { showError, showSuccess } from "../components/Feedback";
import { MemberIdLink } from "../components/member/MemberIdLink";
import { PageShell } from "../components/PageShell";
import { MemberTaskQuotaPanel } from "../components/tasks/MemberTaskQuotaPanel";
import { TaskAmountAllocationPreview } from "../components/tasks/TaskAmountAllocationPreview";
import { TaskInstanceDetailDrawer } from "../components/tasks/TaskInstanceDetailDrawer";
import { TaskIssuePlanEditor } from "../components/tasks/TaskIssuePlanEditor";
import { TaskManualAddDrawer } from "../components/tasks/TaskManualAddDrawer";
import { TaskMonitorPanel } from "../components/tasks/TaskMonitorPanel";
import { TaskProductPoolEditor } from "../components/tasks/TaskProductPoolEditor";
import { TaskSystemConfigPanel } from "../components/tasks/TaskSystemConfigPanel";
import { usePageData } from "../hooks/usePageData";
import {
  acknowledgeTaskMonitorAlertEvent,
  approveTaskReview,
  createTaskAlertRule,
  createTaskIssuePlan,
  createTaskMonitorSavedView,
  addTaskProductPoolItems,
  batchCreateTaskQuotas,
  deleteTaskAlertRule,
  deleteTaskProductPoolItem,
  deleteTaskMonitorSavedView,
  createTaskProductPool,
  createTaskQuota,
  generateTaskQuotaBatch,
  createTaskPackageManualAdd,
  cancelTaskPackage,
  createTaskTemplate,
  getTaskSystemConfig,
  listTaskMonitorAlertEvents,
  getTaskPackageDetail,
  listTaskManualAddLogs,
  listTaskSystemConfigAuditLogs,
  listMetaAccounts,
  listTaskAlertRules,
  listTaskMonitorRows,
  listTaskIssuePlans,
  listTaskMonitorSavedViews,
  listTaskProductPools,
  listTaskQuotas,
  listTaskGenerationRuns,
  listTaskInstances,
  listTaskPackageManualAddCandidates,
  listTaskPackages,
  listTaskTemplates,
  patchTaskSystemConfig,
  pauseTaskPackage,
  pauseNextTaskPackageQuota,
  previewBatchTaskQuotas,
  previewTaskPackageManualAdd,
  previewTaskQuotaAllocation,
  rejectTaskReview,
  retryTaskGenerationRun,
  resumeTaskPackage,
  resolveTaskMonitorAlertEvent,
  enableTaskIssuePlan,
  disableTaskIssuePlan,
  updateTaskAlertRule,
  updateTaskMonitorSavedView,
  getTaskMonitorSummary,
  type MetaWabaAccount,
  type TaskMonitorAlertEvent,
  type TaskInstance,
  type TaskManualAddCandidate,
  type TaskManualAddLog,
  type TaskManualAddPreviewResponse,
  type TaskPackageAdminDetail,
  type TaskPackageAdminListItem,
  type TaskGenerationRun,
  type TaskIssuePlan,
  type TaskIssuePlanCreatePayload,
  type TaskMonitorRow,
  type TaskMonitorQueryParams,
  type TaskMonitorSummary,
  type TaskSystemConfig,
  type TaskSystemConfigAuditLog,
  type TaskAlertRule,
  type TaskMonitorSavedView,
  type TaskProductPool,
  type TaskQuota,
  type TaskQuotaBatchPreviewResponse,
  type TaskQuotaCreatePayload,
  type TaskQuotaBatchCreatePayload,
} from "../services/api";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";
import {
  listPlatformUserMemberStatusIndex,
  type PlatformUserMemberStatusSummary,
} from "../services/operations";
import { playTaskMonitorAlertSound } from "../services/taskMonitorAlertSound";
import { taskMonitorAlertRealtime } from "../services/taskMonitorAlertRealtime";
import { useAppStore } from "../stores/appStore";
import { withSorter } from "../utils/withSorter";

export const TASK_AMOUNT_ALLOCATION_MODE_OPTIONS = [
  { label: "Average", value: "average" },
  { label: "Incremental", value: "incremental" },
  { label: "Manual", value: "manual" },
] as const;

export const TASK_PRODUCT_COUNT_MODE_OPTIONS = [
  { label: "Fixed", value: "fixed" },
  { label: "Range", value: "range" },
] as const;

export const TASK_PLAN_CLAIM_GATE_OPTIONS = [
  { label: "Certified Member", value: "certified_member" },
  { label: "WhatsApp Bound", value: "whatsapp_bound" },
  { label: "None", value: "none" },
] as const;

export const TASK_PLAN_ISSUE_ANCHOR_OPTIONS = [
  { label: "Certified At", value: "certified_at" },
  { label: "Registered At", value: "registered_at" },
  { label: "Bound At", value: "bound_at" },
] as const;

export const TASK_PLAN_ISSUE_MODE_OPTIONS = [
  { label: "Calendar Day", value: "calendar_day" },
  { label: "Elapsed Delay", value: "elapsed_delay" },
] as const;

export const TASK_PLAN_AFTER_LAST_RULE_MODE_OPTIONS = [
  { label: "Arithmetic Growth", value: "arithmetic_growth" },
  { label: "Repeat Last", value: "repeat_last" },
  { label: "Stop", value: "stop" },
] as const;

const TEMPLATE_STATUS_COLORS: Record<string, string> = {
  active: "green",
  draft: "default",
  disabled: "red",
};

const TEMPLATE_STATUS_LABELS: Record<string, string> = {
  active: "Active",
  draft: "Draft",
  disabled: "Disabled",
};

const INSTANCE_STATUS_COLORS: Record<string, string> = {
  pending: "default",
  claimed: "blue",
  active: "blue",
  submitted: "orange",
  approved: "green",
  rejected: "red",
  completed: "green",
  expired: "default",
  paused: "orange",
  cancelled: "red",
};

const INSTANCE_STATUS_LABELS: Record<string, string> = {
  pending: "pending",
  claimed: "claimed",
  active: "active",
  submitted: "submitted",
  approved: "approved",
  rejected: "rejected",
  completed: "completed",
  expired: "expired",
  paused: "paused",
  cancelled: "cancelled",
};

function renderMemberTag(status: string | null | undefined): JSX.Element {
  if (!status) {
    return <Tag>-</Tag>;
  }
  const color =
    status === "approved" || status === "bound"
      ? "green"
      : status === "rejected" || status === "failed"
        ? "red"
        : "blue";
  return <Tag color={color}>{status}</Tag>;
}

const QUOTA_STATUS_COLORS: Record<string, string> = {
  pending: "default",
  locked: "blue",
  completed: "green",
};

const QUOTA_STATUS_LABELS: Record<string, string> = {
  pending: "\u5f85\u4e0b\u53d1",
  locked: "\u5df2\u9501\u5b9a",
  completed: "\u5df2\u5b8c\u6210",
};

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleDateString("zh-CN");
}

function formatMoney(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function parseManualPackageAmounts(value: unknown): string[] {
  if (typeof value !== "string") {
    return [];
  }
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseBatchUserIds(value: unknown): string[] {
  if (typeof value !== "string") {
    return [];
  }
  return Array.from(
    new Set(
      value
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function parseBatchTagKeys(value: unknown): string[] {
  if (typeof value !== "string") {
    return [];
  }
  return Array.from(
    new Set(
      value
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function hasBatchSelectorFilters(payload: TaskQuotaBatchCreatePayload): boolean {
  return Boolean(
    (payload.user_ids && payload.user_ids.length > 0) ||
      payload.owner_staff_user_id ||
      payload.certified_status ||
      payload.tag_ids?.length ||
      payload.tag_keys?.length ||
      payload.min_total_real_recharge ||
      payload.max_total_real_recharge,
  );
}

type QuotaFormValues = {
  account_id: string;
  user_id: string;
  site_id?: string;
  day_no: number;
  package_count: number;
  day_total_amount: number;
  tolerance_amount?: number;
  amount_allocation_mode?: string;
  package_amounts_text?: string;
  product_pool_id: string;
  product_count_mode?: string;
  product_count_fixed?: number;
  product_count_min?: number;
  product_count_max?: number;
  reward_ratio?: number;
};

type QuotaBatchFormValues = Omit<QuotaFormValues, "user_id"> & {
  user_ids_text: string;
  owner_staff_user_id?: string;
  certified_status?: "certified" | "uncertified";
  min_total_real_recharge?: number;
  max_total_real_recharge?: number;
  tag_keys_text?: string;
};

type QuotaBatchPreviewSummary = {
  user_count: number;
  total_quota_count: number;
  package_amounts: string[];
  computed_total_amount: string;
  total_batch_amount: string;
  reward_ratio?: string;
  product_pool_id: string;
};

type IssuePlanFormValues = {
  account_id: string;
  site_id?: string;
  name: string;
  claim_gate?: string;
  issue_anchor?: string;
  issue_mode?: string;
  require_previous_batch_completed?: boolean;
  max_unfinished_batches?: number;
  after_last_rule_mode?: string;
  growth_package_count_step?: number;
  growth_amount_step?: number;
  default_product_pool_id?: string;
  first_day_package_count: number;
  first_day_total_amount: number;
  default_tolerance_amount?: number;
  default_reward_ratio?: number;
  first_day_amount_allocation_mode?: string;
  first_day_package_amounts_text?: string;
  first_day_product_count_mode?: string;
  first_day_product_count_fixed?: number;
  first_day_product_count_min?: number;
  first_day_product_count_max?: number;
  first_day_reward_ratio?: number;
  first_day_issue_time_of_day?: string;
  first_day_elapsed_delay_hours?: number;
};

export function buildTaskQuotaCreatePayload(values: QuotaFormValues): TaskQuotaCreatePayload {
  const amountAllocationMode = values.amount_allocation_mode || "average";
  const productCountMode = values.product_count_mode === "fixed" ? "fixed" : "range";
  return {
    account_id: values.account_id,
    user_id: values.user_id,
    site_id: values.site_id,
    day_no: values.day_no,
    package_count: values.package_count,
    day_total_amount: String(values.day_total_amount),
    tolerance_amount: values.tolerance_amount !== undefined ? String(values.tolerance_amount) : undefined,
    amount_allocation_mode: amountAllocationMode,
    package_amounts: amountAllocationMode === "manual" ? parseManualPackageAmounts(values.package_amounts_text) : undefined,
    product_pool_id: values.product_pool_id,
    product_count_mode: productCountMode,
    product_count_fixed: productCountMode === "fixed" ? values.product_count_fixed : undefined,
    product_count_min: productCountMode === "range" ? values.product_count_min : undefined,
    product_count_max: productCountMode === "range" ? values.product_count_max : undefined,
    reward_ratio: values.reward_ratio !== undefined ? String(values.reward_ratio) : undefined,
  };
}

export function buildTaskQuotaBatchCreatePayload(values: QuotaBatchFormValues): TaskQuotaBatchCreatePayload {
  const amountAllocationMode = values.amount_allocation_mode || "average";
  const productCountMode = values.product_count_mode === "fixed" ? "fixed" : "range";
  return {
    account_id: values.account_id,
    user_ids: parseBatchUserIds(values.user_ids_text),
    site_id: values.site_id,
    day_no: values.day_no,
    package_count: values.package_count,
    day_total_amount: String(values.day_total_amount),
    tolerance_amount: values.tolerance_amount !== undefined ? String(values.tolerance_amount) : undefined,
    amount_allocation_mode: amountAllocationMode,
    package_amounts: amountAllocationMode === "manual" ? parseManualPackageAmounts(values.package_amounts_text) : undefined,
    product_pool_id: values.product_pool_id,
    product_count_mode: productCountMode,
    product_count_fixed: productCountMode === "fixed" ? values.product_count_fixed : undefined,
    product_count_min: productCountMode === "range" ? values.product_count_min : undefined,
    product_count_max: productCountMode === "range" ? values.product_count_max : undefined,
    reward_ratio: values.reward_ratio !== undefined ? String(values.reward_ratio) : undefined,
    owner_staff_user_id: values.owner_staff_user_id || undefined,
    certified_status: values.certified_status || undefined,
    min_total_real_recharge:
      values.min_total_real_recharge !== undefined ? String(values.min_total_real_recharge) : undefined,
    max_total_real_recharge:
      values.max_total_real_recharge !== undefined ? String(values.max_total_real_recharge) : undefined,
    tag_keys: parseBatchTagKeys(values.tag_keys_text),
  };
}

function compactTaskMonitorQueryParams(params: TaskMonitorQueryParams): TaskMonitorQueryParams {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  ) as TaskMonitorQueryParams;
}

function normalizeTaskMonitorQueryParams(input: Record<string, unknown> | null | undefined): TaskMonitorQueryParams {
  if (!input) {
    return {};
  }
  const readString = (key: keyof TaskMonitorQueryParams): string | undefined => {
    const value = input[key];
    return typeof value === "string" && value.trim().length > 0 ? value.trim() : undefined;
  };
  const readBoolean = (key: keyof TaskMonitorQueryParams): boolean | undefined => {
    const value = input[key];
    return typeof value === "boolean" ? value : undefined;
  };
  return compactTaskMonitorQueryParams({
    user_id: readString("user_id"),
    user_query: readString("user_query"),
    status: readString("status"),
    day_planned_amount_min: readString("day_planned_amount_min"),
    day_planned_amount_max: readString("day_planned_amount_max"),
    day_manual_added_amount_min: readString("day_manual_added_amount_min"),
    day_manual_added_amount_max: readString("day_manual_added_amount_max"),
    day_effective_amount_min: readString("day_effective_amount_min"),
    day_effective_amount_max: readString("day_effective_amount_max"),
    latest_manual_add_operator_id: readString("latest_manual_add_operator_id"),
    planned_amount_min: readString("planned_amount_min"),
    planned_amount_max: readString("planned_amount_max"),
    manual_added_amount_min: readString("manual_added_amount_min"),
    manual_added_amount_max: readString("manual_added_amount_max"),
    effective_amount_min: readString("effective_amount_min"),
    effective_amount_max: readString("effective_amount_max"),
    has_manual_add: readBoolean("has_manual_add"),
    current_product_amount_min: readString("current_product_amount_min"),
    current_product_amount_max: readString("current_product_amount_max"),
    total_recharge_amount_min: readString("total_recharge_amount_min"),
    total_recharge_amount_max: readString("total_recharge_amount_max"),
    total_withdraw_amount_min: readString("total_withdraw_amount_min"),
    total_withdraw_amount_max: readString("total_withdraw_amount_max"),
  });
}

export function buildTaskQuotaBatchPreviewSummary(
  values: QuotaBatchFormValues,
  package_amounts: string[],
  computed_total_amount: string,
): QuotaBatchPreviewSummary {
  const userCount = parseBatchUserIds(values.user_ids_text).length;
  const totalBatchAmount = userCount * Number(values.day_total_amount || 0);
  return {
    user_count: userCount,
    total_quota_count: userCount,
    package_amounts,
    computed_total_amount,
    total_batch_amount: String(totalBatchAmount),
    reward_ratio: values.reward_ratio !== undefined ? String(values.reward_ratio) : undefined,
    product_pool_id: values.product_pool_id,
  };
}

export function buildTaskIssuePlanCreatePayload(values: IssuePlanFormValues): TaskIssuePlanCreatePayload {
  const defaultToleranceAmount = values.default_tolerance_amount !== undefined ? String(values.default_tolerance_amount) : "10.00";
  const defaultRewardRatio = values.default_reward_ratio !== undefined ? String(values.default_reward_ratio) : "0.20";
  const firstDayAmountAllocationMode = values.first_day_amount_allocation_mode || "average";
  const firstDayProductCountMode = values.first_day_product_count_mode === "fixed" ? "fixed" : "range";
  const claimGate = values.claim_gate || "certified_member";
  const issueAnchor = values.issue_anchor || "certified_at";
  const issueMode = values.issue_mode || "calendar_day";
  const requirePreviousBatchCompleted = values.require_previous_batch_completed ?? true;
  const maxUnfinishedBatches = values.max_unfinished_batches ?? 1;
  const afterLastRuleMode = values.after_last_rule_mode || "arithmetic_growth";
  const growthPackageCountStep = values.growth_package_count_step ?? 1;
  const growthAmountStep = values.growth_amount_step !== undefined ? String(values.growth_amount_step) : "0.00";
  return {
    account_id: values.account_id,
    site_id: values.site_id,
    name: values.name,
    plan_type: "official",
    status: "active",
    claim_gate: claimGate,
    issue_anchor: issueAnchor,
    issue_mode: issueMode,
    require_previous_batch_completed: requirePreviousBatchCompleted,
    max_unfinished_batches: maxUnfinishedBatches,
    after_last_rule_mode: afterLastRuleMode,
    growth_package_count_step: growthPackageCountStep,
    growth_amount_step: growthAmountStep,
    default_product_pool_id: values.default_product_pool_id,
    default_tolerance_amount: defaultToleranceAmount,
    default_reward_ratio: defaultRewardRatio,
    day_rules: [
      {
        day_no: 1,
        package_count: values.first_day_package_count,
        day_total_amount: String(values.first_day_total_amount),
        tolerance_amount: defaultToleranceAmount,
        amount_allocation_mode: firstDayAmountAllocationMode,
        package_amounts_json:
          firstDayAmountAllocationMode === "manual"
            ? parseManualPackageAmounts(values.first_day_package_amounts_text)
            : [],
        product_pool_id: values.default_product_pool_id,
        product_count_mode: firstDayProductCountMode,
        product_count_fixed: firstDayProductCountMode === "fixed" ? values.first_day_product_count_fixed : undefined,
        product_count_min: firstDayProductCountMode === "range" ? values.first_day_product_count_min : undefined,
        product_count_max: firstDayProductCountMode === "range" ? values.first_day_product_count_max : undefined,
        reward_ratio: values.first_day_reward_ratio !== undefined ? String(values.first_day_reward_ratio) : defaultRewardRatio,
        issue_time_of_day: values.first_day_issue_time_of_day || undefined,
        elapsed_delay_hours: values.first_day_elapsed_delay_hours,
        status: "active",
      },
    ],
  };
}

export function TasksPage(): JSX.Element {
  const openCustomersPage = useAppStore((state) => state.openCustomersPage);
  const seenAlertEventIdsRef = useRef<Set<string>>(new Set());
  const realtimeBaselineReadyRef = useRef(false);

  const [activeTab, setActiveTab] = useState("templates");
  const [accounts, setAccounts] = useState<MetaWabaAccount[]>([]);
  const [sites, setSites] = useState<H5Site[]>([]);

  const [tplFilterAccount, setTplFilterAccount] = useState<string | undefined>();
  const [tplFilterType, setTplFilterType] = useState<string | undefined>();
  const [tplFilterStatus, setTplFilterStatus] = useState<string | undefined>();

  const [instFilterAccount, setInstFilterAccount] = useState<string | undefined>();
  const [instFilterStatus, setInstFilterStatus] = useState<string | undefined>();
  const [instSearchUser, setInstSearchUser] = useState("");

  const [pkgFilterAccount, setPkgFilterAccount] = useState<string | undefined>();
  const [pkgFilterStatus, setPkgFilterStatus] = useState<string | undefined>();
  const [quotaFilterAccount, setQuotaFilterAccount] = useState<string | undefined>();
  const [poolFilterAccount, setPoolFilterAccount] = useState<string | undefined>();
  const [monitorFilterAccount, setMonitorFilterAccount] = useState<string | undefined>();
  const [monitorDraftFilters, setMonitorDraftFilters] = useState<TaskMonitorQueryParams>({});
  const [monitorAppliedFilters, setMonitorAppliedFilters] = useState<TaskMonitorQueryParams>({});
  const [planFilterAccount, setPlanFilterAccount] = useState<string | undefined>();
  const [settingsAccountId, setSettingsAccountId] = useState<string | undefined>();
  const [settingsSiteId, setSettingsSiteId] = useState<string | undefined>();
  const [taskSystemConfig, setTaskSystemConfig] = useState<TaskSystemConfig | null>(null);
  const [taskSystemConfigAuditLogs, setTaskSystemConfigAuditLogs] = useState<TaskSystemConfigAuditLog[]>([]);
  const [taskSystemConfigSaving, setTaskSystemConfigSaving] = useState(false);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [creating, setCreating] = useState(false);
  const [quotaCreateOpen, setQuotaCreateOpen] = useState(false);
  const [quotaCreateForm] = Form.useForm();
  const [quotaCreating, setQuotaCreating] = useState(false);
  const [quotaBatchCreateOpen, setQuotaBatchCreateOpen] = useState(false);
  const [quotaBatchCreateForm] = Form.useForm();
  const [quotaBatchCreating, setQuotaBatchCreating] = useState(false);
  const [quotaBatchPreviewLoading, setQuotaBatchPreviewLoading] = useState(false);
  const [quotaBatchPreview, setQuotaBatchPreview] = useState<TaskQuotaBatchPreviewResponse | null>(null);
  const [quotaPreviewLoading, setQuotaPreviewLoading] = useState(false);
  const [quotaPreview, setQuotaPreview] = useState<string[]>([]);
  const [quotaPreviewTotal, setQuotaPreviewTotal] = useState<string | null>(null);
  const [quotaProductCountMode, setQuotaProductCountMode] = useState<"fixed" | "range">("range");
  const [quotaBatchProductCountMode, setQuotaBatchProductCountMode] = useState<"fixed" | "range">("range");
  const [planCreateOpen, setPlanCreateOpen] = useState(false);
  const [planCreateForm] = Form.useForm();
  const [planCreating, setPlanCreating] = useState(false);
  const [planProductCountMode, setPlanProductCountMode] = useState<"fixed" | "range">("range");
  const [savedViewCreateOpen, setSavedViewCreateOpen] = useState(false);
  const [savedViewCreateForm] = Form.useForm();
  const [savedViewCreating, setSavedViewCreating] = useState(false);
  const [alertRuleCreateOpen, setAlertRuleCreateOpen] = useState(false);
  const [alertRuleCreateForm] = Form.useForm();
  const [alertRuleCreating, setAlertRuleCreating] = useState(false);
  const [poolCreateOpen, setPoolCreateOpen] = useState(false);
  const [poolCreateForm] = Form.useForm();
  const [poolCreating, setPoolCreating] = useState(false);
  const [poolItemsOpen, setPoolItemsOpen] = useState(false);
  const [poolItemsTarget, setPoolItemsTarget] = useState<TaskProductPool | null>(null);
  const [poolItemCreateForm] = Form.useForm();
  const [poolItemCreating, setPoolItemCreating] = useState(false);
  const [planActionLoadingId, setPlanActionLoadingId] = useState<string | null>(null);
  const [generationActionKey, setGenerationActionKey] = useState<string | null>(null);

  const [packageDetailOpen, setPackageDetailOpen] = useState(false);
  const [packageDetailLoading, setPackageDetailLoading] = useState(false);
  const [packageDetail, setPackageDetail] = useState<TaskPackageAdminDetail | null>(null);

  const [manualAddOpen, setManualAddOpen] = useState(false);
  const [manualAddLoading, setManualAddLoading] = useState(false);
  const [manualAddSubmitting, setManualAddSubmitting] = useState(false);
  const [manualAddPackageId, setManualAddPackageId] = useState<string | null>(null);
  const [manualAddCandidates, setManualAddCandidates] = useState<TaskManualAddCandidate[]>([]);
  const [manualAddReason, setManualAddReason] = useState("");
  const [manualAddSelectedIds, setManualAddSelectedIds] = useState<string[]>([]);
  const [manualAddPreviewLoading, setManualAddPreviewLoading] = useState(false);
  const [manualAddPreview, setManualAddPreview] = useState<TaskManualAddPreviewResponse | null>(null);
  const [manualLogPackageId, setManualLogPackageId] = useState<string | undefined>();

  useEffect(() => {
    listSites().then(setSites).catch(() => undefined);
    listMetaAccounts({}).then(setAccounts).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!settingsAccountId && accounts.length > 0) {
      setSettingsAccountId(accounts[0]?.account_id);
    }
  }, [accounts, settingsAccountId]);

  const accountOptions = useMemo(
    () => accounts.map((item) => ({ label: item.display_name, value: item.account_id })),
    [accounts],
  );

  const settingsScopedSites = useMemo(() => {
    if (!settingsAccountId) {
      return sites;
    }
    const matchedSites = sites.filter((site) => site.account_id === settingsAccountId);
    if (matchedSites.length > 0) {
      return matchedSites;
    }
    return sites.filter((site) => !site.account_id);
  }, [settingsAccountId, sites]);

  const settingsSiteOptions = useMemo(
    () =>
      settingsScopedSites
        .filter((site): site is H5Site & { id: string } => typeof site.id === "string" && site.id.length > 0)
        .map((site) => ({ label: site.brand_name || site.site_key, value: site.id })),
    [settingsScopedSites],
  );

  useEffect(() => {
    if (settingsScopedSites.length === 0) {
      if (settingsSiteId) {
        setSettingsSiteId(undefined);
      }
      return;
    }
    const hasCurrentSite = Boolean(settingsSiteId)
      && settingsScopedSites.some((site) => site.id === settingsSiteId);
    if (!hasCurrentSite) {
      setSettingsSiteId(settingsScopedSites[0]?.id);
    }
  }, [settingsScopedSites, settingsSiteId]);

  const fetchTemplates = useCallback(async () => {
    const templates = await listTaskTemplates({
      account_id: tplFilterAccount,
      status: tplFilterStatus,
      task_type: tplFilterType,
    });
    return { templates };
  }, [tplFilterAccount, tplFilterStatus, tplFilterType]);
  const tplData = usePageData({ fetcher: fetchTemplates });
  const templates = tplData.data?.templates ?? [];

  const fetchInstances = useCallback(async () => {
    const instances = await listTaskInstances({
      account_id: instFilterAccount,
      status: instFilterStatus,
    });
    const taskInstanceMemberStatusIndex = await listPlatformUserMemberStatusIndex(
      instances.map((record) => ({
        id: record.user_id,
        account_id: record.account_id,
        public_user_id: record.public_user_id,
      })),
      instFilterAccount,
    );
    return { instances, taskInstanceMemberStatusIndex };
  }, [instFilterAccount, instFilterStatus]);
  const instData = usePageData({
    fetcher: fetchInstances,
    deps: [instFilterAccount, instFilterStatus],
  });
  const instances = instData.data?.instances ?? [];
  const taskInstanceMemberStatusIndex: Record<string, PlatformUserMemberStatusSummary> =
    instData.data?.taskInstanceMemberStatusIndex ?? {};
  // Contract marker: title: "浼氬憳璁よ瘉"
  // Contract marker: title: "WhatsApp 缁戝畾"
  // Contract marker: title: "娴兼艾鎲崇拋銈堢槈"
  // Contract marker: title: "WhatsApp 缂佹垵鐣?

  const fetchPackages = useCallback(async () => {
    const packages = await listTaskPackages({
      account_id: pkgFilterAccount,
      status: pkgFilterStatus,
    });
    return { packages };
  }, [pkgFilterAccount, pkgFilterStatus]);
  const pkgData = usePageData({ fetcher: fetchPackages, deps: [pkgFilterAccount, pkgFilterStatus] });
  const packages = pkgData.data?.packages ?? [];

  useEffect(() => {
    if (!manualLogPackageId && packages.length > 0) {
      setManualLogPackageId(packages[0]?.id);
    }
  }, [manualLogPackageId, packages]);

  const fetchManualAddLogs = useCallback(async () => {
    if (!manualLogPackageId) {
      return { manualAddLogs: [] as TaskManualAddLog[] };
    }
    const manualAddLogs = await listTaskManualAddLogs(manualLogPackageId);
    return { manualAddLogs };
  }, [manualLogPackageId]);
  const manualAddLogData = usePageData({ fetcher: fetchManualAddLogs, deps: [manualLogPackageId] });
  const manualAddLogs = manualAddLogData.data?.manualAddLogs ?? [];

  const fetchQuotas = useCallback(async () => {
    const quotas = await listTaskQuotas({
      account_id: quotaFilterAccount,
    });
    return { quotas };
  }, [quotaFilterAccount]);
  const quotaData = usePageData({ fetcher: fetchQuotas, deps: [quotaFilterAccount] });
  const quotas = quotaData.data?.quotas ?? [];

  const fetchProductPools = useCallback(async () => {
    const productPools = await listTaskProductPools({
      account_id: poolFilterAccount,
    });
    return { productPools };
  }, [poolFilterAccount]);
  const poolData = usePageData({ fetcher: fetchProductPools, deps: [poolFilterAccount] });
  const productPools = poolData.data?.productPools ?? [];

  const fetchGenerationRuns = useCallback(async () => {
    const generationRuns = await listTaskGenerationRuns({
      account_id: monitorFilterAccount,
    });
    return { generationRuns };
  }, [monitorFilterAccount]);
  const generationRunData = usePageData({ fetcher: fetchGenerationRuns, deps: [monitorFilterAccount] });
  const generationRuns = generationRunData.data?.generationRuns ?? [];

  const monitorQueryParams = useMemo(
    () =>
      compactTaskMonitorQueryParams({
        account_id: monitorFilterAccount,
        ...monitorAppliedFilters,
      }),
    [monitorAppliedFilters, monitorFilterAccount],
  );

  const fetchMonitorRows = useCallback(async () => {
    const [monitorRows, monitorSummary] = await Promise.all([
      listTaskMonitorRows(monitorQueryParams),
      getTaskMonitorSummary(monitorQueryParams),
    ]);
    return { monitorRows, monitorSummary };
  }, [monitorQueryParams]);
  const monitorData = usePageData({ fetcher: fetchMonitorRows, deps: [JSON.stringify(monitorQueryParams)] });
  const monitorRows = monitorData.data?.monitorRows ?? [];
  const monitorSummary: TaskMonitorSummary | null = monitorData.data?.monitorSummary ?? null;

  const fetchMonitorConfigs = useCallback(async () => {
    const [savedViews, alertRules, alertEvents] = await Promise.all([
      listTaskMonitorSavedViews({
        account_id: monitorFilterAccount,
      }),
      listTaskAlertRules({
        account_id: monitorFilterAccount,
      }),
      listTaskMonitorAlertEvents({
        account_id: monitorFilterAccount,
      }),
    ]);
    return { savedViews, alertRules, alertEvents };
  }, [monitorFilterAccount]);
  const monitorConfigData = usePageData({ fetcher: fetchMonitorConfigs, deps: [monitorFilterAccount] });
  const savedViews = monitorConfigData.data?.savedViews ?? [];
  const alertRules = monitorConfigData.data?.alertRules ?? [];
  const alertEvents = monitorConfigData.data?.alertEvents ?? [];
  const setMonitorConfigPageData = monitorConfigData.setData;

  const handleMonitorFilterChange = useCallback((patch: Partial<TaskMonitorQueryParams>): void => {
    setMonitorDraftFilters((prev) => compactTaskMonitorQueryParams({ ...prev, ...patch }));
  }, []);

  const handleApplyMonitorFilters = useCallback((): void => {
    setMonitorAppliedFilters(compactTaskMonitorQueryParams(monitorDraftFilters));
  }, [monitorDraftFilters]);

  const handleResetMonitorFilters = useCallback((): void => {
    setMonitorDraftFilters({});
    setMonitorAppliedFilters({});
  }, []);

  useEffect(() => {
    const defaultSavedView = savedViews.find((item) => item.is_default) ?? savedViews[0];
    const refreshSeconds = defaultSavedView?.refresh_seconds ?? 0;
    if (refreshSeconds <= 0) {
      return undefined;
    }
    const timerId = window.setInterval(() => {
      void monitorData.reload();
      void monitorConfigData.reload();
    }, refreshSeconds * 1000);
    return () => window.clearInterval(timerId);
  }, [monitorConfigData, monitorData, savedViews]);

  useEffect(() => {
    taskMonitorAlertRealtime.connect({
      accountId: monitorFilterAccount,
      onSnapshot: (events) => {
        const openSoundEnabledIds = events
          .filter((event) => event.status === "open" && event.sound_enabled)
          .map((event) => event.id);
        if (realtimeBaselineReadyRef.current) {
          const hasNewSoundEnabledAlert = openSoundEnabledIds.some(
            (id) => !seenAlertEventIdsRef.current.has(id),
          );
          if (hasNewSoundEnabledAlert) {
            playTaskMonitorAlertSound();
          }
        }
        seenAlertEventIdsRef.current = new Set(openSoundEnabledIds);
        realtimeBaselineReadyRef.current = true;
        setMonitorConfigPageData((current) => {
          if (!current) {
            return current;
          }
          return {
            ...current,
            alertEvents: events,
          };
        });
      },
    });
    return () => {
      taskMonitorAlertRealtime.disconnect();
      seenAlertEventIdsRef.current = new Set();
      realtimeBaselineReadyRef.current = false;
    };
  }, [monitorFilterAccount, setMonitorConfigPageData]);

  const fetchIssuePlans = useCallback(async () => {
    const issuePlans = await listTaskIssuePlans({
      account_id: planFilterAccount,
    });
    return { issuePlans };
  }, [planFilterAccount]);
  const planData = usePageData({ fetcher: fetchIssuePlans, deps: [planFilterAccount] });
  const issuePlans = planData.data?.issuePlans ?? [];

  const fetchTaskSystemConfig = useCallback(async () => {
    if (!settingsAccountId) {
      return {
        taskSystemConfig: null as TaskSystemConfig | null,
        taskSystemConfigAuditLogs: [] as TaskSystemConfigAuditLog[],
      };
    }
    const [config, auditLogs] = await Promise.all([
      getTaskSystemConfig({
        account_id: settingsAccountId,
        site_id: settingsSiteId,
      }),
      listTaskSystemConfigAuditLogs({
        account_id: settingsAccountId,
        site_id: settingsSiteId,
      }),
    ]);
    return { taskSystemConfig: config, taskSystemConfigAuditLogs: auditLogs };
  }, [settingsAccountId, settingsSiteId]);
  const settingsData = usePageData({
    fetcher: fetchTaskSystemConfig,
    deps: [settingsAccountId, settingsSiteId],
  });

  const fetchReviews = useCallback(async () => {
    const reviews = await listTaskInstances({ status: "submitted" });
    return { reviews };
  }, []);
  const reviewData = usePageData({ fetcher: fetchReviews });
  const reviews = reviewData.data?.reviews ?? [];

  useEffect(() => {
    setTaskSystemConfig(settingsData.data?.taskSystemConfig ?? null);
    setTaskSystemConfigAuditLogs(settingsData.data?.taskSystemConfigAuditLogs ?? []);
  }, [settingsData.data]);

  const filteredInstances = useMemo(() => {
    if (!instSearchUser.trim()) {
      return instances;
    }
    const query = instSearchUser.toLowerCase();
    return instances.filter((item) => item.public_user_id.toLowerCase().includes(query));
  }, [instances, instSearchUser]);

  const refreshAll = useCallback(() => {
    void tplData.reload();
    void instData.reload();
    void pkgData.reload();
    void quotaData.reload();
    void poolData.reload();
    void generationRunData.reload();
    void monitorData.reload();
    void monitorConfigData.reload();
    void planData.reload();
    void reviewData.reload();
    void settingsData.reload();
  }, [generationRunData, instData, monitorConfigData, monitorData, pkgData, planData, poolData, quotaData, reviewData, settingsData, tplData]);

  const updateTaskSystemConfig = useCallback(
    (patch: Partial<TaskSystemConfig>) => {
      setTaskSystemConfig((current) => (current ? { ...current, ...patch } : current));
    },
    [],
  );

  const handleSaveTaskSystemConfig = async (): Promise<void> => {
    if (!taskSystemConfig) {
      showError("Task system configuration is not loaded");
      return;
    }
    setTaskSystemConfigSaving(true);
    try {
      const saved = await patchTaskSystemConfig({
        account_id: taskSystemConfig.accountId,
        site_id: taskSystemConfig.siteId ?? undefined,
        status: taskSystemConfig.status,
        whatsapp_binding_reward_enabled: taskSystemConfig.whatsappBindingRewardEnabled,
        whatsapp_binding_reward_amount: taskSystemConfig.whatsappBindingRewardAmount,
        whatsapp_binding_reward_wallet_type: taskSystemConfig.whatsappBindingRewardWalletType,
        whatsapp_binding_reward_currency: taskSystemConfig.whatsappBindingRewardCurrency,
        certified_member_enabled: taskSystemConfig.certifiedMemberEnabled,
        certified_recharge_threshold: taskSystemConfig.certifiedRechargeThreshold,
        certified_recharge_scope: taskSystemConfig.certifiedRechargeScope,
        auto_certify_on_recharge: taskSystemConfig.autoCertifyOnRecharge,
        newbie_task_enabled: taskSystemConfig.newbieTaskEnabled,
        newbie_plan_id: taskSystemConfig.newbiePlanId ?? undefined,
        newbie_auto_popup: taskSystemConfig.newbieAutoPopup,
        official_plan_id: taskSystemConfig.officialPlanId ?? undefined,
        show_task_balance_transfer_prompt: taskSystemConfig.showTaskBalanceTransferPrompt,
        min_task_balance_transfer_prompt_amount: taskSystemConfig.minTaskBalanceTransferPromptAmount,
        max_active_batches_per_user: taskSystemConfig.maxActiveBatchesPerUser,
        max_active_packages_per_user: taskSystemConfig.maxActivePackagesPerUser,
        metadata_json: taskSystemConfig.metadataJson,
      });
      setTaskSystemConfig(saved);
      showSuccess("Task system settings saved");
      void settingsData.reload();
    } catch {
      showError("Failed to save task system settings");
    } finally {
      setTaskSystemConfigSaving(false);
    }
  };

  const resetManualAddState = (): void => {
    setManualAddOpen(false);
    setManualAddPackageId(null);
    setManualAddCandidates([]);
    setManualAddReason("");
    setManualAddSelectedIds([]);
    setManualAddPreview(null);
    setManualAddLoading(false);
    setManualAddPreviewLoading(false);
    setManualAddSubmitting(false);
  };

  const handleCreateTemplate = async (values: {
    name: string;
    task_type: string;
    account_id?: string;
    reward_amount?: number;
    description?: string;
  }): Promise<void> => {
    setCreating(true);
    try {
      await createTaskTemplate({
        account_id: values.account_id,
        task_key: `tpl-${Date.now()}`,
        name: values.name,
        title: values.name,
        description: values.description,
        task_type: values.task_type,
        status: "draft",
        reward_amount: values.reward_amount?.toString(),
        reward_points: 0,
        claim_timeout_seconds: 86400,
        auto_review_enabled: false,
      });
      showSuccess("Template created");
      setCreateModalOpen(false);
      createForm.resetFields();
      void tplData.reload();
    } catch {
      showError("Failed to create template");
    } finally {
      setCreating(false);
    }
  };

  const handleCreateQuota = async (values: QuotaFormValues): Promise<void> => {
    setQuotaCreating(true);
    try {
      await createTaskQuota(buildTaskQuotaCreatePayload(values));
      showSuccess("Quota created");
      setQuotaCreateOpen(false);
      setQuotaProductCountMode("range");
      quotaCreateForm.resetFields();
      void quotaData.reload();
    } catch {
      showError("Failed to create quota");
    } finally {
      setQuotaCreating(false);
    }
  };

  const handleBatchCreateQuota = async (values: QuotaBatchFormValues): Promise<void> => {
    setQuotaBatchCreating(true);
    try {
      const payload = buildTaskQuotaBatchCreatePayload(values);
      if ((payload.items?.length ?? 0) === 0 && !hasBatchSelectorFilters(payload)) {
        showError("Please provide at least one batch selector");
        return;
      }
      const created = await batchCreateTaskQuotas(payload);
      showSuccess(`Created ${created.length} quotas`);
      setQuotaBatchCreateOpen(false);
      setQuotaBatchProductCountMode("range");
      setQuotaBatchPreview(null);
      quotaBatchCreateForm.resetFields();
      void quotaData.reload();
    } catch {
      showError("Failed to batch create quotas");
    } finally {
      setQuotaBatchCreating(false);
    }
  };

  const handlePreviewBatchQuota = async (): Promise<void> => {
    const values = (quotaBatchCreateForm as { getFieldsValue?: () => Record<string, unknown> }).getFieldsValue?.();
    if (!values) {
      showError("Batch quota form is not ready");
      return;
    }
    if (!values.package_count || !values.day_total_amount || !values.product_pool_id) {
      showError("Package count, total amount, and product pool are required");
      return;
    }
    setQuotaBatchPreviewLoading(true);
    try {
      const payload = buildTaskQuotaBatchCreatePayload(values as QuotaBatchFormValues);
      if ((payload.items?.length ?? 0) === 0 && !hasBatchSelectorFilters(payload)) {
        showError("Please provide at least one batch selector");
        return;
      }
      const preview = await previewBatchTaskQuotas(payload);
      setQuotaBatchPreview(preview);
    } catch {
      showError("Failed to preview batch quotas");
    } finally {
      setQuotaBatchPreviewLoading(false);
    }
  };

  const handlePreviewQuota = async (): Promise<void> => {
    const values = (quotaCreateForm as { getFieldsValue?: () => Record<string, unknown> }).getFieldsValue?.();
    if (!values) {
      showError("Quota form is not ready");
      return;
    }
    if (!values.package_count || !values.day_total_amount) {
      showError("Package count and total amount are required");
      return;
    }
    setQuotaPreviewLoading(true);
    try {
      const amountAllocationMode = typeof values.amount_allocation_mode === "string" && values.amount_allocation_mode
        ? values.amount_allocation_mode
        : "average";
      const preview = await previewTaskQuotaAllocation({
        package_count: Number(values.package_count),
        day_total_amount: String(values.day_total_amount),
        amount_allocation_mode: amountAllocationMode,
        package_amounts: amountAllocationMode === "manual"
          ? parseManualPackageAmounts(values.package_amounts_text)
          : undefined,
      });
      setQuotaPreview(preview.packageAmounts);
      setQuotaPreviewTotal(preview.computedTotalAmount);
    } catch {
      showError("Failed to preview quota allocation");
    } finally {
      setQuotaPreviewLoading(false);
    }
  };

  const handleGenerateQuotaBatch = async (quota: TaskQuota): Promise<void> => {
    setGenerationActionKey(`quota:${quota.id}`);
    try {
      await generateTaskQuotaBatch(quota.id);
      showSuccess(`Generated batch for quota ${quota.id}`);
      void quotaData.reload();
      void generationRunData.reload();
    } catch {
      showError("Failed to generate quota batch");
    } finally {
      setGenerationActionKey(null);
    }
  };

  const handleOpenPoolItems = (pool: TaskProductPool): void => {
    setPoolItemsTarget(pool);
    setPoolItemsOpen(true);
  };

  const handleCreatePoolItem = async (values: {
    product_id: string;
    product_name: string;
    price: number;
    currency?: string;
    product_description?: string;
  }): Promise<void> => {
    if (!poolItemsTarget) {
      showError("No product pool selected");
      return;
    }
    setPoolItemCreating(true);
    try {
      const updatedPool = await addTaskProductPoolItems(poolItemsTarget.id, {
        items: [
          {
            productId: values.product_id,
            productName: values.product_name,
            price: String(values.price),
            currency: values.currency || poolItemsTarget.currency || "USD",
            productDescription: values.product_description,
          },
        ],
      });
      setPoolItemsTarget(updatedPool);
      poolItemCreateForm.resetFields();
      void poolData.reload();
    } catch {
      showError("Failed to add pool item");
    } finally {
      setPoolItemCreating(false);
    }
  };

  const handleDeletePoolItem = async (itemId: string): Promise<void> => {
    if (!poolItemsTarget) {
      return;
    }
    try {
      await deleteTaskProductPoolItem(itemId);
      const nextItems = poolItemsTarget.items.filter((item) => item.id !== itemId);
      setPoolItemsTarget({
        ...poolItemsTarget,
        items: nextItems,
        itemCount: Math.max(0, nextItems.length),
      });
      showSuccess("Pool item deleted");
      void poolData.reload();
    } catch {
      showError("Failed to delete pool item");
    }
  };

  const handleCreateSavedView = async (values: {
    account_id: string;
    name: string;
  }): Promise<void> => {
    setSavedViewCreating(true);
    try {
      await createTaskMonitorSavedView({
        account_id: values.account_id,
        name: values.name,
        filter_json: monitorAppliedFilters,
        sort_json: [],
        columns_json: ["public_user_id", "task_balance", "risk_tags"],
        refresh_seconds: 15,
        sound_enabled: true,
        is_default: savedViews.length === 0,
      });
      showSuccess("Saved view created");
      setSavedViewCreateOpen(false);
      savedViewCreateForm.resetFields();
      void monitorConfigData.reload();
    } catch {
      showError("Failed to create saved view");
    } finally {
      setSavedViewCreating(false);
    }
  };

  const handleApplySavedView = useCallback((record: TaskMonitorSavedView): void => {
    const normalizedFilters = normalizeTaskMonitorQueryParams(record.filter_json);
    setMonitorFilterAccount(record.account_id);
    setMonitorDraftFilters(normalizedFilters);
    setMonitorAppliedFilters(normalizedFilters);
  }, []);

  const handleCreateAlertRule = async (values: {
    account_id: string;
    name: string;
    threshold: number;
  }): Promise<void> => {
    setAlertRuleCreating(true);
    try {
      await createTaskAlertRule({
        account_id: values.account_id,
        name: values.name,
        status: "active",
        condition_json: {
          field: "actual_day_amount",
          operator: ">=",
          value: values.threshold,
        },
        action_json: {
          notify_staff: true,
          require_manual_review: true,
        },
        sound_enabled: true,
        priority: "high",
      });
      showSuccess("Alert rule created");
      setAlertRuleCreateOpen(false);
      alertRuleCreateForm.resetFields();
      void monitorConfigData.reload();
    } catch {
      showError("Failed to create alert rule");
    } finally {
      setAlertRuleCreating(false);
    }
  };

  const handleAcknowledgeAlertEvent = async (event: TaskMonitorAlertEvent): Promise<void> => {
    try {
      await acknowledgeTaskMonitorAlertEvent(event.id);
      showSuccess("Alert acknowledged");
      void monitorConfigData.reload();
    } catch {
      showError("Failed to acknowledge alert");
    }
  };

  const handleResolveAlertEvent = async (event: TaskMonitorAlertEvent): Promise<void> => {
    try {
      await resolveTaskMonitorAlertEvent(event.id);
      showSuccess("Alert resolved");
      void monitorConfigData.reload();
    } catch {
      showError("Failed to resolve alert");
    }
  };

  const handleSetDefaultSavedView = async (record: TaskMonitorSavedView): Promise<void> => {
    try {
      await updateTaskMonitorSavedView(record.id, {
        name: record.name,
        filter_json: record.filter_json,
        sort_json: record.sort_json,
        columns_json: record.columns_json,
        refresh_seconds: record.refresh_seconds,
        sound_enabled: record.sound_enabled,
        is_default: true,
      });
      showSuccess("Saved view updated");
      void monitorConfigData.reload();
    } catch {
      showError("Failed to update saved view");
    }
  };

  const handleDeleteSavedView = async (record: TaskMonitorSavedView): Promise<void> => {
    try {
      await deleteTaskMonitorSavedView(record.id);
      showSuccess("Saved view deleted");
      void monitorConfigData.reload();
    } catch {
      showError("Failed to delete saved view");
    }
  };

  const handleToggleAlertRule = async (record: TaskAlertRule): Promise<void> => {
    try {
      await updateTaskAlertRule(record.id, {
        name: record.name,
        status: record.status === "active" ? "paused" : "active",
        condition_json: record.condition_json,
        action_json: record.action_json,
        sound_enabled: record.sound_enabled,
        priority: record.priority,
        metadata_json: record.metadata_json,
      });
      showSuccess("Alert rule updated");
      void monitorConfigData.reload();
    } catch {
      showError("Failed to update alert rule");
    }
  };

  const handleDeleteAlertRule = async (record: TaskAlertRule): Promise<void> => {
    try {
      await deleteTaskAlertRule(record.id);
      showSuccess("Alert rule deleted");
      void monitorConfigData.reload();
    } catch {
      showError("Failed to delete alert rule");
    }
  };

  const handleRetryGenerationRun = async (record: TaskGenerationRun): Promise<void> => {
    setGenerationActionKey(`run:${record.id}`);
    try {
      await retryTaskGenerationRun(record.id);
      showSuccess(`Retried generation run ${record.id}`);
      void generationRunData.reload();
    } catch {
      showError("Failed to retry generation run");
    } finally {
      setGenerationActionKey(null);
    }
  };

  const handleCreateIssuePlan = async (values: IssuePlanFormValues): Promise<void> => {
    setPlanCreating(true);
    try {
      await createTaskIssuePlan(buildTaskIssuePlanCreatePayload(values));
      showSuccess("Issue plan created");
      setPlanCreateOpen(false);
      setPlanProductCountMode("range");
      planCreateForm.resetFields();
      void planData.reload();
    } catch {
      showError("Failed to create issue plan");
    } finally {
      setPlanCreating(false);
    }
  };

  const handleToggleIssuePlan = async (plan: TaskIssuePlan): Promise<void> => {
    setPlanActionLoadingId(plan.id);
    try {
      if (plan.status === "active") {
        await disableTaskIssuePlan(plan.id);
        showSuccess(`Issue plan disabled: ${plan.name}`);
      } else {
        await enableTaskIssuePlan(plan.id);
        showSuccess(`Issue plan enabled: ${plan.name}`);
      }
      void planData.reload();
    } catch {
      showError("Failed to update issue plan status");
    } finally {
      setPlanActionLoadingId(null);
    }
  };

  const handleCreateProductPool = async (values: {
    account_id: string;
    site_id?: string;
    name: string;
    code?: string;
    currency?: string;
  }): Promise<void> => {
    setPoolCreating(true);
    try {
      await createTaskProductPool({
        accountId: values.account_id,
        siteId: values.site_id,
        name: values.name,
        code: values.code,
        currency: values.currency || "USD",
        poolType: "default",
        priceMode: "snapshot",
        allowRepeatInSameBatch: false,
        allowRepeatInSamePackage: false,
        status: "active",
      });
      showSuccess("Product pool created");
      setPoolCreateOpen(false);
      poolCreateForm.resetFields();
      void poolData.reload();
    } catch {
      showError("Failed to create product pool");
    } finally {
      setPoolCreating(false);
    }
  };

  const handleApprove = async (instance: TaskInstance): Promise<void> => {
    try {
      await approveTaskReview(instance.id);
      showSuccess("Review approved");
      void reviewData.reload();
    } catch {
      showError("Failed to approve review");
    }
  };

  const handleReject = async (instance: TaskInstance): Promise<void> => {
    try {
      await rejectTaskReview(instance.id);
      showSuccess("Review rejected");
      void reviewData.reload();
    } catch {
      showError("Failed to reject review");
    }
  };

  const handleOpenCustomerPage = (record: {
    account_id: string | null;
    user_id: string;
    public_user_id: string;
  }, detailTab?: "overview" | "attribution" | "conversations" | "tickets" | "finance" | "timeline" | "profile"): void => {
    openCustomersPage({
      account_id: record.account_id ?? undefined,
      selected_profile_id: record.user_id,
      query: record.public_user_id,
      detail_tab: detailTab,
    });
  };

  const handleOpenPackageDetail = async (packageId: string): Promise<void> => {
    setPackageDetailOpen(true);
    setPackageDetailLoading(true);
    try {
      const detail = await getTaskPackageDetail(packageId);
      setPackageDetail(detail);
    } catch {
      showError("Failed to load package detail");
    } finally {
      setPackageDetailLoading(false);
    }
  };

  const handleOpenManualAdd = async (packageId: string): Promise<void> => {
    setManualAddOpen(true);
    setManualAddPackageId(packageId);
    setManualAddLoading(true);
    setManualAddPreview(null);
    try {
      const candidates = await listTaskPackageManualAddCandidates(packageId);
      setManualAddCandidates(candidates);
    } catch {
      showError("Failed to load manual add candidates");
    } finally {
      setManualAddLoading(false);
    }
  };

  const handlePreviewManualAdd = async (): Promise<void> => {
    if (!manualAddPackageId || manualAddSelectedIds.length === 0) {
      showError("Select at least one product before previewing");
      return;
    }
    setManualAddPreviewLoading(true);
    try {
      const preview = await previewTaskPackageManualAdd(manualAddPackageId, {
        pool_item_ids: manualAddSelectedIds,
        reason_text: manualAddReason || undefined,
      });
      setManualAddPreview(preview);
    } catch {
      showError("Failed to preview manual add");
    } finally {
      setManualAddPreviewLoading(false);
    }
  };

  const handleSubmitManualAdd = async (): Promise<void> => {
    if (!manualAddPackageId || manualAddSelectedIds.length === 0) {
      showError("Select at least one product before submitting");
      return;
    }
    setManualAddSubmitting(true);
    try {
      await createTaskPackageManualAdd(manualAddPackageId, {
        pool_item_ids: manualAddSelectedIds,
        reason_text: manualAddReason || undefined,
      });
      resetManualAddState();
      await pkgData.reload();
      if (packageDetail?.id === manualAddPackageId) {
        const detail = await getTaskPackageDetail(manualAddPackageId);
        setPackageDetail(detail);
      }
    } catch {
      showError("Failed to submit manual add");
    } finally {
      setManualAddSubmitting(false);
    }
  };

  const handleTaskPackageStatusAction = async (
    record: TaskPackageAdminListItem,
    action: "pause" | "resume" | "cancel",
  ): Promise<void> => {
    try {
      if (action === "pause") {
        await pauseTaskPackage(record.id, { reason_text: "manual_pause_from_admin" });
        showSuccess(`Paused package ${record.progress_label}`);
      } else if (action === "resume") {
        await resumeTaskPackage(record.id, { reason_text: "manual_resume_from_admin" });
        showSuccess(`Resumed package ${record.progress_label}`);
      } else {
        await cancelTaskPackage(record.id, { reason_text: "manual_cancel_from_admin" });
        showSuccess(`Cancelled package ${record.progress_label}`);
      }
      await pkgData.reload();
      if (packageDetail?.id === record.id) {
        const detail = await getTaskPackageDetail(record.id);
        setPackageDetail(detail);
      }
    } catch {
      showError("Task package action failed");
    }
  };

  const handlePauseNextBatch = async (record: TaskMonitorRow): Promise<void> => {
    try {
      const quota = await pauseNextTaskPackageQuota(record.package_id, {
        reason: "manual_pause_next_batch_from_monitor",
      });
      showSuccess(`Paused next batch day ${quota.day_no} for ${record.public_user_id}`);
      await monitorData.reload();
    } catch {
      showError("Pause next batch failed");
    }
  };

  const tplStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Templates <Typography.Text strong>{templates.length}</Typography.Text></span>
      <span>Active <Typography.Text strong style={{ color: "#52c41a" }}>{templates.filter((item) => item.status === "active").length}</Typography.Text></span>
      <span>Draft <Typography.Text strong>{templates.filter((item) => item.status === "draft").length}</Typography.Text></span>
      <span>Disabled <Typography.Text strong style={{ color: "#ff4d4f" }}>{templates.filter((item) => item.status === "disabled").length}</Typography.Text></span>
    </Space>
  );

  const instStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Instances <Typography.Text strong>{filteredInstances.length}</Typography.Text></span>
      <span>Pending <Typography.Text strong>{filteredInstances.filter((item) => item.status === "pending").length}</Typography.Text></span>
      <span>Claimed <Typography.Text strong style={{ color: "#1677ff" }}>{filteredInstances.filter((item) => item.status === "claimed").length}</Typography.Text></span>
      <span>Completed <Typography.Text strong style={{ color: "#52c41a" }}>{filteredInstances.filter((item) => item.status === "approved" || item.status === "completed").length}</Typography.Text></span>
      <span>Rejected <Typography.Text strong style={{ color: "#ff4d4f" }}>{filteredInstances.filter((item) => item.status === "rejected").length}</Typography.Text></span>
    </Space>
  );

  const pkgStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Packages <Typography.Text strong>{packages.length}</Typography.Text></span>
      <span>Manual Add <Typography.Text strong style={{ color: "#1677ff" }}>{packages.filter((item) => item.has_manual_add).length}</Typography.Text></span>
      <span>Active <Typography.Text strong style={{ color: "#52c41a" }}>{packages.filter((item) => item.status === "active").length}</Typography.Text></span>
    </Space>
  );

  const reviewStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Pending Reviews <Typography.Text strong style={{ color: "#faad14" }}>{reviews.length}</Typography.Text></span>
    </Space>
  );

  const quotaStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Quotas <Typography.Text strong>{quotas.length}</Typography.Text></span>
      <span>Pending <Typography.Text strong>{quotas.filter((item) => item.status === "pending").length}</Typography.Text></span>
      <span>Locked <Typography.Text strong style={{ color: "#52c41a" }}>{quotas.filter((item) => item.status === "locked").length}</Typography.Text></span>
    </Space>
  );

  const manualAddLogStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Logs <Typography.Text strong>{manualAddLogs.length}</Typography.Text></span>
      <span>Added Amount <Typography.Text strong style={{ color: "#1677ff" }}>{manualAddLogs.reduce((sum, item) => sum + item.added_amount, 0)}</Typography.Text></span>
    </Space>
  );

  const poolStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Pools <Typography.Text strong>{productPools.length}</Typography.Text></span>
      <span>Active <Typography.Text strong style={{ color: "#52c41a" }}>{productPools.filter((item) => item.status === "active").length}</Typography.Text></span>
      <span>Total Items <Typography.Text strong>{productPools.reduce((sum, item) => sum + item.itemCount, 0)}</Typography.Text></span>
    </Space>
  );

  const monitorStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Runs <Typography.Text strong>{generationRuns.length}</Typography.Text></span>
      <span>Success <Typography.Text strong style={{ color: "#52c41a" }}>{generationRuns.filter((item) => item.status === "success").length}</Typography.Text></span>
      <span>Failed <Typography.Text strong style={{ color: "#ff4d4f" }}>{generationRuns.filter((item) => item.status !== "success").length}</Typography.Text></span>
      <span>Saved Views <Typography.Text strong>{savedViews.length}</Typography.Text></span>
      <span>Alert Rules <Typography.Text strong>{alertRules.length}</Typography.Text></span>
    </Space>
  );

  const taskMonitorStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Rows <Typography.Text strong>{monitorSummary?.total_count ?? monitorRows.length}</Typography.Text></span>
      <span>Manual Add <Typography.Text strong style={{ color: "#1677ff" }}>{monitorSummary?.manual_add_count ?? monitorRows.filter((item) => item.has_manual_add).length}</Typography.Text></span>
      <span>Effective <Typography.Text strong style={{ color: "#52c41a" }}>{monitorSummary?.total_effective_amount ?? 0}</Typography.Text></span>
      <span>Recharge <Typography.Text strong>{monitorSummary?.total_real_recharge_amount ?? 0}</Typography.Text></span>
      <span>Withdraw <Typography.Text strong>{monitorSummary?.total_withdraw_amount ?? 0}</Typography.Text></span>
      <span>Views <Typography.Text strong>{savedViews.length}</Typography.Text></span>
      <span>Rules <Typography.Text strong>{alertRules.length}</Typography.Text></span>
    </Space>
  );

  const planStats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>Total Plans <Typography.Text strong>{issuePlans.length}</Typography.Text></span>
      <span>Active <Typography.Text strong style={{ color: "#52c41a" }}>{issuePlans.filter((item) => item.status === "active").length}</Typography.Text></span>
      <span>Day Rules <Typography.Text strong>{issuePlans.reduce((sum, item) => sum + item.day_rules.length, 0)}</Typography.Text></span>
    </Space>
  );

  const actions = (
    <Space>
      <Button size="small" icon={<ReloadOutlined />} onClick={refreshAll}>
        Refresh
      </Button>
    </Space>
  );

  const tplColumns = [
    { title: "Task Key", dataIndex: "task_key", key: "task_key", width: 140, ellipsis: true },
    { title: "Name", dataIndex: "name", key: "name", width: 140, ellipsis: true },
    { title: "Task Type", dataIndex: "task_type", key: "task_type", width: 100 },
    {
      title: "Public User",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={TEMPLATE_STATUS_COLORS[value] ?? "default"}>
          {TEMPLATE_STATUS_LABELS[value] ?? value}
        </Tag>
      ),
    },
    { title: "Reward Amount", dataIndex: "reward_amount", key: "reward_amount", width: 100, render: (value: string | null) => formatMoney(value) },
    { title: "Created At", dataIndex: "created_at", key: "created_at", width: 140, render: (value: string) => formatDate(value) },
  ];

  const instColumns = [
    {
      title: "Actions",
      dataIndex: "id",
      key: "id",
      width: 160,
      ellipsis: true,
      render: (value: string) => <Typography.Text copyable style={{ fontSize: 12 }}>{value.slice(0, 16)}...</Typography.Text>,
    },
    { title: "Template Name", dataIndex: "template_name", key: "template_name", width: 120, ellipsis: true },
    {
      title: "Verification",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 120,
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
      title: "Public User",
      dataIndex: "site_key",
      key: "site_key",
      width: 130,
      render: (siteKey: string | null) => {
        if (!siteKey) {
          return "-";
        }
        const site = sites.find((item) => item.site_key === siteKey);
        return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
      },
    },
    {
      title: "Actions",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={INSTANCE_STATUS_COLORS[value] ?? "default"}>
          {INSTANCE_STATUS_LABELS[value] ?? value}
        </Tag>
      ),
    },
    {
      title: "Quota ID",
      key: "verification_status",
      width: 120,
      render: (_: unknown, record: { user_id: string }) =>
        renderMemberTag(taskInstanceMemberStatusIndex[record.user_id]?.latestVerificationStatus),
    },
    {
      title: "WhatsApp Binding",
      key: "binding_status",
      width: 140,
      render: (_: unknown, record: { user_id: string }) =>
        renderMemberTag(taskInstanceMemberStatusIndex[record.user_id]?.latestBindingStatus),
    },
    { title: "Claimed At", dataIndex: "claimed_at", key: "claimed_at", width: 140, render: (value: string | null) => formatDate(value) },
    {
      title: "Actions",
      key: "actions",
      width: 120,
      render: (_: unknown, record: { account_id: string | null; user_id: string; public_user_id: string }) => (
        <Button size="small" onClick={() => handleOpenCustomerPage(record)}>
          查看客户
        </Button>
      ),
    },
  ];

  const pkgColumns = [
    {
      title: "Package ID",
      dataIndex: "id",
      key: "id",
      width: 160,
      ellipsis: true,
      render: (value: string) => <Typography.Text copyable style={{ fontSize: 12 }}>{value.slice(0, 16)}...</Typography.Text>,
    },
    {
      title: "Public User",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 140,
      render: (value: string, record: TaskPackageAdminListItem) => (
        <MemberIdLink
          accountId={record.account_id}
          userId={record.user_id}
          publicUserId={record.public_user_id}
          label={value || record.public_user_id}
        />
      ),
    },
    { title: "Progress", dataIndex: "progress_label", key: "progress_label", width: 90 },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={INSTANCE_STATUS_COLORS[value] ?? "default"}>
          {INSTANCE_STATUS_LABELS[value] ?? value}
        </Tag>
      ),
    },
    { title: "System Generated Amount", dataIndex: "system_generated_amount", key: "system_generated_amount", width: 110 },
    { title: "Manual Added Amount", dataIndex: "manual_added_amount", key: "manual_added_amount", width: 110 },
    { title: "Effective Amount", dataIndex: "effective_amount", key: "effective_amount", width: 110 },
    { title: "Estimated Reward Amount", dataIndex: "estimated_reward_amount", key: "estimated_reward_amount", width: 110 },
    {
      title: "Actions",
      key: "actions",
      width: 240,
      render: (_: unknown, record: TaskPackageAdminListItem) => (
        <Space size={6}>
          <Button size="small" onClick={() => void handleOpenPackageDetail(record.id)}>
            Package Detail
          </Button>
          <Button size="small" onClick={() => void handleOpenManualAdd(record.id)}>
            Manual Add
          </Button>
          <Button
            size="small"
            onClick={() => {
              setManualLogPackageId(record.id);
              setActiveTab("manual-add-logs");
              void manualAddLogData.reload();
            }}
          >
            Manual Logs
          </Button>
          {record.status === "active" ? (
            <Button size="small" onClick={() => void handleTaskPackageStatusAction(record, "pause")}>
              Pause
            </Button>
          ) : null}
          {record.status === "paused" ? (
            <Button size="small" onClick={() => void handleTaskPackageStatusAction(record, "resume")}>
              Resume
            </Button>
          ) : null}
          {!["completed", "expired", "cancelled"].includes(record.status) ? (
            <Button size="small" danger onClick={() => void handleTaskPackageStatusAction(record, "cancel")}>
              Cancel
            </Button>
          ) : null}
          <Button
            size="small"
            onClick={() =>
              handleOpenCustomerPage({
                account_id: record.account_id,
                user_id: record.user_id,
                public_user_id: record.public_user_id,
              })
            }
          >
            Customer Detail
          </Button>
        </Space>
      ),
    },
  ];

  const reviewColumns = [
    {
      title: "Task ID",
      dataIndex: "id",
      key: "id",
      width: 160,
      ellipsis: true,
      render: (value: string) => <Typography.Text copyable style={{ fontSize: 12 }}>{value.slice(0, 16)}...</Typography.Text>,
    },
    { title: "Template Name", dataIndex: "template_name", key: "template_name", width: 120, ellipsis: true },
    {
      title: "Public User",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 120,
      render: (value: string, record: TaskInstance) => (
        <MemberIdLink
          accountId={record.account_id}
          userId={record.user_id}
          publicUserId={record.public_user_id}
          label={value || record.public_user_id}
        />
      ),
    },
    { title: "Submitted At", dataIndex: "submitted_at", key: "submitted_at", width: 140, render: (value: string | null) => formatDate(value) },
    {
      title: "Actions",
      key: "actions",
      width: 160,
      render: (_: unknown, record: TaskInstance) => (
        <Space size={4}>
          <Button size="small" type="primary" style={{ fontSize: 11 }} onClick={() => void handleApprove(record)}>
            Approve
          </Button>
          <Button size="small" danger style={{ fontSize: 11 }} onClick={() => void handleReject(record)}>
            Reject
          </Button>
        </Space>
      ),
    },
  ];

  const quotaColumns = [
    {
      title: "Quota ID",
      dataIndex: "id",
      key: "id",
      width: 180,
      ellipsis: true,
    },
    { title: "User ID", dataIndex: "user_id", key: "user_id", width: 140, ellipsis: true },
    { title: "Day No", dataIndex: "day_no", key: "day_no", width: 80 },
    { title: "Package Count", dataIndex: "package_count", key: "package_count", width: 100 },
    { title: "Day Total Amount", dataIndex: "day_total_amount", key: "day_total_amount", width: 120 },
    { title: "Product Pool ID", dataIndex: "product_pool_id", key: "product_pool_id", width: 160, ellipsis: true },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={QUOTA_STATUS_COLORS[value] ?? "default"}>
          {QUOTA_STATUS_LABELS[value] ?? value}
        </Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 140,
      render: (_: unknown, record: TaskQuota) => (
        <Button
          size="small"
          loading={generationActionKey === `quota:${record.id}`}
          disabled={!["locked", "pending"].includes(record.status)}
          onClick={() => void handleGenerateQuotaBatch(record)}
        >
          Generate Batch
        </Button>
      ),
    },
  ];

const poolColumns = [
    {
      title: "Pool ID",
      dataIndex: "id",
      key: "id",
      width: 180,
      ellipsis: true,
    },
    { title: "Name", dataIndex: "name", key: "name", width: 180 },
    { title: "Code", dataIndex: "code", key: "code", width: 140 },
    { title: "Pool Type", dataIndex: "poolType", key: "poolType", width: 100 },
    { title: "Item Count", dataIndex: "itemCount", key: "itemCount", width: 100 },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={TEMPLATE_STATUS_COLORS[value] ?? "default"}>
          {TEMPLATE_STATUS_LABELS[value] ?? value}
        </Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 160,
      render: (_: unknown, record: TaskProductPool) => (
        <Button size="small" onClick={() => handleOpenPoolItems(record)}>
          Manage Items
        </Button>
      ),
    },
  ];

  const generationRunColumns = [
    {
      title: "Run ID",
      dataIndex: "id",
      key: "id",
      width: 180,
      ellipsis: true,
    },
    {
      title: "Public User",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 140,
      render: (value: string, record: TaskGenerationRun) => (
        <MemberIdLink
          accountId={record.account_id}
          userId={record.user_id}
          publicUserId={record.public_user_id}
          label={value || record.public_user_id}
        />
      ),
    },
    { title: "Selection Algorithm", dataIndex: "selection_algorithm", key: "selection_algorithm", width: 220 },
    { title: "Target Day Amount", dataIndex: "target_day_amount", key: "target_day_amount", width: 100 },
    { title: "Actual Day System Amount", dataIndex: "actual_day_system_amount", key: "actual_day_system_amount", width: 100 },
    { title: "Generated Item Count", dataIndex: "generated_item_count", key: "generated_item_count", width: 100 },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => <Tag color={value === "success" ? "green" : "red"}>{value}</Tag>,
    },
    {
      title: "Actions",
      key: "actions",
      width: 120,
      render: (_: unknown, record: TaskGenerationRun) => (
        <Button
          size="small"
          loading={generationActionKey === `run:${record.id}`}
          disabled={record.status === "success"}
          onClick={() => void handleRetryGenerationRun(record)}
        >
          Retry Run
        </Button>
      ),
    },
  ];

  const taskMonitorColumns = [
    {
      title: "Package ID",
      dataIndex: "package_id",
      key: "package_id",
      width: 180,
      ellipsis: true,
    },
    {
      title: "Public User",
      dataIndex: "public_user_id",
      key: "public_user_id",
      width: 140,
      render: (value: string, record: TaskMonitorRow) => (
        <MemberIdLink
          accountId={record.account_id}
          userId={record.user_id}
          publicUserId={record.public_user_id}
          label={value || record.public_user_id}
        />
      ),
    },
    { title: "Progress", dataIndex: "progress_label", key: "progress_label", width: 90 },
    { title: "Current Item", dataIndex: "current_item_index", key: "current_item_index", width: 90 },
    {
      title: "Current Product",
      dataIndex: "current_product_name",
      key: "current_product_name",
      width: 180,
      render: (_value: string | null, record: TaskMonitorRow) =>
        record.current_product_name || record.current_product_id || "-",
    },
    { title: "Day Planned Amount", dataIndex: "day_planned_amount", key: "day_planned_amount", width: 110 },
    {
      title: "Day System Amount",
      dataIndex: "day_system_generated_amount",
      key: "day_system_generated_amount",
      width: 110,
    },
    {
      title: "Day Manual Added Amount",
      dataIndex: "day_manual_added_amount",
      key: "day_manual_added_amount",
      width: 120,
    },
    { title: "Day Effective Amount", dataIndex: "day_effective_amount", key: "day_effective_amount", width: 110 },
    { title: "Planned Amount", dataIndex: "planned_amount", key: "planned_amount", width: 100 },
    { title: "Manual Added Amount", dataIndex: "manual_added_amount", key: "manual_added_amount", width: 100 },
    { title: "Manual Added Items", dataIndex: "manual_added_item_count", key: "manual_added_item_count", width: 100 },
    { title: "Effective Amount", dataIndex: "effective_amount", key: "effective_amount", width: 100 },
    { title: "Current Product Amount", dataIndex: "current_product_amount", key: "current_product_amount", width: 100 },
    { title: "Current Product Source", dataIndex: "current_product_origin", key: "current_product_origin", width: 140 },
    {
      title: "Latest Manual Add By",
      dataIndex: "latest_manual_add_operator_id",
      key: "latest_manual_add_operator_id",
      width: 180,
    },
    {
      title: "Latest Manual Add At",
      dataIndex: "latest_manual_add_at",
      key: "latest_manual_add_at",
      width: 180,
      render: (value: string | null) => formatDate(value),
    },
    { title: "Total Real Recharge Amount", dataIndex: "total_real_recharge_amount", key: "total_real_recharge_amount", width: 100 },
    { title: "Total Withdraw Amount", dataIndex: "total_withdraw_amount", key: "total_withdraw_amount", width: 100 },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => <Tag color={value === "completed" ? "green" : "blue"}>{value}</Tag>,
    },
    {
      title: "Actions",
      key: "actions",
      width: 280,
      render: (_: unknown, record: TaskMonitorRow) => (
        <Space>
          <Button size="small" onClick={() => void handleOpenPackageDetail(record.package_id)}>
            Package Detail
          </Button>
          <Button size="small" onClick={() => void handleOpenManualAdd(record.package_id)}>
            Manual Add
          </Button>
          <Button
            size="small"
            onClick={() => handleOpenCustomerPage({
              account_id: record.account_id,
              user_id: record.user_id,
              public_user_id: record.public_user_id,
            })}
          >
            Customer Detail
          </Button>
          <Button
            size="small"
            onClick={() => handleOpenCustomerPage({
              account_id: record.account_id,
              user_id: record.user_id,
              public_user_id: record.public_user_id,
            }, "finance")}
          >
            Customer Wallet
          </Button>
          <Button size="small" onClick={() => void handlePauseNextBatch(record)}>
            Pause Next Batch
          </Button>
        </Space>
      ),
    },
  ];

const planColumns = [
    {
      title: "Plan ID",
      dataIndex: "id",
      key: "id",
      width: 180,
      ellipsis: true,
    },
    { title: "Name", dataIndex: "name", key: "name", width: 180 },
    { title: "Plan Type", dataIndex: "plan_type", key: "plan_type", width: 100 },
    { title: "After Last Rule Mode", dataIndex: "after_last_rule_mode", key: "after_last_rule_mode", width: 160 },
    { title: "Default Product Pool", dataIndex: "default_product_pool_id", key: "default_product_pool_id", width: 160, ellipsis: true },
    {
      title: "Day Rules",
      key: "day_rules_count",
      width: 100,
      render: (_: unknown, record: TaskIssuePlan) => record.day_rules.length,
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (value: string) => (
        <Tag color={TEMPLATE_STATUS_COLORS[value] ?? "default"}>
          {TEMPLATE_STATUS_LABELS[value] ?? value}
        </Tag>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 140,
      render: (_: unknown, record: TaskIssuePlan) => (
        <Button
          size="small"
          loading={planActionLoadingId === record.id}
          onClick={() => void handleToggleIssuePlan(record)}
        >
          {record.status === "active" ? "Disable" : "Enable"}
        </Button>
      ),
    },
  ];

  const detailItemColumns = [
    { title: "Product Name", dataIndex: "product_name", key: "product_name" },
    { title: "Origin", dataIndex: "origin", key: "origin" },
    { title: "Status", dataIndex: "status", key: "status" },
    { title: "Price", dataIndex: "price", key: "price" },
  ];

  const detailLogColumns = [
    { title: "Id", dataIndex: "id", key: "id", ellipsis: true },
    { title: "Operator Id", dataIndex: "operator_id", key: "operator_id" },
    { title: "Added Item Count", dataIndex: "added_item_count", key: "added_item_count" },
    { title: "Added Amount", dataIndex: "added_amount", key: "added_amount" },
    { title: "Reason Text", dataIndex: "reason_text", key: "reason_text" },
  ];

  const renderTemplates = (): JSX.Element => (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          placeholder="Filter Account"
          allowClear
          style={{ width: 160 }}
          value={tplFilterAccount}
          onChange={(value) => {
            setTplFilterAccount(value);
            void tplData.reload();
          }}
          options={accountOptions}
        />
        <Select
          placeholder="Filter Type"
          allowClear
          style={{ width: 120 }}
          value={tplFilterType}
          onChange={(value) => {
            setTplFilterType(value);
            void tplData.reload();
          }}
          options={[
            { label: "Daily", value: "daily" },
            { label: "Share", value: "share" },
            { label: "Video", value: "video" },
            { label: "Custom", value: "custom" },
          ]}
        />
        <Select
          placeholder="Filter Status"
          allowClear
          style={{ width: 120 }}
          value={tplFilterStatus}
          onChange={(value) => {
            setTplFilterStatus(value);
            void tplData.reload();
          }}
          options={Object.entries(TEMPLATE_STATUS_LABELS).map(([key, value]) => ({ label: value, value: key }))}
        />
        <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
          New Template
        </Button>
      </Space>
      {tplData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{tplData.error}</Typography.Text> : null}
      <Table dataSource={templates} columns={withSorter(tplColumns)} rowKey="id" size="small" loading={tplData.loading} pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ y: "calc(100vh - 440px)" }} />
    </div>
  );

  const renderInstances = (): JSX.Element => (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select placeholder="Filter Account" allowClear style={{ width: 160 }} value={instFilterAccount} onChange={(value) => { setInstFilterAccount(value); void instData.reload(); }} options={accountOptions} />
        <Select placeholder="Filter Status" allowClear style={{ width: 120 }} value={instFilterStatus} onChange={(value) => { setInstFilterStatus(value); void instData.reload(); }} options={Object.entries(INSTANCE_STATUS_LABELS).map(([key, value]) => ({ label: value, value: key }))} />
        <Input placeholder="Search user / public ID" prefix={<SearchOutlined />} allowClear style={{ width: 180 }} value={instSearchUser} onChange={(event) => setInstSearchUser(event.target.value)} />
      </Space>
      {instData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{instData.error}</Typography.Text> : null}
      <Table dataSource={filteredInstances} columns={withSorter(instColumns)} rowKey="id" size="small" loading={instData.loading} pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ y: "calc(100vh - 440px)" }} />
    </div>
  );

  const renderPackages = (): JSX.Element => (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select placeholder="Filter Account" allowClear style={{ width: 160 }} value={pkgFilterAccount} onChange={(value) => { setPkgFilterAccount(value); void pkgData.reload(); }} options={accountOptions} />
        <Select placeholder="Filter Status" allowClear style={{ width: 120 }} value={pkgFilterStatus} onChange={(value) => { setPkgFilterStatus(value); void pkgData.reload(); }} options={Object.entries(INSTANCE_STATUS_LABELS).map(([key, value]) => ({ label: value, value: key }))} />
      </Space>
      {pkgData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{pkgData.error}</Typography.Text> : null}
      <Table dataSource={packages} columns={withSorter(pkgColumns)} rowKey="id" size="small" loading={pkgData.loading} pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ y: "calc(100vh - 440px)" }} />
    </div>
  );

  const manualAddLogColumns = [
    { title: "Id", dataIndex: "id", key: "id", width: 180, ellipsis: true },
    { title: "Operator Id", dataIndex: "operator_id", key: "operator_id", width: 140, ellipsis: true },
    { title: "Added Item Count", dataIndex: "added_item_count", key: "added_item_count", width: 100 },
    { title: "Added Amount", dataIndex: "added_amount", key: "added_amount", width: 100 },
    { title: "Before Effective Amount", dataIndex: "before_effective_amount", key: "before_effective_amount", width: 120 },
    { title: "After Effective Amount", dataIndex: "after_effective_amount", key: "after_effective_amount", width: 120 },
    { title: "Reason Text", dataIndex: "reason_text", key: "reason_text", width: 220, ellipsis: true },
    { title: "Created At", dataIndex: "created_at", key: "created_at", width: 180, render: formatDate },
  ];

  const renderManualAddLogs = (): JSX.Element => (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          placeholder="Filter Package"
          style={{ width: 280 }}
          value={manualLogPackageId}
          onChange={(value) => {
            setManualLogPackageId(value);
            void manualAddLogData.reload();
          }}
          options={packages.map((item) => ({
            label: `${item.public_user_id} / ${item.progress_label} / ${item.id.slice(0, 8)}`,
            value: item.id,
          }))}
        />
      </Space>
      {manualAddLogData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{manualAddLogData.error}</Typography.Text> : null}
      <Table
        dataSource={manualAddLogs}
        columns={withSorter(manualAddLogColumns)}
        rowKey="id"
        size="small"
        loading={manualAddLogData.loading}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        scroll={{ y: "calc(100vh - 440px)" }}
      />
    </div>
  );

  const renderReviews = (): JSX.Element => (
    <div>
      {reviewData.error ? <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{reviewData.error}</Typography.Text> : null}
      {reviews.length === 0 && !reviewData.loading ? (
        <Empty description="No pending reviews." />
      ) : (
        <Table dataSource={reviews} columns={withSorter(reviewColumns)} rowKey="id" size="small" loading={reviewData.loading} pagination={{ pageSize: 20, showSizeChanger: true }} scroll={{ y: "calc(100vh - 380px)" }} />
      )}
    </div>
  );

  const renderQuotasPanel = (): JSX.Element => (
    <Space direction="vertical" style={{ width: "100%" }} size={12}>
      <Button size="small" onClick={() => void handlePreviewQuota()} loading={quotaPreviewLoading}>
        Preview Amount Allocation
      </Button>
      <TaskAmountAllocationPreview amounts={quotaPreview} total={quotaPreviewTotal} />
      <MemberTaskQuotaPanel
        accountOptions={accountOptions}
        filterAccount={quotaFilterAccount}
        onFilterAccountChange={(value) => {
          setQuotaFilterAccount(value);
          void quotaData.reload();
        }}
        onCreate={() => setQuotaCreateOpen(true)}
        onBatchCreate={() => setQuotaBatchCreateOpen(true)}
        error={quotaData.error}
        quotas={quotas}
        columns={withSorter(quotaColumns)}
        loading={quotaData.loading}
      />
    </Space>
  );

  const renderProductPools = (): JSX.Element => (
    <TaskProductPoolEditor
      accountOptions={accountOptions}
      filterAccount={poolFilterAccount}
      onFilterAccountChange={(value) => {
        setPoolFilterAccount(value);
        void poolData.reload();
      }}
      onCreate={() => setPoolCreateOpen(true)}
      error={poolData.error}
      productPools={productPools}
      columns={withSorter(poolColumns)}
      loading={poolData.loading}
    />
  );

  const renderMonitoringPanel = (): JSX.Element => (
    <TaskMonitorPanel
      accountOptions={accountOptions}
      filterAccount={monitorFilterAccount}
      monitorFilters={monitorDraftFilters}
      onFilterAccountChange={(value) => {
        setMonitorFilterAccount(value);
        void monitorData.reload();
      }}
      onMonitorFilterChange={handleMonitorFilterChange}
      onApplyFilters={handleApplyMonitorFilters}
      onResetFilters={handleResetMonitorFilters}
      onCreateSavedView={() => setSavedViewCreateOpen(true)}
      onCreateAlertRule={() => setAlertRuleCreateOpen(true)}
      monitorError={monitorData.error}
      monitorConfigError={monitorConfigData.error}
      generationRuns={generationRuns}
      generationRunColumns={withSorter(generationRunColumns)}
      savedViews={savedViews}
      savedViewColumns={withSorter([
        { title: "Name", dataIndex: "name", key: "name" },
        { title: "Refresh Seconds", dataIndex: "refresh_seconds", key: "refresh_seconds" },
        { title: "Default", dataIndex: "is_default", key: "is_default", render: (_: unknown, record: TaskMonitorSavedView) => (record.is_default ? "Yes" : "No") },
        {
          title: "Actions",
          key: "actions",
          render: (_: unknown, record: TaskMonitorSavedView) => (
            <Space>
              <Button size="small" onClick={() => handleApplySavedView(record)}>
                Apply View
              </Button>
              <Button size="small" disabled={record.is_default} onClick={() => void handleSetDefaultSavedView(record)}>
                Set Default
              </Button>
              <Button size="small" onClick={() => void handleDeleteSavedView(record)}>
                Delete View
              </Button>
            </Space>
          ),
        },
      ])}
      alertRules={alertRules}
      alertRuleColumns={withSorter([
        { title: "Name", dataIndex: "name", key: "name" },
        { title: "Priority", dataIndex: "priority", key: "priority" },
        { title: "Status", dataIndex: "status", key: "status" },
        {
          title: "Actions",
          key: "actions",
          render: (_: unknown, record: TaskAlertRule) => (
            <Space>
              <Button size="small" onClick={() => void handleToggleAlertRule(record)}>
                {record.status === "active" ? "Pause Rule" : "Resume Rule"}
              </Button>
              <Button size="small" onClick={() => void handleDeleteAlertRule(record)}>
                Delete Rule
              </Button>
            </Space>
          ),
        },
      ])}
      alertEvents={alertEvents}
      alertEventColumns={withSorter([
        { title: "Rule Name", dataIndex: "rule_name", key: "rule_name" },
        { title: "Public User ID", dataIndex: "public_user_id", key: "public_user_id" },
        { title: "Priority", dataIndex: "priority", key: "priority" },
        { title: "Status", dataIndex: "status", key: "status" },
        { title: "Current Value", dataIndex: "current_value", key: "current_value" },
        {
          title: "Actions",
          key: "actions",
          render: (_: unknown, record: TaskMonitorAlertEvent) => (
            <Space>
              <Button size="small" disabled={record.status !== "open"} onClick={() => void handleAcknowledgeAlertEvent(record)}>
                Ack
              </Button>
              <Button size="small" disabled={record.status === "resolved"} onClick={() => void handleResolveAlertEvent(record)}>
                Resolve
              </Button>
            </Space>
          ),
        },
      ])}
      monitorRows={monitorRows}
      monitorRowColumns={withSorter(taskMonitorColumns)}
      loading={monitorData.loading}
      configLoading={monitorConfigData.loading}
    />
  );

  const renderIssuePlans = (): JSX.Element => (
    <TaskIssuePlanEditor
      accountOptions={accountOptions}
      filterAccount={planFilterAccount}
      onFilterAccountChange={(value) => {
        setPlanFilterAccount(value);
        void planData.reload();
      }}
      onCreate={() => setPlanCreateOpen(true)}
      error={planData.error}
      plans={issuePlans}
      columns={withSorter(planColumns)}
      loading={planData.loading}
    />
  );

  const renderSettings = (): JSX.Element => (
    <TaskSystemConfigPanel
      accountOptions={accountOptions}
      settingsAccountId={settingsAccountId}
      settingsSiteId={settingsSiteId}
      settingsSiteOptions={settingsSiteOptions}
      taskSystemConfig={taskSystemConfig}
      taskSystemConfigAuditLogs={taskSystemConfigAuditLogs}
      issuePlanOptions={issuePlans.map((item) => ({ label: item.name, value: item.id }))}
      error={settingsData.error}
      saving={taskSystemConfigSaving}
      onAccountChange={setSettingsAccountId}
      onSiteChange={setSettingsSiteId}
      onSave={() => void handleSaveTaskSystemConfig()}
      onUpdateConfig={updateTaskSystemConfig}
      formatDate={formatDate}
    />
  );

  const currentStats =
    activeTab === "templates"
      ? tplStats
      : activeTab === "instances"
        ? instStats
        : activeTab === "packages"
          ? pkgStats
          : activeTab === "issue-plans"
            ? planStats
          : activeTab === "quotas"
            ? quotaStats
            : activeTab === "manual-add-logs"
              ? manualAddLogStats
            : activeTab === "product-pools"
              ? poolStats
              : activeTab === "monitoring"
                ? taskMonitorStats
                : activeTab === "settings"
                  ? planStats
              : reviewStats;

  return (
    <PageShell
      title="Task Operations"
      subtitle="Manage templates, issue plans, quotas, product pools, review tasks, monitoring, and system settings from one workspace."
      actions={actions}
      stats={currentStats}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: "templates", label: "Templates", children: renderTemplates() },
          { key: "instances", label: "Instances", children: renderInstances() },
          { key: "packages", label: "Packages", children: renderPackages() },
          { key: "issue-plans", label: "Issue Plans", children: renderIssuePlans() },
          { key: "quotas", label: "Quotas", children: renderQuotasPanel() },
          { key: "manual-add-logs", label: "Manual Add Logs", children: renderManualAddLogs() },
          { key: "product-pools", label: "Product Pools", children: renderProductPools() },
          { key: "monitoring", label: "Monitoring", children: renderMonitoringPanel() },
          { key: "reviews", label: "Reviews", children: renderReviews() },
          { key: "settings", label: "System Settings", children: renderSettings() },
        ]}
        size="small"
      />

      <Modal
        title="New Template"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        onOk={() => createForm.submit()}
        confirmLoading={creating}
        okText="Create"
        cancelText="Cancel"
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreateTemplate}>
          <Form.Item label="Template Name" name="name" rules={[{ required: true, message: "Please input template name" }]}><Input placeholder="Daily Task Template" /></Form.Item>
          <Form.Item label="Task Type" name="task_type" rules={[{ required: true, message: "Please select task type" }]}><Select options={[{ label: "Daily", value: "daily" }, { label: "Share", value: "share" }, { label: "Video", value: "video" }, { label: "Custom", value: "custom" }]} placeholder="Select task type" /></Form.Item>
          <Form.Item label="Account" name="account_id"><Select allowClear options={accountOptions} placeholder="Select account" /></Form.Item>
          <Form.Item label="Reward Amount" name="reward_amount"><InputNumber min={0} step={0.5} style={{ width: "100%" }} placeholder="0.00" /></Form.Item>
          <Form.Item label="Description" name="description"><Input.TextArea rows={3} placeholder="Template description" /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title="New Saved View"
        open={savedViewCreateOpen}
        onCancel={() => {
          setSavedViewCreateOpen(false);
          savedViewCreateForm.resetFields();
        }}
        onOk={() => savedViewCreateForm.submit()}
        confirmLoading={savedViewCreating}
        okText="Create"
        cancelText="Cancel"
      >
        <Form form={savedViewCreateForm} layout="vertical" onFinish={handleCreateSavedView}>
          <Form.Item label="Account" name="account_id" rules={[{ required: true, message: "Please select account" }]}><Select options={accountOptions} placeholder="Select account" /></Form.Item>
          <Form.Item label="View Name" name="name" rules={[{ required: true, message: "Please input view name" }]}><Input placeholder="High Risk Tasks" /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title="New Alert Rule"
        open={alertRuleCreateOpen}
        onCancel={() => {
          setAlertRuleCreateOpen(false);
          alertRuleCreateForm.resetFields();
        }}
        onOk={() => alertRuleCreateForm.submit()}
        confirmLoading={alertRuleCreating}
        okText="Create"
        cancelText="Cancel"
      >
        <Form form={alertRuleCreateForm} layout="vertical" onFinish={handleCreateAlertRule}>
          <Form.Item label="Account" name="account_id" rules={[{ required: true, message: "Please select account" }]}><Select options={accountOptions} placeholder="Select account" /></Form.Item>
          <Form.Item label="Rule Name" name="name" rules={[{ required: true, message: "Please input rule name" }]}><Input placeholder="High Amount Alert" /></Form.Item>
          <Form.Item label="Threshold" name="threshold" rules={[{ required: true, message: "Please input threshold" }]}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title="New Issue Plan"
        open={planCreateOpen}
        onCancel={() => {
          setPlanCreateOpen(false);
          setPlanProductCountMode("range");
          planCreateForm.resetFields();
        }}
        onOk={() => planCreateForm.submit()}
        confirmLoading={planCreating}
        okText="Create"
        cancelText="Cancel"
      >
        <Form form={planCreateForm} layout="vertical" onFinish={handleCreateIssuePlan}>
          <Form.Item label="Account" name="account_id" rules={[{ required: true, message: "Please select account" }]}><Select options={accountOptions} placeholder="Select account" /></Form.Item>
          <Form.Item label="Site" name="site_id"><Select allowClear options={sites.map((site) => ({ label: site.name || site.brand_name || site.site_key, value: site.id }))} placeholder="Select site" /></Form.Item>
          <Form.Item label="Plan Name" name="name" rules={[{ required: true, message: "Please input plan name" }]}><Input placeholder="Official Growth Plan" /></Form.Item>
          <Form.Item label="Claim Gate" name="claim_gate"><Select allowClear options={TASK_PLAN_CLAIM_GATE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select claim gate" /></Form.Item>
          <Form.Item label="Issue Anchor" name="issue_anchor"><Select allowClear options={TASK_PLAN_ISSUE_ANCHOR_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select issue anchor" /></Form.Item>
          <Form.Item label="Issue Mode" name="issue_mode"><Select allowClear options={TASK_PLAN_ISSUE_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select issue mode" /></Form.Item>
          <Form.Item label="Require Previous Batch Completed" name="require_previous_batch_completed" valuePropName="checked" initialValue={true}><Checkbox>Block next batch until previous batch completes</Checkbox></Form.Item>
          <Form.Item label="Max Unfinished Batches" name="max_unfinished_batches"><InputNumber min={1} style={{ width: "100%" }} placeholder="1" /></Form.Item>
          <Form.Item label="After Last Rule Mode" name="after_last_rule_mode"><Select allowClear options={TASK_PLAN_AFTER_LAST_RULE_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select mode" /></Form.Item>
          <Form.Item label="Growth Package Count Step" name="growth_package_count_step"><InputNumber min={0} style={{ width: "100%" }} placeholder="1" /></Form.Item>
          <Form.Item label="Growth Amount Step" name="growth_amount_step"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="0.00" /></Form.Item>
          <Form.Item label="Default Product Pool" name="default_product_pool_id"><Select allowClear options={productPools.map((pool) => ({ label: pool.name, value: pool.id }))} placeholder="Select product pool" /></Form.Item>
          <Form.Item label="Default Tolerance Amount" name="default_tolerance_amount"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="10.00" /></Form.Item>
          <Form.Item label="Default Reward Ratio" name="default_reward_ratio"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="0.20" /></Form.Item>
          <Form.Item label="First Day Package Count" name="first_day_package_count" rules={[{ required: true, message: "Please input first day package count" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
          <Form.Item label="First Day Total Amount" name="first_day_total_amount" rules={[{ required: true, message: "Please input first day total amount" }]}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
          <Form.Item label="First Day Allocation Mode" name="first_day_amount_allocation_mode"><Select allowClear options={TASK_AMOUNT_ALLOCATION_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select mode" /></Form.Item>
          <Form.Item label="First Day Manual Package Amounts" name="first_day_package_amounts_text"><Input.TextArea rows={2} placeholder="100,100,100" /></Form.Item>
          <Form.Item label="First Day Product Count Mode" name="first_day_product_count_mode" initialValue="range"><Select options={TASK_PRODUCT_COUNT_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select mode" onChange={(value) => setPlanProductCountMode(value === "fixed" ? "fixed" : "range")} /></Form.Item>
          {planProductCountMode === "fixed" ? (
            <Form.Item label="First Day Fixed Product Count" name="first_day_product_count_fixed" rules={[{ required: true, message: "Please input fixed product count" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
          ) : (
            <>
              <Form.Item label="First Day Min Product Count" name="first_day_product_count_min"><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
              <Form.Item label="First Day Max Product Count" name="first_day_product_count_max"><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
            </>
          )}
          <Form.Item label="First Day Reward Ratio" name="first_day_reward_ratio"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="0.20" /></Form.Item>
          <Form.Item label="First Day Issue Time" name="first_day_issue_time_of_day"><Input placeholder="09:00" /></Form.Item>
          <Form.Item label="First Day Delay Hours" name="first_day_elapsed_delay_hours"><InputNumber min={0} style={{ width: "100%" }} placeholder="24" /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title="New Quota"
        open={quotaCreateOpen}
        onCancel={() => {
          setQuotaCreateOpen(false);
          setQuotaProductCountMode("range");
          quotaCreateForm.resetFields();
          setQuotaPreview([]);
          setQuotaPreviewTotal(null);
        }}
        onOk={() => quotaCreateForm.submit()}
        confirmLoading={quotaCreating}
        okText="Create"
        cancelText="Cancel"
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Form form={quotaCreateForm} layout="vertical" onFinish={handleCreateQuota}>
            <Form.Item label="Account" name="account_id" rules={[{ required: true, message: "Please select account" }]}><Select options={accountOptions} placeholder="Select account" /></Form.Item>
            <Form.Item label="User ID" name="user_id" rules={[{ required: true, message: "Please input user id" }]}><Input placeholder="user-1" /></Form.Item>
            <Form.Item label="Site" name="site_id"><Select allowClear options={sites.map((site) => ({ label: site.name || site.brand_name || site.site_key, value: site.id }))} placeholder="Select site" /></Form.Item>
            <Form.Item label="Day No" name="day_no" rules={[{ required: true, message: "Please input day number" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
            <Form.Item label="Package Count" name="package_count" rules={[{ required: true, message: "Please input package count" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
            <Form.Item label="Day Total Amount" name="day_total_amount" rules={[{ required: true, message: "Please input total amount" }]}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
            <Form.Item label="Tolerance Amount" name="tolerance_amount"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="0.00" /></Form.Item>
            <Form.Item label="Amount Allocation Mode" name="amount_allocation_mode"><Select allowClear options={TASK_AMOUNT_ALLOCATION_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select mode" /></Form.Item>
            <Form.Item label="Manual Package Amounts" name="package_amounts_text"><Input.TextArea rows={2} placeholder="100,100,100" /></Form.Item>
            <Form.Item label="Product Pool" name="product_pool_id" rules={[{ required: true, message: "Please select product pool" }]}><Select options={productPools.map((pool) => ({ label: pool.name, value: pool.id }))} placeholder="Select product pool" /></Form.Item>
            <Form.Item label="Product Count Mode" name="product_count_mode" initialValue="range"><Select options={TASK_PRODUCT_COUNT_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select mode" onChange={(value) => setQuotaProductCountMode(value === "fixed" ? "fixed" : "range")} /></Form.Item>
            {quotaProductCountMode === "fixed" ? (
              <Form.Item label="Fixed Product Count" name="product_count_fixed" rules={[{ required: true, message: "Please input fixed product count" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
            ) : (
              <>
                <Form.Item label="Min Product Count" name="product_count_min"><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
                <Form.Item label="Max Product Count" name="product_count_max"><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
              </>
            )}
            <Form.Item label="Reward Ratio" name="reward_ratio"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="0.20" /></Form.Item>
          </Form>
          <Button onClick={() => void handlePreviewQuota()} loading={quotaPreviewLoading}>Preview Amount Allocation</Button>
          <TaskAmountAllocationPreview amounts={quotaPreview} total={quotaPreviewTotal} />
        </Space>
      </Modal>

      <Modal
        title="Batch Create Quotas"
        open={quotaBatchCreateOpen}
        onCancel={() => {
          setQuotaBatchCreateOpen(false);
          setQuotaBatchProductCountMode("range");
          setQuotaBatchPreview(null);
          quotaBatchCreateForm.resetFields();
        }}
        onOk={() => quotaBatchCreateForm.submit()}
        confirmLoading={quotaBatchCreating}
        okText="Create"
        cancelText="Cancel"
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
        <Form form={quotaBatchCreateForm} layout="vertical" onFinish={handleBatchCreateQuota}>
          <Form.Item label="Account" name="account_id" rules={[{ required: true, message: "Please select account" }]}><Select options={accountOptions} placeholder="Select account" /></Form.Item>
          <Form.Item label="Site" name="site_id"><Select allowClear options={sites.map((site) => ({ label: site.name || site.brand_name || site.site_key, value: site.id }))} placeholder="Select site" /></Form.Item>
          <Form.Item label="User IDs" name="user_ids_text"><Input.TextArea rows={3} placeholder={"user-1\nuser-2\nuser-3"} /></Form.Item>
          <Form.Item label="Owner Staff User ID" name="owner_staff_user_id"><Input placeholder="staff-user-1" /></Form.Item>
          <Form.Item label="Certified Status" name="certified_status">
            <Select
              allowClear
              options={[
                { label: "Certified", value: "certified" },
                { label: "Uncertified", value: "uncertified" },
              ]}
              placeholder="Select certified status"
            />
          </Form.Item>
          <Form.Item label="Min Real Recharge" name="min_total_real_recharge"><InputNumber min={0} step={0.01} style={{ width: "100%" }} /></Form.Item>
          <Form.Item label="Max Real Recharge" name="max_total_real_recharge"><InputNumber min={0} step={0.01} style={{ width: "100%" }} /></Form.Item>
          <Form.Item label="Tag Keys" name="tag_keys_text"><Input.TextArea rows={2} placeholder={"vip\nhigh_value"} /></Form.Item>
          <Form.Item label="Day No" name="day_no" rules={[{ required: true, message: "Please input day number" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
          <Form.Item label="Package Count" name="package_count" rules={[{ required: true, message: "Please input package count" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
          <Form.Item label="Day Total Amount" name="day_total_amount" rules={[{ required: true, message: "Please input total amount" }]}><InputNumber min={0} style={{ width: "100%" }} /></Form.Item>
          <Form.Item label="Tolerance Amount" name="tolerance_amount"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="0.00" /></Form.Item>
          <Form.Item label="Amount Allocation Mode" name="amount_allocation_mode"><Select allowClear options={TASK_AMOUNT_ALLOCATION_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select mode" /></Form.Item>
          <Form.Item label="Manual Package Amounts" name="package_amounts_text"><Input.TextArea rows={2} placeholder="100,100,100" /></Form.Item>
          <Form.Item label="Product Pool" name="product_pool_id" rules={[{ required: true, message: "Please select product pool" }]}><Select options={productPools.map((pool) => ({ label: pool.name, value: pool.id }))} placeholder="Select product pool" /></Form.Item>
          <Form.Item label="Product Count Mode" name="product_count_mode" initialValue="range"><Select options={TASK_PRODUCT_COUNT_MODE_OPTIONS.map((item) => ({ label: item.label, value: item.value }))} placeholder="Select mode" onChange={(value) => setQuotaBatchProductCountMode(value === "fixed" ? "fixed" : "range")} /></Form.Item>
          {quotaBatchProductCountMode === "fixed" ? (
            <Form.Item label="Fixed Product Count" name="product_count_fixed" rules={[{ required: true, message: "Please input fixed product count" }]}><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
          ) : (
            <>
              <Form.Item label="Min Product Count" name="product_count_min"><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
              <Form.Item label="Max Product Count" name="product_count_max"><InputNumber min={1} style={{ width: "100%" }} /></Form.Item>
            </>
          )}
          <Form.Item label="Reward Ratio" name="reward_ratio"><InputNumber min={0} step={0.01} style={{ width: "100%" }} placeholder="0.20" /></Form.Item>
        </Form>
        <Button onClick={() => void handlePreviewBatchQuota()} loading={quotaBatchPreviewLoading}>
          Preview Batch Create
        </Button>
        {quotaBatchPreview ? (
          <Space direction="vertical" style={{ width: "100%" }} size={4}>
            <Typography.Text strong>Batch Preview</Typography.Text>
            <Typography.Text>User Count: {quotaBatchPreview.userCount}</Typography.Text>
            <Typography.Text>Total Quotas: {quotaBatchPreview.totalQuotaCount}</Typography.Text>
            <Typography.Text>Per-user Amounts: {quotaBatchPreview.packageAmounts.join(", ")}</Typography.Text>
            <Typography.Text>Per-user Total: {quotaBatchPreview.computedTotalAmount}</Typography.Text>
            <Typography.Text>Total Batch Amount: {quotaBatchPreview.totalBatchAmount}</Typography.Text>
            <Typography.Text>Product Pool: {quotaBatchPreview.productPoolId}</Typography.Text>
            <Typography.Text>Reward Ratio: {quotaBatchPreview.rewardRatio ?? "-"}</Typography.Text>
          </Space>
        ) : null}
        </Space>
      </Modal>

      <Modal
        title="New Product Pool"
        open={poolCreateOpen}
        onCancel={() => {
          setPoolCreateOpen(false);
          poolCreateForm.resetFields();
        }}
        onOk={() => poolCreateForm.submit()}
        confirmLoading={poolCreating}
        okText="Create"
        cancelText="Cancel"
      >
        <Form form={poolCreateForm} layout="vertical" onFinish={handleCreateProductPool}>
          <Form.Item label="Account" name="account_id" rules={[{ required: true, message: "Please select account" }]}><Select options={accountOptions} placeholder="Select account" /></Form.Item>
          <Form.Item label="Site" name="site_id"><Select allowClear options={sites.map((site) => ({ label: site.name || site.brand_name || site.site_key, value: site.id }))} placeholder="Select site" /></Form.Item>
          <Form.Item label="Pool Name" name="name" rules={[{ required: true, message: "Please input pool name" }]}><Input placeholder="Seasonal Pool" /></Form.Item>
          <Form.Item label="Code" name="code"><Input placeholder="seasonal-pool" /></Form.Item>
          <Form.Item label="Currency" name="currency"><Input placeholder="USD" /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title={poolItemsTarget ? `Manage Pool Items: ${poolItemsTarget.name}` : "Manage Pool Items"}
        open={poolItemsOpen}
        onCancel={() => {
          setPoolItemsOpen(false);
          setPoolItemsTarget(null);
          poolItemCreateForm.resetFields();
        }}
        footer={null}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Form form={poolItemCreateForm} layout="vertical" onFinish={handleCreatePoolItem}>
            <Form.Item label="Product ID" name="product_id" rules={[{ required: true, message: "Please input product id" }]}><Input placeholder="product-001" /></Form.Item>
            <Form.Item label="Product Name" name="product_name" rules={[{ required: true, message: "Please input product name" }]}><Input placeholder="Alpha" /></Form.Item>
            <Form.Item label="Price" name="price" rules={[{ required: true, message: "Please input price" }]}><InputNumber min={0.01} step={0.01} style={{ width: "100%" }} /></Form.Item>
            <Form.Item label="Currency" name="currency"><Input placeholder={poolItemsTarget?.currency || "USD"} /></Form.Item>
            <Form.Item label="Description" name="product_description"><Input.TextArea rows={2} placeholder="Product description" /></Form.Item>
            <Button type="primary" onClick={() => poolItemCreateForm.submit()} loading={poolItemCreating}>Add Item</Button>
          </Form>
          <Table
            dataSource={poolItemsTarget?.items ?? []}
            rowKey="id"
            size="small"
            pagination={false}
            columns={withSorter([
              { title: "Product ID", dataIndex: "productId", key: "productId", width: 140 },
              { title: "Product Name", dataIndex: "productName", key: "productName", width: 160 },
              { title: "Price", dataIndex: "price", key: "price", width: 100 },
              { title: "Currency", dataIndex: "currency", key: "currency", width: 100 },
              {
                title: "Actions",
                key: "actions",
                width: 100,
                render: (_: unknown, record: { id: string }) => (
                  <Button size="small" danger onClick={() => void handleDeletePoolItem(record.id)}>Delete Item</Button>
                ),
              },
            ])}
          />
        </Space>
      </Modal>

      <TaskInstanceDetailDrawer
        open={packageDetailOpen}
        loading={packageDetailLoading}
        detail={packageDetail}
        onClose={() => {
          setPackageDetailOpen(false);
          setPackageDetail(null);
        }}
        formatMoney={formatMoney}
        itemColumns={withSorter(detailItemColumns)}
        logColumns={withSorter(detailLogColumns)}
      />

      <TaskManualAddDrawer
        open={manualAddOpen}
        loading={manualAddLoading}
        submitting={manualAddSubmitting}
        previewLoading={manualAddPreviewLoading}
        candidates={manualAddCandidates}
        selectedIds={manualAddSelectedIds}
        reason={manualAddReason}
        preview={manualAddPreview}
        onClose={() => {
          setManualAddOpen(false);
          setManualAddPackageId(null);
          setManualAddCandidates([]);
          setManualAddSelectedIds([]);
          setManualAddReason("");
    setManualAddPreview(null);
        }}
        onSubmit={() => void handleSubmitManualAdd()}
        onReasonChange={setManualAddReason}
        onToggleCandidate={(candidateId, checked) => {
          setManualAddSelectedIds((current) =>
            checked ? [...current, candidateId] : current.filter((value) => value !== candidateId),
          );
        }}
        onPreview={() => void handlePreviewManualAdd()}
        formatMoney={formatMoney}
        columns={withSorter([
          { title: "Product Name", dataIndex: "product_name", key: "product_name" },
          { title: "Product ID", dataIndex: "product_id", key: "product_id" },
          { title: "Price", dataIndex: "price", key: "price" },
        ])}
      />
    </PageShell>
  );
}

export default TasksPage;
