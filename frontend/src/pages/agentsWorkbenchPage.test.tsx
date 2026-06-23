import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentsPage } from "./AgentsPage";

const hoisted = vi.hoisted(() => ({
  listAgentsMock: vi.fn(),
  listAgencyRoleSummariesMock: vi.fn(),
  createAgencyBillingMock: vi.fn(),
  listAgencyBillingMock: vi.fn(),
  getAgencyBillingDetailMock: vi.fn(),
  updateAgencyBillingMock: vi.fn(),
  cancelAgencyBillingMock: vi.fn(),
  resetAgentPasswordMock: vi.fn(),
  updateAgentMock: vi.fn(),
}));

vi.mock("../components/PageShell", () => ({
  PageShell: ({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) => (
    <div>
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
      {children}
    </div>
  ),
}));

vi.mock("../components/Feedback", () => ({
  showError: vi.fn(),
  showSuccess: vi.fn(),
  DangerButton: ({ label }: { label: string }) => <button type="button">{label}</button>,
}));

vi.mock("../components/agents/AgencyPermissionGrantsPanel", () => ({
  AgencyPermissionGrantsPanel: ({ agencyId }: { agencyId: string }) => <div>grants:{agencyId}</div>,
}));

vi.mock("../components/agents/AgencyRolesPanel", () => ({
  AgencyRolesPanel: ({
    agencyId,
    initialRoleKey,
    permissionEditingDisabled,
  }: {
    agencyId: string;
    initialRoleKey?: string | null;
    permissionEditingDisabled?: boolean;
  }) => (
    <div>roles:{agencyId}:{initialRoleKey ?? "-"}:{permissionEditingDisabled ? "locked" : "open"}</div>
  ),
}));

vi.mock("../components/agents/AgencyMembersPanel", () => ({
  AgencyMembersPanel: ({
    agencyId,
    initialMemberId,
    roleOptions,
    onRoleCenter,
    roleAssignmentDisabled,
  }: {
    agencyId: string;
    initialMemberId?: string | null;
    roleOptions?: Array<{ label: string; value: string }>;
    onRoleCenter?: (roleName: string) => void;
    roleAssignmentDisabled?: boolean;
  }) => (
    <div>
      <div>members:{agencyId}:{initialMemberId ?? "-"}:{roleAssignmentDisabled ? "locked" : "open"}:{roleOptions?.length ?? 0}</div>
      <button type="button" onClick={() => onRoleCenter?.("support")}>
        jump-role-center
      </button>
    </div>
  ),
}));

vi.mock("../services/permissions", () => ({
  listAgencyRoleSummaries: hoisted.listAgencyRoleSummariesMock,
}));

vi.mock("../services/api", () => ({
  listAgents: hoisted.listAgentsMock,
  checkAgentUsername: vi.fn(),
  createAgent: vi.fn(),
  createAgencyBilling: hoisted.createAgencyBillingMock,
  listAgencyBilling: hoisted.listAgencyBillingMock,
  getAgencyBillingDetail: hoisted.getAgencyBillingDetailMock,
  updateAgencyBilling: hoisted.updateAgencyBillingMock,
  cancelAgencyBilling: hoisted.cancelAgencyBillingMock,
  resetAgentPassword: hoisted.resetAgentPasswordMock,
  restoreAgent: vi.fn(),
  updateAgent: hoisted.updateAgentMock,
  updateAgentStatus: vi.fn(),
}));

const billingDraft = {
  id: "bill-1",
  agency_id: "agency-1",
  billing_type: "monthly",
  amount: 3000,
  billing_period_start: "2026-06-01",
  billing_period_end: "2026-06-30",
  status: "draft",
  created_at: "2026-06-22T00:00:00Z",
  line_items: [
    { description: "基础服务费", quantity: 1, unit_price: 2800 },
    { description: "消息配额", quantity: 2, unit_price: 100 },
  ],
};

describe("AgentsPage workbench", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
    vi.stubGlobal(
      "getComputedStyle",
      vi.fn().mockImplementation(() => ({
        getPropertyValue: () => "",
      })),
    );

    hoisted.listAgentsMock.mockReset().mockResolvedValue([
      {
        id: "agency-1",
        name: "上海锦囊",
        username: "jinang001",
        brand_name: "锦囊品牌",
        status: "active",
        created_at: "2026-06-22T00:00:00Z",
        updated_at: "2026-06-22T09:00:00Z",
        member_count: 3,
        role_count: 2,
        granted_permission_count: 6,
      },
      {
        id: "agency-2",
        name: "深圳启航",
        username: "qihang001",
        brand_name: "启航品牌",
        status: "suspended",
        created_at: "2026-06-22T00:00:00Z",
        updated_at: "2026-06-22T10:00:00Z",
        member_count: 1,
        role_count: 1,
        granted_permission_count: 2,
      },
      {
        id: "agency-3",
        name: "归档代理",
        username: "archive001",
        brand_name: "归档品牌",
        status: "archived",
        created_at: "2026-06-22T00:00:00Z",
        updated_at: "2026-06-22T08:00:00Z",
        member_count: 0,
        role_count: 0,
        granted_permission_count: 0,
      },
    ]);
    hoisted.createAgencyBillingMock.mockReset().mockResolvedValue({
      ...billingDraft,
      id: "bill-new",
    });
    hoisted.listAgencyRoleSummariesMock.mockReset().mockResolvedValue([
      {
        role_key: "agent",
        name: "代理商管理员",
        scope: "account",
        status: "active",
        member_count: 2,
        source: "api",
        permission_origin: "custom",
        permission_origin_role_key: null,
        account_scope: ["agency-1"],
        permission_count: 4,
        permissions: ["tickets.view"],
        is_template: false,
        template_name: null,
        updated_at: "2026-06-22T09:00:00Z",
      },
      {
        role_key: "support",
        name: "客服",
        scope: "account",
        status: "active",
        member_count: 1,
        source: "api",
        permission_origin: "custom",
        permission_origin_role_key: null,
        account_scope: ["agency-1"],
        permission_count: 2,
        permissions: ["tickets.view"],
        is_template: false,
        template_name: null,
        updated_at: "2026-06-22T09:00:00Z",
      },
    ]);
    hoisted.listAgencyBillingMock.mockReset().mockResolvedValue([billingDraft]);
    hoisted.getAgencyBillingDetailMock.mockReset().mockResolvedValue(billingDraft);
    hoisted.updateAgencyBillingMock.mockReset().mockResolvedValue({
      ...billingDraft,
      status: "pending",
    });
    hoisted.cancelAgencyBillingMock.mockReset().mockResolvedValue({
      ...billingDraft,
      status: "cancelled",
    });
    hoisted.resetAgentPasswordMock.mockReset().mockResolvedValue(undefined);
    hoisted.updateAgentMock.mockReset().mockResolvedValue(undefined);
    window.history.replaceState({}, "", "/system/agents");
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows the overview workspace before an agency is selected", async () => {
    render(<AgentsPage />);

    expect(await screen.findByRole("heading", { name: "代理商管理" })).toBeTruthy();
    expect(screen.getByText("人员管理 / 代理商管理")).toBeTruthy();
    expect(await screen.findByText("代理总览")).toBeTruthy();
    expect(screen.getByText("请选择左侧代理商，进入权限池、角色、成员、编辑和账单工作区。")).toBeTruthy();
  });

  it("uses the agent list as a pure selector and exposes edit and billing tabs in the workspace", async () => {
    render(<AgentsPage />);

    await screen.findByText("上海锦囊（jinang001）");

    expect(screen.queryByRole("button", { name: "进入工作台" })).toBeNull();
    expect(screen.queryByRole("button", { name: "编辑" })).toBeNull();
    expect(screen.queryByRole("button", { name: "角色与权限" })).toBeNull();

    fireEvent.click(screen.getByText("上海锦囊（jinang001）"));

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-1&tab=overview");
    });

    expect(screen.getByRole("tab", { name: "编辑" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "账单" })).toBeTruthy();
  });

  it("restores the selected agency and roles tab from the query string", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-1&tab=roles&role=agent");

    render(<AgentsPage />);

    expect(await screen.findByText("roles:agency-1:agent:open")).toBeTruthy();
    expect(screen.getByText("人员管理 / 代理商管理 / 上海锦囊 / 角色")).toBeTruthy();
  });

  it("restores the selected agency members tab from the query string", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-1&tab=members&member=member-1");

    render(<AgentsPage />);

    expect(await screen.findByText("members:agency-1:member-1:open:2")).toBeTruthy();
    expect(screen.getByText("人员管理 / 代理商管理 / 上海锦囊 / 成员")).toBeTruthy();
  });

  it("preloads agency roles before opening the members tab so role assignment is not falsely locked", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-1&tab=members");

    render(<AgentsPage />);

    await waitFor(() => {
      expect(hoisted.listAgencyRoleSummariesMock).toHaveBeenCalledWith("agency-1");
    });
    expect(await screen.findByText("members:agency-1:-:open:2")).toBeTruthy();
  });

  it("navigates from the overview shortcuts into the governed workbench tabs", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));

    expect(await screen.findByRole("button", { name: "配置权限池" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "管理角色" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "管理成员" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "编辑资料" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "查看账单" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "管理成员" }));

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-1&tab=members");
    });
    expect(await screen.findByText("members:agency-1:-:open:2")).toBeTruthy();
  });

  it("converges agent profile, password and status operations into the edit workbench", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(screen.getByRole("tab", { name: "编辑" }));

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-1&tab=edit");
    });

    expect(await screen.findByText("编辑工作台")).toBeTruthy();
    expect(screen.getByText("编辑代理信息")).toBeTruthy();
    expect(screen.getByText("当前账号")).toBeTruthy();
    expect((screen.getAllByText("重置密码")).length).toBeGreaterThan(0);
    expect(screen.getByText("状态操作")).toBeTruthy();
    expect(screen.getByText("资料、密码与状态操作统一在这里处理。成员、角色和权限池请分别在对应 Tab 内维护。")).toBeTruthy();
  });

  it("jumps from the members tab into the current agency role tab", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-1&tab=members");

    render(<AgentsPage />);

    expect(await screen.findByText("members:agency-1:-:open:2")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "jump-role-center" }));

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-1&tab=roles&role=support");
    });
    expect(await screen.findByText("roles:agency-1:support:open")).toBeTruthy();
  });

  it("locks the roles workspace when the permission pool is empty", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-3&tab=roles");

    render(<AgentsPage />);

    expect(await screen.findByText("roles:agency-3:-:locked")).toBeTruthy();
    expect(screen.getByText("当前权限池为空")).toBeTruthy();
    expect(screen.getByText("请先配置该代理商的权限池，再继续配置角色权限。")).toBeTruthy();
  });

  it("locks the members workspace when the permission pool is empty", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-3&tab=members");

    render(<AgentsPage />);

    expect(await screen.findByText("members:agency-3:-:locked:0")).toBeTruthy();
    expect(screen.getByText("请先配置权限池和角色")).toBeTruthy();
    expect(screen.getByText("成员只能绑定角色，角色权限来自代理权限池。")).toBeTruthy();
  });

  it("filters billing records with scoped params", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));

    await waitFor(() => {
      expect(hoisted.listAgencyBillingMock).toHaveBeenCalledWith("agency-1", {});
    });

    fireEvent.change(screen.getByLabelText("账单状态"), { target: { value: "draft" } });
    fireEvent.change(screen.getByLabelText("账单类型"), { target: { value: "monthly" } });
    fireEvent.change(screen.getByLabelText("周期开始"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("周期结束"), { target: { value: "2026-06-30" } });
    fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));

    await waitFor(() => {
      expect(hoisted.listAgencyBillingMock).toHaveBeenLastCalledWith("agency-1", {
        status: "draft",
        billing_type: "monthly",
        period_start: "2026-06-01",
        period_end: "2026-06-30",
      });
    });
  });

  it("resets billing filters back to the full list and clears draft inputs", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));

    fireEvent.change(screen.getByLabelText("账单状态"), { target: { value: "draft" } });
    fireEvent.change(screen.getByLabelText("账单类型"), { target: { value: "monthly" } });
    fireEvent.change(screen.getByLabelText("周期开始"), { target: { value: "2026-06-01" } });
    fireEvent.change(screen.getByLabelText("周期结束"), { target: { value: "2026-06-30" } });
    fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));

    await waitFor(() => {
      expect(hoisted.listAgencyBillingMock).toHaveBeenLastCalledWith("agency-1", {
        status: "draft",
        billing_type: "monthly",
        period_start: "2026-06-01",
        period_end: "2026-06-30",
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "重置筛选" }));

    await waitFor(() => {
      expect(hoisted.listAgencyBillingMock).toHaveBeenLastCalledWith("agency-1", {});
    });

    expect((screen.getByLabelText("账单状态") as HTMLSelectElement).value).toBe("");
    expect((screen.getByLabelText("账单类型") as HTMLSelectElement).value).toBe("");
    expect((screen.getByLabelText("周期开始") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("周期结束") as HTMLInputElement).value).toBe("");
  });

  it("shows a creation-oriented empty state when the agency has no billing records", async () => {
    hoisted.listAgencyBillingMock.mockReset().mockResolvedValue([]);

    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));

    expect(await screen.findByText("暂无账单")).toBeTruthy();
    expect(screen.getByText("当前暂无账单，可在左侧新建账单。")).toBeTruthy();
  });

  it("shows billing detail with line items inside the tab workspace", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));

    const billRow = await screen.findByRole("row", { name: /月账单/i });
    fireEvent.click(billRow);

    await waitFor(() => {
      expect(hoisted.getAgencyBillingDetailMock).toHaveBeenCalledWith("agency-1", "bill-1");
    });

    expect(await screen.findByText("账单详情")).toBeTruthy();
    expect(screen.getByDisplayValue("3000")).toBeTruthy();
    expect(screen.getByDisplayValue("基础服务费")).toBeTruthy();
    expect(screen.getByDisplayValue("消息配额")).toBeTruthy();
  });

  it("updates billing status through the formal state flow", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));
    fireEvent.click(await screen.findByRole("row", { name: /月账单/i }));

    expect(await screen.findByText("账单详情")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "提交账单" }));

    await waitFor(() => {
      expect(hoisted.updateAgencyBillingMock).toHaveBeenCalledWith("agency-1", "bill-1", { status: "pending" });
    });
  });

  it("shows verified bills as read-only and hides edit-only actions", async () => {
    const verifiedBill = {
      ...billingDraft,
      status: "verified",
    };
    hoisted.listAgencyBillingMock.mockReset().mockResolvedValue([verifiedBill]);
    hoisted.getAgencyBillingDetailMock.mockReset().mockResolvedValue(verifiedBill);

    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));
    fireEvent.click(await screen.findByRole("row", { name: /月账单/i }));

    expect(await screen.findByText("当前账单已进入只读状态")).toBeTruthy();
    expect(screen.getByText("已支付、已核销和已作废账单只允许查看，不再支持编辑或作废。")).toBeTruthy();
    expect((screen.getByLabelText("账单金额") as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "保存账单" })).toBeNull();
    expect(screen.queryByRole("button", { name: "作废账单" })).toBeNull();
  });

  it("creates a bill with agency scoped payload", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));

    await screen.findByText("账单详情");
    fireEvent.click(screen.getByRole("button", { name: "新建账单" }));

    fireEvent.change(screen.getByLabelText("账单金额"), { target: { value: "3600" } });
    fireEvent.change(screen.getByLabelText("第一条明细说明"), { target: { value: "新建基础服务费" } });
    fireEvent.click(screen.getByRole("button", { name: "保存账单" }));

    await waitFor(() => {
      expect(hoisted.createAgencyBillingMock).toHaveBeenCalledWith(
        "agency-1",
        expect.objectContaining({
          amount: 3600,
        }),
      );
    });
  });

  it("keeps one blank line item in create mode when the operator deletes the last detail row", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));

    await screen.findByText("账单详情");
    fireEvent.click(screen.getByRole("button", { name: "新建账单" }));
    fireEvent.click(screen.getByRole("button", { name: /删\s*除/ }));

    expect(screen.getByLabelText("第一条明细说明")).toBeTruthy();
  });

  it("keeps archived agencies at the bottom of the list", async () => {
    render(<AgentsPage />);

    await screen.findByText("上海锦囊（jinang001）");

    const items = document.querySelectorAll(".ant-list-item");
    expect(items.length).toBeGreaterThanOrEqual(3);
    expect(items[items.length - 1]?.textContent).toContain("archive001");
  });

  it("keeps the left agent card compact without repeating login labels", async () => {
    render(<AgentsPage />);

    await screen.findByText("上海锦囊（jinang001）");

    const items = Array.from(document.querySelectorAll(".ant-list-item"));
    const firstItem = items[0] as HTMLElement;
    expect(firstItem.textContent).toContain("上海锦囊（jinang001）");
    expect(firstItem.textContent).toContain("品牌 锦囊品牌");
    expect(firstItem.textContent).not.toContain("登录名");
  });

  it("renders billing status summary in the list row", async () => {
    render(<AgentsPage />);

    fireEvent.click(await screen.findByText("上海锦囊（jinang001）"));
    fireEvent.click(await screen.findByRole("tab", { name: "账单" }));

    const table = await screen.findByRole("table");
    expect(within(table).getByText("草稿")).toBeTruthy();
    expect(within(table).getByText("2 项明细")).toBeTruthy();
  });
});
