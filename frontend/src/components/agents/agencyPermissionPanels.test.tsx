import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgencyPermissionGrantsPanel } from "./AgencyPermissionGrantsPanel";
import { AgencyMembersPanel } from "./AgencyMembersPanel";
import { AgencyRolesPanel } from "./AgencyRolesPanel";
import { AgentDetailPage } from "../../pages/AgentDetailPage";

const hoisted = vi.hoisted(() => ({
  listAgentsMock: vi.fn(),
  listAgentMembersMock: vi.fn(),
  removeAgentMemberMock: vi.fn(),
  listAgencyRoleSummariesMock: vi.fn(),
  listPermissionDefinitionsMock: vi.fn(),
  listPermissionTemplatesMock: vi.fn(),
  listAgencyGrantedPermissionsMock: vi.fn(),
  updateAgencyGrantedPermissionsMock: vi.fn(),
  updateAgencyRolePermissionsMock: vi.fn(),
  createCustomRoleMock: vi.fn(),
  applyPermissionTemplateMock: vi.fn(),
  deleteAgencyRoleMock: vi.fn(),
  copyAgencyPermissionsMock: vi.fn(),
}));

vi.mock("../PageShell", () => ({
  PageShell: ({
    title,
    subtitle,
    actions,
    children,
  }: {
    title: string;
    subtitle?: string;
    actions?: React.ReactNode;
    children?: React.ReactNode;
  }) => (
    <div>
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
      {actions}
      {children}
    </div>
  ),
}));

vi.mock("../Feedback", () => ({
  showSuccess: vi.fn(),
  showError: vi.fn(),
  DangerButton: ({ label, disabled }: { label: string; disabled?: boolean }) => (
    <button type="button" disabled={disabled}>
      {label}
    </button>
  ),
}));

vi.mock("../../services/api", () => ({
  listAgents: hoisted.listAgentsMock,
  listAgentMembers: hoisted.listAgentMembersMock,
  addAgentMember: vi.fn(),
  updateAgentMemberRole: vi.fn(),
  removeAgentMember: hoisted.removeAgentMemberMock,
  checkAgentUsername: vi.fn(),
}));

vi.mock("../../services/permissions", () => ({
  listAgencyRoleSummaries: hoisted.listAgencyRoleSummariesMock,
  listPermissionDefinitions: hoisted.listPermissionDefinitionsMock,
  listPermissionTemplates: hoisted.listPermissionTemplatesMock,
  listAgencyGrantedPermissions: hoisted.listAgencyGrantedPermissionsMock,
  updateAgencyGrantedPermissions: hoisted.updateAgencyGrantedPermissionsMock,
  updateAgencyRolePermissions: hoisted.updateAgencyRolePermissionsMock,
  applyPermissionTemplate: hoisted.applyPermissionTemplateMock,
  createCustomRole: hoisted.createCustomRoleMock,
  deleteAgencyRole: hoisted.deleteAgencyRoleMock,
  copyAgencyPermissions: hoisted.copyAgencyPermissionsMock,
}));

function buildPermissionDefinitions() {
  return [
    {
      module: "tickets",
      label: "工单",
      permissions: [
        { code: "tickets.view", label: "查看工单" },
        { code: "tickets.reply", label: "回复工单" },
        { code: "tickets.delete", label: "删除工单", super_admin_only: true },
      ],
    },
    {
      module: "finance",
      label: "财务",
      permissions: [{ code: "finance.view", label: "查看账单" }],
    },
  ];
}

describe("AgentDetailPage compatibility redirect", () => {
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
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("redirects the legacy detail route into the single workbench overview route", async () => {
    window.history.replaceState({}, "", "/system/agents/agency-1");

    render(<AgentDetailPage />);

    expect(screen.getByText("代理详情兼容入口")).toBeTruthy();

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-1&tab=overview");
    });
  });

  it("preserves role targeting when redirecting the legacy detail route", async () => {
    window.history.replaceState({}, "", "/system/agents/agency-1?tab=roles&role=support");

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-1&tab=roles&role=support");
    });
  });

  it("normalizes the old permission-grants tab into the formal permissions tab", async () => {
    window.history.replaceState({}, "", "/system/agents/agency-1?tab=permission-grants");

    render(<AgentDetailPage />);

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe("/system/agents?agencyId=agency-1&tab=permissions");
    });
  });
});

describe("agency permission panels", () => {
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

    hoisted.listPermissionDefinitionsMock.mockReset().mockResolvedValue(buildPermissionDefinitions());
    hoisted.listAgentMembersMock.mockReset().mockResolvedValue([
      {
        id: "member-1",
        agency_id: "agency-1",
        user_id: "agent-1",
        username: "member001",
        display_name: "成员一号",
        status: "active",
        role: "support",
        created_at: "2026-06-22T00:00:00Z",
      },
    ]);
    hoisted.removeAgentMemberMock.mockReset().mockResolvedValue(undefined);
    hoisted.listAgencyGrantedPermissionsMock.mockReset().mockResolvedValue({
      agency_id: "agency-1",
      permissions: [],
    });
    hoisted.updateAgencyGrantedPermissionsMock.mockReset().mockResolvedValue({
      agency_id: "agency-1",
      permissions: ["tickets.view", "tickets.reply"],
    });
    hoisted.listAgencyRoleSummariesMock.mockReset().mockResolvedValue([
      {
        role_key: "support",
        name: "客服",
        scope: "account",
        status: "active",
        member_count: 0,
        source: "api",
        permission_origin: "custom",
        permission_origin_role_key: null,
        account_scope: ["agency-1"],
        permission_count: 0,
        permissions: [],
        is_template: false,
        template_name: null,
        updated_at: "2026-06-22T00:00:00Z",
      },
    ]);
    hoisted.listPermissionTemplatesMock.mockReset().mockResolvedValue({
      presets: [],
      custom: [],
      all: [],
    });
    hoisted.updateAgencyRolePermissionsMock.mockReset().mockResolvedValue({
      role_key: "support",
      permissions: ["tickets.view", "tickets.reply"],
      permission_count: 2,
    });
    hoisted.createCustomRoleMock.mockReset().mockResolvedValue({
      role_key: "custom_quality",
      name: "质检",
      permissions: ["tickets.view", "tickets.reply"],
      permission_count: 2,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("hides super-admin-only grant permissions and module select-all only includes visible permissions", async () => {
    render(<AgencyPermissionGrantsPanel agencyId="agency-1" />);

    expect(await screen.findByText("查看工单")).toBeTruthy();
    expect(screen.getByText("权限池")).toBeTruthy();
    expect(
      screen.getByText("超管先在这里配置代理可下放的权限池，代理角色只能从这组权限中继续分配。"),
    ).toBeTruthy();
    expect(screen.queryByText("删除工单")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "工单全选" }));
    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));

    await waitFor(() => {
      expect(hoisted.updateAgencyGrantedPermissionsMock).toHaveBeenCalledWith("agency-1", [
        "tickets.reply",
        "tickets.view",
      ]);
    });
  });

  it("hides forbidden role permissions in the drawer and module select-all only grants visible ones", async () => {
    render(<AgencyRolesPanel agencyId="agency-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "编辑权限" }));

    expect(await screen.findByText("查看工单")).toBeTruthy();
    expect(screen.queryByText("删除工单")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "工单全选" }));
    fireEvent.click(screen.getByRole("button", { name: "保存权限" }));

    await waitFor(() => {
      expect(hoisted.updateAgencyRolePermissionsMock).toHaveBeenCalledWith("agency-1", "support", [
        "tickets.reply",
        "tickets.view",
      ]);
    });
  });

  it("hides forbidden role permissions in the create-role flow and module select-all only grants visible ones", async () => {
    render(<AgencyRolesPanel agencyId="agency-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "新建角色" }));

    expect(await screen.findByText("查看工单")).toBeTruthy();
    expect(screen.queryByText("删除工单")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "工单全选" }));
    fireEvent.change(screen.getByLabelText("Role key"), { target: { value: "quality" } });
    fireEvent.click(screen.getByRole("button", { name: /创\s*建/ }));

    await waitFor(() => {
      expect(hoisted.createCustomRoleMock).toHaveBeenCalledWith({
        agencyId: "agency-1",
        roleName: "custom_quality",
        permissions: ["tickets.reply", "tickets.view"],
      });
    });
  });

  it("disables role deletion when permission management is locked", async () => {
    hoisted.listAgencyRoleSummariesMock.mockReset().mockResolvedValue([
      {
        role_key: "custom_quality",
        name: "质检",
        scope: "account",
        status: "active",
        member_count: 0,
        source: "api",
        permission_origin: "custom",
        permission_origin_role_key: null,
        account_scope: ["agency-1"],
        permission_count: 1,
        permissions: ["tickets.view"],
        is_template: false,
        template_name: null,
        updated_at: "2026-06-22T00:00:00Z",
      },
    ]);

    render(<AgencyRolesPanel agencyId="agency-1" permissionEditingDisabled />);

    expect((await screen.findAllByText("质检")).length).toBeGreaterThan(0);
    expect((screen.getByRole("button", { name: "删除角色" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("disables member removal when the member workbench is browse-only", async () => {
    render(<AgencyMembersPanel agencyId="agency-1" roleOptions={[]} roleAssignmentDisabled />);

    expect(await screen.findByText("请先配置权限池和角色")).toBeTruthy();
    expect((screen.getByRole("button", { name: "移除" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
