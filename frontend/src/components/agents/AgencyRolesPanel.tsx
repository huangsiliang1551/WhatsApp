import { useCallback, useEffect, useMemo, useRef, useState, type JSX, type ReactNode } from "react";
import {
  Button,
  Card,
  Checkbox,
  Collapse,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";

import { showError, showSuccess } from "../Feedback";
import {
  applyPermissionTemplate,
  createCustomRole,
  deleteAgencyRole,
  listAgencyRoleSummaries,
  listPermissionDefinitions,
  listPermissionTemplates,
  updateAgencyRolePermissions,
  type AgencyRoleSummary,
  type PermissionModule,
  type PermissionTemplateCollection,
} from "../../services/permissions";

type AgencyRolesPanelProps = {
  agencyId: string;
  initialRoles?: AgencyRoleSummary[] | null;
  onRolesChanged?: (roles: AgencyRoleSummary[]) => Promise<void> | void;
  initialRoleKey?: string | null;
  onSelectedRoleChange?: (roleKey: string | null) => void;
  permissionEditingDisabled?: boolean;
  extraActions?: ReactNode;
};

function normalizeCustomRoleKey(rawRoleKey: string): string {
  const normalized = rawRoleKey
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_ -]/g, "")
    .replace(/[\s-]+/g, "_")
    .replace(/^custom_/, "")
    .replace(/^_+|_+$/g, "");
  if (!normalized) {
    throw new Error("角色标识不能为空。");
  }
  return `custom_${normalized}`;
}

function canDeleteRole(role: AgencyRoleSummary | null): boolean {
  if (!role) return false;
  return role.role_key.startsWith("custom_") && role.member_count === 0;
}

function getDefaultTemplateId(options: Array<{ value: string }>): string | undefined {
  return options.length === 1 ? options[0]?.value : undefined;
}

function getAssignableModules(definitions: PermissionModule[]): PermissionModule[] {
  return definitions
    .map((module) => ({
      ...module,
      permissions: module.permissions.filter((permission) => !permission.super_admin_only),
    }))
    .filter((module) => module.permissions.length > 0);
}

function mergePermissionCodes(previous: string[], nextCodes: string[], checked: boolean): string[] {
  if (checked) {
    return Array.from(new Set([...previous, ...nextCodes])).sort();
  }
  return previous.filter((item) => !nextCodes.includes(item));
}

function sanitizePermissionCodes(permissionCodes: string[], allowedCodes: string[]): string[] {
  const allowed = new Set(allowedCodes);
  return permissionCodes.filter((code) => allowed.has(code)).sort();
}

function sanitizeRoles(roles: AgencyRoleSummary[], allowedCodes: string[]): AgencyRoleSummary[] {
  return roles.map((role) => {
    const permissions = sanitizePermissionCodes(role.permissions, allowedCodes);
    return {
      ...role,
      permissions,
      permission_count: permissions.length,
    };
  });
}

type PermissionModuleSelectorProps = {
  modules: PermissionModule[];
  selectedPermissions: string[];
  onChange: (updater: (previous: string[]) => string[]) => void;
  emptyText: string;
  keyPrefix: string;
  disabled?: boolean;
};

function PermissionModuleSelector({
  modules,
  selectedPermissions,
  onChange,
  emptyText,
  keyPrefix,
  disabled = false,
}: PermissionModuleSelectorProps): JSX.Element {
  if (modules.length === 0) {
    return <Empty description={emptyText} />;
  }

  return (
    <>
      {modules.map((module) => {
        const moduleLabel = module.label || module.module;
        const moduleCodes = module.permissions.map((permission) => permission.code);
        return (
          <Collapse
            key={`${keyPrefix}-${module.module}`}
            defaultActiveKey={[module.module]}
            items={[
              {
                key: module.module,
                label: <Typography.Text strong>{moduleLabel}</Typography.Text>,
                children: (
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Space wrap>
                      <Button
                        size="small"
                        disabled={disabled}
                        onClick={() => onChange((previous) => mergePermissionCodes(previous, moduleCodes, true))}
                      >
                        {`${moduleLabel}全选`}
                      </Button>
                      <Button
                        size="small"
                        disabled={disabled}
                        onClick={() => onChange((previous) => mergePermissionCodes(previous, moduleCodes, false))}
                      >
                        {`${moduleLabel}清空`}
                      </Button>
                    </Space>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                        gap: 8,
                      }}
                    >
                      {module.permissions.map((permission) => (
                        <Checkbox
                          key={`${keyPrefix}-${permission.code}`}
                          checked={selectedPermissions.includes(permission.code)}
                          disabled={disabled}
                          onChange={(event) => {
                            const checked = event.target.checked;
                            onChange((previous) => mergePermissionCodes(previous, [permission.code], checked));
                          }}
                        >
                          {permission.label}
                        </Checkbox>
                      ))}
                    </div>
                  </Space>
                ),
              },
            ]}
          />
        );
      })}
    </>
  );
}

export function AgencyRolesPanel({
  agencyId,
  initialRoles = null,
  onRolesChanged,
  initialRoleKey = null,
  onSelectedRoleChange,
  permissionEditingDisabled = false,
  extraActions,
}: AgencyRolesPanelProps): JSX.Element {
  const usedInitialRolesRef = useRef(false);
  const [roles, setRoles] = useState<AgencyRoleSummary[]>([]);
  const [definitions, setDefinitions] = useState<PermissionModule[]>([]);
  const [templates, setTemplates] = useState<PermissionTemplateCollection>({
    presets: [],
    custom: [],
    all: [],
  });
  const [selectedRoleKey, setSelectedRoleKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [permissionDrawerOpen, setPermissionDrawerOpen] = useState(false);
  const [editingPermissions, setEditingPermissions] = useState<string[]>([]);
  const [savingPermissions, setSavingPermissions] = useState(false);

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createSaving, setCreateSaving] = useState(false);
  const [createForm] = Form.useForm();

  const [applyModalOpen, setApplyModalOpen] = useState(false);
  const [applySaving, setApplySaving] = useState(false);
  const [applyForm] = Form.useForm();

  const [pendingDeleteRole, setPendingDeleteRole] = useState<AgencyRoleSummary | null>(null);
  const [deleteSaving, setDeleteSaving] = useState(false);

  const selectedRole = useMemo(
    () => roles.find((role) => role.role_key === selectedRoleKey) ?? null,
    [roles, selectedRoleKey],
  );

  const templateOptions = useMemo(
    () => [...templates.presets, ...templates.custom].map((template) => ({ label: template.name, value: template.id })),
    [templates],
  );

  const roleOptions = useMemo(
    () => roles.map((role) => ({ label: `${role.name} (${role.role_key})`, value: role.role_key })),
    [roles],
  );

  const assignableModules = useMemo(() => getAssignableModules(definitions), [definitions]);
  const allAssignablePermissionCodes = useMemo(
    () => assignableModules.flatMap((module) => module.permissions.map((permission) => permission.code)),
    [assignableModules],
  );
  const permissionManagementDisabled = permissionEditingDisabled || assignableModules.length === 0;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const shouldUseInitialRoles = !usedInitialRolesRef.current && Array.isArray(initialRoles);
      const [nextRoles, nextDefinitions, nextTemplates] = shouldUseInitialRoles
        ? await Promise.all([
            Promise.resolve(initialRoles),
            listPermissionDefinitions(),
            listPermissionTemplates(),
          ])
        : await Promise.all([
            listAgencyRoleSummaries(agencyId),
            listPermissionDefinitions(),
            listPermissionTemplates(),
          ]);

      const nextAssignableModules = getAssignableModules(nextDefinitions);
      const nextAllowedCodes = nextAssignableModules.flatMap((module) =>
        module.permissions.map((permission) => permission.code),
      );
      const sanitizedRoles = sanitizeRoles(nextRoles, nextAllowedCodes);

      usedInitialRolesRef.current = true;
      setRoles(sanitizedRoles);
      setDefinitions(nextDefinitions);
      setTemplates(nextTemplates);
      setSelectedRoleKey((previous) =>
        sanitizedRoles.find((role) => role.role_key === initialRoleKey)?.role_key ??
        sanitizedRoles.find((role) => role.role_key === previous)?.role_key ??
        sanitizedRoles[0]?.role_key ??
        null,
      );
      await onRolesChanged?.(sanitizedRoles);
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "加载角色失败");
      setRoles([]);
      setDefinitions([]);
      setTemplates({ presets: [], custom: [], all: [] });
    } finally {
      setLoading(false);
    }
  }, [agencyId, initialRoleKey, initialRoles, onRolesChanged]);

  useEffect(() => {
    usedInitialRolesRef.current = false;
    void load();
  }, [agencyId, load]);

  useEffect(() => {
    onSelectedRoleChange?.(selectedRoleKey);
  }, [onSelectedRoleChange, selectedRoleKey]);

  const handleSavePermissions = useCallback(async () => {
    if (!selectedRole || permissionManagementDisabled) return;
    setSavingPermissions(true);
    try {
      const nextPermissions = sanitizePermissionCodes(editingPermissions, allAssignablePermissionCodes);
      await updateAgencyRolePermissions(agencyId, selectedRole.role_key, nextPermissions);
      setEditingPermissions(nextPermissions);
      showSuccess("角色权限已更新");
      setPermissionDrawerOpen(false);
      await load();
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "保存角色权限失败");
    } finally {
      setSavingPermissions(false);
    }
  }, [agencyId, allAssignablePermissionCodes, editingPermissions, load, permissionManagementDisabled, selectedRole]);

  const handleCreateRole = useCallback(async (values: { roleKey: string }) => {
    if (permissionManagementDisabled) return;
    setCreateSaving(true);
    try {
      const nextPermissions = sanitizePermissionCodes(editingPermissions, allAssignablePermissionCodes);
      await createCustomRole({
        agencyId,
        roleName: normalizeCustomRoleKey(values.roleKey),
        permissions: nextPermissions,
      });
      showSuccess("自定义角色已创建");
      setCreateModalOpen(false);
      createForm.resetFields();
      setEditingPermissions([]);
      await load();
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "创建角色失败");
    } finally {
      setCreateSaving(false);
    }
  }, [agencyId, allAssignablePermissionCodes, createForm, editingPermissions, load, permissionManagementDisabled]);

  const handleApplyTemplate = useCallback(async (values: { templateId: string; targetRole: string }) => {
    if (permissionManagementDisabled) return;
    setApplySaving(true);
    try {
      await applyPermissionTemplate({
        agencyId,
        templateId: values.templateId,
        targetRole: values.targetRole,
      });
      showSuccess("模板已应用");
      setApplyModalOpen(false);
      await load();
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "应用模板失败");
    } finally {
      setApplySaving(false);
    }
  }, [agencyId, load, permissionManagementDisabled]);

  const handleConfirmDeleteRole = useCallback(async () => {
    if (!pendingDeleteRole) return;
    setDeleteSaving(true);
    try {
      await deleteAgencyRole(agencyId, pendingDeleteRole.role_key);
      showSuccess("角色已删除");
      setPendingDeleteRole(null);
      if (selectedRoleKey === pendingDeleteRole.role_key) {
        setSelectedRoleKey(null);
      }
      await load();
    } catch (cause) {
      showError(cause instanceof Error ? cause.message : "删除角色失败");
    } finally {
      setDeleteSaving(false);
    }
  }, [agencyId, load, pendingDeleteRole, selectedRoleKey]);

  const columns = useMemo(
    () => [
      {
        title: "角色",
        dataIndex: "name",
        key: "name",
        render: (_: unknown, role: AgencyRoleSummary) => (
          <Button type="link" onClick={() => setSelectedRoleKey(role.role_key)}>
            {role.name}
          </Button>
        ),
      },
      { title: "角色标识", dataIndex: "role_key", key: "role_key", width: 180 },
      { title: "成员数", dataIndex: "member_count", key: "member_count", width: 90 },
      { title: "权限数", dataIndex: "permission_count", key: "permission_count", width: 100 },
      {
        title: "来源",
        dataIndex: "permission_origin",
        key: "permission_origin",
        width: 140,
        render: (value: string) => <Tag>{value}</Tag>,
      },
      {
        title: "操作",
        key: "actions",
        width: 320,
        render: (_: unknown, role: AgencyRoleSummary) => (
          <Space wrap>
            <Button
              size="small"
              disabled={permissionManagementDisabled}
              onClick={() => {
                if (permissionManagementDisabled) return;
                setSelectedRoleKey(role.role_key);
                setEditingPermissions(sanitizePermissionCodes(role.permissions, allAssignablePermissionCodes));
                setPermissionDrawerOpen(true);
              }}
            >
              编辑权限
            </Button>
            <Button
              size="small"
              disabled={permissionManagementDisabled}
              onClick={() => {
                if (permissionManagementDisabled) return;
                setSelectedRoleKey(role.role_key);
                applyForm.setFieldsValue({
                  targetRole: role.role_key,
                  templateId: getDefaultTemplateId(templateOptions),
                });
                setApplyModalOpen(true);
              }}
            >
              套用模板
            </Button>
            <Button
              size="small"
              danger
              disabled={permissionManagementDisabled || !canDeleteRole(role)}
              onClick={() => setPendingDeleteRole(role)}
            >
              删除角色
            </Button>
          </Space>
        ),
      },
    ],
    [allAssignablePermissionCodes, applyForm, permissionManagementDisabled, templateOptions],
  );

  const selectedPermissionCodes = permissionDrawerOpen ? editingPermissions : selectedRole?.permissions ?? [];

  return (
    <>
      <Card
        size="small"
        style={{ marginBottom: 16 }}
        extra={(
          <Space wrap>
            <Button onClick={() => void load()}>刷新</Button>
            <Button
              type="primary"
              disabled={permissionManagementDisabled}
              onClick={() => {
                if (permissionManagementDisabled) return;
                setEditingPermissions([]);
                createForm.resetFields();
                setCreateModalOpen(true);
              }}
            >
              新建角色
            </Button>
            <Button
              disabled={!selectedRole || permissionManagementDisabled}
              onClick={() => {
                if (!selectedRole || permissionManagementDisabled) return;
                setEditingPermissions(sanitizePermissionCodes(selectedRole.permissions, allAssignablePermissionCodes));
                setPermissionDrawerOpen(true);
              }}
            >
              编辑权限
            </Button>
            {extraActions}
          </Space>
        )}
      >
        {selectedRole ? (
          <Descriptions column={2} size="small" title="当前角色">
            <Descriptions.Item label="角色名称">{selectedRole.name}</Descriptions.Item>
            <Descriptions.Item label="角色标识">{selectedRole.role_key}</Descriptions.Item>
            <Descriptions.Item label="成员数">{selectedRole.member_count}</Descriptions.Item>
            <Descriptions.Item label="权限数">{selectedRole.permission_count}</Descriptions.Item>
            <Descriptions.Item label="来源">{selectedRole.permission_origin}</Descriptions.Item>
            <Descriptions.Item label="模板">{selectedRole.template_name ?? "-"}</Descriptions.Item>
          </Descriptions>
        ) : (
          <Empty description="暂无角色" />
        )}
      </Card>

      <Table
        rowKey="role_key"
        dataSource={roles}
        columns={columns}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true }}
        rowClassName={(record) => (record.role_key === selectedRoleKey ? "permission-role-selected" : "")}
        onRow={(record) => ({
          onClick: () => setSelectedRoleKey(record.role_key),
        })}
      />

      <Drawer
        title={selectedRole ? `${selectedRole.name} 权限` : "角色权限"}
        open={permissionDrawerOpen}
        onClose={() => setPermissionDrawerOpen(false)}
        width={720}
        extra={(
          <Space>
            <Button disabled={permissionManagementDisabled} onClick={() => setEditingPermissions(allAssignablePermissionCodes)}>
              全选
            </Button>
            <Button disabled={permissionManagementDisabled} onClick={() => setEditingPermissions([])}>
              清空
            </Button>
            <Button
              type="primary"
              loading={savingPermissions}
              disabled={permissionManagementDisabled}
              onClick={() => void handleSavePermissions()}
            >
              保存权限
            </Button>
          </Space>
        )}
      >
        <PermissionModuleSelector
          modules={assignableModules}
          selectedPermissions={selectedPermissionCodes}
          onChange={(updater) => setEditingPermissions((previous) => updater(previous))}
          emptyText="暂无可授予权限"
          keyPrefix="drawer"
          disabled={permissionManagementDisabled}
        />
      </Drawer>

      <Modal
        title="新建自定义角色"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => createForm.submit()}
        confirmLoading={createSaving}
        okText="创建"
      >
        <Form form={createForm} layout="vertical" onFinish={(values) => void handleCreateRole(values)}>
          <Form.Item
            label="角色标识"
            name="roleKey"
            rules={[{ required: true, message: "角色标识不能为空。" }]}
          >
            <Input aria-label="Role key" placeholder="quality" />
          </Form.Item>
          <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
            新角色会按 <code>custom_*</code> 规则创建。
          </Typography.Text>
          <Space wrap style={{ marginBottom: 12 }}>
            <Button size="small" disabled={permissionManagementDisabled} onClick={() => setEditingPermissions(allAssignablePermissionCodes)}>
              全选
            </Button>
            <Button size="small" disabled={permissionManagementDisabled} onClick={() => setEditingPermissions([])}>
              清空
            </Button>
          </Space>
          <PermissionModuleSelector
            modules={assignableModules}
            selectedPermissions={editingPermissions}
            onChange={(updater) => setEditingPermissions((previous) => updater(previous))}
            emptyText="暂无可授予权限"
            keyPrefix="create"
            disabled={permissionManagementDisabled}
          />
        </Form>
      </Modal>

      <Modal
        title="套用模板"
        open={applyModalOpen}
        onCancel={() => setApplyModalOpen(false)}
        onOk={() => applyForm.submit()}
        confirmLoading={applySaving}
        okText="应用"
      >
        <Form form={applyForm} layout="vertical" onFinish={(values) => void handleApplyTemplate(values)}>
          <Form.Item
            label="目标角色"
            name="targetRole"
            rules={[{ required: true, message: "请选择目标角色。" }]}
          >
            <Select options={roleOptions} />
          </Form.Item>
          <Form.Item label="模板" name="templateId" rules={[{ required: true, message: "请选择模板。" }]}>
            <Select aria-label="Template" options={templateOptions} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="删除角色"
        open={Boolean(pendingDeleteRole)}
        onCancel={() => {
          if (!deleteSaving) setPendingDeleteRole(null);
        }}
        onOk={() => void handleConfirmDeleteRole()}
        confirmLoading={deleteSaving}
        okText="删除"
      >
        <Typography.Text>
          {pendingDeleteRole ? `确认删除角色 ${pendingDeleteRole.role_key} 吗？` : "确认删除当前角色吗？"}
        </Typography.Text>
      </Modal>
    </>
  );
}
