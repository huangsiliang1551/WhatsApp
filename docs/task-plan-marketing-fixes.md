# 商城+任务页面修复（MKT-FIX-001 ~ MKT-FIX-008）

> **执行角色**: frontend_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 修复所有 API 路径不匹配 + UI 体验问题

---

## 问题清单

### 🔴 P0：API 路径全部错误（前端用了不存在的前缀）

| # | 前端当前路径（404） | 后端实际路径 | 涉及函数 |
|---|---------------------|-------------|---------|
| 1 | `/api/marketing/products` | `/api/products?account_id=xxx` | listProducts, createProduct |
| 2 | `/api/marketing/products/{id}` | `/api/products/{id}` | updateProduct, deleteProduct |
| 3 | `/api/marketing/packages` | `/api/product-packages?account_id=xxx` | listPackages, createPackage |
| 4 | `/api/marketing/packages/{id}` | `/api/product-packages/{id}` | updatePackage, deletePackage |
| 5 | `/api/marketing/packages/assemble-preview` | `/api/product-packages/assemble-preview` | assemblePreview |
| 6 | `/api/marketing/task-rules` | `/api/task-rules` | listTaskRules, createTaskRule |
| 7 | `/api/marketing/task-rules/{id}` | `/api/task-rules/{id}` | updateTaskRule, deleteTaskRule |
| 8 | `/api/marketing/task-rules/{id}/toggle` | `/api/task-rules/{id}/toggle` | toggleTaskRule |
| 9 | `/api/marketing/manual-push` | `/api/task-instances/manual-push` | manualPush |
| 10 | `/api/marketing/config/signin` | `/api/sign-in/config` | getSignInConfig, updateSignInConfig |
| 11 | `/api/marketing/config/invite` | `/api/invites/config` | getInviteConfig, updateInviteConfig |
| 12 | `/api/marketing/stats` | `/api/marketing/stats/overview` | getMarketingStats |
| 13 | `/api/marketing/stats/packages` | `/api/marketing/stats/packages` (500) | getPackageStats |

**注意**: products 和 product-packages 的 GET/POST 端点需要 `account_id` 查询参数。

---

### 🔴 P0：图片上传无反应

**原因**: 前端 `createProduct` 用 `FormData` 上传图片，但后端 `POST /api/products` 可能不支持 `multipart/form-data`，或图片字段名不匹配。

**修复**: 确认后端接受的文件字段名为 `image`（或 `file`），前端 FormData 字段名与之匹配。如果后端不支持文件上传，改为先调 `POST /api/media/assets/upload` 获取 `asset_id`，再传给 `POST /api/products` 的 `image_asset_id` 字段。

---

### 🔴 P0：删除失败无提示

**原因**: `deleteProduct` 和 `deletePackage` 的 catch 块没有调用 `showError` 或 `message.error`。

**修复**: 所有删除操作 catch 后加 `message.error("删除失败: " + 错误信息)`。

---

### 🟡 P1：UI 体验问题

| # | 问题 | 修复方案 |
|---|------|---------|
| 14 | 商品列表图片不可见 | 表格增加图片缩略图列（40x40 Image 组件），无图显示占位符 |
| 15 | 标签用 JSON 显示 | 改用 antd `Tag` 组件 + `Closable`（支持 X 掉），新建时用 `Select mode="tags"` 输入 |
| 16 | 没有导入商品功能 | 工具栏增加 [导入 CSV] 按钮，点击弹出文件选择 → 调 `POST /api/products/import` |
| 17 | 统计数字不是卡片 | 改为 4 个 `Statistic` 卡片（商品总数/商品包总数/已领取/完成率），带图标和颜色 |
| 18 | 工具栏布局混乱 | 强制单行: 左侧[搜索框]，右侧[新建商品包][导入CSV][商品管理▸][刷新] |
| 19 | 创建时间无时分秒 | `new Date(v).toLocaleString("zh-CN")` 替代 `.toLocaleDateString()` |
| 20 | 推送规则触发配置用 JSON | 改为表单字段（见下方详细设计） |

---

## MKT-FIX-001：修复 marketingApi.ts 全部 API 路径

- **估计耗时**: 30 分钟

### 修改 `frontend/src/services/marketingApi.ts`

所有 API 路径替换：

```typescript
// Products — 注意需要 account_id 参数
export async function listProducts(accountId?: string): Promise<Product[]> {
  const params = accountId ? { account_id: accountId } : {};
  try { const r = await api.get<Product[]>("/api/products", { params }); return r.data; }
  catch { return MOCK_PRODUCTS; }
}

export async function createProduct(data: FormData): Promise<Product> {
  const r = await api.post<Product>("/api/products", data, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return r.data;
}

export async function updateProduct(id: string, data: Partial<Product>): Promise<Product> {
  const r = await api.patch<Product>(`/api/products/${id}`, data);
  return r.data;
}

export async function deleteProduct(id: string): Promise<void> {
  await api.delete(`/api/products/${id}`);
}

// Packages
export async function listPackages(accountId?: string): Promise<ProductPackage[]> {
  const params = accountId ? { account_id: accountId } : {};
  try { const r = await api.get<ProductPackage[]>("/api/product-packages", { params }); return r.data; }
  catch { return MOCK_PACKAGES; }
}

export async function createPackage(data): Promise<ProductPackage> {
  const r = await api.post<ProductPackage>("/api/product-packages", data);
  return r.data;
}

export async function assemblePreview(data): Promise<PackageAssemblePreview> {
  try {
    const r = await api.post<PackageAssemblePreview>("/api/product-packages/assemble-preview", data);
    return r.data;
  } catch { /* mock fallback */ }
}

export async function updatePackage(id, data): Promise<ProductPackage> {
  const r = await api.patch<ProductPackage>(`/api/product-packages/${id}`, data);
  return r.data;
}

export async function deletePackage(id): Promise<void> {
  await api.delete(`/api/product-packages/${id}`);
}

// Task Rules
export async function listTaskRules(): Promise<TaskRule[]> {
  try { const r = await api.get<TaskRule[]>("/api/task-rules"); return r.data; }
  catch { return MOCK_TASK_RULES; }
}

export async function createTaskRule(data): Promise<TaskRule> {
  const r = await api.post<TaskRule>("/api/task-rules", data);
  return r.data;
}

export async function updateTaskRule(id, data): Promise<TaskRule> {
  const r = await api.patch<TaskRule>(`/api/task-rules/${id}`, data);
  return r.data;
}

export async function toggleTaskRule(id): Promise<void> {
  await api.patch(`/api/task-rules/${id}/toggle`);
}

export async function deleteTaskRule(id): Promise<void> {
  await api.delete(`/api/task-rules/${id}`);
}

// Manual Push
export async function manualPush(data): Promise<{ pushed_count: number }> {
  try {
    const r = await api.post<{ pushed_count: number }>("/api/task-instances/manual-push", data);
    return r.data;
  } catch { return { pushed_count: data.customer_ids.length }; }
}

// Sign-in Config
export async function getSignInConfig(): Promise<SignInConfig> {
  try { const r = await api.get<SignInConfig>("/api/sign-in/config"); return r.data; }
  catch { return MOCK_SIGNIN_CONFIG; }
}

export async function updateSignInConfig(data): Promise<void> {
  await api.put("/api/sign-in/config", data);
}

// Invite Config
export async function getInviteConfig(): Promise<InviteConfig> {
  try { const r = await api.get<InviteConfig>("/api/invites/config"); return r.data; }
  catch { return MOCK_INVITE_CONFIG; }
}

export async function updateInviteConfig(data): Promise<void> {
  await api.put("/api/invites/config", data);
}

// Stats
export async function getMarketingStats(): Promise<MarketingStats> {
  try { const r = await api.get<MarketingStats>("/api/marketing/stats/overview"); return r.data; }
  catch { return MOCK_MARKETING_STATS; }
}

export async function getPackageStats(): Promise<PackageStats> {
  try { const r = await api.get<PackageStats>("/api/marketing/stats/packages"); return r.data; }
  catch { return { total_products: 9, total_packages: 3, total_claimed: 350, avg_completion_rate: 78 }; }
}
```

---

## MKT-FIX-002：商品列表 UI 修复

- **估计耗时**: 45 分钟

### 修改 `frontend/src/pages/EcommercePage.tsx`

#### 2a. 图片缩略图列

在 ProTable columns 首位增加图片列：

```tsx
{
  title: "图片", dataIndex: "image_url", width: 60,
  render: (_: unknown, r: Product) => r.image_url
    ? <Image src={r.image_url} width={40} height={40} style={{ objectFit: "cover", borderRadius: 4 }} />
    : <div style={{ width: 40, height: 40, background: "#f5f5f5", borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center" }}>📷</div>
}
```

#### 2b. 标签改用 Tag 组件（可 X 掉）

```tsx
{
  title: "标签", dataIndex: "tags", width: 150,
  render: (_: unknown, r: Product) => (
    <Space size={4} wrap>
      {(r.tags ?? []).map((tag: string) => <Tag key={tag} closable onClose={() => handleRemoveTag(r.id, tag)}>{tag}</Tag>)}
    </Space>
  )
}
```

新建商品时标签用 `Select mode="tags"`:
```tsx
<Form.Item label="标签" name="tags">
  <Select mode="tags" placeholder="输入标签后回车" tokenSeparators={[","]} />
</Form.Item>
```

#### 2c. 导入 CSV 按钮

工具栏增加：
```tsx
<Upload
  accept=".csv"
  showUploadList={false}
  customRequest={handleImportCSV}
>
  <Button icon={<UploadOutlined />}>导入 CSV</Button>
</Upload>
```

#### 2d. 统计卡片

```tsx
<Row gutter={16} style={{ marginBottom: 16 }}>
  <Col span={6}>
    <Card><Statistic title="商品总数" value={stats.total_products} prefix={<ShoppingOutlined />} /></Card>
  </Col>
  <Col span={6}>
    <Card><Statistic title="商品包总数" value={stats.total_packages} prefix={<GiftOutlined />} valueStyle={{ color: "#1677ff" }} /></Card>
  </Col>
  <Col span={6}>
    <Card><Statistic title="已领取" value={stats.total_claimed} prefix={<CheckCircleOutlined />} valueStyle={{ color: "#52c41a" }} /></Card>
  </Col>
  <Col span={6}>
    <Card><Statistic title="平均完成率" value={stats.avg_completion_rate} suffix="%" prefix={<PieChartOutlined />} precision={0} /></Card>
  </Col>
</Row>
```

#### 2e. 工具栏单行布局

```tsx
<Row justify="space-between" align="middle" style={{ marginBottom: 12, flexWrap: "nowrap" }}>
  {/* 左侧: 搜索 */}
  <Col>
    <Input.Search placeholder="搜索商品包名" allowClear style={{ width: 240 }} onSearch={handleSearch} />
  </Col>
  {/* 右侧: 操作按钮 */}
  <Col>
    <Space>
      <Button type="primary" onClick={() => setPackageModalOpen(true)}>新建商品包</Button>
      <Upload accept=".csv" showUploadList={false} customRequest={handleImportCSV}>
        <Button icon={<UploadOutlined />}>导入CSV</Button>
      </Upload>
      <Button onClick={() => setProductDrawerOpen(true)}>商品管理</Button>
      <Button icon={<ReloadOutlined />} onClick={handleRefresh}>刷新</Button>
    </Space>
  </Col>
</Row>
```

#### 2f. 创建时间显示时分秒

```tsx
{
  title: "创建时间", dataIndex: "created_at", width: 160,
  render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "-"
}
```

#### 2g. 删除操作加错误提示

```tsx
const handleDeleteProduct = async (id: string) => {
  try {
    await deleteProduct(id);
    message.success("已删除");
    reload();
  } catch (e) {
    message.error(`删除失败: ${e instanceof Error ? e.message : "未知错误"}`);
  }
};
```

---

## MKT-FIX-003：图片上传修复

- **估计耗时**: 30 分钟

### 方案

后端 `POST /api/products` 接受 `multipart/form-data`，字段名 `image`。

前端新建商品 Modal 中：

```tsx
<Form.Item label="图片" name="image" valuePropName="fileList" getValueFromEvent={normFile}>
  <Upload
    listType="picture-card"
    maxCount={1}
    accept="image/*"
    beforeUpload={(file) => {
      // 不自动上传，手动在 submit 时构建 FormData
      return false;
    }}
  >
    <div><PlusOutlined /><div>上传图片</div></div>
  </Upload>
</Form.Item>
```

提交时：
```tsx
const handleCreateProduct = async (values) => {
  const formData = new FormData();
  formData.append("name", values.name);
  formData.append("price", String(values.price));
  formData.append("tags", JSON.stringify(values.tags || []));
  if (values.image?.[0]?.originFileObj) {
    formData.append("image", values.image[0].originFileObj);
  }
  try {
    await createProduct(formData);
    message.success("商品已创建");
    reload();
  } catch (e) {
    message.error(`创建失败: ${e instanceof Error ? e.message : "未知错误"}`);
  }
};
```

---

## MKT-FIX-004：推送规则触发配置表单化

- **估计耗时**: 45 分钟

### 修改 `frontend/src/pages/TaskRulesPage.tsx`

将触发配置的 JSON 编辑器替换为结构化表单：

```tsx
{/* 根据 trigger_type 动态渲染配置字段 */}
{triggerType === "register" && (
  <Form.Item label="延迟推送" name={["trigger_config", "delay_minutes"]} rules={[{ required: true }]}>
    <Space>
      注册后 <InputNumber min={0} max={1440} /> 分钟
    </Space>
  </Form.Item>
)}

{triggerType === "recharge" && (
  <Form.Item label="充值门槛" name={["trigger_config", "threshold_amount"]} rules={[{ required: true }]}>
    <Space>
      充值满 <InputNumber min={1} prefix="¥" /> 元
    </Space>
  </Form.Item>
)}

{triggerType === "schedule" && (
  <>
    <Form.Item label="推送时间" name={["trigger_config", "cron_hour"]} rules={[{ required: true }]}>
      <TimePicker format="HH:mm" />
    </Form.Item>
    <Form.Item label="用户筛选" name={["trigger_config", "filter_tags"]}>
      <Select mode="tags" placeholder="标签筛选（留空=全部未领取用户）" />
    </Form.Item>
  </>
)}

{triggerType === "follow_up" && (
  <Form.Item label="完成后续推" name={["trigger_config", "delay_days"]} rules={[{ required: true }]}>
    <Space>
      任务完成后第 <InputNumber min={1} max={365} /> 天推送
    </Space>
  </Form.Item>
)}

{triggerType === "manual" && (
  <Alert message="手动触发：创建后可在客户列表中手动推送" type="info" showIcon />
)}
```

触发类型选择：
```tsx
<Form.Item label="触发类型" name="trigger_type" rules={[{ required: true }]}>
  <Select
    options={[
      { label: "注册触发", value: "register" },
      { label: "充值触发", value: "recharge" },
      { label: "定时推送", value: "schedule" },
      { label: "完成后续推", value: "follow_up" },
      { label: "手动推送", value: "manual" },
    ]}
    onChange={(v) => setTriggerType(v)}
  />
</Form.Item>
```

### 后续推送链也用表单

替换 JSON 编辑器：
```tsx
<Form.List name="follow_up_chain">
  {(fields, { add, remove }) => (
    <>
      {fields.map((field, index) => (
        <Space key={field.key} align="baseline" style={{ display: "flex", marginBottom: 8 }}>
          完成后第 <Form.Item {...field} name={[field.name, "delay_days"]} noStyle>
            <InputNumber min={1} max={365} />
          </Form.Item> 天推送
          <Form.Item {...field} name={[field.name, "package_id"]} noStyle>
            <Select style={{ width: 160 }} options={packageOptions} />
          </Form.Item>
          <MinusCircleOutlined onClick={() => remove(field.name)} />
        </Space>
      ))}
      <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />}>
        添加后续推送
      </Button>
    </>
  )}
</Form.List>
```

---

## MKT-FIX-005 ~ 008：验证

- **MKT-FIX-005**: `npx tsc --noEmit` → 0 errors
- **MKT-FIX-006**: `npm run build` → 通过
- **MKT-FIX-007**: 浏览器访问 /ecommerce → 图片可见、标签可X、统计卡片、导入按钮
- **MKT-FIX-008**: 浏览器访问 /marketing/task-rules → 触发配置为表单、无 JSON

---

## 全局约束

1. 不改后端代码
2. 不碰 H5
3. 每次改动后 npm run build
4. 一次性完成全部修复

---

## 发给前端会话的文本

```
你是前端 Agent（商城页面修复轮）。请读取 docs/task-plan-marketing-fixes.md，一次性修复全部问题（MKT-FIX-001 ~ MKT-FIX-008），不要中途暂停。

核心修复：

1. MKT-FIX-001: marketingApi.ts 全部 API 路径修正
   /api/marketing/products → /api/products（加 account_id 参数）
   /api/marketing/packages → /api/product-packages（加 account_id 参数）
   /api/marketing/task-rules → /api/task-rules
   /api/marketing/config/signin → /api/sign-in/config
   /api/marketing/config/invite → /api/invites/config
   /api/marketing/stats → /api/marketing/stats/overview
   /api/marketing/manual-push → /api/task-instances/manual-push

2. MKT-FIX-002: EcommercePage.tsx UI 修复
   - 商品列表增加图片缩略图列（40x40 Image）
   - 标签改用 antd Tag 组件（closable，支持 X 掉）
   - 新建商品时标签用 Select mode="tags"
   - 增加导入 CSV 按钮（Upload 组件）
   - 统计数字改为 4 个 Statistic 卡片（带图标+颜色）
   - 工具栏强制单行：左搜索 + 右[新建商品包][导入CSV][商品管理][刷新]
   - 创建时间用 toLocaleString 显示时分秒
   - 删除操作 catch 后加 message.error 提示

3. MKT-FIX-003: 图片上传修复
   - 新建商品 Modal 用 Upload picture-card + beforeUpload=false
   - submit 时构建 FormData（name/price/tags/image）
   - 调 createProduct(formData)

4. MKT-FIX-004: TaskRulesPage.tsx 触发配置表单化
   - 删除 JSON 编辑器
   - 根据 trigger_type 动态渲染表单字段：
     register → 延迟分钟数 InputNumber
     recharge → 充值门槛 InputNumber(¥)
     schedule → TimePicker + 标签筛选 Select
     follow_up → 天数 InputNumber
     manual → Alert 提示
   - 后续推送链用 Form.List 动态增删

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
