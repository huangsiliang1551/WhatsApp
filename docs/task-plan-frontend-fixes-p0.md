# 管理后台前端修复 + P0 功能补全（FX-001 ~ FX-013）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 修复截图发现的视觉问题 + 补全 P0 级功能缺失

---

## Part A：视觉修复（5 项）

### FX-001：会话工作台快捷工具栏文字截断

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 问题

截图显示 QuickToolbar 按钮文字被截断：
- "发送模板" 显示为 "发送g板"
- "发送媒体" 显示为 "发送y体"
- "模拟入站" 显示为 "g拟入q"

#### 根因

按钮 `min-width` 不足或 `overflow: hidden` 导致中文被截断。

#### 修复方案

修改 `frontend/src/pages/admin-chat/QuickToolbar.tsx`：

1. 每个按钮设置 `min-width: 90px`
2. 移除 `overflow: hidden` 或改为 `overflow: visible`
3. 确认按钮间距 `gap: 8px`

#### 验证

- 三个按钮完整显示："发送模板"、"发送媒体"、"模拟入站"
- 不同分辨率下不截断
- `npm run build` 通过

---

### FX-002：模板消息页缺少"创建模板"按钮

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 问题

截图显示 TemplatePage 标题行右侧只有"统计"和"刷新"按钮，缺少核心操作入口。

#### 修复方案

修改 `frontend/src/pages/TemplatePage.tsx`：

在 PageShell 的 `actions` prop 中添加：

```tsx
<Space>
  <Button type="primary" onClick={() => openCreateModal()}>
    创建模板
  </Button>
  <Button onClick={() => void syncTemplates()}>
    同步 Meta
  </Button>
</Space>
```

#### 验证

- "创建模板"按钮显示在标题行右侧
- 点击弹出创建表单
- "同步 Meta"按钮可用
- `npm run build` 通过

---

### FX-003：Meta 账户页缺少"接入新账户"按钮

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 问题

截图显示 MetaAccountsPage 标题行无操作按钮。

#### 修复方案

修改 `frontend/src/pages/MetaAccountsPage.tsx`：

在 PageShell 的 `actions` prop 中添加：

```tsx
<Space>
  <Button type="primary" onClick={() => setActiveTab("embedded_signup")}>
    接入新账户
  </Button>
  <Button onClick={() => openManualCreateModal()}>
    手动添加
  </Button>
</Space>
```

#### 验证

- "接入新账户"按钮显示
- 点击切换到 Embedded Signup Tab
- "手动添加"按钮弹出创建表单
- `npm run build` 通过

---

### FX-004：后台用户页缺少"创建用户"按钮

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 问题

截图显示 UsersPage 只有表格和"删除"操作，缺少创建入口。

#### 修复方案

修改 `frontend/src/pages/UsersPage.tsx`：

1. 在 PageShell 的 `actions` 中添加 `[创建用户]` 按钮
2. 点击弹出 Modal 创建表单（复用现有 createPlatformUser API）
3. 表格操作列增加"编辑"按钮（修改 display_name / language）

#### 验证

- "创建用户"按钮显示
- 创建 Modal 可弹出并提交
- 行内"编辑"操作可用
- `npm run build` 通过

---

### FX-005：页面标题标签清理

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 问题

每个页面标题旁都有"进行中"+"API/混合"标签，无实际操作价值，占用视觉空间。

#### 修复方案

修改 `frontend/src/components/PageShell.tsx`：

1. **移除** `dataBadges` 相关的 Tag 渲染（"进行中"/"API"/"混合"等）
2. **保留** PageShell 的 `title` + `subtitle` + `actions` + `stats`
3. 如果原页面传入了 `dataBadges`，忽略即可（不报错）

同时检查各页面调用 PageShell 时传入的多余 prop，清理无用代码。

#### 验证

- 所有页面标题行不再显示"进行中"/"API"/"混合"标签
- 标题 + 副标题 + 操作按钮仍正常
- `npm run build` 通过

---

## Part B：P0 功能补全（8 项）

### FX-006：快捷回复/话术库

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

人工坐席在会话工作台可一键插入预设回复，减少重复输入。

#### 前端实现

**新增 `frontend/src/pages/admin-chat/CannedResponses.tsx`**

```typescript
interface CannedResponse {
  id: string;
  title: string;        // 如 "订单查询回复"
  content: string;      // 如 "您好，您的订单 {{order_id}} 目前状态为 {{status}}..."
  category: string;     // 如 "物流" / "退款" / "问候"
  variables: string[];  // 如 ["order_id", "status"]
}

interface CannedResponsesProps {
  onSelect: (text: string) => void;  // 插入到输入框
}
```

**UI 设计**:
- QuickToolbar 增加第 4 个按钮: "💬 快捷回复"
- 点击弹出 Popover，显示分类 + 话术列表
- 点击话术 → 弹出变量填写框（如有变量）→ 确认后插入输入框
- 话术数据: 先存 localStorage（后端 API 就绪后切换）

**初始话术数据（内置 10 条）**:

| 分类 | 标题 | 内容 |
|------|------|------|
| 问候 | 标准问候 | 您好！我是客服 {{agent_name}}，请问有什么可以帮您？ |
| 问候 | 欢迎回来 | 您好 {{customer_name}}，欢迎回来！请问还有什么需要帮助的吗？ |
| 物流 | 订单查询 | 您的订单 {{order_id}} 目前状态为 {{status}}，预计 {{eta}} 送达。 |
| 物流 | 物流延迟 | 非常抱歉，您的订单配送有所延迟，我们正在催促物流方加快处理。 |
| 退款 | 退款已处理 | 您的退款申请已通过，预计 {{days}} 个工作日内退回到您的账户。 |
| 退款 | 退款待审核 | 您的退款申请正在审核中，我们会在 24 小时内给您回复。 |
| 结束 | 结束语 | 感谢您的咨询，如有其他问题随时联系我们。祝您生活愉快！ |
| 转接 | 转人工 | 您的问题需要专业团队处理，我现在为您转接人工客服。 |
| 转接 | 转接完成 | 您好，我已经接手您的会话，请问具体遇到了什么问题？ |
| 等待 | 请等待 | 正在为您查询，请稍等片刻。 |

#### 验收标准

1. QuickToolbar 有"快捷回复"按钮
2. Popover 显示分类 + 话术列表
3. 点击话术 → 变量替换 → 插入输入框
4. localStorage 持久化
5. `npm run build` 通过

---

### FX-007：会话内部备注

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

坐席可在会话中添加仅内部可见的备注（客户不可见），用于交接说明或记录。

#### 前端实现

**修改 `frontend/src/pages/admin-chat/MessagePanel.tsx`**:

1. 输入区域上方增加 Tab 切换: `[消息] [备注]`
2. 备注模式: 输入框背景变黄，placeholder "输入内部备注（仅团队可见）"
3. 消息流中备注显示为: 黄色背景条 + 🔒 图标 + "内部备注: xxx"
4. 备注区分: `message_type === "internal_note"`

**修改 `frontend/src/pages/admin-chat/HistoryTab.tsx`**:

- 时间线中增加备注事件显示

#### 后端依赖

后端需提供 `POST /api/conversations/{id}/notes`（见后端文档 BFX-003）。
在后端 API 就绪前，先用 `sendOutboundMessage` 的 `message_type: "internal_note"` 字段模拟。

#### 验收标准

1. 输入区域有 [消息] / [备注] Tab 切换
2. 备注模式下输入框背景变黄
3. 备注在消息流中显示为黄色条
4. 备注不出发给客户（后端控制）
5. `npm run build` 通过

---

### FX-008：客户 360 聚合视图

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

选中客户后一站式看到所有关联数据，不需要在多个页面跳转。

#### 前端实现

**修改 `frontend/src/pages/admin-chat/CustomerTab.tsx`**:

重构为 4 个折叠区域：

```
👤 客户信息
  └── 基本信息（ID/昵称/语言/注册时间）
  └── 会员状态（认证/WhatsApp绑定）

💬 会话记录（最近 10 条）
  └── 每条: 时间 + 模式 + 最后消息预览 → 点击跳转工作台

🎫 工单记录（最近 5 条）
  └── 每条: 状态 + 标题 + 时间 → 点击跳转工单页

💰 财务概要
  └── 钱包余额 / 总充值 / 总提现 / 最近交易
```

后端 API 就绪后使用 `GET /api/customers/{id}/summary`（见后端文档 BFX-002）。
就绪前从现有 API 拼凑: `resolveCustomerProfileSummaryByConversation` + `listConversations` + `listSupportTickets`。

#### 验收标准

1. CustomerTab 有 4 个折叠区域
2. 每个区域显示关联数据
3. 点击可跳转到对应页面
4. `npm run build` 通过

---

### FX-009：消息状态回执前端展示

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 目标

前端消息气泡显示送达状态: ✓ 已发送 / ✓✓ 已送达 / ✓✓(蓝) 已读

#### 前端实现

**修改 `frontend/src/pages/admin-chat/MessagePanel.tsx`**:

1. 出站消息气泡右下角增加状态图标:

| status | 图标 | 颜色 | 文字 |
|--------|------|------|------|
| `sent` | ✓ | 灰色 | 已发送 |
| `delivered` | ✓✓ | 灰色 | 已送达 |
| `read` | ✓✓ | 蓝色 | 已读 |
| `failed` | ✕ | 红色 | 发送失败 |

2. 状态来自 `message.delivery_status` 字段
3. hover 显示详细时间: "已送达 14:32:05"

#### 验收标准

1. 出站消息显示送达状态图标
2. 不同状态有不同颜色
3. hover 显示详细时间
4. `npm run build` 通过

---

### FX-010：工作时间配置 UI

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

管理员可配置营业时间，非工作时间自动切换行为。

#### 前端实现

**修改 `frontend/src/pages/SettingsPage.tsx`**:

在"运行时开关"Tab 中增加"工作时间配置"区域：

```
工作时间配置
┌──────────────────────────────────────┐
│ 工作日: [一✅] [二✅] [三✅] [四✅] [五✅] [六❌] [日❌] │
│ 开始时间: [09:00 ▾]                    │
│ 结束时间: [18:00 ▾]                    │
│ 时区: [Asia/Shanghai ▾]               │
│                                        │
│ 非工作时间行为:                         │
│ ○ AI 托管（AI 自动回复）               │
│ ○ 留言模式（提示客户工作时间再来）      │
│ ○ 不回复                              │
│                                        │
│ 留言提示语:                             │
│ ┌──────────────────────────────────┐  │
│ │ 您好，当前为非工作时间...         │  │
│ └──────────────────────────────────┘  │
│                    [保存]              │
└──────────────────────────────────────┘
```

后端 API 就绪后使用 `PUT /api/runtime/business-hours`（见后端文档 BFX-005）。
就绪前先存 localStorage。

#### 验收标准

1. 工作时间配置区域在设置页可见
2. 工作日可勾选
3. 时间选择器可用
4. 非工作时间行为可选
5. 保存功能可用（localStorage 或 API）
6. `npm run build` 通过

---

### FX-011：全局搜索 Cmd+K 绑定

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 目标

`Ctrl+K` / `Cmd+K` 快捷键唤起全局搜索。

#### 前端实现

**修改 `frontend/src/App.tsx`**:

1. 添加全局 keydown 监听: `Ctrl+K` 或 `Meta+K`
2. 触发 GlobalSearch 组件的 `visible` 状态
3. 阻止浏览器默认行为

```typescript
useEffect(() => {
  function handleKeyDown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === "k") {
      e.preventDefault();
      setSearchVisible(true);
    }
  }
  window.addEventListener("keydown", handleKeyDown);
  return () => window.removeEventListener("keydown", handleKeyDown);
}, []);
```

#### 验收标准

1. Ctrl+K 唤起搜索框
2. Esc 关闭搜索框
3. `npm run build` 通过

---

### FX-012：会话标签

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

坐席可给会话打标签（如"VIP"、"投诉"、"退款"），方便筛选和统计。

#### 前端实现

**修改 `frontend/src/pages/admin-chat/OperationsTab.tsx`**:

1. 在操作区增加"会话标签"区域:
   ```
   会话标签: [VIP ✕] [投诉 ✕] [+ 添加标签]
   ```
2. "+ 添加标签" 弹出 Select（从平台标签中选择或输入新标签）
3. 已有标签显示为 Tag，点击 ✕ 移除

**修改 `frontend/src/pages/admin-chat/ConversationList.tsx`**:

1. 会话卡片第 3 行增加标签显示
2. 筛选区增加"按标签筛选"下拉

后端 API 就绪后使用 `PUT /api/conversations/{id}/tags`（见后端文档 BFX-006）。
就绪前先存 localStorage。

#### 验收标准

1. 操作 Tab 有标签区域
2. 可添加/移除标签
3. 会话列表显示标签
4. 按标签筛选可用
5. `npm run build` 通过

---

### FX-013：AI 回复质量看板

- **优先级**: P1
- **估计耗时**: 60 分钟

#### 目标

Dashboard 增加 AI 表现可视化面板。

#### 前端实现

**修改 `frontend/src/pages/DashboardPage.tsx`**:

增加 "AI 表现趋势" 面板（在现有"AI 表现"卡片下方）:

```
┌─ AI 表现趋势 (7天) ────────────────────┐
│                                         │
│  100% ┤                                 │
│   80% ┤ ████████████████                │  回复率
│   60% ┤                                 │
│   40% ┤                                 │
│   20% ┤ ░░░░░░░░░░░░░░                  │  降级率
│    0% ┤──────────────────────────────    │
│        周一 周二 周三 周四 周五 周六 周日 │
│                                         │
│  ■ 回复率  ■ 降级率  ■ 人工转接率       │
└─────────────────────────────────────────┘
```

**增加 "常见问题 Top10" 面板**:

```
┌─ 热门意图 Top 10 ──────────────────────┐
│ 1. 订单查询      ██████████  45次 (32%) │
│ 2. 物流追踪      ████████    38次 (27%) │
│ 3. 退款申请      ██████      25次 (18%) │
│ 4. 商品咨询      ████        15次 (11%) │
│ 5. 投诉          ██          8次  (6%)  │
│ ...                                     │
└─────────────────────────────────────────┘
```

数据来自 `GET /api/dashboard/ai-performance`（见后端文档 BFX-007）。
就绪前使用 mock 数据。

#### 验收标准

1. Dashboard 有 AI 趋势图
2. 有热门意图排行
3. mock 数据正确显示
4. `npm run build` 通过

---

## 全量验证（FX-VER）

```powershell
cd E:\codex\WhatsApp\frontend

# 类型检查
npx tsc --noEmit

# 构建
npm run build

# 全部测试
npm run test -- --environment jsdom src/pages/admin-chat.test.tsx
npm run test -- --environment jsdom src/pages/templatePage.test.tsx
npm run test -- --environment jsdom src/pages/metaAccountsPage.test.tsx
npm run test -- --environment jsdom src/pages/dashboardPage.test.tsx
npm run test -- --environment jsdom src/pages/loginPage.test.tsx
npm run test -- --environment jsdom src/services/adminAuth.test.ts
npm run test -- --environment jsdom src/services/chatRealtime.test.ts
npm run test -- --environment jsdom src/services/operations.test.ts
npm run test -- --environment jsdom src/pages/memberCustomerNavigation.test.tsx
```

### 最终验收清单

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | npx tsc --noEmit | 0 errors |
| 2 | npm run build | 通过 |
| 3 | QuickToolbar 按钮文字 | 完整显示不截断 |
| 4 | TemplatePage "创建模板"按钮 | 存在且可点击 |
| 5 | MetaAccountsPage "接入新账户"按钮 | 存在且可点击 |
| 6 | UsersPage "创建用户"按钮 | 存在且可点击 |
| 7 | 页面标题标签 | 无"进行中"/"API"标签 |
| 8 | 快捷回复功能 | Popover 可选话术插入输入框 |
| 9 | 会话备注功能 | Tab 切换 + 黄色备注条 |
| 10 | 客户 360 视图 | 4 个折叠区域有数据 |
| 11 | 消息状态回执 | 出站消息有 ✓/✓✓ 图标 |
| 12 | 工作时间配置 | 设置页可见可操作 |
| 13 | Ctrl+K 全局搜索 | 快捷键唤起搜索框 |
| 14 | 会话标签 | 可添加/移除/筛选 |
| 15 | AI 质量看板 | Dashboard 有趋势图 + Top10 |
| 16 | 全部测试 | 不退化 |

## 全局约束

1. **不碰 H5**: 不改 `h5-member/` 目录
2. **不改后端**: 不改 `app/` 目录
3. **保持 real/mock 分层**: 后端 API 未就绪时用 localStorage/mock fallback
4. **保持 prefill 跳转机制**
5. **保持 chatRealtime 集成**
6. **进度文件**: `.codex-run/progress/FX-XXX.json`
7. **单任务最大执行 90 分钟**
8. **每次改动后 `npm run build` 必须通过**
9. **一次性执行全部任务，不中途暂停确认**
