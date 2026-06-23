import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Button, Card, Col, Form, InputNumber, Modal, Row, Select, Switch, Table, Tag, Tabs, TimePicker, Typography, Input, message, Checkbox, Radio, Space, Pagination, Popconfirm } from "antd";
import { withSorter } from "../utils/withSorter";
import { PlusOutlined } from "@ant-design/icons";
import { usePageData } from "../hooks/usePageData";
import { PageShell } from "../components/PageShell";
import { api, getRuntimeConfigSummary, listRuntimeState, type RuntimeAccountState } from "../services/api";
import {
  listAutoTagRules, createAutoTagRule, updateAutoTagRule, deleteAutoTagRule,
  getEmailConfig, updateEmailConfig, testEmailConfig,
  type AutoTagRule, type EmailConfig,
} from "../services/api";
import { AIProvidersSettingsTab } from "./AIProvidersSettingsTab";
import { TranslationProvidersSettingsTab } from "./TranslationProvidersSettingsTab";
import { showError, showSuccess, DangerButton } from "../components/Feedback";
import {
  listLanguages, createLanguage, updateLanguage,
  deleteLanguage, setDefaultLanguage,
  type H5Language, type CreateLanguageRequest, type UpdateLanguageRequest,
} from "../services/h5MultiTenantApi";
import { listSites, type H5Site } from "../services/h5MultiTenantApi";
import dayjs from "dayjs";
import {
  listSecrets, createSecret, updateSecret, deleteSecret, getSecretValue,
  type SecretEntry,
} from "../services/errorTracker";

const STORAGE_KEY = "fx_business_hours";

interface BusinessHours {
  workDays: number[];
  startTime: string;
  endTime: string;
  timezone: string;
  offHoursBehavior: "ai" | "leave_message" | "no_reply";
  leaveMessage: string;
}

const DEFAULT_HOURS: BusinessHours = {
  workDays: [1, 2, 3, 4, 5],
  startTime: "09:00",
  endTime: "18:00",
  timezone: "Asia/Shanghai",
  offHoursBehavior: "ai",
  leaveMessage: "您好，当前为非工作时间，我们会在下一个工作日尽快回复您。",
};

const WEEK_LABELS = ["日", "一", "二", "三", "四", "五", "六"];

const LANGUAGE_OPTIONS = [
  { value: "zh-CN", label: "中文（简体）", emoji: "🇨🇳" },
  { value: "zh-TW", label: "中文（繁體）", emoji: "🇹🇼" },
  { value: "en-US", label: "English", emoji: "🇺🇸" },
  { value: "hi-IN", label: "हिन्दी", emoji: "🇮🇳" },
  { value: "ur-PK", label: "اردو", emoji: "🇵🇰" },
  { value: "bn-BD", label: "বাংলা", emoji: "🇧🇩" },
  { value: "id-ID", label: "Bahasa Indonesia", emoji: "🇮🇩" },
  { value: "ms-MY", label: "Bahasa Melayu", emoji: "🇲🇾" },
  { value: "fil-PH", label: "Filipino", emoji: "🇵🇭" },
  { value: "vi-VN", label: "Tiếng Việt", emoji: "🇻🇳" },
  { value: "th-TH", label: "ภาษาไทย", emoji: "🇹🇭" },
  { value: "my-MM", label: "မြန်မာ", emoji: "🇲🇲" },
  { value: "km-KH", label: "ភាសាខ្មែរ", emoji: "🇰🇭" },
  { value: "lo-LA", label: "ລາວ", emoji: "🇱🇦" },
  { value: "ja-JP", label: "日本語", emoji: "🇯🇵" },
  { value: "ko-KR", label: "한국어", emoji: "🇰🇷" },
  { value: "ar-SA", label: "العربية", emoji: "🇸🇦" },
  { value: "fa-IR", label: "فارسی", emoji: "🇮🇷" },
  { value: "tr-TR", label: "Türkçe", emoji: "🇹🇷" },
  { value: "he-IL", label: "עברית", emoji: "🇮🇱" },
  { value: "ru-RU", label: "Русский", emoji: "🇷🇺" },
  { value: "uk-UA", label: "Українська", emoji: "🇺🇦" },
  { value: "pl-PL", label: "Polski", emoji: "🇵🇱" },
  { value: "cs-CZ", label: "Čeština", emoji: "🇨🇿" },
  { value: "sk-SK", label: "Slovenčina", emoji: "🇸🇰" },
  { value: "hu-HU", label: "Magyar", emoji: "🇭🇺" },
  { value: "ro-RO", label: "Română", emoji: "🇷🇴" },
  { value: "bg-BG", label: "Български", emoji: "🇧🇬" },
  { value: "el-GR", label: "Ελληνικά", emoji: "🇬🇷" },
  { value: "sq-AL", label: "Shqip", emoji: "🇦🇱" },
  { value: "hr-HR", label: "Hrvatski", emoji: "🇭🇷" },
  { value: "sr-RS", label: "Српски", emoji: "🇷🇸" },
  { value: "es-ES", label: "Español", emoji: "🇪🇸" },
  { value: "pt-PT", label: "Português", emoji: "🇵🇹" },
  { value: "fr-FR", label: "Français", emoji: "🇫🇷" },
  { value: "it-IT", label: "Italiano", emoji: "🇮🇹" },
  { value: "de-DE", label: "Deutsch", emoji: "🇩🇪" },
  { value: "nl-NL", label: "Nederlands", emoji: "🇳🇱" },
  { value: "sv-SE", label: "Svenska", emoji: "🇸🇪" },
  { value: "nb-NO", label: "Norsk", emoji: "🇳🇴" },
  { value: "da-DK", label: "Dansk", emoji: "🇩🇰" },
  { value: "fi-FI", label: "Suomi", emoji: "🇫🇮" },
  { value: "et-EE", label: "Eesti", emoji: "🇪🇪" },
  { value: "lv-LV", label: "Latviešu", emoji: "🇱🇻" },
  { value: "lt-LT", label: "Lietuvių", emoji: "🇱🇹" },
  { value: "am-ET", label: "አማርኛ", emoji: "🇪🇹" },
  { value: "sw-TZ", label: "Kiswahili", emoji: "🇹🇿" },
  { value: "ha-NG", label: "Hausa", emoji: "🇳🇬" },
  { value: "yo-NG", label: "Yorùbá", emoji: "🇳🇬" },
  { value: "zu-ZA", label: "isiZulu", emoji: "🇿🇦" },
  { value: "af-ZA", label: "Afrikaans", emoji: "🇿🇦" },
  { value: "ne-NP", label: "नेपाली", emoji: "🇳🇵" },
  { value: "si-LK", label: "සිංහල", emoji: "🇱🇰" },
  { value: "ka-GE", label: "ქართული", emoji: "🇬🇪" },
  { value: "hy-AM", label: "Հայերեն", emoji: "🇦🇲" },
  { value: "mn-MN", label: "Монгол", emoji: "🇲🇳" },
  { value: "kk-KZ", label: "Қазақ", emoji: "🇰🇿" },
  { value: "uz-UZ", label: "Oʻzbek", emoji: "🇺🇿" },
];

function loadHours(): BusinessHours {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_HOURS, ...JSON.parse(raw) as Partial<BusinessHours> };
  } catch { /* ignore */ }
  return DEFAULT_HOURS;
}

function saveHours(h: BusinessHours): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(h));
}

const TIMEZONES = [
  "Asia/Shanghai",
  "Asia/Hong_Kong",
  "Asia/Tokyo",
  "Asia/Singapore",
  "America/New_York",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Australia/Sydney",
];

export function SettingsPage(): JSX.Element {
  const [businessHours, setBusinessHours] = useState<BusinessHours>(loadHours);
  const [savingHours, setSavingHours] = useState(false);
  const [globalAiLoading, setGlobalAiLoading] = useState(false);
  const [accountAiLoading, setAccountAiLoading] = useState<Record<string, boolean>>({});
  const [accountSearch, setAccountSearch] = useState("");
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([]);
  const [batchAiLoading, setBatchAiLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const fetchData = useCallback(async () => {
    const [config, state] = await Promise.all([
      getRuntimeConfigSummary(),
      listRuntimeState(),
    ]);
    return { config, state };
  }, []);

  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const config = data?.config;
  const state = data?.state;

  const handleSaveHours = async () => {
    const targetAccount = state?.accounts?.[0];
    if (!targetAccount) {
      message.warning("没有可用账号，无法保存工作时间配置");
      return;
    }
    setSavingHours(true);
    try {
      await api.put("/api/runtime/business-hours", null, {
        params: {
          account_id: targetAccount.account_id,
          weekdays: businessHours.workDays,
          start_time: businessHours.startTime,
          end_time: businessHours.endTime,
          timezone: businessHours.timezone,
          off_hours_behavior: businessHours.offHoursBehavior,
          off_hours_message: businessHours.offHoursBehavior === "leave_message" ? businessHours.leaveMessage : null,
        },
      });
      saveHours(businessHours);
      showSuccess("工作时间配置已保存");
    } catch (e) {
      showError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSavingHours(false);
    }
  };

  // ── AI three-level toggle ──
  const handleGlobalAiToggle = async (enabled: boolean) => {
    setGlobalAiLoading(true);
    try {
      await api.post("/api/runtime/ai/global", { enabled });
      showSuccess(`AI 全局${enabled ? "开启" : "关闭"}`);
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setGlobalAiLoading(false);
    }
  };

  const handleBatchAiToggle = async (enabled: boolean) => {
    const ids = selectedAccountIds;
    if (ids.length === 0) return;
    setBatchAiLoading(true);
    try {
      await Promise.all(ids.map((id) =>
        api.post(`/api/runtime/accounts/${id}/ai`, { enabled })
      ));
      showSuccess(`已批量${enabled ? "开启" : "关闭"} ${ids.length} 个账号的 AI`);
      setSelectedAccountIds([]);
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "批量操作失败");
    } finally {
      setBatchAiLoading(false);
    }
  };

  const handleAccountAiToggle = async (accountId: string, enabled: boolean) => {
    setAccountAiLoading(prev => ({ ...prev, [accountId]: true }));
    try {
      await api.post(`/api/runtime/accounts/${accountId}/ai`, { enabled });
      showSuccess(`账号 AI ${enabled ? "开启" : "关闭"}`);
      void reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setAccountAiLoading(prev => ({ ...prev, [accountId]: false }));
    }
  };

  const filteredAccounts = useMemo(() => {
    if (!state?.accounts) return [];
    if (!accountSearch.trim()) return state.accounts;
    const q = accountSearch.trim().toLowerCase();
    return state.accounts.filter((a) =>
      a.display_name.toLowerCase().includes(q)
    );
  }, [state?.accounts, accountSearch]);

  const paginatedAccounts = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredAccounts.slice(start, start + pageSize);
  }, [filteredAccounts, currentPage, pageSize]);

  // ── Language Management ──
  const [languages, setLanguages] = useState<H5Language[]>([]);
  const [langLoading, setLangLoading] = useState(false);
  const [langModalOpen, setLangModalOpen] = useState(false);
  const [editingLang, setEditingLang] = useState<H5Language | null>(null);
  const [langForm] = Form.useForm();
  const [langSaving, setLangSaving] = useState(false);

  const fetchLanguages = useCallback(async () => {
    setLangLoading(true);
    try {
      const data = await listLanguages();
      setLanguages(data);
    } catch { /* ignore */ }
    finally { setLangLoading(false); }
  }, []);

  useEffect(() => { void fetchLanguages(); }, [fetchLanguages]);

  const handleOpenLangModal = useCallback((lang?: H5Language) => {
    setEditingLang(lang ?? null);
    if (lang) {
      langForm.setFieldsValue({
        language_code: lang.language_code,
        display_name: lang.display_name,
        flag_emoji: lang.flag_emoji,
      });
    } else {
      langForm.resetFields();
    }
    setLangModalOpen(true);
  }, [langForm]);

  const handleLangSave = useCallback(async (values: CreateLanguageRequest) => {
    setLangSaving(true);
    try {
      if (editingLang) {
        const updateData: UpdateLanguageRequest = {
          display_name: values.display_name,
          flag_emoji: values.flag_emoji,
        };
        await updateLanguage(editingLang.id, updateData);
        showSuccess("语言已更新");
      } else {
        await createLanguage(values);
        showSuccess("语言已创建");
      }
      setLangModalOpen(false);
      setEditingLang(null);
      void fetchLanguages();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLangSaving(false);
    }
  }, [editingLang, fetchLanguages]);

  const handleDeleteLang = useCallback(async (id: string) => {
    try {
      await deleteLanguage(id);
      showSuccess("语言已删除");
      void fetchLanguages();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    }
  }, [fetchLanguages]);

  const handleSetDefaultLang = useCallback(async (id: string) => {
    try {
      await setDefaultLanguage(id);
      showSuccess("已设为默认语言");
      void fetchLanguages();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    }
  }, [fetchLanguages]);

  // ── Secret Management ──
  const [secrets, setSecrets] = useState<SecretEntry[]>([]);
  const [secretsLoading, setSecretsLoading] = useState(false);
  const [secretModalOpen, setSecretModalOpen] = useState(false);
  const [secretViewModalOpen, setSecretViewModalOpen] = useState(false);
  const [secretViewValue, setSecretViewValue] = useState("");
  const [secretViewName, setSecretViewName] = useState("");
  const [editingSecret, setEditingSecret] = useState<SecretEntry | null>(null);
  const [secretForm] = Form.useForm();
  const [secretSaving, setSecretSaving] = useState(false);

  const fetchSecrets = useCallback(async () => {
    setSecretsLoading(true);
    try {
      const data = await listSecrets();
      setSecrets(data);
    } catch { /* ignore */ }
    finally { setSecretsLoading(false); }
  }, []);

  useEffect(() => { void fetchSecrets(); }, [fetchSecrets]);

  const handleOpenSecretModal = useCallback((secret?: SecretEntry) => {
    setEditingSecret(secret ?? null);
    if (secret) {
      secretForm.setFieldsValue({
        name: secret.name,
        description: secret.description,
        value: "",
      });
    } else {
      secretForm.resetFields();
    }
    setSecretModalOpen(true);
  }, [secretForm]);

  const handleSecretSave = useCallback(async (values: { name: string; value?: string; description?: string }) => {
    setSecretSaving(true);
    try {
      if (editingSecret) {
        await updateSecret(editingSecret.id, {
          value: values.value || undefined,
          description: values.description,
        });
        showSuccess("密钥已更新");
      } else {
        await createSecret({
          name: values.name,
          value: values.value ?? "",
          description: values.description,
        });
        showSuccess("密钥已创建");
      }
      setSecretModalOpen(false);
      setEditingSecret(null);
      void fetchSecrets();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setSecretSaving(false);
    }
  }, [editingSecret, fetchSecrets]);

  // ── Auto-Tag Rules ──
  const [autoTagRules, setAutoTagRules] = useState<AutoTagRule[]>([]);
  const [autoTagsLoading, setAutoTagsLoading] = useState(false);
  const [autoTagModalOpen, setAutoTagModalOpen] = useState(false);
  const [editingAutoTag, setEditingAutoTag] = useState<AutoTagRule | null>(null);
  const [autoTagForm] = Form.useForm();
  const [autoTagSaving, setAutoTagSaving] = useState(false);

  const fetchAutoTagRules = useCallback(async () => {
    setAutoTagsLoading(true);
    try {
      const rules = await listAutoTagRules();
      setAutoTagRules(rules);
    } catch { /* ignore */ }
    finally { setAutoTagsLoading(false); }
  }, []);

  useEffect(() => { void fetchAutoTagRules(); }, [fetchAutoTagRules]);

  const handleOpenAutoTagModal = useCallback((rule?: AutoTagRule) => {
    setEditingAutoTag(rule ?? null);
    if (rule) {
      autoTagForm.setFieldsValue({
        name: rule.name,
        condition_type: rule.condition_type,
        condition_operator: rule.condition_operator,
        condition_value: rule.condition_value,
        tag_name: rule.tag_name,
        is_enabled: rule.is_enabled,
      });
    } else {
      autoTagForm.resetFields();
      autoTagForm.setFieldsValue({ is_enabled: true, condition_operator: "gte", condition_value: 0 });
    }
    setAutoTagModalOpen(true);
  }, [autoTagForm]);

  const handleAutoTagSave = useCallback(async (values: {
    name: string; condition_type: string; condition_operator: string;
    condition_value: number; tag_name: string; is_enabled: boolean;
  }) => {
    setAutoTagSaving(true);
    try {
      if (editingAutoTag) {
        await updateAutoTagRule(editingAutoTag.id, values);
        showSuccess("规则已更新");
      } else {
        await createAutoTagRule(values);
        showSuccess("规则已创建");
      }
      setAutoTagModalOpen(false);
      void fetchAutoTagRules();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setAutoTagSaving(false);
    }
  }, [editingAutoTag, fetchAutoTagRules]);

  const handleDeleteAutoTag = useCallback(async (id: string) => {
    try {
      await deleteAutoTagRule(id);
      showSuccess("规则已删除");
      void fetchAutoTagRules();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    }
  }, [fetchAutoTagRules]);

  // ── Email Config ──
  const [emailConfig, setEmailConfig] = useState<EmailConfig | null>(null);
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailSaving, setEmailSaving] = useState(false);
  const [emailForm] = Form.useForm();
  const [testEmailTo, setTestEmailTo] = useState("");
  const [testEmailModalOpen, setTestEmailModalOpen] = useState(false);
  const [testEmailLoading, setTestEmailLoading] = useState(false);

  const fetchEmailConfig = useCallback(async () => {
    setEmailLoading(true);
    try {
      const config = await getEmailConfig();
      setEmailConfig(config);
      if (config) {
        emailForm.setFieldsValue(config);
      }
    } catch { /* ignore */ }
    finally { setEmailLoading(false); }
  }, [emailForm]);

  useEffect(() => { void fetchEmailConfig(); }, [fetchEmailConfig]);

  const handleEmailSave = useCallback(async (values: EmailConfig) => {
    setEmailSaving(true);
    try {
      await updateEmailConfig(values);
      showSuccess("邮件配置已保存");
      setEmailConfig(values);
    } catch (e) {
      showError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setEmailSaving(false);
    }
  }, []);

  const handleTestEmail = useCallback(async () => {
    if (!testEmailTo) { showError("请输入测试邮箱地址"); return; }
    setTestEmailLoading(true);
    try {
      await testEmailConfig(testEmailTo);
      showSuccess("测试邮件已发送");
      setTestEmailModalOpen(false);
      setTestEmailTo("");
    } catch (e) {
      showError(e instanceof Error ? e.message : "发送失败");
    } finally {
      setTestEmailLoading(false);
    }
  }, [testEmailTo]);

  const handleDeleteSecret = useCallback(async (id: string) => {
    try {
      await deleteSecret(id);
      showSuccess("密钥已删除");
      void fetchSecrets();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    }
  }, [fetchSecrets]);

  const handleViewSecret = useCallback(async (secret: SecretEntry) => {
    try {
      const { value } = await getSecretValue(secret.id);
      setSecretViewName(secret.name);
      setSecretViewValue(value);
      setSecretViewModalOpen(true);
    } catch (e) {
      showError(e instanceof Error ? e.message : "解密失败");
    }
  }, []);

  const secretColumns = useMemo(() => [
    { title: "名称", dataIndex: "name", key: "name", width: 200 },
    { title: "描述", dataIndex: "description", key: "description", width: 200, render: (v: string | null) => v || "-" },
    { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 120, render: (v: string) => new Date(v).toLocaleDateString("zh-CN") },
    {
      title: "操作", key: "actions", width: 220,
      render: (_: unknown, record: SecretEntry) => (
        <Space>
          <Button type="link" size="small" onClick={() => void handleViewSecret(record)}>查看解密</Button>
          <Button type="link" size="small" onClick={() => handleOpenSecretModal(record)}>编辑</Button>
          <DangerButton
            label="删除"
            confirmTitle={`确认删除密钥 ${record.name}?`}
            onConfirm={() => handleDeleteSecret(record.id)}
            type="link"
            danger
          />
        </Space>
      ),
    },
  ], [handleViewSecret, handleOpenSecretModal, handleDeleteSecret]);

  const langColumns = useMemo(() => [
    { title: "语言代码", dataIndex: "language_code", key: "language_code", width: 100 },
    {
      title: "显示名称", dataIndex: "display_name", key: "display_name", width: 180,
      render: (_: string, record: H5Language) => (
        <Space>
          {record.flag_emoji && <span>{record.flag_emoji}</span>}
          <span>{record.display_name}</span>
          {record.is_default && <Tag color="blue">默认</Tag>}
        </Space>
      ),
    },
    {
      title: "状态", dataIndex: "is_enabled", key: "is_enabled", width: 80,
      render: (v: boolean) => <Tag color={v ? "success" : "default"}>{v ? "启用" : "禁用"}</Tag>,
    },
    {
      title: "操作", key: "actions", width: 200,
      render: (_: unknown, record: H5Language) => (
        <Space>
          <Button type="link" size="small" onClick={() => handleOpenLangModal(record)}>编辑</Button>
          {!record.is_default && (
            <Button type="link" size="small" onClick={() => void handleSetDefaultLang(record.id)}>设为默认</Button>
          )}
          {!record.is_default && (
            <DangerButton
              label="删除"
              confirmTitle={`确认删除语言 ${record.display_name}?`}
              onConfirm={() => handleDeleteLang(record.id)}
              type="link"
              danger
            />
          )}
        </Space>
      ),
    },
  ], [handleOpenLangModal, handleSetDefaultLang, handleDeleteLang]);

  const toggleDay = (d: number) => {
    setBusinessHours((prev) => ({
      ...prev,
      workDays: prev.workDays.includes(d)
        ? prev.workDays.filter((x) => x !== d)
        : [...prev.workDays, d].sort(),
    }));
  };

  if (!config) {
    return (
      <PageShell title="系统设置" subtitle="AI 配置、运行时开关和系统参数" actions={null}>
        {loading && <div style={{ textAlign: "center", padding: 48, color: "#999" }}>加载中...</div>}
        {error && <Typography.Text type="danger">{error}</Typography.Text>}
      </PageShell>
    );
  }

  const tabItems = [
    {
      key: "ai",
      label: "AI 配置",
      children: <AIProvidersSettingsTab />,
    },
    {
      key: "runtime",
      label: "运行时开关",
      children: (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card size="small" title="三级 AI 控制" extra={
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Switch checked={state?.global_ai_enabled ?? false} loading={globalAiLoading} onChange={handleGlobalAiToggle} />
              <Typography.Text strong style={{ fontSize: 12 }}>全局 AI</Typography.Text>
              <Tag color={state?.global_ai_enabled ? "processing" : "default"}>{state?.global_ai_enabled ? "开启" : "关闭"}</Tag>
            </div>
          }>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
              <Typography.Title level={5} style={{ margin: 0, fontSize: 14, flexShrink: 0 }}>账号级 AI 状态</Typography.Title>
              <Input.Search
                size="small"
                placeholder="搜索账号名称…"
                allowClear
                onSearch={(v) => { setAccountSearch(v); setCurrentPage(1); }}
                onChange={(e) => { setAccountSearch(e.target.value); setCurrentPage(1); }}
                style={{ maxWidth: 240, flexShrink: 0 }}
              />
            </div>
            <Table
              size="small"
              rowKey="account_id"
              dataSource={paginatedAccounts}
              columns={withSorter([
                {
                  title: "账号", dataIndex: "display_name", key: "display_name",
                  render: (_: unknown, r: RuntimeAccountState) => (
                    <Typography.Text style={{ fontSize: 12 }}>{r.display_name}</Typography.Text>
                  ),
                },
                {
                  title: "AI 状态", key: "ai_enabled", width: 160,
                  render: (_: unknown, r: RuntimeAccountState) => (
                    <Switch
                      size="small"
                      checked={r.ai_enabled}
                      loading={accountAiLoading[r.account_id] ?? false}
                      onChange={(checked) => handleAccountAiToggle(r.account_id, checked)}
                    />
                  ),
                },
                {
                  title: "标识", key: "tag", width: 80,
                  render: (_: unknown, r: RuntimeAccountState) => (
                    <Tag color={r.ai_enabled ? "processing" : "default"} style={{ fontSize: 10 }}>
                      {r.ai_enabled ? "开启" : "关闭"}
                    </Tag>
                  ),
                },
              ])}
              pagination={false}
              scroll={{ y: 360 }}
              rowSelection={{
                selectedRowKeys: selectedAccountIds,
                onChange: (keys) => { setSelectedAccountIds(keys as string[]); setCurrentPage(1); },
              }}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 8, minHeight: 32 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {selectedAccountIds.length > 0 && (
                  <span style={{ fontSize: 12, color: "#666", flexShrink: 0 }}>
                    已选 {selectedAccountIds.length} 个
                  </span>
                )}
                <Button
                  size="small"
                  type="primary"
                  disabled={selectedAccountIds.length === 0}
                  loading={batchAiLoading}
                  onClick={() => handleBatchAiToggle(true)}
                  style={{ fontSize: 12 }}
                >
                  批量开启 AI
                </Button>
                <Button
                  size="small"
                  disabled={selectedAccountIds.length === 0}
                  loading={batchAiLoading}
                  onClick={() => handleBatchAiToggle(false)}
                  style={{ fontSize: 12 }}
                >
                  批量关闭 AI
                </Button>
              </div>
              <div style={{ flex: 1 }} />
              <Pagination
                size="small"
                current={currentPage}
                pageSize={pageSize}
                total={filteredAccounts.length}
                onChange={(p, ps) => { setCurrentPage(p); setPageSize(ps); }}
                showSizeChanger
                pageSizeOptions={["20", "50", "100"]}
                showTotal={(total) => `共 ${total} 个账号`}
              />
            </div>
          </Card>
          <Card size="small" title="⏰ 工作时间配置">
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <div>
                <Typography.Text style={{ fontSize: 13, fontWeight: 500, display: "block", marginBottom: 6 }}>工作日</Typography.Text>
                <Space>
                  {WEEK_LABELS.map((label, i) => (
                    <Checkbox key={i} checked={businessHours.workDays.includes(i)} onChange={() => toggleDay(i)}>
                      {label}
                    </Checkbox>
                  ))}
                </Space>
              </div>
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <div>
                  <Typography.Text style={{ fontSize: 12, display: "block", marginBottom: 4 }}>开始时间</Typography.Text>
                  <TimePicker
                    size="small"
                    value={dayjs(businessHours.startTime, "HH:mm")}
                    format="HH:mm"
                    onChange={(t) => t && setBusinessHours((prev) => ({ ...prev, startTime: t.format("HH:mm") }))}
                  />
                </div>
                <div>
                  <Typography.Text style={{ fontSize: 12, display: "block", marginBottom: 4 }}>结束时间</Typography.Text>
                  <TimePicker
                    size="small"
                    value={dayjs(businessHours.endTime, "HH:mm")}
                    format="HH:mm"
                    onChange={(t) => t && setBusinessHours((prev) => ({ ...prev, endTime: t.format("HH:mm") }))}
                  />
                </div>
                <div>
                  <Typography.Text style={{ fontSize: 12, display: "block", marginBottom: 4 }}>时区</Typography.Text>
                  <Select
                    size="small"
                    value={businessHours.timezone}
                    onChange={(v) => setBusinessHours((prev) => ({ ...prev, timezone: v }))}
                    options={TIMEZONES.map((tz) => ({ label: tz, value: tz }))}
                    style={{ width: 160 }}
                  />
                </div>
              </div>
              <div>
                <Typography.Text style={{ fontSize: 13, fontWeight: 500, display: "block", marginBottom: 6 }}>非工作时间行为</Typography.Text>
                <Radio.Group
                  value={businessHours.offHoursBehavior}
                  onChange={(e) => setBusinessHours((prev) => ({ ...prev, offHoursBehavior: e.target.value }))}
                >
                  <Radio value="ai">AI 托管（AI 自动回复）</Radio>
                  <Radio value="leave_message">留言模式（提示客户工作时间再来）</Radio>
                  <Radio value="no_reply">不回复</Radio>
                </Radio.Group>
              </div>
              {businessHours.offHoursBehavior === "leave_message" && (
                <div>
                  <Typography.Text style={{ fontSize: 12, display: "block", marginBottom: 4 }}>留言提示语</Typography.Text>
                  <Input.TextArea
                    rows={2}
                    value={businessHours.leaveMessage}
                    onChange={(e) => setBusinessHours((prev) => ({ ...prev, leaveMessage: e.target.value }))}
                  />
                </div>
              )}
              <Button type="primary" size="small" onClick={handleSaveHours} loading={savingHours}>
                保存
              </Button>
            </Space>
          </Card>
        </Space>
      ),
    },
    {
      key: "languages",
      label: "语言管理",
      children: (
        <div>
          <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
            <Col>
              <Typography.Text>管理系统支持的语言，新增后 H5 站点可选择使用。</Typography.Text>
            </Col>
            <Col>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenLangModal()}>
                新增语言
              </Button>
            </Col>
          </Row>
          <Table
            dataSource={languages}
            columns={withSorter(langColumns)}
            rowKey="id"
            size="small"
            loading={langLoading}
            pagination={false}
          />
          <Modal
            title={editingLang ? "编辑语言" : "新增语言"}
            open={langModalOpen}
            onCancel={() => { setLangModalOpen(false); setEditingLang(null); }}
            onOk={() => langForm.submit()}
            confirmLoading={langSaving}
            okText="保存"
            cancelText="取消"
          >
            <Form form={langForm} layout="vertical" onFinish={handleLangSave}>
              <Form.Item label="语言" name="language_code" rules={[{ required: true, message: "请选择语言" }]}>
                <Select
                  placeholder="选择语言"
                  disabled={!!editingLang}
                  showSearch
                  optionFilterProp="label"
                  options={LANGUAGE_OPTIONS.map(l => ({
                    value: l.value,
                    label: `${l.emoji} ${l.label}（${l.value}）`,
                  }))}
                  onChange={(value) => {
                    const lang = LANGUAGE_OPTIONS.find(l => l.value === value);
                    if (lang) {
                      langForm.setFieldsValue({
                        display_name: lang.label,
                        flag_emoji: lang.emoji,
                      });
                    }
                  }}
                />
              </Form.Item>
              <Form.Item label="显示名称" name="display_name" rules={[{ required: true, message: "请输入显示名称" }]}>
                <Input placeholder="自动填充，可手动修改" />
              </Form.Item>
            </Form>
          </Modal>
        </div>
      ),
    },
    {
      key: "translation",
      label: "翻译配置",
      children: <TranslationProvidersSettingsTab />,
    },
    {
      key: "secrets",
      label: "密钥管理",
      children: (
        <div>
          <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
            <Col>
              <Typography.Text>管理系统密钥，密钥值加密存储，仅后台可查看解密。</Typography.Text>
            </Col>
            <Col>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenSecretModal()}>
                新增密钥
              </Button>
            </Col>
          </Row>
          <Table
            dataSource={secrets}
            columns={withSorter(secretColumns)}
            rowKey="id"
            size="small"
            loading={secretsLoading}
            pagination={false}
          />

          {/* 新增/编辑密钥 Modal */}
          <Modal
            title={editingSecret ? "编辑密钥" : "新增密钥"}
            open={secretModalOpen}
            onCancel={() => { setSecretModalOpen(false); setEditingSecret(null); }}
            onOk={() => secretForm.submit()}
            confirmLoading={secretSaving}
            okText="保存"
            cancelText="取消"
          >
            <Form form={secretForm} layout="vertical" onFinish={handleSecretSave}>
              <Form.Item label="密钥名称" name="name" rules={[{ required: true, message: "请输入密钥名称" }]}>
                <Input placeholder="例如: OPENAI_API_KEY" disabled={!!editingSecret} />
              </Form.Item>
              <Form.Item label="密钥值" name="value" rules={!editingSecret ? [{ required: true, message: "请输入密钥值" }] : []}>
                <Input.Password placeholder="输入密钥值" />
              </Form.Item>
              <Form.Item label="描述" name="description">
                <Input.TextArea rows={2} placeholder="可选描述" />
              </Form.Item>
            </Form>
          </Modal>

          {/* 查看解密值 Modal */}
          <Modal
            title={`密钥值 - ${secretViewName}`}
            open={secretViewModalOpen}
            onCancel={() => setSecretViewModalOpen(false)}
            footer={<Button onClick={() => setSecretViewModalOpen(false)}>关闭</Button>}
          >
            <Input.Password
              value={secretViewValue}
              readOnly
              style={{ width: "100%" }}
            />
            <Typography.Text style={{ fontSize: 12, color: "#999", display: "block", marginTop: 8 }}>
              该值已解密显示，请妥善保管。
            </Typography.Text>
          </Modal>
        </div>
      ),
    },
    {
      key: "autoTag",
      label: "自动打标规则",
      children: (
        <div>
          <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
            <Col>
              <Typography.Text>管理客户自动打标规则，根据用户行为自动添加标签。</Typography.Text>
            </Col>
            <Col>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenAutoTagModal()}>
                新增规则
              </Button>
            </Col>
          </Row>
          <Table
            dataSource={autoTagRules}
            columns={withSorter([
              { title: "规则名称", dataIndex: "name", key: "name" },
              {
                title: "条件", key: "condition",
                render: (_: unknown, r: AutoTagRule) => (
                  <Typography.Text style={{ fontSize: 12 }}>
                    {r.condition_type} {r.condition_operator} {r.condition_value}
                  </Typography.Text>
                ),
              },
              { title: "标签", dataIndex: "tag_name", key: "tag_name", render: (v: string) => <Tag>{v}</Tag> },
              {
                title: "状态", dataIndex: "is_enabled", key: "is_enabled", width: 80,
                render: (v: boolean) => <Tag color={v ? "success" : "default"}>{v ? "启用" : "禁用"}</Tag>,
              },
              {
                title: "操作", key: "actions", width: 160,
                render: (_: unknown, r: AutoTagRule) => (
                  <Space>
                    <Button type="link" size="small" onClick={() => handleOpenAutoTagModal(r)}>编辑</Button>
                    <DangerButton
                      label="删除"
                      confirmTitle={`确认删除规则「${r.name}」?`}
                      onConfirm={() => handleDeleteAutoTag(r.id)}
                      type="link"
                      danger
                    />
                  </Space>
                ),
              },
            ])}
            rowKey="id"
            size="small"
            loading={autoTagsLoading}
            pagination={false}
          />
          <Modal
            title={editingAutoTag ? "编辑规则" : "新增规则"}
            open={autoTagModalOpen}
            onCancel={() => { setAutoTagModalOpen(false); setEditingAutoTag(null); }}
            onOk={() => autoTagForm.submit()}
            confirmLoading={autoTagSaving}
            okText="保存"
            cancelText="取消"
          >
            <Form form={autoTagForm} layout="vertical" onFinish={handleAutoTagSave}>
              <Form.Item label="规则名称" name="name" rules={[{ required: true, message: "请输入规则名称" }]}>
                <Input placeholder="例如: 高活跃客户" />
              </Form.Item>
              <Space style={{ width: "100%" }} size={12}>
                <Form.Item label="条件类型" name="condition_type" rules={[{ required: true }]}>
                  <Select style={{ width: 160 }} options={[
                    { label: "累计充值", value: "recharge_total" },
                    { label: "签到次数", value: "sign_in_count" },
                    { label: "会话次数", value: "conversation_count" },
                  ]} />
                </Form.Item>
                <Form.Item label="运算符" name="condition_operator" rules={[{ required: true }]}>
                  <Select style={{ width: 100 }} options={[
                    { label: ">=", value: "gte" },
                    { label: ">", value: "gt" },
                    { label: "=", value: "eq" },
                    { label: "<=", value: "lte" },
                    { label: "<", value: "lt" },
                  ]} />
                </Form.Item>
                <Form.Item label="值" name="condition_value" rules={[{ required: true, message: "请输入" }]}>
                  <InputNumber min={0} style={{ width: 120 }} />
                </Form.Item>
              </Space>
              <Form.Item label="标签名称" name="tag_name" rules={[{ required: true, message: "请输入标签名称" }]}>
                <Input placeholder="例如: VIP" />
              </Form.Item>
              <Form.Item label="启用" name="is_enabled" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Form>
          </Modal>
        </div>
      ),
    },
    {
      key: "email",
      label: "邮件配置",
      children: (
        <div>
          <Typography.Text style={{ display: "block", marginBottom: 16 }}>
            配置 SMTP 邮件服务，用于发送系统通知和告警邮件。
          </Typography.Text>
          <Card size="small" loading={emailLoading}>
            <Form
              form={emailForm}
              layout="vertical"
              onFinish={handleEmailSave}
              style={{ maxWidth: 480 }}
            >
              <Form.Item label="SMTP 服务器" name="smtp_host" rules={[{ required: true, message: "请输入 SMTP 服务器" }]}>
                <Input placeholder="smtp.qq.com" />
              </Form.Item>
              <Space style={{ width: "100%" }} size={12}>
                <Form.Item label="端口" name="smtp_port" rules={[{ required: true, message: "请输入端口" }]}>
                  <InputNumber min={1} max={65535} style={{ width: 120 }} placeholder="465" />
                </Form.Item>
                <Form.Item label="SSL" name="smtp_ssl" valuePropName="checked" initialValue={true}>
                  <Switch />
                </Form.Item>
              </Space>
              <Form.Item label="用户名" name="smtp_user" rules={[{ required: true, message: "请输入用户名" }]}>
                <Input placeholder="your@qq.com" />
              </Form.Item>
              <Form.Item label="密码/授权码" name="smtp_password" rules={[{ required: true, message: "请输入密码" }]}>
                <Input.Password placeholder="输入 SMTP 密码或授权码" />
              </Form.Item>
              <Space style={{ width: "100%" }} size={12}>
                <Form.Item label="发件人名称" name="from_name">
                  <Input placeholder="例如: 客服中心" style={{ width: 220 }} />
                </Form.Item>
                <Form.Item label="发件人邮箱" name="from_email" rules={[{ required: true, message: "请输入发件人邮箱" }]}>
                  <Input placeholder="noreply@example.com" style={{ width: 220 }} />
                </Form.Item>
              </Space>
              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" loading={emailSaving}>保存配置</Button>
                  <Button onClick={() => setTestEmailModalOpen(true)}>发送测试邮件</Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>

          <Modal
            title="发送测试邮件"
            open={testEmailModalOpen}
            onCancel={() => { setTestEmailModalOpen(false); setTestEmailTo(""); }}
            onOk={() => void handleTestEmail()}
            confirmLoading={testEmailLoading}
            okText="发送"
            cancelText="取消"
          >
            <Typography.Text style={{ display: "block", marginBottom: 12 }}>
              输入测试邮箱地址，系统将发送一封测试邮件。
            </Typography.Text>
            <Input
              placeholder="test@example.com"
              value={testEmailTo}
              onChange={(e) => setTestEmailTo(e.target.value)}
            />
          </Modal>
        </div>
      ),
    },
    {
      key: "system",
      label: "系统信息",
      children: (
        <Row gutter={[16, 16]}>
          <Col span={12}>
            <Card size="small" title="运行环境">
              <Typography.Text style={{ fontSize: 13, display: "block", marginBottom: 4 }}>环境: <Tag>{config.app_env}</Tag></Typography.Text>
              <Typography.Text style={{ fontSize: 13, display: "block", marginBottom: 4 }}>测试模式: <Tag color={config.test_mode ? "warning" : "default"}>{config.test_mode ? "开启" : "关闭"}</Tag></Typography.Text>
              <Typography.Text style={{ fontSize: 13, display: "block", marginBottom: 4 }}>消息提供商: <Tag>{config.messaging_provider}</Tag></Typography.Text>
              <Typography.Text style={{ fontSize: 13, display: "block" }}>队列后端: <Tag>{config.queue_backend}</Tag></Typography.Text>
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="账号概览">
              <Typography.Text style={{ fontSize: 13, display: "block", marginBottom: 4 }}>账号数: <Typography.Text strong>{state?.accounts.length ?? 0}</Typography.Text></Typography.Text>
              <Typography.Text style={{ fontSize: 13, display: "block" }}>AI 全局: <Tag color={state?.global_ai_enabled ? "processing" : "default"}>{state?.global_ai_enabled ? "开启" : "关闭"}</Tag></Typography.Text>
            </Card>
          </Col>
          <Col span={24} style={{ marginTop: 16 }}>
            <Card size="small" title="翻译配置">
              <Row gutter={16}>
                <Col span={6}><Typography.Text style={{ fontSize: 13, display: "block", marginBottom: 4 }}>翻译提供商: <Tag>{config.translation_provider}</Tag></Typography.Text></Col>
                <Col span={6}><Typography.Text style={{ fontSize: 13, display: "block", marginBottom: 4 }}>实时翻译: <Tag color={config.live_translation_enabled ? "success" : "default"}>{config.live_translation_enabled ? "已启用" : "已禁用"}</Tag></Typography.Text></Col>
                <Col span={6}><Typography.Text style={{ fontSize: 13, display: "block", marginBottom: 4 }}>客服语言: <Tag>{config.console_language}</Tag></Typography.Text></Col>
                <Col span={6}><Typography.Text style={{ fontSize: 13, display: "block" }}>自动翻译(人工接管): <Tag color={config.auto_translate_on_human_handover ? "success" : "default"}>{config.auto_translate_on_human_handover ? "已启用" : "已禁用"}</Tag></Typography.Text></Col>
              </Row>
            </Card>
          </Col>
        </Row>
      ),
    },
  ];

  return (
    <PageShell title="系统设置" subtitle="AI 配置、运行时开关和系统参数" actions={null}>
      <div style={{ overflowY: "auto", height: "100%" }}>
        <Tabs items={tabItems} />
      </div>
    </PageShell>
  );
}
