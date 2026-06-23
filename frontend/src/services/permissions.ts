import { adminAuth } from "./adminAuth";

export type PermissionDefinition = {
  code: string;
  label: string;
  super_admin_only?: boolean;
};

export type PermissionModule = {
  module: string;
  label: string;
  permissions: PermissionDefinition[];
};

export type AgencyRolePermission = {
  id: string | null;
  role_name: string;
  is_template: boolean;
  template_name: string | null;
  permissions: string[];
  created_by: string | null;
  updated_at: string | null;
  member_count?: number;
};

export type AgencyRolePermissionUpdateResult = {
  status: string;
  action?: string;
  role_name: string;
  permissions: string[];
};

export type AgencyGrantedPermissions = {
  agency_id: string;
  permissions: string[];
};

export type PermissionTemplate = {
  id: string;
  name: string;
  description: string | null;
  agency_id: string | null;
  is_preset: boolean;
  permissions: string[];
  permission_count: number;
};

export type PermissionTemplateCollection = {
  presets: PermissionTemplate[];
  custom: PermissionTemplate[];
  all: PermissionTemplate[];
};

export type ApplyPermissionTemplateInput = {
  agencyId: string;
  templateId: string;
  targetRole: string;
};

export type ApplyPermissionTemplateResult = {
  status: string;
  template_name: string | null;
  target_role: string;
  role_name: string;
  permissions: string[];
  permission_count: number;
};

export type CreateCustomRoleInput = {
  agencyId: string;
  roleName: string;
  permissions: string[];
};

export type CreateCustomRoleResult = {
  status: string;
  id: string;
  role_name: string;
  permissions: string[];
  permission_count: number;
};

export type CopyAgencyPermissionsResult = {
  status: string;
  source_agency_id: string;
  target_agency_id: string;
  roles_copied: number;
};

export type DeleteAgencyRoleResult = {
  status: string;
  agency_id: string;
  role_name: string;
};

export type AgencyRoleSummary = {
  role_key: string;
  name: string;
  scope: "account";
  status: "active" | "draft";
  member_count: number;
  source: "api";
  permission_origin: string;
  permission_origin_role_key: string | null;
  account_scope: string[];
  permission_count: number;
  permissions: string[];
  is_template: boolean;
  template_name: string | null;
  updated_at: string | null;
};

type PermissionDefinitionsResponse = {
  total: number;
  modules: Record<string, PermissionDefinition[]>;
};

type AgencyPermissionsResponse = {
  agency_id: string;
  roles: AgencyRolePermission[];
};

type PermissionTemplateResponse = {
  id: string;
  name: string;
  description?: string;
  agency_id?: string;
  is_preset?: boolean;
  permissions: string[];
  permission_count: number;
};

type PermissionTemplatesResponse = {
  presets: PermissionTemplateResponse[];
  custom: PermissionTemplateResponse[];
};

type ErrorBody = {
  detail?: string | { message?: string };
  message?: string;
};

const MODULE_LABELS: Record<string, string> = {
  dashboard: "概览",
  conversations: "会话工作台",
  tickets: "工单管理",
  customers: "客户管理",
  sites: "站点管理",
  templates: "模板消息",
  reports: "报表中心",
  agents: "代理商管理",
  profile: "个人中心",
  roles: "角色管理",
  security: "安全中心",
};

const ROLE_LABELS: Record<string, string> = {
  agent: "代理商管理员",
  support: "客服",
  manager: "经理",
  finance: "财务",
};

function normalizeRoleName(roleName: string): string {
  return roleName
    .replace(/^custom_/, "")
    .replace(/_/g, " ")
    .trim();
}

function getRoleDisplayName(roleName: string, templateName: string | null): string {
  return ROLE_LABELS[roleName] ?? templateName ?? normalizeRoleName(roleName) ?? roleName;
}

function getModuleLabel(module: string): string {
  return MODULE_LABELS[module] ?? module;
}

function buildHeaders(contentType?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = adminAuth.getAccessToken();
  if (contentType) {
    headers["Content-Type"] = contentType;
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function extractErrorMessage(errorBody: ErrorBody, status: number): string {
  if (typeof errorBody.detail === "string" && errorBody.detail.trim()) {
    return errorBody.detail;
  }
  if (
    errorBody.detail &&
    typeof errorBody.detail === "object" &&
    typeof errorBody.detail.message === "string" &&
    errorBody.detail.message.trim()
  ) {
    return errorBody.detail.message;
  }
  if (typeof errorBody.message === "string" && errorBody.message.trim()) {
    return errorBody.message;
  }
  return `HTTP ${status}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
    });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({} as ErrorBody));
      const message = extractErrorMessage(errorBody as ErrorBody, response.status);
      throw new Error(message);
    }
    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

async function requestOptionalJson<T>(path: string, init?: RequestInit): Promise<T | null> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
    });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({} as ErrorBody));
      const message = extractErrorMessage(errorBody as ErrorBody, response.status);
      throw new Error(message);
    }
    if (response.status === 204) {
      return null;
    }
    const body = await response.text();
    if (!body.trim()) {
      return null;
    }
    return JSON.parse(body) as T;
  } finally {
    clearTimeout(timeout);
  }
}

function normalizePermissionTemplate(
  template: PermissionTemplateResponse,
  isPreset: boolean,
): PermissionTemplate {
  return {
    id: template.id,
    name: template.name,
    description: template.description ?? null,
    agency_id: template.agency_id ?? null,
    is_preset: isPreset,
    permissions: template.permissions ?? [],
    permission_count: template.permission_count ?? (template.permissions ?? []).length,
  };
}

export async function resolveCurrentAgencyId(): Promise<string | null> {
  const currentUser = adminAuth.getCurrentUser();
  if (currentUser?.agency_id) {
    return currentUser.agency_id;
  }
  const me = await adminAuth.getMe().catch(() => null);
  return me?.agency_id ?? null;
}

export async function listPermissionDefinitions(): Promise<PermissionModule[]> {
  const data = await requestJson<PermissionDefinitionsResponse>("/api/permissions/definitions", {
    headers: buildHeaders(),
  });
  return Object.entries(data.modules)
    .map(([module, permissions]) => ({
      module,
      label: getModuleLabel(module),
      permissions,
    }))
    .sort((left, right) => left.module.localeCompare(right.module, "zh-CN"));
}

export function flattenPermissionCodes(modules: PermissionModule[]): string[] {
  const codes = new Set<string>();
  modules.forEach((module) => {
    module.permissions.forEach((permission) => {
      codes.add(permission.code);
    });
  });
  return Array.from(codes);
}

export async function listAgencyRolePermissions(agencyId: string): Promise<AgencyRolePermission[]> {
  const data = await requestJson<AgencyPermissionsResponse>(
    `/api/permissions/agency/${encodeURIComponent(agencyId)}`,
    { headers: buildHeaders() },
  );
  return data.roles ?? [];
}

export async function listAgencyGrantedPermissions(agencyId: string): Promise<AgencyGrantedPermissions> {
  return requestJson<AgencyGrantedPermissions>(
    `/api/agents/${encodeURIComponent(agencyId)}/granted-permissions`,
    { headers: buildHeaders() },
  );
}

export async function updateAgencyGrantedPermissions(
  agencyId: string,
  permissions: string[],
): Promise<AgencyGrantedPermissions> {
  return requestJson<AgencyGrantedPermissions>(
    `/api/agents/${encodeURIComponent(agencyId)}/granted-permissions`,
    {
      method: "PUT",
      headers: buildHeaders("application/json"),
      body: JSON.stringify({ permissions }),
    },
  );
}

export async function updateAgencyRolePermissions(
  agencyId: string,
  roleName: string,
  permissions: string[],
): Promise<AgencyRolePermissionUpdateResult> {
  return requestJson<AgencyRolePermissionUpdateResult>(
    `/api/permissions/agency/${encodeURIComponent(agencyId)}`,
    {
      method: "PUT",
      headers: buildHeaders("application/json"),
      body: JSON.stringify({
        role_name: roleName,
        permissions,
      }),
    },
  );
}

export async function listPermissionTemplates(): Promise<PermissionTemplateCollection> {
  const data = await requestJson<PermissionTemplatesResponse>("/api/permissions/templates", {
    headers: buildHeaders(),
  });
  const presets = (data.presets ?? []).map((template) =>
    normalizePermissionTemplate(template, true),
  );
  const custom = (data.custom ?? []).map((template) =>
    normalizePermissionTemplate(template, false),
  );
  return {
    presets,
    custom,
    all: [...presets, ...custom],
  };
}

export async function applyPermissionTemplate(
  input: ApplyPermissionTemplateInput,
): Promise<ApplyPermissionTemplateResult> {
  return requestJson<ApplyPermissionTemplateResult>("/api/permissions/apply-template", {
    method: "POST",
    headers: buildHeaders("application/json"),
    body: JSON.stringify({
      agency_id: input.agencyId,
      template_id: input.templateId,
      target_role: input.targetRole,
    }),
  });
}

export async function createCustomRole(
  input: CreateCustomRoleInput,
): Promise<CreateCustomRoleResult> {
  return requestJson<CreateCustomRoleResult>("/api/permissions/custom-role", {
    method: "POST",
    headers: buildHeaders("application/json"),
    body: JSON.stringify({
      agency_id: input.agencyId,
      role_name: input.roleName,
      permissions: input.permissions,
    }),
  });
}

export async function copyAgencyPermissions(
  sourceAgencyId: string,
  targetAgencyId: string,
): Promise<CopyAgencyPermissionsResult> {
  return requestJson<CopyAgencyPermissionsResult>("/api/permissions/copy", {
    method: "POST",
    headers: buildHeaders("application/json"),
    body: JSON.stringify({
      source_agency_id: sourceAgencyId,
      target_agency_id: targetAgencyId,
    }),
  });
}

export async function deleteAgencyRole(
  agencyId: string,
  roleName: string,
): Promise<DeleteAgencyRoleResult> {
  const data = await requestOptionalJson<DeleteAgencyRoleResult>(
    `/api/permissions/agency/${encodeURIComponent(agencyId)}/roles/${encodeURIComponent(roleName)}`,
    {
      method: "DELETE",
      headers: buildHeaders(),
    },
  );
  return (
    data ?? {
      status: "ok",
      agency_id: agencyId,
      role_name: roleName,
    }
  );
}

export async function listAgencyRoleSummaries(agencyId: string): Promise<AgencyRoleSummary[]> {
  const roles = await listAgencyRolePermissions(agencyId);

  const roleMap = new Map<string, AgencyRolePermission>();
  roles.forEach((role) => {
    roleMap.set(role.role_name, role);
  });

  const roleKeys = new Set<string>(roles.map((role) => role.role_name));

  return Array.from(roleKeys)
    .map((roleKey) => {
      const role = roleMap.get(roleKey);
      const permissions = role?.permissions ?? [];
      const hasConfig = Boolean(role?.id);
      return {
        role_key: roleKey,
        name: getRoleDisplayName(roleKey, role?.template_name ?? null),
        scope: "account" as const,
        status: hasConfig ? ("active" as const) : ("draft" as const),
        member_count: role?.member_count ?? 0,
        source: "api" as const,
        permission_origin: role?.is_template
          ? "template"
          : role?.template_name
            ? "template_applied"
            : hasConfig
              ? "custom"
              : "unconfigured",
        permission_origin_role_key: role?.template_name ?? null,
        account_scope: [agencyId],
        permission_count: permissions.length,
        permissions,
        is_template: role?.is_template ?? false,
        template_name: role?.template_name ?? null,
        updated_at: role?.updated_at ?? null,
      };
    })
    .sort((left, right) => {
      if (left.role_key === "agent" && right.role_key !== "agent") return -1;
      if (right.role_key === "agent" && left.role_key !== "agent") return 1;
      if (right.member_count !== left.member_count) return right.member_count - left.member_count;
      return left.name.localeCompare(right.name, "zh-CN");
    });
}

