import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

vi.mock("./adminAuth", () => ({
  adminAuth: {
    getAccessToken: () => "token-1",
    getCurrentUser: () => ({ agency_id: "agency-1" }),
    getMe: vi.fn(async () => ({ agency_id: "agency-1" })),
  },
}));

describe("permissions service", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("maps permission definitions object into module rows", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total: 2,
        modules: {
          roles: [{ code: "roles.view", label: "查看角色" }],
          security: [{ code: "security.view", label: "查看安全中心" }],
        },
      }),
    });

    const { listPermissionDefinitions } = await import("./permissions");
    const modules = await listPermissionDefinitions();

    expect(modules.map((item) => item.module)).toEqual(["roles", "security"]);
    expect(modules[0].permissions[0].code).toBe("roles.view");
  });

  it("treats menu visibility ids as canonical values without legacy aliases", async () => {
    const { canSeePageWithMenus } = await import("../hooks/usePermissions");

    expect(canSeePageWithMenus(["tickets"], "tickets")).toBe(true);
    expect(canSeePageWithMenus(["task-rules"], "task_rules")).toBe(false);
    expect(canSeePageWithMenus(["security"], "security_settings")).toBe(false);
  });

  it("flattens canonical permission codes from backend definitions only", async () => {
    const { flattenPermissionCodes } = await import("./permissions");

    const codes = flattenPermissionCodes([
      {
        module: "roles",
        label: "Roles",
        permissions: [
          { code: "roles.view", label: "View roles" },
          { code: "roles.edit", label: "Edit roles" },
        ],
      },
      {
        module: "security_settings",
        label: "Security",
        permissions: [
          { code: "security_settings.view", label: "View security settings" },
          { code: "roles.view", label: "Duplicate roles view" },
        ],
      },
    ]);

    expect(codes).toEqual([
      "roles.view",
      "roles.edit",
      "security_settings.view",
    ]);
  });

  it("builds agency role summaries from permission-center payload counts only", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        agency_id: "agency-1",
        roles: [
          {
            id: "role-1",
            role_name: "agent",
            is_template: false,
            template_name: null,
            permissions: ["tags.view", "tags.edit"],
            created_by: "seed",
            updated_at: "2026-06-22T00:00:00Z",
            member_count: 1,
          },
          {
            id: "role-2",
            role_name: "custom_support",
            is_template: false,
            template_name: null,
            permissions: ["tickets.view"],
            created_by: "seed",
            updated_at: "2026-06-22T00:00:00Z",
            member_count: 2,
          },
        ],
      }),
    });

    const { listAgencyRoleSummaries } = await import("./permissions");
    const roles = await listAgencyRoleSummaries("agency-1");

    expect(roles).toHaveLength(2);
    expect(roles[0]).toMatchObject({
      role_key: "agent",
      member_count: 1,
      permission_count: 2,
      source: "api",
    });
    expect(roles[1]).toMatchObject({
      role_key: "custom_support",
      member_count: 2,
      permission_count: 1,
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("keeps placeholder roles without persisted config as draft and unconfigured", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        agency_id: "agency-1",
        roles: [
          {
            id: null,
            role_name: "support",
            is_template: false,
            template_name: null,
            permissions: [],
            created_by: null,
            updated_at: null,
            member_count: 3,
          },
        ],
      }),
    });

    const { listAgencyRoleSummaries } = await import("./permissions");
    const roles = await listAgencyRoleSummaries("agency-1");

    expect(roles).toEqual([
      expect.objectContaining({
        role_key: "support",
        status: "draft",
        permission_origin: "unconfigured",
        permission_count: 0,
        member_count: 3,
      }),
    ]);
  });

  it("updates agency role permissions with auth header and payload", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        role_name: "agent",
        permissions: ["tickets.view", "tickets.reply"],
      }),
    });

    const { updateAgencyRolePermissions } = await import("./permissions");
    const result = await updateAgencyRolePermissions("agency-1", "agent", [
      "tickets.view",
      "tickets.reply",
    ]);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/permissions/agency/agency-1",
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          role_name: "agent",
          permissions: ["tickets.view", "tickets.reply"],
        }),
      }),
    );
    expect(result.permissions).toEqual(["tickets.view", "tickets.reply"]);
  });

  it("lists permission templates as normalized preset and custom template groups", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        presets: [
          {
            id: "standard_support",
            name: "Standard Support",
            description: "Preset support role",
            is_preset: true,
            permissions: ["tickets.view", "tickets.reply"],
            permission_count: 2,
          },
        ],
        custom: [
          {
            id: "tpl-1",
            name: "Night Shift",
            agency_id: "agency-1",
            permissions: ["tickets.view"],
            permission_count: 1,
          },
        ],
      }),
    });

    const { listPermissionTemplates } = await import("./permissions");
    const result = await listPermissionTemplates();

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/permissions/templates",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result.presets).toEqual([
      {
        id: "standard_support",
        name: "Standard Support",
        description: "Preset support role",
        agency_id: null,
        is_preset: true,
        permissions: ["tickets.view", "tickets.reply"],
        permission_count: 2,
      },
    ]);
    expect(result.custom).toEqual([
      {
        id: "tpl-1",
        name: "Night Shift",
        description: null,
        agency_id: "agency-1",
        is_preset: false,
        permissions: ["tickets.view"],
        permission_count: 1,
      },
    ]);
    expect(result.all.map((template) => template.id)).toEqual([
      "standard_support",
      "tpl-1",
    ]);
  });

  it("applies a permission template to an agency role", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        template_name: "Standard Support",
        target_role: "agent",
        role_name: "agent",
        permissions: ["tickets.view", "tickets.reply"],
        permission_count: 2,
      }),
    });

    const { applyPermissionTemplate } = await import("./permissions");
    const result = await applyPermissionTemplate({
      agencyId: "agency-1",
      templateId: "standard_support",
      targetRole: "agent",
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/permissions/apply-template",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          agency_id: "agency-1",
          template_id: "standard_support",
          target_role: "agent",
        }),
      }),
    );
    expect(result).toMatchObject({
      status: "ok",
      template_name: "Standard Support",
      target_role: "agent",
      role_name: "agent",
      permission_count: 2,
    });
  });

  it("creates a custom role with canonical permission codes and agency scope", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        id: "role-3",
        role_name: "custom_finance_viewer",
        permissions: ["reports.view"],
        permission_count: 1,
      }),
    });

    const { createCustomRole } = await import("./permissions");
    const result = await createCustomRole({
      agencyId: "agency-1",
      roleName: "custom_finance_viewer",
      permissions: ["reports.view"],
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/permissions/custom-role",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          agency_id: "agency-1",
          role_name: "custom_finance_viewer",
          permissions: ["reports.view"],
        }),
      }),
    );
    expect(result).toMatchObject({
      status: "ok",
      id: "role-3",
      role_name: "custom_finance_viewer",
      permission_count: 1,
    });
  });

  it("copies permissions from one agency to another", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        status: "ok",
        source_agency_id: "agency-source",
        target_agency_id: "agency-target",
        roles_copied: 3,
      }),
    });

    const { copyAgencyPermissions } = await import("./permissions");
    const result = await copyAgencyPermissions("agency-source", "agency-target");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/permissions/copy",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          source_agency_id: "agency-source",
          target_agency_id: "agency-target",
        }),
      }),
    );
    expect(result).toEqual({
      status: "ok",
      source_agency_id: "agency-source",
      target_agency_id: "agency-target",
      roles_copied: 3,
    });
  });

  it("deletes an agency role and tolerates a 204 response body", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      text: async () => "",
    });

    const { deleteAgencyRole } = await import("./permissions");
    const result = await deleteAgencyRole("agency-1", "custom_finance_viewer");

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/permissions/agency/agency-1/roles/custom_finance_viewer",
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({
          Authorization: "Bearer token-1",
        }),
      }),
    );
    expect(result).toEqual({
      status: "ok",
      agency_id: "agency-1",
      role_name: "custom_finance_viewer",
    });
  });

  it("extracts readable messages from structured permission-center errors", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({
        detail: {
          message: "Super-admin-only permissions cannot be assigned to agency roles.",
          forbidden_permissions: ["agents.permissions"],
        },
      }),
    });

    const { updateAgencyRolePermissions } = await import("./permissions");

    await expect(
      updateAgencyRolePermissions("agency-1", "support", ["agents.permissions"]),
    ).rejects.toThrow("Super-admin-only permissions cannot be assigned to agency roles.");
  });
});
