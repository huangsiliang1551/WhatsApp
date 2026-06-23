import { useCallback, useMemo, useState, type JSX } from "react";
import { Button, Card, Col, Form, Image, Input, InputNumber, Modal, Row, Select, Slider, Space, Statistic, Table, Tag, Typography, Upload, message } from "antd";
import { withSorter } from "../utils/withSorter";
import { CheckCircleOutlined, CloseOutlined, GiftOutlined, PieChartOutlined, PlusOutlined, ReloadOutlined, SearchOutlined, ShoppingOutlined, ThunderboltOutlined, UploadOutlined } from "@ant-design/icons";
import { PageShell } from "../components/PageShell";
import { usePageData } from "../hooks/usePageData";
import { DangerButton, showSuccess, showError } from "../components/Feedback";
import { api } from "../services/api";
import { useAppStore } from "../stores/appStore";
import {
  listProducts, createProduct, updateProduct, deleteProduct,
  listPackages, createPackage, updatePackage, deletePackage,
  assemblePreview, getPackageStats, fileToDataUrl,
} from "../services/marketingApi";
import type { Product, ProductPackage, ProductPackageItem, PackageAssemblePreview } from "../services/marketingApi";


// ── Component ──

export function EcommercePage(): JSX.Element {
  const actorAccountIds = useAppStore((state) => state.actorAccountIds);
  const accountId = actorAccountIds.length > 0 ? actorAccountIds[0] : undefined;

  // ── Product Drawer state ──
  const [prodDrawerOpen, setProdDrawerOpen] = useState(false);
  const [prodSearch, setProdSearch] = useState("");

  // ── Product CRUD ──
  const [prodModalOpen, setProdModalOpen] = useState(false);
  const [editingProd, setEditingProd] = useState<Product | null>(null);
  const [prodForm] = Form.useForm();
  const [prodSaving, setProdSaving] = useState(false);

  // ── Package CRUD ──
  const [pkgModalOpen, setPkgModalOpen] = useState(false);
  const [editingPkg, setEditingPkg] = useState<ProductPackage | null>(null);
  const [pkgForm] = Form.useForm();
  const [pkgSaving, setPkgSaving] = useState(false);
  const [addedProducts, setAddedProducts] = useState<ProductPackageItem[]>([]);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importSearch, setImportSearch] = useState("");
  const [priceRange, setPriceRange] = useState<[number, number]>([0, 300]);
  const [autoAssembleLoading, setAutoAssembleLoading] = useState(false);

  // ── Data fetching ──
  const fetchAll = useCallback(async () => {
    const [packages, stats] = await Promise.all([listPackages(accountId), getPackageStats()]);
    return { packages, stats };
  }, [accountId]);
  const { data, loading, error, reload } = usePageData({ fetcher: fetchAll });
  const packages = data?.packages ?? [];
  const stats = data?.stats;

  const fetchProducts = useCallback(async () => {
    const products = await listProducts(accountId);
    return { products };
  }, [accountId]);
  const prodData = usePageData({ fetcher: fetchProducts, immediate: prodDrawerOpen });
  const products = prodData.data?.products ?? [];

  // ── Search ──
  const [search, setSearch] = useState("");
  const filteredPkgs = useMemo(() => {
    if (!search.trim()) return packages;
    const q = search.toLowerCase();
    return packages.filter((p) => p.name.toLowerCase().includes(q));
  }, [packages, search]);

  const filteredProds = useMemo(() => {
    if (!prodSearch.trim()) return products;
    const q = prodSearch.toLowerCase();
    return products.filter((p) => p.name.toLowerCase().includes(q) || p.tags.some((t) => t.toLowerCase().includes(q)));
  }, [products, prodSearch]);

  const filteredImportProducts = useMemo(() => {
    return products.filter((p) => {
      if (importSearch.trim()) {
        const q = importSearch.toLowerCase();
        const matchName = p.name.toLowerCase().includes(q);
        const matchTag = p.tags.some(t => t.toLowerCase().includes(q));
        if (!matchName && !matchTag) return false;
      }
      if (p.price < priceRange[0] || p.price > priceRange[1]) return false;
      return true;
    });
  }, [products, importSearch, priceRange]);

  // ── Stats ──
  const renderStats = () => {
    if (!stats) return null;
    return (
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title="商品总数" value={stats.total_products} prefix={<ShoppingOutlined />} valueStyle={{ fontSize: 20 }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title="商品包总数" value={stats.total_packages} prefix={<GiftOutlined />} valueStyle={{ fontSize: 20, color: "#1677ff" }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title="已领取" value={stats.total_claimed} prefix={<CheckCircleOutlined />} valueStyle={{ fontSize: 20, color: "#52c41a" }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" styles={{ body: { padding: "12px 16px" } }}>
            <Statistic title="平均完成率" value={stats.avg_completion_rate} suffix="%" prefix={<PieChartOutlined />} precision={0} valueStyle={{ fontSize: 20 }} />
          </Card>
        </Col>
      </Row>
    );
  };

  // ── Package handlers ──

  const handleOpenProductDrawer = () => {
    setProdDrawerOpen(true);
    void prodData.reload();
  };

  const handlePkgSave = async (values: { name: string; target_amount: number; margin_percent: number; reward_amount: number }) => {
    if (addedProducts.length === 0) {
      showError("请添加至少一个商品");
      return;
    }
    setPkgSaving(true);
    try {
      if (editingPkg) {
        await updatePackage(editingPkg.id, {
          name: values.name,
          completion_reward: values.reward_amount,
        });
        showSuccess("商品包已更新");
      } else {
        await createPackage({
          name: values.name,
          account_id: accountId ?? "",
          target_amount: values.target_amount,
          amount_tolerance_pct: values.margin_percent,
          product_count: addedProducts.length,
          completion_reward: values.reward_amount,
        });
        showSuccess("商品包已创建");
      }
      setPkgModalOpen(false);
      pkgForm.resetFields();
      setAddedProducts([]);
      void reload();
    } catch { showError("保存失败"); }
    finally { setPkgSaving(false); }
  };

  const handlePkgEdit = (pkg: ProductPackage) => {
    setEditingPkg(pkg);
    pkgForm.setFieldsValue({
      name: pkg.name,
      target_amount: pkg.target_amount,
      margin_percent: pkg.margin_percent,
      reward_amount: pkg.reward_amount,
    });
    setAddedProducts(pkg.items ?? []);
    setPkgModalOpen(true);
    void prodData.reload();
  };

  const handlePkgDelete = async (pkg: ProductPackage) => {
    try { await deletePackage(pkg.id); showSuccess("商品包已删除"); void reload(); }
    catch (e) { message.error(`删除失败: ${e instanceof Error ? e.message : "未知错误"}`); }
  };

  const handleAutoAssemble = async () => {
    const target = pkgForm.getFieldValue("target_amount");
    if (!target) { showError("请先填写目标金额"); return; }
    const margin = pkgForm.getFieldValue("margin_percent") || 10;
    setAutoAssembleLoading(true);
    try {
      const result = await assemblePreview(accountId!, {
        target_amount: target,
        tolerance_pct: margin,
        product_count: products.length,
      });
      setAddedProducts(result.items.map(item => ({
        product_id: item.product_id,
        product_name: item.product_name,
        price: item.price,
        quantity: 1,
      })));
      showSuccess(`已自动配品 ${result.items.length} 件，总价 ¥${result.total_value.toFixed(2)}`);
    } catch {
      showError("自动配品失败，请手动导入商品");
    } finally {
      setAutoAssembleLoading(false);
    }
  };

  // ── Import CSV ──
  const handleImportCSV = (options: any) => {
    const { file } = options;
    const formData = new FormData();
    formData.append("file", file);
    api.post("/api/products/import", formData, { headers: { "Content-Type": "multipart/form-data" } })
      .then(() => {
        message.success(`已导入: ${file.name}`);
        void reload();
        void prodData.reload();
      })
      .catch((e: unknown) => {
        message.error(`导入失败: ${e instanceof Error ? e.message : "未知错误"}`);
      });
  };

  // ── Tag removal ──
  const handleRemoveTag = async (productId: string, tag: string) => {
    const prod = products.find((p) => p.id === productId);
    if (!prod) return;
    const newTags = prod.tags.filter((t) => t !== tag);
    try {
      await updateProduct(productId, { ...prod, tags: newTags });
      void prodData.reload();
    } catch (e) { message.error(`删除标签失败: ${e instanceof Error ? e.message : "未知错误"}`); }
  };

  const actions = (
    <Row justify="space-between" align="middle" style={{ marginBottom: 12, flexWrap: "nowrap" }}>
      <Col>
        <Input placeholder="搜索商品包名" prefix={<SearchOutlined />} allowClear style={{ width: 240 }}
          value={search} onChange={(e) => setSearch(e.target.value)} />
      </Col>
      <Col>
        <Space>
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={() => { setEditingPkg(null); pkgForm.resetFields(); setAddedProducts([]); setImportSearch(""); setPriceRange([0, 300]); setPkgModalOpen(true); void prodData.reload(); }}>新建商品包</Button>
          <Upload accept=".csv" showUploadList={false} customRequest={handleImportCSV}>
            <Button size="small" icon={<UploadOutlined />}>导入CSV</Button>
          </Upload>
          <Button size="small" icon={<PlusOutlined />} onClick={handleOpenProductDrawer}>商品管理</Button>
          <Button size="small" icon={<ReloadOutlined />} onClick={() => void reload()} loading={loading}>刷新</Button>
        </Space>
      </Col>
    </Row>
  );

  const handleProdSave = async (values: { name: string; price: number; tags: string[]}) => {
    setProdSaving(true);
    try {
      const fileList = prodForm.getFieldValue("image") as Array<{ originFileObj?: File }> | undefined;
      const newFile = fileList?.[0]?.originFileObj;

      if (editingProd) {
        // Edit: preserve existing image_url unless a new file is uploaded
        const imageUrl = newFile ? await fileToDataUrl(newFile) : editingProd.image_url;
        await updateProduct(editingProd.id, { name: values.name, price: values.price, tags: values.tags || [], image_url: imageUrl });
        showSuccess("商品已更新");
      } else {
        const formData = new FormData();
        formData.append("name", values.name);
        formData.append("price", String(values.price));
        formData.append("tags", JSON.stringify(values.tags || []));
        if (newFile) formData.append("image", newFile);
        await createProduct(formData);
        showSuccess("商品已创建");
      }
      setProdModalOpen(false);
      prodForm.resetFields();
      void prodData.reload();
      void reload();
    } catch (e) { message.error(`保存失败: ${e instanceof Error ? e.message : "未知错误"}`); }
    finally { setProdSaving(false); }
  };

  const handleProdEdit = (prod: Product) => {
    setEditingProd(prod);
    prodForm.setFieldsValue({
      name: prod.name,
      price: prod.price,
      tags: prod.tags.join(", "),
      image: prod.image_url ? [{ url: prod.image_url }] : [],
    });
    setProdModalOpen(true);
  };

  const handleProdDelete = async (prod: Product) => {
    try { await deleteProduct(prod.id); showSuccess("商品已删除"); void prodData.reload(); void reload(); }
    catch (e) { message.error(`删除失败: ${e instanceof Error ? e.message : "未知错误"}`); }
  };

  // ── Package Columns ──

  const pkgColumns = [
    { title: "包名", dataIndex: "name", key: "name", width: 130, ellipsis: true },
    { title: "目标金额", dataIndex: "target_amount", key: "target_amount", width: 100, render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "商品数", dataIndex: "item_count", key: "item_count", width: 70 },
    { title: "实际价值", key: "actual_value", width: 90, render: (_: unknown, r: ProductPackage) => {
      const total = r.items.reduce((s, i) => s + i.price * i.quantity, 0);
      return <Typography.Text strong>¥{total.toFixed(2)}</Typography.Text>;
    }},
    { title: "完成奖励", dataIndex: "reward_amount", key: "reward_amount", width: 90, render: (v: number) => `¥${v.toFixed(2)}` },
    { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 150, render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "-" },
    {
      title: "操作", key: "actions", width: 120, fixed: "right" as const,
      render: (_: unknown, r: ProductPackage) => (
        <Space size={4}>
          <Button size="small" type="link" style={{ fontSize: 11, padding: 0 }} onClick={() => handlePkgEdit(r)}>编辑</Button>
          <DangerButton label="删除" confirmTitle={`确认删除「${r.name}」？`} confirmDescription="此操作不可恢复"
            onConfirm={() => handlePkgDelete(r)} type="link" danger />
        </Space>
      ),
    },
  ];

  // ── Product Columns (with sorting) ──

  const prodColumns = [
    { title: "图片", key: "image", width: 60,
      render: (_: unknown, r: Product) => r.image_url
        ? <Image src={r.image_url} width={40} height={40} style={{ objectFit: "cover", borderRadius: 4 }} />
        : <div style={{ width: 40, height: 40, background: "#f5f5f5", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>📷</div>
    },
    { title: "名称", dataIndex: "name", key: "name", width: 130, ellipsis: true, sorter: (a: Product, b: Product) => a.name.localeCompare(b.name) },
    { title: "价格", dataIndex: "price", key: "price", width: 80, render: (v: number) => `¥${v.toFixed(2)}`, sorter: (a: Product, b: Product) => a.price - b.price },
    {
      title: "标签", dataIndex: "tags", key: "tags", width: 150,
      sorter: (a: Product, b: Product) => (a.tags?.length ?? 0) - (b.tags?.length ?? 0),
      render: (_: unknown, r: Product) => (
        <Space size={4} wrap>
          {(r.tags ?? []).map((tag: string) => <Tag key={tag} closable style={{ fontSize: 10, margin: 0 }} onClose={() => void handleRemoveTag(r.id, tag)}>{tag}</Tag>)}
        </Space>
      )
    },
    {
      title: "操作", key: "actions", width: 100,
      render: (_: unknown, r: Product) => (
        <Space size={4}>
          <Button size="small" type="link" style={{ fontSize: 11, padding: 0 }} onClick={() => handleProdEdit(r)}>编辑</Button>
          <DangerButton label="删除" confirmTitle={`确认删除「${r.name}」？`} confirmDescription="此操作不可恢复"
            onConfirm={() => handleProdDelete(r)} type="link" danger />
        </Space>
      ),
    },
  ];

  // ── Render ──

  return (
    <PageShell title="商城管理" subtitle="管理商品、商品包和凑包配置" actions={actions}>
      {error && <Typography.Text type="danger" style={{ display: "block", marginBottom: 8 }}>{error}</Typography.Text>}

      {renderStats()}

      <Table dataSource={filteredPkgs} columns={withSorter(pkgColumns)} rowKey="id" size="small" loading={loading}
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        scroll={{ y: "calc(100vh - 420px)" }} />

      {/* ── Product Management Modal ── */}
      <Modal title="商品管理" open={prodDrawerOpen} onCancel={() => setProdDrawerOpen(false)} width={760} footer={null}
        styles={{ body: { padding: 12, maxHeight: "calc(100vh - 200px)", overflow: "auto" } }}>
        <Space style={{ marginBottom: 12, width: "100%" }}>
          <Input placeholder="搜索商品名/标签…" prefix={<SearchOutlined />} allowClear style={{ width: 280 }}
            value={prodSearch} onChange={(e) => setProdSearch(e.target.value)} />
          <Button size="small" type="primary" icon={<PlusOutlined />}
            onClick={() => { setEditingProd(null); prodForm.resetFields(); setProdModalOpen(true); }}>新建商品</Button>
        </Space>
        <Table dataSource={filteredProds} columns={withSorter(prodColumns)} rowKey="id" size="small" loading={prodData.loading}
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条` }} scroll={{ y: "calc(100vh - 320px)" }} />
      </Modal>

      {/* ── Package Create/Edit Modal ── */}
      <Modal title={editingPkg ? "编辑商品包" : "新建商品包"} open={pkgModalOpen} width={640}
        onCancel={() => { setPkgModalOpen(false); pkgForm.resetFields(); setAddedProducts([]); setImportModalOpen(false); }}
        onOk={() => pkgForm.submit()} confirmLoading={pkgSaving} okText="保存" cancelText="取消">
        <Form form={pkgForm} layout="vertical" onFinish={handlePkgSave}>
          <Form.Item label="包名称" name="name" rules={[{ required: true, message: "请输入包名称" }]}>
            <Input placeholder="例如: 新人大礼包" />
          </Form.Item>
          <Space style={{ width: "100%" }} size={12}>
            <Form.Item label="目标金额 (¥)" name="target_amount" rules={[{ required: true, message: "请输入" }]}>
              <InputNumber min={1} step={1} style={{ width: 140 }} placeholder="99" prefix="¥" />
            </Form.Item>
            <Form.Item label="浮动比例 (%)" name="margin_percent" initialValue={10}>
              <InputNumber min={0} max={100} style={{ width: 120 }} placeholder="10" suffix="%" />
            </Form.Item>
            <Form.Item label="完成奖励 (¥)" name="reward_amount" rules={[{ required: true, message: "请输入" }]}>
              <InputNumber min={0} step={0.5} style={{ width: 120 }} placeholder="5" prefix="¥" />
            </Form.Item>
            <Form.Item label=" " colon={false}>
              <Button type="primary" ghost icon={<ThunderboltOutlined />} onClick={handleAutoAssemble} loading={autoAssembleLoading}>自动配品</Button>
            </Form.Item>
          </Space>
          {/* 已配商品 */}
          <div style={{ marginTop: 16 }}>
            <Row justify="space-between" align="middle" style={{ marginBottom: 8 }}>
              <Col>
                <Typography.Text strong>
                  已配商品 ({addedProducts.length} 件，总价 ¥{addedProducts.reduce((s, i) => s + i.price * i.quantity, 0).toFixed(2)})
                </Typography.Text>
              </Col>
              <Col>
                <Button size="small" icon={<PlusOutlined />} onClick={() => setImportModalOpen(true)}>导入商品</Button>
              </Col>
            </Row>
            {addedProducts.length > 0 ? (
              <div style={{ maxHeight: addedProducts.length <= 8 ? undefined : 300, overflowY: addedProducts.length <= 8 ? undefined : "auto", overflowX: "hidden" }}>
                <Row gutter={[8, 8]}>
                  {addedProducts.map((item) => {
                    const prod = products.find(p => p.id === item.product_id);
                    return (
                      <Col key={item.product_id} span={6}>
                        <Card
                          size="small"
                          styles={{ body: { padding: 8, textAlign: "center" } }}
                        >
                          {prod?.image_url
                            ? <Image src={prod.image_url} width={64} height={64} style={{ objectFit: "cover", borderRadius: 4 }} preview={false} />
                            : <div style={{ width: 64, height: 64, background: "#f5f5f5", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, margin: "0 auto" }}>📷</div>
                          }
                          <Typography.Text ellipsis style={{ fontSize: 11, display: "block", marginTop: 4 }}>{item.product_name}</Typography.Text>
                          <Typography.Text strong style={{ fontSize: 12 }}>¥{item.price.toFixed(2)}</Typography.Text>
                          <Button size="small" type="primary" danger block style={{ marginTop: 4, fontSize: 11 }}
                            onClick={() => setAddedProducts(prev => prev.filter(p => p.product_id !== item.product_id))}
                          >移除</Button>
                        </Card>
                      </Col>
                    );
                  })}
                </Row>
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: 24, color: "#999", border: "1px dashed #d9d9d9", borderRadius: 6 }}>
                暂无商品，点击"自动配品"或"导入商品"添加
              </div>
            )}
          </div>
        </Form>
      </Modal>

      {/* ── Import Products Modal ── */}
      <Modal
        title="商品库"
        open={importModalOpen}
        onCancel={() => setImportModalOpen(false)}
        footer={null}
        width={640}
      >
        <Input
          placeholder="搜索商品名/标签…"
          prefix={<SearchOutlined />}
          allowClear
          style={{ marginBottom: 12 }}
          value={importSearch}
          onChange={(e) => setImportSearch(e.target.value)}
        />
        <div style={{ marginBottom: 12, padding: "0 8px" }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            价格区间: ¥{priceRange[0]} - ¥{priceRange[1]}
          </Typography.Text>
          <Slider
            range
            min={0}
            max={Math.ceil(Math.max(...products.map(p => p.price), 100))}
            value={priceRange}
            onChange={(v) => setPriceRange(v as [number, number])}
          />
        </div>
        <div style={{ maxHeight: 400, overflow: "auto" }}>
          <Row gutter={[12, 12]}>
            {filteredImportProducts.map((prod) => {
              const isAdded = addedProducts.some(a => a.product_id === prod.id);
              return (
                <Col key={prod.id} span={6}>
                  <Card
                    size="small"
                    hoverable
                    styles={{ body: { padding: 8, textAlign: "center" } }}
                    style={{ opacity: isAdded ? 0.5 : 1 }}
                  >
                    {prod.image_url
                      ? <Image src={prod.image_url} width={64} height={64} style={{ objectFit: "cover", borderRadius: 4 }} preview={false} />
                      : <div style={{ width: 64, height: 64, background: "#f5f5f5", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, margin: "0 auto" }}>📷</div>
                    }
                    <Typography.Text ellipsis style={{ fontSize: 11, display: "block", marginTop: 4 }}>{prod.name}</Typography.Text>
                    <Typography.Text strong style={{ fontSize: 12 }}>¥{prod.price.toFixed(2)}</Typography.Text>
                    <Button
                      size="small"
                      type={isAdded ? "default" : "primary"}
                      block
                      style={{ marginTop: 4 }}
                      disabled={isAdded}
                      onClick={() => {
                        setAddedProducts(prev => [...prev, {
                          product_id: prod.id,
                          product_name: prod.name,
                          price: prod.price,
                          quantity: 1,
                        }]);
                      }}
                    >
                      {isAdded ? "已添加" : "导入"}
                    </Button>
                  </Card>
                </Col>
              );
            })}
          </Row>
          {filteredImportProducts.length === 0 && (
            <div style={{ textAlign: "center", padding: 32, color: "#999" }}>
              无匹配商品
            </div>
          )}
        </div>
      </Modal>

      {/* ── Product Create/Edit Modal ── */}
      <Modal title={editingProd ? "编辑商品" : "新建商品"} open={prodModalOpen} width={480}
        onCancel={() => { setProdModalOpen(false); prodForm.resetFields(); }}
        onOk={() => prodForm.submit()} confirmLoading={prodSaving} okText="保存" cancelText="取消">
        <Form form={prodForm} layout="vertical" onFinish={handleProdSave}>
          <Form.Item label="商品名称" name="name" rules={[{ required: true, message: "请输入商品名称" }]}>
            <Input placeholder="例如: Travel Tote" />
          </Form.Item>
          <Form.Item label="价格 (¥)" name="price" rules={[{ required: true, message: "请输入价格" }]}>
            <InputNumber min={0} step={0.5} style={{ width: "100%" }} placeholder="79.50" prefix="¥" />
          </Form.Item>
          <Form.Item label="图片" name="image" valuePropName="fileList" getValueFromEvent={(e) => Array.isArray(e) ? e : e?.fileList}>
            <Upload
              listType="picture-card"
              maxCount={1}
              accept="image/*"
              beforeUpload={() => false}
            >
              <div><PlusOutlined /><div style={{ fontSize: 11 }}>上传图片</div></div>
            </Upload>
          </Form.Item>
          <Form.Item label="标签" name="tags">
            <Select mode="tags" placeholder="输入标签后回车" tokenSeparators={[","]} />
          </Form.Item>
        </Form>
      </Modal>
    </PageShell>
  );
}
