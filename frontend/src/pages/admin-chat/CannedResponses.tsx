import { type JSX, useCallback, useEffect, useMemo, useState } from "react";
import { Button, Input, Modal, Popconfirm, Select, Space, Tag, Typography, message } from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import {
  listCannedResponses,
  createCannedResponse,
  updateCannedResponse,
  deleteCannedResponse,
} from "../../services/api";
import type { CannedResponseItem } from "../../services/api";

/** 单条话术（前端使用） */
export interface CannedResponse {
  id: string;
  title: string;
  content: string;
  category: string;
  variables: string[];
}

export interface CannedResponsesProps {
  open: boolean;
  onClose: () => void;
  onSelect: (text: string) => void;
  /** F-07: 从选中会话传入 accountId */
  accountId?: string;
  /** F-07: 会话管理模式，AI托管时禁止录入 */
  conversationMode?: string | null;
}

function toCannedResponse(item: CannedResponseItem): CannedResponse {
  return {
    id: item.id,
    title: item.title,
    content: item.content,
    category: item.category,
    variables: item.variables ?? [],
  };
}

export function CannedResponses({ open, onClose, onSelect, accountId, conversationMode }: CannedResponsesProps): JSX.Element {
  const [responses, setResponses] = useState<CannedResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>("全部");
  const [searchText, setSearchText] = useState("");

  const [varModalOpen, setVarModalOpen] = useState(false);
  const [selectedResponse, setSelectedResponse] = useState<CannedResponse | null>(null);
  const [varValues, setVarValues] = useState<Record<string, string>>({});

  // CRUD Modal
  const [crudModalOpen, setCrudModalOpen] = useState(false);
  const [editingResponse, setEditingResponse] = useState<CannedResponse | null>(null);
  const [crudTitle, setCrudTitle] = useState("");
  const [crudContent, setCrudContent] = useState("");
  const [crudCategory, setCrudCategory] = useState("");
  const [crudVariables, setCrudVariables] = useState("");
  const [crudSaving, setCrudSaving] = useState(false);

  const loadResponses = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listCannedResponses(accountId, selectedCategory === "全部" ? undefined : selectedCategory, searchText || undefined);
      setResponses(items.map(toCannedResponse));
    } catch {
      message.error("加载快捷回复失败");
    } finally {
      setLoading(false);
    }
  }, [accountId, selectedCategory, searchText]);

  useEffect(() => {
    if (open) {
      setSelectedCategory("全部");
      setSearchText("");
      void loadResponses();
    }
  }, [open, accountId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 当筛选条件变化时重新加载
  useEffect(() => {
    if (open) void loadResponses();
  }, [selectedCategory, searchText]); // eslint-disable-line react-hooks/exhaustive-deps

  const categories = useMemo(() => {
    const set = new Set(responses.map((r) => r.category));
    return ["全部", ...Array.from(set)];
  }, [responses]);

  const filtered = useMemo(() => {
    if (selectedCategory === "全部" && !searchText) return responses;
    let result = responses;
    if (selectedCategory !== "全部") {
      result = result.filter((r) => r.category === selectedCategory);
    }
    if (searchText) {
      const q = searchText.toLowerCase();
      result = result.filter((r) => r.title.toLowerCase().includes(q) || r.content.toLowerCase().includes(q));
    }
    return result;
  }, [responses, selectedCategory, searchText]);

  const isAiManaged = conversationMode === "ai_managed";

  const handleClickResponse = (r: CannedResponse) => {
    if (isAiManaged) {
      message.warning("AI 托管状态下不允许录入快捷回复，请先接管会话");
      return;
    }
    if (r.variables.length === 0) {
      onSelect(r.content);
      onClose();
    } else {
      setSelectedResponse(r);
      const init: Record<string, string> = {};
      r.variables.forEach((v) => { init[v] = ""; });
      setVarValues(init);
      setVarModalOpen(true);
    }
  };

  const handleVarConfirm = () => {
    if (!selectedResponse) return;
    let text = selectedResponse.content;
    selectedResponse.variables.forEach((v) => {
      text = text.replace(`{{${v}}}`, varValues[v] || `{{${v}}}`);
    });
    onSelect(text);
    setVarModalOpen(false);
    setSelectedResponse(null);
    onClose();
  };

  // CRUD handlers
  const openCreateModal = () => {
    setEditingResponse(null);
    setCrudTitle("");
    setCrudContent("");
    setCrudCategory("");
    setCrudVariables("");
    setCrudModalOpen(true);
  };

  const openEditModal = (r: CannedResponse) => {
    setEditingResponse(r);
    setCrudTitle(r.title);
    setCrudContent(r.content);
    setCrudCategory(r.category);
    setCrudVariables(r.variables.join(", "));
    setCrudModalOpen(true);
  };

  const handleCrudSave = async () => {
    if (!crudTitle.trim() || !crudContent.trim()) {
      message.warning("标题和内容不能为空");
      return;
    }
    setCrudSaving(true);
    try {
      const vars = crudVariables
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
      if (editingResponse) {
        await updateCannedResponse(editingResponse.id, {
          title: crudTitle.trim(),
          content: crudContent.trim(),
          category: crudCategory.trim() || "通用",
          variables: vars,
        });
        message.success("更新成功");
      } else {
        await createCannedResponse({
          account_id: accountId,
          title: crudTitle.trim(),
          content: crudContent.trim(),
          category: crudCategory.trim() || "通用",
          variables: vars,
        });
        message.success("创建成功");
      }
      setCrudModalOpen(false);
      void loadResponses();
    } catch {
      message.error("保存失败");
    } finally {
      setCrudSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteCannedResponse(id);
      message.success("已删除");
      void loadResponses();
    } catch {
      message.error("删除失败");
    }
  };

  return (
    <>
      <Modal
        title="💬 快捷回复"
        open={open}
        onCancel={onClose}
        footer={null}
        width={460}
      >
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Input.Search
              size="small"
              placeholder="搜索话术..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
              style={{ flex: 1 }}
            />
            <Select
              size="small"
              value={selectedCategory}
              onChange={setSelectedCategory}
              options={categories.map((c) => ({ label: c, value: c }))}
              style={{ width: 100 }}
            />
            <Button size="small" type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
              新增
            </Button>
          </div>
          <div style={{ maxHeight: 360, overflowY: "auto" }}>
            {loading ? (
              <div style={{ padding: 24, textAlign: "center", color: "#999" }}>加载中...</div>
            ) : filtered.length === 0 ? (
              <div style={{ padding: 24, textAlign: "center", color: "#999" }}>暂无话术</div>
            ) : (
              filtered.map((r) => (
                <div
                  key={r.id}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 6,
                    marginBottom: 4,
                    border: "1px solid #f0f0f0",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                  }}
                >
                  <div
                    onClick={() => handleClickResponse(r)}
                    style={{ cursor: "pointer", flex: 1, minWidth: 0 }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <Typography.Text strong style={{ fontSize: 13 }}>{r.title}</Typography.Text>
                      <Tag style={{ fontSize: 10, margin: 0 }}>{r.category}</Tag>
                      {r.variables.length > 0 && (
                        <Typography.Text type="secondary" style={{ fontSize: 10 }}>{r.variables.length} 个变量</Typography.Text>
                      )}
                    </div>
                    <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", lineHeight: 1.5 }} ellipsis={{ tooltip: r.content }}>
                      {r.content}
                    </Typography.Text>
                  </div>
                  <Space size={2} style={{ flexShrink: 0, marginLeft: 8 }}>
                    <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEditModal(r)} />
                    <Popconfirm title="确认删除这条话术？" onConfirm={() => handleDelete(r.id)} okText="确认" cancelText="取消">
                      <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                  </Space>
                </div>
              ))
            )}
          </div>
        </Space>
      </Modal>

      {/* 变量填写 Modal */}
      <Modal
        title="填写变量"
        open={varModalOpen}
        onCancel={() => { setVarModalOpen(false); setSelectedResponse(null); }}
        onOk={handleVarConfirm}
        okText="插入"
        cancelText="取消"
      >
        {selectedResponse && (
          <Space direction="vertical" size={8} style={{ width: "100%" }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>{selectedResponse.content}</Typography.Text>
            {selectedResponse.variables.map((v) => (
              <div key={v}>
                <Typography.Text style={{ fontSize: 12 }}>{v}:</Typography.Text>
                <Input
                  size="small"
                  value={varValues[v] || ""}
                  onChange={(e) => setVarValues((prev) => ({ ...prev, [v]: e.target.value }))}
                  placeholder={`输入 ${v}`}
                  style={{ marginTop: 2 }}
                />
              </div>
            ))}
          </Space>
        )}
      </Modal>

      {/* CRUD Modal */}
      <Modal
        title={editingResponse ? "编辑话术" : "新增话术"}
        open={crudModalOpen}
        onCancel={() => setCrudModalOpen(false)}
        onOk={handleCrudSave}
        confirmLoading={crudSaving}
        okText="保存"
        cancelText="取消"
      >
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <div>
            <Typography.Text style={{ fontSize: 12 }}>标题</Typography.Text>
            <Input size="small" value={crudTitle} onChange={(e) => setCrudTitle(e.target.value)} placeholder="话术标题" />
          </div>
          <div>
            <Typography.Text style={{ fontSize: 12 }}>内容</Typography.Text>
            <Input.TextArea size="small" rows={3} value={crudContent} onChange={(e) => setCrudContent(e.target.value)} placeholder="话术内容，变量用 {{var}} 表示" />
          </div>
          <div>
            <Typography.Text style={{ fontSize: 12 }}>分类</Typography.Text>
            <Input size="small" value={crudCategory} onChange={(e) => setCrudCategory(e.target.value)} placeholder="如：问候、物流、退款" />
          </div>
          <div>
            <Typography.Text style={{ fontSize: 12 }}>变量（逗号分隔）</Typography.Text>
            <Input size="small" value={crudVariables} onChange={(e) => setCrudVariables(e.target.value)} placeholder="如：agent_name, order_id" />
          </div>
        </Space>
      </Modal>
    </>
  );
}
