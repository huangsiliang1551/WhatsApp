import { useEffect, useState, type JSX } from "react";

import { ProTable, type ProColumns } from "@ant-design/pro-table";
import { Alert, Button, Card, Col, Form, Input, Row, Select, Space, Statistic, Switch, Tag } from "antd";

import { createPlatformTag, listPlatformTags, type PlatformTag } from "../services/api";

type TagFormValues = {
  tag_key: string;
  name: string;
  description?: string;
  color?: string;
  source_type: string;
  is_active: boolean;
};

const INITIAL_VALUES: TagFormValues = {
  tag_key: "",
  name: "",
  description: "",
  color: "",
  source_type: "manual",
  is_active: true,
};

export function TagsPage(): JSX.Element {
  const [form] = Form.useForm<TagFormValues>();
  const [tags, setTags] = useState<PlatformTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadTags(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      setTags(await listPlatformTags());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "标签加载失败");
    } finally {
      setLoading(false);
      setPendingAction(null);
    }
  }

  useEffect(() => {
    form.setFieldsValue(INITIAL_VALUES);
    void loadTags();
  }, [form]);

  async function handleSubmit(values: TagFormValues): Promise<void> {
    setPendingAction("create");
    setError(null);
    setNotice(null);
    try {
      const created = await createPlatformTag({
        tag_key: values.tag_key.trim(),
        name: values.name.trim(),
        description: values.description?.trim() || "",
        color: values.color?.trim() || "",
        source_type: values.source_type,
        is_active: values.is_active,
      });
      setNotice(`标签已创建: ${created.name}`);
      form.resetFields();
      form.setFieldsValue(INITIAL_VALUES);
      await loadTags();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "标签创建失败");
      setPendingAction(null);
    }
  }

  const columns: ProColumns<PlatformTag>[] = [
    { title: "标签名称", dataIndex: "name" },
    { title: "Tag Key", dataIndex: "tag_key" },
    {
      title: "来源",
      render: (_, record) => <Tag>{record.source_type}</Tag>,
    },
    {
      title: "状态",
      render: (_, record) => <Tag color={record.is_active ? "success" : "default"}>{record.is_active ? "启用" : "停用"}</Tag>,
    },
    {
      title: "颜色",
      render: (_, record) => record.color || "-",
    },
    {
      title: "说明",
      render: (_, record) => record.description || "-",
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      {error ? <Alert message={error} showIcon type="error" /> : null}
      {notice ? <Alert message={notice} showIcon type="success" /> : null}

      <Card>
        <Space align="center" size={[12, 12]} wrap>
          <Button loading={loading} onClick={() => void loadTags()} type="primary">
            刷新
          </Button>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col lg={6} md={12} xs={24}>
          <Card>
            <Statistic title="标签总数" value={tags.length} />
          </Card>
        </Col>
        <Col lg={6} md={12} xs={24}>
          <Card>
            <Statistic title="启用标签" value={tags.filter((item) => item.is_active).length} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col lg={14} xs={24}>
          <ProTable<PlatformTag>
            columns={columns}
            dataSource={tags}
            loading={loading}
            options={false}
            pagination={{ pageSize: 8 }}
            rowKey="id"
            search={false}
            toolBarRender={false}
          />
        </Col>
        <Col lg={10} xs={24}>
          <Card title="新建标签">
            <Form<TagFormValues> form={form} layout="vertical" onFinish={(values) => void handleSubmit(values)}>
              <Form.Item label="Tag Key" name="tag_key" rules={[{ required: true, message: "请输入 tag_key" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入标签名称" }]}>
                <Input />
              </Form.Item>
              <Form.Item label="来源" name="source_type" rules={[{ required: true, message: "请选择来源" }]}>
                <Select
                  options={[
                    { label: "manual", value: "manual" },
                    { label: "rule", value: "rule" },
                    { label: "system", value: "system" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="颜色" name="color">
                <Input placeholder="#1677ff" />
              </Form.Item>
              <Form.Item label="说明" name="description">
                <Input.TextArea rows={4} />
              </Form.Item>
              <Form.Item label="启用" name="is_active" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Button block htmlType="submit" loading={pendingAction === "create"} type="primary">
                创建标签
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
