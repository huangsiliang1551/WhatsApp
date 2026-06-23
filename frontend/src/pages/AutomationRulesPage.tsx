import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { Button, Form, Input, Modal, Select, Space, Table, Tag, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { PlusOutlined, ReloadOutlined } from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import {
  listAudienceRuleSets,
  createAudienceRuleSet,
  updateAudienceRuleSet,
  deleteAudienceRuleSet,
  listMetaAccounts,
} from "../services/api";
import type { AudienceRuleSet } from "../services/api";

// ── Constants ──

const STATUS_LABELS: Record<string, string> = { active: "启用", disabled: "停用" };
const STATUS_COLORS: Record<string, string> = { active: "green", disabled: "default" };

// ── Component ──

export function AutomationRulesPage(): JSX.Element {
  const [accounts, setAccounts] = useState<Array<{ account_id: string; display_name: string }>>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AudienceRuleSet | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  // ── Load accounts once ──
  useEffect(() => {
    listMetaAccounts({}).then(setAccounts).catch(() => { /* ignore */ });
  }, []);

  const accountOptions = useMemo(() => accounts.map((a) => ({ label: a.display_name, value: a.account_id })), [accounts]);

  // ── Fetch rules ──
  const fetchRules = useCallback(async () => {
    const rules = await listAudienceRuleSets();
    return { rules };
  }, []);
  const { data, loading, error, reload } = usePageData({ fetcher: fetchRules });
  const rules = data?.rules ?? [];

  // ── Stats ──
  const stats = (
    <Space size="middle" style={{ fontSize: 13 }}>
      <span>总规则 <Typography.Text strong>{rules.length}</Typography.Text></span>
      <span>启用 <Typography.Text strong style={{ color: "#52c41a" }}>{rules.filter((r) => r.status === "active").length}</Typography.Text></span>
      <span>停用 <Typography.Text strong style={{ color: "#999" }}>{rules.filter((r) => r.status === "disabled").length}</Typography.Text></span>
    </Space>
  );

  const actions = (
    <Space>
      <Button size="small" icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>刷新</Button>
      <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => { setEditingRule(null); form.resetFields(); setModalOpen(true); }}>创建规则</Button>
    </Space>
  );

  // ── Handlers ──

  const handleToggleStatus = async (rule: AudienceRuleSet) => {
    const newStatus = rule.status === "active" ? "disabled" : "active";
    try {
      await updateAudienceRuleSet(rule.id, { status: newStatus });
      showSuccess(`${rule.name} 已${newStatus === "active" ? "启用" : "停用"}`);
      void reload();
    } catch { showError("状态更新失败"); }
  };

  const handleDelete = async (rule: AudienceRuleSet) => {
    try {
      await deleteAudienceRuleSet(rule.id);
      showSuccess(`${rule.name} 已删除`);
      void reload();
    } catch { showError("删除失败"); }
  };

  const handleSave = async (values: { name: string; scope_type: string; scope_id?: string; description?: string; rules_json: string }) => {
    setSaving(true);
    try {
      let parsedJson: Record<string, unknown>;
      try { parsedJson = JSON.parse(values.rules_json); }
      catch { showError("JSON 格式错误，请检查"); setSaving(false); return; }

      const payload = {
        rule_key: editingRule?.rule_key ?? `rule-${Date.now()}`,
        name: values.name,
        scope_type: values.scope_type,
        scope_id: values.scope_id ?? undefined,
        status: "active",
        description: values.description ?? undefined,
        rules_json: parsedJson,
      };

      if (editingRule) {
        await updateAudienceRuleSet(editingRule.id, payload);
        showSuccess("规则已更新");
      } else {
        await createAudienceRuleSet(payload);
        showSuccess("规则已创建");
      }
      setModalOpen(false);
      form.resetFields();
      void reload();
    } catch { showError("保存失败"); }
    finally { setSaving(false); }
  };

  const handleEdit = (rule: AudienceRuleSet) => {
    setEditingRule(rule);
    form.setFieldsValue({
      name: rule.name,
      scope_type: rule.scope_type,
      scope_id: rule.scope_id ?? undefined,
      description: rule.description ?? "",
      rules_json: JSON.stringify(rule.rules_json, null, 2),
    });
    setModalOpen(true);
  };

  // ── Columns ──

  const columns = [
    { title: "名称", dataIndex: "name", key: "name", width: 160, ellipsis: true },
    { title: "账号", dataIndex: "scope_id", key: "scope_id", width: 100, render: (v: string | null) => v || "全局" },
    {
      title: "状态", dataIndex: "status", key: "status", width: 70,
      render: (v: string) => <Tag color={STATUS_COLORS[v] ?? "default"} style={{ fontSize: 10, margin: 0 }}>{STATUS_LABELS[v] ?? v}</Tag>,
    },
    { title: "规则数", key: "rule_count", width: 65, render: (_: unknown, r: AudienceRuleSet) => {
      const json = r.rules_json;
      const conds = json && typeof json === "object" && "conditions" in json
        ? (json as Record<string, unknown[]>).conditions
        : undefined;
      return Array.isArray(conds) ? conds.length : 0;
    }},
    { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 85, render: (v: string) => new Date(v).toLocaleDateString("zh-CN") },
    {
      title: "操作", key: "actions", width: 180, fixed: "right" as const,
      render: (_: unknown, r: AudienceRuleSet) => (
        <Space size={4}>
          <Button size="small" type="link" style={{ fontSize: 11, padding: 0 }} onClick={() => handleEdit(r)}>编辑</Button>
          {r.status === "active" ? (
            <Button size="small" type="link" style={{ fontSize: 11, padding: 0, color: "#faad14" }} onClick={() => void handleToggleStatus(r)}>停用</Button>
          ) : (
            <Button size="small" type="link" style={{ fontSize: 11, padding: 0, color: "#52c41a" }} onClick={() => void handleToggleStatus(r)}>启用</Button>
          )}
          <DangerButton
            label="删除"
            confirmTitle={`确认删除规则「${r.name}」？`}
            confirmDescription="此操作不可恢复"
            onConfirm={() => handleDelete(r)}
            type="link"
            danger
          />
        </Space>
      ),
    },
  ];

  // ── Render ──

  return (
    <PageShell title="自动分配规则" subtitle="管理会话自动分配和受众触达规则" stats={stats} actions={actions}>
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{error}</Typography.Text>}

      <Table
        dataSource={rules}
        columns={withSorter(columns)}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 380px)" }}
      />

      <div style={{ marginTop: 12, padding: "8px 12px", background: "#fffbe6", borderRadius: 6, border: "1px solid #ffe58f" }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          ⚠️ 规则引擎为预览版，规则创建后仅存储，暂未接入自动执行引擎
        </Typography.Text>
      </div>

      {/* Create/Edit Modal */}
      <Modal
        title={editingRule ? "编辑规则" : "创建规则"}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        width={640}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item label="规则名称" name="name" rules={[{ required: true, message: "请输入规则名称" }]}>
            <Input placeholder="例如: VIP 优先分配" />
          </Form.Item>
          <Form.Item label="作用域类型" name="scope_type" rules={[{ required: true, message: "请选择作用域类型" }]}>
            <Select options={[
              { label: "任务模板 (task_template)", value: "task_template" },
              { label: "受众 (audience)", value: "audience" },
              { label: "全局 (global)", value: "global" },
            ]} placeholder="选择作用域类型" />
          </Form.Item>
          <Form.Item label="关联账号" name="scope_id">
            <Select allowClear placeholder="选择账号（空=全局）" options={accountOptions} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} placeholder="规则描述" />
          </Form.Item>
          <Form.Item label="规则内容 (JSON)" name="rules_json" rules={[{ required: true, message: "请输入 JSON 规则内容" }]}>
            <Input.TextArea
              rows={10}
              placeholder={JSON.stringify({ conditions: [{ field: "user_level", op: "eq", value: "vip" }], actions: [{ type: "assign_to", value: "agent-senior" }]}, null, 2)}
              style={{ fontFamily: "monospace", fontSize: 12 }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}
