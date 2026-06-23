# 商品包配品流程重设计（PKG-FIX-002）

> **执行角色**: frontend_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 重设计商品包创建/编辑的配品流程，去掉手动选品，改为自动配品+商品库导入

---

## 新交互流程

```
┌─ 新建商品包 ──────────────────────────────────────────────────────┐
│ 包名称:    [新人大礼包                ]                            │
│ 目标金额:  [99] ¥    浮动: [10] %    完成奖励: [5] ¥              │
│                                              [⚡ 自动配品]         │
│ ─────────────────────────────────────────────────────────────────  │
│ 已配商品 (3件，总价 ¥96.50)                      [📦 导入商品]    │
│ ┌──────────────────────────────────────────────────────────────┐  │
│ │ [📷] Travel Tote    ¥79.50  [✕ 移除]                        │  │
│ │ [📷] USB Cable      ¥12.00  [✕ 移除]                        │  │
│ │ [📷] Ear Buds       ¥15.00  [✕ 移除]                        │  │
│ └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│                                        [取消]  [保存]             │
└────────────────────────────────────────────────────────────────────┘
```

### 导入商品弹窗

```
┌─ 商品库 ──────────────────────────────────────────────┐
│ 🔍 [搜索商品名/标签...]                                │
│                                                        │
│ 价格区间: ¥[0] ━━━━━━━━━●━━━━━ [¥300]                │
│                                                        │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│ │  📷      │ │  📷      │ │  📷      │ │  📷      │  │
│ │ Travel   │ │ USB      │ │ Screen   │ │ Ear      │  │
│ │ Tote     │ │ Cable    │ │ Film     │ │ Buds     │  │
│ │ ¥79.50   │ │ ¥12.00   │ │ ¥8.00    │ │ ¥15.00   │  │
│ │ [导入]   │ │ [已添加] │ │ [导入]   │ │ [已添加] │  │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                        │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│ │  📷      │ │  📷      │ │  📷      │   ↓ 滚动加载  │
│ │ Phone    │ │ Desk     │ │ LED      │               │
│ │ Case     │ │ Lamp     │ │ Bulb     │               │
│ │ ¥22.00   │ │ ¥58.00   │ │ ¥15.00   │               │
│ │ [导入]   │ │ [导入]   │ │ [导入]   │               │
│ └──────────┘ └──────────┘ └──────────┘               │
└────────────────────────────────────────────────────────┘
```

---

## 具体改动

### 修改文件: `frontend/src/pages/EcommercePage.tsx`

#### 1. 删除可视化选品区

删除当前 Modal 内的选品卡片网格（`filteredProds.map(...)` 那一大块），以及 `prodSearch` 搜索框。

#### 2. 新增"自动配品"按钮

在"完成奖励"字段后面增加：

```tsx
<Button
  type="primary"
  ghost
  icon={<ThunderboltOutlined />}
  onClick={handleAutoAssemble}
  loading={autoAssembleLoading}
>
  自动配品
</Button>
```

**handleAutoAssemble 逻辑**:
```typescript
const handleAutoAssemble = async () => {
  const target = pkgForm.getFieldValue("target_amount");
  if (!target) { showError("请先填写目标金额"); return; }
  const margin = pkgForm.getFieldValue("margin_percent") || 10;
  setAutoAssembleLoading(true);
  try {
    // 调用后端凑包预览
    const allProductIds = products.map(p => p.id);
    const result = await assemblePreview({
      target_amount: target,
      margin_percent: margin,
      product_ids: allProductIds,
    });
    // 将结果写入已配商品列表
    setAddedProducts(result.items.map(item => {
      const prod = products.find(p => p.id === item.product_id);
      return {
        product_id: item.product_id,
        product_name: prod?.name ?? item.product_name,
        price: prod?.price ?? item.price,
        quantity: 1,
      };
    }));
    showSuccess(`已自动配品 ${result.items.length} 件，总价 ¥${result.total_amount.toFixed(2)}`);
  } catch {
    showError("自动配品失败，请手动导入商品");
  } finally {
    setAutoAssembleLoading(false);
  }
};
```

#### 3. 新增"已配商品"底部区域

替换原来的选品区，改为只读列表+删除功能：

```tsx
{/* 已配商品 */}
<div style={{ marginTop: 16 }}>
  <Row justify="space-between" align="middle" style={{ marginBottom: 8 }}>
    <Col>
      <Typography.Text strong>
        已配商品 ({addedProducts.length} 件，
        总价 ¥{addedProducts.reduce((s, i) => s + i.price * i.quantity, 0).toFixed(2)})
      </Typography.Text>
    </Col>
    <Col>
      <Button size="small" icon={<PlusOutlined />} onClick={() => setImportModalOpen(true)}>
        导入商品
      </Button>
    </Col>
  </Row>
  {addedProducts.length > 0 ? (
    <div style={{ maxHeight: 200, overflow: "auto", border: "1px solid #f0f0f0", borderRadius: 6, padding: 8 }}>
      {addedProducts.map((item, idx) => (
        <Row key={item.product_id} align="middle" gutter={8}
          style={{ padding: "6px 0", borderBottom: idx < addedProducts.length - 1 ? "1px solid #f5f5f5" : "none" }}>
          <Col flex="none">
            {products.find(p => p.id === item.product_id)?.image_url
              ? <Image src={products.find(p => p.id === item.product_id)!.image_url!} width={32} height={32} style={{ objectFit: "cover", borderRadius: 4 }} preview={false} />
              : <div style={{ width: 32, height: 32, background: "#f5f5f5", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center" }}>📷</div>
            }
          </Col>
          <Col flex="auto">
            <Typography.Text style={{ fontSize: 12 }}>{item.product_name}</Typography.Text>
            <Typography.Text strong style={{ fontSize: 12, marginLeft: 8 }}>¥{item.price.toFixed(2)}</Typography.Text>
          </Col>
          <Col flex="none">
            <Button size="small" type="text" danger icon={<CloseOutlined />}
              onClick={() => setAddedProducts(prev => prev.filter(p => p.product_id !== item.product_id))}
            />
          </Col>
        </Row>
      ))}
    </div>
  ) : (
    <div style={{ textAlign: "center", padding: 24, color: "#999", border: "1px dashed #d9d9d9", borderRadius: 6 }}>
      暂无商品，点击"自动配品"或"导入商品"添加
    </div>
  )}
</div>
```

#### 4. 新增"导入商品"弹窗

```tsx
{/* 导入商品弹窗 */}
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
  {/* 价格区间滑块 */}
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
  {/* 商品网格（瀑布流/滚动加载） */}
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
```

#### 5. 新增状态变量

```typescript
const [addedProducts, setAddedProducts] = useState<ProductPackageItem[]>([]);
const [importModalOpen, setImportModalOpen] = useState(false);
const [importSearch, setImportSearch] = useState("");
const [priceRange, setPriceRange] = useState<[number, number]>([0, 300]);
const [autoAssembleLoading, setAutoAssembleLoading] = useState(false);
```

#### 6. 导入商品过滤逻辑

```typescript
const filteredImportProducts = useMemo(() => {
  return products.filter((p) => {
    // 关键词过滤
    if (importSearch.trim()) {
      const q = importSearch.toLowerCase();
      const matchName = p.name.toLowerCase().includes(q);
      const matchTag = p.tags.some(t => t.toLowerCase().includes(q));
      if (!matchName && !matchTag) return false;
    }
    // 价格区间过滤
    if (p.price < priceRange[0] || p.price > priceRange[1]) return false;
    return true;
  });
}, [products, importSearch, priceRange]);
```

#### 7. 修改 handlePkgSave

从 `addedProducts` 构建 items（不再从 `selectedProductIds`）：

```typescript
const handlePkgSave = async (values: { name: string; target_amount: number; margin_percent: number; reward_amount: number }) => {
  if (addedProducts.length === 0) {
    showError("请添加至少一个商品");
    return;
  }
  setPkgSaving(true);
  try {
    const payload = {
      name: values.name,
      account_id: accountId,
      target_amount: values.target_amount,
      amount_tolerance_pct: values.margin_percent,
      product_count: addedProducts.length,
      product_ids: addedProducts.map(i => i.product_id),
      product_snapshot: addedProducts,
      total_value: addedProducts.reduce((s, i) => s + i.price * i.quantity, 0),
      completion_reward: values.reward_amount,
    };
    if (editingPkg) {
      await updatePackage(editingPkg.id, payload);
      showSuccess("商品包已更新");
    } else {
      await createPackage(payload);
      showSuccess("商品包已创建");
    }
    setPkgModalOpen(false);
    pkgForm.resetFields();
    setAddedProducts([]);
    void reload();
  } catch {
    showError("保存失败");
  } finally {
    setPkgSaving(false);
  }
};
```

#### 8. 修改 handlePkgEdit

从 `pkg.items` 加载到 `addedProducts`：

```typescript
const handlePkgEdit = (pkg: ProductPackage) => {
  setEditingPkg(pkg);
  pkgForm.setFieldsValue({
    name: pkg.name,
    target_amount: pkg.target_amount,
    margin_percent: pkg.margin_percent ?? pkg.amount_tolerance_pct,
    reward_amount: pkg.reward_amount,
  });
  setAddedProducts(pkg.items ?? []);
  setPkgModalOpen(true);
  void prodData.reload();
};
```

#### 9. 删除预览按钮和预览区域

删除 `handlePreviewAssemble` 函数、预览按钮、以及 `assemblePreviewData` 相关的渲染区域。

#### 10. Modal 打开/关闭清理

```typescript
// 新建按钮 onClick
onClick={() => {
  setEditingPkg(null);
  pkgForm.resetFields();
  setAddedProducts([]);
  setImportSearch("");
  setPriceRange([0, 300]);
  setPkgModalOpen(true);
  void prodData.reload();
}}

// Modal onCancel
onCancel={() => {
  setPkgModalOpen(false);
  pkgForm.resetFields();
  setAddedProducts([]);
  setImportModalOpen(false);
}}
```

---

## 验证标准

```powershell
cd E:\codex\WhatsApp\frontend
npx tsc --noEmit        # 0 errors
npm run build           # 通过
```

浏览器验证：
1. 新建商品包 → 填写目标金额 → 点击"自动配品" → 自动填充商品
2. 点击"导入商品" → 弹出商品库 → 搜索/价格滑块过滤 → 点击导入
3. 已配商品区显示件数+总价 → 可移除商品
4. 预览按钮已删除
5. 编辑商品包 → 已有商品自动加载到底部
6. 保存 → 列表刷新

---

## 约束

1. 不改后端
2. 不碰 H5
3. npm run build 通过
4. 一次性完成

---

## 发给前端会话的文本

```
你是前端 Agent（商品包配品重设计轮）。请读取 docs/task-plan-package-redesign.md，一次性完成 PKG-FIX-002 全部修改，不要中途暂停。

核心修改（EcommercePage.tsx）：

1. 删除可视化选品区和预览按钮/预览区域
2. 删除 selectedProductIds state，改为 addedProducts: ProductPackageItem[]
3. 在"完成奖励"后增加"⚡自动配品"按钮：
   - 校验目标金额已填
   - 调 assemblePreview 传全部商品 ID
   - 结果写入 addedProducts
4. 已配商品底部区域：
   - 显示 N 件 + 总价
   - 每行：图片+名称+价格+✕移除
   - 空状态提示"点击自动配品或导入商品"
5. "📦导入商品"按钮 → 弹出商品库 Modal：
   - 搜索框（商品名/标签）
   - 价格区间 Slider
   - 商品卡片网格（64x64图片+名称+价格）
   - 已添加的显示"已添加"(disabled)，未添加显示"导入"
   - 点击导入追加到 addedProducts
6. handlePkgSave 从 addedProducts 构建 payload
7. handlePkgEdit 从 pkg.items 加载 addedProducts
8. Modal 打开/关闭清理 addedProducts/importSearch/priceRange

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
