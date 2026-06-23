# H5 多租户系统 — 前端完整实现（H5MT-FE-FINAL）

> **执行角色**: frontend_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 实现 H5 多租户前端完整功能：动态语言 UI + H5 来源筛选 + 站点权限 UI

---

## 一、动态语言管理 UI

### 1.1 语言管理页面（SettingsPage 新增 Tab）

```tsx
// frontend/src/pages/SettingsPage.tsx 新增 "语言管理" Tab

{
  key: "languages",
  label: "语言管理",
  children: (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Typography.Text>管理系统支持的语言，新增后 H5 站点可选择使用。</Typography.Text>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setLangModalOpen(true)}>
            新增语言
          </Button>
        </Col>
      </Row>

      <Table
        dataSource={languages}
        columns={[
          { title: "语言代码", dataIndex: "language_code", width: 100 },
          { 
            title: "显示名称", 
            dataIndex: "display_name",
            render: (name, record) => (
              <Space>
                {record.flag_emoji && <span>{record.flag_emoji}</span>}
                <span>{name}</span>
                {record.is_default && <Tag color="blue">默认</Tag>}
              </Space>
            ),
          },
          { 
            title: "状态",
            dataIndex: "is_enabled",
            render: (v) => <Tag color={v ? "success" : "default"}>{v ? "启用" : "禁用"}</Tag>,
          },
          {
            title: "操作",
            render: (_, record) => (
              <Space>
                <Button type="link" onClick={() => handleEditLang(record)}>编辑</Button>
                {!record.is_default && (
                  <Button type="link" onClick={() => handleSetDefault(record.id)}>
                    设为默认
                  </Button>
                )}
                <DangerButton
                  label="删除"
                  onConfirm={() => handleDeleteLang(record.id)}
                  type="link"
                  danger
                />
              </Space>
            ),
          },
        ]}
        rowKey="id"
        size="small"
      />

      {/* 新增/编辑语言 Modal */}
      <Modal
        title={editingLang ? "编辑语言" : "新增语言"}
        open={langModalOpen}
        onCancel={() => setLangModalOpen(false)}
        onOk={() => langForm.submit()}
      >
        <Form form={langForm} layout="vertical">
          <Form.Item label="语言代码" name="language_code" rules={[{ required: true }]}>
            <Input placeholder="zh-CN / en-US / ja-JP" disabled={!!editingLang} />
          </Form.Item>
          <Form.Item label="显示名称" name="display_name" rules={[{ required: true }]}>
            <Input placeholder="中文 / English / 日本語" />
          </Form.Item>
          <Form.Item label="国旗 Emoji" name="flag_emoji">
            <Input placeholder="🇨🇳 🇺🇸 🇯🇵" />
          </Form.Item>
          <Form.Item label="启用" name="is_enabled" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  ),
}
```

### 1.2 站点翻译管理（SitesPage 增强）

在站点卡片的操作菜单中增加"翻译管理"选项：

```tsx
// SitesPage.tsx 站点卡片 Dropdown 菜单增加
{
  key: "translations",
  label: "翻译管理",
  onClick: () => handleOpenTranslations(site),
}
```

点击后打开 Drawer，显示该站点的所有翻译：

```tsx
<Drawer title={`${site.brand_name} 翻译管理`} width={640} open={translationsOpen} onClose={...}>
  <Space direction="vertical" style={{ width: "100%" }} size={16}>
    {/* 语言选择 */}
    <Select
      style={{ width: 200 }}
      value={selectedLang}
      onChange={setSelectedLang}
      options={languages.map(l => ({ label: `${l.flag_emoji} ${l.display_name}`, value: l.language_code }))}
    />

    {/* 翻译列表 */}
    <Table
      dataSource={translations}
      columns={[
        { title: "Key", dataIndex: "translation_key", width: 200 },
        { 
          title: "翻译文本",
          dataIndex: "translated_text",
          render: (text, record) => (
            <Space>
              <Typography.Text>{text}</Typography.Text>
              {record.is_ai_translated && <Tag color="orange">AI</Tag>}
            </Space>
          ),
        },
        {
          title: "操作",
          render: (_, record) => (
            <Space>
              <Button type="link" onClick={() => handleEditTranslation(record)}>编辑</Button>
              <Button type="link" onClick={() => handleRetranslate(record)}>
                <ReloadOutlined /> 重新翻译
              </Button>
            </Space>
          ),
        },
      ]}
    />

    {/* 批量翻译按钮 */}
    <Button
      type="primary"
      onClick={() => handleBatchTranslate(site.id, selectedLang)}
      loading={translating}
    >
      AI 批量翻译缺失项
    </Button>
  </Space>
</Drawer>
```

---

## 二、H5 来源筛选（10 个页面）

### 2.1 ChatPage（会话列表 H5 筛选）

```tsx
// frontend/src/pages/ChatPage.tsx 修改

// 在筛选区增加 H5 站点筛选
<Col>
  <Select
    placeholder="H5 站点"
    allowClear
    style={{ width: 160 }}
    value={siteFilter}
    onChange={setSiteFilter}
    options={sites.map(s => ({ label: s.brand_name || s.site_key, value: s.site_key }))}
  />
</Col>

// 查询时传递 site_key
const ws = useWorkspaceState({ accountId, siteKey: siteFilter });
```

### 2.2 CustomersPage（显示注册来源）

```tsx
// frontend/src/pages/CustomersPage.tsx 修改

// 表格增加"来源 H5"列
{
  title: "来源 H5",
  dataIndex: "registration_site_id",
  width: 120,
  render: (siteId) => {
    const site = sites.find(s => s.id === siteId);
    return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
  },
},

// 增加 H5 筛选
<Col>
  <Select
    placeholder="来源 H5"
    allowClear
    style={{ width: 160 }}
    value={siteFilter}
    onChange={setSiteFilter}
    options={sites.map(s => ({ label: s.brand_name || s.site_key, value: s.id }))}
  />
</Col>
```

### 2.3 UsersPage（显示注册站点 + 筛选）

```tsx
// frontend/src/pages/UsersPage.tsx 修改

// 表格"站点"列改为显示站点名
{
  title: "注册站点",
  dataIndex: "registration_site_id",
  width: 120,
  render: (siteId) => {
    const site = sites.find(s => s.id === siteId);
    return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
  },
},

// 增加 H5 筛选
<Col>
  <Select
    placeholder="注册站点"
    allowClear
    style={{ width: 160 }}
    value={siteFilter}
    onChange={setSiteFilter}
    options={sites.map(s => ({ label: s.brand_name || s.site_key, value: s.id }))}
  />
</Col>
```

### 2.4 MembersPage（H5 筛选）

```tsx
// frontend/src/pages/MembersPage.tsx 修改

// 增加 H5 站点筛选
<Col>
  <Select
    placeholder="H5 站点"
    allowClear
    style={{ width: 160 }}
    value={siteFilter}
    onChange={setSiteFilter}
    options={sites.map(s => ({ label: s.brand_name || s.site_key, value: s.site_key }))}
  />
</Col>
```

### 2.5 TicketsPage（显示客户来源 H5）

```tsx
// frontend/src/pages/TicketsPage.tsx 修改

// 表格增加"客户来源"列
{
  title: "客户来源",
  dataIndex: "site_key",
  width: 120,
  render: (siteKey) => {
    const site = sites.find(s => s.site_key === siteKey);
    return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
  },
},

// 增加 H5 筛选
<Col>
  <Select placeholder="客户来源" allowClear style={{ width: 160 }} ... />
</Col>
```

### 2.6 TasksPage（显示用户来源 H5）

```tsx
// frontend/src/pages/TasksPage.tsx 修改

// 表格增加"用户来源"列
{
  title: "用户来源",
  dataIndex: "site_key",
  width: 120,
  render: (siteKey) => {
    const site = sites.find(s => s.site_key === siteKey);
    return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
  },
},
```

### 2.7 ReviewsPage（显示用户来源 H5）

```tsx
// frontend/src/pages/ReviewsPage.tsx 修改

// 表格增加"用户来源"列
{
  title: "用户来源",
  dataIndex: "site_key",
  width: 120,
  render: (siteKey) => {
    const site = sites.find(s => s.site_key === siteKey);
    return site ? <Tag color="blue">{site.brand_name || site.site_key}</Tag> : "-";
  },
},
```

### 2.8 AssignmentsPage（H5 筛选）

```tsx
// frontend/src/pages/AssignmentsPage.tsx 修改

// 增加 H5 站点筛选
<Col>
  <Select placeholder="H5 站点" allowClear style={{ width: 160 }} ... />
</Col>
```

### 2.9 ReportsPage（H5 筛选）

```tsx
// frontend/src/pages/ReportsPage.tsx 修改

// 增加 H5 站点筛选
<Col>
  <Select placeholder="H5 站点" allowClear style={{ width: 160 }} ... />
</Col>
```

### 2.10 WhatsAppStatsPage（H5 筛选）

```tsx
// frontend/src/pages/WhatsAppStatsPage.tsx 修改

// 增加 H5 站点筛选
<Col>
  <Select placeholder="H5 站点" allowClear style={{ width: 160 }} ... />
</Col>
```

---

## 三、站点权限 UI

### 3.1 站点权限管理（SitesPage 增强）

在站点卡片操作菜单增加"权限管理"：

```tsx
// SitesPage.tsx 站点卡片 Dropdown 菜单增加
{
  key: "permissions",
  label: "权限管理",
  onClick: () => handleOpenPermissions(site),
}
```

点击后打开 Drawer：

```tsx
<Drawer title={`${site.brand_name} 权限管理`} width={520} open={permissionsOpen} onClose={...}>
  <Space direction="vertical" style={{ width: "100%" }} size={16}>
    <Row justify="space-between" align="middle">
      <Col>
        <Typography.Text>管理站点访问权限（4 角色：管理员/编辑/分析师/客服）</Typography.Text>
      </Col>
      <Col>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setPermModalOpen(true)}>
          添加权限
        </Button>
      </Col>
    </Row>

    <Table
      dataSource={permissions}
      columns={[
        { 
          title: "用户",
          dataIndex: "user_id",
          render: (userId) => {
            const user = users.find(u => u.id === userId);
            return user?.display_name || userId;
          },
        },
        {
          title: "角色",
          dataIndex: "role",
          render: (role) => (
            <Tag color={roleColors[role]}>
              {roleLabels[role]}
            </Tag>
          ),
        },
        {
          title: "操作",
          render: (_, record) => (
            <Space>
              <Button type="link" onClick={() => handleEditRole(record)}>修改角色</Button>
              <DangerButton label="撤销" onConfirm={() => handleRevoke(record.id)} type="link" danger />
            </Space>
          ),
        },
      ]}
    />
  </Space>

  {/* 添加权限 Modal */}
  <Modal title="添加权限" open={permModalOpen} ...>
    <Form form={permForm} layout="vertical">
      <Form.Item label="用户" name="user_id" rules={[{ required: true }]}>
        <Select
          showSearch
          options={users.map(u => ({ label: u.display_name || u.id, value: u.id }))}
        />
      </Form.Item>
      <Form.Item label="角色" name="role" rules={[{ required: true }]}>
        <Select
          options={[
            { label: "管理员（全部权限）", value: "admin" },
            { label: "编辑（编辑站点配置）", value: "editor" },
            { label: "分析师（只读数据）", value: "analyst" },
            { label: "客服（仅查看会话）", value: "support" },
          ]}
        />
      </Form.Item>
    </Form>
  </Modal>
</Drawer>
```

---

## 四、API 层

### 4.1 新增 h5MultiTenantApi.ts

```typescript
// frontend/src/services/h5MultiTenantApi.ts (~200行)

// 语言管理
export async function listLanguages(): Promise<H5Language[]>
export async function createLanguage(data: CreateLanguageRequest): Promise<H5Language>
export async function updateLanguage(id: string, data: UpdateLanguageRequest): Promise<H5Language>
export async function deleteLanguage(id: string): Promise<void>
export async function setDefaultLanguage(id: string): Promise<void>

// 翻译管理
export async function getTranslations(siteId: string, langCode: string): Promise<Record<string, string>>
export async function translateKey(siteId: string, langCode: string, data: TranslateKeyRequest): Promise<string>
export async function batchTranslate(siteId: string, langCode: string, data: BatchTranslateRequest): Promise<Record<string, string>>

// 站点权限
export async function getUserPermissions(userId: string): Promise<SitePermission[]>
export async function getSitePermissions(siteId: string): Promise<SitePermission[]>
export async function grantPermission(data: GrantPermissionRequest): Promise<SitePermission>
export async function revokePermission(id: string): Promise<void>
export async function updatePermissionRole(id: string, role: string): Promise<SitePermission>

// 部署
export async function generateDeployScript(siteId: string): Promise<string>
export async function verifyDeployment(siteId: string): Promise<DeployVerification>

// 站点列表（增强）
export async function listSitesEnhanced(): Promise<H5SiteEnhanced[]>
```

---

## 五、任务清单

| 任务 | 文件 | 行数 |
|------|------|------|
| 语言管理 Tab | SettingsPage.tsx | +100 行 |
| 翻译管理 Drawer | SitesPage.tsx | +150 行 |
| ChatPage H5 筛选 | ChatPage.tsx | +20 行 |
| CustomersPage 来源显示+筛选 | CustomersPage.tsx | +30 行 |
| UsersPage 来源显示+筛选 | UsersPage.tsx | +30 行 |
| MembersPage H5 筛选 | MembersPage.tsx | +15 行 |
| TicketsPage 来源显示+筛选 | TicketsPage.tsx | +25 行 |
| TasksPage 来源显示 | TasksPage.tsx | +15 行 |
| ReviewsPage 来源显示 | ReviewsPage.tsx | +15 行 |
| AssignmentsPage H5 筛选 | AssignmentsPage.tsx | +15 行 |
| ReportsPage H5 筛选 | ReportsPage.tsx | +15 行 |
| WhatsAppStatsPage H5 筛选 | WhatsAppStatsPage.tsx | +15 行 |
| 权限管理 Drawer | SitesPage.tsx | +120 行 |
| h5MultiTenantApi.ts | services/h5MultiTenantApi.ts | ~200 行 |
| **总计** | | ~800 行 |

---

## 发给前端 Agent 的文本

```
你是前端 Agent（H5 多租户最终轮）。请读取 docs/task-plan-h5-mt-frontend-final.md，一次性实现全部前端任务，不要中途暂停。

核心任务：

1. 动态语言管理 UI：
   - SettingsPage 新增"语言管理" Tab（CRUD + 设为默认）
   - SitesPage 站点卡片增加"翻译管理" Drawer（翻译列表 + AI 批量翻译）

2. H5 来源筛选（10 个页面）：
   - ChatPage: 增加 H5 站点筛选下拉
   - CustomersPage: 显示注册来源 H5 + 筛选
   - UsersPage: 显示注册站点名 + 筛选
   - MembersPage: 增加 H5 筛选
   - TicketsPage: 显示客户来源 H5 + 筛选
   - TasksPage: 显示用户来源 H5
   - ReviewsPage: 显示用户来源 H5
   - AssignmentsPage: 增加 H5 筛选
   - ReportsPage: 增加 H5 筛选
   - WhatsAppStatsPage: 增加 H5 筛选

3. 站点权限 UI：
   - SitesPage 站点卡片增加"权限管理" Drawer
   - 4 角色：管理员/编辑/分析师/客服

4. API 层：
   - h5MultiTenantApi.ts（语言/翻译/权限/部署 API）

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
