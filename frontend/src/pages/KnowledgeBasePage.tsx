import { useCallback, useEffect, useState, type JSX } from "react";
import { Button, Card, Col, Drawer, Form, Input, Menu, message, Modal, Row, Select, Space, Table, Tag, Typography } from "antd";
import { withSorter } from "../utils/withSorter";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import { usePageData } from "../hooks/usePageData";
import { usePermissions } from "../hooks/usePermissions";
import { PageShell } from "../components/PageShell";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import {
  listKnowledgeCategories, createKnowledgeCategory, updateKnowledgeCategory, deleteKnowledgeCategory,
  listKnowledgeArticles, createKnowledgeArticle, updateKnowledgeArticle, deleteKnowledgeArticle,
  type KnowledgeCategory, type KnowledgeArticle,
} from "../services/api";

export function KnowledgeBasePage(): JSX.Element {
  const { can } = usePermissions();
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>();
  const [searchText, setSearchText] = useState("");
  const [searchDraft, setSearchDraft] = useState("");

  // ── Category Modal ──
  const [catModalOpen, setCatModalOpen] = useState(false);
  const [editingCat, setEditingCat] = useState<KnowledgeCategory | null>(null);
  const [catForm] = Form.useForm();
  const [catSaving, setCatSaving] = useState(false);

  // ── Article Drawer ──
  const [articleDrawerOpen, setArticleDrawerOpen] = useState(false);
  const [editingArticle, setEditingArticle] = useState<KnowledgeArticle | null>(null);
  const [articleForm] = Form.useForm();
  const [articleSaving, setArticleSaving] = useState(false);

  // ── Fetch categories ──
  const catFetcher = useCallback(async () => {
    const categories = await listKnowledgeCategories();
    return { categories };
  }, []);
  const { data: catData, loading: catLoading, reload: catReload } = usePageData({ fetcher: catFetcher });
  const categories = catData?.categories ?? [];

  // ── Fetch articles ──
  const articleFetcher = useCallback(async () => {
    const articles = await listKnowledgeArticles({
      category_id: selectedCategory,
      search: searchText || undefined,
    });
    return { articles };
  }, [selectedCategory, searchText]);
  const { data: articleData, loading: articleLoading, reload: articleReload } = usePageData({ fetcher: articleFetcher });
  const articles = articleData?.articles ?? [];

  // Reload articles when filter changes
  useEffect(() => { void articleReload(); }, [selectedCategory, searchText]);

  // ── Debounced search ──
  useEffect(() => {
    const timer = setTimeout(() => setSearchText(searchDraft), 300);
    return () => clearTimeout(timer);
  }, [searchDraft]);

  // ── Category Handlers ──
  const handleOpenCatModal = (cat?: KnowledgeCategory) => {
    setEditingCat(cat ?? null);
    if (cat) {
      catForm.setFieldsValue({ name: cat.name, description: cat.description });
    } else {
      catForm.resetFields();
    }
    setCatModalOpen(true);
  };

  const handleCatSave = async (values: { name: string; description?: string }) => {
    setCatSaving(true);
    try {
      if (editingCat) {
        await updateKnowledgeCategory(editingCat.id, values);
        showSuccess("分类已更新");
      } else {
        await createKnowledgeCategory(values);
        showSuccess("分类已创建");
      }
      setCatModalOpen(false);
      void catReload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setCatSaving(false);
    }
  };

  const handleCatDelete = async (cat: KnowledgeCategory) => {
    try {
      await deleteKnowledgeCategory(cat.id);
      showSuccess("分类已删除");
      if (selectedCategory === cat.id) setSelectedCategory(undefined);
      void catReload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    }
  };

  // ── Article Handlers ──
  const handleOpenArticleDrawer = (article?: KnowledgeArticle) => {
    setEditingArticle(article ?? null);
    if (article) {
      articleForm.setFieldsValue({
        title: article.title,
        category_id: article.category_id,
        keywords: article.keywords,
        content: article.content,
      });
    } else {
      articleForm.resetFields();
      if (selectedCategory) {
        articleForm.setFieldsValue({ category_id: selectedCategory });
      }
    }
    setArticleDrawerOpen(true);
  };

  const handleArticleSave = async (values: { title: string; category_id?: string; keywords?: string; content: string }) => {
    setArticleSaving(true);
    try {
      if (editingArticle) {
        await updateKnowledgeArticle(editingArticle.id, values);
        showSuccess("文章已更新");
      } else {
        await createKnowledgeArticle(values as { title: string; category_id: string; content: string; keywords?: string });
        showSuccess("文章已创建");
      }
      setArticleDrawerOpen(false);
      void articleReload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setArticleSaving(false);
    }
  };

  const handleArticleDelete = async (article: KnowledgeArticle) => {
    try {
      await deleteKnowledgeArticle(article.id);
      showSuccess("文章已删除");
      void articleReload();
    } catch (e) {
      showError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const selectedCategoryName = categories.find((c) => c.id === selectedCategory)?.name ?? "全部分类";

  const articleColumns = [
    { title: "标题", dataIndex: "title", key: "title", ellipsis: true, render: (v: string) => <Typography.Text strong>{v}</Typography.Text> },
    { title: "关键词", dataIndex: "keywords", key: "keywords", width: 180, render: (v: string | null) => v ? <Tag>{v}</Tag> : "-" },
    { title: "浏览量", dataIndex: "view_count", key: "view_count", width: 80 },
    {
      title: "操作", key: "actions", width: 140,
      render: (_: unknown, r: KnowledgeArticle) => (
        <Space size="small">
          <Button size="small" onClick={() => handleOpenArticleDrawer(r)}>编辑</Button>
          <DangerButton label="删除" confirmTitle="确认删除此文章?" onConfirm={() => handleArticleDelete(r)} type="link" danger />
        </Space>
      ),
    },
  ];

  return (
    <PageShell title="知识库管理" subtitle="管理知识分类和文章">
      <Row gutter={16} style={{ height: "calc(100vh - 180px)", overflow: "hidden" }}>
        {/* Left: Category List */}
        <Col span={5}>
          <Card
            title="分类"
            size="small"
            styles={{ body: { padding: 0, overflow: "auto", maxHeight: "calc(100vh - 260px)" } }}
            extra={can("knowledge.manage") && (
              <Button size="small" icon={<PlusOutlined />} onClick={() => handleOpenCatModal()}>新增</Button>
            )}
          >
            <Menu
              mode="inline"
              selectedKeys={selectedCategory ? [selectedCategory] : []}
              onClick={(info) => setSelectedCategory(info.key === selectedCategory ? undefined : info.key)}
              items={[
                { key: "__all", label: <Typography.Text strong>全部分类</Typography.Text> },
                ...categories.map((c) => ({
                  key: c.id,
                  label: (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                      <span>{c.name}</span>
                      {can("knowledge.manage") && (
                        <Space size={2} onClick={(e) => e.stopPropagation()}>
                          <Button size="small" type="link" style={{ fontSize: 11, padding: 0 }} onClick={() => handleOpenCatModal(c)}>编辑</Button>
                          <DangerButton label="删" confirmTitle={`确认删除分类「${c.name}」?`} onConfirm={() => handleCatDelete(c)} type="link" danger />
                        </Space>
                      )}
                    </div>
                  ),
                })),
              ]}
              style={{ border: "none" }}
            />
          </Card>
        </Col>

        {/* Right: Article List */}
        <Col span={19} style={{ display: "flex", flexDirection: "column" }}>
          <Card
            title={selectedCategoryName}
            size="small"
            styles={{ body: { flex: 1, overflow: "auto" } }}
            extra={
              <Space>
                <Input
                  placeholder="搜索文章标题…"
                  prefix={<SearchOutlined />}
                  allowClear
                  style={{ width: 200 }}
                  value={searchDraft}
                  onChange={(e) => setSearchDraft(e.target.value)}
                />
                {can("knowledge.manage") && (
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => handleOpenArticleDrawer()}>
                    新增文章
                  </Button>
                )}
              </Space>
            }
          >
            <Table
              dataSource={articles}
              columns={withSorter(articleColumns)}
              rowKey="id"
              size="small"
              loading={articleLoading}
              pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
              scroll={{ y: "calc(100vh - 320px)" }}
            />
          </Card>
        </Col>
      </Row>

      {/* ── Category Modal ── */}
      <Modal
        title={editingCat ? "编辑分类" : "新增分类"}
        open={catModalOpen}
        onCancel={() => { setCatModalOpen(false); setEditingCat(null); }}
        onOk={() => catForm.submit()}
        confirmLoading={catSaving}
        okText="保存"
        cancelText="取消"
      >
        <Form form={catForm} layout="vertical" onFinish={handleCatSave}>
          <Form.Item label="分类名称" name="name" rules={[{ required: true, message: "请输入分类名称" }]}>
            <Input placeholder="例如: 常见问题" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} placeholder="可选描述" />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Article Drawer ── */}
      <Drawer
        title={editingArticle ? "编辑文章" : "新增文章"}
        width={640}
        open={articleDrawerOpen}
        onClose={() => { setArticleDrawerOpen(false); setEditingArticle(null); }}
        extra={
          <Space>
            <Button onClick={() => { setArticleDrawerOpen(false); setEditingArticle(null); }}>取消</Button>
            <Button type="primary" loading={articleSaving} onClick={() => articleForm.submit()}>
              保存
            </Button>
          </Space>
        }
      >
        <Form form={articleForm} layout="vertical" onFinish={handleArticleSave}>
          <Form.Item label="标题" name="title" rules={[{ required: true, message: "请输入文章标题" }]}>
            <Input placeholder="文章标题" />
          </Form.Item>
          <Form.Item label="分类" name="category_id">
            <Select
              placeholder="选择分类"
              allowClear
              options={categories.map((c) => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>
          <Form.Item label="关键词" name="keywords">
            <Input placeholder="逗号分隔，例如: 退款, 退货, 售后" />
          </Form.Item>
          <Form.Item label="内容" name="content" rules={[{ required: true, message: "请输入文章内容" }]}>
            <Input.TextArea rows={15} placeholder="文章内容（支持 Markdown 格式）" />
          </Form.Item>
        </Form>
      </Drawer>
    </PageShell>
  );
}

export default KnowledgeBasePage;
