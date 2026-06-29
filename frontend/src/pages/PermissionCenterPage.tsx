import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { EmptyGuide, PageShell } from "../components/PageShell";
import { showError, showSuccess } from "../components/Feedback";
import { usePermissions } from "../hooks/usePermissions";
import {
  applyPermissionTemplate,
  createCustomRole,
  deleteAgencyRole,
  flattenPermissionCodes,
  listAgencyGrantedPermissions,
  listAgencyRolePermissions,
  listPermissionDefinitions,
  listPermissionTemplates,
  resolveCurrentAgencyId,
  updateAgencyGrantedPermissions,
  updateAgencyRolePermissions,
  type AgencyRolePermission,
  type PermissionModule,
  type PermissionTemplate,
} from "../services/permissions";

type RoleEditorValues = {
  roleName: string;
  permissions: string[];
};

type TemplateApplyValues = {
  templateId: string;
  targetRole: string;
};

function getRoleLabel(roleName: string): string {
  if (roleName === "agent") return "代理商管理员";
  if (roleName === "support") return "客服";
  if (roleName === "manager") return "经理";
  if (roleName === "finance") return "财务";
  return roleName;
}

export function PermissionCenterPage(): JSX.Element {
  const { can, loading: permissionLoading } = usePermissions();
  const canView = can("roles.view");
  const canEdit = can("roles.edit_perms");
  const canCreate = can("roles.create");
  const canDelete = can("roles.delete");

  const [agencyId, setAgencyId] = useState("");
  const [definitions, setDefinitions] = useState<PermissionModule[]>([]);
  const [grantedPermissions, setGrantedPermissions] = useState<string[]>([]);
  const [roles, setRoles] = useState<AgencyRolePermission[]>([]);
  const [templates, setTemplates] = useState<PermissionTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [poolSaving, setPoolSaving] = useState(false);
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<AgencyRolePermission | null>(null);
  const [roleSaving, setRoleSaving] = useState(false);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [roleForm] = Form.useForm<RoleEditorValues>();
  const [templateForm] = Form.useForm<TemplateApplyValues>();

  useEffect(() => {
    void resolveCurrentAgencyId().then((resolvedAgencyId) => {
      if (resolvedAgencyId) {
        setAgencyId((current) => current || resolvedAgencyId);
      }
    });
  }, []);

  const loadPage = useCallback(async (): Promise<void> => {
    if (!canView) {
      return;
    }
    if (!agencyId.trim()) {
      setDefinitions(await listPermissionDefinitions().catch(() => []));
      setRoles([]);
      setTemplates([]);
      setGrantedPermissions([]);
      return;
    }
    setLoading(true);
    setPageError(null);
    try {
      const [modules, granted, agencyRoles, templateCollection] = await Promise.all([
        listPermissionDefinitions(),
        listAgencyGrantedPermissions(agencyId.trim()),
        listAgencyRolePermissions(agencyId.trim()),
        listPermissionTemplates(),
      ]);
      setDefinitions(modules);
      setGrantedPermissions(granted.permissions);
      setRoles(agencyRoles);
      setTemplates(templateCollection.all);
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载权限中心失败";
      setPageError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [agencyId, canView]);

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  const allPermissionCodes = useMemo(() => flattenPermissionCodes(definitions), [definitions]);
  const customRoleCount = useMemo(
    () => roles.filter((role) => role.role_name.startsWith("custom_")).length,
    [roles],
  );

  const openCreateRole = useCallback((): void => {
    setEditingRole(null);
    roleForm.setFieldsValue({ roleName: "", permissions: [] });
    setRoleModalOpen(true);
  }, [roleForm]);

  const openEditRole = useCallback((role: AgencyRolePermission): void => {
    setEditingRole(role);
    roleForm.setFieldsValue({ roleName: role.role_name, permissions: role.permissions });
    setRoleModalOpen(true);
  }, [roleForm]);

  const handleSaveGrantedPermissions = useCallback(async (): Promise<void> => {
    if (!agencyId.trim()) {
      showError("请先输入 agency_id");
      return;
    }
    setPoolSaving(true);
    try {
      const result = await updateAgencyGrantedPermissions(agencyId.trim(), grantedPermissions);
      setGrantedPermissions(result.permissions);
      showSuccess("权限池已保存");
    } catch (error) {
      showError(error instanceof Error ? error.message : "保存权限池失败");
    } finally {
      setPoolSaving(false);
    }
  }, [agencyId, grantedPermissions]);

  const handleSaveRole = useCallback(async (): Promise<void> => {
    if (!agencyId.trim()) {
      showError("请先输入 agency_id");
      return;
    }
    const values = await roleForm.validateFields();
    setRoleSaving(true);
    try {
      if (editingRole && editingRole.role_name.startsWith("custom_")) {
        await updateAgencyRolePermissions(agencyId.trim(), values.roleName, values.permissions);
      } else if (editingRole) {
        await updateAgencyRolePermissions(agencyId.trim(), editingRole.role_name, values.permissions);
      } else if (values.roleName.startsWith("custom_")) {
        await createCustomRole({
          agencyId: agencyId.trim(),
          roleName: values.roleName,
          permissions: values.permissions,
        });
      } else {
        await updateAgencyRolePermissions(agencyId.trim(), values.roleName, values.permissions);
      }
      showSuccess("角色权限已保存");
      setRoleModalOpen(false);
      await loadPage();
    } catch (error) {
      showError(error instanceof Error ? error.message : "保存角色失败");
    } finally {
      setRoleSaving(false);
    }
  }, [agencyId, editingRole, loadPage, roleForm]);

  const handleDeleteRole = useCallback(async (roleName: string): Promise<void> => {
    if (!agencyId.trim()) {
      showError("请先输入 agency_id");
      return;
    }
    try {
      await deleteAgencyRole(agencyId.trim(), roleName);
      showSuccess("自定义角色已删除");
      await loadPage();
    } catch (error) {
      showError(error instanceof Error ? error.message : "删除角色失败");
    }
  }, [agencyId, loadPage]);

  const handleApplyTemplate = useCallback(async (): Promise<void> => {
    if (!agencyId.trim()) {
      showError("请先输入 agency_id");
      return;
    }
    const values = await templateForm.validateFields();
    setTemplateSaving(true);
    try {
      await applyPermissionTemplate({
        agencyId: agencyId.trim(),
        templateId: values.templateId,
        targetRole: values.targetRole,
      });
      showSuccess("模板已应用");
      setTemplateModalOpen(false);
      await loadPage();
    } catch (error) {
      showError(error instanceof Error ? error.message : "应用模板失败");
    } finally {
      setTemplateSaving(false);
    }
  }, [agencyId, loadPage, templateForm]);

  if (!permissionLoading && !canView) {
    return (
      <PageShell title="权限中心" subtitle="四级授权、权限池与角色配置">
        <EmptyGuide
          icon="馃敀"
          title="缺少 roles.view 权限"
          description="当前账号无法读取权限定义与角色配置。"
        />
      </PageShell>
    );
  }

  const availableRolePermissions = grantedPermissions.length > 0 ? grantedPermissions : allPermissionCodes;

  return (
    <PageShell
      title="权限中心"
      subtitle="按 agency_id 管理权限池、角色授权和模板应用。"
      actions={(
        <Space wrap>
          <Input
            style={{ width: 240 }}
            value={agencyId}
            placeholder="输入 agency_id"
            onChange={(event) => setAgencyId(event.target.value)}
          />
          <Button loading={loading} onClick={() => void loadPage()}>
            刷新
          </Button>
          <Button type="primary" disabled={!canCreate} onClick={openCreateRole}>
            新建角色
          </Button>
          <Button disabled={!canEdit} onClick={() => setTemplateModalOpen(true)}>
            应用模板
          </Button>
        </Space>
      )}
      stats={(
        <Space wrap size={12}>
          <Card size="small"><Statistic title="权限模块" value={definitions.length} /></Card>
          <Card size="small"><Statistic title="权限池规模" value={grantedPermissions.length} /></Card>
          <Card size="small"><Statistic title="角色配置数" value={roles.length} /></Card>
          <Card size="small"><Statistic title="自定义角色" value={customRoleCount} /></Card>
        </Space>
      )}
    >
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        {pageError ? <Alert type="error" showIcon message={pageError} /> : null}
        {!agencyId.trim() ? (
          <Alert
            type="info"
            showIcon
            message="请先输入 agency_id"
            description="权限中心接口是 agency 作用域；如果当前账号已有 agency_id，页面会自动回填。"
          />
        ) : null}
        <Tabs
          items={[
            {
              key: "grants",
              label: "权限池",
              children: (
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
                  <Alert
                    type="info"
                    showIcon
                    message="权限池说明"
                    description="角色配置必须是权限池的子集。没有后端成功返回时，页面不会显示假保存成功。"
                  />
                  {definitions.map((module) => (
                    <Card key={module.module} size="small" title={module.label}>
                      <Checkbox.Group
                        style={{ width: "100%" }}
                        value={grantedPermissions}
                        onChange={(nextValues) => setGrantedPermissions(nextValues as string[])}
                        disabled={!canEdit}
                      >
                        <Space direction="vertical" style={{ width: "100%" }}>
                          {module.permissions.map((permission) => (
                            <Checkbox key={permission.code} value={permission.code}>
                              <Space size={8}>
                                <Typography.Text>{permission.label}</Typography.Text>
                                <Typography.Text type="secondary">{permission.code}</Typography.Text>
                                {permission.super_admin_only ? <Tag color="warning">仅超级管理员</Tag> : null}
                              </Space>
                            </Checkbox>
                          ))}
                        </Space>
                      </Checkbox.Group>
                    </Card>
                  ))}
                  <Button type="primary" loading={poolSaving} disabled={!canEdit} onClick={() => void handleSaveGrantedPermissions()}>
                    保存权限池
                  </Button>
                </Space>
              ),
            },
            {
              key: "roles",
              label: "角色授权",
              children: (
                <Table
                  rowKey={(record) => record.id ?? record.role_name}
                  loading={loading}
                  dataSource={roles}
                  locale={{ emptyText: <Empty description="当前 agency 暂无角色配置" /> }}
                  pagination={false}
                  columns={[
                    {
                      title: "角色",
                      dataIndex: "role_name",
                      render: (value: string, record: AgencyRolePermission) => (
                        <Space>
                          <Typography.Text strong>{getRoleLabel(value)}</Typography.Text>
                          {record.is_template ? <Tag>模板</Tag> : null}
                          {record.template_name ? <Tag color="processing">{record.template_name}</Tag> : null}
                        </Space>
                      ),
                    },
                    { title: "成员数", dataIndex: "member_count", width: 90 },
                    {
                      title: "权限数",
                      render: (_: unknown, record: AgencyRolePermission) => record.permissions.length,
                      width: 90,
                    },
                    {
                      title: "权限预览",
                      render: (_: unknown, record: AgencyRolePermission) => (
                        <Typography.Text type="secondary">
                          {record.permissions.slice(0, 4).join(", ") || "未配置"}
                        </Typography.Text>
                      ),
                    },
                    {
                      title: "操作",
                      width: 180,
                      render: (_: unknown, record: AgencyRolePermission) => (
                        <Space>
                          <Button type="link" disabled={!canEdit} onClick={() => openEditRole(record)}>
                            编辑
                          </Button>
                          {record.role_name.startsWith("custom_") ? (
                            <Button
                              type="link"
                              danger
                              disabled={!canDelete}
                              onClick={() => void handleDeleteRole(record.role_name)}
                            >
                              删除
                            </Button>
                          ) : null}
                        </Space>
                      ),
                    },
                  ]}
                />
              ),
            },
            {
              key: "templates",
              label: "权限模板",
              children: (
                <Table
                  rowKey="id"
                  loading={loading}
                  dataSource={templates}
                  locale={{ emptyText: <Empty description="没有可用模板" /> }}
                  pagination={false}
                  columns={[
                    { title: "模板名", dataIndex: "name" },
                    { title: "来源", render: (_: unknown, record: PermissionTemplate) => (record.is_preset ? "预置" : "代理商") },
                    { title: "权限数", dataIndex: "permission_count", width: 90 },
                    {
                      title: "权限预览",
                      render: (_: unknown, record: PermissionTemplate) => (
                        <Typography.Text type="secondary">
                          {record.permissions.slice(0, 4).join(", ") || "空模板"}
                        </Typography.Text>
                      ),
                    },
                  ]}
                />
              ),
            },
          ]}
        />

        <Modal
          title={editingRole ? `编辑角色 ${editingRole.role_name}` : "新建角色"}
          open={roleModalOpen}
          onCancel={() => setRoleModalOpen(false)}
          onOk={() => void handleSaveRole()}
          okText="保存角色"
          confirmLoading={roleSaving}
        >
          <Form form={roleForm} layout="vertical">
            <Form.Item
              label="角色键"
              name="roleName"
              rules={[{ required: true, message: "请输入角色键" }]}
              extra="自定义角色必须以 custom_ 开头；内置角色可直接输入 agent/support/manager/finance。"
            >
              <Input disabled={Boolean(editingRole)} />
            </Form.Item>
            <Form.Item
              label="权限列表"
              name="permissions"
              rules={[{ required: true, message: "至少选择一个权限" }]}
            >
              <Select
                mode="multiple"
                showSearch
                optionFilterProp="label"
                options={availableRolePermissions.map((permissionCode) => ({
                  label: permissionCode,
                  value: permissionCode,
                }))}
              />
            </Form.Item>
          </Form>
        </Modal>

        <Modal
          title="应用权限模板"
          open={templateModalOpen}
          onCancel={() => setTemplateModalOpen(false)}
          onOk={() => void handleApplyTemplate()}
          okText="应用模板"
          confirmLoading={templateSaving}
        >
          <Form form={templateForm} layout="vertical">
            <Form.Item label="模板" name="templateId" rules={[{ required: true, message: "请选择模板" }]}>
              <Select
                showSearch
                optionFilterProp="label"
                options={templates.map((template) => ({
                  label: `${template.name} (${template.permission_count})`,
                  value: template.id,
                }))}
              />
            </Form.Item>
            <Form.Item
              label="目标角色"
              name="targetRole"
              rules={[{ required: true, message: "请输入目标角色" }]}
            >
              <Input placeholder="support 或 custom_xxx" />
            </Form.Item>
          </Form>
        </Modal>
      </Space>
    </PageShell>
  );
}
