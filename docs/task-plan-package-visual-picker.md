# 商品包可视化选品修复（PKG-FIX-001）

> **执行角色**: frontend_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 将商品包创建/编辑的商品选择从 JSON 输入改为可视化选品

---

## 问题

当前 `EcommercePage.tsx` 的商品包创建/编辑 Modal 使用 `TextArea` 让用户手动输入 JSON 格式的商品列表（第 355-358 行），对非技术用户不友好。

另外"预览凑包结果"按钮（第 358-361 行）在校验时检查的是 `items_json` 字段（JSON 字符串），改为可视化选品后需要改为检查已选商品列表。

---

## 修改方案

### 修改文件

`frontend/src/pages/EcommercePage.tsx`

### 具体改动

#### 1. 新增状态：已选商品 ID 列表

在 Package CRUD state 区域（约第 36-41 行）新增：

```typescript
const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
```

#### 2. 替换 JSON TextArea 为可视化选品区

删除第 355-358 行的 `Form.Item` (items_json)，替换为：

```tsx
<Form.Item label="选择商品" required>
  <div style={{ maxHeight: 300, overflow: "auto", border: "1px solid #d9d9d9", borderRadius: 6, padding: 8 }}>
    <Row gutter={[8, 8]}>
      {filteredProds.map((prod) => {
        const isSelected = selectedProductIds.includes(prod.id);
        return (
          <Col key={prod.id} span={12}>
            <Card
              size="small"
              hoverable
              onClick={() => {
                setSelectedProductIds((prev) =>
                  isSelected ? prev.filter((id) => id !== prod.id) : [...prev, prod.id]
                );
              }}
              styles={{
                body: { padding: 8, display: "flex", alignItems: "center", gap: 8 },
              }}
              style={{
                border: isSelected ? "2px solid #1677ff" : "1px solid #d9d9d9",
                background: isSelected ? "#e6f4ff" : "#fff",
                cursor: "pointer",
              }}
            >
              {prod.image_url ? (
                <Image src={prod.image_url} width={36} height={36} style={{ objectFit: "cover", borderRadius: 4 }} preview={false} />
              ) : (
                <div style={{ width: 36, height: 36, background: "#f5f5f5", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>📷</div>
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <Typography.Text ellipsis style={{ fontSize: 12, display: "block" }}>{prod.name}</Typography.Text>
                <Typography.Text strong style={{ fontSize: 12 }}>¥{prod.price.toFixed(2)}</Typography.Text>
              </div>
              {isSelected && <CheckCircleOutlined style={{ color: "#1677ff", fontSize: 16 }} />}
            </Card>
          </Col>
        );
      })}
    </Row>
    {filteredProds.length === 0 && (
      <div style={{ textAlign: "center", padding: 24, color: "#999" }}>
        暂无商品，请先在"商品管理"中添加商品
      </div>
    )}
  </div>
  <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: "block" }}>
    已选 {selectedProductIds.length} 个商品
    {selectedProductIds.length > 0 && (
      <span>，总价 ¥{
        selectedProductIds
          .map((id) => products.find((p) => p.id === id)?.price ?? 0)
          .reduce((s, p) => s + p, 0)
          .toFixed(2)
      }</span>
    )}
  </Typography.Text>
</Form.Item>
```

#### 3. 修改 handlePkgSave

替换第 109-138 行的 `handlePkgSave` 函数：

```typescript
const handlePkgSave = async (values: { name: string; target_amount: number; margin_percent: number; reward_amount: number }) => {
  if (selectedProductIds.length === 0) {
    showError("请至少选择一个商品");
    return;
  }
  setPkgSaving(true);
  try {
    const items: ProductPackageItem[] = selectedProductIds.map((pid) => {
      const prod = products.find((p) => p.id === pid);
      return {
        product_id: pid,
        product_name: prod?.name ?? pid,
        price: prod?.price ?? 0,
        quantity: 1,
      };
    });

    const payload = {
      name: values.name,
      account_id: accountId,
      target_amount: values.target_amount,
      amount_tolerance_pct: values.margin_percent,
      product_count: items.length,
      product_ids: selectedProductIds,
      product_snapshot: items,
      total_value: items.reduce((s, i) => s + i.price * i.quantity, 0),
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
    setSelectedProductIds([]);
    setAssemblePreviewData(null);
    void reload();
  } catch {
    showError("保存失败");
  } finally {
    setPkgSaving(false);
  }
};
```

#### 4. 修改 handlePkgEdit

替换第 140-151 行的 `handlePkgEdit` 函数：

```typescript
const handlePkgEdit = (pkg: ProductPackage) => {
  setEditingPkg(pkg);
  pkgForm.setFieldsValue({
    name: pkg.name,
    target_amount: pkg.target_amount,
    margin_percent: pkg.margin_percent ?? pkg.amount_tolerance_pct,
    reward_amount: pkg.reward_amount,
  });
  // Pre-select products from existing package
  const ids = pkg.product_ids ?? pkg.items?.map((i) => i.product_id) ?? [];
  setSelectedProductIds(ids);
  setAssemblePreviewData({
    total_amount: pkg.items?.reduce((s, i) => s + i.price * i.quantity, 0) ?? 0,
    within_range: true,
    items: pkg.items ?? [],
  });
  setPkgModalOpen(true);
  // Ensure products are loaded for selection
  void prodData.reload();
};
```

#### 5. 修改 handlePreviewAssemble

替换第 158-171 行的 `handlePreviewAssemble` 函数：

```typescript
const handlePreviewAssemble = async () => {
  const target = pkgForm.getFieldValue("target_amount");
  if (!target) {
    showError("请先填写目标金额");
    return;
  }
  if (selectedProductIds.length === 0) {
    showError("请先选择商品");
    return;
  }
  const margin = pkgForm.getFieldValue("margin_percent") || 10;
  setPreviewLoading(true);
  try {
    const result = await assemblePreview({
      target_amount: target,
      margin_percent: margin,
      product_ids: selectedProductIds,
    });
    setAssemblePreviewData(result);
  } catch {
    // Fallback: calculate locally
    const items: ProductPackageItem[] = selectedProductIds.map((pid) => {
      const prod = products.find((p) => p.id === pid);
      return { product_id: pid, product_name: prod?.name ?? pid, price: prod?.price ?? 0, quantity: 1 };
    });
    const total = items.reduce((s, i) => s + i.price * i.quantity, 0);
    const minAmt = target * (1 - margin / 100);
    const maxAmt = target * (1 + margin / 100);
    setAssemblePreviewData({
      total_amount: total,
      within_range: total >= minAmt && total <= maxAmt,
      items,
    });
  } finally {
    setPreviewLoading(false);
  }
};
```

#### 6. 清理 Modal 打开时的状态

修改第 208 行的新建商品包按钮 onClick：

```typescript
onClick={() => {
  setEditingPkg(null);
  pkgForm.resetFields();
  setSelectedProductIds([]);
  setAssemblePreviewData(null);
  setPkgModalOpen(true);
  void prodData.reload();  // 确保商品列表已加载
}}
```

#### 7. 修改 Modal 关闭时的清理

修改第 338 行的 onCancel：

```typescript
onCancel={() => {
  setPkgModalOpen(false);
  pkgForm.resetFields();
  setSelectedProductIds([]);
  setAssemblePreviewData(null);
}}
```

#### 8. Modal 内搜索商品

在选品区上方增加搜索框（在 `<Form.Item label="选择商品">` 前面加）：

```tsx
<Input
  placeholder="搜索商品…"
  prefix={<SearchOutlined />}
  allowClear
  style={{ marginBottom: 8 }}
  value={prodSearch}
  onChange={(e) => setProdSearch(e.target.value)}
/>
```

---

## 验证标准

```powershell
cd E:\codex\WhatsApp\frontend
npx tsc --noEmit        # 0 errors
npm run build           # 通过
```

浏览器验证：
1. 新建商品包 → 看到可视化商品选择区（卡片式，可点击选中/取消）
2. 选中商品后显示蓝色边框 + 对勾图标
3. 底部显示"已选 N 个商品，总价 ¥xxx"
4. 预览按钮：未填目标金额 → 提示"请先填写目标金额"
5. 预览按钮：未选商品 → 提示"请先选择商品"
6. 编辑商品包 → 已有商品自动选中
7. 保存成功 → 列表刷新

---

## 约束

1. 不改后端
2. 不碰 H5
3. npm run build 通过
4. 一次性完成

---

## 发给前端会话的文本

```
你是前端 Agent（商品包选品修复轮）。请读取 docs/task-plan-package-visual-picker.md，一次性完成 PKG-FIX-001 全部修改，不要中途暂停。

核心修改（EcommercePage.tsx）：

1. 新增 selectedProductIds state（string[]）
2. 删除 items_json TextArea，替换为可视化选品区：
   - Row+Col 卡片网格，每个商品一张卡片（图片+名称+价格）
   - 点击选中/取消，选中时蓝色边框+对勾
   - 底部显示"已选 N 个商品，总价 ¥xxx"
   - 选品区上方增加搜索框（复用 prodSearch）
3. handlePkgSave: 从 selectedProductIds 构建 items 数组，不再解析 JSON
4. handlePkgEdit: 用 pkg.product_ids 或 pkg.items 预选商品
5. handlePreviewAssemble: 校验 target_amount + selectedProductIds（非 JSON）
6. Modal 打开/关闭时清理 selectedProductIds
7. 新建按钮点击时调 prodData.reload() 确保商品列表加载

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
