# 管理后台前端任务清单（Admin Frontend Agent 专用）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**

---

## 0. 当前管理后台前端状态

### 代码规模

| 类型 | 文件数 | 说明 |
|------|--------|------|
| 页面 (pages/) | 42 | 包含 H5App.tsx (3626 行，不碰) |
| 服务 (services/) | 17 | api.ts (2755行)、operations.ts (1487行) 最大 |
| 组件 (components/) | 3 | AdminRoutePageShell、AdminDataSourceLegend、Panel |
| 路由 (routes/) | 2 | consoleRoutes.ts、adminUrlState.ts |
| 状态 (stores/) | 1 | appStore.ts |
| 测试 | 4 | operations.test.ts、h5.test.ts、h5Member.test.ts、memberCustomerNavigation.test.tsx |

### 已完成

- AntD + ProLayout + ProTable 迁移
- 蓝灰主题统一
- 后台导航、路由、侧边栏分组
- H5 快捷入口从后台壳去掉
- 构建通过（有 chunk warning）
- 核心页（Dashboard、Chat、MetaAccounts、Template、Settings、Monitoring、WhatsAppStats、Audit）已接真实接口
- customer/member-status 聚合服务 (operations.ts) 已建
- CustomersPage 的 prefill 跳转机制已建并被测试锁定
- 多页面（Users、Chat、Assignments、OperationsCenter、Tasks、Tickets、Reviews）已部分接入 member-status

### 真实接口 / hybrid / mock 状态

**已接真实接口（16 页）**:
Dashboard、Chat、MetaAccounts、Template、Settings、Monitoring、WhatsAppStats、Audit、Integrations、ApiWebhooks、ProviderEvents、SystemLogs、Users、Sites、Tags、AudienceRules、Tasks

**仍为 hybrid/mock（19 页）**:
Notifications、OrganizationSettings、AccessControl、SecuritySettings、IdentitySync、MemberAccess、Roles、EvidenceCenter、OperationsCenter、Ecommerce、AutomationRules、RiskCenter、Assignments、Customers、Members、Reviews、Tickets、Reports、Alerts

### 已知约束（不要违反）

1. **不碰 H5**: 不修改 H5App.tsx、H5 路由、H5 样式
2. **不修改后端**: 不改 app/db/、app/providers/、alembic/
3. **保持 real/mock 分层**: 不把 mock 装成 API
4. **保留 prefill 跳转机制**: openCustomersPage + customersPagePrefill + nonce 已被测试锁定
5. **member-status 统一走 operations.ts**: 不在页面里散着调 verification/binding API
6. **不新增说明型运营文案**: 不写"等待后端"、"原型"等提示
7. **构建验证**: 每次改动后 `npm run build` 必须通过

---

## 1. 执行编排

```
Phase 1 - Chat 工作台完善（P0，配合后端人工接管）:
  AF-001 (Chat 接管 UI)             ── frontend_agent
  AF-002 (Chat 测试)                ── testing_agent         ← 依赖 AF-001

Phase 2 - Customer drill-through 集成（P1）:
  AF-003 (集成测试)                  ── testing_agent
  AF-004 (共享 member-status hook)   ── frontend_agent       ← 依赖 AF-003

Phase 3 - 模板管理页完善（P0）:
  AF-005 (模板管理增强)              ── frontend_agent
  AF-006 (模板测试)                  ── testing_agent         ← 依赖 AF-005

Phase 4 - Meta 账户页完善（P0）:
  AF-007 (Meta 账户增强)             ── frontend_agent
  AF-008 (Meta 测试)                 ── testing_agent         ← 依赖 AF-007

Phase 5 - 系统治理线补齐（P2）:
  AF-009 (Notifications 增强)        ── frontend_agent
  AF-010 (OrgSettings 增强)          ── frontend_agent
  AF-011 (AccessControl 增强)        ── frontend_agent
  AF-012 (其他治理页补齐)            ── frontend_agent

Phase 6 - 协同类页面补齐（P1）:
  AF-013 (Assignments 增强)          ── frontend_agent
  AF-014 (Tickets 增强)              ── frontend_agent
  AF-015 (Members/Reviews 增强)      ── frontend_agent

Phase 7 - 构建与性能（P2）:
  AF-016 (Build chunk 优化)          ── frontend_agent
  AF-017 (最终验证)                  ── testing_agent         ← 依赖所有
```

---

## 2. 任务详情

### AF-001：Chat 工作台 - 人工接管 UI

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: 后端 BE-001/BE-002 完成（接管 API 可用）
- **估计耗时**: 60 分钟

#### 当前状态

`frontend/src/pages/ChatPage.tsx` (1422 行) 已有会话列表、消息面板、AI 状态展示。需要增加人工接管相关 UI。

#### 需要增加的功能

1. **会话接管控制**
   - 会话详情区增加「接管」按钮
   - 点击接管 → 调用 `POST /api/conversations/{id}/handover`
   - 接管后消息面板切换为人工输入模式
   - 显示当前接管坐席信息

2. **AI/人工状态指示**
   - 会话列表显示当前模式标签（AI托管/人工接管/暂停）
   - 接管状态变化有视觉提示

3. **恢复 AI 控制**
   - 接管状态下显示「恢复 AI」按钮
   - 点击 → 调用 `POST /api/conversations/{id}/restore-ai`
   - 恢复后消息面板切回 AI 模式

4. **接管历史**
   - 会话详情区可查看接管日志
   - 显示时间、坐席、触发原因

5. **AI 开关三级控制 UI**
   - 全局开关 → 系统设置页（已有）
   - 账号级开关 → Meta 账户详情页
   - 会话级开关 → Chat 会话详情区

#### 涉及文件

- **修改**: `frontend/src/pages/ChatPage.tsx`
- **修改**: `frontend/src/services/api.ts`（接管 API 封装）
- **可能新增**: `frontend/src/services/handover.ts`（如果接管 API 过多）

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
npm run test -- src/services/operations.test.ts
```

#### 验收标准

1. 会话列表显示模式标签
2. 接管按钮可点击并调用 API
3. 接管后消息面板切换为人工模式
4. 恢复 AI 按钮可点击
5. AI 开关三级控制在 UI 上可见
6. 构建通过
7. 现有测试通过

#### 重试策略

- 最大重试: 3 次
- 失败回滚: git checkout ChatPage.tsx、api.ts

---

### AF-002：Chat 接管测试

- **角色**: testing_agent
- **前置依赖**: AF-001
- **估计耗时**: 20 分钟

#### 测试场景

1. 会话列表正确显示模式标签
2. 接管按钮触发正确的 API 调用
3. 恢复 AI 按钮触发正确的 API 调用
4. 不覆盖现有 ChatPage 功能

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
```

---

### AF-003：Customer drill-through 集成测试

- **角色**: testing_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 当前状态

已有 `memberCustomerNavigation.test.tsx` (551 行) 测试基础。需要更高层级的集成测试。

#### 需要新增的测试

从 `App.tsx` 或更接近真实路由的层面验证：

1. source page（如 UsersPage）触发 jump → CustomersPage 成为 active page
2. prefill 被消费（account_id、query、selected_profile_id 恢复）
3. detail/member status 被加载
4. nonce 防重复消费

#### 注意

- 不要过度锁定 AntD DOM 结构
- 不要过度锁 URL query 顺序
- 重点锁业务行为

#### 涉及文件

- **新增**: `frontend/src/pages/customerDrillThrough.test.tsx`（或扩展现有测试）

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run test -- src/pages/customerDrillThrough.test.tsx
npm run test -- src/pages/memberCustomerNavigation.test.tsx
npm run build
```

#### 验收标准

1. 集成测试通过
2. 现有 memberCustomerNavigation.test.tsx 不退化
3. 构建通过

---

### AF-004：抽共享 customer/member-status hook

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: AF-003
- **估计耗时**: 45 分钟

#### 问题

Chat / Assignments / Customers / Users / Tickets 都有重复的 member status 载入逻辑：
- loading / error / requestIdRef / latestVerification / latestBinding
- 每个页面独立实现相同的数据获取和状态管理

#### 需要做的

1. **抽取共享 hook**
   - 新增 `frontend/src/hooks/useMemberStatus.ts`
   - 封装 member status 数据获取
   - 封装 loading/error 状态
   - 封装 latestVerification / latestBinding 计算

2. **替换重复代码**
   - 在 ChatPage、AssignmentsPage、CustomersPage、UsersPage、TicketsPage 中替换
   - 保持入口不变
   - 聚合仍经 operations.ts
   - 跳转仍经 appStore.ts

#### 涉及文件

- **新增**: `frontend/src/hooks/useMemberStatus.ts`
- **修改**: `frontend/src/pages/ChatPage.tsx`
- **修改**: `frontend/src/pages/AssignmentsPage.tsx`
- **修改**: `frontend/src/pages/CustomersPage.tsx`
- **修改**: `frontend/src/pages/UsersPage.tsx`
- **修改**: `frontend/src/pages/TicketsPage.tsx`

#### 验收标准

1. 共享 hook 封装完成
2. 至少 3 个页面使用共享 hook
3. 功能不变
4. 现有测试不退化
5. 构建通过

---

### AF-005：模板管理页增强

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: 后端 BE-004/BE-005 完成
- **估计耗时**: 45 分钟

#### 当前状态

`frontend/src/pages/TemplatePage.tsx` (995 行) 已接真实接口。需要增强：

1. **模板创建/编辑表单**
   - 模板名称、语言、分类
   - 内容编辑器（支持变量占位符高亮）
   - 预览功能
   - 变量列表自动生成

2. **模板审核状态展示**
   - 状态标签：草稿 / 审核中 / 已通过 / 已拒绝
   - 审核原因展示
   - 拒绝后可重新编辑提交

3. **模板发送**
   - 选择模板 → 选择收件人 → 填写变量 → 发送
   - 发送结果反馈

4. **模板统计**
   - 发送量、成功率、失败率
   - 按时间范围筛选

#### 涉及文件

- **修改**: `frontend/src/pages/TemplatePage.tsx`
- **修改**: `frontend/src/services/api.ts`

#### 验收标准

1. 模板 CRUD UI 完整
2. 审核状态可见
3. 模板发送流程可用
4. 统计数据展示
5. 构建通过

---

### AF-006：模板页测试

- **角色**: testing_agent
- **前置依赖**: AF-005
- **估计耗时**: 15 分钟

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
```

---

### AF-007：Meta 账户页增强

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: 后端 BE-017 ~ BE-019 完成
- **估计耗时**: 45 分钟

#### 当前状态

`frontend/src/pages/MetaAccountsPage.tsx` (1115 行) 已接真实接口。需要增强：

1. **Embedded Signup 入口**
   - "接入新账户"按钮 → 发起 Embedded Signup 流程
   - 进度展示：创建会话 → Meta 授权 → 完成

2. **WABA 详情**
   - 展示 WABA 下的 Phone Numbers 列表
   - Webhook 订阅状态
   - 每个号码的消息统计

3. **账户健康状态**
   - 连接状态（正常/异常/过期）
   - Token 有效期
   - 质量评分展示

4. **AI 开关控制**
   - 账户级 AI 开关 toggle
   - 当前状态展示（受全局开关约束提示）

#### 涉及文件

- **修改**: `frontend/src/pages/MetaAccountsPage.tsx`
- **修改**: `frontend/src/services/api.ts`

#### 验收标准

1. Embedded Signup 入口可用
2. WABA 详情展示完整
3. 账户健康状态可见
4. AI 开关可控
5. 构建通过

---

### AF-008：Meta 账户测试

- **角色**: testing_agent
- **前置依赖**: AF-007
- **估计耗时**: 15 分钟

---

### AF-009：NotificationsPage 增强

- **角色**: frontend_agent
- **优先级**: P2
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 当前状态

`frontend/src/pages/NotificationsPage.tsx` (588 行) 为 hybrid/mock。

#### 需要增强

1. 增加更多统计卡片
2. 增加到 Roles / AccessControl / Security / Audit 的联动
3. 增强渠道详情的结果与原因展示
4. 统一 API/混合/模拟 标识

#### 涉及文件

- **修改**: `frontend/src/pages/NotificationsPage.tsx`
- **修改**: `frontend/src/services/notificationCenter.ts`

#### 验收标准

1. 统计卡片增加
2. 跨页联动按钮可用
3. 构建通过

---

### AF-010：OrganizationSettingsPage 增强

- **角色**: frontend_agent
- **优先级**: P2
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 需要增强

1. 清理残留英文数据源标签
2. 增加到 Meta / Members / Sites / Security / Audit 的联动
3. 增加组织治理维度摘要指标

#### 涉及文件

- **修改**: `frontend/src/pages/OrganizationSettingsPage.tsx`
- **修改**: `frontend/src/services/organizationCenter.ts`

---

### AF-011：AccessControlPage 增强

- **角色**: frontend_agent
- **优先级**: P2
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 需要增强

1. 增加到 Roles / Members / Security / Audit 的联动
2. 补更明显的基线结果视图
3. 补更多后台会话和事件摘要

#### 涉及文件

- **修改**: `frontend/src/pages/AccessControlPage.tsx`
- **修改**: `frontend/src/services/accessControl.ts`

---

### AF-012：其他治理页补齐

- **角色**: frontend_agent
- **优先级**: P2
- **前置依赖**: AF-009, AF-010, AF-011
- **估计耗时**: 60 分钟

#### 范围

- SecuritySettingsPage
- IdentitySyncPage
- MemberAccessPage
- RolesPage

#### 每页通用增强

1. 更多跨页联动按钮
2. 更完整的多账号统计卡片
3. 清晰的"最终结果 + 原因"展示
4. 统一数据源标识

#### 涉及文件

- `frontend/src/pages/SecuritySettingsPage.tsx`
- `frontend/src/pages/IdentitySyncPage.tsx`
- `frontend/src/pages/MemberAccessPage.tsx`
- `frontend/src/pages/RolesPage.tsx`
- `frontend/src/services/securityCenter.ts`
- `frontend/src/services/identitySync.ts`
- `frontend/src/services/memberAccess.ts`

---

### AF-013：AssignmentsPage 增强

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 后端 BE-001/BE-002 完成
- **估计耗时**: 30 分钟

#### 需要增强

1. 会话分配操作 UI（分配给坐席、取消分配）
2. 坐席在线状态展示
3. 分配统计（待分配、已分配、超时）
4. 与 ChatPage 的联动

#### 涉及文件

- **修改**: `frontend/src/pages/AssignmentsPage.tsx`

---

### AF-014：TicketsPage 增强

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 需要增强

1. 工单详情完善（状态流转、回复历史）
2. 工单与会话的关联展示
3. 工单分配与处理
4. 工单统计

#### 涉及文件

- **修改**: `frontend/src/pages/TicketsPage.tsx`

---

### AF-015：Members/Reviews 增强

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### MembersPage 增强

1. 会员列表展示
2. 会员详情（认证状态、WhatsApp 绑定、钱包摘要）
3. 与 CustomersPage 联动

#### ReviewsPage 增强

1. 审核队列展示
2. 审核操作（通过/拒绝 + 原因）
3. 审核历史

#### 涉及文件

- `frontend/src/pages/MembersPage.tsx`
- `frontend/src/pages/ReviewsPage.tsx`

---

### AF-016：Build chunk 优化

- **角色**: frontend_agent
- **优先级**: P2
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 当前问题

构建有 circular chunk warning：
- `vendor-antd -> vendor-antd-rc -> vendor-antd`
- `vendor-antd -> vendor-antd-icons -> vendor-antd`
- 若干 chunk 超过 500kB

#### 需要做的

1. 优化 `vite.config.ts` 中的 `manualChunks` 配置
2. 拆分 AntD 相关 chunk
3. 减少单个 chunk 体积

#### 涉及文件

- **修改**: `frontend/vite.config.ts`

#### 验收标准

1. circular chunk warning 消除或减少
2. 单个 chunk < 500kB（尽量）
3. 构建通过
4. 页面功能不受影响

---

### AF-017：最终验证

- **角色**: testing_agent
- **前置依赖**: 所有 AF 任务完成
- **估计耗时**: 20 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
npm run test -- src/services/operations.test.ts
npm run test -- src/pages/memberCustomerNavigation.test.tsx
```

#### 验收标准

1. `npm run build` 通过
2. `operations.test.ts` 全部通过
3. `memberCustomerNavigation.test.tsx` 全部通过
4. 无新增 console error
5. 所有页面可浏览

---

## 3. 全局约束

1. **严格不碰 H5**: 不修改 H5App.tsx、H5 路由、H5 样式
2. **不修改后端**: 不改 app/ 目录
3. **保持 real/mock 分层**: services 层清晰区分
4. **页面组件不直接写 fetch**: 统一走 services
5. **所有数据默认带 account_id 作用域**
6. **不新增说明型运营文案**
7. 进度文件: `.codex-run/progress/AF-XXX.json`
8. 单任务最大执行 60 分钟
9. 失败自动回滚 + 重试最多 3 次
10. 每次改动后 `npm run build` 必须通过
