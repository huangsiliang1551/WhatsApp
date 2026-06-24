import { useEffect, useMemo, useState, type FormEvent, type JSX } from "react";

import { Panel } from "../components/Panel";
import { useAppStore } from "../stores/appStore";
import {
  createTemplateDraft,
  getTemplateAnalytics,
  getTemplateStatsSummary,
  isApiFeatureUnavailable,
  listMediaAssets,
  listMessageTemplates,
  listMetaAccounts,
  listTemplateDailyStats,
  listTemplateSendLogs,
  rebuildTemplateStats,
  sendTemplateMessage,
  submitTemplate,
  syncTemplates,
  updateTemplateDraft,
  updateTemplateStatus,
  type MediaAssetView,
  type MessageTemplateView,
  type MetaWabaAccount,
  type TemplateCategory,
  type TemplateSendLogView,
  type TemplateSendResponse,
  type TemplateSendStatus,
  type TemplateStatsDailyRow,
  type TemplateStatsDetailResponse,
  type TemplateStatsSummary,
  type TemplateStatus,
  type TemplateSubmitResponse,
  type TemplateSyncResponse,
} from "../services/api";

type TemplateFilters = {
  account_id: string;
  waba_id: string;
  status: "ALL" | TemplateStatus;
  language: string;
};

type DraftFormState = {
  account_id: string;
  waba_id: string;
  name: string;
  language: string;
  category: TemplateCategory;
  header_text: string;
  header_media_asset_id: string;
  header_media_handle: string;
  body_text: string;
  footer_text: string;
  sample_variables_text: string;
};

type StatusFormState = {
  status: TemplateStatus;
  meta_template_id: string;
  rejected_reason: string;
};

type SendFormState = {
  account_id: string;
  conversation_id: string;
  phone_number_id: string;
  agent_id: string;
  idempotency_key: string;
  variables_text: string;
};

type SyncFormState = {
  account_id: string;
  waba_id: string;
  import_missing: boolean;
};

type StatsFilters = {
  account_id: string;
  waba_id: string;
  phone_number_id: string;
  category: "ALL" | TemplateCategory;
  language: string;
  date_from: string;
  date_to: string;
};

type LogFilters = {
  status: "ALL" | TemplateSendStatus;
  phone_number_id: string;
  date_from: string;
  date_to: string;
  conversation_id: string;
};

const CATEGORY_OPTIONS: Array<{ value: TemplateCategory; label: string }> = [
  { value: "UTILITY", label: "通知服务" },
  { value: "MARKETING", label: "营销" },
  { value: "AUTHENTICATION", label: "验证码" },
];

const STATUS_OPTIONS: Array<{ value: TemplateStatus; label: string }> = [
  { value: "DRAFT", label: "草稿" },
  { value: "PENDING", label: "待审核" },
  { value: "APPROVED", label: "已批准" },
  { value: "REJECTED", label: "已拒绝" },
  { value: "DISABLED", label: "已停用" },
  { value: "PAUSED", label: "已暂停" },
];

const SEND_STATUS_OPTIONS: Array<{ value: "ALL" | TemplateSendStatus; label: string }> = [
  { value: "ALL", label: "全部状态" },
  { value: "QUEUED", label: "已入队" },
  { value: "SENT", label: "已发送" },
  { value: "DELIVERED", label: "已送达" },
  { value: "READ", label: "已读" },
  { value: "FAILED", label: "失败" },
];

const DEFAULT_ACCOUNT_ID = "demo-account-cn";

const INITIAL_FILTERS: TemplateFilters = {
  account_id: "ALL",
  waba_id: "ALL",
  status: "ALL",
  language: "",
};

const INITIAL_DRAFT_FORM: DraftFormState = {
  account_id: DEFAULT_ACCOUNT_ID,
  waba_id: "",
  name: "order_update_cn",
  language: "zh_CN",
  category: "UTILITY",
  header_text: "",
  header_media_asset_id: "",
  header_media_handle: "",
  body_text: "您好，{{customer_name}}，您的订单 {{order_id}} 已进入发货流程。",
  footer_text: "如需人工协助，请直接回复这条消息。",
  sample_variables_text: "customer_name=张三\norder_id=SO-10001",
};

const INITIAL_STATUS_FORM: StatusFormState = {
  status: "DRAFT",
  meta_template_id: "",
  rejected_reason: "",
};

const INITIAL_SEND_FORM: SendFormState = {
  account_id: DEFAULT_ACCOUNT_ID,
  conversation_id: "",
  phone_number_id: "",
  agent_id: "",
  idempotency_key: "",
  variables_text: "",
};

const INITIAL_SYNC_FORM: SyncFormState = {
  account_id: DEFAULT_ACCOUNT_ID,
  waba_id: "",
  import_missing: true,
};

const INITIAL_STATS_FILTERS: StatsFilters = {
  account_id: "ALL",
  waba_id: "ALL",
  phone_number_id: "ALL",
  category: "ALL",
  language: "",
  date_from: "",
  date_to: "",
};

const INITIAL_LOG_FILTERS: LogFilters = {
  status: "ALL",
  phone_number_id: "ALL",
  date_from: "",
  date_to: "",
  conversation_id: "",
};

const EMPTY_STATS: TemplateStatsSummary = {
  send_count: 0,
  delivered_count: 0,
  delivery_rate: 0,
  read_count: 0,
  read_rate: 0,
  read_rate_by_send: 0,
  failed_count: 0,
  billable_count: 0,
  estimated_cost: 0,
  estimated_cost_status: "not_applicable",
  estimated_cost_note: null,
};

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  return new Date(value).toLocaleString("zh-CN");
}

function formatLanguage(code: string): string {
  return code.replace("_", "-").toUpperCase();
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatCost(value: number): string {
  return value.toFixed(4);
}

function formatOptionalText(value: string | null | undefined, fallback: string = "未设置"): string {
  return value && value.trim().length > 0 ? value : fallback;
}

function formatConversationText(value: string | null | undefined): string {
  return formatOptionalText(value, "未关联");
}

function formatAccountLabel(accountId: string, accountMap: Map<string, MetaWabaAccount>): string {
  const account = accountMap.get(accountId);
  return account ? `${account.display_name} (${accountId})` : accountId;
}

function formatTemplateStatus(status: TemplateStatus): string {
  return STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
}

function formatTemplateCategory(category: TemplateCategory): string {
  return CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? category;
}

function formatSendStatus(status: TemplateSendStatus): string {
  return SEND_STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
}

function formatCostStatus(status: string): string {
  switch (status) {
    case "estimated":
      return "预估";
    case "not_applicable":
      return "不适用";
    case "pending":
      return "待计算";
    case "partial":
      return "部分统计";
    default:
      return status;
  }
}

function getStatusBadgeClass(status: TemplateStatus): string {
  if (status === "APPROVED") {
    return "badge badge-success";
  }
  if (status === "REJECTED") {
    return "badge badge-warning";
  }
  if (status === "PAUSED") {
    return "badge badge-mode";
  }
  if (status === "DISABLED") {
    return "badge badge-muted";
  }
  return "badge badge-neutral";
}

function getSendStatusBadgeClass(status: TemplateSendStatus): string {
  if (status === "READ" || status === "DELIVERED" || status === "SENT") {
    return "badge badge-success";
  }
  if (status === "FAILED") {
    return "badge badge-warning";
  }
  return "badge badge-neutral";
}

function parseVariables(input: string): Record<string, string> {
  const result: Record<string, string> = {};
  const lines = input
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  for (const line of lines) {
    const index = line.indexOf("=");
    if (index <= 0) {
      throw new Error("模板变量必须使用 key=value，每行一组。");
    }
    const key = line.slice(0, index).trim();
    const value = line.slice(index + 1).trim();
    if (!key) {
      throw new Error("模板变量名不能为空。");
    }
    result[key] = value;
  }

  return result;
}

function stringifyVariables(variables: Record<string, string>): string {
  return Object.entries(variables)
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
}

function toOptionalString(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function getTemplatePreview(template: MessageTemplateView): string {
  const body = template.body_text.trim();
  return body.length > 64 ? `${body.slice(0, 64)}...` : body;
}

function unique<T>(values: T[]): T[] {
  return Array.from(new Set(values));
}

function buildAccountOptions(
  accounts: MetaWabaAccount[],
  ...extraValues: Array<string | null | undefined>
): string[] {
  return unique(
    [...accounts.map((account) => account.account_id), ...extraValues]
      .filter((value): value is string => Boolean(value && value.trim()))
      .sort((left, right) => left.localeCompare(right))
  );
}

function filterAccountsByScope(accounts: MetaWabaAccount[], accountId: string): MetaWabaAccount[] {
  if (accountId === "ALL") {
    return accounts;
  }
  return accounts.filter((account) => account.account_id === accountId);
}

function buildWabaOptions(
  accounts: MetaWabaAccount[],
  accountId: string,
  ...extraValues: Array<string | null | undefined>
): string[] {
  return unique(
    [
      ...filterAccountsByScope(accounts, accountId)
        .map((account) => account.waba_id)
        .filter((value): value is string => Boolean(value)),
      ...extraValues.filter((value): value is string => Boolean(value && value.trim())),
    ].sort((left, right) => left.localeCompare(right))
  );
}

function buildPhoneOptions(
  accounts: MetaWabaAccount[],
  accountId: string,
  wabaId: string,
  ...extraValues: Array<string | null | undefined>
): string[] {
  return unique(
    [
      ...filterAccountsByScope(accounts, accountId)
        .filter((account) => wabaId === "ALL" || account.waba_id === wabaId)
        .flatMap((account) => account.phone_numbers.map((phone) => phone.phone_number_id))
        .filter((value): value is string => Boolean(value)),
      ...extraValues.filter((value): value is string => Boolean(value && value.trim())),
    ].sort((left, right) => left.localeCompare(right))
  );
}

function buildTemplateFormState(template: MessageTemplateView): DraftFormState {
  return {
    account_id: template.account_id,
    waba_id: template.waba_id ?? "",
    name: template.name,
    language: template.language,
    category: template.category,
    header_text: template.header_text ?? "",
    header_media_asset_id: template.header_media_asset_id ?? "",
    header_media_handle: template.header_media_handle ?? "",
    body_text: template.body_text,
    footer_text: template.footer_text ?? "",
    sample_variables_text: stringifyVariables(template.sample_variables),
  };
}

function buildStatusFormState(template: MessageTemplateView): StatusFormState {
  return {
    status: template.status,
    meta_template_id: template.meta_template_id ?? "",
    rejected_reason: template.rejected_reason ?? "",
  };
}

function buildDefaultSendVariables(template: MessageTemplateView): string {
  return stringifyVariables(template.sample_variables);
}

function buildHeaderAssetOptions(
  assets: MediaAssetView[],
  template: MessageTemplateView | null
): MediaAssetView[] {
  if (!template) {
    return [];
  }
  return assets.filter((asset) => {
    if (asset.account_id !== template.account_id) {
      return false;
    }
    if (template.waba_id && asset.waba_id && asset.waba_id !== template.waba_id) {
      return false;
    }
    if (!isTemplateHeaderAssetTypeSupported(asset)) {
      return false;
    }
    return asset.is_active;
  });
}

function isTemplateHeaderAssetTypeSupported(asset: MediaAssetView): boolean {
  return ["image", "video", "document"].includes(asset.asset_type);
}

export function TemplatePage(): JSX.Element {
  const openWorkspacePage = useAppStore((state) => state.openWorkspacePage);
  const openAuditPage = useAppStore((state) => state.openAuditPage);

  const [accounts, setAccounts] = useState<MetaWabaAccount[]>([]);
  const [templates, setTemplates] = useState<MessageTemplateView[]>([]);
  const [mediaAssets, setMediaAssets] = useState<MediaAssetView[]>([]);
  const [sendLogs, setSendLogs] = useState<TemplateSendLogView[]>([]);
  const [dailyStats, setDailyStats] = useState<TemplateStatsDailyRow[]>([]);
  const [statsSummary, setStatsSummary] = useState<TemplateStatsSummary>(EMPTY_STATS);
  const [analytics, setAnalytics] = useState<TemplateStatsDetailResponse | null>(null);

  const [filters, setFilters] = useState<TemplateFilters>(INITIAL_FILTERS);
  const [statsFilters, setStatsFilters] = useState<StatsFilters>(INITIAL_STATS_FILTERS);
  const [logFilters, setLogFilters] = useState<LogFilters>(INITIAL_LOG_FILTERS);

  const [draftForm, setDraftForm] = useState<DraftFormState>(INITIAL_DRAFT_FORM);
  const [editForm, setEditForm] = useState<DraftFormState>(INITIAL_DRAFT_FORM);
  const [statusForm, setStatusForm] = useState<StatusFormState>(INITIAL_STATUS_FORM);
  const [syncForm, setSyncForm] = useState<SyncFormState>(INITIAL_SYNC_FORM);
  const [sendForm, setSendForm] = useState<SendFormState>(INITIAL_SEND_FORM);

  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [lastSubmitResult, setLastSubmitResult] = useState<TemplateSubmitResponse | null>(null);
  const [lastSyncResult, setLastSyncResult] = useState<TemplateSyncResponse | null>(null);
  const [lastSendResult, setLastSendResult] = useState<TemplateSendResponse | null>(null);

  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  const accountMap = useMemo(
    () => new Map(accounts.map((account) => [account.account_id, account])),
    [accounts]
  );

  const templateWabaOptions = useMemo(
    () => buildWabaOptions(accounts, filters.account_id),
    [accounts, filters.account_id]
  );
  const draftWabaOptions = useMemo(
    () => buildWabaOptions(accounts, draftForm.account_id, draftForm.waba_id),
    [accounts, draftForm.account_id, draftForm.waba_id]
  );
  const statsWabaOptions = useMemo(
    () => buildWabaOptions(accounts, statsFilters.account_id),
    [accounts, statsFilters.account_id]
  );
  const statsPhoneOptions = useMemo(
    () =>
      buildPhoneOptions(
        accounts,
        statsFilters.account_id,
        statsFilters.waba_id,
        statsFilters.phone_number_id !== "ALL" ? statsFilters.phone_number_id : undefined
      ),
    [accounts, statsFilters.account_id, statsFilters.phone_number_id, statsFilters.waba_id]
  );
  const logPhoneOptions = useMemo(
    () =>
      buildPhoneOptions(
        accounts,
        filters.account_id,
        filters.waba_id,
        logFilters.phone_number_id !== "ALL" ? logFilters.phone_number_id : undefined
      ),
    [accounts, filters.account_id, filters.waba_id, logFilters.phone_number_id]
  );
  const syncWabaOptions = useMemo(
    () => buildWabaOptions(accounts, syncForm.account_id, syncForm.waba_id),
    [accounts, syncForm.account_id, syncForm.waba_id]
  );

  const filteredTemplates = useMemo(() => {
    return templates.filter((template) => {
      if (filters.account_id !== "ALL" && template.account_id !== filters.account_id) {
        return false;
      }
      if (filters.waba_id !== "ALL" && template.waba_id !== filters.waba_id) {
        return false;
      }
      if (filters.status !== "ALL" && template.status !== filters.status) {
        return false;
      }
      if (filters.language.trim() && !template.language.includes(filters.language.trim())) {
        return false;
      }
      return true;
    });
  }, [filters, templates]);

  const selectedTemplate = useMemo(
    () => filteredTemplates.find((template) => template.template_id === selectedTemplateId) ?? null,
    [filteredTemplates, selectedTemplateId]
  );
  const accountOptions = useMemo(
    () =>
      buildAccountOptions(
        accounts,
        DEFAULT_ACCOUNT_ID,
        draftForm.account_id,
        syncForm.account_id,
        selectedTemplate?.account_id,
        sendForm.account_id
      ),
    [accounts, draftForm.account_id, selectedTemplate?.account_id, sendForm.account_id, syncForm.account_id]
  );
  const editWabaOptions = useMemo(
    () => buildWabaOptions(accounts, selectedTemplate?.account_id ?? DEFAULT_ACCOUNT_ID, editForm.waba_id),
    [accounts, editForm.waba_id, selectedTemplate?.account_id]
  );
  const lastSendExternalConversationId = useMemo(
    () => (lastSendResult ? toOptionalString(lastSendResult.external_conversation_id ?? "") ?? null : null),
    [lastSendResult]
  );

  const scopedHeaderAssets = useMemo(
    () => buildHeaderAssetOptions(mediaAssets, selectedTemplate),
    [mediaAssets, selectedTemplate]
  );
  const draftHeaderAssets = useMemo(
    () =>
      mediaAssets.filter((asset) => {
        if (!asset.is_active || asset.account_id !== draftForm.account_id) {
          return false;
        }
        if (draftForm.waba_id && asset.waba_id && asset.waba_id !== draftForm.waba_id) {
          return false;
        }
        return isTemplateHeaderAssetTypeSupported(asset);
      }),
    [draftForm.account_id, draftForm.waba_id, mediaAssets]
  );

  const sendPhoneOptions = useMemo(() => {
    if (!selectedTemplate) {
      return [];
    }
    return buildPhoneOptions(
      accounts,
      selectedTemplate.account_id,
      selectedTemplate.waba_id ?? "ALL",
      sendForm.phone_number_id
    );
  }, [accounts, selectedTemplate, sendForm.phone_number_id]);

  const filteredLogs = useMemo(() => {
    return sendLogs.filter((log) => {
      if (
        logFilters.status !== "ALL" &&
        log.status !== logFilters.status
      ) {
        return false;
      }
      if (
        logFilters.phone_number_id !== "ALL" &&
        log.phone_number_id !== logFilters.phone_number_id
      ) {
        return false;
      }
      if (logFilters.conversation_id.trim()) {
        const externalConversationId = log.external_conversation_id ?? log.conversation_id ?? "";
        if (!externalConversationId.includes(logFilters.conversation_id.trim())) {
          return false;
        }
      }
      return true;
    });
  }, [logFilters, sendLogs]);

  useEffect(() => {
    if (filteredTemplates.length === 0) {
      setSelectedTemplateId(null);
      return;
    }
    if (!selectedTemplateId || !filteredTemplates.some((item) => item.template_id === selectedTemplateId)) {
      setSelectedTemplateId(filteredTemplates[0].template_id);
    }
  }, [filteredTemplates, selectedTemplateId]);

  useEffect(() => {
    if (!selectedTemplate) {
      setEditForm(INITIAL_DRAFT_FORM);
      setStatusForm(INITIAL_STATUS_FORM);
      setSendForm((current) => ({
        ...current,
        account_id: filters.account_id !== "ALL" ? filters.account_id : DEFAULT_ACCOUNT_ID,
        conversation_id: "",
        phone_number_id: "",
        variables_text: "",
      }));
      setAnalytics(null);
      return;
    }

    setEditForm(buildTemplateFormState(selectedTemplate));
    setStatusForm(buildStatusFormState(selectedTemplate));
    setSyncForm((current) => ({
      ...current,
      account_id: selectedTemplate.account_id,
      waba_id: selectedTemplate.waba_id ?? "",
    }));
    setSendForm((current) => ({
      ...current,
      account_id: selectedTemplate.account_id,
      phone_number_id: "",
      variables_text: buildDefaultSendVariables(selectedTemplate),
    }));
  }, [filters.account_id, selectedTemplate]);

  useEffect(() => {
    void refreshCoreData();
  }, [
    filters.account_id,
    filters.language,
    filters.status,
    filters.waba_id,
    logFilters.conversation_id,
    logFilters.date_from,
    logFilters.date_to,
    logFilters.phone_number_id,
    logFilters.status,
  ]);

  useEffect(() => {
    void refreshStats();
  }, [
    statsFilters.account_id,
    statsFilters.category,
    statsFilters.date_from,
    statsFilters.date_to,
    statsFilters.language,
    statsFilters.phone_number_id,
    statsFilters.waba_id,
  ]);

  useEffect(() => {
    if (!selectedTemplate) {
      setAnalytics(null);
      return;
    }
    void refreshAnalytics(selectedTemplate.template_id);
  }, [
    selectedTemplate?.template_id,
    statsFilters.date_from,
    statsFilters.date_to,
    statsFilters.phone_number_id,
    statsFilters.waba_id,
  ]);

  async function refreshCoreData(): Promise<void> {
    setRefreshing(true);
    const nextWarnings: string[] = [];

    const [accountResult, templateResult, mediaResult, logResult] = await Promise.allSettled([
      listMetaAccounts(),
      listMessageTemplates(
        filters.account_id !== "ALL" ? filters.account_id : undefined,
        filters.waba_id !== "ALL" ? filters.waba_id : undefined,
        {
          ...(filters.status !== "ALL" ? { status: filters.status } : {}),
          ...(filters.language.trim() ? { language: filters.language.trim() } : {}),
        }
      ),
      listMediaAssets({
        account_id: filters.account_id !== "ALL" ? filters.account_id : undefined,
        waba_id: filters.waba_id !== "ALL" ? filters.waba_id : undefined,
        is_active: true,
      }),
      listTemplateSendLogs({
        account_id: filters.account_id !== "ALL" ? filters.account_id : undefined,
        waba_id: filters.waba_id !== "ALL" ? filters.waba_id : undefined,
        status: logFilters.status !== "ALL" ? logFilters.status : undefined,
        phone_number_id:
          logFilters.phone_number_id !== "ALL" ? logFilters.phone_number_id : undefined,
        external_conversation_id: toOptionalString(logFilters.conversation_id),
        date_from: toOptionalString(logFilters.date_from),
        date_to: toOptionalString(logFilters.date_to),
        limit: 40,
      }),
    ]);

    if (accountResult.status === "fulfilled") {
      setAccounts(accountResult.value);
    } else {
      setAccounts([]);
      nextWarnings.push("Meta 账号列表加载失败。");
    }

    if (templateResult.status === "fulfilled") {
      setTemplates(templateResult.value);
    } else {
      setTemplates([]);
      setError("模板列表加载失败。");
    }

    if (mediaResult.status === "fulfilled") {
      setMediaAssets(mediaResult.value);
    } else if (isApiFeatureUnavailable(mediaResult.reason)) {
      setMediaAssets([]);
      nextWarnings.push("媒体资源接口尚未就绪，模板头部素材列表暂不可用。");
    } else {
      setMediaAssets([]);
      nextWarnings.push("模板头部素材列表加载失败。");
    }

    if (logResult.status === "fulfilled") {
      setSendLogs(logResult.value);
    } else if (isApiFeatureUnavailable(logResult.reason)) {
      setSendLogs([]);
      nextWarnings.push("模板发送日志接口尚未就绪。");
    } else {
      setSendLogs([]);
      nextWarnings.push("模板发送日志加载失败。");
    }

    setWarnings(nextWarnings);
    setLastUpdatedAt(new Date().toISOString());
    setRefreshing(false);
  }

  async function refreshStats(): Promise<void> {
    const params = {
      account_id: statsFilters.account_id !== "ALL" ? statsFilters.account_id : undefined,
      waba_id: statsFilters.waba_id !== "ALL" ? statsFilters.waba_id : undefined,
      phone_number_id:
        statsFilters.phone_number_id !== "ALL" ? statsFilters.phone_number_id : undefined,
      category: statsFilters.category !== "ALL" ? statsFilters.category : undefined,
      language: toOptionalString(statsFilters.language),
      date_from: toOptionalString(statsFilters.date_from),
      date_to: toOptionalString(statsFilters.date_to),
    };

    const [summaryResult, dailyResult] = await Promise.allSettled([
      getTemplateStatsSummary(params),
      listTemplateDailyStats(params),
    ]);

    if (summaryResult.status === "fulfilled") {
      setStatsSummary(summaryResult.value);
    } else if (!isApiFeatureUnavailable(summaryResult.reason)) {
      setStatsSummary(EMPTY_STATS);
      setWarnings((current) =>
        Array.from(new Set([...current, "模板统计概览加载失败。"]))
      );
    } else {
      setStatsSummary(EMPTY_STATS);
    }

    if (dailyResult.status === "fulfilled") {
      setDailyStats(dailyResult.value);
    } else if (!isApiFeatureUnavailable(dailyResult.reason)) {
      setDailyStats([]);
      setWarnings((current) =>
        Array.from(new Set([...current, "模板按日统计加载失败。"]))
      );
    } else {
      setDailyStats([]);
    }
  }

  async function refreshAnalytics(templateId: string): Promise<void> {
    try {
      const detail = await getTemplateAnalytics(templateId, {
        waba_id: statsFilters.waba_id !== "ALL" ? statsFilters.waba_id : undefined,
        phone_number_id:
          statsFilters.phone_number_id !== "ALL" ? statsFilters.phone_number_id : undefined,
        date_from: toOptionalString(statsFilters.date_from),
        date_to: toOptionalString(statsFilters.date_to),
      });
      setAnalytics(detail);
    } catch (fetchError) {
      if (!isApiFeatureUnavailable(fetchError)) {
        setWarnings((current) =>
          Array.from(new Set([...current, "单模板分析加载失败。"]))
        );
      }
      setAnalytics(null);
    }
  }

  async function handleCreateDraft(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPendingAction("create-draft");
    setError(null);
    setNotice(null);
    try {
      const created = await createTemplateDraft({
        account_id: draftForm.account_id,
        waba_id: toOptionalString(draftForm.waba_id),
        name: draftForm.name.trim(),
        language: draftForm.language.trim(),
        category: draftForm.category,
        header_text: toOptionalString(draftForm.header_text),
        header_media_asset_id: toOptionalString(draftForm.header_media_asset_id),
        header_media_handle: toOptionalString(draftForm.header_media_handle),
        body_text: draftForm.body_text.trim(),
        footer_text: toOptionalString(draftForm.footer_text),
        sample_variables: parseVariables(draftForm.sample_variables_text),
      });
      setSelectedTemplateId(created.template_id);
      setNotice(`已创建模板草稿 ${created.name}。`);
      await refreshCoreData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建模板草稿失败。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleUpdateDraft(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedTemplate) {
      return;
    }
    setPendingAction("update-draft");
    setError(null);
    setNotice(null);
    try {
      const updated = await updateTemplateDraft(selectedTemplate.template_id, {
        waba_id: toOptionalString(editForm.waba_id),
        name: editForm.name.trim(),
        language: editForm.language.trim(),
        category: editForm.category,
        header_text: toOptionalString(editForm.header_text),
        header_media_asset_id: toOptionalString(editForm.header_media_asset_id),
        header_media_handle: toOptionalString(editForm.header_media_handle),
        body_text: editForm.body_text.trim(),
        footer_text: toOptionalString(editForm.footer_text),
        sample_variables: parseVariables(editForm.sample_variables_text),
      });
      setSelectedTemplateId(updated.template_id);
      setNotice(`已更新模板草稿 ${updated.name}。`);
      await refreshCoreData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "更新模板草稿失败。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleUpdateStatus(): Promise<void> {
    if (!selectedTemplate) {
      return;
    }
    setPendingAction("update-status");
    setError(null);
    setNotice(null);
    try {
      const updated = await updateTemplateStatus(selectedTemplate.template_id, {
        status: statusForm.status,
        meta_template_id: toOptionalString(statusForm.meta_template_id),
        rejected_reason:
          statusForm.status === "REJECTED" ? toOptionalString(statusForm.rejected_reason) : undefined,
      });
      setSelectedTemplateId(updated.template_id);
      setNotice(`模板状态已更新为 ${formatTemplateStatus(updated.status)}。`);
      await refreshCoreData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "更新模板状态失败。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSubmitTemplate(): Promise<void> {
    if (!selectedTemplate) {
      return;
    }
    setPendingAction("submit-template");
    setError(null);
    setNotice(null);
    try {
      const result = await submitTemplate(selectedTemplate.template_id);
      setLastSubmitResult(result);
      setNotice(`模板 ${result.template.name} 已提交到 Provider。`);
      await refreshCoreData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "提交模板失败。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSyncTemplates(): Promise<void> {
    setPendingAction("sync-templates");
    setError(null);
    setNotice(null);
    try {
      const result = await syncTemplates({
        account_id: syncForm.account_id,
        waba_id: syncForm.waba_id.trim(),
        import_missing: syncForm.import_missing,
      });
      setLastSyncResult(result);
      setNotice(`模板同步完成，新增 ${result.created_count}，更新 ${result.updated_count}。`);
      await refreshCoreData();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "同步模板失败。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleSendTemplate(): Promise<void> {
    if (!selectedTemplate) {
      return;
    }
    setPendingAction("send-template");
    setError(null);
    setNotice(null);
    try {
      const result = await sendTemplateMessage(selectedTemplate.template_id, {
        account_id: sendForm.account_id,
        conversation_id: sendForm.conversation_id.trim(),
        phone_number_id: toOptionalString(sendForm.phone_number_id),
        agent_id: toOptionalString(sendForm.agent_id),
        idempotency_key: toOptionalString(sendForm.idempotency_key),
        variables: parseVariables(sendForm.variables_text),
      });
      setLastSendResult(result);
      setNotice(`模板 ${selectedTemplate.name} 已发送到外部会话 ${result.external_conversation_id}。`);
      await refreshCoreData();
      await refreshStats();
      await refreshAnalytics(selectedTemplate.template_id);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "发送模板失败。");
    } finally {
      setPendingAction(null);
    }
  }

  async function handleRebuildStats(): Promise<void> {
    setPendingAction("rebuild-stats");
    setError(null);
    setNotice(null);
    try {
      await rebuildTemplateStats({
        account_id: statsFilters.account_id !== "ALL" ? statsFilters.account_id : undefined,
        waba_id: statsFilters.waba_id !== "ALL" ? statsFilters.waba_id : undefined,
        phone_number_id:
          statsFilters.phone_number_id !== "ALL" ? statsFilters.phone_number_id : undefined,
        date_from: toOptionalString(statsFilters.date_from),
        date_to: toOptionalString(statsFilters.date_to),
      });
      setNotice("模板统计已重建。");
      await refreshStats();
      if (selectedTemplate) {
        await refreshAnalytics(selectedTemplate.template_id);
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "重建模板统计失败。");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <Panel title="消息模板">
      <section className="dashboard-section">
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>模板概览</strong>
              <p className="muted">
                这里维护模板草稿、审核状态、发送验证和统计分析，作用域覆盖账号、WABA 和
                Phone-Number-ID。
              </p>
            </div>
            <span className="badge badge-neutral">
              {refreshing ? "刷新中" : `模板 ${filteredTemplates.length}`}
            </span>
          </div>

          {error ? <p className="status-error">{error}</p> : null}
          {notice ? <p className="status-ok">{notice}</p> : null}
          {warnings.map((warning) => (
            <p className="info-banner" key={warning}>
              {warning}
            </p>
          ))}

          <div className="meta-form">
            <label>
              账号
              <select
                value={filters.account_id}
                onChange={(event) => {
                  const accountId = event.target.value;
                  setFilters((current) => ({
                    ...current,
                    account_id: accountId,
                    waba_id: "ALL",
                  }));
                  setStatsFilters((current) => ({
                    ...current,
                    account_id: accountId,
                    waba_id: "ALL",
                    phone_number_id: "ALL",
                  }));
                  setLogFilters((current) => ({
                    ...current,
                    phone_number_id: "ALL",
                  }));
                }}
              >
                <option value="ALL">全部账号</option>
                {accountOptions.map((accountId) => (
                  <option key={accountId} value={accountId}>
                    {formatAccountLabel(accountId, accountMap)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              WABA
              <select
                value={filters.waba_id}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    waba_id: event.target.value,
                  }))
                }
              >
                <option value="ALL">全部 WABA</option>
                {templateWabaOptions.map((wabaId) => (
                  <option key={wabaId} value={wabaId}>
                    {wabaId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              状态
              <select
                value={filters.status}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    status: event.target.value as "ALL" | TemplateStatus,
                  }))
                }
              >
                <option value="ALL">全部状态</option>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              语言
              <input
                value={filters.language}
                onChange={(event) =>
                  setFilters((current) => ({
                    ...current,
                    language: event.target.value,
                  }))
                }
                placeholder="如 zh_CN"
              />
            </label>
          </div>

          <p className="muted">
            最近刷新：{formatTimestamp(lastUpdatedAt)}。当前只保留正式模板状态，不再展示旧别名。
          </p>
        </article>
      </section>

      <section className="dashboard-section" style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr 1fr" }}>
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>新建模板草稿</strong>
              <p className="muted">先录入正文，再补头部素材或变量示例。</p>
            </div>
          </div>

          <form className="meta-form" onSubmit={(event) => void handleCreateDraft(event)}>
            <label>
              账号
              <select
                value={draftForm.account_id}
                onChange={(event) =>
                  setDraftForm((current) => ({
                    ...current,
                    account_id: event.target.value,
                    waba_id: "",
                    header_media_asset_id: "",
                  }))
                }
              >
                {accountOptions.map((accountId) => (
                  <option key={accountId} value={accountId}>
                    {formatAccountLabel(accountId, accountMap)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              WABA
              <select
                value={draftForm.waba_id}
                onChange={(event) =>
                  setDraftForm((current) => ({
                    ...current,
                    waba_id: event.target.value,
                    header_media_asset_id: "",
                  }))
                }
              >
                <option value="">不绑定 WABA</option>
                {draftWabaOptions.map((wabaId) => (
                  <option key={wabaId} value={wabaId}>
                    {wabaId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              模板名称
              <input
                value={draftForm.name}
                onChange={(event) =>
                  setDraftForm((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>

            <label>
              语言
              <input
                value={draftForm.language}
                onChange={(event) =>
                  setDraftForm((current) => ({ ...current, language: event.target.value }))
                }
              />
            </label>

            <label>
              分类
              <select
                value={draftForm.category}
                onChange={(event) =>
                  setDraftForm((current) => ({
                    ...current,
                    category: event.target.value as TemplateCategory,
                  }))
                }
              >
                {CATEGORY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              头部文案
              <input
                value={draftForm.header_text}
                onChange={(event) =>
                  setDraftForm((current) => ({ ...current, header_text: event.target.value }))
                }
              />
            </label>

            <label>
              头部素材
              <select
                value={draftForm.header_media_asset_id}
                onChange={(event) =>
                  setDraftForm((current) => ({
                    ...current,
                    header_media_asset_id: event.target.value,
                  }))
                }
              >
                <option value="">不绑定素材</option>
                {draftHeaderAssets.map((asset) => (
                  <option key={asset.asset_id} value={asset.asset_id}>
                    {asset.name} / {asset.asset_type}
                  </option>
                ))}
              </select>
              <small className="muted">模板头部媒体仅支持图片、视频和文档。</small>
            </label>

            <label>
              头部句柄
              <input
                value={draftForm.header_media_handle}
                onChange={(event) =>
                  setDraftForm((current) => ({
                    ...current,
                    header_media_handle: event.target.value,
                  }))
                }
              />
            </label>

            <label className="meta-form-span-2">
              正文
              <textarea
                rows={4}
                value={draftForm.body_text}
                onChange={(event) =>
                  setDraftForm((current) => ({ ...current, body_text: event.target.value }))
                }
              />
            </label>

            <label className="meta-form-span-2">
              页脚
              <input
                value={draftForm.footer_text}
                onChange={(event) =>
                  setDraftForm((current) => ({ ...current, footer_text: event.target.value }))
                }
              />
            </label>

            <label className="meta-form-span-2">
              示例变量
              <textarea
                rows={3}
                value={draftForm.sample_variables_text}
                onChange={(event) =>
                  setDraftForm((current) => ({
                    ...current,
                    sample_variables_text: event.target.value,
                  }))
                }
              />
            </label>

            <div className="meta-form-actions meta-form-span-2">
              <button className="seed-button" disabled={pendingAction !== null} type="submit">
                {pendingAction === "create-draft" ? "创建中..." : "创建草稿"}
              </button>
            </div>
          </form>
        </article>

        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>模板列表</strong>
              <p className="muted">按账号、WABA、语言和状态浏览模板。</p>
            </div>
          </div>

          <div className="template-list">
            {filteredTemplates.map((template) => (
              <button
                key={template.template_id}
                className="template-list-item"
                onClick={() => setSelectedTemplateId(template.template_id)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  border:
                    selectedTemplateId === template.template_id
                      ? "1px solid var(--accent, #2563eb)"
                      : "1px solid rgba(148, 163, 184, 0.35)",
                  borderRadius: 8,
                  background: "transparent",
                  padding: 12,
                  marginBottom: 10,
                }}
                type="button"
              >
                <div className="template-card-header">
                  <strong>{template.name}</strong>
                  <span className={getStatusBadgeClass(template.status)}>
                    {formatTemplateStatus(template.status)}
                  </span>
                </div>
                <div className="template-detail-grid">
                  <span>{formatAccountLabel(template.account_id, accountMap)}</span>
                  <span>{formatOptionalText(template.waba_id, "未绑定 WABA")}</span>
                  <span>{formatTemplateCategory(template.category)}</span>
                  <span>{formatLanguage(template.language)}</span>
                </div>
                <p className="muted">{getTemplatePreview(template)}</p>
              </button>
            ))}
            {filteredTemplates.length === 0 ? <p className="muted">当前筛选条件下没有模板。</p> : null}
          </div>
        </article>
      </section>

      <section className="dashboard-section">
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>模板详情</strong>
              <p className="muted">编辑草稿、变更状态、同步 Provider 和发送验证都在这里完成。</p>
            </div>
          </div>

          {!selectedTemplate ? (
            <p className="muted">请先从左侧选择一个模板。</p>
          ) : (
            <>
              <div className="template-detail-grid">
                <span>{`模板 ID：${selectedTemplate.template_id}`}</span>
                <span>{`账号：${formatAccountLabel(selectedTemplate.account_id, accountMap)}`}</span>
                <span>{`WABA：${formatOptionalText(selectedTemplate.waba_id, "未绑定")}`}</span>
                <span>{`语言：${formatLanguage(selectedTemplate.language)}`}</span>
                <span>{`分类：${formatTemplateCategory(selectedTemplate.category)}`}</span>
                <span>{`状态：${formatTemplateStatus(selectedTemplate.status)}`}</span>
                <span>{`Meta 模板 ID：${formatOptionalText(selectedTemplate.meta_template_id, "未同步")}`}</span>
                <span>{`最近同步：${formatTimestamp(selectedTemplate.last_synced_at)}`}</span>
              </div>

              <div className="template-preview-block">
                <strong>模板预览</strong>
                {selectedTemplate.header_text ? <p>{selectedTemplate.header_text}</p> : null}
                <p>{selectedTemplate.body_text}</p>
                {selectedTemplate.footer_text ? <p className="muted">{selectedTemplate.footer_text}</p> : null}
              </div>

              <form className="meta-form" onSubmit={(event) => void handleUpdateDraft(event)}>
                <label>
                  模板名称
                  <input
                    disabled={selectedTemplate.status !== "DRAFT"}
                    value={editForm.name}
                    onChange={(event) =>
                      setEditForm((current) => ({ ...current, name: event.target.value }))
                    }
                  />
                </label>

                <label>
                  语言
                  <input
                    disabled={selectedTemplate.status !== "DRAFT"}
                    value={editForm.language}
                    onChange={(event) =>
                      setEditForm((current) => ({ ...current, language: event.target.value }))
                    }
                  />
                </label>

                <label>
                  分类
                  <select
                    disabled={selectedTemplate.status !== "DRAFT"}
                    value={editForm.category}
                    onChange={(event) =>
                      setEditForm((current) => ({
                        ...current,
                        category: event.target.value as TemplateCategory,
                      }))
                    }
                  >
                    {CATEGORY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  WABA
                  <select
                    disabled={selectedTemplate.status !== "DRAFT"}
                    value={editForm.waba_id}
                    onChange={(event) =>
                      setEditForm((current) => ({ ...current, waba_id: event.target.value }))
                    }
                  >
                    <option value="">不绑定 WABA</option>
                    {editWabaOptions.map((wabaId) => (
                      <option key={wabaId} value={wabaId}>
                        {wabaId}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  头部素材
                  <select
                    disabled={selectedTemplate.status !== "DRAFT"}
                    value={editForm.header_media_asset_id}
                    onChange={(event) =>
                      setEditForm((current) => ({
                        ...current,
                        header_media_asset_id: event.target.value,
                      }))
                    }
                  >
                    <option value="">不绑定素材</option>
                    {scopedHeaderAssets.map((asset) => (
                      <option key={asset.asset_id} value={asset.asset_id}>
                        {asset.name} / {asset.asset_type}
                      </option>
                    ))}
                  </select>
                  <small className="muted">模板头部媒体仅支持图片、视频和文档。</small>
                </label>

                <label>
                  头部句柄
                  <input
                    disabled={selectedTemplate.status !== "DRAFT"}
                    value={editForm.header_media_handle}
                    onChange={(event) =>
                      setEditForm((current) => ({
                        ...current,
                        header_media_handle: event.target.value,
                      }))
                    }
                  />
                </label>

                <label className="meta-form-span-2">
                  正文
                  <textarea
                    disabled={selectedTemplate.status !== "DRAFT"}
                    rows={4}
                    value={editForm.body_text}
                    onChange={(event) =>
                      setEditForm((current) => ({ ...current, body_text: event.target.value }))
                    }
                  />
                </label>

                <label className="meta-form-span-2">
                  页脚
                  <input
                    disabled={selectedTemplate.status !== "DRAFT"}
                    value={editForm.footer_text}
                    onChange={(event) =>
                      setEditForm((current) => ({ ...current, footer_text: event.target.value }))
                    }
                  />
                </label>

                <label className="meta-form-span-2">
                  示例变量
                  <textarea
                    disabled={selectedTemplate.status !== "DRAFT"}
                    rows={3}
                    value={editForm.sample_variables_text}
                    onChange={(event) =>
                      setEditForm((current) => ({
                        ...current,
                        sample_variables_text: event.target.value,
                      }))
                    }
                  />
                </label>

                <div className="meta-form-actions meta-form-span-2">
                  <button
                    className="seed-button seed-button-secondary"
                    disabled={pendingAction !== null || selectedTemplate.status !== "DRAFT"}
                    type="submit"
                  >
                    {pendingAction === "update-draft" ? "保存中..." : "保存草稿"}
                  </button>
                </div>
              </form>

              <div className="template-preview-block">
                <strong>模板生命周期</strong>
                <div className="meta-form">
                  <label>
                    状态
                    <select
                      value={statusForm.status}
                      onChange={(event) =>
                        setStatusForm((current) => ({
                          ...current,
                          status: event.target.value as TemplateStatus,
                        }))
                      }
                    >
                      {STATUS_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    Meta 模板 ID
                    <input
                      value={statusForm.meta_template_id}
                      onChange={(event) =>
                        setStatusForm((current) => ({
                          ...current,
                          meta_template_id: event.target.value,
                        }))
                      }
                    />
                  </label>

                  <label className="meta-form-span-2">
                    拒绝原因
                    <input
                      value={statusForm.rejected_reason}
                      onChange={(event) =>
                        setStatusForm((current) => ({
                          ...current,
                          rejected_reason: event.target.value,
                        }))
                      }
                      placeholder="仅在状态为已拒绝时填写"
                    />
                  </label>

                  <div className="meta-form-actions meta-form-span-2">
                    <button
                      className="seed-button seed-button-secondary"
                      disabled={pendingAction !== null}
                      onClick={() => void handleUpdateStatus()}
                      type="button"
                    >
                      {pendingAction === "update-status" ? "保存中..." : "保存状态"}
                    </button>
                    <button
                      className="seed-button seed-button-secondary"
                      disabled={pendingAction !== null}
                      onClick={() => void handleSubmitTemplate()}
                      type="button"
                    >
                      {pendingAction === "submit-template" ? "提交中..." : "提交到 Provider"}
                    </button>
                  </div>
                </div>

                {lastSubmitResult ? (
                  <div className="template-detail-grid" style={{ marginTop: 10 }}>
                    <span>{`发送通道：${lastSubmitResult.provider}`}</span>
                    <span>{`动作：${lastSubmitResult.action}`}</span>
                    <span>{`远端状态：${formatTemplateStatus(lastSubmitResult.remote_status)}`}</span>
                    <span>{`提交时间：${formatTimestamp(lastSubmitResult.template.submitted_at)}`}</span>
                  </div>
                ) : null}
              </div>

              <div className="template-preview-block">
                <strong>模板同步</strong>
                <div className="meta-form">
                  <label>
                    账号
                    <select
                      value={syncForm.account_id}
                      onChange={(event) =>
                        setSyncForm((current) => ({
                          ...current,
                          account_id: event.target.value,
                          waba_id: "",
                        }))
                      }
                    >
                      {accountOptions.map((accountId) => (
                        <option key={accountId} value={accountId}>
                          {formatAccountLabel(accountId, accountMap)}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    WABA
                    <select
                      value={syncForm.waba_id}
                      onChange={(event) =>
                        setSyncForm((current) => ({ ...current, waba_id: event.target.value }))
                      }
                    >
                      <option value="">请选择 WABA</option>
                      {syncWabaOptions.map((wabaId) => (
                        <option key={wabaId} value={wabaId}>
                          {wabaId}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    导入缺失模板
                    <select
                      value={syncForm.import_missing ? "true" : "false"}
                      onChange={(event) =>
                        setSyncForm((current) => ({
                          ...current,
                          import_missing: event.target.value === "true",
                        }))
                      }
                    >
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </label>

                  <div className="meta-form-actions meta-form-span-2">
                    <button
                      className="seed-button seed-button-secondary"
                      disabled={pendingAction !== null || !syncForm.waba_id.trim()}
                      onClick={() => void handleSyncTemplates()}
                      type="button"
                    >
                      {pendingAction === "sync-templates" ? "同步中..." : "从 Provider 同步"}
                    </button>
                  </div>
                </div>

                {lastSyncResult ? (
                  <div className="template-detail-grid" style={{ marginTop: 10 }}>
                    <span>{`发送通道：${lastSyncResult.provider}`}</span>
                    <span>{`账号：${formatAccountLabel(lastSyncResult.account_id, accountMap)}`}</span>
                    <span>{`WABA：${lastSyncResult.waba_id}`}</span>
                    <span>{`新增：${lastSyncResult.created_count}`}</span>
                    <span>{`更新：${lastSyncResult.updated_count}`}</span>
                    <span>{`跳过：${lastSyncResult.skipped_count}`}</span>
                  </div>
                ) : null}
              </div>

              <div className="template-preview-block">
                <strong>发送验证</strong>
                <p className="muted">
                  这里只有已批准模板允许直接发送。这里填写外部会话 ID，结果会同时展示外部会话
                  ID 和内部会话 ID。
                </p>
                <div className="meta-form">
                  <label>
                    账号
                    <input
                      disabled
                      readOnly
                      value={sendForm.account_id}
                    />
                  </label>

                  <label>
                    外部会话 ID
                    <input
                      value={sendForm.conversation_id}
                      onChange={(event) =>
                        setSendForm((current) => ({
                          ...current,
                          conversation_id: event.target.value,
                        }))
                      }
                      placeholder="例如 conv-template-1"
                    />
                  </label>

                  <label>
                    Phone-Number-ID
                    <select
                      value={sendForm.phone_number_id}
                      onChange={(event) =>
                        setSendForm((current) => ({
                          ...current,
                          phone_number_id: event.target.value,
                        }))
                      }
                    >
                      <option value="">自动选择</option>
                      {sendPhoneOptions.map((phoneNumberId) => (
                        <option key={phoneNumberId} value={phoneNumberId}>
                          {phoneNumberId}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    客服 ID
                    <input
                      value={sendForm.agent_id}
                      onChange={(event) =>
                        setSendForm((current) => ({ ...current, agent_id: event.target.value }))
                      }
                      placeholder="人工接管会话可填写"
                    />
                  </label>

                  <label>
                    幂等键
                    <input
                      value={sendForm.idempotency_key}
                      onChange={(event) =>
                        setSendForm((current) => ({
                          ...current,
                          idempotency_key: event.target.value,
                        }))
                      }
                      placeholder="可选，避免重复发送"
                    />
                  </label>

                  <label className="meta-form-span-2">
                    模板变量
                    <textarea
                      rows={3}
                      value={sendForm.variables_text}
                      onChange={(event) =>
                        setSendForm((current) => ({
                          ...current,
                          variables_text: event.target.value,
                        }))
                      }
                    />
                  </label>

                  <div className="meta-form-actions meta-form-span-2">
                    <button
                      className="seed-button"
                      disabled={pendingAction !== null || selectedTemplate.status !== "APPROVED"}
                      onClick={() => void handleSendTemplate()}
                      type="button"
                    >
                      {pendingAction === "send-template" ? "发送中..." : "发送模板"}
                    </button>
                  </div>
                </div>

                {lastSendResult ? (
                  <>
                    <div className="template-detail-grid" style={{ marginTop: 10 }}>
                      <span>{`状态：${formatSendStatus(lastSendResult.status)}`}</span>
                      <span>{`发送通道：${formatOptionalText(lastSendResult.provider)}`}</span>
                      <span>{`外部会话 ID：${formatConversationText(lastSendResult.external_conversation_id)}`}</span>
                      <span>{`内部会话 ID：${formatConversationText(lastSendResult.internal_conversation_id)}`}</span>
                      <span>{`Phone-Number-ID：${formatOptionalText(lastSendResult.phone_number_id, "自动分配")}`}</span>
                      <span>{`消息 ID：${formatOptionalText(lastSendResult.message_id, "待回执")}`}</span>
                      <span>{`发送日志：${lastSendResult.send_log_id}`}</span>
                      <span>{`头部素材：${formatOptionalText(lastSendResult.header_media_asset_name ?? lastSendResult.header_media_asset_id, "未使用")}`}</span>
                    </div>
                    <p className="muted" style={{ marginTop: 10 }}>
                      “打开会话”按外部会话 ID 跳转；内部会话 ID 仅用于排障和追踪。
                    </p>
                    <div className="meta-form-actions" style={{ marginTop: 10 }}>
                      {lastSendExternalConversationId ? (
                        <button
                          className="seed-button seed-button-secondary"
                          onClick={() =>
                            openWorkspacePage({
                              accountId: lastSendResult.account_id,
                              conversationKey: `${lastSendResult.account_id}:${lastSendExternalConversationId}`,
                            })
                          }
                          type="button"
                        >
                          打开会话
                        </button>
                      ) : null}
                      <button
                        className="seed-button seed-button-secondary"
                        onClick={() =>
                          openAuditPage({
                            account_id: lastSendResult.account_id,
                            phone_number_id: lastSendResult.phone_number_id ?? undefined,
                            target_type: "message_template",
                            target_id: lastSendResult.template_id,
                            limit: 50,
                          })
                        }
                        type="button"
                      >
                        查看审计
                      </button>
                    </div>
                  </>
                ) : null}
              </div>
            </>
          )}
        </article>
      </section>

      <section className="dashboard-section">
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>模板统计</strong>
              <p className="muted">按账号、WABA、Phone-Number-ID 和日期维度查看发送效果。</p>
            </div>
            <span className="badge badge-neutral">{`发送 ${statsSummary.send_count}`}</span>
          </div>

          <div className="meta-form">
            <label>
              账号
              <select
                value={statsFilters.account_id}
                onChange={(event) =>
                  setStatsFilters((current) => ({
                    ...current,
                    account_id: event.target.value,
                    waba_id: "ALL",
                    phone_number_id: "ALL",
                  }))
                }
              >
                <option value="ALL">全部账号</option>
                {accountOptions.map((accountId) => (
                  <option key={accountId} value={accountId}>
                    {formatAccountLabel(accountId, accountMap)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              WABA
              <select
                value={statsFilters.waba_id}
                onChange={(event) =>
                  setStatsFilters((current) => ({
                    ...current,
                    waba_id: event.target.value,
                    phone_number_id: "ALL",
                  }))
                }
              >
                <option value="ALL">全部 WABA</option>
                {statsWabaOptions.map((wabaId) => (
                  <option key={wabaId} value={wabaId}>
                    {wabaId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Phone-Number-ID
              <select
                value={statsFilters.phone_number_id}
                onChange={(event) =>
                  setStatsFilters((current) => ({
                    ...current,
                    phone_number_id: event.target.value,
                  }))
                }
              >
                <option value="ALL">全部号码</option>
                {statsPhoneOptions.map((phoneNumberId) => (
                  <option key={phoneNumberId} value={phoneNumberId}>
                    {phoneNumberId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              分类
              <select
                value={statsFilters.category}
                onChange={(event) =>
                  setStatsFilters((current) => ({
                    ...current,
                    category: event.target.value as "ALL" | TemplateCategory,
                  }))
                }
              >
                <option value="ALL">全部分类</option>
                {CATEGORY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              语言
              <input
                value={statsFilters.language}
                onChange={(event) =>
                  setStatsFilters((current) => ({
                    ...current,
                    language: event.target.value,
                  }))
                }
                placeholder="如 zh_CN"
              />
            </label>

            <label>
              开始日期
              <input
                type="date"
                value={statsFilters.date_from}
                onChange={(event) =>
                  setStatsFilters((current) => ({
                    ...current,
                    date_from: event.target.value,
                  }))
                }
              />
            </label>

            <label>
              结束日期
              <input
                type="date"
                value={statsFilters.date_to}
                onChange={(event) =>
                  setStatsFilters((current) => ({
                    ...current,
                    date_to: event.target.value,
                  }))
                }
              />
            </label>

            <div className="meta-form-actions meta-form-span-2">
              <button
                className="seed-button seed-button-secondary"
                disabled={pendingAction !== null}
                onClick={() => void handleRebuildStats()}
                type="button"
              >
                {pendingAction === "rebuild-stats" ? "重建中..." : "重建统计"}
              </button>
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: 12,
              marginTop: 16,
            }}
          >
            <article className="queue-stat-card">
              <strong>发送量</strong>
              <span>{statsSummary.send_count}</span>
              <p className="muted">模板消息触发次数</p>
            </article>
            <article className="queue-stat-card">
              <strong>送达率</strong>
              <span>{formatPercent(statsSummary.delivery_rate)}</span>
              <p className="muted">已送达 / 已发送</p>
            </article>
            <article className="queue-stat-card">
              <strong>已读率</strong>
              <span>{formatPercent(statsSummary.read_rate_by_send)}</span>
              <p className="muted">已读 / 已发送</p>
            </article>
            <article className="queue-stat-card">
              <strong>失败数</strong>
              <span>{statsSummary.failed_count}</span>
              <p className="muted">发送失败或回执失败</p>
            </article>
            <article className="queue-stat-card">
              <strong>预估成本</strong>
              <span>{formatCost(statsSummary.estimated_cost)}</span>
              <p className="muted">
                {`${formatCostStatus(statsSummary.estimated_cost_status)} / ${
                  statsSummary.estimated_cost_note ?? "按接口口径汇总"
                }`}
              </p>
            </article>
          </div>

          <div className="template-log-list" style={{ marginTop: 16 }}>
            {dailyStats.map((row) => (
              <article className="template-log-row" key={`${row.date}-${row.account_id}-${row.template_name}`}>
                <div className="template-card-header">
                  <strong>{row.template_name}</strong>
                  <span className="badge badge-neutral">{row.date}</span>
                </div>
                <div className="template-detail-grid">
                  <span>{`账号：${formatAccountLabel(row.account_id, accountMap)}`}</span>
                  <span>{`WABA：${formatOptionalText(row.waba_id)}`}</span>
                  <span>{`Phone-Number-ID：${formatOptionalText(row.phone_number_id)}`}</span>
                  <span>{`分类：${formatTemplateCategory(row.template_category)}`}</span>
                  <span>{`语言：${formatLanguage(row.template_language)}`}</span>
                  <span>{`发送：${row.send_count}`}</span>
                  <span>{`送达率：${formatPercent(row.delivery_rate)}`}</span>
                  <span>{`已读率：${formatPercent(row.read_rate_by_send)}`}</span>
                  <span>{`失败：${row.failed_count}`}</span>
                  <span>{`成本：${formatCost(row.estimated_cost)}`}</span>
                  <span>{`成本状态：${formatCostStatus(row.estimated_cost_status)}`}</span>
                </div>
                {row.estimated_cost_note ? <p className="muted">{row.estimated_cost_note}</p> : null}
              </article>
            ))}
            {dailyStats.length === 0 ? <p className="muted">当前没有模板统计数据。</p> : null}
          </div>

          {analytics ? (
            <div className="template-preview-block" style={{ marginTop: 16 }}>
              <strong>当前模板分析</strong>
              <div className="template-detail-grid" style={{ marginTop: 10 }}>
                <span>{`模板：${analytics.template_name}`}</span>
                <span>{`送达率：${formatPercent(analytics.summary.delivery_rate)}`}</span>
                <span>{`已读率：${formatPercent(analytics.summary.read_rate_by_send)}`}</span>
                <span>{`失败数：${analytics.summary.failed_count}`}</span>
                <span>{`预估成本：${formatCost(analytics.summary.estimated_cost)}`}</span>
                <span>{`成本状态：${formatCostStatus(analytics.summary.estimated_cost_status)}`}</span>
              </div>
              {analytics.failure_reasons.length > 0 ? (
                <div className="template-log-list" style={{ marginTop: 12 }}>
                  {analytics.failure_reasons.map((item) => (
                    <article className="template-log-row" key={item.error_code}>
                      <div className="template-card-header">
                        <strong>{item.error_code}</strong>
                        <span className="badge badge-warning">{item.failed_count}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted" style={{ marginTop: 10 }}>
                  当前模板没有失败原因聚合数据。
                </p>
              )}
            </div>
          ) : null}
        </article>
      </section>

      <section className="dashboard-section">
        <article className="settings-card">
          <div className="settings-card-header">
            <div>
              <strong>发送日志</strong>
              <p className="muted">
                发送日志按账号、模板和号码维度保留。用户界面只展示外部会话 ID 和内部会话 ID，
                旧 `conversation_id` 仅作兼容回填。
              </p>
            </div>
            <span className="badge badge-neutral">{`日志 ${filteredLogs.length}`}</span>
          </div>

          <div className="meta-form">
            <label>
              日志状态
              <select
                value={logFilters.status}
                onChange={(event) =>
                  setLogFilters((current) => ({
                    ...current,
                    status: event.target.value as "ALL" | TemplateSendStatus,
                  }))
                }
              >
                {SEND_STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Phone-Number-ID
              <select
                value={logFilters.phone_number_id}
                onChange={(event) =>
                  setLogFilters((current) => ({
                    ...current,
                    phone_number_id: event.target.value,
                  }))
                }
              >
                <option value="ALL">全部号码</option>
                {logPhoneOptions.map((phoneNumberId) => (
                  <option key={phoneNumberId} value={phoneNumberId}>
                    {phoneNumberId}
                  </option>
                ))}
              </select>
            </label>

            <label>
              外部会话 ID
              <input
                value={logFilters.conversation_id}
                onChange={(event) =>
                  setLogFilters((current) => ({
                    ...current,
                    conversation_id: event.target.value,
                  }))
                }
                placeholder="按外部会话过滤"
              />
            </label>

            <label>
              开始日期
              <input
                type="date"
                value={logFilters.date_from}
                onChange={(event) =>
                  setLogFilters((current) => ({
                    ...current,
                    date_from: event.target.value,
                  }))
                }
              />
            </label>

            <label>
              结束日期
              <input
                type="date"
                value={logFilters.date_to}
                onChange={(event) =>
                  setLogFilters((current) => ({
                    ...current,
                    date_to: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          <div className="template-log-list">
            {filteredLogs.map((log) => {
              const externalConversationId = log.external_conversation_id ?? log.conversation_id;
              return (
                <article className="template-log-row" key={log.id}>
                  <div className="template-card-header">
                    <strong>{log.template_name ?? log.template_id ?? "未知模板"}</strong>
                    <span className={getSendStatusBadgeClass(log.status)}>
                      {formatSendStatus(log.status)}
                    </span>
                  </div>
                  <div className="template-detail-grid">
                    <span>{`账号：${formatAccountLabel(log.account_id, accountMap)}`}</span>
                    <span>{`WABA：${formatOptionalText(log.waba_id)}`}</span>
                    <span>{`Phone-Number-ID：${formatOptionalText(log.phone_number_id)}`}</span>
                    <span>{`外部会话 ID：${formatConversationText(externalConversationId)}`}</span>
                    <span>{`内部会话 ID：${formatConversationText(log.internal_conversation_id)}`}</span>
                    <span>{`语言：${log.template_language ? formatLanguage(log.template_language) : "未设置"}`}</span>
                    <span>{`分类：${log.template_category ? formatTemplateCategory(log.template_category) : "未设置"}`}</span>
                    <span>{`消息 ID：${formatOptionalText(log.message_id, "待回执")}`}</span>
                    <span>{`成本：${formatCost(log.estimated_cost ?? 0)}`}</span>
                    <span>{`送达时间：${formatTimestamp(log.delivered_at)}`}</span>
                    <span>{`已读时间：${formatTimestamp(log.read_at)}`}</span>
                    <span>{`失败时间：${formatTimestamp(log.failed_at)}`}</span>
                  </div>
                  {log.error_code ? <p className="status-error">{`错误码：${log.error_code}`}</p> : null}
                  <div className="meta-form-actions">
                    {externalConversationId ? (
                      <button
                        className="seed-button seed-button-secondary"
                        onClick={() =>
                          openWorkspacePage({
                            accountId: log.account_id,
                            conversationKey: `${log.account_id}:${externalConversationId}`,
                          })
                        }
                        type="button"
                      >
                        打开会话
                      </button>
                    ) : null}
                    <button
                      className="seed-button seed-button-secondary"
                      onClick={() =>
                        openAuditPage({
                          account_id: log.account_id,
                          phone_number_id: log.phone_number_id ?? undefined,
                          target_type: "message_template",
                          target_id: log.template_id ?? undefined,
                          limit: 50,
                        })
                      }
                      type="button"
                    >
                      查看审计
                    </button>
                  </div>
                </article>
              );
            })}
            {filteredLogs.length === 0 ? <p className="muted">当前没有模板发送日志。</p> : null}
          </div>
        </article>
      </section>
    </Panel>
  );
}
