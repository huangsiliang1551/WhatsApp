# 上线前完整修复方案（LAUNCH-READY）

> **执行角色**: api_agent + frontend_agent + deploy_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-19
> **总架构师签发**
> **目标**: 一次性修复所有上线缺失项，达到生产可用标准

---

## 一、决策总览

```
三级架构:
  Level 1 超级管理员: / → 全部权限 + 全局监控
  Level 2 代理商: /agent/login → /agent/ → 自己的站点/下属/账单/审计
  Level 3 下属: /workspace/ → 按角色分配（固定 3 角色）

代理商账号: 超管创建时设置密码
代理商品牌: 全部自定义
代理商数据: 只看自己的，一个代理商一个站点
H5 模板: 超管创建，代理商选择，自动同步，全部免费
WABA 分配: 超管手动分配，可收回再分配，不能一个号分配多人
计费: 混合（按月+按站点+按充值），账单含费用明细
审计: 记录所有操作，代理商只查自己站点
通知: 代理商收到系统通知
SSL: Let's Encrypt + 自动续期
多语言: 多国语言，超管后台管理
移动端: 代理商适配，客服不适配
超管冗余页面: 移除 7 个，保留 API 测试 + 链路调试
```

---

## 二、后端任务（LR-BE）

### LR-BE-001：代理商账号密码（P0）

**修改**: `app/api/routes/agency.py` + `app/services/agency_service.py`

```python
# 创建代理商时接收 username + password
class CreateAgencyRequest(BaseModel):
    name: str
    username: str          # 登录用户名
    password: str          # 初始密码（min 8）
    brand_name: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None

# create_agency() 中：
# 1. 创建 agencies 记录
# 2. 创建 admin_users 记录（user_type="agent", agency_id=agency.id）
# 3. 密码 hash 存储
```

### LR-BE-002：代理商认证 API 完善（P0）

**修改**: `app/api/routes/agent_auth.py`

```python
# POST /api/agent-auth/login
# 接收 username + password
# 验证 admin_users 表中 user_type="agent" 的记录
# 返回 JWT token（含 agency_id, user_type）

# GET /api/agent-auth/me
# 返回当前代理商信息（含代理商品牌/联系人/站点数）

# POST /api/agent-auth/logout
# 清除 token / 记录登出日志

# POST /api/agent-auth/reset-password
# 代理商修改自己的密码
```

### LR-BE-003：代理商自助修改信息（P1）

**修改**: `app/api/routes/agency.py`

```python
# PATCH /api/agents/me
# 代理商修改自己的信息：brand_name/contact_name/contact_phone/contact_email
# 不允许修改：name/username/password（超管控制）
```

### LR-BE-004：WABA 分配完善（P0）

**修改**: `app/api/routes/waba_assignment.py`

```python
# POST /api/waba/{waba_id}/assign
# - 分配 WABA 给站点
# - 检查：该 WABA 是否已分配给其他站点（不能一个号分配多人）

# POST /api/waba/{waba_id}/reassign
# - 先收回（从原站点解绑）
# - 再分配给新站点
# - 检查：新站点是否属于同一代理商

# POST /api/waba/{waba_id}/revoke
# - 收回 WABA（不重新分配）
# - 记录审计日志

# GET /api/waba/{waba_id}/assignment
# - 查看 WABA 当前分配状态
```

### LR-BE-005：H5 模板市场初始化（P0）

**新增**: 数据初始化脚本

```python
# app/scripts/init_default_template.py
# 创建默认模板：当前 H5 前端作为第一套模板
default_template = H5Template(
    name="默认商城版",
    description="当前 H5 会员端标准模板",
    preview_url="/preview/default.png",
    template_data={
        "version": "1.0.0",
        "frontend_build": "dist/",
        "theme": {"primaryColor": "#1677ff"},
        "pages": ["home","tasks","invite","profile","recharge","withdraw"]
    }
)
```

### LR-BE-006：站点模板应用逻辑（P0）

**修改**: `app/api/routes/h5_templates.py`

```python
# POST /api/h5-templates/{template_id}/apply
# - 将模板应用到代理商的所有站点
# - 生成新的部署脚本（基于模板的 frontend_build）
# - 返回部署命令
```

### LR-BE-007：模板自动同步（P2）

**新增**: `app/services/template_sync_service.py`

```python
class TemplateSyncService:
    def sync_template_update(self, template_id: str):
        """模板更新后自动同步到所有使用该模板的代理商站点"""
        # 1. 查找所有使用此模板的代理商
        # 2. 更新站点的前端配置
        # 3. 标记需要重新部署
```

### LR-BE-008：账单创建 + 费用明细（P0+P2）

**修改**: `app/api/routes/agency_billing.py`

```python
# POST /api/agent-billing
# 超管创建账单
class CreateBillingRequest(BaseModel):
    agency_id: str
    billing_type: str  # monthly/per_site/per_recharge
    amount: float
    billing_period_start: str
    billing_period_end: str
    line_items: list[dict]  # 费用明细

# line_items 示例:
# [
#   {"description": "月费", "quantity": 1, "unit_price": 2999.00},
#   {"description": "站点费用 (3个站点)", "quantity": 3, "unit_price": 1000.00},
#   {"description": "充值分成 (¥50,000 * 2%)", "quantity": 1, "unit_price": 1000.00},
# ]

# GET /api/agent-billing/{id}
# 返回账单详情 + line_items 费用明细
```

### LR-BE-009：代理商审计日志（P1）

**修改**: `app/api/routes/agent_audit.py` (新增)

```python
# GET /api/agent-audit
# 代理商查看自己站点的审计日志
# 过滤：只返回 target 属于该代理商的站点的日志

# 记录所有操作（在中间件中统一拦截）：
# - 站点 CRUD
# - WABA 分配/收回
# - 下属管理
# - 模板选择
# - 账单操作
# - 登录/登出
```

### LR-BE-010：代理商通知（P1）

**新增**: 通知触发

```python
# 在以下场景创建通知：
# - 新站点分配给代理商
# - WABA 分配/收回
# - 账单创建/到期提醒
# - 模板更新需要同步
# - 下属账号创建

# 代理商通过 /api/notifications 查看（已有通知系统）
```

### LR-BE-011：数据隔离中间件集成（P1）

**修改**: `app/api/deps.py`

```python
# 在 get_db_session 依赖中集成 AgentDataIsolationMiddleware
# 根据 request actor 的 user_type 自动过滤数据
async def get_db_session(request: Request, actor = Depends(get_actor)):
    session = SessionLocal()
    if actor.user_type == "agent":
        # 自动过滤：只查询该代理商的数据
        middleware = AgentDataIsolationMiddleware(session, actor.agency_id)
        middleware.apply_filters()
    elif actor.user_type == "agent_member":
        # 按角色过滤
        middleware = AgentDataIsolationMiddleware(session, actor.agency_id, actor.role)
        middleware.apply_filters()
    yield session
    session.close()
```

### LR-BE-012：现有数据迁移（P0）

**新增**: 迁移脚本

```python
# app/scripts/migrate_to_multitenant.py
# 1. 创建默认代理商（将所有现有站点归属到默认代理商）
# 2. 为现有 admin 用户设置 user_type = "super_admin"
# 3. 将现有 WABA 分配到默认代理商
# 4. 将现有模板设置为全局模板（agent_id = NULL）
# 5. 将现有知识库设置为全局（agent_id = NULL）
```

### LR-BE-013：性能监控 API（P2）

**新增**: `app/api/routes/performance.py`

```python
# GET /api/performance/backend
# 后端服务器性能：CPU/内存/磁盘/数据库连接数/Redis 连接数

# GET /api/performance/frontend/{site_key}
# 前端服务器性能：从 uptime_checks 表获取响应时间/状态

# GET /api/performance/summary
# 汇总数据（Dashboard 用）
```

### LR-BE-014：多语言管理增强（P2）

**修改**: `app/api/routes/h5_languages.py`

```python
# 增强语言管理：
# - 支持 57 种中大型国家语言
# - 语言包管理（上传/下载翻译文件）
# - 代理商后台语言配置
# - 前端 i18n 文件生成
```

### LR-BE-015：SSL 自动续期（P1）

**修改**: `scripts/deploy-h5-site.sh`

```bash
# 在部署脚本中增加 certbot 自动续期 cron job
echo "设置 SSL 自动续期..."
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
echo "SSL 自动续期已配置（每天 3:00 检查）"
```

---

## 三、前端任务（LR-FE）

### LR-FE-001：代理商登录页面（P0）

**新增**: `frontend/src/pages/agent/AgentLoginPage.tsx` (~120 行)

```tsx
// 独立登录页面
// 用户名 + 密码 → POST /api/agent-auth/login
// 成功后 localStorage 存储 token → 跳转 /agent/
// 失败显示错误信息
```

### LR-FE-002：代理商登出（P0）

**修改**: `frontend/src/pages/agent/AgentLayout.tsx`

```tsx
// Sider 底部增加"登出"按钮
// 点击 → POST /api/agent-auth/logout → 清除 token → 跳转 /agent/login
```

### LR-FE-003：下属登出（P0）

**修改**: `frontend/src/pages/workspace/WorkspaceLayout.tsx`

```tsx
// 同代理商登出逻辑
```

### LR-FE-004：AgentsPage 增加密码字段（P0）

**修改**: `frontend/src/pages/AgentsPage.tsx`

```tsx
// 创建表单增加：
<Form.Item label="登录用户名" name="username" rules={[{ required: true }]}>
  <Input placeholder="agent001" disabled={!!editing} />
</Form.Item>
{!editing && (
  <Form.Item label="初始密码" name="password" rules={[{ required: true, min: 8 }]}>
    <Input.Password placeholder="至少 8 位" />
  </Form.Item>
)}

// 操作菜单增加：
{ key: "create-billing", label: "创建账单" }
{ key: "reset-password", label: "重置密码" }
```

### LR-FE-005：WABA 分配 Modal（P0）

**修改**: `frontend/src/pages/SitesPage.tsx`

```tsx
// 站点卡片菜单"分配 WABA"功能完善：
<Modal title="WABA 分配管理">
  {/* 已绑定 WABA 列表 */}
  <Table dataSource={boundWabas} columns={[
    { title: "WABA 名称" },
    { title: "号码" },
    { title: "操作", render: () => (
      <Space>
        <Button onClick={handleRevoke}>收回</Button>
        <Button onClick={handleReassign}>重新分配</Button>
      </Space>
    )}
  ]} />
  
  {/* 分配新 WABA */}
  <Select mode="multiple" options={availableWabas} />
  <Button onClick={handleAssign}>确认分配</Button>
</Modal>
```

### LR-FE-006：站点模板应用（P0）

**修改**: `frontend/src/pages/agent/AgentTemplatePage.tsx`

```tsx
// 选择模板后：
// 1. 调用 POST /api/h5-templates/{id}/apply
// 2. 返回部署脚本
// 3. 显示部署命令（可复制）
// 4. 提示"请在 H5 服务器上执行部署脚本"
```

### LR-FE-007：代理商密码重置（P1）

**修改**: `frontend/src/pages/agent/AgentProfilePage.tsx` (新增)

```tsx
// 代理商修改密码页面
<Form>
  <Form.Item label="当前密码" name="current_password">
    <Input.Password />
  </Form.Item>
  <Form.Item label="新密码" name="new_password">
    <Input.Password />
  </Form.Item>
  <Form.Item label="确认新密码" name="confirm_password">
    <Input.Password />
  </Form.Item>
</Form>
```

### LR-FE-008：代理商自助修改信息（P1）

**修改**: `frontend/src/pages/agent/AgentProfilePage.tsx`

```tsx
// 代理商修改：品牌名称/联系人/联系电话/联系邮箱
// 调用 PATCH /api/agents/me
```

### LR-FE-009：代理商审计日志 Tab（P1）

**修改**: `frontend/src/pages/agent/AgentDashboardPage.tsx`

```tsx
// 仪表盘增加 Tab：概览 / 审计日志
// 审计日志 Tab：
<Table dataSource={auditLogs} columns={[
  { title: "时间" },
  { title: "操作" },
  { title: "目标" },
  { title: "详情" },
  { title: "IP" },
]} />
```

### LR-FE-010：下属工作台真实功能（P1）

**修改**:
- `WorkspaceConversations.tsx`: 实现会话列表 + 消息面板（客服角色）
- `WorkspaceFinance.tsx`: 实现资金明细 + 提现处理（财务角色）
- `WorkspaceSites.tsx`: 实现站点只读列表（经理角色）

### LR-FE-011：账单详情费用明细（P2）

**修改**: `frontend/src/pages/agent/AgentBillingPage.tsx`

```tsx
// 详情 Modal 增加费用明细表
<Table dataSource={bill.line_items} columns={[
  { title: "项目", dataIndex: "description" },
  { title: "数量", dataIndex: "quantity" },
  { title: "单价", dataIndex: "unit_price" },
  { title: "小计", render: (_, r) => r.quantity * r.unit_price },
]} />
```

### LR-FE-012：超管后台冗余页面移除（P2）

**修改**: `frontend/src/routes/consoleRoutes.ts`

```tsx
// 移除以下页面（设置 visibleInNav: false 或直接删除）：
// 1. /system/organization → 移除
// 2. /system/member-access → 移除
// 3. /system/access-control → 移除
// 4. /system/identity-sync → 移除
// 5. /evidence-center → 移除
// 6. /system/logs → 移除
// 7. /users → 合并到 /members（保留 /members）

// 保留：
// - /whatsapp-api-test (API 测试)
// - /debug (链路调试)
```

### LR-FE-013：错误边界处理（P1）

**修改**: `frontend/src/App.tsx`

```tsx
// 代理商/下属访问无权限页面 → 404
// 使用 React ErrorBoundary 包裹路由
// 404 页面显示："页面不存在或您没有访问权限"
```

### LR-FE-014：超管 Dashboard 性能监控（P2）

**修改**: `frontend/src/pages/DashboardPage.tsx`

```tsx
// 增加性能监控卡片：
<Card title="后端服务器性能">
  <Statistic title="CPU" value={perf.cpu_percent} suffix="%" />
  <Statistic title="内存" value={perf.memory_mb} suffix="MB" />
  <Statistic title="数据库连接" value={perf.db_connections} />
  <Statistic title="Redis 连接" value={perf.redis_connections} />
</Card>
```

### LR-FE-015：站点管理前端服务器监控（P2）

**修改**: `frontend/src/pages/SitesPage.tsx`

```tsx
// 站点卡片增加前端服务器性能指标：
<Statistic title="响应时间" value={site.avg_response_time} suffix="ms" />
<Statistic title="可用率" value={site.uptime_percent} suffix="%" />
```

### LR-FE-016：代理商数据概览（P2）

**修改**: `frontend/src/pages/agent/AgentDashboardPage.tsx`

```tsx
// 因为一个代理商只有一个站点，仪表盘直接显示站点汇总：
<Card title="站点数据">
  <Statistic title="用户总数" value={stats.total_users} />
  <Statistic title="今日活跃" value={stats.active_users_today} />
  <Statistic title="今日签到" value={stats.sign_in_count_today} />
  <Statistic title="任务完成率" value={stats.task_completion_rate} suffix="%" />
  <Statistic title="今日收入" value={stats.revenue_today} prefix="¥" />
</Card>
```

### LR-FE-017：移动端适配（P2）

**修改**: `frontend/src/pages/agent/AgentLayout.tsx`

```tsx
// Sider 在移动端折叠
const isMobile = window.innerWidth < 768;
<Sider
  collapsible
  collapsed={isMobile}
  width={200}
>
  {/* 移动端只显示图标 */}
</Sider>
```

### LR-FE-018：多语言支持（P2）

**新增**: `frontend/src/i18n/` 目录

```
frontend/src/i18n/
  ├── zh-CN.json  (中文)
  ├── en-US.json  (英文)
  ├── ja-JP.json  (日文)
  └── index.ts    (i18n 初始化)

// 代理商后台/下属工作台使用 i18n
// 语言从代理商配置中读取
// 超管后台 /settings 语言管理页面配置可用语言
```

### LR-FE-019：大数据量分页优化（P2）

**修改**: 所有列表页面

```tsx
// 统一使用虚拟滚动 + 服务端分页
<Table
  virtual
  scroll={{ y: 600 }}
  pagination={{
    pageSize: 50,
    showTotal: (total) => `共 ${total} 条`,
  }}
  // 服务端分页：onChange → 调用 API 获取指定页数据
/>
```

---

## 四、部署任务（LR-DEPLOY）

### LR-DEPLOY-001：SSL 自动续期（P1）

**修改**: `scripts/deploy-h5-site.sh`

```bash
# 增加 certbot 自动续期配置
echo "[8/8] 配置 SSL 自动续期..."
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
echo "SSL 自动续期已配置（每天 3:00 检查，到期自动续期）"
```

---

## 五、任务清单

| # | 任务 | 类型 | 优先级 |
|---|------|------|--------|
| LR-BE-001 | 代理商账号密码 | 后端 | P0 |
| LR-BE-002 | 代理商认证 API 完善 | 后端 | P0 |
| LR-BE-003 | 代理商自助修改信息 | 后端 | P1 |
| LR-BE-004 | WABA 分配完善 | 后端 | P0 |
| LR-BE-005 | H5 模板市场初始化 | 后端 | P0 |
| LR-BE-006 | 站点模板应用逻辑 | 后端 | P0 |
| LR-BE-007 | 模板自动同步 | 后端 | P2 |
| LR-BE-008 | 账单创建 + 费用明细 | 后端 | P0+P2 |
| LR-BE-009 | 代理商审计日志 | 后端 | P1 |
| LR-BE-010 | 代理商通知 | 后端 | P1 |
| LR-BE-011 | 数据隔离中间件集成 | 后端 | P1 |
| LR-BE-012 | 现有数据迁移 | 后端 | P0 |
| LR-BE-013 | 性能监控 API | 后端 | P2 |
| LR-BE-014 | 多语言管理增强 | 后端 | P2 |
| LR-BE-015 | SSL 自动续期 | 部署 | P1 |
| LR-FE-001 | 代理商登录页面 | 前端 | P0 |
| LR-FE-002 | 代理商登出 | 前端 | P0 |
| LR-FE-003 | 下属登出 | 前端 | P0 |
| LR-FE-004 | AgentsPage 增加密码字段 | 前端 | P0 |
| LR-FE-005 | WABA 分配 Modal | 前端 | P0 |
| LR-FE-006 | 站点模板应用 | 前端 | P0 |
| LR-FE-007 | 代理商密码重置 | 前端 | P1 |
| LR-FE-008 | 代理商自助修改信息 | 前端 | P1 |
| LR-FE-009 | 代理商审计日志 Tab | 前端 | P1 |
| LR-FE-010 | 下属工作台真实功能 | 前端 | P1 |
| LR-FE-011 | 账单详情费用明细 | 前端 | P2 |
| LR-FE-012 | 超管冗余页面移除 | 前端 | P2 |
| LR-FE-013 | 错误边界处理 | 前端 | P1 |
| LR-FE-014 | 超管 Dashboard 性能监控 | 前端 | P2 |
| LR-FE-015 | 站点管理前端监控 | 前端 | P2 |
| LR-FE-016 | 代理商数据概览 | 前端 | P2 |
| LR-FE-017 | 移动端适配 | 前端 | P2 |
| LR-FE-018 | 多语言支持 | 前端 | P2 |
| LR-FE-019 | 大数据量分页优化 | 前端 | P2 |
| LR-DEPLOY-001 | SSL 自动续期脚本 | 部署 | P1 |

**总计**: 35 个任务（15 后端 + 19 前端 + 1 部署）

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（上线修复轮）。请读取 docs/task-plan-launch-ready.md，一次性实现 LR-BE-001 ~ LR-BE-015 全部 15 个后端任务，不要中途暂停。

核心任务：
P0: 代理商账号密码 + 认证 API + WABA 分配（收回/重分配/不能一号多人）+ 模板市场初始化 + 模板应用逻辑 + 账单创建 + 数据迁移脚本
P1: 代理商自助修改 + 审计日志（记录所有操作）+ 通知系统 + 数据隔离中间件 + SSL 自动续期
P2: 模板自动同步 + 性能监控 API + 多语言增强 + 账单费用明细

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（上线修复轮）。请读取 docs/task-plan-launch-ready.md，一次性实现 LR-FE-001 ~ LR-FE-019 全部 19 个前端任务，不要中途暂停。

核心任务：
P0: 代理商登录页 + 代理商/下属登出 + AgentsPage 密码字段 + WABA 分配 Modal + 站点模板应用
P1: 代理商密码重置 + 自助修改信息 + 审计日志 Tab + 下属工作台真实功能 + 错误边界 404
P2: 账单明细 + 冗余页面移除(7个) + 超管性能监控 + 站点前端监控 + 数据概览 + 移动端适配 + 多语言 + 大数据分页

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```

## 发给部署 Agent 的文本

```
你是部署 Agent。修改 scripts/deploy-h5-site.sh 增加 SSL 自动续期 cron job（每天 3:00 certbot renew）。一次性完成。
```
