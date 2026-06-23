# V2.0 迭代功能完整方案（ITER-V2）

> **执行角色**: api_agent（后端）+ frontend_agent（前端）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-19
> **总架构师签发**
> **目标**: 一次性交付 8 大迭代功能

---

## 一、功能总览

| # | 功能 | 后端 | 前端 | 预估行数 |
|---|------|------|------|---------|
| 1 | 数据库备份/恢复 | ✅ | ✅ | ~400 行 |
| 2 | 批量操作增强 | ✅ | ✅ | ~500 行 |
| 3 | 知识库管理 | ✅ | ✅ | ~600 行 |
| 4 | 客户画像增强 | ✅ | ✅ | ~400 行 |
| 5 | 消息模板变量预览 | ✅ | ✅ | ~200 行 |
| 6 | API 调用统计 | ✅ | ✅ | ~350 行 |
| 7 | API 调用频率设置 | ✅ | ✅ | ~300 行 |
| 8 | 系统健康检查 + 邮件系统 | ✅ | ✅ | ~500 行 |
| | **总计** | | | **~3,250 行** |

---

## 二、IV-BE 后端任务

### IV-BE-001：数据库备份/恢复

**新增表**: `db_backups`

```sql
CREATE TABLE db_backups (
  id VARCHAR(36) PRIMARY KEY,
  filename VARCHAR(200) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size BIGINT,
  backup_type VARCHAR(20),     -- manual/auto_daily/auto_weekly
  status VARCHAR(20),          -- running/completed/failed
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT,
  created_by VARCHAR(36)
);
```

**新增服务**: `app/services/backup_service.py`

```python
class BackupService:
    BACKUP_DIR = "/opt/whatsapp/backups"
    MAX_BACKUPS = 7  # 保留最近 7 个

    async def create_backup(self, user_id: str, backup_type: str = "manual"):
        """pg_dump 备份数据库"""
        filename = f"backup_{datetime.now():%Y%m%d_%H%M%S}.sql.gz"
        filepath = os.path.join(self.BACKUP_DIR, filename)
        # 执行 pg_dump | gzip > filepath
        # 清理超过 7 个的旧备份

    async def restore_backup(self, backup_id: str):
        """从备份恢复数据库"""
        backup = session.get(DbBackup, backup_id)
        # gunzip + psql < filepath

    def list_backups(self) -> list[DbBackup]:
        """列出所有备份"""

    async def schedule_auto_backup(self):
        """定时自动备份（worker 调用）"""
        # 每天 3:00 自动备份
        # 每周日 3:00 全量备份
```

**API 端点**:

```
POST   /api/backups                    创建备份（手动）
GET    /api/backups                    列出备份
POST   /api/backups/{id}/restore       恢复备份
DELETE /api/backups/{id}               删除备份
GET    /api/backups/{id}/download      下载备份文件
```

### IV-BE-002：批量操作增强

**新增服务**: `app/services/batch_service.py`

```python
class BatchService:
    def batch_update_tags(self, entity_type: str, entity_ids: list[str],
                          add_tags: list[str], remove_tags: list[str]):
        """批量修改标签（客户/会话/工单）"""

    def batch_assign_conversations(self, conversation_ids: list[str],
                                    agent_id: str):
        """批量分配会话给客服"""

    def batch_send_template(self, entity_type: str, entity_ids: list[str],
                            template_id: str, variables: dict):
        """批量发送模板消息"""

    def batch_import_products(self, csv_data: str, account_id: str):
        """批量导入商品（CSV）"""
```

**API 端点**:

```
POST /api/batch/tags                    批量修改标签
POST /api/batch/assign-conversations    批量分配会话
POST /api/batch/send-template          批量发送模板
POST /api/batch/import-products         批量导入商品
```

### IV-BE-003：知识库管理

**新增表**: `knowledge_categories` + `knowledge_articles`

```sql
CREATE TABLE knowledge_categories (
  id VARCHAR(36) PRIMARY KEY,
  agency_id VARCHAR(36),        -- NULL = 全局
  name VARCHAR(200) NOT NULL,
  description TEXT,
  sort_order INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE knowledge_articles (
  id VARCHAR(36) PRIMARY KEY,
  category_id VARCHAR(36) REFERENCES knowledge_categories(id),
  agency_id VARCHAR(36),        -- NULL = 全局
  title VARCHAR(500) NOT NULL,
  content TEXT NOT NULL,         -- 纯文本
  keywords TEXT,                 -- 关键词（逗号分隔）
  is_published BOOLEAN DEFAULT TRUE,
  view_count INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

**新增服务**: `app/services/knowledge_base_service.py`

```python
class KnowledgeBaseService:
    def search(self, query: str, agency_id: str | None = None) -> list:
        """语义检索 + 关键词匹配"""
        # 1. 关键词匹配：title/content/keywords LIKE query
        # 2. 语义检索：调用 AI provider 做相关性评分
        # 3. 合并排序返回

    def get_ai_answer(self, question: str, agency_id: str | None) -> str | None:
        """AI 从知识库检索回答"""
        articles = self.search(question, agency_id)
        if articles:
            # 将 top 3 文章作为上下文交给 AI 生成回答
            context = "\n".join([a.content for a in articles[:3]])
            return ai_provider.generate(f"根据以下知识库回答用户问题:\n{context}\n问题: {question}")
        return None
```

**API 端点**:

```
GET    /api/knowledge/categories           分类列表
POST   /api/knowledge/categories           创建分类
PATCH  /api/knowledge/categories/{id}      编辑分类
DELETE /api/knowledge/categories/{id}      删除分类
GET    /api/knowledge/articles             文章列表（支持搜索）
POST   /api/knowledge/articles             创建文章
PATCH  /api/knowledge/articles/{id}        编辑文章
DELETE /api/knowledge/articles/{id}        删除文章
GET    /api/knowledge/search?q=xxx         搜索文章
POST   /api/knowledge/ai-answer            AI 回答（测试用）
```

### IV-BE-004：客户画像增强

**新增表**: `customer_auto_tag_rules`

```sql
CREATE TABLE customer_auto_tag_rules (
  id VARCHAR(36) PRIMARY KEY,
  agency_id VARCHAR(36),
  name VARCHAR(200) NOT NULL,
  condition_type VARCHAR(50),   -- recharge_total/sign_in_count/conversation_count
  condition_operator VARCHAR(10), -- gt/lt/eq/gte/lte
  condition_value DECIMAL,
  tag_name VARCHAR(100) NOT NULL,
  is_enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**新增服务**: `app/services/customer_profile_service.py`

```python
class CustomerProfileService:
    def get_profile(self, user_id: str) -> dict:
        """客户画像数据"""
        return {
            "behavior": {
                "sign_in_count": ...,       # 签到次数
                "sign_in_streak": ...,      # 连续签到天数
                "recharge_total": ...,      # 累计充值
                "recharge_count": ...,      # 充值次数
                "withdraw_total": ...,      # 累计提现
                "conversation_count": ...,  # 会话次数
                "last_active_at": ...,
            },
            "auto_tags": [...],  # 自动标签
            "manual_tags": [...], # 手动标签
        }

    def evaluate_auto_tags(self, user_id: str):
        """评估自动打标规则"""
        # 查询所有启用的规则
        # 根据用户行为数据匹配规则
        # 自动添加/移除标签
```

**API 端点**:

```
GET    /api/customers/{id}/profile              客户画像
GET    /api/auto-tag-rules                       规则列表
POST   /api/auto-tag-rules                      创建规则
PATCH  /api/auto-tag-rules/{id}                  编辑规则
DELETE /api/auto-tag-rules/{id}                  删除规则
POST   /api/auto-tag-rules/{id}/evaluate         立即评估（测试用）
```

### IV-BE-005：消息模板变量预览

**新增服务**: `app/services/template_preview_service.py`

```python
SYSTEM_VARIABLES = {
    "{{customer_name}}": "客户姓名",
    "{{customer_phone}}": "客户手机号",
    "{{recharge_total}}": "累计充值金额",
    "{{withdraw_total}}": "累计提现金额",
    "{{brand_name}}": "品牌名称",
    "{{current_date}}": "当前日期",
}

class TemplatePreviewService:
    def get_variables(self) -> dict:
        """返回系统变量 + 自定义变量列表"""

    def preview(self, template_content: str, variables: dict) -> str:
        """替换变量生成预览文本"""
        result = template_content
        for key, value in variables.items():
            result = result.replace(key, str(value))
        return result

    def preview_with_mock(self, template_content: str) -> str:
        """使用 mock 数据预览"""
        mock_data = {
            "{{customer_name}}": "张三",
            "{{customer_phone}}": "138****8888",
            "{{recharge_total}}": "¥1,234.56",
            "{{withdraw_total}}": "¥500.00",
            "{{brand_name}}": "示例品牌",
            "{{current_date}}": "2026-06-19",
        }
        return self.preview(template_content, mock_data)
```

**API 端点**:

```
GET  /api/templates/variables              变量列表
POST /api/templates/preview                预览（body: content + variables）
POST /api/templates/preview-mock           mock 预览
```

### IV-BE-006：API 调用统计

**中间件**: `app/core/api_stats_middleware.py`

```python
class ApiStatsMiddleware:
    """记录每个请求到 Redis"""
    async def __call__(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start

        # Redis key 格式
        # api_stats:{agency_id}:{endpoint}:{date}:count
        # api_stats:{agency_id}:{endpoint}:{date}:total_ms
        agency_id = get_agency_id_from_request(request)
        endpoint = request.url.path
        date = datetime.now().strftime("%Y-%m-%d")

        redis.incr(f"api_stats:{agency_id}:{endpoint}:{date}:count")
        redis.incrby(f"api_stats:{agency_id}:{endpoint}:{date}:total_ms", int(elapsed * 1000))
```

**API 端点**:

```
GET /api/api-stats/summary                    汇总统计
GET /api/api-stats/by-agency/{id}             按代理商统计
GET /api/api-stats/by-endpoint                按端点统计
GET /api/api-stats/timeline?days=7            时间线统计
```

### IV-BE-007：API 调用频率设置

**新增表**: `api_rate_limits`

```sql
CREATE TABLE api_rate_limits (
  id VARCHAR(36) PRIMARY KEY,
  agency_id VARCHAR(36),        -- NULL = 全局
  endpoint_pattern VARCHAR(200), -- /api/* 或具体路径
  max_requests INT NOT NULL,    -- 最大请求数
  window_seconds INT NOT NULL,  -- 时间窗口（秒）
  ban_minutes INT DEFAULT 30,   -- 封禁时长（分钟）
  is_enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);
```

**中间件**: `app/core/rate_limit_middleware.py`

```python
class RateLimitMiddleware:
    async def __call__(self, request, call_next):
        agency_id = get_agency_id(request)
        ip = request.client.host
        endpoint = request.url.path

        # 1. 检查 IP 是否被封禁
        if redis.exists(f"banned:{ip}"):
            raise HTTPException(429, "IP 已被封禁")

        # 2. 检查频率限制
        rules = get_rate_rules(agency_id, endpoint)
        for rule in rules:
            key = f"rate:{agency_id}:{rule.endpoint_pattern}:{int(time.time() / rule.window_seconds)}"
            count = redis.incr(key)
            if count == 1:
                redis.expire(key, rule.window_seconds)
            if count > rule.max_requests:
                # 封禁 IP
                redis.setex(f"banned:{ip}", rule.ban_minutes * 60, "1")
                raise HTTPException(429, f"请求过于频繁，IP 已封禁 {rule.ban_minutes} 分钟")

        return await call_next(request)
```

**API 端点**:

```
GET    /api/rate-limits                    规则列表
POST   /api/rate-limits                    创建规则
PATCH  /api/rate-limits/{id}               编辑规则
DELETE /api/rate-limits/{id}               删除规则
GET    /api/rate-limits/banned-ips         被封禁的 IP 列表
DELETE /api/rate-limits/banned-ips/{ip}    解除封禁
```

### IV-BE-008：系统健康检查 + 邮件系统

**新增表**: `email_config` + `health_checks`

```sql
CREATE TABLE email_config (
  id VARCHAR(36) PRIMARY KEY,
  smtp_host VARCHAR(200) NOT NULL,
  smtp_port INT NOT NULL DEFAULT 465,
  smtp_user VARCHAR(200) NOT NULL,
  smtp_password VARCHAR(500) NOT NULL,  -- 加密存储
  smtp_ssl BOOLEAN DEFAULT TRUE,
  from_name VARCHAR(100),
  from_email VARCHAR(200),
  is_enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE health_checks (
  id VARCHAR(36) PRIMARY KEY,
  check_type VARCHAR(50),       -- db/redis/api/site/ssl
  target VARCHAR(200),          -- 检查目标
  status VARCHAR(20),           -- healthy/warning/error
  response_time_ms INT,
  details TEXT,
  checked_at TIMESTAMP DEFAULT NOW()
);
```

**邮件服务**: `app/services/email_service.py`

```python
class EmailService:
    async def send_email(self, to: str, subject: str, body: str):
        """发送邮件"""
        config = session.scalar(select(EmailConfig).where(EmailConfig.is_enabled == True))
        if not config:
            raise ValueError("邮件服务未配置")
        # 使用 smtplib 发送

    async def send_health_alert(self, check: HealthCheck):
        """发送健康告警邮件"""
        subject = f"[系统告警] {check.check_type} 异常: {check.target}"
        body = f"检查类型: {check.check_type}\n目标: {check.target}\n状态: {check.status}\n详情: {check.details}\n时间: {check.checked_at}"
        await self.send_email(config.alert_email, subject, body)
```

**健康检查服务**: `app/services/health_check_service.py`

```python
class HealthCheckService:
    async def check_all(self) -> list[HealthCheck]:
        """执行全部检查"""
        results = []
        results.append(await self._check_db())
        results.append(await self._check_redis())
        results.append(await self._check_api())
        results.extend(await self._check_sites())
        results.extend(await self._check_ssl())

        # 异常时发送通知
        for r in results:
            if r.status == "error":
                await self._send_alert(r)
        return results

    async def _check_db(self):
        start = time.time()
        try:
            session.execute(text("SELECT 1"))
            return HealthCheck(check_type="db", target="PostgreSQL",
                             status="healthy", response_time_ms=int((time.time()-start)*1000))
        except Exception as e:
            return HealthCheck(check_type="db", target="PostgreSQL",
                             status="error", details=str(e))

    async def _check_redis(self): ...
    async def _check_api(self): ...
    async def _check_sites(self): ...  # 检查所有 H5 站点可达性
    async def _check_ssl(self): ...    # 检查 SSL 证书到期时间
```

**API 端点**:

```
# 邮件配置
GET    /api/email-config                    获取配置
PUT    /api/email-config                    更新配置
POST   /api/email-config/test              发送测试邮件

# 健康检查
GET    /api/health-checks                   最近检查结果
POST   /api/health-checks/run              手动执行检查
GET    /api/health-checks/summary           汇总（Dashboard 用）
```

---

## 三、IV-FE 前端任务

### IV-FE-001：数据库备份/恢复页面

**新增**: 超管后台 `/system/backups` 页面

```tsx
<PageShell title="数据库备份" subtitle="管理和恢复数据库备份">
  <Row justify="space-between">
    <Space>
      <Button type="primary" onClick={handleBackup}>立即备份</Button>
      <Select value={autoSchedule} onChange={setAutoSchedule}
        options={[{label:"每天",value:"daily"},{label:"每周",value:"weekly"},{label:"关闭",value:"off"}]} />
    </Space>
  </Row>
  <Table dataSource={backups} columns={[
    { title: "文件名", dataIndex: "filename" },
    { title: "大小", dataIndex: "file_size", render: formatBytes },
    { title: "类型", dataIndex: "backup_type", render: (t) => <Tag>{t}</Tag> },
    { title: "状态", dataIndex: "status" },
    { title: "时间", dataIndex: "completed_at" },
    { title: "操作", render: (_, r) => (
      <Space>
        <Button onClick={() => handleRestore(r)}>恢复</Button>
        <Button onClick={() => handleDownload(r)}>下载</Button>
        <DangerButton onConfirm={() => handleDelete(r)}>删除</DangerButton>
      </Space>
    )}
  ]} />
</PageShell>
```

### IV-FE-002：批量操作增强

**修改**: ChatPage / CustomersPage / TicketsPage / TemplatePage

```tsx
// 通用批量操作栏（选中后显示在底部）
{selectedIds.length > 0 && (
  <BatchActionBar
    count={selectedIds.length}
    actions={[
      { label: "修改标签", icon: <TagOutlined />, onClick: handleBatchTags },
      { label: "分配客服", icon: <UserOutlined />, onClick: handleBatchAssign, show: page === "conversations" },
      { label: "发送模板", icon: <SendOutlined />, onClick: handleBatchTemplate },
    ]}
  />
)}

// 批量标签 Modal
<Modal title="批量修改标签">
  <Form>
    <Form.Item label="添加标签"><Select mode="tags" /></Form.Item>
    <Form.Item label="移除标签"><Select mode="tags" /></Form.Item>
  </Form>
</Modal>

// 批量导入商品（EcommercePage 增加）
<Upload accept=".csv" beforeUpload={handleImportCSV}>
  <Button icon={<UploadOutlined />}>批量导入商品</Button>
</Upload>
```

### IV-FE-003：知识库管理页面

**新增**: `frontend/src/pages/KnowledgeBasePage.tsx`

```tsx
<PageShell title="知识库管理">
  <Row gutter={16}>
    {/* 左侧：分类列表 */}
    <Col span={6}>
      <Card title="分类" extra={<Button icon={<PlusOutlined />} onClick={handleAddCategory}>新增</Button>}>
        <Menu items={categories.map(c => ({ key: c.id, label: c.name }))}
              selectedKeys={[selectedCategory]} onClick={handleSelectCategory} />
      </Card>
    </Col>
    {/* 右侧：文章列表 */}
    <Col span={18}>
      <Card title={selectedCategoryName} extra={
        <Space>
          <Input.Search placeholder="搜索文章" onSearch={handleSearch} />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAddArticle}>新增文章</Button>
        </Space>
      }>
        <Table dataSource={articles} columns={[
          { title: "标题", dataIndex: "title" },
          { title: "关键词", dataIndex: "keywords" },
          { title: "浏览量", dataIndex: "view_count" },
          { title: "操作", render: (_, r) => (
            <Space>
              <Button onClick={() => handleEdit(r)}>编辑</Button>
              <DangerButton onConfirm={() => handleDelete(r)}>删除</DangerButton>
            </Space>
          )}
        ]} />
      </Card>
    </Col>
  </Row>

  {/* 文章编辑 Modal */}
  <Drawer title="编辑文章" width={640}>
    <Form>
      <Form.Item label="标题" name="title" rules={[{ required: true }]}><Input /></Form.Item>
      <Form.Item label="分类" name="category_id"><Select options={categories} /></Form.Item>
      <Form.Item label="关键词" name="keywords"><Input placeholder="逗号分隔" /></Form.Item>
      <Form.Item label="内容" name="content" rules={[{ required: true }]}>
        <Input.TextArea rows={15} />
      </Form.Item>
    </Form>
  </Drawer>
</PageShell>
```

### IV-FE-004：客户画像增强

**修改**: `frontend/src/pages/CustomerDetailDrawer.tsx`

```tsx
// 新增 Tab: "客户画像"
<Tabs.TabPane tab="客户画像" key="profile">
  {/* 行为数据卡片 */}
  <Row gutter={16}>
    <Col span={8}>
      <Statistic title="签到次数" value={profile.behavior.sign_in_count} />
      <Statistic title="连续签到" value={profile.behavior.sign_in_streak} suffix="天" />
    </Col>
    <Col span={8}>
      <Statistic title="累计充值" value={profile.behavior.recharge_total} prefix="¥" />
      <Statistic title="充值次数" value={profile.behavior.recharge_count} />
    </Col>
    <Col span={8}>
      <Statistic title="会话次数" value={profile.behavior.conversation_count} />
      <Statistic title="最后活跃" value={formatTimeAgo(profile.behavior.last_active_at)} />
    </Col>
  </Row>

  {/* 标签区域 */}
  <Divider>标签</Divider>
  <Space wrap>
    {profile.auto_tags.map(t => <Tag color="blue">{t} (自动)</Tag>)}
    {profile.manual_tags.map(t => <Tag>{t}</Tag>)}
  </Space>
</Tabs.TabPane>
```

**新增**: 自动打标规则页面（SettingsPage Tab）

```tsx
// 自动打标规则管理
<Table dataSource={rules} columns={[
  { title: "规则名称" },
  { title: "条件", render: (_, r) => `${r.condition_type} ${r.condition_operator} ${r.condition_value}` },
  { title: "标签", dataIndex: "tag_name" },
  { title: "状态", render: (_, r) => <Switch checked={r.is_enabled} /> },
]} />
```

### IV-FE-005：消息模板变量预览

**修改**: `frontend/src/pages/TemplatePage.tsx`

```tsx
// 编辑模板时，在内容输入框下方增加实时预览
<Form.Item label="模板内容" name="content">
  <Input.TextArea rows={8} onChange={handleContentChange} />
</Form.Item>

{/* 变量插入工具栏 */}
<Space style={{ marginBottom: 8 }}>
  <Typography.Text type="secondary">插入变量：</Typography.Text>
  {variables.map(v => (
    <Button size="small" onClick={() => insertVariable(v.code)}>{v.label}</Button>
  ))}
</Space>

{/* 实时预览 */}
<Card title="预览" size="small" style={{ marginBottom: 16 }}>
  <Typography.Paragraph>{previewText}</Typography.Paragraph>
</Card>
```

### IV-FE-006：API 调用统计页面

**新增**: 超管后台 `/system/api-stats` 页面

```tsx
<PageShell title="API 调用统计">
  {/* 汇总卡片 */}
  <Row gutter={16} style={{ marginBottom: 16 }}>
    <Col span={6}><Statistic title="今日总调用" value={summary.today_count} /></Col>
    <Col span={6}><Statistic title="平均响应时间" value={summary.avg_ms} suffix="ms" /></Col>
    <Col span={6}><Statistic title="活跃代理商" value={summary.active_agencies} /></Col>
    <Col span={6}><Statistic title="被限流次数" value={summary.rate_limited} /></Col>
  </Row>

  {/* 按代理商统计 */}
  <Table dataSource={byAgency} columns={[
    { title: "代理商", dataIndex: "agency_name" },
    { title: "调用次数", dataIndex: "count" },
    { title: "平均响应", dataIndex: "avg_ms", suffix: "ms" },
    { title: "峰值", dataIndex: "peak_count" },
  ]} />

  {/* 按端点统计 */}
  <Table dataSource={byEndpoint} columns={[
    { title: "端点", dataIndex: "endpoint" },
    { title: "调用次数", dataIndex: "count" },
    { title: "平均响应", dataIndex: "avg_ms" },
  ]} />

  {/* 时间线图 */}
  {/* 折线图：过去 7 天每日调用量 */}
</PageShell>
```

代理商后台也增加简化版：只看自己的统计数据。

### IV-FE-007：API 频率设置页面

**新增**: 超管后台 `/system/rate-limits` 页面

```tsx
<PageShell title="API 频率限制" subtitle="配置 API 调用频率限制和 IP 封禁规则">
  <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增规则</Button>

  <Table dataSource={rules} columns={[
    { title: "代理商", dataIndex: "agency_name", render: (v) => v || "全局" },
    { title: "端点", dataIndex: "endpoint_pattern" },
    { title: "限制", render: (_, r) => `${r.max_requests} 次 / ${r.window_seconds}秒` },
    { title: "封禁时长", render: (_, r) => `${r.ban_minutes} 分钟` },
    { title: "状态", render: (_, r) => <Switch checked={r.is_enabled} /> },
    { title: "操作", render: (_, r) => (
      <Space>
        <Button onClick={() => handleEdit(r)}>编辑</Button>
        <DangerButton onConfirm={() => handleDelete(r)}>删除</DangerButton>
      </Space>
    )}
  ]} />

  {/* 被封禁 IP 列表 */}
  <Divider>被封禁 IP</Divider>
  <Table dataSource={bannedIps} columns={[
    { title: "IP 地址", dataIndex: "ip" },
    { title: "封禁时间", dataIndex: "banned_at" },
    { title: "剩余时间", dataIndex: "remaining_minutes" },
    { title: "操作", render: (_, r) => <Button onClick={() => handleUnban(r.ip)}>解封</Button> }
  ]} />
</PageShell>
```

### IV-FE-008：系统健康检查 + 邮件配置

**修改**: DashboardPage 增加健康检查卡片

```tsx
{/* 系统健康检查卡片 */}
<Card title="系统健康" extra={
  <Space>
    <Tag color="green">上次检查: {lastCheckTime}</Tag>
    <Button size="small" onClick={handleRunCheck}>立即检查</Button>
  </Space>
}>
  <Row gutter={16}>
    <Col span={4}>
      <Badge status={health.db === "healthy" ? "success" : "error"} />
      <Typography.Text>数据库</Typography.Text>
    </Col>
    <Col span={4}>
      <Badge status={health.redis === "healthy" ? "success" : "error"} />
      <Typography.Text>Redis</Typography.Text>
    </Col>
    <Col span={4}>
      <Badge status={health.api === "healthy" ? "success" : "error"} />
      <Typography.Text>API 服务</Typography.Text>
    </Col>
    <Col span={4}>
      <Badge status={health.sites === "healthy" ? "success" : "error"} />
      <Typography.Text>H5 站点</Typography.Text>
    </Col>
    <Col span={4}>
      <Badge status={health.ssl === "healthy" ? "success" : "error"} />
      <Typography.Text>SSL 证书</Typography.Text>
    </Col>
  </Row>
</Card>
```

**新增**: SettingsPage 增加"邮件配置" Tab

```tsx
<Tabs.TabPane tab="邮件配置" key="email">
  <Form>
    <Form.Item label="SMTP 服务器" name="smtp_host"><Input placeholder="smtp.qq.com" /></Form.Item>
    <Form.Item label="端口" name="smtp_port"><InputNumber placeholder="465" /></Form.Item>
    <Form.Item label="用户名" name="smtp_user"><Input placeholder="your@qq.com" /></Form.Item>
    <Form.Item label="密码/授权码" name="smtp_password"><Input.Password /></Form.Item>
    <Form.Item label="SSL" name="smtp_ssl" valuePropName="checked"><Switch /></Form.Item>
    <Form.Item label="发件人名称" name="from_name"><Input /></Form.Item>
    <Form.Item label="发件人邮箱" name="from_email"><Input /></Form.Item>
    <Form.Item>
      <Space>
        <Button type="primary" htmlType="submit">保存</Button>
        <Button onClick={handleTestEmail}>发送测试邮件</Button>
      </Space>
    </Form.Item>
  </Form>
</Tabs.TabPane>
```

---

## 四、新增权限码（16 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `backups.view` | 查看备份 | ❌ |
| `backups.create` | 创建备份 | ❌ |
| `backups.restore` | 恢复备份 | ❌ |
| `batch.tags` | 批量修改标签 | ✅ |
| `batch.assign` | 批量分配会话 | ✅ |
| `batch.send_template` | 批量发送模板 | ✅ |
| `batch.import` | 批量导入商品 | ❌ |
| `knowledge.view` | 查看知识库 | ✅ |
| `knowledge.manage` | 管理知识库 | ✅ |
| `knowledge.ai_test` | AI 回答测试 | ✅ |
| `customer_profile.view` | 查看客户画像 | ✅ |
| `auto_tag.manage` | 管理打标规则 | ❌ |
| `api_stats.view` | 查看 API 统计 | ✅ |
| `rate_limits.manage` | 管理频率限制 | ❌ |
| `email_config.manage` | 管理邮件配置 | ❌ |
| `health_check.view` | 查看健康检查 | ✅ |

---

## 五、任务清单

| # | 任务 | 类型 |
|---|------|------|
| IV-BE-001 | 数据库备份/恢复 | 后端 |
| IV-BE-002 | 批量操作增强 | 后端 |
| IV-BE-003 | 知识库管理 | 后端 |
| IV-BE-004 | 客户画像增强 | 后端 |
| IV-BE-005 | 模板变量预览 | 后端 |
| IV-BE-006 | API 调用统计 | 后端 |
| IV-BE-007 | API 频率设置 | 后端 |
| IV-BE-008 | 健康检查 + 邮件系统 | 后端 |
| IV-FE-001 | 备份/恢复页面 | 前端 |
| IV-FE-002 | 批量操作 UI | 前端 |
| IV-FE-003 | 知识库页面 | 前端 |
| IV-FE-004 | 客户画像 UI | 前端 |
| IV-FE-005 | 模板变量预览 UI | 前端 |
| IV-FE-006 | API 统计页面 | 前端 |
| IV-FE-007 | API 频率设置页面 | 前端 |
| IV-FE-008 | 健康检查 + 邮件配置 UI | 前端 |

**总计**: 16 个任务（8 后端 + 8 前端）

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（V2.0 迭代轮）。请读取 docs/task-plan-iter-v2.md，一次性实现 IV-BE-001 ~ IV-BE-008 全部 8 个后端任务，不要中途暂停。

IV-BE-001: 数据库备份/恢复（db_backups 表 + pg_dump + 保留7个 + 定时备份）
IV-BE-002: 批量操作（标签/分配会话/发模板/导入商品）
IV-BE-003: 知识库管理（categories + articles 表 + 关键词+语义检索 + AI 回答）
IV-BE-004: 客户画像（行为数据 + 自动打标规则 + customer_auto_tag_rules 表）
IV-BE-005: 模板变量预览（系统变量 + mock 数据预览）
IV-BE-006: API 调用统计（Redis 计数中间件 + 4 个统计端点）
IV-BE-007: API 频率限制（api_rate_limits 表 + 中间件 + IP 封禁）
IV-BE-008: 健康检查（5 项检查 + email_config 表 + SMTP 邮件发送 + 60分钟定时检查）

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（V2.0 迭代轮）。请读取 docs/task-plan-iter-v2.md，一次性实现 IV-FE-001 ~ IV-FE-008 全部 8 个前端任务，不要中途暂停。

IV-FE-001: 数据库备份页面（列表+立即备份+恢复+下载+自动备份设置）
IV-FE-002: 批量操作 UI（ChatPage/CustomersPage/TicketsPage 底部批量栏+标签Modal+分配Modal+模板Modal+商品导入）
IV-FE-003: 知识库页面（左侧分类+右侧文章+搜索+编辑 Drawer）
IV-FE-004: 客户画像 Tab（行为数据卡片+标签区域+自动打标规则管理）
IV-FE-005: 模板变量预览（变量插入工具栏+实时预览卡片）
IV-FE-006: API 统计页面（汇总卡片+按代理商表格+按端点表格+代理商简化版）
IV-FE-007: API 频率设置页面（规则 CRUD+被封禁 IP 列表+解封）
IV-FE-008: 健康检查卡片（Dashboard 内）+ 邮件配置 Tab（SettingsPage 内）

新增权限码 16 个（backups/batch/knowledge/customer_profile/auto_tag/api_stats/rate_limits/email_config/health_check）
新增路由：/system/backups, /system/knowledge, /system/api-stats, /system/rate-limits

约束：npm run build + 一次性完成。开始吧。
```
