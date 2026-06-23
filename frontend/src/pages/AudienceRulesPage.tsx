import { useEffect, useState, type JSX } from "react";

import { ProTable, type ProColumns } from "@ant-design/pro-table";
import { Alert, Button, Card, Col, Form, Input, Row, Select, Space, Statistic, Tag } from "antd";

import {
  createAudienceRuleSet,
  listAudienceRuleSets,
  type AudienceRuleSet,
  type AudienceRuleSetCreatePayload,
} from "../services/api";

type RuleFormValues = Omit<AudienceRuleSetCreatePayload, "rules_json"> & {
  rules_json_text: string;
};

const DEFAULT_RULES_JSON = `{
  "site_keys": [],
  "country_codes": [],
  "language_codes": ["zh-CN"],
  "requires_phone": false,
  "requires_email": false,
  "requires_whatsapp": false,
  "is_anonymous": false,
  "is_new_user": true,
  "include_tag_keys": [],
  "exclude_tag_keys": []
}`;

const INITIAL_VALUES: RuleFormValues = {
  description: "",
  name: "",
  rule_key: "",
  rules_json_text: DEFAULT_RULES_JSON,
  scope_id: "",
  scope_type: "task_template",
  status: "draft",
};

export function AudienceRulesPage(): JSX.Element {
  const [form] = Form.useForm<RuleFormValues>();
  const [rules, setRules] = useState<AudienceRuleSet[]>([]);
  const [loading, setLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadRules(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      setRules(await listAudienceRuleSets());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "受众规则加载失败");
    } finally {
      setLoading(false);
      setPendingAction(null);
    }
  }

  useEffect(() => {
    form.setFieldsValue(INITIAL_VALUES);
    void loadRules();
  }, [form]);

  async function handleSubmit(values: RuleFormValues): Promise<void> {
    setPendingAction("create");
    setError(null);
    setNotice(null);

    try {
      const created = await createAudienceRuleSet({
        description: values.description?.trim() || "",
        name: values.name.trim(),
        rule_key: values.rule_key.trim(),
        rules_json: JSON.parse(values.rules_json_text) as Record<string, unknown>,
        scope_id: values.scope_id?.trim() || undefined,
        scope_type: values.scope_type.trim(),
        status: values.status,
      });

      setNotice(`规则集已创建: ${created.name}`);
      form.resetFields();
      form.setFieldsValue(INITIAL_VALUES);
      await loadRules();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "规则集创建失败");
      setPendingAction(null);
    }
  }

  const columns: ProColumns<AudienceRuleSet>[] = [
    { title: "名称", render: (_, record) => record.name },
    { title: "Rule Key", dataIndex: "rule_key" },
    { title: "范围", render: (_, record) => <Tag>{record.scope_type}</Tag> },
    { title: "状态", render: (_, record) => <Tag color="processing">{record.status}</Tag> },
    { title: "说明", render: (_, record) => record.description || "-" },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {error ? <Alert message={error} showIcon type="error" /> : null}
      {notice ? <Alert message={notice} showIcon type="success" /> : null}

      <Card>
        <Space align="center" size={[12, 12]} wrap>
          <Button loading={loading} onClick={() => void loadRules()} type="primary">
            刷新
          </Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col lg={6} md={12} xs={24}>
          <Card>
            <Statistic title="规则总数" value={rules.length} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col lg={14} xs={24}>
          <ProTable<AudienceRuleSet>
            columns={columns}
            dataSource={rules}
            expandable={{
              expandedRowRender: (record) => (
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                  {JSON.stringify(record.rules_json, null, 2)}
                </pre>
              ),
            }}
            loading={loading}
            options={false}
            pagination={{ pageSize: 8 }}
            rowKey="id"
            search={false}
            toolBarRender={false}
          />
        </Col>
        <Col lg={10} xs={24}>
          <Card title="新建规则">
            <Form<RuleFormValues> form={form} layout="vertical" onFinish={(values) => void handleSubmit(values)}>
              <Form.Item label="Rule Key" name="rule_key" rules={[{ required: true, message: "请输入 rule_key" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="Scope Type" name="scope_type" rules={[{ required: true, message: "请输入 scope_type" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="Scope ID" name="scope_id">
                <Input />
              </Form.Item>
              <Form.Item label="状态" name="status" rules={[{ required: true, message: "请选择状态" }]}>
                <Select
                  options={[
                    { label: "draft", value: "draft" },
                    { label: "active", value: "active" },
                    { label: "paused", value: "paused" },
                    { label: "archived", value: "archived" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="说明" name="description">
                <Input.TextArea rows={3} />
              </Form.Item>
              <Form.Item label="Rules JSON" name="rules_json_text" rules={[{ required: true, message: "请输入规则 JSON" }]}>
                <Input.TextArea rows={12} />
              </Form.Item>
              <Button block htmlType="submit" loading={pendingAction === "create"} type="primary">
                创建规则
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
