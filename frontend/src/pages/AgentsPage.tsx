import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Modal,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  type TableProps,
} from "antd";
import { withSorter } from "../utils/withSorter";
import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";

import { DangerButton, showError, showSuccess } from "../components/Feedback";
import { AgencyMembersPanel } from "../components/agents/AgencyMembersPanel";
import { AgencyPermissionGrantsPanel } from "../components/agents/AgencyPermissionGrantsPanel";
import { AgencyRolesPanel } from "../components/agents/AgencyRolesPanel";
import { PageShell } from "../components/PageShell";
import {
  cancelAgencyBilling,
  checkAgentUsername,
  createAgencyBilling,
  createAgent,
  getAgencyBillingDetail,
  listAgencyBilling,
  listAgents,
  resetAgentPassword,
  restoreAgent,
  updateAgencyBilling,
  updateAgent,
  updateAgentStatus,
  type Agent,
  type AgentBilling,
  type AgentBillingLineItem,
  type AgentBillingListParams,
  type AgentCreatePayload,
} from "../services/api";
import { listAgencyRoleSummaries, type AgencyRoleSummary } from "../services/permissions";

type WorkbenchTabKey = "overview" | "permissions" | "roles" | "members" | "edit" | "billing";

type WorkbenchLocationState = {
  agencyId: string | null;
  tab: WorkbenchTabKey;
  role: string | null;
  member: string | null;
};

type AgentEditFormValues = {
  name: string;
  brand_name?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
};

type ResetPasswordFormValues = {
  password: string;
};

type BillingFilterDraft = {
  status: string;
  billing_type: string;
  period_start: string;
  period_end: string;
};

type BillingEditorFormValues = {
  billing_type: string;
  amount: number | string;
  billing_period_start?: string;
  billing_period_end?: string;
  line_items: AgentBillingLineItem[];
};

type BillingEditorMode = "idle" | "create" | "detail";

const PAGE_TITLE = "代理商管理";
const PAGE_SUBTITLE = "代理、权限池、角色与成员统一管理";
const PAGE_BREADCRUMB = "人员管理 / 代理商管理";

const AGENT_STATUS_SORT_ORDER: Record<string, number> = {
  active: 0,
  suspended: 1,
  archived: 9,
};

const AGENT_STATUS_LABELS: Record<string, string> = {
  active: "启用",
  suspended: "停用",
  archived: "归档",
};

const BILLING_TYPE_LABELS: Record<string, string> = {
  monthly: "月账单",
  subscription: "订阅账单",
  usage: "用量账单",
};

const BILLING_STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: "草稿", color: "default" },
  pending: { label: "待确认", color: "warning" },
  paid: { label: "已支付", color: "processing" },
  verified: { label: "已核销", color: "success" },
  cancelled: { label: "已作废", color: "default" },
};

const WORKBENCH_TAB_ITEMS: Array<{ key: WorkbenchTabKey; label: string }> = [
  { key: "overview", label: "概览" },
  { key: "permissions", label: "权限池" },
  { key: "roles", label: "角色" },
  { key: "members", label: "成员" },
  { key: "edit", label: "编辑" },
  { key: "billing", label: "账单" },
];

const EMPTY_BILLING_FILTER_DRAFT: BillingFilterDraft = {
  status: "",
  billing_type: "",
  period_start: "",
  period_end: "",
};

const EMPTY_LINE_ITEM: AgentBillingLineItem = {
  description: "",
  quantity: 1,
  unit_price: 0,
};

function normalizeWorkbenchTab(rawTab: string | null): WorkbenchTabKey {
  if (
    rawTab === "permissions" ||
    rawTab === "roles" ||
    rawTab === "members" ||
    rawTab === "edit" ||
    rawTab === "billing"
  ) {
    return rawTab;
  }
  return "overview";
}

function readWorkbenchLocation(search: string = window.location.search): WorkbenchLocationState {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  return {
    agencyId: params.get("agencyId"),
    tab: normalizeWorkbenchTab(params.get("tab")),
    role: params.get("role"),
    member: params.get("member"),
  };
}

function buildWorkbenchLocation(state: WorkbenchLocationState): string {
  const params = new URLSearchParams();
  if (state.agencyId) {
    params.set("agencyId", state.agencyId);
  }
  if (state.tab !== "overview" || state.agencyId) {
    params.set("tab", state.tab);
  }
  if (state.tab === "roles" && state.role) {
    params.set("role", state.role);
  }
  if (state.tab === "members" && state.member) {
    params.set("member", state.member);
  }
  const query = params.toString();
  return query ? `/system/agents?${query}` : "/system/agents";
}

function syncWorkbenchLocation(state: WorkbenchLocationState): void {
  const nextLocation = buildWorkbenchLocation(state);
  const currentLocation = `${window.location.pathname}${window.location.search}`;
  if (nextLocation !== currentLocation) {
    window.history.replaceState({}, "", nextLocation);
  }
}

function pushWorkbenchLocation(state: WorkbenchLocationState): void {
  const nextLocation = buildWorkbenchLocation(state);
  const currentLocation = `${window.location.pathname}${window.location.search}`;
  if (nextLocation !== currentLocation) {
    window.history.pushState({}, "", nextLocation);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("zh-CN");
}

function formatCurrency(amount: number): string {
  return `¥${amount.toFixed(2)}`;
}

function getAgentStatusLabel(status: string): string {
  return AGENT_STATUS_LABELS[status] ?? status;
}

function getAgentStatusTag(status: string): JSX.Element {
  const color = status === "active" ? "success" : status === "suspended" ? "warning" : "default";
  return <Tag color={color}>{getAgentStatusLabel(status)}</Tag>;
}

function getBillingStatusTag(status: string): JSX.Element {
  const config = BILLING_STATUS_MAP[status];
  return <Tag color={config?.color ?? "default"}>{config?.label ?? status}</Tag>;
}

function getBillingTypeLabel(type: string): string {
  return BILLING_TYPE_LABELS[type] ?? type;
}

function normalizeLineItems(items?: AgentBillingLineItem[] | null): AgentBillingLineItem[] {
  if (!Array.isArray(items) || items.length === 0) {
    return [];
  }
  return items.map((item) => ({
    description: item.description ?? "",
    quantity: Number(item.quantity ?? 1),
    unit_price: Number(item.unit_price ?? 0),
  }));
}

function buildRoleOptions(roles: AgencyRoleSummary[]): Array<{ label: string; value: string }> {
  return roles.map((role) => ({
    label: role.name,
    value: role.role_key,
  }));
}

function buildBillingFormValues(bill: AgentBilling | null = null): BillingEditorFormValues {
  const lineItems = normalizeLineItems(bill?.line_items);
  return {
    billing_type: bill?.billing_type ?? "monthly",
    amount: bill?.amount ?? "",
    billing_period_start: bill?.billing_period_start ?? "",
    billing_period_end: bill?.billing_period_end ?? "",
    line_items: lineItems.length > 0 ? lineItems : [{ ...EMPTY_LINE_ITEM }],
  };
}

function buildBillingPayload(values: BillingEditorFormValues): {
  billing_type: string;
  amount: number;
  billing_period_start?: string;
  billing_period_end?: string;
  line_items: AgentBillingLineItem[];
} {
  return {
    billing_type: values.billing_type,
    amount: Number(values.amount),
    billing_period_start: values.billing_period_start || undefined,
    billing_period_end: values.billing_period_end || undefined,
    line_items: normalizeLineItems(values.line_items).filter(
      (item) => item.description.trim().length > 0 || Number(item.quantity) > 0 || Number(item.unit_price) > 0,
    ),
  };
}

function getBillingFiltersFromDraft(draft: BillingFilterDraft): AgentBillingListParams {
  return {
    status: draft.status || undefined,
    billing_type: draft.billing_type || undefined,
    period_start: draft.period_start || undefined,
    period_end: draft.period_end || undefined,
  };
}

function getBillingTransitionActions(status: string): Array<{ key: string; label: string; nextStatus: string }> {
  if (status === "draft") {
    return [{ key: "submit", label: "提交账单", nextStatus: "pending" }];
  }
  if (status === "pending") {
    return [{ key: "mark-paid", label: "标记已支付", nextStatus: "paid" }];
  }
  if (status === "paid") {
    return [{ key: "verify", label: "核销完成", nextStatus: "verified" }];
  }
  return [];
}

function canCancelBilling(status: string): boolean {
  return status === "draft" || status === "pending";
}

function canEditBilling(status: string): boolean {
  return status === "draft" || status === "pending";
}

function getBillingStatusGuide(mode: BillingEditorMode, status: string): { type: "info" | "warning"; message: string; description: string } {
  if (mode === "create") {
    return {
      type: "info",
      message: "当前为新建草稿",
      description: "先补全账单类型、金额与 line_items，再保存草稿或继续流转。",
    };
  }
  if (canEditBilling(status)) {
    return {
      type: "info",
      message: "当前状态允许编辑",
      description: "可以继续修改账单字段和 line_items；保存后再按状态流推进。",
    };
  }
  return {
    type: "warning",
    message: "当前账单已进入只读状态",
    description: "已支付、已核销和已作废账单只允许查看，不再支持编辑或作废。",
  };
}

function getBreadcrumbText(selectedAgent: Agent | null, activeTab: WorkbenchTabKey): string {
  if (!selectedAgent) {
    return PAGE_BREADCRUMB;
  }

  const suffix =
    activeTab === "permissions"
      ? " / 权限池"
      : activeTab === "roles"
        ? " / 角色"
        : activeTab === "members"
          ? " / 成员"
          : activeTab === "edit"
            ? " / 编辑"
            : activeTab === "billing"
              ? " / 账单"
              : "";

  return `${PAGE_BREADCRUMB} / ${selectedAgent.name}${suffix}`;
}

export function AgentsPage(): JSX.Element {
  const initialLocation = readWorkbenchLocation();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchValue, setSearchValue] = useState("");
  const [selectedAgencyId, setSelectedAgencyId] = useState<string | null>(initialLocation.agencyId);
  const [activeTab, setActiveTab] = useState<WorkbenchTabKey>(initialLocation.tab);
  const [selectedRoleKey, setSelectedRoleKey] = useState<string | null>(initialLocation.role);
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(initialLocation.member);
  const [roleSummaries, setRoleSummaries] = useState<AgencyRoleSummary[]>([]);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm] = Form.useForm<AgentCreatePayload>();
  const [editForm] = Form.useForm<AgentEditFormValues>();
  const [savingEdit, setSavingEdit] = useState(false);
  const [resetPasswordForm] = Form.useForm<ResetPasswordFormValues>();
  const [resettingPassword, setResettingPassword] = useState(false);

  const [bills, setBills] = useState<AgentBilling[]>([]);
  const [billsLoading, setBillsLoading] = useState(false);
  const [billingFilters, setBillingFilters] = useState<AgentBillingListParams>({});
  const [billingFilterDraft, setBillingFilterDraft] = useState<BillingFilterDraft>(EMPTY_BILLING_FILTER_DRAFT);
  const [billingMode, setBillingMode] = useState<BillingEditorMode>("idle");
  const [selectedBillId, setSelectedBillId] = useState<string | null>(null);
  const [selectedBill, setSelectedBill] = useState<AgentBilling | null>(null);
  const [billingDetailLoading, setBillingDetailLoading] = useState(false);
  const [billingSaving, setBillingSaving] = useState(false);
  const [billingActionLoading, setBillingActionLoading] = useState<string | null>(null);
  const [billingForm] = Form.useForm<BillingEditorFormValues>();

  const applyLocationFromBrowser = useCallback(() => {
    const nextLocation = readWorkbenchLocation();
    setSelectedAgencyId(nextLocation.agencyId);
    setActiveTab(nextLocation.tab);
    setSelectedRoleKey(nextLocation.role);
    setSelectedMemberId(nextLocation.member);
  }, []);

  const resetBillingWorkspace = useCallback(() => {
    setBills([]);
    setBillsLoading(false);
    setBillingFilters({});
    setBillingFilterDraft(EMPTY_BILLING_FILTER_DRAFT);
    setBillingMode("idle");
    setSelectedBillId(null);
    setSelectedBill(null);
    setBillingDetailLoading(false);
    setBillingSaving(false);
    setBillingActionLoading(null);
    billingForm.setFieldsValue(buildBillingFormValues(null));
  }, [billingForm]);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      setAgents(await listAgents());
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "加载代理列表失败");
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadBillDetail = useCallback(
    async (agencyId: string, billId: string) => {
      setBillingDetailLoading(true);
      try {
        const detail = await getAgencyBillingDetail(agencyId, billId);
        setSelectedBillId(billId);
        setSelectedBill(detail);
        setBillingMode("detail");
        billingForm.setFieldsValue(buildBillingFormValues(detail));
      } catch (cause) {
        showError(cause instanceof Error ? cause.message : "加载账单详情失败");
      } finally {
        setBillingDetailLoading(false);
      }
    },
    [billingForm],
  );

  const loadBills = useCallback(
    async (agencyId: string, nextFilters: AgentBillingListParams = {}): Promise<AgentBilling[]> => {
      setBillsLoading(true);
      try {
        const nextBills = await listAgencyBilling(agencyId, nextFilters);
        setBills(nextBills);
        if (selectedBillId && !nextBills.some((bill) => bill.id === selectedBillId)) {
          setSelectedBillId(null);
          setSelectedBill(null);
          if (billingMode === "detail") {
            setBillingMode("idle");
            billingForm.setFieldsValue(buildBillingFormValues(null));
          }
        }
        return nextBills;
      } catch (cause) {
        showError(cause instanceof Error ? cause.message : "加载账单失败");
        setBills([]);
        return [];
      } finally {
        setBillsLoading(false);
      }
    },
    [billingForm, billingMode, selectedBillId],
  );

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  useEffect(() => {
    window.addEventListener("popstate", applyLocationFromBrowser);
    return () => window.removeEventListener("popstate", applyLocationFromBrowser);
  }, [applyLocationFromBrowser]);

  useEffect(() => {
    setRoleSummaries([]);
  }, [selectedAgencyId]);

  useEffect(() => {
    syncWorkbenchLocation({
      agencyId: selectedAgencyId,
      tab: activeTab,
      role: selectedRoleKey,
      member: selectedMemberId,
    });
  }, [activeTab, selectedAgencyId, selectedMemberId, selectedRoleKey]);

  const filteredAgents = useMemo(() => {
    const keyword = searchValue.trim().toLowerCase();
    const matchedAgents = !keyword
      ? agents
      : agents.filter((agent) =>
          [agent.name, agent.username, agent.brand_name].filter(Boolean).some((value) => value?.toLowerCase().includes(keyword)),
        );

    return matchedAgents
      .map((agent, index) => ({ agent, index }))
      .sort((left, right) => {
        const leftOrder = AGENT_STATUS_SORT_ORDER[left.agent.status] ?? 5;
        const rightOrder = AGENT_STATUS_SORT_ORDER[right.agent.status] ?? 5;
        if (leftOrder !== rightOrder) {
          return leftOrder - rightOrder;
        }
        return left.index - right.index;
      })
      .map(({ agent }) => agent);
  }, [agents, searchValue]);

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedAgencyId) ?? null,
    [agents, selectedAgencyId],
  );

  const totalMembers = useMemo(() => agents.reduce((sum, agent) => sum + (agent.member_count ?? 0), 0), [agents]);
  const totalRoles = useMemo(() => agents.reduce((sum, agent) => sum + (agent.role_count ?? 0), 0), [agents]);
  const totalGrantedPermissions = useMemo(
    () => agents.reduce((sum, agent) => sum + (agent.granted_permission_count ?? 0), 0),
    [agents],
  );
  const permissionPoolEmpty = (selectedAgent?.granted_permission_count ?? 0) === 0;
  const roleOptions = useMemo(() => buildRoleOptions(roleSummaries), [roleSummaries]);

  const loadRoleSummaries = useCallback(async (agencyId: string): Promise<AgencyRoleSummary[]> => {
    try {
      const roles = await listAgencyRoleSummaries(agencyId);
      setRoleSummaries(roles);
      return roles;
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "加载代理角色失败");
      setRoleSummaries([]);
      return [];
    }
  }, []);

  useEffect(() => {
    if (!selectedAgent) {
      editForm.resetFields();
      resetPasswordForm.resetFields();
      return;
    }

    editForm.setFieldsValue({
      name: selectedAgent.name,
      brand_name: selectedAgent.brand_name ?? "",
      contact_name: selectedAgent.contact_name ?? "",
      contact_phone: selectedAgent.contact_phone ?? "",
      contact_email: selectedAgent.contact_email ?? "",
    });
    resetPasswordForm.resetFields();
  }, [editForm, resetPasswordForm, selectedAgent]);

  useEffect(() => {
    if (activeTab === "billing" && selectedAgent) {
      void loadBills(selectedAgent.id, billingFilters);
    }
  }, [activeTab, billingFilters, loadBills, selectedAgent]);

  useEffect(() => {
    if (!selectedAgent) return;
    if (activeTab !== "roles" && activeTab !== "members") return;
    if (activeTab === "members" && permissionPoolEmpty) return;
    void loadRoleSummaries(selectedAgent.id);
  }, [activeTab, loadRoleSummaries, permissionPoolEmpty, selectedAgent]);

  useEffect(() => {
    if (activeTab !== "billing") {
      resetBillingWorkspace();
    }
  }, [activeTab, resetBillingWorkspace]);

  const selectAgency = useCallback(
    (agencyId: string, tab: WorkbenchTabKey = "overview") => {
      const nextState: WorkbenchLocationState = {
        agencyId,
        tab,
        role: tab === "roles" ? selectedRoleKey : null,
        member: tab === "members" ? selectedMemberId : null,
      };

      if (tab !== "roles") {
        setSelectedRoleKey(null);
        nextState.role = null;
      }
      if (tab !== "members") {
        setSelectedMemberId(null);
        nextState.member = null;
      }

      setSelectedAgencyId(agencyId);
      setActiveTab(tab);
      pushWorkbenchLocation(nextState);
    },
    [selectedMemberId, selectedRoleKey],
  );

  const handleTabChange = useCallback(
    (key: string) => {
      if (!selectedAgent) return;

      const nextTab = key as WorkbenchTabKey;
      const nextState: WorkbenchLocationState = {
        agencyId: selectedAgent.id,
        tab: nextTab,
        role: nextTab === "roles" ? selectedRoleKey : null,
        member: nextTab === "members" ? selectedMemberId : null,
      };

      setActiveTab(nextTab);
      if (nextTab !== "roles") {
        setSelectedRoleKey(null);
        nextState.role = null;
      }
      if (nextTab !== "members") {
        setSelectedMemberId(null);
        nextState.member = null;
      }

      pushWorkbenchLocation(nextState);
    },
    [selectedAgent, selectedMemberId, selectedRoleKey],
  );

  const handleCreateAgent = useCallback(
    async (values: AgentCreatePayload) => {
      setCreating(true);
      try {
        await createAgent(values);
        showSuccess("代理商已创建");
        setCreateModalOpen(false);
        createForm.resetFields();
        await loadAgents();
      } catch (cause) {
        showError(cause instanceof Error ? cause.message : "创建代理商失败");
      } finally {
        setCreating(false);
      }
    },
    [createForm, loadAgents],
  );

  const handleSaveEdit = useCallback(
    async (values: AgentEditFormValues) => {
      if (!selectedAgent) return;

      setSavingEdit(true);
      try {
        await updateAgent(selectedAgent.id, values);
        showSuccess("代理商信息已更新");
        await loadAgents();
      } catch (cause) {
        showError(cause instanceof Error ? cause.message : "保存代理商信息失败");
      } finally {
        setSavingEdit(false);
      }
    },
    [loadAgents, selectedAgent],
  );

  const handleResetPassword = useCallback(
    async (values: ResetPasswordFormValues) => {
      if (!selectedAgent) return;

      setResettingPassword(true);
      try {
        await resetAgentPassword(selectedAgent.id, values.password);
        showSuccess("密码已重置");
        resetPasswordForm.resetFields();
      } catch (cause) {
        showError(cause instanceof Error ? cause.message : "重置密码失败");
      } finally {
        setResettingPassword(false);
      }
    },
    [resetPasswordForm, selectedAgent],
  );

  const handleArchive = useCallback(
    (agent: Agent) => {
      Modal.confirm({
        title: "确认归档",
        content: `归档后，代理商 ${agent.name} 及其成员将无法继续登录后台。确认归档吗？`,
        okText: "确认",
        cancelText: "取消",
        onOk: async () => {
          try {
            await updateAgentStatus(agent.id, "archived");
            showSuccess("代理商已归档");
            await loadAgents();
          } catch (cause) {
            showError(cause instanceof Error ? cause.message : "归档代理商失败");
          }
        },
      });
    },
    [loadAgents],
  );

  const handleSuspend = useCallback(
    (agent: Agent) => {
      Modal.confirm({
        title: "确认停用",
        content: `停用后，代理商 ${agent.name} 将无法继续登录后台。确认停用吗？`,
        okText: "确认",
        cancelText: "取消",
        onOk: async () => {
          try {
            await updateAgentStatus(agent.id, "suspended");
            showSuccess("代理商已停用");
            await loadAgents();
          } catch (cause) {
            showError(cause instanceof Error ? cause.message : "停用代理商失败");
          }
        },
      });
    },
    [loadAgents],
  );

  const handleRestore = useCallback(
    (agent: Agent) => {
      Modal.confirm({
        title: "确认恢复",
        content: `确认恢复代理商 ${agent.name} 吗？`,
        okText: "确认",
        cancelText: "取消",
        onOk: async () => {
          try {
            await restoreAgent(agent.id);
            showSuccess("代理商已恢复");
            await loadAgents();
          } catch (cause) {
            showError(cause instanceof Error ? cause.message : "恢复代理商失败");
          }
        },
      });
    },
    [loadAgents],
  );

  const handleApplyBillingFilters = useCallback(async () => {
    if (!selectedAgent) return;
    const nextFilters = getBillingFiltersFromDraft(billingFilterDraft);
    setBillingFilters(nextFilters);
    await loadBills(selectedAgent.id, nextFilters);
  }, [billingFilterDraft, loadBills, selectedAgent]);

  const handleResetBillingFilters = useCallback(async () => {
    if (!selectedAgent) return;
    setBillingFilterDraft(EMPTY_BILLING_FILTER_DRAFT);
    setBillingFilters({});
    await loadBills(selectedAgent.id, {});
  }, [loadBills, selectedAgent]);

  const handleSelectBill = useCallback(
    async (bill: AgentBilling) => {
      if (!selectedAgent) return;
      await loadBillDetail(selectedAgent.id, bill.id);
    },
    [loadBillDetail, selectedAgent],
  );

  const handleNewBill = useCallback(() => {
    setBillingMode("create");
    setSelectedBillId(null);
    setSelectedBill(null);
    billingForm.setFieldsValue(buildBillingFormValues(null));
  }, [billingForm]);

  const handleRemoveLineItem = useCallback(
    (index: number, remove: (index: number) => void) => {
      const currentItems = normalizeLineItems(billingForm.getFieldValue("line_items"));
      if (currentItems.length <= 1) {
        billingForm.setFieldsValue({ line_items: [{ ...EMPTY_LINE_ITEM }]});
        return;
      }
      remove(index);
    },
    [billingForm],
  );

  const handleSaveBill = useCallback(async () => {
    if (!selectedAgent) return;
    setBillingSaving(true);
    try {
      const values = await billingForm.validateFields();
      const payload = buildBillingPayload(values);

      if (billingMode === "create") {
        const created = await createAgencyBilling(selectedAgent.id, payload);
        showSuccess("账单已创建");
        const nextBills = await loadBills(selectedAgent.id, billingFilters);
        if (nextBills.some((bill) => bill.id === created.id)) {
          await loadBillDetail(selectedAgent.id, created.id);
        } else {
          setBillingMode("idle");
          setSelectedBillId(null);
          setSelectedBill(null);
          billingForm.setFieldsValue(buildBillingFormValues(null));
        }
      } else if (selectedBillId) {
        await updateAgencyBilling(selectedAgent.id, selectedBillId, payload);
        showSuccess("账单已更新");
        const nextBills = await loadBills(selectedAgent.id, billingFilters);
        if (nextBills.some((bill) => bill.id === selectedBillId)) {
          await loadBillDetail(selectedAgent.id, selectedBillId);
        }
      }
    } catch (cause) {
      if (cause instanceof Error) {
        showError(cause.message);
      }
    } finally {
      setBillingSaving(false);
    }
  }, [billingFilters, billingForm, billingMode, loadBillDetail, loadBills, selectedAgent, selectedBillId]);

  const handleBillingTransition = useCallback(
    async (nextStatus: string) => {
      if (!selectedAgent || !selectedBillId) return;
      setBillingActionLoading(nextStatus);
      try {
        await updateAgencyBilling(selectedAgent.id, selectedBillId, { status: nextStatus });
        showSuccess("账单状态已更新");
        const nextBills = await loadBills(selectedAgent.id, billingFilters);
        if (nextBills.some((bill) => bill.id === selectedBillId)) {
          await loadBillDetail(selectedAgent.id, selectedBillId);
        }
      } catch (cause) {
        showError(cause instanceof Error ? cause.message : "更新账单状态失败");
      } finally {
        setBillingActionLoading(null);
      }
    },
    [billingFilters, loadBillDetail, loadBills, selectedAgent, selectedBillId],
  );

  const handleCancelBill = useCallback(async () => {
    if (!selectedAgent || !selectedBillId) return;
    setBillingActionLoading("cancelled");
    try {
      await cancelAgencyBilling(selectedAgent.id, selectedBillId);
      showSuccess("账单已作废");
      const nextBills = await loadBills(selectedAgent.id, billingFilters);
      if (nextBills.some((bill) => bill.id === selectedBillId)) {
        await loadBillDetail(selectedAgent.id, selectedBillId);
      }
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "作废账单失败");
    } finally {
      setBillingActionLoading(null);
    }
  }, [billingFilters, loadBillDetail, loadBills, selectedAgent, selectedBillId]);

  const billingColumns = useMemo<TableProps<AgentBilling>["columns"]>(
    () => [
      {
        title: "账单类型",
        dataIndex: "billing_type",
        key: "billing_type",
        render: (value: string) => getBillingTypeLabel(value),
      },
      {
        title: "金额",
        dataIndex: "amount",
        key: "amount",
        width: 120,
        render: (value: number) => formatCurrency(value),
      },
      {
        title: "周期开始",
        dataIndex: "billing_period_start",
        key: "billing_period_start",
        width: 140,
        render: (value: string | null) => formatDate(value),
      },
      {
        title: "周期结束",
        dataIndex: "billing_period_end",
        key: "billing_period_end",
        width: 140,
        render: (value: string | null) => formatDate(value),
      },
      {
        title: "状态",
        dataIndex: "status",
        key: "status",
        width: 120,
        render: (value: string) => getBillingStatusTag(value),
      },
      {
        title: "明细",
        key: "line_items",
        width: 120,
        render: (_: unknown, bill: AgentBilling) => `${normalizeLineItems(bill.line_items).length} 项明细`,
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        key: "created_at",
        width: 180,
        render: (value: string | null) => formatDateTime(value),
      },
    ],
    [],
  );

  const selectedAgentTitle = selectedAgent?.name ?? PAGE_TITLE;
  const selectedAgentSubtitle = selectedAgent
    ? `登录名 ${selectedAgent.username || "-"} · 品牌 ${selectedAgent.brand_name || "-"} · 状态 ${getAgentStatusLabel(selectedAgent.status)}`
    : PAGE_SUBTITLE;
  const breadcrumbText = getBreadcrumbText(selectedAgent, activeTab);

  const renderOverview = (): JSX.Element => {
    if (!selectedAgent) {
      return (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <Card>
            <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 8 }}>
              代理总览
            </Typography.Title>
            <Typography.Text type="secondary">
              请选择左侧代理商，进入权限池、角色、成员、编辑和账单工作区。
            </Typography.Text>
          </Card>
          <Space size={16} wrap>
            <Card>
              <Statistic title="代理数量" value={agents.length} />
            </Card>
            <Card>
              <Statistic title="成员数量" value={totalMembers} />
            </Card>
            <Card>
              <Statistic title="角色数量" value={totalRoles} />
            </Card>
            <Card>
              <Statistic title="授权总量" value={totalGrantedPermissions} />
            </Card>
          </Space>
          <Card title="治理顺序">
            <Typography.Paragraph style={{ marginBottom: 0 }}>
              先配置权限池，再配置角色，最后给成员绑定角色。成员不能直接绑定权限。
            </Typography.Paragraph>
          </Card>
        </Space>
      );
    }

    return (
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Card>
          <Descriptions column={2} size="small" title="代理信息">
            <Descriptions.Item label="代理名称">{selectedAgent.name}</Descriptions.Item>
            <Descriptions.Item label="登录名">{selectedAgent.username || "-"}</Descriptions.Item>
            <Descriptions.Item label="品牌">{selectedAgent.brand_name || "-"}</Descriptions.Item>
            <Descriptions.Item label="状态">{getAgentStatusTag(selectedAgent.status)}</Descriptions.Item>
            <Descriptions.Item label="成员数">{selectedAgent.member_count ?? 0}</Descriptions.Item>
            <Descriptions.Item label="角色数">{selectedAgent.role_count ?? 0}</Descriptions.Item>
            <Descriptions.Item label="权限池规模">{selectedAgent.granted_permission_count ?? 0}</Descriptions.Item>
            <Descriptions.Item label="最近更新时间">{formatDateTime(selectedAgent.updated_at)}</Descriptions.Item>
          </Descriptions>
        </Card>
        <Card title="快捷操作">
          <Space wrap>
            <Button type="primary" onClick={() => selectAgency(selectedAgent.id, "permissions")}>
              配置权限池
            </Button>
            <Button onClick={() => selectAgency(selectedAgent.id, "roles")}>管理角色</Button>
            <Button onClick={() => selectAgency(selectedAgent.id, "members")}>管理成员</Button>
            <Button onClick={() => selectAgency(selectedAgent.id, "edit")}>编辑资料</Button>
            <Button onClick={() => selectAgency(selectedAgent.id, "billing")}>查看账单</Button>
          </Space>
        </Card>
        <Space size={16} wrap>
          <Card>
            <Statistic title="成员数量" value={selectedAgent.member_count ?? 0} />
          </Card>
          <Card>
            <Statistic title="角色数量" value={selectedAgent.role_count ?? 0} />
          </Card>
          <Card>
            <Statistic title="权限池规模" value={selectedAgent.granted_permission_count ?? 0} />
          </Card>
        </Space>
        <Alert
          type="info"
          showIcon
          message="治理顺序"
          description="请按“权限池 → 角色 → 成员”的顺序配置，代理只能把超管授予的权限继续下放给角色。"
        />
      </Space>
    );
  };

  const renderRoles = (): JSX.Element => {
    if (!selectedAgent) return renderOverview();

    return (
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {permissionPoolEmpty ? (
          <Alert
            type="warning"
            showIcon
            message="当前权限池为空"
            description="请先配置该代理商的权限池，再继续配置角色权限。"
          />
        ) : null}
        <AgencyRolesPanel
          agencyId={selectedAgent.id}
          initialRoleKey={selectedRoleKey}
          onSelectedRoleChange={setSelectedRoleKey}
          onRolesChanged={setRoleSummaries}
          permissionEditingDisabled={permissionPoolEmpty}
        />
      </Space>
    );
  };

  const renderMembers = (): JSX.Element => {
    if (!selectedAgent) return renderOverview();

    return (
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {permissionPoolEmpty ? (
          <Alert
            type="warning"
            showIcon
            message="请先配置权限池和角色"
            description="成员只能绑定角色，角色权限来自代理权限池。"
          />
        ) : null}
        <AgencyMembersPanel
          agencyId={selectedAgent.id}
          roleOptions={roleOptions}
          initialMemberId={selectedMemberId}
          onSelectedMemberChange={setSelectedMemberId}
          roleAssignmentDisabled={permissionPoolEmpty}
          onRoleCenter={(roleName) => {
            setSelectedRoleKey(roleName);
            setActiveTab("roles");
            pushWorkbenchLocation({
              agencyId: selectedAgent.id,
              tab: "roles",
              role: roleName,
              member: null,
            });
          }}
        />
      </Space>
    );
  };

  const renderEdit = (): JSX.Element => {
    if (!selectedAgent) return renderOverview();

    return (
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="编辑工作台"
          description="资料、密码与状态操作统一在这里处理。成员、角色和权限池请分别在对应 Tab 内维护。"
        />
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.15fr) minmax(320px, 0.85fr)", gap: 16 }}>
          <Card title="编辑代理信息">
            <Form form={editForm} layout="vertical" onFinish={(values) => void handleSaveEdit(values)}>
              <Form.Item label="代理名称" name="name" rules={[{ required: true, message: "请输入代理名称" }]}>
                <Input placeholder="例如：上海锦囊" />
              </Form.Item>
              <Form.Item label="品牌名称" name="brand_name">
                <Input placeholder="例如：锦囊品牌" />
              </Form.Item>
              <Form.Item label="联系人" name="contact_name">
                <Input placeholder="姓名" />
              </Form.Item>
              <Form.Item label="联系电话" name="contact_phone">
                <Input placeholder="手机号" />
              </Form.Item>
              <Form.Item label="联系邮箱" name="contact_email">
                <Input placeholder="email@example.com" />
              </Form.Item>
              <Button type="primary" loading={savingEdit} onClick={() => editForm.submit()}>
                保存代理信息
              </Button>
            </Form>
          </Card>

          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card title="当前账号">
              <Descriptions size="small" column={1}>
                <Descriptions.Item label="登录名">{selectedAgent.username || "-"}</Descriptions.Item>
                <Descriptions.Item label="品牌名称">{selectedAgent.brand_name || "-"}</Descriptions.Item>
                <Descriptions.Item label="当前状态">{getAgentStatusTag(selectedAgent.status)}</Descriptions.Item>
                <Descriptions.Item label="成员数量">{selectedAgent.member_count ?? 0}</Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title="重置密码">
              <Form form={resetPasswordForm} layout="vertical" onFinish={(values) => void handleResetPassword(values)}>
                <Form.Item
                  label="新密码"
                  name="password"
                  rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}
                >
                  <Input.Password placeholder="请输入新密码" />
                </Form.Item>
                <Button type="primary" loading={resettingPassword} onClick={() => resetPasswordForm.submit()}>
                  重置密码
                </Button>
              </Form>
            </Card>

            <Card title="状态操作">
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Typography.Text type="secondary">
                  停用会阻止该代理及其成员继续登录；归档用于彻底下线该代理主体。
                </Typography.Text>
                <Space wrap>
                  {selectedAgent.status === "active" ? (
                    <Button onClick={() => handleSuspend(selectedAgent)}>停用代理商</Button>
                  ) : (
                    <Button onClick={() => handleRestore(selectedAgent)}>恢复代理商</Button>
                  )}
                  <DangerButton
                    label="归档代理商"
                    type="default"
                    confirmTitle="确认归档该代理商？"
                    confirmDescription="归档后该代理商及其成员将无法继续登录后台。"
                    onConfirm={async () => handleArchive(selectedAgent)}
                  />
                </Space>
              </Space>
            </Card>
          </Space>
        </div>
      </Space>
    );
  };

  const renderBillingEditor = (): JSX.Element => {
    const currentStatus = selectedBill?.status ?? "draft";
    const transitionActions = billingMode === "detail" ? getBillingTransitionActions(currentStatus) : [];
    const canEditCurrentBill = billingMode === "create" || canEditBilling(currentStatus);
    const statusGuide = getBillingStatusGuide(billingMode, currentStatus);

    return (
      <Card
        title="账单详情"
        extra={(
          <Space wrap>
            <Button onClick={handleNewBill}>切换新建</Button>
            {selectedAgent ? (
              <Button onClick={() => void loadBills(selectedAgent.id, billingFilters)} loading={billsLoading}>
                刷新列表
              </Button>
            ) : null}
          </Space>
        )}
      >
        {billingMode === "idle" ? (
          <Empty description={bills.length === 0 ? "当前暂无账单，可在左侧新建账单。" : "从左侧选择一张账单查看或编辑明细。"} />
        ) : (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Alert type={statusGuide.type} showIcon message={statusGuide.message} description={statusGuide.description} />
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="当前状态">
                {billingMode === "create" ? getBillingStatusTag("draft") : getBillingStatusTag(currentStatus)}
              </Descriptions.Item>
              <Descriptions.Item label="账单编号">{selectedBill?.id ?? "新建中"}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDateTime(selectedBill?.created_at)}</Descriptions.Item>
              <Descriptions.Item label="代理作用域">{selectedAgent?.name ?? "-"}</Descriptions.Item>
            </Descriptions>

            <Form form={billingForm} layout="vertical" initialValues={buildBillingFormValues(null)}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                <Form.Item
                  label="账单类型"
                  name="billing_type"
                  rules={[{ required: true, message: "请选择账单类型" }]}
                >
                  <select
                    aria-label="账单类型"
                    disabled={!canEditCurrentBill}
                    style={{ width: "100%", minHeight: 32 }}
                  >
                    <option value="monthly">月账单</option>
                    <option value="subscription">订阅账单</option>
                    <option value="usage">用量账单</option>
                  </select>
                </Form.Item>
                <Form.Item
                  label="账单金额"
                  name="amount"
                  rules={[{ required: true, message: "请输入账单金额" }]}
                >
                  <Input
                    aria-label="账单金额"
                    type="number"
                    disabled={!canEditCurrentBill}
                    placeholder="请输入金额"
                  />
                </Form.Item>
                <Form.Item label="账期开始" name="billing_period_start">
                  <Input
                    aria-label="账期开始"
                    type="date"
                    disabled={!canEditCurrentBill}
                  />
                </Form.Item>
                <Form.Item label="账期结束" name="billing_period_end">
                  <Input
                    aria-label="账期结束"
                    type="date"
                    disabled={!canEditCurrentBill}
                  />
                </Form.Item>
              </div>

              <Form.List name="line_items">
                {(fields, { add, remove }) => (
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Space style={{ justifyContent: "space-between", width: "100%" }}>
                      <Typography.Text strong>账单明细</Typography.Text>
                      <Button
                        onClick={() => add({ ...EMPTY_LINE_ITEM })}
                        disabled={!canEditCurrentBill}
                      >
                        新增明细
                      </Button>
                    </Space>
                    {fields.map((field) => (
                      <Card key={field.key} size="small">
                        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 12 }}>
                          <Form.Item
                            label="说明"
                            name={[field.name, "description"]}
                            style={{ marginBottom: 0 }}
                            rules={[{ required: true, message: "请输入明细说明" }]}
                          >
                            <Input
                              aria-label={field.name === 0 ? "第一条明细说明" : `明细说明-${field.name}`}
                              disabled={!canEditCurrentBill}
                              placeholder="例如：基础服务费"
                            />
                          </Form.Item>
                          <Form.Item
                            label="数量"
                            name={[field.name, "quantity"]}
                            style={{ marginBottom: 0 }}
                            rules={[{ required: true, message: "请输入数量" }]}
                          >
                            <Input
                              type="number"
                              disabled={!canEditCurrentBill}
                            />
                          </Form.Item>
                          <Form.Item
                            label="单价"
                            name={[field.name, "unit_price"]}
                            style={{ marginBottom: 0 }}
                            rules={[{ required: true, message: "请输入单价" }]}
                          >
                            <Input
                              type="number"
                              disabled={!canEditCurrentBill}
                            />
                          </Form.Item>
                          <div style={{ display: "flex", alignItems: "end" }}>
                            <Button
                              danger
                              onClick={() => handleRemoveLineItem(field.name, remove)}
                              disabled={!canEditCurrentBill}
                            >
                              删除
                            </Button>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </Space>
                )}
              </Form.List>
            </Form>

            <Space wrap>
              {canEditCurrentBill ? (
                <Button type="primary" loading={billingSaving} onClick={() => void handleSaveBill()}>
                  保存账单
                </Button>
              ) : null}
              {transitionActions.map((action) => (
                <Button
                  key={action.key}
                  loading={billingActionLoading === action.nextStatus}
                  onClick={() => void handleBillingTransition(action.nextStatus)}
                >
                  {action.label}
                </Button>
              ))}
              {billingMode === "detail" && canCancelBilling(currentStatus) ? (
                <DangerButton
                  label="作废账单"
                  type="default"
                  confirmTitle="确认作废这张账单？"
                  confirmDescription="只有草稿和待确认账单可以作废。"
                  loading={billingActionLoading === "cancelled"}
                  onConfirm={async () => handleCancelBill()}
                />
              ) : null}
            </Space>
          </Space>
        )}
      </Card>
    );
  };

  const renderBilling = (): JSX.Element => {
    if (!selectedAgent) return renderOverview();

    return (
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Alert
          type="info"
          showIcon
          message="账单治理顺序"
          description="先按筛选定位账单，再查看详情、编辑 line_items，最后按状态流推进：草稿 → 待确认 → 已支付 → 已核销。草稿/待确认也可直接作废。"
        />
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.1fr) minmax(360px, 0.9fr)", gap: 16 }}>
          <Card
            title="账单列表"
            extra={(
              <Space wrap>
                <Button onClick={() => void loadBills(selectedAgent.id, billingFilters)} loading={billsLoading}>
                  刷新账单
                </Button>
                <Button type="primary" onClick={handleNewBill}>
                  新建账单
                </Button>
              </Space>
            )}
          >
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12, marginBottom: 16 }}>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span>账单状态</span>
                <select
                  aria-label="账单状态"
                  value={billingFilterDraft.status}
                  onChange={(event) => setBillingFilterDraft((current) => ({ ...current, status: event.target.value }))}
                  style={{ minHeight: 32 }}
                >
                  <option value="">全部</option>
                  <option value="draft">草稿</option>
                  <option value="pending">待确认</option>
                  <option value="paid">已支付</option>
                  <option value="verified">已核销</option>
                  <option value="cancelled">已作废</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span>账单类型</span>
                <select
                  aria-label="账单类型"
                  value={billingFilterDraft.billing_type}
                  onChange={(event) => setBillingFilterDraft((current) => ({ ...current, billing_type: event.target.value }))}
                  style={{ minHeight: 32 }}
                >
                  <option value="">全部</option>
                  <option value="monthly">月账单</option>
                  <option value="subscription">订阅账单</option>
                  <option value="usage">用量账单</option>
                </select>
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span>周期开始</span>
                <Input
                  aria-label="周期开始"
                  type="date"
                  value={billingFilterDraft.period_start}
                  onChange={(event) => setBillingFilterDraft((current) => ({ ...current, period_start: event.target.value }))}
                />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <span>周期结束</span>
                <Input
                  aria-label="周期结束"
                  type="date"
                  value={billingFilterDraft.period_end}
                  onChange={(event) => setBillingFilterDraft((current) => ({ ...current, period_end: event.target.value }))}
                />
              </label>
            </div>
            <Space style={{ marginBottom: 16 }}>
              <Button type="primary" onClick={() => void handleApplyBillingFilters()}>
                应用筛选
              </Button>
              <Button onClick={() => void handleResetBillingFilters()}>重置筛选</Button>
            </Space>
            <Table
              rowKey="id"
              dataSource={bills}
              columns={withSorter(billingColumns)}
              loading={billsLoading}
              pagination={false}
              locale={{ emptyText: <Empty description="暂无账单" /> }}
              onRow={(record) => ({
                onClick: () => void handleSelectBill(record),
                style: {
                  cursor: "pointer",
                  backgroundColor: selectedBillId === record.id ? "#f0f7ff" : undefined,
                },
              })}
            />
          </Card>
          {renderBillingEditor()}
        </div>
      </Space>
    );
  };

  const renderWorkspaceContent = (): JSX.Element => {
    if (!selectedAgent && selectedAgencyId) {
      return (
        <Alert
          type="warning"
          showIcon
          message="当前代理商不存在"
          description="该深链对应的代理商未找到，请从左侧重新选择。"
        />
      );
    }

    if (activeTab === "permissions" && selectedAgent) return <AgencyPermissionGrantsPanel agencyId={selectedAgent.id} />;
    if (activeTab === "roles") return renderRoles();
    if (activeTab === "members") return renderMembers();
    if (activeTab === "edit") return renderEdit();
    if (activeTab === "billing") return renderBilling();
    return renderOverview();
  };

  return (
    <PageShell
      title={selectedAgentTitle}
      subtitle={selectedAgentSubtitle}
      actions={(
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={() => void loadAgents()}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              createForm.resetFields();
              setCreateModalOpen(true);
            }}
          >
            新建代理商
          </Button>
        </Space>
      )}
    >
      <div style={{ padding: "0 4px 12px" }}>
        <Typography.Text type="secondary">{breadcrumbText}</Typography.Text>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px minmax(0, 1fr)", gap: 16, alignItems: "start" }}>
        <Card title="代理列表">
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Input
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
              placeholder="搜索代理名称 / 登录名 / 品牌"
            />
            <List
              loading={loading}
              dataSource={filteredAgents}
              locale={{ emptyText: <Empty description="暂无代理商" /> }}
              renderItem={(agent) => {
                const selected = agent.id === selectedAgencyId;
                const primaryLabel = agent.username ? `${agent.name}（${agent.username}）` : agent.name;

                return (
                  <List.Item
                    key={agent.id}
                    style={{
                      display: "block",
                      padding: 12,
                      border: selected ? "1px solid #1677ff" : "1px solid #f0f0f0",
                      borderRadius: 12,
                      marginBottom: 8,
                      background: selected ? "#f0f7ff" : "#fff",
                      cursor: "pointer",
                    }}
                    onClick={() => selectAgency(agent.id)}
                  >
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space wrap align="center" style={{ justifyContent: "space-between", width: "100%" }}>
                        <Typography.Text strong>{primaryLabel}</Typography.Text>
                        {getAgentStatusTag(agent.status)}
                      </Space>
                      {agent.brand_name?.trim() ? (
                        <Typography.Text type="secondary">品牌 {agent.brand_name}</Typography.Text>
                      ) : null}
                      <Space size={12} wrap>
                        <Typography.Text type="secondary">成员 {agent.member_count ?? 0}</Typography.Text>
                        <Typography.Text type="secondary">角色 {agent.role_count ?? 0}</Typography.Text>
                        <Typography.Text type="secondary">权限池 {agent.granted_permission_count ?? 0}</Typography.Text>
                      </Space>
                    </Space>
                  </List.Item>
                );
              }}
            />
          </Space>
        </Card>

        <div>
          {selectedAgent ? (
            <>
              <Tabs activeKey={activeTab} onChange={handleTabChange} items={WORKBENCH_TAB_ITEMS} />
              <div style={{ marginTop: 16 }}>{renderWorkspaceContent()}</div>
            </>
          ) : (
            renderWorkspaceContent()
          )}
        </div>
      </div>

      <Modal
        title="新建代理商"
        open={createModalOpen}
        forceRender
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        onOk={() => createForm.submit()}
        confirmLoading={creating}
        width={520}
      >
        <Form form={createForm} layout="vertical" onFinish={(values) => void handleCreateAgent(values)}>
          <Form.Item label="代理名称" name="name" rules={[{ required: true, message: "请输入代理名称" }]}>
            <Input placeholder="例如：上海锦囊" />
          </Form.Item>
          <Form.Item
            label="登录名"
            name="username"
            rules={[
              { required: true, message: "请输入登录名" },
              {
                pattern: /^[a-zA-Z][a-zA-Z0-9_]{2,49}$/,
                message: "字母开头，长度 3-50，只能包含字母、数字和下划线",
              },
              {
                validator: async (_, value: string | undefined) => {
                  if (!value || value.length < 3) return;
                  const exists = await checkAgentUsername(value);
                  if (exists) throw new Error("该登录名已被占用");
                },
                validateTrigger: "onBlur",
              },
            ]}
          >
            <Input placeholder="agent001" />
          </Form.Item>
          <Form.Item label="初始密码" name="password" rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}>
            <Input.Password placeholder="至少 8 位" />
          </Form.Item>
          <Form.Item label="品牌名称" name="brand_name">
            <Input placeholder="例如：锦囊品牌" />
          </Form.Item>
          <Form.Item label="联系人" name="contact_name">
            <Input placeholder="姓名" />
          </Form.Item>
          <Form.Item label="联系电话" name="contact_phone">
            <Input placeholder="手机号" />
          </Form.Item>
          <Form.Item label="联系邮箱" name="contact_email">
            <Input placeholder="email@example.com" />
          </Form.Item>
        </Form>
      </Modal>

      {!selectedAgent ? (
        <div style={{ display: "none" }}>
          <Form form={editForm} />
          <Form form={resetPasswordForm} />
          <Form form={billingForm} initialValues={buildBillingFormValues(null)} />
        </div>
      ) : null}
    </PageShell>
  );
}
