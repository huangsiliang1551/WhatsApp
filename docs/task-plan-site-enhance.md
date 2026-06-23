# 站点管理页面 P0+P1 功能迭代（SITE-ENHANCE）

> **执行角色**: frontend_agent + api_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 增强站点管理页面，提升运营效率和用户体验

---

## 一、功能清单

### P0 高优先级（4 个功能）

| # | 功能 | 说明 |
|---|------|------|
| 1 | 站点健康状态指示器 | 🟢🟡🔴⚪ 状态指示器 + 最后验证时间 |
| 2 | 站点数据统计卡片 | 用户数/活跃数/签到数/任务完成率/收入 |
| 3 | 批量操作 | 批量暂停/恢复/删除/更新配置 |
| 4 | 最后验证时间 | 显示最后验证时间 + 自动刷新设置 |

### P1 中优先级（5 个功能）

| # | 功能 | 说明 |
|---|------|------|
| 5 | 站点克隆 | 一键克隆配置创建新站点（含翻译+权限） |
| 6 | 配置导入导出 | 导出 JSON + 导入创建 |
| 7 | 站点对比 | 多站点对比指标表格 |
| 8 | 域名管理增强 | DNS 验证 + SSL 到期提醒 |
| 9 | 部署流水线可视化 | Build → Deploy → Verify 可视化 + 历史 |

---

## 二、后端任务（SITE-BE）

### SITE-BE-001：站点分析 API（P0）

- **估计耗时**: 60 分钟

#### 新增 API

```
GET /api/h5/sites/{site_id}/analytics
```

#### 响应结构

```json
{
  "site_id": "site-001",
  "total_users": 1234,
  "active_users_today": 234,
  "sign_in_count_today": 89,
  "task_completion_rate": 87.5,
  "revenue_today": 12345.67,
  "last_verified_at": "2026-06-16T10:30:00Z",
  "health_status": "healthy"  // healthy/warning/error/unverified
}
```

#### 实现位置

- **新增**: `app/services/h5_site_analytics_service.py` (~150 行)
- **新增**: `app/api/routes/h5_site_analytics.py` (~80 行)
- **迁移**: 无需（使用现有表聚合查询）

---

### SITE-BE-002：站点克隆 API（P1）

- **估计耗时**: 45 分钟

#### 新增 API

```
POST /api/h5/sites/{site_id}/clone
Body: {
  "new_site_key": "wechat-02",
  "new_brand_name": "我的站点 2",
  "new_domain": "h5-wechat-02.example.com",
  "clone_brand_config": true,
  "clone_deploy_config": true,
  "clone_translations": false,
  "clone_permissions": false
}
```

#### 实现位置

- **修改**: `app/services/h5_site_service.py` 增加 `clone_site()` 方法 (~100 行)
- **修改**: `app/api/routes/platform.py` 增加 clone 端点 (~30 行)

---

### SITE-BE-003：站点配置导入导出 API（P1）

- **估计耗时**: 30 分钟

#### 新增 API

```
GET /api/h5/sites/{site_id}/export-config
Response: JSON 配置文件下载

POST /api/h5/sites/import-config
Body: JSON 配置文件
Response: 新创建的站点
```

#### 实现位置

- **修改**: `app/services/h5_site_service.py` 增加 `export_config()` / `import_config()` (~80 行)
- **修改**: `app/api/routes/platform.py` 增加 2 个端点 (~40 行)

---

### SITE-BE-004：批量操作 API（P0）

- **估计耗时**: 30 分钟

#### 新增 API

```
POST /api/h5/sites/batch-update
Body: {
  "site_ids": ["site-001", "site-002"],
  "action": "pause" | "resume" | "delete" | "update_config",
  "config": { ... }  // 仅 update_config 时需要
}
```

#### 实现位置

- **修改**: `app/services/h5_site_service.py` 增加 `batch_update()` (~60 行)
- **修改**: `app/api/routes/platform.py` 增加 batch 端点 (~30 行)

---

### SITE-BE-005：域名验证 API（P1）

- **估计耗时**: 30 分钟

#### 新增 API

```
POST /api/h5/sites/{site_id}/verify-dns
Response: {
  "dns_valid": true,
  "a_record": "1.2.3.4",
  "ssl_valid": true,
  "ssl_expires_at": "2026-09-16T00:00:00Z",
  "ssl_days_remaining": 92
}
```

#### 实现位置

- **新增**: `app/services/domain_verification_service.py` (~100 行)
- **新增**: `app/api/routes/domain_verification.py` (~40 行)

---

### SITE-BE-006：部署历史 API（P1）

- **估计耗时**: 30 分钟

#### 新增表

```sql
CREATE TABLE deploy_history (
  id VARCHAR(36) PRIMARY KEY,
  site_id VARCHAR(36) REFERENCES h5_sites(id),
  action VARCHAR(32),  -- build/deploy/verify/rollback
  status VARCHAR(32),  -- success/error
  details JSON,
  created_by VARCHAR(36),
  created_at TIMESTAMP
);
```

#### 新增 API

```
GET /api/h5/sites/{site_id}/deploy-history
Response: 部署历史列表

POST /api/h5/sites/{site_id}/deploy-history
Body: { action: "deploy", status: "success", details: {...} }
```

#### 实现位置

- **迁移**: `alembic/versions/20260616_0088_deploy_history.py` (~40 行)
- **新增**: `app/services/deploy_history_service.py` (~80 行)
- **新增**: `app/api/routes/deploy_history.py` (~40 行)

---

## 三、前端任务（SITE-FE）

### SITE-FE-001：站点健康状态指示器（P0）

- **估计耗时**: 30 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

在站点卡片中增加健康状态指示器：

```tsx
// 在站点卡片中增加
<Space>
  <Tag color={healthColors[site.health_status]}>
    {healthIcons[site.health_status]} {healthLabels[site.health_status]}
  </Tag>
  <Typography.Text type="secondary">
    最后验证: {formatTimeAgo(site.last_verified_at)}
  </Typography.Text>
</Space>
```

**状态定义**:
- 🟢 healthy（正常）
- 🟡 warning（警告，> 1 小时未验证）
- 🔴 error（异常，最后验证失败）
- ⚪ unverified（未验证）

---

### SITE-FE-002：站点数据统计卡片（P0）

- **估计耗时**: 45 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

将站点列表从 Table 改为 Card Grid，每个站点卡片显示统计数据：

```tsx
<Card
  title={
    <Space>
      <Tag color={healthColors[site.health_status]}>
        {healthIcons[site.health_status]}
      </Tag>
      <Typography.Text strong>{site.brand_name}</Typography.Text>
    </Space>
  }
  extra={
    <Dropdown menu={{ items: getActionItems(site) }}>
      <Button type="text" icon={<EllipsisOutlined />} />
    </Dropdown>
  }
>
  <Row gutter={[16, 16]}>
    <Col span={8}>
      <Statistic title="用户" value={analytics.total_users} />
    </Col>
    <Col span={8}>
      <Statistic title="今日活跃" value={analytics.active_users_today} />
    </Col>
    <Col span={8}>
      <Statistic title="今日签到" value={analytics.sign_in_count_today} />
    </Col>
    <Col span={8}>
      <Statistic title="任务完成率" value={analytics.task_completion_rate} suffix="%" />
    </Col>
    <Col span={8}>
      <Statistic title="今日收入" value={analytics.revenue_today} prefix="¥" precision={2} />
    </Col>
    <Col span={8}>
      <Statistic title="最后验证" value={formatTimeAgo(analytics.last_verified_at)} />
    </Col>
  </Row>
</Card>
```

**数据加载**: 调用 `GET /api/h5/sites/{site_id}/analytics`

---

### SITE-FE-003：批量操作（P0）

- **估计耗时**: 45 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

1. 增加 Checkbox 选择框
2. 底部批量操作栏

```tsx
// 表格增加选择列
columns.unshift({
  title: <Checkbox checked={allSelected} onChange={toggleSelectAll} />,
  render: (_, record) => (
    <Checkbox
      checked={selectedSiteIds.includes(record.id)}
      onChange={() => toggleSelectSite(record.id)}
    />
  ),
});

// 底部批量操作栏
{selectedSiteIds.length > 0 && (
  <div style={{ position: "fixed", bottom: 0, left: 0, right: 0, background: "#fff", padding: 16, borderTop: "1px solid #f0f0f0", zIndex: 100 }}>
    <Space>
      <Typography.Text>已选择 {selectedSiteIds.length} 个站点</Typography.Text>
      <Button onClick={() => handleBatchAction("pause")}>批量暂停</Button>
      <Button onClick={() => handleBatchAction("resume")}>批量恢复</Button>
      <Button danger onClick={() => handleBatchAction("delete")}>批量删除</Button>
      <Button onClick={() => setBatchConfigModalOpen(true)}>批量更新配置</Button>
    </Space>
  </div>
)}
```

---

### SITE-FE-004：最后验证时间 + 自动刷新（P0）

- **估计耗时**: 30 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

1. 显示最后验证时间（已在 SITE-FE-001 中完成）
2. 增加"立即验证"按钮
3. 增加"设置自动验证"选项

```tsx
// 在站点卡片中增加
<Space>
  <Button size="small" onClick={() => handleVerify(site)}>
    立即验证
  </Button>
  <Dropdown menu={{
    items: [
      { key: "30min", label: "每 30 分钟", onClick: () => setAutoVerify(site.id, 30) },
      { key: "1hour", label: "每 1 小时", onClick: () => setAutoVerify(site.id, 60) },
      { key: "off", label: "关闭自动验证", onClick: () => setAutoVerify(site.id, 0) },
    ]
  }}>
    <Button size="small">自动验证 ▾</Button>
  </Dropdown>
</Space>
```

---

### SITE-FE-005：站点克隆（P1）

- **估计耗时**: 45 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

在站点操作菜单中增加"克隆站点"选项，点击后弹出 Modal：

```tsx
<Modal title="克隆站点" open={cloneModalOpen} onCancel={() => setCloneModalOpen(false)}>
  <Form form={cloneForm} layout="vertical">
    <Form.Item label="源站点">
      <Input value={cloneSource?.brand_name} disabled />
    </Form.Item>
    <Form.Item label="新站点 Key" name="new_site_key" rules={[{ required: true }]}>
      <Input placeholder="wechat-02" />
    </Form.Item>
    <Form.Item label="新品牌名称" name="new_brand_name" rules={[{ required: true }]}>
      <Input placeholder="我的站点 2" />
    </Form.Item>
    <Form.Item label="新域名" name="new_domain" rules={[{ required: true }]}>
      <Input placeholder="h5-wechat-02.example.com" />
    </Form.Item>
    <Form.Item label="克隆选项">
      <Space direction="vertical">
        <Checkbox checked={cloneBrand} onChange={(e) => setCloneBrand(e.target.checked)}>
          克隆品牌配置
        </Checkbox>
        <Checkbox checked={cloneDeploy} onChange={(e) => setCloneDeploy(e.target.checked)}>
          克隆部署配置
        </Checkbox>
        <Checkbox checked={cloneTranslations} onChange={(e) => setCloneTranslations(e.target.checked)}>
          克隆翻译（仅结构，不含翻译文本）
        </Checkbox>
        <Checkbox checked={clonePermissions} onChange={(e) => setClonePermissions(e.target.checked)}>
          克隆权限
        </Checkbox>
      </Space>
    </Form.Item>
  </Form>
</Modal>
```

---

### SITE-FE-006：配置导入导出（P1）

- **估计耗时**: 45 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

1. 站点操作菜单增加"导出配置"
2. 顶部工具栏增加"导入配置"按钮

```tsx
// 导出
const handleExportConfig = async (site: PlatformSite) => {
  const response = await fetch(`/api/h5/sites/${site.id}/export-config`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${site.site_key}-config.json`;
  a.click();
};

// 导入
<Modal title="导入站点配置" open={importModalOpen}>
  <Upload.Dragger
    accept=".json"
    beforeUpload={(file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const config = JSON.parse(e.target.result);
        setImportConfig(config);
      };
      reader.readAsText(file);
      return false;
    }}
  >
    <p>点击或拖拽 JSON 配置文件到此区域</p>
  </Upload.Dragger>
  {importConfig && (
    <div>
      <Typography.Text>预览：</Typography.Text>
      <pre>{JSON.stringify(importConfig, null, 2)}</pre>
    </div>
  )}
</Modal>
```

---

### SITE-FE-007：站点对比（P1）

- **估计耗时**: 45 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

顶部工具栏增加"站点对比"按钮，点击后弹出 Modal：

```tsx
<Modal title="站点对比" open={compareModalOpen} width={800}>
  <Space style={{ marginBottom: 16 }}>
    <Select
      mode="multiple"
      placeholder="选择 2-3 个站点对比"
      style={{ width: 400 }}
      value={compareSites}
      onChange={setCompareSites}
      options={sites.map(s => ({ label: s.brand_name, value: s.id }))}
    />
  </Space>
  {compareSites.length >= 2 && (
    <Table
      dataSource={compareData}
      columns={[
        { title: "指标", dataIndex: "metric" },
        ...compareSites.map(siteId => ({
          title: sites.find(s => s.id === siteId)?.brand_name,
          dataIndex: siteId,
        })),
      ]}
    />
  )}
</Modal>
```

**对比指标**:
- 用户数
- 今日活跃
- 任务完成率
- 收入
- 部署版本

---

### SITE-FE-008：域名管理增强（P1）

- **估计耗时**: 30 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

在站点卡片中增加域名验证状态：

```tsx
<Space direction="vertical" size={4}>
  <Typography.Text>域名: {site.domain}</Typography.Text>
  <Space>
    <Tag color={dnsValid ? "success" : "error"}>
      DNS: {dnsValid ? "✓" : "✗"} {dnsRecord}
    </Tag>
    <Tag color={sslValid ? "success" : "error"}>
      SSL: {sslValid ? "✓" : "✗"} {sslDaysRemaining}天
    </Tag>
    <Button size="small" onClick={() => handleVerifyDns(site)}>
      验证
    </Button>
  </Space>
</Space>
```

---

### SITE-FE-009：部署流水线可视化（P1）

- **估计耗时**: 45 分钟

#### 修改文件

`frontend/src/pages/SitesPage.tsx`

#### 修改内容

在站点操作菜单中增加"部署历史"，点击后弹出 Drawer：

```tsx
<Drawer title="部署历史" open={deployHistoryOpen} width={640}>
  <Timeline>
    {deployHistory.map(item => (
      <Timeline.Item
        color={item.status === "success" ? "green" : "red"}
      >
        <Space direction="vertical" size={4}>
          <Space>
            <Tag color={item.status === "success" ? "success" : "error"}>
              {item.action}
            </Tag>
            <Typography.Text type="secondary">
              {formatTimeAgo(item.created_at)}
            </Typography.Text>
          </Space>
          <Typography.Text>{item.details}</Typography.Text>
          <Typography.Text type="secondary">
            操作人: {item.created_by}
          </Typography.Text>
        </Space>
      </Timeline.Item>
    ))}
  </Timeline>
</Drawer>
```

---

## 四、任务清单

| # | 任务 | 类型 | 工作量 | 依赖 |
|---|------|------|--------|------|
| SITE-BE-001 | 站点分析 API | 后端 | 60 分钟 | - |
| SITE-BE-002 | 站点克隆 API | 后端 | 45 分钟 | - |
| SITE-BE-003 | 配置导入导出 API | 后端 | 30 分钟 | - |
| SITE-BE-004 | 批量操作 API | 后端 | 30 分钟 | - |
| SITE-BE-005 | 域名验证 API | 后端 | 30 分钟 | - |
| SITE-BE-006 | 部署历史 API | 后端 | 30 分钟 | - |
| SITE-FE-001 | 健康状态指示器 | 前端 | 30 分钟 | SITE-BE-001 |
| SITE-FE-002 | 数据统计卡片 | 前端 | 45 分钟 | SITE-BE-001 |
| SITE-FE-003 | 批量操作 | 前端 | 45 分钟 | SITE-BE-004 |
| SITE-FE-004 | 最后验证时间 | 前端 | 30 分钟 | SITE-BE-001 |
| SITE-FE-005 | 站点克隆 | 前端 | 45 分钟 | SITE-BE-002 |
| SITE-FE-006 | 配置导入导出 | 前端 | 45 分钟 | SITE-BE-003 |
| SITE-FE-007 | 站点对比 | 前端 | 45 分钟 | SITE-BE-001 |
| SITE-FE-008 | 域名管理增强 | 前端 | 30 分钟 | SITE-BE-005 |
| SITE-FE-009 | 部署流水线可视化 | 前端 | 45 分钟 | SITE-BE-006 |

**总计**: 15 个任务（6 后端 + 9 前端），预计 8.5 小时

---

## 五、执行顺序

```
Day 1 (后端):
  SITE-BE-001 站点分析 API
  SITE-BE-004 批量操作 API
  SITE-BE-002 站点克隆 API
  SITE-BE-003 配置导入导出 API
  SITE-BE-005 域名验证 API
  SITE-BE-006 部署历史 API

Day 2 (前端):
  SITE-FE-001 健康状态指示器
  SITE-FE-002 数据统计卡片
  SITE-FE-003 批量操作
  SITE-FE-004 最后验证时间
  SITE-FE-005 站点克隆
  SITE-FE-006 配置导入导出
  SITE-FE-007 站点对比
  SITE-FE-008 域名管理增强
  SITE-FE-009 部署流水线可视化
```

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（站点增强轮）。请读取 docs/task-plan-site-enhance.md，一次性实现 SITE-BE-001 ~ SITE-BE-006 全部 6 个后端任务，不要中途暂停。

核心任务：
1. SITE-BE-001 站点分析 API（GET /api/h5/sites/{id}/analytics）
2. SITE-BE-002 站点克隆 API（POST /api/h5/sites/{id}/clone）
3. SITE-BE-003 配置导入导出 API（GET export + POST import）
4. SITE-BE-004 批量操作 API（POST /api/h5/sites/batch-update）
5. SITE-BE-005 域名验证 API（POST /api/h5/sites/{id}/verify-dns）
6. SITE-BE-006 部署历史 API（deploy_history 表 + CRUD）

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（站点增强轮）。请读取 docs/task-plan-site-enhance.md，一次性实现 SITE-FE-001 ~ SITE-FE-009 全部 9 个前端任务，不要中途暂停。

核心任务：
1. SITE-FE-001 健康状态指示器（🟢🟡🔴⚪ + 最后验证时间）
2. SITE-FE-002 数据统计卡片（Card Grid + Statistic）
3. SITE-FE-003 批量操作（Checkbox + 底部操作栏）
4. SITE-FE-004 最后验证时间（立即验证 + 自动验证设置）
5. SITE-FE-005 站点克隆（Modal + 克隆选项）
6. SITE-FE-006 配置导入导出（导出下载 + 导入上传）
7. SITE-FE-007 站点对比（多站点选择 + 对比表格）
8. SITE-FE-008 域名管理增强（DNS + SSL 验证状态）
9. SITE-FE-009 部署流水线可视化（Timeline 历史）

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
