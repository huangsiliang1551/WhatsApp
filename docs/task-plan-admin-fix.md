# 超管端全页面问题修复方案（ADMIN-FIX）

> **执行角色**: api_agent（后端）+ frontend_agent（前端）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-19
> **总架构师签发**
> **目标**: 修复超管端所有页面的数据显示、菜单调整、功能缺失问题

---

## 一、问题清单（22 项）

### A 类：数据显示问题（11 项）

| # | 页面 | 问题 | 预期 |
|---|------|------|------|
| AF-01 | 会话工作台 | 无数据 | 显示所有代理商的所有会话 |
| AF-02 | 工单管理 | 无数据 | 显示所有代理商的所有工单 |
| AF-03 | 客户管理 | 无数据 | 显示所有代理商的所有会员 |
| AF-04 | 审核队列 | 页面异常 | 显示所有代理商的审核项 |
| AF-05 | 媒体库 | 无数据 | 显示媒体资源 |
| AF-06 | 标签 | 无数据 | 显示标签 |
| AF-07 | 客服团队 | 无数据 | 显示代理商客服状态，区分代理商 |
| AF-08 | 任务管理 | 无数据 | 显示代理商的任务实例，区分代理商 |
| AF-09 | 报表中心 | 无数据 | 显示全局+代理商，区分 |
| AF-10 | 运营中心 | 无数据 | 显示全局+代理商，区分 |
| AF-11 | Meta 账户 | 无数据 | 显示全局+代理商，区分 |

### B 类：页面错误（2 项）

| # | 页面 | 问题 | 预期 |
|---|------|------|------|
| AF-12 | 审核队列 | 页面异常 | 修复异常，正常显示 |
| AF-13 | 任务规则 | 页面异常 | 修复异常，正常显示 |

### C 类：菜单调整（4 项）

| # | 页面 | 问题 | 预期 |
|---|------|------|------|
| AF-14 | 角色管理 | 超管不应该有此菜单 | 超管隐藏，代理商显示 |
| AF-15 | 自动分配规则 | 超管不应该有此菜单 | 超管隐藏，代理商显示 |
| AF-16 | 集成管理 | 不需要 | 删除页面和代码 |
| AF-17 | WhatsApp 统计 | 与报表中心重复 | 合并到报表中心 |

### D 类：功能缺失（5 项）

| # | 页面 | 问题 | 预期 |
|---|------|------|------|
| AF-18 | 模板消息 | 无数据 | 显示固定模板+代理商模板，区分 |
| AF-19 | 系统设置 | AI 配置/翻译配置 | 恢复之前的数据 |
| AF-20 | 代理商管理 | 缺少密码修改/账单管理/核销 | 增加代理商密码修改+账单管理+付款核销 |
| AF-21 | H5 模板市场 | 缺少预览功能 | 增加预览（非线上版本）+ 测试账号 |
| AF-22 | 报表中心 | 缺少财务报表 | 增加财务报表 Tab |

---

## 二、后端任务（AF-BE）

### AF-BE-001：超管端数据全量查询修复（AF-01~AF-11）

**根因**: 数据隔离中间件对超管也进行了过滤，或者查询 API 需要 account_id/agency_id 但前端未传递。

**修复策略**: 所有查询 API 增加超管判断逻辑：

```python
# 通用模式
async def list_xxx(
    account_id: str | None = Query(None),
    agency_id: str | None = Query(None),
    actor: RequestActor = Depends(get_actor),
    session: Session = Depends(get_db_session),
):
    query = select(XxxModel)
    
    if actor.is_super_admin:
        # 超管：返回所有数据
        if agency_id:
            # 如果指定了代理商，只返回该代理商的
            query = query.filter_by(agency_id=agency_id)
    elif actor.user_type == "agent":
        # 代理商：只返回自己的
        query = query.filter_by(agency_id=actor.agency_id)
    elif actor.user_type == "agent_member":
        # 下属：按角色过滤
        query = query.filter_by(agency_id=actor.agency_id)
    
    return session.scalars(query).all()
```

**需修改的文件**:

| 文件 | 修改内容 |
|------|---------|
| `app/api/routes/conversations.py` | 超管查看所有会话 |
| `app/api/routes/tickets.py` | 超管查看所有工单 |
| `app/api/routes/platform.py` (users) | 超管查看所有会员 |
| `app/api/routes/reviews.py` | 超管查看所有审核 |
| `app/api/routes/media.py` | 超管查看所有媒体 |
| `app/api/routes/tags.py` | 超管查看所有标签 |
| `app/api/routes/members.py` | 超管查看所有客服 + 区分代理商 |
| `app/api/routes/task_instances.py` | 超管查看所有任务 + 区分代理商 |
| `app/api/routes/reports.py` | 超管查看全局+代理商 |
| `app/api/routes/operations.py` | 超管查看全局+代理商 |
| `app/api/routes/meta_accounts.py` | 超管查看全局+代理商 |

### AF-BE-002：页面错误修复（AF-12, AF-13）

**审核队列异常**: 检查 `app/api/routes/reviews.py` 的 API 是否正常，修复前端调用错误。

**任务规则异常**: 检查 `app/api/routes/task_rules.py` 的 API 是否正常，修复前端调用错误。

### AF-BE-003：模板消息区分（AF-18）

```python
# app/api/routes/templates.py
@router.get("")
async def list_templates(
    agency_id: str | None = Query(None),
    actor: RequestActor = Depends(get_actor),
):
    # 全局固定模板（agency_id = NULL）
    global_templates = session.scalars(
        select(MessageTemplate).where(MessageTemplate.agency_id.is_(None))
    ).all()
    
    # 代理商模板
    if actor.is_super_admin:
        agency_templates = session.scalars(
            select(MessageTemplate).where(MessageTemplate.agency_id.is_not(None))
        ).all()
    elif actor.user_type == "agent":
        agency_templates = session.scalars(
            select(MessageTemplate).where(MessageTemplate.agency_id == actor.agency_id)
        ).all()
    
    return {
        "global_templates": [...],  # 固定模板
        "agency_templates": [...],  # 代理商模板
    }
```

### AF-BE-004：代理商管理增强（AF-20）

```python
# app/api/routes/agency.py 增强

@router.patch("/{agency_id}/reset-password")
async def reset_agent_password(agency_id: str, payload: ResetPasswordRequest):
    """超管重置代理商密码"""

@router.get("/{agency_id}/billing")
async def list_agency_billing(agency_id: str):
    """查看代理商的所有账单"""

@router.post("/{agency_id}/billing/{billing_id}/verify")
async def verify_billing_payment(agency_id: str, billing_id: str):
    """核销账单（标记已收到付款）"""
```

### AF-BE-005：H5 模板预览（AF-21）

```python
# app/api/routes/h5_templates.py 增强

@router.get("/{template_id}/preview")
async def preview_template(template_id: str):
    """预览模板（返回预览 URL + 测试账号）"""
    template = session.get(H5Template, template_id)
    return {
        "preview_url": f"/preview/templates/{template_id}",
        "test_account": {
            "username": "preview_user",
            "password": "Preview@2026",
        },
        "template_data": template.template_data,
    }
```

### AF-BE-006：财务报表 API（AF-22）

```python
# app/api/routes/reports.py 增加

@router.get("/finance")
async def finance_report(
    agency_id: str | None = Query(None),
    period: str = Query("monthly"),  # daily/weekly/monthly
    actor: RequestActor = Depends(get_actor),
):
    """财务报表"""
    return {
        "total_revenue": ...,       # 总收入
        "total_billing": ...,       # 总账单
        "paid_billing": ...,        # 已付账单
        "pending_billing": ...,     # 待付账单
        "recharge_amount": ...,     # 充值金额
        "withdraw_amount": ...,     # 提现金额
        "commission": ...,          # 佣金
        "details": [...],           # 明细
    }
```

---

## 三、前端任务（AF-FE）

### AF-FE-001：菜单调整（AF-14~AF-17）

**修改**: `frontend/src/routes/consoleRoutes.ts`

```tsx
// 角色管理 → 超管隐藏
{ id: "roles", visibleInNav: false, ... }

// 自动分配规则 → 超管隐藏
{ id: "automation", visibleInNav: false, ... }

// 集成管理 → 删除
// 移除 IntegrationsPage 相关路由

// WhatsApp 统计 → 合并到报表中心
{ id: "whatsapp_stats", visibleInNav: false, ... }
```

**修改**: `frontend/src/App.tsx`

```tsx
// 移除集成管理的懒加载和渲染
// WhatsApp 统计内容合并到 ReportsPage
```

**新增**: `frontend/src/pages/agent/AgentRolesPage.tsx`
```tsx
// 代理商后台增加角色管理页面
// 路径: /agent/roles
```

**新增**: `frontend/src/pages/agent/AgentAutomationPage.tsx`
```tsx
// 代理商后台增加自动分配规则页面
// 路径: /agent/automation
```

### AF-FE-002：数据显示修复（AF-01~AF-11）

各页面修复 API 调用，超管端不传 agency_id（获取全部数据）：

| 页面 | 修改内容 |
|------|---------|
| ChatPage | 超管不传 agency_id，获取所有会话 |
| TicketsPage | 同上 |
| CustomersPage | 同上 |
| ReviewsPage | 修复页面异常 |
| MediaLibraryPage | 超管获取所有媒体 |
| TagsPage | 超管获取所有标签 |
| MembersPage | 显示代理商客服，增加代理商筛选 |
| TasksPage | 显示代理商任务，增加代理商筛选 |
| ReportsPage | 全局+代理商区分 |
| OperationsCenterPage | 全局+代理商区分 |
| MetaAccountsPage | 全局+代理商区分 |

### AF-FE-003：模板消息区分显示（AF-18）

**修改**: `frontend/src/pages/TemplatePage.tsx`

```tsx
<Tabs>
  <Tabs.TabPane tab="全局模板" key="global">
    <Table dataSource={globalTemplates} />
  </Tabs.TabPane>
  <Tabs.TabPane tab="代理商模板" key="agency">
    <Select placeholder="选择代理商" options={agencies} />
    <Table dataSource={agencyTemplates} />
  </Tabs.TabPane>
</Tabs>
```

### AF-FE-004：代理商管理增强（AF-20）

**修改**: `frontend/src/pages/AgentsPage.tsx`

```tsx
// 操作菜单增加：
{ key: "reset-password", label: "重置密码", onClick: () => handleResetPassword(agent) }
{ key: "billing", label: "账单管理", onClick: () => handleBilling(agent) }

// 新增 Modal: 重置密码
<Modal title="重置代理商密码">
  <Form>
    <Form.Item label="新密码" name="password">
      <Input.Password />
    </Form.Item>
  </Form>
</Modal>

// 新增 Drawer: 账单管理
<Drawer title={`${agent.name} 账单管理`}>
  <Table dataSource={bills} columns={[
    { title: "类型" },
    { title: "金额" },
    { title: "状态", render: (s) => <Tag>{s}</Tag> },
    { title: "操作", render: (_, r) => (
      r.status === "pending" && (
        <Button onClick={() => handleVerifyPayment(r)}>核销</Button>
      )
    )},
  ]} />
</Drawer>
```

### AF-FE-005：H5 模板预览（AF-21）

**修改**: `frontend/src/pages/H5TemplateMarketPage.tsx`

```tsx
// 操作列增加"预览"按钮
<Button onClick={() => handlePreview(template)}>预览</Button>

// 预览 Modal
<Modal title="模板预览" width={800}>
  <Space direction="vertical" style={{ width: "100%" }}>
    <Alert message="预览模式（非线上版本）" type="info" />
    <iframe src={previewUrl} style={{ width: "100%", height: 500 }} />
    <Descriptions>
      <Descriptions.Item label="测试账号">preview_user</Descriptions.Item>
      <Descriptions.Item label="测试密码">Preview@2026</Descriptions.Item>
    </Descriptions>
  </Space>
</Modal>
```

### AF-FE-006：报表中心增强（AF-17, AF-22）

**修改**: `frontend/src/pages/ReportsPage.tsx`

```tsx
<Tabs>
  <Tabs.TabPane tab="WhatsApp 统计" key="whatsapp">
    {/* 原 WhatsAppStatsPage 内容 */}
  </Tabs.TabPane>
  <Tabs.TabPane tab="运营报表" key="operations">
    {/* 运营数据 */}
  </Tabs.TabPane>
  <Tabs.TabPane tab="财务报表" key="finance">
    {/* 收入/账单/充值/提现/佣金 */}
    <Row gutter={16}>
      <Col span={6}><Statistic title="总收入" value={finance.total_revenue} prefix="¥" /></Col>
      <Col span={6}><Statistic title="已付账单" value={finance.paid_billing} prefix="¥" /></Col>
      <Col span={6}><Statistic title="待付账单" value={finance.pending_billing} prefix="¥" /></Col>
      <Col span={6}><Statistic title="充值金额" value={finance.recharge_amount} prefix="¥" /></Col>
    </Row>
    <Table dataSource={finance.details} />
  </Tabs.TabPane>
</Tabs>
```

### AF-FE-007：系统设置数据恢复（AF-19）

**修改**: `frontend/src/pages/SettingsPage.tsx`

```tsx
// AI 配置 Tab: 确保加载已保存的配置
// 翻译配置 Tab: 确保加载已保存的配置
// 检查 API 调用是否正确传递数据
```

### AF-FE-008：删除集成管理页面（AF-16）

**删除**: `frontend/src/pages/IntegrationsPage.tsx`

**修改**: `frontend/src/routes/consoleRoutes.ts`
- 移除 integrations 路由定义

**修改**: `frontend/src/App.tsx`
- 移除 IntegrationsPage 懒加载
- 移除 renderPage 中的 integrations 分支

---

## 四、任务清单

| # | 任务 | 类型 | 优先级 | 关联 |
|---|------|------|--------|------|
| AF-BE-001 | 超管端数据全量查询修复 | 后端 | P0 | AF-01~11 |
| AF-BE-002 | 页面错误修复 | 后端 | P0 | AF-12,13 |
| AF-BE-003 | 模板消息区分 | 后端 | P1 | AF-18 |
| AF-BE-004 | 代理商管理增强 | 后端 | P1 | AF-20 |
| AF-BE-005 | H5 模板预览 | 后端 | P1 | AF-21 |
| AF-BE-006 | 财务报表 API | 后端 | P1 | AF-22 |
| AF-FE-001 | 菜单调整 | 前端 | P0 | AF-14~17 |
| AF-FE-002 | 数据显示修复 | 前端 | P0 | AF-01~11 |
| AF-FE-003 | 模板消息区分显示 | 前端 | P1 | AF-18 |
| AF-FE-004 | 代理商管理增强 UI | 前端 | P1 | AF-20 |
| AF-FE-005 | H5 模板预览 UI | 前端 | P1 | AF-21 |
| AF-FE-006 | 报表中心增强 | 前端 | P1 | AF-17,22 |
| AF-FE-007 | 系统设置数据恢复 | 前端 | P1 | AF-19 |
| AF-FE-008 | 删除集成管理页面 | 前端 | P0 | AF-16 |

**总计**: 14 个任务（6 后端 + 8 前端）

---

## 五、执行顺序

```
Day 1 (后端):
  AF-BE-001 超管端数据全量查询（11 个 API）
  AF-BE-002 页面错误修复
  AF-BE-003 模板消息区分
  AF-BE-004 代理商管理增强
  AF-BE-005 H5 模板预览
  AF-BE-006 财务报表 API

Day 2 (前端):
  AF-FE-001 菜单调整（隐藏角色/自动分配 + 删除集成管理 + 合并 WhatsApp）
  AF-FE-002 数据显示修复（11 个页面）
  AF-FE-003 模板消息区分显示
  AF-FE-004 代理商管理增强 UI
  AF-FE-005 H5 模板预览 UI
  AF-FE-006 报表中心增强（WhatsApp + 运营 + 财务）
  AF-FE-007 系统设置数据恢复
  AF-FE-008 删除集成管理页面
```

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（超管修复轮）。请读取 docs/task-plan-admin-fix.md，一次性实现 AF-BE-001 ~ AF-BE-006 全部 6 个后端任务，不要中途暂停。

AF-BE-001（P0，超管全量查询）：
修改 11 个 API，超管不传 agency_id 时返回所有数据：
- conversations.py / tickets.py / platform.py(users) / reviews.py
- media.py / tags.py / members.py / task_instances.py
- reports.py / operations.py / meta_accounts.py
通用模式：actor.is_super_admin → 返回全部；agent → 只返回自己的

AF-BE-002（P0，页面错误）：修复 reviews.py 和 task_rules.py 的 API 异常

AF-BE-003（P1，模板区分）：templates.py 返回 global_templates + agency_templates

AF-BE-004（P1，代理商增强）：agency.py 增加 reset-password + billing + verify-payment

AF-BE-005（P1，模板预览）：h5_templates.py 增加 preview 端点（预览 URL + 测试账号）

AF-BE-006（P1，财务报表）：reports.py 增加 /finance 端点（收入/账单/充值/提现/佣金）

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（超管修复轮）。请读取 docs/task-plan-admin-fix.md，一次性实现 AF-FE-001 ~ AF-FE-008 全部 8 个前端任务，不要中途暂停。

AF-FE-001（P0，菜单调整）：
- 角色管理 visibleInNav: false（超管隐藏）
- 自动分配规则 visibleInNav: false（超管隐藏）
- AgentLayout.tsx 增加角色管理 + 自动分配规则菜单
- WhatsApp 统计 visibleInNav: false（合并到报表）

AF-FE-002（P0，数据显示）：
11 个页面修复 API 调用，超管不传 agency_id 获取全部数据
重点：ChatPage/TicketsPage/CustomersPage/MembersPage/TasksPage/ReportsPage

AF-FE-003（P1，模板区分）：TemplatePage Tabs（全局模板 + 代理商模板）
AF-FE-004（P1，代理商增强）：AgentsPage 增加重置密码 + 账单管理 Drawer + 核销按钮
AF-FE-005（P1，模板预览）：H5TemplateMarketPage 增加预览 Modal + 测试账号
AF-FE-006（P1，报表增强）：ReportsPage Tabs（WhatsApp + 运营 + 财务）
AF-FE-007（P1，设置恢复）：SettingsPage AI 配置 + 翻译配置加载已保存数据
AF-FE-008（P0，删除集成管理）：删除 IntegrationsPage + 路由 + 懒加载

约束：npm run build + 一次性完成。开始吧。
```
