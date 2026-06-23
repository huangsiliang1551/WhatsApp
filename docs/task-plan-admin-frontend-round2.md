# 管理后台前端第二轮任务（内部优化轮）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **上一轮**: AF-001 ~ AF-017 全部完成 (17/17)

---

## 0. 当前状态

### 上一轮完成的能力

- Chat 人工接管 UI（按钮 + 恢复 + AI 三级开关）
- 模板管理 CRUD + 审核 + 发送 + 统计
- Meta 账户 Embedded Signup + AI 开关 + Token/Webhook 健康
- 系统治理线增强（Notifications / OrgSettings / AccessControl / Security / IdentitySync / MemberAccess / Roles）
- 协同页面增强（Assignments / Tickets / Members / Reviews）
- useMemberStatus 共享 hook 抽取
- customer drill-through 集成测试
- Chunk 优化

### 当前文件大小（仍需治理的巨石）

| 文件 | 行数 | 说明 |
|------|------|------|
| `pages/ChatPage.tsx` | 1464 | **最大后台页面，需拆分** |
| `pages/MetaAccountsPage.tsx` | 1115 | 已增强，暂不拆 |
| `pages/UsersPage.tsx` | 1020 | 暂不拆 |
| `pages/TemplatePage.tsx` | 995 | 已增强，暂不拆 |
| `pages/IdentitySyncPage.tsx` | 888 | 暂不拆 |
| `pages/ReviewsPage.tsx` | 875 | 暂不拆 |
| `pages/SettingsPage.tsx` | 861 | 暂不拆 |
| `pages/WhatsAppStatsPage.tsx` | 844 | 暂不拆 |
| `pages/CustomersPage.tsx` | 800 | 暂不拆 |
| `pages/AssignmentsPage.tsx` | 799 | 暂不拆 |
| `pages/DashboardPage.tsx` | 750 | **需增强** |
| `pages/OperationsCenterPage.tsx` | 693 | **需增强** |
| `pages/EvidenceCenterPage.tsx` | 683 | **需增强** |

### 当前测试覆盖

| 测试文件 | 行数 | 覆盖范围 |
|----------|------|---------|
| `pages/memberCustomerNavigation.test.tsx` | 551 | customer 跳转 |
| `services/h5.test.ts` | 717 | H5 旧服务 |
| `services/h5Member.test.ts` | 2731 | H5 会员服务 |
| `services/operations.test.ts` | 352 | member-status 聚合 |

**后台页面零测试**: ChatPage、TemplatePage、MetaAccountsPage、DashboardPage、UsersPage 等均无专门测试。

### 当前 hooks

| Hook | 行数 | 说明 |
|------|------|------|
| `hooks/useHealth.ts` | 16 | 健康检查 |
| `hooks/useMemberStatus.ts` | 116 | member-status 聚合（上轮新增） |

---

## 1. 执行编排

```
Phase 1（ChatPage 拆分，P0）:
  AF2-001 (拆 ConversationList)          ── frontend_agent
  AF2-002 (拆 MessagePanel)              ── frontend_agent     ← 依赖 AF2-001
  AF2-003 (拆 ChatSidebar + HandoverControls) ── frontend_agent ← 依赖 AF2-002
  AF2-004 (ChatPage 拆分验证)            ── testing_agent      ← 依赖 AF2-003

Phase 2（Dashboard + 运营中心增强，P1）:
  AF2-005 (DashboardPage 增强)           ── frontend_agent
  AF2-006 (OperationsCenterPage 增强)    ── frontend_agent

Phase 3（证据中心增强，P1）:
  AF2-007 (EvidenceCenterPage 增强)      ── frontend_agent

Phase 4（测试覆盖补齐，P0）:
  AF2-008 (ChatPage 测试)                ── testing_agent      ← 依赖 AF2-004
  AF2-009 (TemplatePage 测试)            ── testing_agent
  AF2-010 (MetaAccountsPage 测试)        ── testing_agent
  AF2-011 (DashboardPage 测试)           ── testing_agent      ← 依赖 AF2-005

Phase 5（最终验证）:
  AF2-012 (构建 + 全量测试)              ── testing_agent      ← 依赖所有
```

---

## 2. 任务详情

### AF2-001：ChatPage 拆分 — ConversationList

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 45 分钟

#### 目标

从 `ChatPage.tsx`（1464 行）中抽出左侧会话列表为独立组件。

#### 当前状态

ChatPage 包含：
- 左侧会话列表（搜索、筛选、排序、分页加载）
- 中间消息面板（消息流、输入框、发送）
- 右侧详情侧栏（客户信息、member-status、AI 状态、接管控制）
- 全局状态（当前选中会话、消息列表、加载状态）

#### 需要拆分的内容

**新建 `frontend/src/pages/admin-chat/ConversationList.tsx`**

包含：
- 会话列表渲染
- 搜索输入框
- 账号筛选下拉
- 状态筛选（全部/AI托管/人工接管/暂停）
- 会话卡片（最后消息预览、时间、未读数、模式标签）
- 分页/无限滚动加载
- 选中高亮

Props 接口：
```typescript
interface ConversationListProps {
  accountId: string | null;
  conversations: ConversationItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onSearch: (query: string) => void;
  onFilterMode: (mode: string | null) => void;
  loading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
}
```

#### 涉及文件

- **新增**: `frontend/src/pages/admin-chat/ConversationList.tsx`
- **新增**: `frontend/src/pages/admin-chat/index.ts`（导出汇总）
- **修改**: `frontend/src/pages/ChatPage.tsx`（减少 ~350 行）

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
```

#### 验收标准

1. ConversationList 作为独立组件可用
2. ChatPage 使用 ConversationList 替换内联列表代码
3. 会话列表功能不变（搜索、筛选、选中、模式标签）
4. ChatPage 减少约 350 行
5. 构建通过

#### 重试策略

- 最大重试: 3 次
- 失败回滚: 恢复 ChatPage.tsx 原始内容

---

### AF2-002：ChatPage 拆分 — MessagePanel

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: AF2-001
- **估计耗时**: 45 分钟

#### 需要拆分的内容

**新建 `frontend/src/pages/admin-chat/MessagePanel.tsx`**

包含：
- 消息流渲染（气泡式，区分用户/坐席/AI/系统）
- 消息时间戳
- 消息类型标识（文本/图片/模板/系统通知）
- 输入框区域（文本输入 + 发送按钮）
- 人工模式下的输入框（无 AI 辅助标记）
- AI 模式下的输入框（显示 AI 正在生成提示）
- 消息加载状态（骨架屏或 spinner）
- 滚动到底部按钮

Props 接口：
```typescript
interface MessagePanelProps {
  messages: MessageItem[];
  conversationMode: 'ai_managed' | 'human_managed' | 'paused';
  onSendMessage: (text: string, attachments?: File[]) => void;
  loading: boolean;
  aiGenerating: boolean;
  currentAgentName: string | null;
}
```

#### 涉及文件

- **新增**: `frontend/src/pages/admin-chat/MessagePanel.tsx`
- **修改**: `frontend/src/pages/ChatPage.tsx`（减少 ~400 行）

#### 验收标准

1. MessagePanel 作为独立组件可用
2. 消息渲染功能不变
3. 输入框在 AI/人工模式下有不同视觉提示
4. ChatPage 再减约 400 行
5. 构建通过

---

### AF2-003：ChatPage 拆分 — ChatSidebar + HandoverControls

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: AF2-002
- **估计耗时**: 45 分钟

#### 需要拆分的内容

**1. 新建 `frontend/src/pages/admin-chat/ChatSidebar.tsx`**

包含：
- 客户信息卡片（member-status 集成，复用 useMemberStatus hook）
- 会话元数据（创建时间、最后活跃、消息数）
- AI 状态展示（当前模式、最后 AI 回复原因、置信度）
- 标签（account_id、waba_id、phone_number_id）

**2. 新建 `frontend/src/pages/admin-chat/HandoverControls.tsx`**

包含：
- 接管按钮（触发 AI→人工）
- 恢复 AI 按钮（触发人工→AI）
- AI 会话级开关
- 接管历史列表
- 坐席分配选择器
- Popconfirm 确认对话框

Props 接口：
```typescript
interface HandoverControlsProps {
  conversationId: string;
  currentMode: 'ai_managed' | 'human_managed' | 'paused';
  assignedAgent: string | null;
  onHandover: () => void;
  onRestoreAI: () => void;
  onAssignAgent: (agentId: string) => void;
  onToggleAiSwitch: (enabled: boolean) => void;
  aiSwitchEnabled: boolean;
  globalAiEnabled: boolean;
  handoverLogs: HandoverLogItem[];
}
```

#### 涉及文件

- **新增**: `frontend/src/pages/admin-chat/ChatSidebar.tsx`
- **新增**: `frontend/src/pages/admin-chat/HandoverControls.tsx`
- **修改**: `frontend/src/pages/admin-chat/index.ts`（更新导出）
- **修改**: `frontend/src/pages/ChatPage.tsx`（减少 ~400 行）

#### ChatPage 最终目标

拆分后 ChatPage.tsx 应 < 400 行，仅保留：
- 页面级状态管理（当前会话 ID、消息列表、加载状态）
- API 调用逻辑（获取会话、获取消息、发送消息、接管/恢复）
- 三个子组件的布局编排（ConversationList + MessagePanel + ChatSidebar/HandoverControls）
- 全局布局（三栏布局、响应式折叠）

#### 验收标准

1. ChatSidebar 使用 useMemberStatus hook 展示客户信息
2. HandoverControls 包含接管/恢复/AI 开关/历史
3. ChatPage < 400 行
4. 所有功能不变
5. 构建通过

---

### AF2-004：ChatPage 拆分验证

- **角色**: testing_agent
- **前置依赖**: AF2-003
- **估计耗时**: 15 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
npm run test -- src/services/operations.test.ts
npm run test -- src/pages/memberCustomerNavigation.test.tsx
```

#### 验收标准

1. ChatPage.tsx < 400 行
2. `admin-chat/` 目录有 4 个组件 + 1 个 index
3. 构建通过
4. 现有测试不退化

---

### AF2-005：DashboardPage 增强

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 无（可与 Phase 1 并行）
- **估计耗时**: 45 分钟

#### 当前状态

`DashboardPage.tsx`（750 行）已有基础统计卡片和概览。需要增强为实时运营仪表盘。

#### 需要增加的面板

**1. 会话模式分布（饼图或环形图）**
- AI 托管会话数
- 人工接管会话数
- 暂停会话数
- 数据来源：`/api/metrics/summary` 或 mock

**2. AI 回复成功率趋势（时间序列折线图）**
- X 轴：时间（最近 24 小时）
- Y 轴：成功率百分比
- 标注降级率和禁用率
- 数据来源：`business_ai_replies_total` 指标或 mock

**3. 队列深度实时指示（Gauge 或数值卡片）**
- 当前排队任务数
- 处理中任务数
- 失败任务数
- 数据来源：`queue_jobs_current` 指标或 mock

**4. 消息流量趋势（面积图）**
- 入站消息速率
- 出站消息速率
- 模板发送速率
- 数据来源：metrics summary 或 mock

**5. 模板发送成功率（数值卡片 + 趋势箭头）**
- 今日发送量
- 成功率
- 失败原因 Top3

#### 涉及文件

- **修改**: `frontend/src/pages/DashboardPage.tsx`

#### 验收标准

1. Dashboard 有 5 个以上可视化面板
2. 数据来源优先走真实 API，不可用时 mock
3. 面板布局合理（grid 或 flex）
4. 蓝灰主题一致
5. 构建通过

---

### AF2-006：OperationsCenterPage 增强

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 当前状态

`OperationsCenterPage.tsx`（693 行）仍是 mock 为主。

#### 需要增强

1. **运营数据概览**
   - 任务提交统计（待审核 / 已通过 / 已拒绝）
   - 工单统计（待处理 / 处理中 / 已解决）
   - 提现申请统计（待审核 / 已处理）

2. **跨页面联动增强**
   - 从运营中心直接跳转到 TasksPage（带 prefill 待审核筛选）
   - 从运营中心跳转到 TicketsPage（带 prefill 待处理筛选）
   - 从运营中心跳转到 ReviewsPage

3. **时间维度切换**
   - 今日 / 本周 / 本月 切换
   - 各统计卡片随时间范围变化

4. **运营告警摘要**
   - 显示最近的系统告警（如果有 /api/metrics/summary）
   - 异常指标高亮

#### 涉及文件

- **修改**: `frontend/src/pages/OperationsCenterPage.tsx`

#### 验收标准

1. 运营数据概览有 3 个以上维度
2. 跨页面跳转可用（带 prefill）
3. 时间维度切换功能正常
4. 构建通过

---

### AF2-007：EvidenceCenterPage 增强

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 当前状态

`EvidenceCenterPage.tsx`（683 行）已有基础结构。

#### 需要增强

1. **证据列表增强**
   - 多条件筛选（账号、时间范围、类型、状态）
   - 证据预览（图片缩略图、文本摘要）
   - 批量选择 + 批量操作

2. **证据详情面板**
   - 全屏查看证据
   - 关联的会话/任务/工单链接
   - 操作历史

3. **导出功能**
   - 选择证据 → 打包下载
   - 导出清单（CSV 格式）

#### 涉及文件

- **修改**: `frontend/src/pages/EvidenceCenterPage.tsx`

#### 验收标准

1. 筛选功能可用
2. 证据详情可查看
3. 导出功能可触发（mock 实现即可）
4. 构建通过

---

### AF2-008：ChatPage 行为测试

- **角色**: testing_agent
- **优先级**: P0
- **前置依赖**: AF2-004
- **估计耗时**: 30 分钟

#### 需要新增的测试

**新建 `frontend/src/pages/admin-chat.test.tsx`**

测试场景：

1. **ConversationList 渲染**
   - 传入会话列表 → 正确渲染卡片数量
   - 选中会话 → 高亮样式
   - 模式标签显示（ai_managed / human_managed）
   - 搜索输入 → 触发 onSearch

2. **MessagePanel 渲染**
   - 传入消息列表 → 正确渲染气泡
   - AI 模式 → 输入框无特殊标记
   - 人工模式 → 输入框有人工标记
   - 发送消息 → 触发 onSendMessage

3. **HandoverControls 交互**
   - AI 模式下显示"接管"按钮
   - 人工模式下显示"恢复 AI"按钮
   - 点击接管 → Popconfirm 弹出
   - 确认后触发 onHandover
   - AI 开关 toggle → 触发 onToggleAiSwitch

4. **ChatSidebar member-status**
   - 传入 customer 数据 → 显示认证状态
   - 传入 WhatsApp 绑定状态 → 显示对应图标

#### 测试工具

- `@testing-library/react`（项目已有）
- `vitest`（项目已配置）
- mock services（手动 mock API 返回值）

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run test -- src/pages/admin-chat.test.tsx
```

#### 验收标准

1. 测试文件存在且语法正确
2. 至少 10 个测试用例
3. 全部通过
4. 构建通过

---

### AF2-009：TemplatePage 行为测试

- **角色**: testing_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 20 分钟

#### 需要新增的测试

**新建 `frontend/src/pages/templatePage.test.tsx`**

测试场景：

1. 模板列表渲染（传入数据 → 表格行数正确）
2. 搜索过滤功能
3. 状态标签显示（草稿/审核中/已通过/已拒绝）
4. 创建模板按钮可点击
5. 多账号筛选下拉可用

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run test -- src/pages/templatePage.test.tsx
```

#### 验收标准

1. 至少 5 个测试用例
2. 全部通过

---

### AF2-010：MetaAccountsPage 行为测试

- **角色**: testing_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 20 分钟

#### 需要新增的测试

**新建 `frontend/src/pages/metaAccountsPage.test.tsx`**

测试场景：

1. 账户列表渲染
2. WABA 详情展示（phone numbers、webhook 状态）
3. AI 开关 toggle 显示
4. "接入新账户"按钮存在且可点击
5. Token 健康状态展示
6. Embedded Signup Tab 可切换

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run test -- src/pages/metaAccountsPage.test.tsx
```

#### 验收标准

1. 至少 6 个测试用例
2. 全部通过

---

### AF2-011：DashboardPage 行为测试

- **角色**: testing_agent
- **优先级**: P0
- **前置依赖**: AF2-005
- **估计耗时**: 20 分钟

#### 需要新增的测试

**新建 `frontend/src/pages/dashboardPage.test.tsx`**

测试场景：

1. Dashboard 渲染不崩溃
2. 统计卡片数量 >= 5
3. 会话模式分布面板存在
4. AI 成功率面板存在
5. 队列深度面板存在

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run test -- src/pages/dashboardPage.test.tsx
```

#### 验收标准

1. 至少 5 个测试用例
2. 全部通过

---

### AF2-012：最终验证

- **角色**: testing_agent
- **前置依赖**: 所有 AF2 任务完成
- **估计耗时**: 15 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend

# 构建
npm run build

# 全部测试
npm run test -- src/services/operations.test.ts
npm run test -- src/pages/memberCustomerNavigation.test.tsx
npm run test -- src/pages/admin-chat.test.tsx
npm run test -- src/pages/templatePage.test.tsx
npm run test -- src/pages/metaAccountsPage.test.tsx
npm run test -- src/pages/dashboardPage.test.tsx
```

#### 验收标准

| 项目 | 预期 |
|------|------|
| npm run build | 通过 |
| operations.test.ts | 6/6 通过 |
| memberCustomerNavigation.test.tsx | 不退化 |
| admin-chat.test.tsx | 10+ 通过 |
| templatePage.test.tsx | 5+ 通过 |
| metaAccountsPage.test.tsx | 6+ 通过 |
| dashboardPage.test.tsx | 5+ 通过 |
| ChatPage.tsx 行数 | < 400 |
| admin-chat/ 组件数 | 4 个 + index.ts |
| 新增测试文件数 | 4 个 |

---

## 3. 拆分后目标文件结构

```
frontend/src/pages/
├── ChatPage.tsx                    # < 400 行：状态管理 + API + 布局编排
├── admin-chat/                     # 新增目录
│   ├── index.ts                    # 导出汇总
│   ├── ConversationList.tsx        # 会话列表（~300 行）
│   ├── MessagePanel.tsx            # 消息面板（~350 行）
│   ├── ChatSidebar.tsx             # 右侧详情（~250 行）
│   └── HandoverControls.tsx        # 接管控制（~200 行）

frontend/src/pages/                 # 新增测试
├── admin-chat.test.tsx             # Chat 拆分后组件测试
├── templatePage.test.tsx           # 模板页测试
├── metaAccountsPage.test.tsx       # Meta 账户页测试
├── dashboardPage.test.tsx          # Dashboard 测试
```

---

## 4. 全局约束

1. **严格不碰 H5**: 不修改 h5-member/ 目录下任何文件
2. **不修改后端**: 不改 app/ 目录
3. **保持 real/mock 分层**: services 层清晰
4. **useMemberStatus hook 复用**: ChatSidebar 必须使用已有 hook
5. **不新增说明型文案**
6. **保持 prefill 跳转机制**
7. 进度文件: `.codex-run/progress/AF2-XXX.json`
8. 单任务最大执行 60 分钟
9. 失败自动回滚 + 重试最多 3 次
10. 每次改动后 `npm run build` 必须通过
11. 一次性执行全部任务，不中途暂停确认
