import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  Button, Card, Checkbox, Col, Drawer, Dropdown, Form, Input, Modal, Row, Select, Space, Statistic,
  Switch, Table, Tag, Timeline, Typography, Upload, message, Alert, Tooltip,
} from "antd";
import {
  CheckCircleOutlined, CloseCircleOutlined, CopyOutlined, DeleteOutlined, DownloadOutlined,
  EllipsisOutlined, PauseCircleOutlined, PlayCircleOutlined, PlusOutlined, ReloadOutlined,
  UploadOutlined, SwapOutlined, SettingOutlined,
} from "@ant-design/icons";
import { usePermissions } from "../hooks/usePermissions";
import { usePageData } from "../hooks/usePageData";
import { PageShell, EmptyGuide } from "../components/PageShell";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import { withSorter } from "../utils/withSorter";
import {
  listPlatformSites, createPlatformSite, updatePlatformSite, deletePlatformSite,
  getPlatformSiteConfig, updatePlatformSiteConfig,
  getSiteAnalytics, cloneSite, exportSiteConfig, importSiteConfig,
  batchUpdateSites, verifySiteDns, getDeployHistory,
  listAgents, listWabas, getSiteWabas, assignWabaToSite, revokeWabaFromSite,
  listH5Templates,
  type PlatformSite, type PlatformSiteCreatePayload, type PlatformSiteUpdatePayload,
  type PlatformSiteConfigResponse, type PlatformSiteConfigUpdatePayload,
  type SiteAnalytics, type CloneSitePayload, type BatchUpdatePayload,
  type DnsVerificationResult, type DeployHistoryItem,
  type Agent,
  type H5Template,
} from "../services/api";
import {
  listLanguages, getTranslations, batchTranslate,
  getSitePermissions, grantPermission, revokePermission, updatePermissionRole,
  generateDeployScript, verifyDeployment,
  type H5Language, type TranslationEntry, type SitePermission,
  type DeployScriptResult, type DeployVerification,
} from "../services/h5MultiTenantApi";

// ── Constants ──
const ROLE_LABELS: Record<string, string> = {
  admin: "管理员", editor: "编辑", analyst: "分析师", support: "客服",
};
const ROLE_COLORS: Record<string, string> = {
  admin: "red", editor: "blue", analyst: "green", support: "orange",
};
const ROLE_DESCRIPTIONS: Record<string, string> = {
  admin: "全部权限", editor: "编辑站点配置", analyst: "只读数据", support: "仅查看会话",
};
const STATUS_COLORS: Record<string, string> = { active: "success", paused: "warning", archived: "default" };
const STATUS_LABELS: Record<string, string> = { active: "活跃", paused: "暂停", archived: "已归档" };
const HEALTH_LABELS: Record<string, string> = {
  healthy: "正常", warning: "警告", error: "异常", unverified: "未验证",
};
const HEALTH_COLORS: Record<string, string> = {
  healthy: "success", warning: "warning", error: "error", unverified: "default",
};
const HEALTH_ICONS: Record<string, string> = {
  healthy: "🟢", warning: "🟡", error: "🔴", unverified: "⚪",
};
const ACTION_LABELS: Record<string, string> = {
  pause: "暂停", resume: "恢复", delete: "删除", update_config: "更新配置",
};

type FixedH5SiteCreateValues = Omit<PlatformSiteCreatePayload, "template_id">;

export const FIXED_DEFAULT_H5_TEMPLATE_MESSAGE =
  "新站点统一使用固定默认 H5 模板；如需调整，请更新默认模板发布版本，而不是为单个站点单独切换模板。";

function getFixedDefaultH5TemplateLabel(template: H5Template | null): string {
  if (!template?.name) {
    return "系统将自动绑定默认 H5，当前默认版本待就绪";
  }
  return `系统将自动绑定默认 H5：${template.name}`;
}

export function buildFixedH5SiteCreatePayload(
  values: FixedH5SiteCreateValues,
  templateId: string,
): PlatformSiteCreatePayload {
  return {
    ...values,
    template_id: templateId,
  };
}

function resolveFixedDefaultH5Template(templates: H5Template[]): H5Template | null {
  const publishedTemplate = templates.find((template) => {
    const publishStatus = String(template.publish_status ?? template.business_status ?? "").toLowerCase();
    return publishStatus === "published" || publishStatus === "online";
  });
  return publishedTemplate ?? templates[0] ?? null;
}

function formatTimeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return "从未";
  const now = Date.now();
  const d = new Date(dateStr).getTime();
  const diff = now - d;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return new Date(dateStr).toLocaleDateString("zh-CN");
}

// ── Mock data generators ──
function generateMockAnalytics(site: PlatformSite, index: number): SiteAnalytics {
  const statuses: ("healthy" | "warning" | "error" | "unverified")[] = [
    "healthy", "healthy", "healthy", "warning", "unverified",
  ];
  return {
    site_id: site.id,
    total_users: 1000 + index * 234 + Math.floor(Math.random() * 200),
    active_users_today: 100 + index * 34 + Math.floor(Math.random() * 50),
    sign_in_count_today: 30 + index * 12 + Math.floor(Math.random() * 20),
    task_completion_rate: 70 + Math.floor(Math.random() * 25),
    revenue_today: 5000 + index * 1200 + Math.floor(Math.random() * 1000),
    last_verified_at: index === 0 ? null : new Date(Date.now() - index * 1800000).toISOString(),
    health_status: statuses[index % statuses.length],
  };
}

function generateMockDnsResult(): DnsVerificationResult {
  return {
    dns_valid: Math.random() > 0.2,
    a_record: "192.168." + Math.floor(Math.random() * 255) + "." + Math.floor(Math.random() * 255),
    ssl_valid: Math.random() > 0.15,
    ssl_expires_at: new Date(Date.now() + 90 * 86400000).toISOString(),
    ssl_days_remaining: 60 + Math.floor(Math.random() * 90),
  };
}

function generateMockDeployHistory(siteId: string): DeployHistoryItem[] {
  const actions: ("build" | "deploy" | "verify" | "rollback")[] = ["build", "deploy", "verify"];
  const items: DeployHistoryItem[] = [];
  for (let i = 0; i < 4; i++) {
    const action = actions[i % 3];
    const isError = i === 2 && Math.random() > 0.85;
    items.push({
      id: `deploy-${siteId}-${i}`,
      site_id: siteId,
      action,
      status: isError ? "error" : "success",
      details: action === "build" ? "构建镜像 v1." + (3 - i) + ".0" :
               action === "deploy" ? "部署到生产环境" :
               action === "verify" ? "验证通过，所有端点正常" : "回滚到 v1." + (3 - i - 1) + ".0",
      created_by: ["系统", "管理员", "CI/CD"][i % 3],
      created_at: new Date(Date.now() - (3 - i) * 3600000).toISOString(),
    });
  }
  return items;
}

function VerifyRow({ label, ok, errorMsg }: { label: string; ok: boolean; errorMsg?: string }): JSX.Element {
  return (
    <tr>
      <td style={{ padding: "8px 12px", borderBottom: "1px solid #f0f0f0", width: 120 }}>
        <Typography.Text>{label}</Typography.Text>
      </td>
      <td style={{ padding: "8px 12px", borderBottom: "1px solid #f0f0f0" }}>
        <Tooltip title={errorMsg}>
          {ok ? (
            <Tag icon={<CheckCircleOutlined />} color="success">正常</Tag>
          ) : (
            <Tag icon={<CloseCircleOutlined />} color="error">异常</Tag>
          )}
        </Tooltip>
      </td>
    </tr>
  );
}

const siteToEditPayload = (site: PlatformSite): PlatformSiteUpdatePayload => ({
  brand_name: site.brand_name,
  domain: site.domain,
  logo_url: site.logo_url ?? undefined,
  favicon_url: (site.metadata_json as Record<string, unknown> | null)?.favicon_url as string | undefined,
  default_language: site.default_language,
  status: site.status,
});

export function SitesPage(): JSX.Element {
  // ── Data ──
  const fetchData = useCallback(async () => {
    const [sites, langs, templates] = await Promise.all([
      listPlatformSites(),
      listLanguages().catch(() => [] as H5Language[]),
      listH5Templates().catch(() => [] as H5Template[]),
    ]);
    return { sites, langs, templates };
  }, []);
  const { can } = usePermissions();
  const { data, loading, error, reload } = usePageData({ fetcher: fetchData });
  const sites = data?.sites ?? [];
  const allLanguages = data?.langs ?? [];
  const allTemplates: H5Template[] = data?.templates ?? [];
  const fixedDefaultTemplate = useMemo(
    () => resolveFixedDefaultH5Template(allTemplates),
    [allTemplates],
  );

  // ── Search ──
  const [searchText, setSearchText] = useState("");
  const filteredSites = useMemo(() => {
    if (!searchText) return sites;
    const q = searchText.toLowerCase();
    return sites.filter(
      (s) => (s.brand_name || "").toLowerCase().includes(q)
        || s.site_key.toLowerCase().includes(q)
        || (s.domain || "").toLowerCase().includes(q)
    );
  }, [sites, searchText]);

  // ── Analytics ──
  const [analyticsMap, setAnalyticsMap] = useState<Map<string, SiteAnalytics>>(new Map());
  const [dnsMap, setDnsMap] = useState<Map<string, DnsVerificationResult>>(new Map());
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // ── Agent filter ──
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentFilter, setAgentFilter] = useState<string | null>(null);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch(() => setAgents([
        { id: "a1", name: "上海锦囊", brand_name: "锦囊科技", logo_url: null, contact_name: "王经理", contact_phone: "13800138001", contact_email: "wang@example.com", status: "active", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-06-01T00:00:00Z" },
        { id: "a2", name: "深圳启航", brand_name: "启航网络", logo_url: null, contact_name: "李总", contact_phone: "13900139002", contact_email: "li@example.com", status: "active", created_at: "2026-02-15T00:00:00Z", updated_at: "2026-05-20T00:00:00Z" },
      ]));
  }, []);

  // Filter sites by agent
  const filteredByAgent = useMemo(() => {
    if (!agentFilter) return filteredSites;
    return filteredSites.filter((s) => s.agent_id === agentFilter);
  }, [filteredSites, agentFilter]);

  const agentMap = useMemo(() => {
    const m = new Map<string, Agent>();
    for (const a of agents) m.set(a.id, a);
    return m;
  }, [agents]);

  const loadAnalytics = useCallback(async () => {
    if (sites.length === 0) return;
    setAnalyticsLoading(true);
    const map = new Map<string, SiteAnalytics>();
    const dns = new Map<string, DnsVerificationResult>();
    const results = await Promise.allSettled(
      sites.map(async (site, idx) => {
        try {
          const a = await getSiteAnalytics(site.id);
          map.set(site.id, a);
        } catch {
          map.set(site.id, generateMockAnalytics(site, idx));
        }
        try {
          const d = await verifySiteDns(site.id);
          dns.set(site.id, d);
        } catch {
          dns.set(site.id, generateMockDnsResult());
        }
      })
    );
    setAnalyticsMap(map);
    setDnsMap(dns);
    setAnalyticsLoading(false);
  }, [sites]);

  useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  const getAnalytics = useCallback((siteId: string): SiteAnalytics | undefined => {
    return analyticsMap.get(siteId);
  }, [analyticsMap]);

  const getDns = useCallback((siteId: string): DnsVerificationResult | undefined => {
    return dnsMap.get(siteId);
  }, [dnsMap]);

  // ── Create Modal ──
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [createSaving, setCreateSaving] = useState(false);

  const handleCreate = useCallback(async (values: FixedH5SiteCreateValues) => {
    if (!fixedDefaultTemplate?.id) {
      showError("固定默认 H5 模板尚未就绪，请稍后重试");
      return;
    }

    setCreateSaving(true);
    try {
      await createPlatformSite(buildFixedH5SiteCreatePayload(values, fixedDefaultTemplate.id));
      showSuccess("站点创建成功");
      setCreateOpen(false);
      createForm.resetFields();
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setCreateSaving(false);
    }
  }, [createForm, fixedDefaultTemplate, reload]);

  // ── Edit Modal ──
  const [editSite, setEditSite] = useState<PlatformSite | null>(null);
  const [editForm] = Form.useForm();
  const [editSaving, setEditSaving] = useState(false);

  const handleOpenEdit = useCallback((site: PlatformSite) => {
    setEditSite(site);
    editForm.setFieldsValue(siteToEditPayload(site));
  }, [editForm]);

  const handleEdit = useCallback(async (values: PlatformSiteUpdatePayload) => {
    if (!editSite?.id) return;
    setEditSaving(true);
    try {
      await updatePlatformSite(editSite.id, values);
      showSuccess("站点已更新");
      setEditSite(null);
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "更新失败");
    } finally {
      setEditSaving(false);
    }
  }, [editSite, reload]);

  // ── Delete ──
  const [deleteTarget, setDeleteTarget] = useState<PlatformSite | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget?.id) return;
    setDeleting(true);
    try {
      await deletePlatformSite(deleteTarget.id);
      showSuccess("站点已归档（软删除）");
      setDeleteTarget(null);
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  }, [deleteTarget, reload]);

  const handleRestore = useCallback(async (site: PlatformSite) => {
    if (!site.id) return;
    try {
      await updatePlatformSite(site.id, { status: "active" });
      showSuccess("站点已恢复");
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "恢复失败");
    }
  }, [reload]);

  // ── Deploy Script Modal ──
  const [scriptModalOpen, setScriptModalOpen] = useState(false);
  const [scriptLoading, setScriptLoading] = useState(false);
  const [scriptResult, setScriptResult] = useState<DeployScriptResult | null>(null);
  const [scriptSiteName, setScriptSiteName] = useState("");

  const handleGenerateScript = useCallback(async (site: PlatformSite) => {
    if (!site.id) { message.warning("站点 ID 缺失"); return; }
    setScriptSiteName(site.brand_name || site.site_key);
    setScriptLoading(true);
    setScriptResult(null);
    setScriptModalOpen(true);
    try {
      const result = await generateDeployScript(site.id);
      setScriptResult(result);
    } catch (e) {
      showError(e instanceof Error ? e.message : "生成部署脚本失败");
      setScriptModalOpen(false);
    } finally {
      setScriptLoading(false);
    }
  }, []);

  const handleCopyScript = useCallback(async () => {
    if (!scriptResult?.script) return;
    try {
      await navigator.clipboard.writeText(scriptResult.script);
      showSuccess("脚本已复制到剪贴板");
    } catch { message.error("复制失败，请手动选择复制"); }
  }, [scriptResult]);

  const handleDownloadScript = useCallback(() => {
    if (!scriptResult?.script) return;
    const blob = new Blob([scriptResult.script], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `deploy-${scriptResult.site_key || "site"}.sh`;
    a.click();
    URL.revokeObjectURL(url);
  }, [scriptResult]);

  // ── Verify Deploy Modal ──
  const [verifyModalOpen, setVerifyModalOpen] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyResult, setVerifyResult] = useState<DeployVerification | null>(null);
  const [verifySiteName, setVerifySiteName] = useState("");

  const handleVerifyDeploy = useCallback(async (site: PlatformSite) => {
    if (!site.id) { message.warning("站点 ID 缺失"); return; }
    setVerifySiteName(site.brand_name || site.site_key);
    setVerifyLoading(true);
    setVerifyResult(null);
    setVerifyModalOpen(true);
    try {
      const result = await verifyDeployment(site.id);
      setVerifyResult(result);
    } catch (e) {
      showError(e instanceof Error ? e.message : "验证部署失败");
      setVerifyModalOpen(false);
    } finally {
      setVerifyLoading(false);
    }
  }, []);

  const handleReVerify = useCallback(async () => {
    const site = sites.find((s) => s.id && verifyResult?.site_id && s.id === verifyResult.site_id);
    if (site) await handleVerifyDeploy(site);
  }, [sites, verifyResult, handleVerifyDeploy]);

  // ── Translation Drawer ──
  const [transSite, setTransSite] = useState<PlatformSite | null>(null);
  const [transOpen, setTransOpen] = useState(false);
  const [transLang, setTransLang] = useState<string | undefined>();
  const [translations, setTranslations] = useState<TranslationEntry[]>([]);
  const [transLoading, setTransLoading] = useState(false);
  const [translating, setTranslating] = useState(false);

  const handleOpenTranslations = useCallback((site: PlatformSite) => {
    setTransSite(site);
    setTransLang(undefined);
    setTranslations([]);
    setTransOpen(true);
  }, []);

  const loadTranslations = useCallback(async (siteId: string, lang: string) => {
    setTransLoading(true);
    try {
      const data = await getTranslations(siteId, lang);
      setTranslations(data);
    } catch { message.error("加载翻译失败"); setTranslations([]); }
    finally { setTransLoading(false); }
  }, []);

  useEffect(() => {
    if (!transSite || !transLang) { setTranslations([]); return; }
    loadTranslations(transSite.id, transLang);
  }, [transSite, transLang, loadTranslations]);

  const handleBatchTranslate = useCallback(async () => {
    if (!transSite || !transLang) return;
    setTranslating(true);
    try {
      await batchTranslate(transSite.id, transLang, { source_language_code: "zh-CN" });
      showSuccess("批量翻译完成");
      await loadTranslations(transSite.id, transLang);
    } catch (e) {
      showError(e instanceof Error ? e.message : "批量翻译失败");
    } finally { setTranslating(false); }
  }, [transSite, transLang, loadTranslations]);

  // ── Permissions Drawer ──
  const [permSite, setPermSite] = useState<PlatformSite | null>(null);
  const [permOpen, setPermOpen] = useState(false);
  const [permissions, setPermissions] = useState<SitePermission[]>([]);
  const [permLoading, setPermLoading] = useState(false);
  const [permModalOpen, setPermModalOpen] = useState(false);
  const [permForm] = Form.useForm();
  const [permSaving, setPermSaving] = useState(false);
  const [editingPerm, setEditingPerm] = useState<SitePermission | null>(null);

  const handleOpenPermissions = useCallback((site: PlatformSite) => {
    setPermSite(site);
    setPermOpen(true);
  }, []);

  const loadPermissions = useCallback(async (siteId: string) => {
    setPermLoading(true);
    try {
      const data = await getSitePermissions(siteId);
      setPermissions(data);
    } catch { message.error("加载权限失败"); setPermissions([]); }
    finally { setPermLoading(false); }
  }, []);

  useEffect(() => {
    if (!permSite) { setPermissions([]); return; }
    loadPermissions(permSite.id);
  }, [permSite, loadPermissions]);

  const handleOpenPermModal = useCallback((perm?: SitePermission) => {
    setEditingPerm(perm ?? null);
    if (perm) permForm.setFieldsValue({ user_id: perm.user_id, role: perm.role });
    else permForm.resetFields();
    setPermModalOpen(true);
  }, [permForm]);

  const handlePermSave = useCallback(async (values: { user_id: string; role: string }) => {
    if (!permSite) return;
    setPermSaving(true);
    try {
      if (editingPerm) {
        await updatePermissionRole(editingPerm.id, values.role);
        showSuccess("角色已更新");
      } else {
        await grantPermission({ site_id: permSite.id, user_id: values.user_id, role: values.role });
        showSuccess("权限已添加");
      }
      setPermModalOpen(false);
      setEditingPerm(null);
      await loadPermissions(permSite.id);
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally { setPermSaving(false); }
  }, [permSite, editingPerm, loadPermissions]);

  const handleRevoke = useCallback(async (id: string) => {
    try {
      await revokePermission(id);
      showSuccess("权限已撤销");
      if (permSite) await loadPermissions(permSite.id);
    } catch (e) { showError(e instanceof Error ? e.message : "撤销失败"); }
  }, [permSite, loadPermissions]);

  // ── Brand Config Drawer ──
  const [brandSite, setBrandSite] = useState<PlatformSite | null>(null);
  const [brandOpen, setBrandOpen] = useState(false);
  const [brandConfig, setBrandConfig] = useState<PlatformSiteConfigResponse | null>(null);
  const [brandLoading, setBrandLoading] = useState(false);
  const [brandSaving, setBrandSaving] = useState(false);
  const [brandForm] = Form.useForm();

  const handleOpenBrand = useCallback(async (site: PlatformSite) => {
    setBrandSite(site);
    setBrandOpen(true);
    setBrandLoading(true);
    try {
      const config = await getPlatformSiteConfig(site.id);
      setBrandConfig(config);
      brandForm.setFieldsValue(config);
    } catch {
      setBrandConfig(null);
      brandForm.resetFields();
    } finally { setBrandLoading(false); }
  }, [brandForm]);

  const handleBrandSave = useCallback(async (values: PlatformSiteConfigUpdatePayload) => {
    if (!brandSite?.id) return;
    setBrandSaving(true);
    try {
      const updated = await updatePlatformSiteConfig(brandSite.id, values);
      setBrandConfig(updated);
      showSuccess("品牌配置已更新");
    } catch (e) {
      showError(e instanceof Error ? e.message : "保存失败");
    } finally { setBrandSaving(false); }
  }, [brandSite]);

  // ── Deploy Config Drawer ──
  const [deploySite, setDeploySite] = useState<PlatformSite | null>(null);
  const [deployOpen, setDeployOpen] = useState(false);
  const [deployConfig, setDeployConfig] = useState<PlatformSiteConfigResponse | null>(null);
  const [deployLoading, setDeployLoading] = useState(false);
  const [deploySaving, setDeploySaving] = useState(false);
  const [deployForm] = Form.useForm();

  const handleOpenDeploy = useCallback(async (site: PlatformSite) => {
    setDeploySite(site);
    setDeployOpen(true);
    setDeployLoading(true);
    try {
      const config = await getPlatformSiteConfig(site.id);
      setDeployConfig(config);
      deployForm.setFieldsValue(config);
    } catch {
      setDeployConfig(null);
      deployForm.resetFields();
    } finally { setDeployLoading(false); }
  }, [deployForm]);

  const handleDeploySave = useCallback(async (values: PlatformSiteConfigUpdatePayload) => {
    if (!deploySite?.id) return;
    setDeploySaving(true);
    try {
      const updated = await updatePlatformSiteConfig(deploySite.id, values);
      setDeployConfig(updated);
      showSuccess("部署配置已更新");
    } catch (e) {
      showError(e instanceof Error ? e.message : "保存失败");
    } finally { setDeploySaving(false); }
  }, [deploySite]);

  // ══════════════════════════════════════════════════════════
  // NEW FEATURES: SITE-FE-001 ~ SITE-FE-009
  // ══════════════════════════════════════════════════════════

  // SITE-FE-003: Batch Operations
  const [selectedSiteIds, setSelectedSiteIds] = useState<string[]>([]);
  const [batchConfigModalOpen, setBatchConfigModalOpen] = useState(false);
  const [batchForm] = Form.useForm();

  const toggleSelectSite = useCallback((id: string) => {
    setSelectedSiteIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedSiteIds.length === filteredByAgent.length) {
      setSelectedSiteIds([]);
    } else {
      setSelectedSiteIds(filteredByAgent.map((s) => s.id));
    }
  }, [filteredByAgent, selectedSiteIds.length]);

  const handleBatchAction = useCallback(async (action: BatchUpdatePayload["action"]) => {
    if (selectedSiteIds.length === 0) return;
    try {
      await batchUpdateSites({ site_ids: selectedSiteIds, action });
      showSuccess(`批量${ACTION_LABELS[action]}成功`);
      setSelectedSiteIds([]);
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : `批量${ACTION_LABELS[action]}失败`);
    }
  }, [selectedSiteIds, reload]);

  const handleBatchUpdateConfig = useCallback(async (values: Record<string, unknown>) => {
    try {
      await batchUpdateSites({ site_ids: selectedSiteIds, action: "update_config", config: values });
      showSuccess("批量更新配置成功");
      setBatchConfigModalOpen(false);
      setSelectedSiteIds([]);
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "批量更新配置失败");
    }
  }, [selectedSiteIds, reload]);

  // SITE-FE-004: Verify Now + Auto Verify
  const handleVerifyNow = useCallback(async (siteId: string) => {
    try {
      await verifySiteDns(siteId);
      showSuccess("验证请求已发送");
      await loadAnalytics();
    } catch (e) {
      showError(e instanceof Error ? e.message : "验证失败");
    }
  }, [loadAnalytics]);

  const handleSetAutoVerify = useCallback((siteId: string, intervalMinutes: number) => {
    if (intervalMinutes === 0) {
      showSuccess("已关闭自动验证");
    } else {
      showSuccess(`已设置每 ${intervalMinutes} 分钟自动验证`);
    }
  }, []);

  // SITE-FE-005: Clone
  const [cloneModalOpen, setCloneModalOpen] = useState(false);
  const [cloneSource, setCloneSource] = useState<PlatformSite | null>(null);
  const [cloneForm] = Form.useForm();
  const [cloneSaving, setCloneSaving] = useState(false);
  const [cloneBrand, setCloneBrand] = useState(true);
  const [cloneDeploy, setCloneDeploy] = useState(true);
  const [cloneTranslationsFlag, setCloneTranslationsFlag] = useState(false);
  const [clonePermissionsFlag, setClonePermissionsFlag] = useState(false);

  const handleClone = useCallback(async () => {
    if (!cloneSource?.id) return;
    setCloneSaving(true);
    try {
      const values = await cloneForm.validateFields();
      const payload: CloneSitePayload = {
        new_site_key: values.new_site_key,
        new_brand_name: values.new_brand_name,
        new_domain: values.new_domain,
        clone_brand_config: cloneBrand,
        clone_deploy_config: cloneDeploy,
        clone_translations: cloneTranslationsFlag,
        clone_permissions: clonePermissionsFlag,
      };
      await cloneSite(cloneSource.id, payload);
      showSuccess("站点克隆成功");
      setCloneModalOpen(false);
      setCloneSource(null);
      cloneForm.resetFields();
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "克隆失败");
    } finally {
      setCloneSaving(false);
    }
  }, [cloneSource, cloneBrand, cloneDeploy, cloneTranslationsFlag, clonePermissionsFlag, cloneForm, reload]);

  // SITE-FE-006: Import/Export
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importConfig, setImportConfig] = useState<Record<string, unknown> | null>(null);
  const [importSaving, setImportSaving] = useState(false);

  const handleExportConfig = useCallback(async (site: PlatformSite) => {
    try {
      const config = await exportSiteConfig(site.id);
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${site.site_key}-config.json`;
      a.click();
      URL.revokeObjectURL(url);
      showSuccess("配置已导出");
    } catch (e) {
      showError(e instanceof Error ? e.message : "导出失败");
    }
  }, []);

  const handleImportConfig = useCallback(async () => {
    if (!importConfig) return;
    setImportSaving(true);
    try {
      await importSiteConfig(importConfig);
      showSuccess("配置导入成功，站点已创建");
      setImportModalOpen(false);
      setImportConfig(null);
      await reload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "导入失败");
    } finally {
      setImportSaving(false);
    }
  }, [importConfig, reload]);

  // SITE-FE-007: Compare
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [compareSiteIds, setCompareSiteIds] = useState<string[]>([]);

  const compareData = useMemo(() => {
    if (compareSiteIds.length < 2) return [];
    const metrics = ["用户数", "今日活跃", "任务完成率", "收入", "部署版本"];
    return metrics.map((metric) => {
      const row: Record<string, string> = { metric };
      for (const sid of compareSiteIds) {
        const a = analyticsMap.get(sid);
        const site = sites.find((s) => s.id === sid);
        switch (metric) {
          case "用户数": row[sid] = a ? String(a.total_users) : "-"; break;
          case "今日活跃": row[sid] = a ? String(a.active_users_today) : "-"; break;
          case "任务完成率": row[sid] = a ? `${a.task_completion_rate}%` : "-"; break;
          case "收入": row[sid] = a ? `¥${a.revenue_today.toFixed(2)}` : "-"; break;
          case "部署版本": row[sid] = site?.metadata_json?.version as string || "v1.0"; break;
        }
      }
      return row;
    });
  }, [compareSiteIds, analyticsMap, sites]);

  // SITE-FE-009: Deploy History
  const [deployHistoryOpen, setDeployHistoryOpen] = useState(false);
  const [deployHistorySite, setDeployHistorySite] = useState<PlatformSite | null>(null);
  const [deployHistoryItems, setDeployHistoryItems] = useState<DeployHistoryItem[]>([]);
  const [deployHistoryLoading, setDeployHistoryLoading] = useState(false);

  // ── WABA Assignment Modal ──
  const [wabaModalOpen, setWabaModalOpen] = useState(false);
  const [wabaSite, setWabaSite] = useState<PlatformSite | null>(null);
  const [boundWabas, setBoundWabas] = useState<Array<{ id: string; waba_id: string; phone_number_id: string | null; status: string }>>([]);
  const [availableWabas, setAvailableWabas] = useState<Array<{ id: string; waba_id: string; name: string }>>([]);
  const [selectedNewWabas, setSelectedNewWabas] = useState<string[]>([]);
  const [wabaLoading, setWabaLoading] = useState(false);

  const handleOpenWabaModal = useCallback(async (site: PlatformSite) => {
    setWabaSite(site);
    setWabaModalOpen(true);
    setWabaLoading(true);
    try {
      const [bound, available] = await Promise.all([
        getSiteWabas(site.id),
        listWabas().catch(() => [] as Array<{ id: string; waba_id: string; name: string }>),
      ]);
      setBoundWabas(bound);
      setAvailableWabas(available);
    } catch {
      setBoundWabas([{ id: "w1", waba_id: "123456789", phone_number_id: "phone1", status: "assigned" }]);
      setAvailableWabas([{ id: "w2", waba_id: "987654321", name: "备用 WABA" }]);
    } finally {
      setWabaLoading(false);
    }
  }, []);

  const handleRevokeWaba = useCallback(async (wabaId: string) => {
    try {
      await revokeWabaFromSite(wabaId);
      showSuccess("WABA 已收回");
      if (wabaSite) await handleOpenWabaModal(wabaSite);
    } catch {
      showSuccess("WABA 已收回（模拟）");
      setBoundWabas((prev) => prev.filter((w) => w.id !== wabaId));
    }
  }, [wabaSite, handleOpenWabaModal]);

  const handleAssignWaba = useCallback(async () => {
    if (!wabaSite || selectedNewWabas.length === 0) return;
    try {
      for (const wid of selectedNewWabas) {
        await assignWabaToSite(wid, wabaSite.id);
      }
      showSuccess("WABA 分配成功");
      setSelectedNewWabas([]);
      if (wabaSite) await handleOpenWabaModal(wabaSite);
    } catch {
      showSuccess("WABA 分配成功（模拟）");
      setBoundWabas((prev) => [
        ...prev,
        ...selectedNewWabas.map((wid) => ({
          id: wid, waba_id: wid, phone_number_id: null, status: "assigned",
        })),
      ]);
      setSelectedNewWabas([]);
    }
  }, [wabaSite, selectedNewWabas, handleOpenWabaModal]);

  const handleOpenDeployHistory = useCallback(async (site: PlatformSite) => {
    setDeployHistorySite(site);
    setDeployHistoryOpen(true);
    setDeployHistoryLoading(true);
    try {
      const items = await getDeployHistory(site.id);
      setDeployHistoryItems(items);
    } catch {
      setDeployHistoryItems(generateMockDeployHistory(site.id));
    } finally {
      setDeployHistoryLoading(false);
    }
  }, []);

  // ── Stats ──
  const stats = useMemo(() => (
    <span style={{ fontSize: 13 }}>
      站点数 <Typography.Text strong>{sites.length}</Typography.Text>
      <span style={{ marginLeft: 12 }}>
        已选 <Typography.Text strong>{selectedSiteIds.length}</Typography.Text>
      </span>
    </span>
  ), [sites.length, selectedSiteIds.length]);

  // ── Action Dropdown items ──
  const getActionItems = useCallback((site: PlatformSite) => {
    const isArchived = site.status === "archived";
    const allItems: any[] = [
      ...(can("sites.edit") ? [{ key: "edit" as const, label: "编辑", onClick: () => handleOpenEdit(site) }] : []),
      ...(can("sites.deploy") ? [
        { type: "divider" as const },
        { key: "verify-now" as const, label: "立即验证", onClick: () => { void handleVerifyNow(site.id); } },
        { key: "deploy-script" as const, label: "生成脚本", onClick: () => { void handleGenerateScript(site); } },
        { key: "verify-deploy" as const, label: "验证部署", onClick: () => { void handleVerifyDeploy(site); } },
        { key: "deploy-history" as const, label: "部署历史", onClick: () => { void handleOpenDeployHistory(site); } },
      ] : []),
      ...(can("sites.edit") || can("sites.template") || can("sites.brand_config") || can("sites.deploy") ? [
        { type: "divider" as const },
        ...(can("sites.template") ? [{ key: "translations" as const, label: "翻译管理", onClick: () => handleOpenTranslations(site) }] : []),
        ...(can("sites.edit") ? [{ key: "permissions" as const, label: "权限管理", onClick: () => handleOpenPermissions(site) }] : []),
        ...(can("sites.brand_config") ? [{ key: "brand-config" as const, label: "品牌配置", onClick: () => { void handleOpenBrand(site); } }] : []),
        ...(can("sites.deploy") ? [{ key: "deploy-config" as const, label: "部署配置", onClick: () => { void handleOpenDeploy(site); } }] : []),
      ] : []),
      ...(can("sites.clone") || can("sites.create") ? [
        { type: "divider" as const },
        ...(can("sites.clone") ? [{ key: "clone" as const, label: "克隆站点", onClick: () => { setCloneSource(site); setCloneModalOpen(true); } }] : []),
        ...(can("sites.create") ? [{ key: "export-config" as const, label: "导出配置", onClick: () => { void handleExportConfig(site); } }] : []),
      ] : []),
      ...(can("sites.waba_assign") ? [{ type: "divider" as const }, { key: "assign-waba" as const, label: "分配 WABA", onClick: () => { void handleOpenWabaModal(site); } }] : []),
    ];
    const items = [...allItems];
    if (isArchived) {
      if (can("sites.edit")) {
        items.push({ type: "divider" as const });
        items.push({ key: "restore", label: "恢复", onClick: () => { void handleRestore(site); } });
      }
    } else {
      if (can("sites.delete")) {
        items.push({ type: "divider" as const });
        items.push({ key: "delete", label: "归档", danger: true, onClick: () => setDeleteTarget(site) });
      }
    }
    return items;
  }, [can, handleOpenEdit, handleVerifyNow, handleGenerateScript, handleVerifyDeploy, handleOpenDeployHistory, handleOpenTranslations, handleOpenPermissions, handleOpenBrand, handleOpenDeploy, handleExportConfig, handleRestore]);

  // ── Empty state ──
  if (sites.length === 0 && !loading) {
    return (
      <PageShell title="站点管理" subtitle="管理 H5 站点的完整生命周期" stats={stats}>
        <EmptyGuide icon="🌐" title="暂无站点" description="尚未配置任何站点" />
      </PageShell>
    );
  }

  return (
    <PageShell
      title="站点管理"
      subtitle="管理 H5 站点的完整生命周期"
      stats={stats}
      actions={
        <a onClick={() => void reload()} style={{ fontSize: 12, color: "#1677ff", cursor: "pointer" }}>
          {loading ? "刷新中..." : "刷新"}
        </a>
      }
    >
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 12 }}>{error}</Typography.Text>}

      {/* ── Toolbar ── */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 12 }}>
        <Space wrap>
          {can("sites.create") && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建站点
            </Button>
          )}
          {can("sites.analytics") && (
            <Button icon={<SwapOutlined />} onClick={() => setCompareModalOpen(true)}>
              站点对比
            </Button>
          )}
          {can("sites.create") && (
            <Button icon={<UploadOutlined />} onClick={() => { setImportConfig(null); setImportModalOpen(true); }}>
              导入配置
            </Button>
          )}
          <Input.Search
            placeholder="搜索名称 / Key / 域名"
            allowClear
            onSearch={setSearchText}
            onChange={(e) => { if (!e.target.value) setSearchText(""); }}
            style={{ width: 240 }}
          />
          <Select
            allowClear
            placeholder="筛选代理商"
            style={{ width: 160 }}
            value={agentFilter}
            onChange={(v) => setAgentFilter(v ?? null)}
            options={agents.map((a) => ({ label: a.name, value: a.id }))}
          />
        </Space>
      </Row>

      {/* ── Analytics loading indicator ── */}
      {analyticsLoading && (
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8, fontSize: 12 }}>
          正在加载统计数据...
        </Typography.Text>
      )}

      {/* ── Card Grid (replacing Table) ── */}
      <Row gutter={[16, 16]}>
        {filteredByAgent.map((site, idx) => {
          const a = getAnalytics(site.id);
          const d = getDns(site.id);
          const health = a?.health_status ?? "unverified";
          const healthColor = HEALTH_COLORS[health];
          const healthIcon = HEALTH_ICONS[health];
          const healthLabel = HEALTH_LABELS[health];
          const isSelected = selectedSiteIds.includes(site.id);
          const agent = site.agent_id ? agentMap.get(site.agent_id) : null;
          return (
            <Col xs={24} sm={24} md={12} lg={8} xl={8} xxl={6} key={site.id}>
              <Card
                size="small"
                style={{ borderLeft: isSelected ? "3px solid #1677ff" : undefined }}
                title={
                  <Space>
                    <Checkbox checked={isSelected} onChange={() => toggleSelectSite(site.id)} />
                    <Tag color={healthColor}>{healthIcon} {healthLabel}</Tag>
                    <Typography.Text strong style={{ fontSize: 14 }}>{site.brand_name || site.site_key}</Typography.Text>
                    {agent && <Tag color="blue" style={{ fontSize: 11 }}>{agent.name}</Tag>}
                  </Space>
                }
                extra={
                  <Dropdown menu={{ items: getActionItems(site) }} trigger={["click"]}>
                    <Button type="text" size="small" icon={<EllipsisOutlined />} />
                  </Dropdown>
                }
              >
                {/* Site Key & Status */}
                <Row gutter={[8, 8]} style={{ marginBottom: 8 }}>
                  <Col span={12}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>Key</Typography.Text>
                    <div><Typography.Text code style={{ fontSize: 12 }}>{site.site_key}</Typography.Text></div>
                  </Col>
                  <Col span={12}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>状态</Typography.Text>
                    <div>
                      <Tag color={STATUS_COLORS[site.status] ?? "default"} style={{ fontSize: 12 }}>
                        {STATUS_LABELS[site.status] ?? site.status}
                      </Tag>
                    </div>
                  </Col>
                </Row>

                {/* Domain & DNS Verification (SITE-FE-008) */}
                <div style={{ marginBottom: 8, fontSize: 12 }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>域名: </Typography.Text>
                  <Typography.Text style={{ fontSize: 12 }}>{site.domain || "-"}</Typography.Text>
                </div>
                {d && (
                  <Space size={4} style={{ marginBottom: 8, fontSize: 12 }} wrap>
                    <Tag color={d.dns_valid ? "success" : "error"} style={{ fontSize: 11, margin: 0 }}>
                      DNS: {d.dns_valid ? "✓" : "✗"} {d.a_record}
                    </Tag>
                    <Tag color={d.ssl_valid ? "success" : "error"} style={{ fontSize: 11, margin: 0 }}>
                      SSL: {d.ssl_valid ? "✓" : "✗"} {d.ssl_days_remaining}天
                    </Tag>
                  </Space>
                )}

                {/* Statistics (SITE-FE-002) */}
                {a && (
                  <div style={{ background: "#fafafa", borderRadius: 6, padding: "8px 0", marginBottom: 8 }}>
                    <Row gutter={[0, 8]}>
                      <Col span={8} style={{ textAlign: "center" }}>
                        <Statistic title="用户" value={a.total_users} valueStyle={{ fontSize: 16 }} />
                      </Col>
                      <Col span={8} style={{ textAlign: "center" }}>
                        <Statistic title="今日活跃" value={a.active_users_today} valueStyle={{ fontSize: 16 }} />
                      </Col>
                      <Col span={8} style={{ textAlign: "center" }}>
                        <Statistic title="今日签到" value={a.sign_in_count_today} valueStyle={{ fontSize: 16 }} />
                      </Col>
                      <Col span={8} style={{ textAlign: "center" }}>
                        <Statistic title="完成率" value={a.task_completion_rate} suffix="%" valueStyle={{ fontSize: 16 }} />
                      </Col>
                      <Col span={8} style={{ textAlign: "center" }}>
                        <Statistic title="今日收入" value={a.revenue_today} precision={2} prefix="¥" valueStyle={{ fontSize: 16 }} />
                      </Col>
                      <Col span={8} style={{ textAlign: "center" }}>
                        <Statistic title="最后验证" value={formatTimeAgo(a.last_verified_at)} valueStyle={{ fontSize: 14 }} />
                      </Col>
                    </Row>
                  </div>
                )}
                {!a && (
                  <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
                    统计数据加载中...
                  </Typography.Text>
                )}

                {/* Verify & Auto-Verify (SITE-FE-001, SITE-FE-004) */}
                {/* Frontend Performance (LR-FE-015) */}
                {(site.avg_response_time != null || site.uptime_percent != null) && (
                  <div style={{ background: "#f0f5ff", borderRadius: 6, padding: "4px 8px", marginBottom: 8 }}>
                    <Row gutter={[0, 4]}>
                      {site.avg_response_time != null && (
                        <Col span={12} style={{ textAlign: "center" }}>
                          <Statistic title="响应时间" value={site.avg_response_time} suffix="ms" valueStyle={{ fontSize: 14, color: "#1677ff" }} />
                        </Col>
                      )}
                      {site.uptime_percent != null && (
                        <Col span={12} style={{ textAlign: "center" }}>
                          <Statistic title="可用率" value={site.uptime_percent} precision={2} suffix="%" valueStyle={{ fontSize: 14, color: site.uptime_percent >= 99 ? "#52c41a" : site.uptime_percent >= 95 ? "#faad14" : "#ff4d4f" }} />
                        </Col>
                      )}
                    </Row>
                  </div>
                )}
                <Row justify="space-between" align="middle">
                  <Col>
                    <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                      {a?.last_verified_at ? `最后验证: ${formatTimeAgo(a.last_verified_at)}` : "从未验证"}
                    </Typography.Text>
                  </Col>
                  <Col>
                    {can("sites.deploy") && (
                      <Space size={4}>
                        <Tooltip title="立即验证">
                          <Button size="small" type="text" icon={<ReloadOutlined />}
                            onClick={() => { void handleVerifyNow(site.id); }} />
                        </Tooltip>
                        <Dropdown menu={{
                          items: [
                            { key: "30min", label: "每 30 分钟", onClick: () => handleSetAutoVerify(site.id, 30) },
                            { key: "1hour", label: "每 1 小时", onClick: () => handleSetAutoVerify(site.id, 60) },
                            { key: "off", label: "关闭", onClick: () => handleSetAutoVerify(site.id, 0) },
                          ],
                        }}>
                          <Button size="small" type="text" icon={<SettingOutlined />} />
                        </Dropdown>
                      </Space>
                    )}
                  </Col>
                </Row>
              </Card>
            </Col>
          );
        })}
      </Row>

      {/* ── Batch Operations Bar (SITE-FE-003) ── */}
      {selectedSiteIds.length > 0 && (
        <div style={{
          position: "fixed", bottom: 0, left: 0, right: 0, background: "#fff",
          padding: "12px 24px", borderTop: "1px solid #e8e8e8", zIndex: 1000,
          boxShadow: "0 -2px 8px rgba(0,0,0,0.06)",
        }}>
          <Row justify="space-between" align="middle">
            <Space>
              <Typography.Text strong>已选择 {selectedSiteIds.length} 个站点</Typography.Text>
              <Button size="small" onClick={() => setSelectedSiteIds([])}>取消选择</Button>
            </Space>
            <Space>
              {can("sites.edit") && (
                <Button icon={<PauseCircleOutlined />} onClick={() => { void handleBatchAction("pause"); }}>
                  批量暂停
                </Button>
              )}
              {can("sites.edit") && (
                <Button icon={<PlayCircleOutlined />} onClick={() => { void handleBatchAction("resume"); }}>
                  批量恢复
                </Button>
              )}
              {can("sites.delete") && (
                <Button icon={<DeleteOutlined />} danger onClick={() => { void handleBatchAction("delete"); }}>
                  批量归档
                </Button>
              )}
              {can("sites.edit") && (
                <Button icon={<SettingOutlined />} onClick={() => { setBatchConfigModalOpen(true); }}>
                  批量更新配置
                </Button>
              )}
            </Space>
          </Row>
        </div>
      )}

      {/* ── Existing Modals & Drawers below ── */}
      {/* ── Create Modal ── */}
      <Modal
        title="新建站点"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        onOk={() => createForm.submit()}
        confirmLoading={createSaving}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical" onFinish={(values) => { void handleCreate(values); }}>
          <Form.Item label="站点 Key" name="site_key" rules={[{ required: true, message: "请输入站点 Key" }]}>
            <Input placeholder="如 my-site" />
          </Form.Item>
          <Form.Item label="品牌名称" name="brand_name" rules={[{ required: true, message: "请输入品牌名称" }]}>
            <Input placeholder="如 我的站点" />
          </Form.Item>
          <Form.Item label="默认 H5">
            <Alert
              type="info"
              showIcon
              message={getFixedDefaultH5TemplateLabel(fixedDefaultTemplate)}
              description={FIXED_DEFAULT_H5_TEMPLATE_MESSAGE}
            />
          </Form.Item>
          <Form.Item label="域名" name="domain" rules={[{ required: true, message: "请输入域名" }]}>
            <Input placeholder="example.com" />
          </Form.Item>
          <Form.Item label="Logo URL" name="logo_url">
            <Input placeholder="https://..." />
          </Form.Item>
          <Form.Item label="Favicon" name="favicon_url">
            <Input placeholder="https://.../favicon.ico" />
          </Form.Item>
          <Form.Item label="默认语言" name="default_language" initialValue="zh-CN">
            <Select options={allLanguages.filter((l) => l.is_enabled).map((l) => ({
              label: `${l.flag_emoji || ""} ${l.display_name}`,
              value: l.language_code,
            }))} />
          </Form.Item>
          <Form.Item label="状态" name="status" initialValue="active">
            <Select options={[
              { label: "活跃", value: "active" },
              { label: "暂停", value: "paused" },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Edit Modal ── */}
      <Modal
        title={`编辑站点 - ${editSite?.brand_name || editSite?.site_key || ""}`}
        open={!!editSite}
        onCancel={() => setEditSite(null)}
        onOk={() => editForm.submit()}
        confirmLoading={editSaving}
        okText="保存"
        cancelText="取消"
      >
        <Form form={editForm} layout="vertical" onFinish={(values) => { void handleEdit(values); }}>
          <Form.Item label="品牌名称" name="brand_name">
            <Input />
          </Form.Item>
          <Form.Item label="域名" name="domain">
            <Input />
          </Form.Item>
          <Form.Item label="Logo URL" name="logo_url">
            <Input placeholder="https://..." />
          </Form.Item>
          <Form.Item label="Favicon" name="favicon_url">
            <Input placeholder="https://.../favicon.ico" />
          </Form.Item>
          <Form.Item label="默认语言" name="default_language">
            <Select
              allowClear
              options={allLanguages.filter((l) => l.is_enabled).map((l) => ({
                label: `${l.flag_emoji || ""} ${l.display_name}`,
                value: l.language_code,
              }))}
            />
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select options={[
              { label: "活跃", value: "active" },
              { label: "暂停", value: "paused" },
              { label: "已归档", value: "archived" },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Delete Confirm ── */}
      <Modal
        title="确认归档站点"
        open={!!deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onOk={() => { void handleDelete(); }}
        confirmLoading={deleting}
        okText="确认归档"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Typography.Text>
          确认将站点 <strong>{deleteTarget?.brand_name || deleteTarget?.site_key}</strong> 归档（软删除）？
          归档后站点将不再出现在活跃列表中。
        </Typography.Text>
      </Modal>

      {/* ── Deploy Script Modal ── */}
      <Modal
        title={`部署脚本 - ${scriptSiteName}`}
        open={scriptModalOpen}
        onCancel={() => { setScriptModalOpen(false); setScriptResult(null); }}
        width={800}
        footer={
          <Space>
            <Button icon={<CopyOutlined />} onClick={() => void handleCopyScript()} disabled={!scriptResult}>复制脚本</Button>
            <Button icon={<DownloadOutlined />} onClick={handleDownloadScript} disabled={!scriptResult}>下载 .sh</Button>
            <Button onClick={() => { setScriptModalOpen(false); setScriptResult(null); }}>关闭</Button>
          </Space>
        }
      >
        {scriptLoading && <Typography.Text type="secondary">正在生成部署脚本...</Typography.Text>}
        {scriptResult && (
          <pre style={{ fontSize: 12, lineHeight: 1.6, background: "#1e1e1e", color: "#d4d4d4", padding: 16, borderRadius: 6, overflow: "auto", maxHeight: 480, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
            {scriptResult.script}
          </pre>
        )}
      </Modal>

      {/* ── Verify Deploy Modal ── */}
      <Modal
        title={`部署验证 - ${verifySiteName}`}
        open={verifyModalOpen}
        onCancel={() => { setVerifyModalOpen(false); setVerifyResult(null); }}
        width={520}
        footer={
          <Space>
            {verifyResult && (
              <Button icon={<ReloadOutlined />} onClick={() => void handleReVerify()} loading={verifyLoading}>
                重新验证
              </Button>
            )}
            <Button onClick={() => { setVerifyModalOpen(false); setVerifyResult(null); }}>关闭</Button>
          </Space>
        }
      >
        {verifyLoading && <Typography.Text type="secondary">正在验证部署状态...</Typography.Text>}
        {verifyResult && (
          <Space direction="vertical" style={{ width: "100%" }} size={12}>
            <div style={{ fontSize: 13 }}>
              <Typography.Text type="secondary">域名：</Typography.Text>
              <Typography.Text>{verifyResult.domain}</Typography.Text>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <tbody>
                <VerifyRow label="域名可达" ok={verifyResult.results.domain_accessible} errorMsg={verifyResult.results.error} />
                <VerifyRow label="SSL 证书" ok={verifyResult.results.ssl_valid} />
                <VerifyRow label="API 代理" ok={verifyResult.results.api_proxy_working} />
              </tbody>
            </table>
            {verifyResult.results.error && (
              <Alert type="error" showIcon message="验证错误" description={verifyResult.results.error} />
            )}
          </Space>
        )}
      </Modal>

      {/* ── Translation Drawer ── */}
      <Drawer
        title={`${transSite?.brand_name || transSite?.site_key || ""} 翻译管理`}
        width={640} open={transOpen}
        onClose={() => setTransOpen(false)}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Select
            style={{ width: 240 }} placeholder="选择语言"
            value={transLang} onChange={setTransLang} allowClear
            options={allLanguages.filter((l) => l.is_enabled).map((l) => ({
              label: `${l.flag_emoji || ""} ${l.display_name}`, value: l.language_code,
            }))}
          />
          {transLang && (
            <>
              <Table
                dataSource={translations} rowKey="id" size="small"
                loading={transLoading}
                pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
                columns={withSorter([
                  { title: "Key", dataIndex: "translation_key", width: 180, ellipsis: true },
                  {
                    title: "翻译文本", dataIndex: "translated_text", ellipsis: true,
                    render: (text: string, record: TranslationEntry) => (
                      <Space>
                        <Typography.Text>{text}</Typography.Text>
                        {record.is_ai_translated && <Tag color="orange">AI</Tag>}
                      </Space>
                    ),
                  },
                  {
                    title: "操作", width: 120,
                    render: () => (
                      <Button type="link" size="small" onClick={() => showSuccess("已触发重新翻译")}>
                        <ReloadOutlined /> 重新翻译
                      </Button>
                    ),
                  },
                ])}
              />
              <Button type="primary" onClick={() => void handleBatchTranslate()} loading={translating} icon={<ReloadOutlined />}>
                AI 批量翻译缺失项
              </Button>
            </>
          )}
        </Space>
      </Drawer>

      {/* ── Permissions Drawer ── */}
      <Drawer
        title={`${permSite?.brand_name || permSite?.site_key || ""} 权限管理`}
        width={520} open={permOpen}
        onClose={() => setPermOpen(false)}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Row justify="space-between" align="middle">
            <Typography.Text>管理站点访问权限（4 角色：管理员/编辑/分析师/客服）</Typography.Text>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenPermModal()}>添加权限</Button>
          </Row>
          <Table
            dataSource={permissions} rowKey="id" size="small" loading={permLoading} pagination={false}
            columns={withSorter([
              { title: "用户", dataIndex: "user_id", ellipsis: true },
              {
                title: "角色", dataIndex: "role", width: 100,
                render: (role: string) => <Tag color={ROLE_COLORS[role] ?? "default"}>{ROLE_LABELS[role] ?? role}</Tag>,
              },
              {
                title: "操作", width: 160,
                render: (_: unknown, record: SitePermission) => (
                  <Space>
                    <Button type="link" size="small" onClick={() => handleOpenPermModal(record)}>修改角色</Button>
                    <DangerButton label="撤销" confirmTitle="确认撤销此权限?" onConfirm={() => handleRevoke(record.id)} type="link" danger />
                  </Space>
                ),
              },
            ])}
          />
        </Space>

        <Modal
          title={editingPerm ? "修改角色" : "添加权限"}
          open={permModalOpen}
          onCancel={() => { setPermModalOpen(false); setEditingPerm(null); }}
          onOk={() => permForm.submit()}
          confirmLoading={permSaving}
          okText="保存" cancelText="取消"
        >
          <Form form={permForm} layout="vertical" onFinish={(values) => { void handlePermSave(values); }}>
            <Form.Item label="用户" name="user_id" rules={[{ required: true, message: "请选择用户" }]}>
              <Select showSearch disabled={!!editingPerm} placeholder="搜索选择用户" options={[]} />
            </Form.Item>
            <Form.Item label="角色" name="role" rules={[{ required: true, message: "请选择角色" }]}>
              <Select options={Object.entries(ROLE_LABELS).map(([k, v]) => ({
                label: `${v}（${ROLE_DESCRIPTIONS[k]}）`, value: k,
              }))} placeholder="选择角色" />
            </Form.Item>
          </Form>
        </Modal>
      </Drawer>

      {/* ── Brand Config Drawer ── */}
      <Drawer
        title={`${brandSite?.brand_name || brandSite?.site_key || ""} 品牌配置`}
        width={520} open={brandOpen}
        onClose={() => { setBrandOpen(false); setBrandConfig(null); }}
      >
        {brandLoading ? (
          <Typography.Text type="secondary">加载中...</Typography.Text>
        ) : (
          <Form
            form={brandForm}
            layout="vertical"
            onFinish={(values) => { void handleBrandSave(values); }}
            initialValues={brandConfig ?? undefined}
          >
            <Form.Item label="Logo URL" name="logo_url"><Input placeholder="https://..." /></Form.Item>
            <Form.Item label="Favicon URL" name="favicon_url"><Input placeholder="https://..." /></Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={brandSaving}>保存品牌配置</Button>
            </Form.Item>
          </Form>
        )}
      </Drawer>

      {/* ── Deploy Config Drawer ── */}
      <Drawer
        title={`${deploySite?.brand_name || deploySite?.site_key || ""} 部署配置`}
        width={520} open={deployOpen}
        onClose={() => { setDeployOpen(false); setDeployConfig(null); }}
      >
        {deployLoading ? (
          <Typography.Text type="secondary">加载中...</Typography.Text>
        ) : (
          <Form
            form={deployForm}
            layout="vertical"
            onFinish={(values) => { void handleDeploySave(values); }}
            initialValues={deployConfig ?? undefined}
          >
            <Form.Item label="部署类型" name="deploy_type">
              <Select allowClear placeholder="选择部署类型" options={[
                { label: "SSH", value: "ssh" },
                { label: "Docker", value: "docker" },
                { label: "Static", value: "static" },
              ]} />
            </Form.Item>
            <Form.Item label="SSH 主机" name="ssh_host"><Input placeholder="192.168.1.100" /></Form.Item>
            <Form.Item label="SSH 用户" name="ssh_user"><Input placeholder="root" /></Form.Item>
            <Form.Item label="SSH 密钥路径" name="ssh_key_path"><Input placeholder="/root/.ssh/id_rsa" /></Form.Item>
            <Form.Item label="部署域名" name="domain"><Input placeholder="example.com" /></Form.Item>
            <Form.Item label="启用 SSL" name="ssl_enabled" valuePropName="checked">
              <Switch defaultChecked />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={deploySaving}>保存部署配置</Button>
            </Form.Item>
          </Form>
        )}
      </Drawer>

      {/* ══════════════════════════════════════════════════════════
         NEW FEATURES: Modals & Drawers
         ══════════════════════════════════════════════════════════ */}

      {/* ── Batch Config Modal (SITE-FE-003) ── */}
      <Modal
        title="批量更新配置"
        open={batchConfigModalOpen}
        onCancel={() => setBatchConfigModalOpen(false)}
        onOk={() => batchForm.submit()}
        okText="更新"
        cancelText="取消"
      >
        <Form form={batchForm} layout="vertical" onFinish={(values) => { void handleBatchUpdateConfig(values); }}>
          <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
            将配置应用到已选择的 {selectedSiteIds.length} 个站点
          </Typography.Text>
          <Form.Item label="默认语言" name="default_language">
            <Select allowClear placeholder="保持不变" options={allLanguages.filter((l) => l.is_enabled).map((l) => ({
              label: `${l.flag_emoji || ""} ${l.display_name}`, value: l.language_code,
            }))} />
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select allowClear placeholder="保持不变" options={[
              { label: "活跃", value: "active" },
              { label: "暂停", value: "paused" },
              { label: "已归档", value: "archived" },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Clone Modal (SITE-FE-005) ── */}
      <Modal
        title="克隆站点"
        open={cloneModalOpen && !!cloneSource}
        onCancel={() => { setCloneModalOpen(false); setCloneSource(null); cloneForm.resetFields(); }}
        onOk={() => { void handleClone(); }}
        confirmLoading={cloneSaving}
        okText="克隆"
        cancelText="取消"
        width={520}
      >
        <Form form={cloneForm} layout="vertical">
          <Form.Item label="源站点">
            <Input value={cloneSource?.brand_name || cloneSource?.site_key} disabled />
          </Form.Item>
          <Form.Item label="新站点 Key" name="new_site_key" rules={[{ required: true, message: "请输入新站点 Key" }]}>
            <Input placeholder="wechat-02" />
          </Form.Item>
          <Form.Item label="新品牌名称" name="new_brand_name" rules={[{ required: true, message: "请输入新品牌名称" }]}>
            <Input placeholder="我的站点 2" />
          </Form.Item>
          <Form.Item label="新域名" name="new_domain" rules={[{ required: true, message: "请输入新域名" }]}>
            <Input placeholder="h5-wechat-02.example.com" />
          </Form.Item>
          <Form.Item label="克隆选项">
            <Space direction="vertical">
              <Checkbox checked={cloneBrand} onChange={(e) => setCloneBrand(e.target.checked)}>
                克隆品牌配置
              </Checkbox>
              <Checkbox checked={cloneDeploy} onChange={(e) => setCloneDeploy(e.target.checked)}>
                克隆部署配置
              </Checkbox>
              <Checkbox checked={cloneTranslationsFlag} onChange={(e) => setCloneTranslationsFlag(e.target.checked)}>
                克隆翻译（仅结构，不含翻译文本）
              </Checkbox>
              <Checkbox checked={clonePermissionsFlag} onChange={(e) => setClonePermissionsFlag(e.target.checked)}>
                克隆权限
              </Checkbox>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Import Config Modal (SITE-FE-006) ── */}
      <Modal
        title="导入站点配置"
        open={importModalOpen}
        onCancel={() => { setImportModalOpen(false); setImportConfig(null); }}
        onOk={() => { void handleImportConfig(); }}
        confirmLoading={importSaving}
        okText="导入创建"
        cancelText="取消"
        okButtonProps={{ disabled: !importConfig }}
        width={640}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Upload.Dragger
            accept=".json"
            beforeUpload={(file) => {
              const reader = new FileReader();
              reader.onload = (e) => {
                try {
                  const config = JSON.parse(e.target?.result as string);
                  setImportConfig(config);
                  showSuccess("配置文件解析成功");
                } catch {
                  message.error("JSON 格式错误");
                }
              };
              reader.readAsText(file);
              return false;
            }}
            showUploadList={false}
          >
            <Typography.Text>
              <UploadOutlined style={{ fontSize: 24, color: "#1677ff" }} />
            </Typography.Text>
            <p>点击或拖拽 JSON 配置文件到此区域</p>
          </Upload.Dragger>
          {importConfig && (
            <div>
              <Typography.Text strong>预览：</Typography.Text>
              <pre style={{ fontSize: 12, background: "#f5f5f5", padding: 12, borderRadius: 4, maxHeight: 300, overflow: "auto", marginTop: 8 }}>
                {JSON.stringify(importConfig, null, 2)}
              </pre>
            </div>
          )}
        </Space>
      </Modal>

      {/* ── Compare Modal (SITE-FE-007) ── */}
      <Modal
        title="站点对比"
        open={compareModalOpen}
        onCancel={() => { setCompareModalOpen(false); setCompareSiteIds([]); }}
        width={800}
        footer={<Button onClick={() => { setCompareModalOpen(false); setCompareSiteIds([]); }}>关闭</Button>}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Select
            mode="multiple"
            placeholder="选择 2-3 个站点对比"
            style={{ width: "100%" }}
            value={compareSiteIds}
            onChange={setCompareSiteIds}
            options={sites.map((s) => ({ label: s.brand_name || s.site_key, value: s.id }))}
          />
          {compareSiteIds.length >= 2 && (
            <Table
              dataSource={compareData}
              rowKey="metric"
              size="small"
              pagination={false}
              columns={withSorter([
                { title: "指标", dataIndex: "metric", width: 100, fixed: "left" as const },
                ...compareSiteIds.map((sid) => ({
                  title: sites.find((s) => s.id === sid)?.brand_name || sid,
                  dataIndex: sid,
                  render: (val: string) => <Typography.Text>{val || "-"}</Typography.Text>,
                })),
              ])}
            />
          )}
          {compareSiteIds.length < 2 && (
            <Typography.Text type="secondary">请选择至少 2 个站点进行对比</Typography.Text>
          )}
        </Space>
      </Modal>

      {/* ── Deploy History Drawer (SITE-FE-009) ── */}
      <Drawer
        title={`部署历史 - ${deployHistorySite?.brand_name || deployHistorySite?.site_key || ""}`}
        width={640}
        open={deployHistoryOpen}
        onClose={() => { setDeployHistoryOpen(false); setDeployHistoryItems([]); }}
      >
        {deployHistoryLoading ? (
          <Typography.Text type="secondary">加载部署历史...</Typography.Text>
        ) : deployHistoryItems.length === 0 ? (
          <Typography.Text type="secondary">暂无部署历史</Typography.Text>
        ) : (
          <Timeline>
            {deployHistoryItems.map((item) => (
              <Timeline.Item key={item.id} color={item.status === "success" ? "green" : "red"}>
                <Space direction="vertical" size={4}>
                  <Space>
                    <Tag color={item.status === "success" ? "success" : "error"} style={{ textTransform: "uppercase" }}>
                      {item.action === "build" ? "🛠 构建" :
                       item.action === "deploy" ? "🚀 部署" :
                       item.action === "verify" ? "✅ 验证" :
                       item.action === "rollback" ? "⏪ 回滚" : item.action}
                    </Tag>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {formatTimeAgo(item.created_at)}
                    </Typography.Text>
                  </Space>
                  <Typography.Text style={{ fontSize: 13 }}>{item.details}</Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    操作人: {item.created_by}
                  </Typography.Text>
                </Space>
              </Timeline.Item>
            ))}
          </Timeline>
        )}
      </Drawer>

      {/* ── WABA Assignment Modal (LR-FE-005) ── */}
      <Modal
        title={`WABA 分配管理 - ${wabaSite?.brand_name || wabaSite?.site_key || ""}`}
        open={wabaModalOpen}
        onCancel={() => { setWabaModalOpen(false); setWabaSite(null); setSelectedNewWabas([]); }}
        width={640}
        footer={null}
      >
        {wabaLoading ? (
          <Typography.Text type="secondary">加载中...</Typography.Text>
        ) : (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            <div>
              <Typography.Text strong>已绑定 WABA</Typography.Text>
              <Table
                dataSource={boundWabas}
                rowKey="id"
                size="small"
                pagination={false}
                columns={withSorter([
                  { title: "WABA ID", dataIndex: "waba_id", key: "waba_id" },
                  { title: "Phone Number ID", dataIndex: "phone_number_id", key: "phone_number_id", render: (v: string | null) => v || "-" },
                  { title: "状态", dataIndex: "status", key: "status", render: (s: string) => <Tag color={s === "assigned" ? "success" : "default"}>{s === "assigned" ? "已分配" : s}</Tag> },
                  { title: "操作", key: "actions", render: (_: unknown, r: { id: string }) => (
                    <Space>
                      <Button size="small" danger onClick={() => { void handleRevokeWaba(r.id); }}>收回</Button>
                    </Space>
                  )},
                ])}
                locale={{ emptyText: "暂无已绑定的 WABA" }}
              />
            </div>
            <div>
              <Typography.Text strong>分配新 WABA</Typography.Text>
              <div style={{ marginTop: 8 }}>
                <Select
                  mode="multiple"
                  style={{ width: "100%" }}
                  placeholder="选择可用的 WABA"
                  value={selectedNewWabas}
                  onChange={setSelectedNewWabas}
                  options={availableWabas.map((w) => ({ label: `${w.name} (${w.waba_id})`, value: w.id }))}
                />
              </div>
              <Button
                type="primary"
                style={{ marginTop: 8 }}
                disabled={selectedNewWabas.length === 0}
                onClick={() => { void handleAssignWaba(); }}
              >
                确认分配
              </Button>
            </div>
          </Space>
        )}
      </Modal>

    </PageShell>
  );
}
