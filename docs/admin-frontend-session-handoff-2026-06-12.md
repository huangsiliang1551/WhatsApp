# 后台前端接力会话文档

更新时间：2026-06-12
适用目录：`E:\codex\WhatsApp`
线程范围：只负责后台前端全站，不碰 H5，不重做后端，不阻塞主线。

## 1. 这份文档的目的

给新会话直接接班用。

新会话可以扫描目录，但很多线程级约束、已做决策、哪些页面是真接口、哪些仍是 mock/hybrid、哪些坑不能踩，这些不一定能靠扫目录快速看出来。本文档把这些内容一次性整理清楚，目标是让新的会话进入后 5-10 分钟内就能继续推进，而不是重新探索。

## 2. 本线程必须遵守的硬约束

### 2.1 项目与技术方向

- 后端：FastAPI
- 前端：React + Vite + TypeScript
- 当前后台栈：React + Ant Design + ProComponents
- 状态管理：Zustand
- 请求方式：统一经 `frontend/src/services/`
- 样式方向：蓝灰色主流互联网后台

### 2.2 本线程的职责边界

- 只做后台前端全站，不做 H5。
- 不要修改 H5 页面、H5 路由、H5 样式。另一个线程专门负责 H5。
- 不主动重做后端。
- 不主动修改后端主线核心实现。
- 允许优先读取、对接已有后端接口。
- 后端没有的功能，一律先 mock/hybrid，不因为缺后端停下。

### 2.3 默认允许修改的前端目录

- `frontend/src/pages/`
- `frontend/src/components/`
- `frontend/src/features/`
- `frontend/src/services/`
- `frontend/src/mocks/`
- `frontend/src/types/`
- `frontend/src/routes/`
- `frontend/src/styles/`

### 2.4 默认不要修改的区域

- `app/db/`
- `app/providers/`
- `alembic/`
- `worker/`
- `docker-compose.yml`

### 2.5 后台前端实现的固定规则

- 页面组件不得直接写 `fetch`。
- 所有接口统一走 `frontend/src/services/`。
- real API 和 mock fallback 必须分层，不允许揉成一团。
- 所有核心类型统一放 `frontend/src/types/`。
- 所有账号、会话、模板、日志数据默认带 `account_id` 作用域。
- AI 状态必须展示“最终结果 + 原因”，不能只显示布尔值。
- 页面不能直接绑定 Meta webhook 原始 payload。
- 后台不要出现说明性“运营提示文字”。
- 不要新增“原型/首版/等待后端/coming soon”这一类说明文案。

## 3. 用户已经明确给过的设计与产品偏好

- 后台颜色必须走蓝灰后台，不要偏暖色，不要花哨渐变。
- 后台样式统一使用 React + Ant Design / ProComponents。
- 后台要像可工作的系统，不只是几个演示页面。
- 多账号模型必须贯穿全站。
- 后台必须体现：
  - 多账号
  - 会话并行
  - AI 开关三级控制 + 接管优先级
  - 人工接管 / 恢复 AI
  - 模板管理
  - 系统设置
  - 健康状态 / 基础监控

## 4. 当前后台前端的架构入口

### 4.1 入口文件

- `frontend/src/main.tsx`
  - 已接入 `ConfigProvider`
  - 已接入 `AntdApp`
  - 已接入 `antd/dist/reset.css`
  - 已统一蓝灰主题 token

- `frontend/src/App.tsx`
  - 后台主壳是 `ProLayout`
  - 保留了手写路由，不使用 `react-router`
  - 后台页通过懒加载方式映射
  - H5 仍作为懒加载页存在，但本线程不要碰

### 4.2 路由与菜单

- `frontend/src/routes/consoleRoutes.ts`
  - 后台菜单分组、标题、路径、图标、数据源标识都在这里
  - 路由元数据里已有：
    - `group`
    - `icon`
    - `order`
    - `path`
    - `title`
    - `dataBadges`
    - `progress`

- `frontend/src/routes/adminUrlState.ts`
  - 后台跨页跳转时的 URL 状态同步都在这里
  - 大量页面依赖 prefill 跳转，不能随意绕开

### 4.3 状态与跨页导航

- `frontend/src/stores/appStore.ts`
  - `AppPageId` 已包含后台页标识
  - 各页面的 prefill 类型都定义在这里
  - `openWorkspacePage / openAuditPage / openWhatsAppStatsPage / openRolesPage / openMemberAccessPage / openAccessControlPage / openSecuritySettingsPage / openIdentitySyncPage` 等跳转能力已经存在

### 4.4 后台主题与壳组件

- `frontend/src/styles/admin.css`
  - 已经和 H5 样式分离
  - 当前后台主色是标准蓝，底色/边框/文字是灰阶
  - 侧边栏是深蓝灰

- `frontend/src/components/AdminRoutePageShell.tsx`
  - 所有后台页面通用页头包装层
  - 负责显示进度标签和数据源标签

## 5. 当前后台站点整体状态

### 5.1 已完成的核心基础设施

- 后台已整体迁移到 `AntD + ProLayout + ProTable` 风格。
- 后台导航、路由、分组侧边栏已成型。
- 蓝灰主题已统一。
- 后台说明性文字已做过一轮清理。
- 后台不再从壳层暴露 H5 入口。
- 构建是通过的。

### 5.2 当前后台路由分组

`consoleRoutes.ts` 中当前分组为：

- `核心工作台`
  - 概览
  - 会话工作台
  - Meta 账户
  - 模板消息
  - WhatsApp 统计

- `触达资产`
  - 媒体库
  - 标签
  - 受众规则
  - 商城数据

- `业务协同`
  - 任务
  - 审核队列
  - 工单
  - 坐席成员
  - 会话分配
  - 自动化规则
  - 客户

- `系统与审计`
  - 监控健康
  - 集成管理
  - API / Webhook
  - 审计日志
  - 系统日志
  - 证据中心
  - 系统设置
  - 组织与团队设置
  - 用户
  - 通知中心
  - 身份同步
  - 安全设置
  - 成员授权
  - 访问控制
  - 告警中心
  - 通道事件
  - 角色权限
  - 报表中心
  - 导入导出
  - 风控中心
  - 运营中心

## 6. 当前真实接口 / hybrid / mock 状态总表

下面是当前最重要的判断，新会话不要重新猜。

### 6.1 已接真实接口或真实接口优先的页面

这些页面已经能接真实后端数据，或者主数据链路已是真接口优先：

- `DashboardPage`
- `ChatPage`
- `MetaAccountsPage`
- `TemplatePage`
- `SettingsPage`
- `MonitoringPage`
- `WhatsAppStatsPage`
- `AuditPage`
- `IntegrationsPage`
- `ApiWebhooksPage`
- `ProviderEventsPage`
- `SystemLogsPage`
- `UsersPage`
- `SitesPage`
- `TagsPage`
- `AudienceRulesPage`
- `TasksPage`

### 6.2 仍然是 hybrid 或 mock 为主的页面

这些页面已经可浏览、可交互、可跳转，但部分数据和操作仍依赖 mock/hybrid：

- `NotificationsPage`
- `OrganizationSettingsPage`
- `AccessControlPage`
- `SecuritySettingsPage`
- `IdentitySyncPage`
- `MemberAccessPage`
- `RolesPage`
- `EvidenceCenterPage`
- `OperationsCenterPage`
- `EcommercePage`
- `AutomationRulesPage`
- `RiskCenterPage`
- `AssignmentsPage`
- `CustomersPage`
- `MembersPage`
- `ReviewsPage`
- `TicketsPage`
- `ReportsPage`
- `AlertsPage`

### 6.3 数据源标签含义

项目里约定：

- `API`
  - 主要业务数据来自真实接口

- `混合`
  - 有一部分真实接口
  - 缺口由本地推导或 mock service 补齐

- `模拟`
  - 当前主要是前端 mock / 本地服务

新会话继续推进时，不要把这三类标识做没，也不要为了“看起来更完整”把 mock 装成 API。

## 7. 已经完成过的关键改动

以下内容已经做过，不要重复推翻。

### 7.1 后台整体迁移到 Ant Design

已完成：

- 后台壳切换到 `ProLayout`
- 主后台页大面积切换为 `Card / ProTable / Descriptions / Form / Tabs`
- 主题统一到蓝灰后台

### 7.2 清理后台说明性文字

已明确执行过：

- 删掉说明型“运营提示文字”
- 不新增“等待后端、原型、首版、coming soon”类提示
- 页面可保留必要的数据状态标签，但不要写解释型运营文案

### 7.3 重要页面已经增强

已明确增强过的页面：

- `AutomationRulesPage`
  - 多账号过滤
  - 统计卡片
  - 更后台化的规则编排表单
  - 仍为 mock

- `RiskCenterPage`
  - 多账号过滤
  - 统计卡片
  - 风险项详情
  - 仍为 mock

- `RolesPage`
  - 新增角色统计卡片
  - 增加到 `成员授权 / 访问控制 / 审计` 的联动入口

- `SecuritySettingsPage`
  - 新增到 `角色权限` 的联动入口
  - 安全统计扩成 6 个指标

- `IdentitySyncPage`
  - 新增到 `角色权限` 的联动入口
  - 增加映射成员、已验证域名统计

- `ChatPage`
  - 已删除遗留死代码 `loadConversationCustomerContextLegacy`

### 7.4 后台壳和导航层的重要调整

- `AdminRoutePageShell` 与 `App.tsx` 已经完成后台导航壳统一。
- H5 快捷入口已从后台壳去掉。

## 8. 本线程最近改过的关键文件

下面这些文件近期最相关，新会话建议优先读：

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/styles/admin.css`
- `frontend/src/components/AdminRoutePageShell.tsx`
- `frontend/src/routes/consoleRoutes.ts`
- `frontend/src/routes/adminUrlState.ts`
- `frontend/src/stores/appStore.ts`

近期重点页面：

- `frontend/src/pages/ChatPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/MonitoringPage.tsx`
- `frontend/src/pages/MetaAccountsPage.tsx`
- `frontend/src/pages/TemplatePage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/NotificationsPage.tsx`
- `frontend/src/pages/OrganizationSettingsPage.tsx`
- `frontend/src/pages/AccessControlPage.tsx`
- `frontend/src/pages/SecuritySettingsPage.tsx`
- `frontend/src/pages/IdentitySyncPage.tsx`
- `frontend/src/pages/MemberAccessPage.tsx`
- `frontend/src/pages/RolesPage.tsx`
- `frontend/src/pages/AutomationRulesPage.tsx`
- `frontend/src/pages/RiskCenterPage.tsx`

近期重点服务层：

- `frontend/src/services/api.ts`
- `frontend/src/services/operations.ts`
- `frontend/src/services/accessControl.ts`
- `frontend/src/services/notificationCenter.ts`
- `frontend/src/services/securityCenter.ts`
- `frontend/src/services/identitySync.ts`
- `frontend/src/services/memberAccess.ts`
- `frontend/src/services/organizationCenter.ts`

## 9. 当前页面里哪些地方最值得继续做

如果是新会话接手，优先顺序建议如下。

### 优先级 A：系统治理线补齐

优先做这一组，因为它们已成站，但还可以明显提升：

1. `NotificationsPage`
2. `OrganizationSettingsPage`
3. `AccessControlPage`
4. `MemberAccessPage`
5. `SecuritySettingsPage`
6. `IdentitySyncPage`
7. `RolesPage`

建议做法：

- 补更多跨页联动按钮
- 补更完整的多账号统计卡片
- 补清晰的“最终结果 + 原因”展示
- 统一 `API / 混合 / 模拟` 标识文案
- 保持页面像后台产品，而不是调试页

### 优先级 B：协同类后台页补后台化

- `MembersPage`
- `AssignmentsPage`
- `CustomersPage`
- `ReviewsPage`
- `TicketsPage`

这些页很多已经能看，但完成度不够整齐。

### 优先级 C：系统扩展页

- `EvidenceCenterPage`
- `OperationsCenterPage`
- `ReportsPage`
- `AlertsPage`

这组可以继续提高信息密度与联动价值。

## 10. 当前已知问题 / 坑点

### 10.1 不要碰 H5

这是最高优先级边界之一。

不要修改：

- `frontend/src/pages/H5App.tsx`
- H5 对应样式和路径
- `/h5/*`

即使构建输出里有 H5 的 chunk，也不要因为看到它们就去改。

### 10.2 一些文件曾出现过编码显示异常

在终端里不带编码读取时，部分中文可能会乱码。

建议读取方式：

- PowerShell 里优先 `Get-Content -Encoding utf8`

不要因为终端乱码就误判源码有问题。当前构建是通过的。

### 10.3 后台并不是全量 API 化

不要误判为“所有系统治理页都已接真实接口”。

特别是：

- `NotificationsPage`
- `AccessControlPage`
- `SecuritySettingsPage`
- `IdentitySyncPage`
- `OrganizationSettingsPage`
- `MemberAccessPage`
- `RolesPage`

这些页大多是 hybrid/mock service 驱动，不是纯真实接口。

### 10.4 构建里仍有 chunk warning

`npm run build` 通过，但有这些 warning：

- `vendor-antd -> vendor-antd-rc -> vendor-antd` circular chunk
- `vendor-antd -> vendor-antd-icons -> vendor-antd` circular chunk
- 若干 chunk 体积超过 500kB

这不是 blocker，但如果后续有人做性能收口，可以从 `vite` 的 `manualChunks` 开始看。

### 10.5 当前目录不一定能直接当 git 仓库用

之前在 `E:\codex\WhatsApp` 根目录执行过 `git status --short`，返回：

- `fatal: not a git repository (or any of the parent directories): .git`

所以新会话如果要看版本状态，不要默认认为这里有可用 git worktree。

## 11. 最近已经验证过的命令

在 `frontend` 目录执行过：

### 11.1 构建验证

命令：

```powershell
npm run build
```

结果：

- 通过
- `tsc -b && vite build` 成功
- 仍有 AntD 相关 circular chunk warning
- 仍有大包 warning

### 11.2 测试验证

命令：

```powershell
npm run test -- src/services/operations.test.ts
```

结果：

- 通过
- `6/6` 用例通过

## 12. 新会话建议的启动步骤

新的会话进入后，建议按这个顺序：

1. 先读：
   - `Agents.md`
   - `docs/admin-frontend-session-handoff-2026-06-12.md`

2. 明确边界：
   - 只做后台
   - 不碰 H5
   - 不改后端主线

3. 读后台主入口：
   - `frontend/src/main.tsx`
   - `frontend/src/App.tsx`
   - `frontend/src/routes/consoleRoutes.ts`
   - `frontend/src/stores/appStore.ts`

4. 读当前治理页：
   - `NotificationsPage.tsx`
   - `OrganizationSettingsPage.tsx`
   - `AccessControlPage.tsx`
   - `SecuritySettingsPage.tsx`
   - `IdentitySyncPage.tsx`
   - `MemberAccessPage.tsx`
   - `RolesPage.tsx`

5. 开工前先确认：
   - 页面是不是走 `services`
   - 是 real / hybrid / mock 中哪一类
   - 是否带多账号 scope
   - 是否已支持 prefill 跳转

6. 每做完一轮，至少跑：

```powershell
npm run build
npm run test -- src/services/operations.test.ts
```

## 13. 新会话接手后推荐的首个任务

如果没有新的用户指令，建议直接从下面这条开始：

### 任务建议

继续补 `NotificationsPage + OrganizationSettingsPage + AccessControlPage`

### 推荐原因

- 这三页都已经可用，但还不是最完整的后台成品状态。
- 它们都属于系统治理线，能提高全站完成度。
- 它们不依赖重做后端。
- 可以继续用 hybrid/mock 方式向前推进，不阻塞主线。

### 具体方向

- `NotificationsPage`
  - 增加更多统计卡片
  - 增加到 `Roles / AccessControl / Security / Audit` 的联动
  - 增强渠道详情的结果与原因展示

- `OrganizationSettingsPage`
  - 清理还残留的英文数据源标签
  - 增加到 `Meta / Members / Sites / Security / Audit` 的联动
  - 增加组织治理维度的摘要指标

- `AccessControlPage`
  - 增加到 `Roles / Members / Security / Audit` 的联动
  - 补更明显的基线结果视图
  - 补更多后台会话和事件摘要

## 14. 当前不要做的事

- 不要改 H5
- 不要把后台页面重新换路由系统
- 不要把现有 `services` 接口边界推翻重写
- 不要为了“看起来统一”把 real/mock 差异隐藏掉
- 不要主动去大改后端
- 不要新增说明型运营文字

## 15. 一句话总结给新会话

当前后台前端已经完成了 AntD 化、蓝灰主题、多页路由和大部分后台页面骨架，核心实时页已能接真实接口，系统治理页仍以 hybrid/mock 为主；接手后应继续沿着“后台全站完成度提升”的方向推进，优先补 `通知 / 组织治理 / 访问控制 / 权限 / 安全 / 身份同步` 这一组，严格不碰 H5，不重做后端，不破坏现有 real/mock 分层。
