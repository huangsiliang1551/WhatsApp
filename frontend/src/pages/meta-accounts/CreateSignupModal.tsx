import { useState } from "react";
import { Modal, Form, Input, message } from "antd";
import { createEmbeddedSignupSession } from "../../services/api";

interface CreateSignupModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function CreateSignupModal({ open, onClose, onCreated }: CreateSignupModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      await createEmbeddedSignupSession({
        account_id: values.account_id,
        display_name: values.display_name,
        redirect_uri: values.redirect_uri,
      });
      message.success("注册会话已创建");
      form.resetFields();
      onCreated();
    } catch (err: unknown) {
      if (err && typeof err === "object" && "errorFields" in err) return;
      message.error(err instanceof Error ? err.message : "创建失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="创建 Embedded Signup 会话" open={open} onCancel={onClose} onOk={handleOk}
      confirmLoading={loading} okText="创建" cancelText="取消" destroyOnClose>
      <Form form={form} layout="vertical" size="small">
        <Form.Item name="account_id" label="账户 ID" rules={[{ required: true, message: "必填" }]}>
          <Input placeholder="如: acc-1" />
        </Form.Item>
        <Form.Item name="display_name" label="显示名称" rules={[{ required: true, message: "必填" }]}>
          <Input placeholder="如: 主账户" />
        </Form.Item>
        <Form.Item name="redirect_uri" label="Redirect URI" rules={[{ required: true, message: "必填" }]}>
          <Input placeholder="https://your-app.com/callback" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
