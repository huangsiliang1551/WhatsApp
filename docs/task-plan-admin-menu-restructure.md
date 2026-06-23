# 管理后台菜单与页面重构任务（AF4-001 ~ AF4-10）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 重构菜单结构，合并冗余页面，达到产品级菜单体验

---

## 0. 背景

当前 35 个页面分 4 组，"系统与审计"组 19 页严重超载。操作员找不到高频页面，安全/审计功能分散在 4-5 个入口。

**核心原则**: 每组 ≤ 7 页，高频操作前置，低频功能折叠。

---

## 1. 当前 vs 目标菜单结构

### 当前（4 组 35 页）

```
核心工作台 (5): 概览 / 会话工作台 / Meta账户 / 模板消息 / WhatsApp统计
触达资产 (4):   媒体库 / 标签 / 受众规则 / 商城数据
业务协同 (7):   任务 / 审核队列 / 工单 / 坐席成员 / 会话分配 / 自动化规则 / 客户
系统与审计(19): 监控 / 集成 / API-Webhook / 审计 / 系统日志 / 证据 / 设置 / 组织
               / 用户 / 通知 / 身份同步 / 安全设置 / 成员授权 / 访问控制 / 告警
               / 通道事件 / 角色 / 报表 / 导入导出 / 风控 / 操作中心 / 站点
```

### 目标（6 组 28 页）

```
工作台 (6):     概览 / 会话工作台 / 我的队列 / 工单 / 客户 / 审核队列
内容中心 (4):   模板消息 / 媒体库 / 标签 / 商城数据
人员管理 (5):   客服团队 / 任务中心 / 后台用户 / 角色权限 / 自动分配规则
数据报表 (3):   WhatsApp统计 / 报表中心 / 运营看板
系统设置 (5):   Meta账户 / 系统设置 / 集成管理 / 组织团队 / 安全中心
运维监控 (5):   监控健康 / 审计日志 / 告警中心 / 通道事件 / 导入导出
```

---

## 2. 执行编排

```
Phase 1（路由重构 — 零页面改动，仅改配置）:
  AF4-001 (类型 + 路由 + 标签) ── frontend_agent     ← 核心改动
  AF4-002 (App.tsx 适配)       ── frontend_agent     ← 依赖 AF4-001

Phase 2（页面合并 — 新建合并页）:
  AF4-003 (安全中心 Tab 页)    ── frontend_agent     ← 合并 4 安全页
  AF4-004 (审计日志 Tab 扩展)  ── frontend_agent     ← 合并 3 日志页
  AF4-005 (告警中心 Tab 扩展)  ── frontend_agent     ← 合并 2 告警页
  AF4-006 (集成管理 Tab 扩展)  ── frontend_agent     ← 合并 3 集成页

Phase 3（页面改名 + 微调）:
  AF4-007 (导航改名 + 图标)    ── frontend_agent
  AF4-008 (角色权限 Tab 扩展)  ── frontend_agent     ← 合并授权/访问控制

Phase 4（验证）:
  AF4-009 (构建 + 路由验证)    ── testing_agent
  AF4-010 (行为测试不退化)     ── testing_agent
```

---

## Phase 1：路由重构（P0 — 仅改配置文件）

### AF4-001：类型定义 + 路由配置

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 1.1 修改 `frontend/src/types/console.ts`

`ConsoleRouteGroup` 从 4 个扩展到 6 个：

```typescript
export type ConsoleRouteGroup =
  | "workspace"      // 工作台（原 core_workspace）
  | "content"        // 内容中心（原 assets）
  | "people"         // 人员管理（新）
  | "analytics"      // 数据报表（新）
  | "settings"       // 系统设置（新）
  | "devops";        // 运维监控（新）
```

新增 icon key（如缺少）：

```typescript
// 确认 ConsoleRouteIconKey 包含以下值（已存在则跳过）
| "my_queue"        // 我的队列
| "team"            // 客服团队
| "security_center" // 安全中心
| "ops_board"       // 运营看板
```

#### 1.2 修改 `frontend/src/routes/consoleRoutes.ts`

每个路由的 `group` 和 `order` 字段调整如下（仅列变化项）：

| 路由 ID | 原 group | 新 group | 新 order | navLabel 变化 |
|---------|---------|----------|---------|--------------|
| `dashboard` | core_workspace | **workspace** | 10 | 不变 |
| `conversations` | core_workspace | **workspace** | 20 | 不变 |
| `assignments` | collaboration | **workspace** | 30 | **我的队列** |
| `tickets` | collaboration | **workspace** | 40 | 不变 |
| `customers` | collaboration | **workspace** | 50 | 不变 |
| `reviews` | collaboration | **workspace** | 60 | 不变 |
| `templates` | core_workspace | **content** | 10 | 不变 |
| `media` | assets | **content** | 20 | 不变 |
| `tags` | assets | **content** | 30 | 不变 |
| `audience_rules` | assets | **content** | 35 | 不变（后续合并入标签） |
| `ecommerce` | assets | **content** | 40 | 不变 |
| `members` | collaboration | **people** | 10 | **客服团队** |
| `tasks` | collaboration | **people** | 20 | 不变 |
| `users` | system | **people** | 30 | **后台用户** |
| `roles` | system | **people** | 40 | 不变 |
| `automation` | collaboration | **people** | 50 | **自动分配规则** |
| `whatsapp_stats` | core_workspace | **analytics** | 10 | 不变 |
| `reports` | system | **analytics** | 20 | 不变 |
| `operations` | system | **analytics** | 30 | **运营看板** |
| `meta` | core_workspace | **settings** | 10 | 不变 |
| `settings` | system | **settings** | 20 | 不变 |
| `integrations` | system | **settings** | 30 | 不变 |
| `organization` | system | **settings** | 40 | 不变 |
| `security_settings` | system | **settings** | 50 | **安全中心** |
| `monitoring` | system | **devops** | 10 | 不变 |
| `audit` | system | **devops** | 20 | 不变 |
| `alerts` | system | **devops** | 30 | 不变 |
| `provider_events` | system | **devops** | 40 | 不变 |
| `imports` | system | **devops** | 50 | 不变 |

以下路由在 Phase 2 合并后设为 `visibleInNav: false`（保留路由但不在菜单显示）：

| 路由 ID | 合并入 | 处理 |
|---------|--------|------|
| `api_webhooks` | integrations Tab | `visibleInNav: false` |
| `sites` | integrations Tab | `visibleInNav: false` |
| `identity_sync` | security_settings Tab | `visibleInNav: false` |
| `member_access` | security_settings Tab | `visibleInNav: false` |
| `access_control` | security_settings Tab | `visibleInNav: false` |
| `risk` | security_settings Tab | `visibleInNav: false` |
| `system_logs` | audit Tab | `visibleInNav: false` |
| `evidence_center` | audit Tab | `visibleInNav: false` |
| `notifications` | alerts Tab | `visibleInNav: false` |
| `audience_rules` | tags Tab | `visibleInNav: false` |

#### 1.3 修改 `buildGroup` 和 `groupedConsoleRoutes`

```typescript
export const groupedConsoleRoutes = {
  workspace: buildGroup("workspace"),
  content: buildGroup("content"),
  people: buildGroup("people"),
  analytics: buildGroup("analytics"),
  settings: buildGroup("settings"),
  devops: buildGroup("devops"),
} satisfies Record<ConsoleRouteGroup, ConsoleRouteDefinition[]>;
```

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/types/console.ts` | 修改（ConsoleRouteGroup 6 值 + 新 icon key） |
| `frontend/src/routes/consoleRoutes.ts` | 修改（每个路由的 group/order/navLabel/visibleInNav） |

#### 验收标准

1. `ConsoleRouteGroup` 为 6 个值
2. 每个路由的 group/order 正确
3. 被合并路由 `visibleInNav: false`
4. 构建通过

---

### AF4-002：App.tsx 适配

- **优先级**: P0
- **前置依赖**: AF4-001
- **估计耗时**: 15 分钟

#### 修改 `frontend/src/App.tsx`

`GROUP_LABELS` 更新：

```typescript
const GROUP_LABELS: Record<ConsoleRouteGroup, string> = {
  workspace: "工作台",
  content: "内容中心",
  people: "人员管理",
  analytics: "数据报表",
  settings: "系统设置",
  devops: "运维监控",
};
```

侧边栏图标映射（如有 `getGroupIcon` 函数）同步更新。

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/App.tsx` | 修改（GROUP_LABELS + 图标映射） |

#### 验收标准

1. 侧边栏显示 6 个分组
2. 分组名正确（工作台/内容中心/人员管理/数据报表/系统设置/运维监控）
3. 构建通过

---

## Phase 2：页面合并（P1 — Tab 页聚合）

### AF4-003：安全中心（合并 4 安全页 + 风控）

- **优先级**: P1
- **估计耗时**: 60 分钟

#### 目标

将 `SecuritySettingsPage` 重构为 Tab 容器页，聚合 5 个安全相关页面的内容。

#### 实现要求

修改 `frontend/src/pages/SecuritySettingsPage.tsx`（如果不存在则用对应文件）：

```tsx
// 安全中心 — 5 个 Tab
<Tabs defaultActiveKey="security" items={[
  { key: "security", label: "安全策略", children: <SecuritySettingsContent /> },
  { key: "identity", label: "身份同步", children: <IdentitySyncContent /> },
  { key: "authorization", label: "成员授权", children: <MemberAccessContent /> },
  { key: "access", label: "访问控制", children: <AccessControlContent /> },
  { key: "risk", label: "风控名单", children: <RiskContent /> },
]} />
```

**内容组件抽取规则**:
- 从原 `SecuritySettingsPage.tsx` 提取 `SecuritySettingsContent`
- 从原 `IdentitySyncPage.tsx` 提取 `IdentitySyncContent`
- 从原 `MemberAccessPage.tsx` 提取 `MemberAccessContent`
- 从原 `AccessControlPage.tsx` 提取 `AccessControlContent`
- 从原 `RiskPage.tsx` 提取 `RiskContent`

每个 Content 组件保留原页面的核心功能，移除页面级布局（面包屑、页面标题等，由容器统一提供）。

#### 涉及文件

| 文件 | 动作 |
|------|------|
| 安全中心页面文件 | 重写为 Tab 容器 + 5 个 Content 组件 |
| 原 4 个独立安全页面 | 保留文件但标记为 deprecated（路由仍可达，只是不在菜单） |

#### 验收标准

1. 安全中心页面有 5 个 Tab
2. 每个 Tab 内容对应原页面功能
3. Tab 切换不刷新页面
4. 构建通过

---

### AF4-004：审计日志扩展（合并系统日志 + 证据中心）

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 实现要求

修改审计日志页面，增加 Tab：

```tsx
<Tabs defaultActiveKey="audit" items={[
  { key: "audit", label: "审计日志", children: <AuditLogsContent /> },
  { key: "system", label: "系统日志", children: <SystemLogsContent /> },
  { key: "evidence", label: "证据中心", children: <EvidenceContent /> },
]} />
```

#### 验收标准

1. 审计页面有 3 个 Tab
2. 各 Tab 功能对应原页面
3. 构建通过

---

### AF4-005：告警中心扩展（合并通知中心）

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

```tsx
<Tabs defaultActiveKey="alerts" items={[
  { key: "alerts", label: "告警规则", children: <AlertsContent /> },
  { key: "notifications", label: "通知渠道", children: <NotificationsContent /> },
]} />
```

#### 验收标准

1. 告警中心有 2 个 Tab
2. 构建通过

---

### AF4-006：集成管理扩展（合并 API/Webhook + 站点）

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

```tsx
<Tabs defaultActiveKey="integrations" items={[
  { key: "integrations", label: "集成概览", children: <IntegrationsContent /> },
  { key: "webhooks", label: "API / Webhook", children: <ApiWebhooksContent /> },
  { key: "sites", label: "站点管理", children: <SitesContent /> },
]} />
```

#### 验收标准

1. 集成管理有 3 个 Tab
2. 构建通过

---

## Phase 3：改名 + 角色权限扩展（P1）

### AF4-007：导航改名 + Dashboard 快捷入口

- **优先级**: P1
- **估计耗时**: 20 分钟

#### 导航改名清单

| 原 navLabel | 新 navLabel | 说明 |
|-------------|-------------|------|
| 会话分配 | **我的队列** | 客服视角命名 |
| 坐席成员 | **客服团队** | 管理视角命名 |
| 操作中心 | **运营看板** | 运营视角命名 |
| 后台用户（原"用户"） | **后台用户** | 区分 H5 会员 |
| 自动化规则 | **自动分配规则** | 明确功能范围 |
| 系统与审计 | **（已拆分）** | 不再使用 |

#### Dashboard 快捷入口

在 `DashboardPage.tsx` 增加"快捷操作"卡片区域：

```tsx
<Card title="快捷操作">
  <Row gutter={16}>
    <Col span={6}><Button onClick={goTo("/conversations")}>进入工作台</Button></Col>
    <Col span={6}><Button onClick={goTo("/collaboration/assignments")}>我的队列</Button></Col>
    <Col span={6}><Button onClick={goTo("/collaboration/tickets")}>处理工单</Button></Col>
    <Col span={6}><Button onClick={goTo("/collaboration/reviews")}>审核队列</Button></Col>
  </Row>
</Card>
```

#### 验收标准

1. 导航文案全部更新
2. Dashboard 有快捷操作入口
3. 构建通过

---

### AF4-008：角色权限 Tab 扩展（合并成员授权 + 访问控制）

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

```tsx
<Tabs defaultActiveKey="roles" items={[
  { key: "roles", label: "角色定义", children: <RolesContent /> },
  { key: "authorization", label: "成员授权", children: <MemberAccessContent /> },
  { key: "access", label: "访问策略", children: <AccessControlContent /> },
]} />
```

**注意**: `MemberAccessContent` 和 `AccessControlContent` 与 AF4-003 安全中心共用。提取为独立组件后两处都引用。

#### 验收标准

1. 角色权限页有 3 个 Tab
2. 与安全中心的 Tab 内容组件共享
3. 构建通过

---

## Phase 4：验证（P0）

### AF4-009：构建 + 路由验证

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
```

#### 手动路由验证清单

| 路径 | 预期 |
|------|------|
| `/` | Dashboard（工作台组） |
| `/conversations` | 会话工作台 |
| `/collaboration/assignments` | 我的队列 |
| `/collaboration/tickets` | 工单 |
| `/collaboration/customers` | 客户 |
| `/collaboration/reviews` | 审核队列 |
| `/templates` | 模板消息（内容中心组） |
| `/assets/media` | 媒体库 |
| `/collaboration/members` | 客服团队（人员管理组） |
| `/system/users` | 后台用户 |
| `/system/security-settings` | 安全中心（5 Tab） |
| `/audit` | 审计日志（3 Tab） |
| `/system/alerts` | 告警中心（2 Tab） |
| `/system/integrations` | 集成管理（3 Tab） |
| `/system/roles` | 角色权限（3 Tab） |
| `/analytics/whatsapp` | WhatsApp 统计（数据报表组） |
| `/system/operations` | 运营看板 |
| `/monitoring` | 监控健康（运维监控组） |

#### 侧边栏验证

| 验证项 | 预期 |
|--------|------|
| 分组数量 | 6 个 |
| 工作台页面数 | 6 |
| 内容中心页面数 | 4-5（含受众规则过渡期） |
| 人员管理页面数 | 5 |
| 数据报表页面数 | 3 |
| 系统设置页面数 | 5 |
| 运维监控页面数 | 5 |
| 最大组页面数 | ≤ 6 |

#### 验收标准

1. 构建通过
2. 6 个分组显示正确
3. 每组 ≤ 7 页
4. 所有路由可达

---

### AF4-010：行为测试不退化

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend

# 现有测试
npm run test -- src/services/operations.test.ts
npm run test -- src/pages/admin-chat.test.tsx
npm run test -- src/pages/templatePage.test.tsx
npm run test -- src/pages/metaAccountsPage.test.tsx
npm run test -- src/pages/dashboardPage.test.tsx
npm run test -- src/pages/loginPage.test.tsx
npm run test -- src/services/adminAuth.test.ts
npm run test -- src/services/chatRealtime.test.ts
npm run test -- src/pages/memberCustomerNavigation.test.tsx
```

#### 验收标准

1. 全部现有测试通过（不退化）
2. `memberCustomerNavigation.test.tsx` 不失败（如预存问题则记录）

---

## 3. 全局约束

1. **不碰 H5**: 不改 `h5-member/` 目录
2. **不改后端**: 不改 `app/` 目录
3. **保留所有原有路由**: `visibleInNav: false` 的路由仍然可访问（书签兼容）
4. **Tab 合并页保留原功能**: 不删除任何功能，只是重新组织入口
5. **保持 real/mock 分层**
6. **保持 prefill 跳转机制**
7. **进度文件**: `.codex-run/progress/AF4-XXX.json`
8. **单任务最大执行 60 分钟**
9. **失败自动回滚 + 重试最多 3 次**
10. **每次改动后 `npm run build` 必须通过**
11. **一次性执行全部任务，不中途暂停确认**

---

## 4. 改动文件影响范围

| 文件 | 改动类型 | 风险 |
|------|---------|------|
| `types/console.ts` | 类型扩展 | 低（纯类型） |
| `routes/consoleRoutes.ts` | group/order/navLabel/visibleInNav | **中**（核心路由配置） |
| `App.tsx` | GROUP_LABELS | 低 |
| `pages/SecuritySettingsPage.tsx` | 重写为 Tab 容器 | 中 |
| `pages/AuditLogsPage.tsx` (或对应) | 增加 Tab | 中 |
| `pages/AlertsPage.tsx` (或对应) | 增加 Tab | 中 |
| `pages/IntegrationsPage.tsx` (或对应) | 增加 Tab | 中 |
| `pages/RolesPage.tsx` (或对应) | 增加 Tab | 中 |
| `pages/DashboardPage.tsx` | 增加快捷操作卡片 | 低 |
| `pages/h5-member/` | **不动** | 无 |
| `app/` | **不动** | 无 |
