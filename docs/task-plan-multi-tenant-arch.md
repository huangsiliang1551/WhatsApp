# 三级租户架构完整设计（MULTI-TENANT-ARCH）

> **执行角色**: api_agent（后端）+ frontend_agent（前端）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 实现三级租户架构（超级管理员 → 代理商 → 下属），含 H5 模板市场、WABA 分配、数据隔离

---

## 一、架构总览

### 三级架构

```
Level 1: 超级管理员（平台方）
  URL: /（当前后台）
  权限: 全部
  可见: 所有代理商 + 所有站点 + 全局配置 + H5 模板市场

Level 2: 代理商（站点拥有者，仅 1 个管理员）
  URL: /agent/
  权限: 管理自己的站点/下属/品牌/账单 + 查看审计日志
  可见: 自己的站点 + 自己的下属 + 自己的账单 + H5 模板选择（预览）
  品牌: 统一平台品牌（不显示代理商独立品牌）

Level 3: 代理商下属（自定义角色）
  URL: /workspace/
  权限: 按角色分配
    - 客服: 处理会话 + 查看会员
    - 财务: 查看资金明细 + 处理提现
    - 经理: 管理站点 + 查看数据
    - 其他自定义角色
  可见: 按角色分配的功能
```

### 数据归属规则

```
所有业务数据 → 站点 → 代理商（严格隔离）

会话 → site_key → site.agent_id
WhatsApp 账号 → waba.agent_id（独立不共享，可重新分配，1 站点可绑定多个 WABA）
会员 → user.registration_site_id → site.agent_id
资金 → wallet.user.site.agent_id（代理商只读，财务可处理提现）
模板 → template.agent_id（NULL=全局，xxx=代理商私有）
知识库 → kb.agent_id（NULL=全局，xxx=代理商私有）
工单 → ticket.site_key → site.agent_id
任务 → task.site_key → site.agent_id
签到/邀请 → user.site.agent_id
代理商账单 → billing.agent_id（混合计费）
H5 模板 → 超级管理员创建，代理商选择使用（一个代理商一个模板）
```

### H5 模板市场规则

- **模板来源**: 超级管理员创建
- **模板位置**: 超级管理员后台管理 + 代理商后台选择
- **模板付费**: 全部免费
- **模板修改**: 代理商只能选择不能改
- **模板版本**: 不分版本（直接覆盖）
- **模板共享**: 代理商之间不共享
- **模板可见性**: 代理商看不到其他代理商使用了哪些模板
- **模板预览**: 是（预览界面）
- **选择时机**: 站点创建后随时更换
- **使用限制**: 一个代理商一个模板

### WABA 分配规则

- **分配方式**: 超级管理员手动分配
- **绑定数量**: 一个站点可绑定多个 WABA
- **重新分配**: 是（可重新分配给其他站点）
- **共享**: WABA 独立不共享

### 代理商计费

- **计费方式**: 混合（按月 + 按站点 + 按充值）
- **账单可见性**: 代理商只查看自己的账单
- **财务权限**: 可处理提现 + 查看资金明细

---

## 二、后端任务（MT-BE）

### MT-BE-001：代理商表 + 下属表（迁移）

- **估计耗时**: 60 分钟

#### 新增表

```sql
-- 0096_agents.sql
CREATE TABLE agents (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,           -- 代理商名称
  brand_name VARCHAR(200),              -- 品牌名称（用于 H5 站点）
  logo_url VARCHAR(500),                -- Logo（用于 H5 站点）
  contact_name VARCHAR(100),            -- 联系人
  contact_phone VARCHAR(20),            -- 联系电话
  contact_email VARCHAR(200),           -- 联系邮箱
  status VARCHAR(32) DEFAULT 'active',  -- active/paused/archived
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 0097_agent_members.sql
CREATE TABLE agent_members (
  id VARCHAR(36) PRIMARY KEY,
  agent_id VARCHAR(36) REFERENCES agents(id),
  user_id VARCHAR(36) REFERENCES admin_users(id),
  role VARCHAR(32) NOT NULL,  -- finance/manager/support/custom
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(agent_id, user_id)
);

-- 0098_agent_billing.sql
CREATE TABLE agent_billing (
  id VARCHAR(36) PRIMARY KEY,
  agent_id VARCHAR(36) REFERENCES agents(id),
  billing_type VARCHAR(32),  -- monthly/per_site/per_recharge
  amount DECIMAL(12, 2),
  billing_period_start DATE,
  billing_period_end DATE,
  status VARCHAR(32),  -- pending/paid/overdue
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### 修改表

```sql
-- 0099_site_agent_id.sql
ALTER TABLE h5_sites ADD COLUMN agent_id VARCHAR(36) REFERENCES agents(id);

-- 0100_waba_agent_id.sql
ALTER TABLE whatsapp_business_accounts ADD COLUMN agent_id VARCHAR(36) REFERENCES agents(id);

-- 0101_template_agent_id.sql
ALTER TABLE message_templates ADD COLUMN agent_id VARCHAR(36) REFERENCES agents(id);

-- 0102_kb_agent_id.sql
ALTER TABLE support_knowledge_entries ADD COLUMN agent_id VARCHAR(36) REFERENCES agents(id);

-- 0103_admin_user_type.sql
ALTER TABLE admin_users ADD COLUMN user_type VARCHAR(32) DEFAULT 'super_admin';
ALTER TABLE admin_users ADD COLUMN agent_id VARCHAR(36) REFERENCES agents(id);
```

---

### MT-BE-002：H5 模板表（迁移）

- **估计耗时**: 30 分钟

#### 新增表

```sql
-- 0104_h5_templates.sql
CREATE TABLE h5_templates (
  id VARCHAR(36) PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  preview_url VARCHAR(500),        -- 预览图 URL
  template_data JSON,              -- 模板配置数据
  created_by VARCHAR(36),          -- 创建人（超级管理员）
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 0105_agent_template.sql
CREATE TABLE agent_templates (
  id VARCHAR(36) PRIMARY KEY,
  agent_id VARCHAR(36) REFERENCES agents(id),
  template_id VARCHAR(36) REFERENCES h5_templates(id),
  selected_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(agent_id)  -- 一个代理商一个模板
);
```

---

### MT-BE-003：代理商服务（3 个服务）

- **估计耗时**: 120 分钟

#### 服务清单

| 服务 | 说明 | 行数 |
|------|------|------|
| `AgentService` | 代理商 CRUD + 下属管理 | ~200 行 |
| `AgentAuthService` | 代理商认证 + 权限校验 | ~150 行 |
| `AgentDashboardService` | 代理商数据聚合 | ~150 行 |

#### AgentService 方法

```python
class AgentService:
    def list_agents(self) -> list[Agent]
    def create_agent(self, data: AgentCreateRequest) -> Agent
    def update_agent(self, agent_id: str, data: AgentUpdateRequest) -> Agent
    def delete_agent(self, agent_id: str) -> None  # 软删除
    def list_members(self, agent_id: str) -> list[AgentMember]
    def add_member(self, agent_id: str, user_id: str, role: str) -> AgentMember
    def update_member_role(self, member_id: str, role: str) -> AgentMember
    def remove_member(self, member_id: str) -> None
```

#### AgentAuthService 方法

```python
class AgentAuthService:
    def authenticate(self, username: str, password: str) -> AgentAuthResult
    def get_agent_by_user(self, user_id: str) -> Agent | None
    def check_permission(self, user_id: str, resource: str, resource_id: str) -> bool
    def get_accessible_sites(self, user_id: str) -> list[H5Site]
    def get_accessible_data(self, user_id: str, data_type: str) -> list
```

#### AgentDashboardService 方法

```python
class AgentDashboardService:
    def get_dashboard(self, agent_id: str) -> AgentDashboard
    # 返回: 站点统计/收入统计/下属统计
```

---

### MT-BE-004：代理商 API（4 组）

- **估计耗时**: 90 分钟

#### API 清单

| API 组 | 端点 | 说明 |
|--------|------|------|
| 代理商管理 | `/api/agents/*` | CRUD + 下属管理（仅超级管理员） |
| 代理商认证 | `/api/agent-auth/*` | 登录/权限校验 |
| 代理商数据 | `/api/agent-dashboard/*` | 数据聚合（代理商+下属） |
| H5 模板 | `/api/h5-templates/*` | 模板管理（超管）+ 选择（代理商） |

#### 端点详情

```
POST   /api/agents                          创建代理商（超管）
GET    /api/agents                          列表（超管全部，代理商自己）
PATCH  /api/agents/{id}                     更新代理商
DELETE /api/agents/{id}                     删除代理商（软删除）
POST   /api/agents/{id}/members             添加下属
PATCH  /api/agents/{id}/members/{member_id} 修改下属角色
DELETE /api/agents/{id}/members/{member_id} 删除下属

POST   /api/agent-auth/login               代理商登录
GET    /api/agent-auth/me                  当前代理商信息

GET    /api/agent-dashboard                代理商仪表盘数据
GET    /api/agent-dashboard/sites          站点统计
GET    /api/agent-dashboard/revenue        收入统计
GET    /api/agent-dashboard/members        下属统计

GET    /api/h5-templates                   模板列表（超管全部，代理商可选）
POST   /api/h5-templates                   创建模板（超管）
PATCH  /api/h5-templates/{id}              更新模板（超管）
DELETE /api/h5-templates/{id}              删除模板（超管）
POST   /api/h5-templates/{id}/select       代理商选择模板
GET    /api/h5-templates/{id}/preview      模板预览
```

---

### MT-BE-005：WABA 分配 API

- **估计耗时**: 30 分钟

#### 端点

```
POST   /api/waba/{waba_id}/assign          分配 WABA 给站点（超管）
POST   /api/waba/{waba_id}/reassign        重新分配 WABA（超管）
GET    /api/waba/{waba_id}                 WABA 详情
GET    /api/sites/{site_id}/waba           站点的 WABA 列表
```

---

### MT-BE-006：代理商账单 API

- **估计耗时**: 45 分钟

#### 端点

```
GET    /api/agent-billing                  账单列表（超管全部，代理商自己）
POST   /api/agent-billing                  创建账单（超管）
PATCH  /api/agent-billing/{id}             更新账单状态（超管+财务）
GET    /api/agent-billing/{id}             账单详情
```

---

### MT-BE-007：数据隔离中间件

- **估计耗时**: 60 分钟

#### 实现

```python
# app/core/agent_middleware.py

class AgentDataIsolationMiddleware:
    """根据 user_type 过滤数据"""
    
    def filter_queryset(self, queryset, user_id: str, data_type: str):
        user_type = get_user_type(user_id)
        
        if user_type == "super_admin":
            return queryset  # 全部可见
        
        elif user_type == "agent":
            agent_id = get_agent_id(user_id)
            if data_type == "site":
                return queryset.filter(agent_id=agent_id)
            elif data_type == "member":
                return queryset.filter(agent_id=agent_id)
            elif data_type == "conversation":
                site_ids = get_agent_site_ids(agent_id)
                return queryset.filter(site_key__in=site_ids)
            # ... 其他数据类型
        
        elif user_type == "agent_member":
            agent_id = get_agent_id_by_member(user_id)
            role = get_member_role(user_id)
            # 按角色过滤
            if role == "support":
                # 客服只看分配给自己的
                return queryset.filter(assigned_agent_id=user_id)
            elif role == "finance":
                # 财务只看资金相关
                return queryset.filter(data_type__in=["wallet", "withdrawal"])
            # ...
```

---

## 三、前端任务（MT-FE）

### MT-FE-001：代理商后台框架

- **估计耗时**: 60 分钟

#### 新增页面

| 页面 | 路径 | 说明 |
|------|------|------|
| AgentDashboardPage | `/agent/` | 代理商仪表盘 |
| AgentSitesPage | `/agent/sites` | 代理商站点管理 |
| AgentMembersPage | `/agent/members` | 代理商下属管理 |
| AgentBillingPage | `/agent/billing` | 代理商账单 |
| AgentTemplatePage | `/agent/templates` | H5 模板选择 |

#### 路由配置

```typescript
// frontend/src/routes/agentRoutes.ts

export const agentRoutes = [
  { path: "/agent", component: AgentDashboardPage },
  { path: "/agent/sites", component: AgentSitesPage },
  { path: "/agent/members", component: AgentMembersPage },
  { path: "/agent/billing", component: AgentBillingPage },
  { path: "/agent/templates", component: AgentTemplatePage },
];
```

---

### MT-FE-002：代理商仪表盘

- **估计耗时**: 60 分钟

#### 页面结构

```tsx
<PageShell title="代理商仪表盘">
  <Row gutter={16}>
    <Col span={8}>
      <Card title="站点统计">
        <Statistic title="站点总数" value={stats.total_sites} />
        <Statistic title="活跃站点" value={stats.active_sites} />
        <Statistic title="今日活跃用户" value={stats.active_users_today} />
      </Card>
    </Col>
    <Col span={8}>
      <Card title="收入统计">
        <Statistic title="本月收入" value={stats.revenue_this_month} prefix="¥" />
        <Statistic title="待收账款" value={stats.pending_billing} prefix="¥" />
      </Card>
    </Col>
    <Col span={8}>
      <Card title="下属统计">
        <Statistic title="下属总数" value={stats.total_members} />
        <Statistic title="在线客服" value={stats.online_support} />
      </Card>
    </Col>
  </Row>
</PageShell>
```

---

### MT-FE-003：代理商站点管理

- **估计耗时**: 60 分钟

#### 页面结构

```tsx
<PageShell title="站点管理">
  <Table
    dataSource={sites}
    columns={[
      { title: "站点名称", dataIndex: "brand_name" },
      { title: "域名", dataIndex: "domain" },
      { title: "状态", dataIndex: "status" },
      { title: "用户数", dataIndex: "user_count" },
      { title: "今日活跃", dataIndex: "active_users_today" },
      { title: "操作", render: (_, record) => (
        <Space>
          <Button onClick={() => handleEdit(record)}>编辑</Button>
          <Button onClick={() => handleChangeTemplate(record)}>更换模板</Button>
          <Button onClick={() => handleManageWaba(record)}>管理 WABA</Button>
          <Button danger onClick={() => handleDelete(record)}>删除</Button>
        </Space>
      )}
    ]}
  />
</PageShell>
```

---

### MT-FE-004：代理商下属管理

- **估计耗时**: 45 分钟

#### 页面结构

```tsx
<PageShell title="下属管理">
  <Table
    dataSource={members}
    columns={[
      { title: "用户名", dataIndex: "username" },
      { title: "角色", dataIndex: "role" },
      { title: "创建时间", dataIndex: "created_at" },
      { title: "操作", render: (_, record) => (
        <Space>
          <Button onClick={() => handleChangeRole(record)}>修改角色</Button>
          <Button danger onClick={() => handleRemove(record)}>移除</Button>
        </Space>
      )}
    ]}
  />
</PageShell>
```

---

### MT-FE-005：代理商账单

- **估计耗时**: 45 分钟

#### 页面结构

```tsx
<PageShell title="账单管理">
  <Table
    dataSource={billing}
    columns={[
      { title: "账单类型", dataIndex: "billing_type" },
      { title: "金额", dataIndex: "amount" },
      { title: "账单周期", render: (_, record) => `${record.billing_period_start} ~ ${record.billing_period_end}` },
      { title: "状态", dataIndex: "status" },
      { title: "操作", render: (_, record) => (
        <Space>
          {record.status === "pending" && (
            <Button onClick={() => handleMarkPaid(record)}>标记已支付</Button>
          )}
          <Button onClick={() => handleViewDetail(record)}>查看详情</Button>
        </Space>
      )}
    ]}
  />
</PageShell>
```

---

### MT-FE-006：H5 模板选择

- **估计耗时**: 60 分钟

#### 页面结构

```tsx
<PageShell title="H5 模板">
  <Alert message="当前使用的模板：XXX" type="info" />
  
  <Table
    dataSource={templates}
    columns={[
      { title: "模板名称", dataIndex: "name" },
      { title: "描述", dataIndex: "description" },
      { title: "预览", render: (_, record) => (
        <Button onClick={() => handlePreview(record)}>预览</Button>
      )},
      { title: "操作", render: (_, record) => (
        <Space>
          {record.is_selected ? (
            <Tag color="success">当前使用</Tag>
          ) : (
            <Button onClick={() => handleSelect(record)}>选择使用</Button>
          )}
        </Space>
      )}
    ]}
  />
  
  {/* 模板预览 Modal */}
  <Modal title="模板预览" open={previewOpen}>
    <iframe src={previewUrl} style={{ width: "100%", height: 600 }} />
  </Modal>
</PageShell>
```

---

### MT-FE-007：下属工作台框架

- **估计耗时**: 45 分钟

#### 新增页面

| 页面 | 路径 | 说明 |
|------|------|------|
| WorkspaceDashboard | `/workspace/` | 下属工作台首页 |
| WorkspaceConversations | `/workspace/conversations` | 会话处理（客服） |
| WorkspaceFinance | `/workspace/finance` | 资金明细（财务） |
| WorkspaceSites | `/workspace/sites` | 站点管理（经理） |

#### 路由配置

```typescript
// frontend/src/routes/workspaceRoutes.ts

export const workspaceRoutes = [
  { path: "/workspace", component: WorkspaceDashboard },
  { path: "/workspace/conversations", component: WorkspaceConversations, roles: ["support"] },
  { path: "/workspace/finance", component: WorkspaceFinance, roles: ["finance"] },
  { path: "/workspace/sites", component: WorkspaceSites, roles: ["manager"] },
];
```

---

### MT-FE-008：超级管理员后台增强

- **估计耗时**: 60 分钟

#### 新增页面

| 页面 | 路径 | 说明 |
|------|------|------|
| AgentsPage | `/agents` | 代理商列表 + CRUD |
| AgentDetailPage | `/agents/{id}` | 代理商详情 + 下属管理 |
| H5TemplateMarketPage | `/h5-templates` | H5 模板市场管理 |

#### 修改页面

| 页面 | 修改内容 |
|------|---------|
| SitesPage | 增加代理商筛选 + 代理商归属显示 + WABA 分配按钮 |
| App.tsx | 根据 user_type 跳转不同后台 |

---

## 四、任务清单

| # | 任务 | 类型 | 工作量 | 依赖 |
|---|------|------|--------|------|
| MT-BE-001 | 代理商表 + 下属表 | 后端 | 60 分钟 | - |
| MT-BE-002 | H5 模板表 | 后端 | 30 分钟 | - |
| MT-BE-003 | 代理商服务（3 个） | 后端 | 120 分钟 | MT-BE-001 |
| MT-BE-004 | 代理商 API（4 组） | 后端 | 90 分钟 | MT-BE-003 |
| MT-BE-005 | WABA 分配 API | 后端 | 30 分钟 | MT-BE-001 |
| MT-BE-006 | 代理商账单 API | 后端 | 45 分钟 | MT-BE-001 |
| MT-BE-007 | 数据隔离中间件 | 后端 | 60 分钟 | MT-BE-003 |
| MT-FE-001 | 代理商后台框架 | 前端 | 60 分钟 | MT-BE-004 |
| MT-FE-002 | 代理商仪表盘 | 前端 | 60 分钟 | MT-BE-004 |
| MT-FE-003 | 代理商站点管理 | 前端 | 60 分钟 | MT-BE-004 |
| MT-FE-004 | 代理商下属管理 | 前端 | 45 分钟 | MT-BE-004 |
| MT-FE-005 | 代理商账单 | 前端 | 45 分钟 | MT-BE-006 |
| MT-FE-006 | H5 模板选择 | 前端 | 60 分钟 | MT-BE-004 |
| MT-FE-007 | 下属工作台框架 | 前端 | 45 分钟 | MT-BE-004 |
| MT-FE-008 | 超级管理员后台增强 | 前端 | 60 分钟 | MT-BE-004 |

**总计**: 15 个任务（7 后端 + 8 前端），预计 12 小时

---

## 五、执行顺序

```
Day 1 (后端):
  MT-BE-001 代理商表 + 下属表
  MT-BE-002 H5 模板表
  MT-BE-003 代理商服务
  MT-BE-004 代理商 API
  MT-BE-005 WABA 分配 API
  MT-BE-006 代理商账单 API
  MT-BE-007 数据隔离中间件

Day 2 (前端):
  MT-FE-001 代理商后台框架
  MT-FE-002 代理商仪表盘
  MT-FE-003 代理商站点管理
  MT-FE-004 代理商下属管理
  MT-FE-005 代理商账单
  MT-FE-006 H5 模板选择
  MT-FE-007 下属工作台框架
  MT-FE-008 超级管理员后台增强
```

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（三级租户架构轮）。请读取 docs/task-plan-multi-tenant-arch.md，一次性实现 MT-BE-001 ~ MT-BE-007 全部 7 个后端任务，不要中途暂停。

核心任务：
1. MT-BE-001 代理商表 + 下属表 + 账单表 + 站点/WABA/模板/知识库增加 agent_id
2. MT-BE-002 H5 模板表 + 代理商-模板关系表
3. MT-BE-003 代理商服务（AgentService + AgentAuthService + AgentDashboardService）
4. MT-BE-004 代理商 API（4 组 16 个端点）
5. MT-BE-005 WABA 分配 API（分配/重新分配）
6. MT-BE-006 代理商账单 API（CRUD）
7. MT-BE-007 数据隔离中间件（按 user_type 过滤数据）

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（三级租户架构轮）。请读取 docs/task-plan-multi-tenant-arch.md，一次性实现 MT-FE-001 ~ MT-FE-008 全部 8 个前端任务，不要中途暂停。

核心任务：
1. MT-FE-001 代理商后台框架（/agent/* 路由 + 5 个页面）
2. MT-FE-002 代理商仪表盘（站点统计/收入统计/下属统计）
3. MT-FE-003 代理商站点管理（CRUD + 更换模板 + 管理 WABA）
4. MT-FE-004 代理商下属管理（添加/修改角色/移除）
5. MT-FE-005 代理商账单（列表 + 标记已支付）
6. MT-FE-006 H5 模板选择（列表 + 预览 + 选择使用）
7. MT-FE-007 下属工作台框架（/workspace/* 路由 + 4 个页面）
8. MT-FE-008 超级管理员后台增强（AgentsPage + H5TemplateMarketPage + SitesPage 增强）

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```
