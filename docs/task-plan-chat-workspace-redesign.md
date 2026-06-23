# 会话工作台重构任务（CW-001 ~ CW-012）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 重设计会话工作台页面，提升操作效率和信息可读性

---

## 0. 当前问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 顶部统计栏 80px 浪费垂直空间 | 消息可视区域小 |
| 2 | 右侧 6 个 Card 堆叠需滚动 3 屏 | 操作员看不到操作按钮 |
| 3 | HandoverControls + ChatSidebar 共享右侧 | 操作区被信息区挤走 |
| 4 | 会话列表无分组无排序 | 紧急会话淹没在列表中 |
| 5 | 消息面板无日期分隔 | 无法定位时间边界 |
| 6 | 模板/媒体发送藏在 Drawer | 高频操作路径长 |
| 7 | 标签栏用 Button 模拟 | 体验差 |
| 8 | ChatPage 453 行 + 30 个 state | 维护困难 |
| 9 | 无空状态 | 首次打开体验差 |
| 10 | 消息气泡视觉区分弱 | 用户/AI/系统消息难分辨 |

---

## 1. 目标布局

```
┌─────────────────────────────────────────────────────────────┐
│  顶部工具栏 (40px)                                           │
│  [账号▾] [🔍搜索]  ←弹性→  [👤在线▾] [🔄]                  │
├──────────┬────────────────────────────┬─────────────────────┤
│ 会话列表  │     消息面板 (flex:1)      │  上下文面板          │
│  280px   │                           │     340px           │
│          │  ── 6月12日 ──            │                     │
│ 🔍搜索   │  用户 ← 气泡              │  [操作][详情][客户][历史]│
│ ▾账号    │       回复 → 气泡 🤖      │                     │
│          │  ── 6月11日 ──            │  [Tab 内容区]        │
│ ⚡待处理  │  用户 ← 气泡              │                     │
│  客户A 🔴│                           │                     │
│ 🟡人工   │  [📋模板] [🖼媒体] [😀模拟]│                     │
│  客户B   │  ┌────────────────┐ [发送] │                     │
│ 🟢AI    │  │ 输入回复...     │       │                     │
│  客户C   │  └────────────────┘       │                     │
├──────────┴────────────────────────────┴─────────────────────┤
│  标签栏 [Tab1✕] [Tab2✕]  ←弹性→  Ctrl+1~9切换 · Ctrl+W关闭 │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 执行编排（4 Phase）

```
Phase 1（状态管理 + 基础组件）:
  CW-001 (3 个自定义 Hook)       ── frontend_agent
  CW-002 (ConversationList 重写)  ── frontend_agent
  CW-003 (MessagePanel 重写)      ── frontend_agent

Phase 2（右侧面板 + 工具栏）:
  CW-004 (ContextPanel 4Tab)      ── frontend_agent
  CW-005 (QuickToolbar)           ── frontend_agent
  CW-006 (顶部工具栏 + 标签栏)    ── frontend_agent

Phase 3（组装 + 联调）:
  CW-007 (ChatPage 重组)          ── frontend_agent
  CW-008 (清理旧代码)             ── frontend_agent

Phase 4（测试 + 验证）:
  CW-009 (行为测试)               ── testing_agent
  CW-010 (构建 + 回归)            ── testing_agent
```

---

## Phase 1：状态管理 + 基础组件

### CW-001：3 个自定义 Hook

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

将 ChatPage.tsx 的 30 个 useState 拆分为 3 个职责单一的 Hook。

#### Hook 1: `useWorkspaceState`

**新建 `frontend/src/pages/admin-chat/hooks/useWorkspaceState.ts`**

管理：筛选、会话列表、运行时状态、坐席信息

```typescript
interface WorkspaceState {
  // 筛选
  filter: ConvFilter;
  setFilter: (f: Partial<ConvFilter>) => void;

  // 数据
  conversations: ConversationSummary[];
  runtimeState: RuntimeState | null;
  agents: RuntimeAgent[];
  workloads: AgentWorkload[];
  templates: MessageTemplateView[];
  mediaAssets: MediaAssetView[];

  // 状态
  loading: boolean;
  error: string | null;

  // 操作
  reload: () => Promise<void>;
}

function useWorkspaceState(initialFilter?: Partial<ConvFilter>): WorkspaceState
```

- 内部包含: `convs`, `rt`, `agents`, `workloads`, `tmpl`, `media`, `scopeLoad`, `err` 这 8 个 state
- `reload()` 替代原来的 `loadScope()`
- `useEffect` 监听 filter.accountId/managementMode/handoverMode 自动 reload

#### Hook 2: `useConversationDetail`

**新建 `frontend/src/pages/admin-chat/hooks/useConversationDetail.ts`**

管理：选中会话的消息、时间线、AI 状态、模板日志、客户信息

```typescript
interface ConversationDetail {
  // 数据
  messages: ConversationMessage[];
  timeline: ConversationTimelineItem[];
  aiStatus: ConversationAiStatus | null;
  templateLogs: TemplateSendLogView[];
  customerProfile: CustomerProfileSummary | null;

  // member status (来自 useMemberStatus)
  memberStatus: MemberStatusSnapshot | null;
  latestVerification: VerificationSummary | null;
  latestBinding: BindingSummary | null;

  // 状态
  loading: boolean;

  // 操作
  loadForConversation: (conv: ConversationSummary) => Promise<void>;
  reset: () => void;
}

function useConversationDetail(): ConversationDetail
```

- 内部包含: `msgs`, `tl`, `aiSt`, `tmplLogs`, `profile`, `detLoad` + useMemberStatus hook 调用
- `loadForConversation()` 替代原来的 `loadDetail()` + `loadCustomerCtx()`
- `reset()` 清空所有数据

#### Hook 3: `useChatActions`

**新建 `frontend/src/pages/admin-chat/hooks/useChatActions.ts`**

管理：所有写操作（发送/接管/恢复/暂停/关闭/分配/切换 AI）

```typescript
interface ChatActions {
  pendingAction: string | null;

  sendMessage: (conv: ConversationSummary, text: string, agentId: string) => Promise<void>;
  mockInbound: (conv: ConversationSummary, text: string, lang?: string) => Promise<void>;
  handover: (conv: ConversationSummary, agentId: string, reason?: string) => Promise<void>;
  restoreAI: (conv: ConversationSummary, agentId: string, reason?: string) => Promise<void>;
  pause: (conv: ConversationSummary, agentId: string, reason?: string) => Promise<void>;
  close: (conv: ConversationSummary, agentId: string, reason?: string) => Promise<void>;
  toggleAiSwitch: (conv: ConversationSummary) => Promise<void>;
  assignAgent: (conv: ConversationSummary, agentId: string, assignedBy: string, reason?: string) => Promise<void>;
  sendTemplate: (template: MessageTemplateView, conv: ConversationSummary, vars: Record<string,string>, agentId: string) => Promise<void>;
  sendMedia: (media: MediaAssetView, conv: ConversationSummary, caption?: string, fileName?: string, agentId?: string) => Promise<void>;
}

function useChatActions(onSuccess: () => Promise<void>): ChatActions
```

- `onSuccess` 回调用于操作成功后刷新数据
- 每个方法内部包含 try/catch + setPending + message.error 提示

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/admin-chat/hooks/useWorkspaceState.ts` | 新增 |
| `frontend/src/pages/admin-chat/hooks/useConversationDetail.ts` | 新增 |
| `frontend/src/pages/admin-chat/hooks/useChatActions.ts` | 新增 |
| `frontend/src/pages/admin-chat/hooks/index.ts` | 新增（导出汇总） |

#### 验收标准

1. 3 个 Hook 文件存在
2. 类型定义正确
3. 构建通过（暂不集成到 ChatPage）

---

### CW-002：ConversationList 重写

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

重写会话列表：分组显示 + 紧凑卡片 + 色条选中态。

#### 设计要求

**1. 分组规则**（按优先级排序）

```
⚡ 待处理（latest_handover_recommended && management_mode !== "human_managed"）
🟡 人工接管（management_mode === "human_managed"）
🟢 AI 托管（management_mode === "ai_managed" && !recommended）
⏸ 暂停（management_mode === "paused"）
🔒 已关闭（status === "closed"）
```

每个分组标题显示数量: `⚡ 待处理 (3)`

空分组不显示标题。

**2. 卡片设计（3 行）**

```
┌─────────────────────────────┐
│ 🟢 客户ID前12位    3分钟前  │  ← 第 1 行：客户 + 时间
│ 最后一条消息预览截断...      │  ← 第 2 行：消息预览
│ [AI托管] [zh-CN]   💬 3    │  ← 第 3 行：模式标签 + 语言 + 未读数
└─────────────────────────────┘
```

- 卡片高度: ~72px
- 选中态: 左侧 3px 色条（绿=AI, 黄=人工, 红=推荐, 灰=暂停）
- 推荐转人工: 整个卡片加淡红色背景 `#fff2f0`
- 搜索高亮: 匹配文本加 `<mark>` 包裹

**3. 筛选区域**

- 搜索框: 固定在顶部
- 账号下拉: 搜索框下方（如果只有 1 个账号则隐藏）
- 移除模式下拉（已通过分组实现）

**4. 填充剩余高度**

```css
.session-list-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.session-list-scroll {
  flex: 1;
  overflow-y: auto;
}
```

#### Props 接口

```typescript
interface ConversationListProps {
  conversations: ConversationSummary[];
  selectedId: string;
  onSelect: (key: string) => void;
  onSearch: (query: string) => void;
  onFilterAccount: (accountId: string) => void;
  accountId: string;
  runtimeAccounts: { account_id: string; display_name: string }[];
  loading: boolean;
  unreadCounts: Record<string, number>;
}
```

新增 `unreadCounts` prop。

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/admin-chat/ConversationList.tsx` | 重写 |

#### 验收标准

1. 会话按模式分组显示
2. 卡片 3 行紧凑布局
3. 选中态有色条
4. 推荐转人工有红色背景
5. 搜索功能正常
6. 构建通过

---

### CW-003：MessagePanel 重写

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

重写消息面板：气泡式布局 + 日期分隔 + 角色区分 + 空状态。

#### 设计要求

**1. 气泡布局**

| 消息方向 | 对齐 | 背景 | 圆角 | 角色标识 |
|---------|------|------|------|---------|
| inbound（用户） | 左对齐 | `#f5f5f5` | 左上直角，其他 12px | 👤 头像占位 |
| outbound + ai_generated | 右对齐 | `#e6f4ff` | 右上直角，其他 12px | 🤖 小角标 |
| outbound + manual | 右对齐 | `#d4edda` | 右上直角，其他 12px | 👤 坐席名 |
| system | 居中 | `#fafafa` | 全圆角 8px | 无 |

气泡最大宽度: 75%

**2. 日期分隔线**

```
──────── 6月12日 星期四 ────────
```

- 当相邻两条消息的 `created_at` 日期不同时插入
- 居中显示，灰色文字，两侧细线

**3. 消息气泡内容**

```
┌─────────────────────┐
│ 消息正文             │
│ (多行自动换行)       │
│                      │
│ 翻译文本(如有)       │  ← 斜体灰色
│                      │
│ 14:32                │  ← 右下角小字
└─────────────────────┘
```

- 非文本消息（image/audio/video/document）显示图标 + 类型文字
- hover 显示完整信息 Popover（message_id、message_type、provider_reference 等）

**4. 自动滚动**

- 新消息到达 + 当前在底部 → 自动滚动到底部
- 新消息到达 + 当前不在底部 → 显示"↓ N 条新消息"浮动按钮
- 点击浮动按钮 → 滚动到底部

**5. 空状态**

未选择会话时:

```
┌──────────────────────────────┐
│                              │
│         💬                   │
│     选择一个会话开始工作      │
│                              │
│   Ctrl+1~9 切换标签          │
│   Ctrl+W 关闭标签            │
│   Enter 发送 · Shift+Enter 换行 │
│                              │
└──────────────────────────────┘
```

**6. 输入区域**

```
┌──────────────────────────────────┐
│ [🤖] ┌──────────────────┐ [📤]  │  ← 模式图标 + 输入框 + 发送按钮
│       │ 输入回复...       │       │
│       │ (Shift+Enter 换行)│       │
│       └──────────────────┘       │
└──────────────────────────────────┘
```

- 模式图标: 🤖=AI托管(蓝) / 👤=人工(绿) / ⏸=暂停(灰)
- 暂停模式: 输入框 disabled + 提示"会话已暂停"
- 发送按钮: 主色调，Enter 发送，Shift+Enter 换行
- TextArea 自动高度（1-5 行）

#### Props 接口

```typescript
interface MessagePanelProps {
  messages: ConversationMessage[];
  conversationMode: "ai_managed" | "human_managed" | "paused" | null;
  onSendMessage: (text: string) => void;
  loading: boolean;
  aiGenerating: boolean;
  currentAgentName: string | null;
  selectedConversation: ConversationSummary | null;  // null 时显示空状态
}
```

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/admin-chat/MessagePanel.tsx` | 重写 |

#### 验收标准

1. 气泡式布局正确（左/右/居中）
2. 日期分隔线正确显示
3. AI 生成消息有 🤖 角标
4. 空状态显示快捷键提示
5. 自动滚动到底部 / 新消息浮动按钮
6. Enter 发送 + Shift+Enter 换行
7. 构建通过

---

## Phase 2：右侧面板 + 工具栏

### CW-004：ContextPanel（4 Tab 容器）

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

将右侧 6 个 Card 重构为 4 个 Tab 的容器组件。

#### Tab 结构

| Tab Key | Label | 图标 | 内容来源 |
|---------|-------|------|---------|
| `operations` | 操作 | 🎯 | 提取自 HandoverControls |
| `detail` | 详情 | 📋 | 提取自 ChatSidebar 的会话元数据 + AI 状态 |
| `customer` | 客户 | 👤 | 提取自 ChatSidebar 的客户档案 + 认证 + 绑定 |
| `history` | 历史 | 📜 | 提取自 ChatSidebar 的时间线 + 新增模板日志 |

#### 子组件

**OperationsTab.tsx**（提取自 HandoverControls）

```typescript
interface OperationsTabProps {
  conversation: ConversationSummary | null;
  aiStatus: ConversationAiStatus | null;
  agents: RuntimeAgent[];
  agentOptions: { label: string; value: string }[];
  pendingAction: string | null;
  globalAiEnabled: boolean;
  onHandover: () => void;
  onRestoreAI: () => void;
  onPause: () => void;
  onClose: () => void;
  onToggleAiSwitch: () => void;
  onAssignAgent: (agentId: string) => void;
  onReasonChange: (reason: string) => void;
}
```

内容布局（从上到下）：
1. 当前模式标签（大字）
2. 推荐转人工 Alert（仅当 recommended）
3. 坐席分配 Select
4. 原因输入 TextArea（2行）
5. 操作按钮组：[人工接管] [恢复AI] [暂停] [关闭]
6. AI 开关区域：全局状态 + 会话开关按钮

**DetailTab.tsx**（提取自 ChatSidebar 上半部分）

```typescript
interface DetailTabProps {
  conversation: ConversationSummary | null;
  aiStatus: ConversationAiStatus | null;
}
```

内容：
- 会话元数据 Descriptions（账号/模式/状态/号码/客户/最近消息/分配坐席/接管建议）
- AI 三级状态（全局/账号/会话 + 最终结果 + 原因）
- 字段值可复制（点击复制 icon）

**CustomerTab.tsx**（提取自 ChatSidebar 下半部分）

```typescript
interface CustomerTabProps {
  conversation: ConversationSummary | null;
  customerProfile: CustomerProfileSummary | null;
  onOpenCustomerPage: () => void;
}
```

内容：
- 客户档案概要
- 会员认证状态（复用 useMemberStatus hook）
- WhatsApp 绑定状态
- 「跳转客户页」按钮

**HistoryTab.tsx**（提取自 ChatSidebar 时间线部分）

```typescript
interface HistoryTabProps {
  timeline: ConversationTimelineItem[];
  templateLogs: TemplateSendLogView[];
}
```

内容：
- 接管事件时间线（筛选 item_type === "handover"）
- 全部时间线（最近 20 条）
- 模板发送日志（最近 10 条）

#### ContextPanel 容器

```typescript
interface ContextPanelProps {
  conversation: ConversationSummary | null;
  aiStatus: ConversationAiStatus | null;
  timeline: ConversationTimelineItem[];
  templateLogs: TemplateSendLogView[];
  customerProfile: CustomerProfileSummary | null;
  agents: RuntimeAgent[];
  agentOptions: { label: string; value: string }[];
  pendingAction: string | null;
  globalAiEnabled: boolean;
  onHandover: () => void;
  onRestoreAI: () => void;
  onPause: () => void;
  onClose: () => void;
  onToggleAiSwitch: () => void;
  onAssignAgent: (agentId: string) => void;
  onReasonChange: (reason: string) => void;
  onOpenCustomerPage: () => void;
}
```

使用 AntD `Tabs` 组件:
```tsx
<Tabs
  defaultActiveKey="operations"
  size="small"
  items={[
    { key: "operations", label: "🎯 操作", children: <OperationsTab ... /> },
    { key: "detail", label: "📋 详情", children: <DetailTab ... /> },
    { key: "customer", label: "👤 客户", children: <CustomerTab ... /> },
    { key: "history", label: "📜 历史", children: <HistoryTab ... /> },
  ]}
/>
```

未选中会话时显示空状态提示。

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/admin-chat/ContextPanel.tsx` | 新增 |
| `frontend/src/pages/admin-chat/OperationsTab.tsx` | 新增（提取自 HandoverControls） |
| `frontend/src/pages/admin-chat/DetailTab.tsx` | 新增（提取自 ChatSidebar） |
| `frontend/src/pages/admin-chat/CustomerTab.tsx` | 新增（提取自 ChatSidebar） |
| `frontend/src/pages/admin-chat/HistoryTab.tsx` | 新增（提取自 ChatSidebar） |

#### 验收标准

1. 4 个 Tab 可切换
2. 操作 Tab 包含所有接管/恢复/暂停/关闭/AI 开关功能
3. 详情 Tab 包含会话元数据和 AI 状态
4. 客户 Tab 包含客户档案和认证/绑定状态
5. 历史 Tab 包含时间线和模板日志
6. 构建通过

---

### CW-005：QuickToolbar（快捷工具栏）

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 目标

输入框上方的快捷操作栏，替代 Drawer。

#### 设计要求

```
┌──────────────────────────────────────────┐
│ [📋 发送模板 ▾]  [🖼 发送媒体 ▾]  [😀 模拟入站 ▾] │
└──────────────────────────────────────────┘
```

**发送模板 Popover**:
- Select 选择模板（仅显示当前账号 + APPROVED 状态）
- 变量输入区（根据模板 sample_variables 自动生成输入框）
- 预览区域
- 发送按钮

**发送媒体 Popover**:
- Select 选择媒体（仅显示当前账号 + active）
- Caption 输入框
- 文件名输入框
- 发送按钮

**模拟入站 Popover**:
- TextArea 输入文本
- 语言选择（es/fr/zh-CN/en）
- 发送按钮
- 预设示例按钮（西语/法语/中文 各 1 条）

#### Props 接口

```typescript
interface QuickToolbarProps {
  conversation: ConversationSummary | null;
  templates: MessageTemplateView[];
  mediaAssets: MediaAssetView[];
  onSendTemplate: (templateId: string, variables: Record<string, string>) => void;
  onSendMedia: (assetId: string, caption?: string, fileName?: string) => void;
  onMockInbound: (text: string, language?: string) => void;
  disabled: boolean;
}
```

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/admin-chat/QuickToolbar.tsx` | 新增 |

#### 验收标准

1. 3 个 Popover 可弹出
2. 模板选择 + 变量填写 + 发送可用
3. 媒体选择 + caption + 发送可用
4. 模拟入站 + 语言 + 发送可用
5. 禁用态正确（未选中会话时全部 disabled）
6. 构建通过

---

### CW-006：顶部工具栏 + 底部标签栏

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 顶部工具栏（40px）

```tsx
<Row align="middle" gutter={12} style={{ height: 40, paddingInline: 12 }}>
  <Col>
    <Select size="small" style={{ width: 160 }}
      options={[{ label: "全部账号", value: "all" }, ...accounts]}
      value={accountId} onChange={onFilterAccount}
    />
  </Col>
  <Col>
    <Input.Search size="small" placeholder="搜索会话..."
      style={{ width: 200 }} onChange={onSearch} allowClear
    />
  </Col>
  <Col flex="auto" />
  <Col>
    <Tag color={statusColor}>{operatorLabel}</Tag>
    <Select size="small" style={{ width: 100 }}
      options={[{label:"在线",value:"online"},...]}
      value={opStatus} onChange={setOpStatus}
    />
  </Col>
  <Col>
    <Button size="small" icon={<ReloadOutlined />}
      onClick={onReload} loading={loading}
    />
  </Col>
</Row>
```

#### 底部标签栏

**新建 `frontend/src/pages/admin-chat/ChatTabs.tsx`**

```typescript
interface ChatTabsProps {
  tabs: OpenTab[];
  activeKey: string;
  onSelect: (key: string) => void;
  onClose: (key: string) => void;
  unreadCounts: Record<string, number>;
}
```

使用 AntD `Tabs`:
```tsx
<Tabs
  type="editable-card"
  hideAdd
  activeKey={activeKey}
  onChange={onSelect}
  onEdit={(key) => onClose(key as string)}
  items={tabs.map((tab, i) => ({
    key: tab.key,
    label: (
      <Space size={4}>
        <span>#{i + 1}</span>
        <span>{tab.label}</span>
      </Space>
    ),
    closeable: true,
  }))}
  tabBarExtraContent={
    <Typography.Text type="secondary" style={{ fontSize: 11 }}>
      Ctrl+1~9 切换 · Ctrl+W 关闭
    </Typography.Text>
  }
/>
```

每个 Tab 如果有未读消息，显示 Badge 红点。

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/admin-chat/ChatTabs.tsx` | 新增 |

#### 验收标准

1. 顶部工具栏 40px 高度
2. 账号筛选 + 搜索 + 坐席状态 + 刷新按钮
3. 底部标签栏使用 AntD Tabs
4. 未读消息有 Badge
5. 快捷键提示文字显示
6. 构建通过

---

## Phase 3：组装 + 联调

### CW-007：ChatPage 重组

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

用新的 Hook + 子组件重写 ChatPage.tsx，目标 < 200 行。

#### 伪代码

```tsx
export function ChatPage(): JSX.Element {
  // ── 状态 ──
  const ws = useWorkspaceState();
  const detail = useConversationDetail();
  const actions = useChatActions(async () => {
    await ws.reload();
    if (selConv) await detail.loadForConversation(selConv);
  });

  // ── 选中会话 ──
  const [selKey, setSelKey] = useState("");
  const selConv = useMemo(() => findConv(ws.conversations, selKey), [ws.conversations, selKey]);

  // ── 标签管理 ──
  const [openTabs, setOpenTabs] = useState<OpenTab[]>([]);
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({});

  // ── 加载详情 ──
  useEffect(() => {
    if (selConv) void detail.loadForConversation(selConv);
    else detail.reset();
  }, [selConv?.account_id, selConv?.conversation_id]);

  // ── 实时推送 ──
  useEffect(() => { /* chatRealtime 连接 + 回调 */ }, []);

  // ── 快捷键 ──
  useEffect(() => { /* Ctrl+1~9, Ctrl+W */ }, [selKey]);

  // ── Prefill 处理 ──
  useEffect(() => { /* workspacePagePrefill */ }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 120px)" }}>
      {/* 顶部工具栏 */}
      <TopToolbar ... />

      {/* 三栏主体 */}
      <div style={{ display: "flex", flex: 1, minHeight: 0, gap: 12 }}>
        {/* 左侧会话列表 */}
        <div style={{ width: 280, flexShrink: 0 }}>
          <ConversationList ... />
        </div>

        {/* 中间消息面板 */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
          <MessagePanel ... />
          <QuickToolbar ... />
          {/* 输入区域 */}
          <MessageInput ... />
        </div>

        {/* 右侧上下文面板 */}
        <div style={{ width: 340, flexShrink: 0 }}>
          <ContextPanel ... />
        </div>
      </div>

      {/* 底部标签栏 */}
      <ChatTabs ... />
    </div>
  );
}
```

#### 关键设计

1. **高度管理**: 整体使用 `flex column + height: calc(100vh - 120px)` 确保三栏填满
2. **三栏**: 使用 CSS flex（非 AntD Layout.Sider），更精确控制宽度
3. **数据流**: Hook 产出数据 → 通过 props 传给子组件
4. **事件流**: 子组件回调 → 调用 actions 方法 → onSuccess 刷新数据

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/ChatPage.tsx` | 重写（目标 < 200 行） |

#### 验收标准

1. ChatPage.tsx < 200 行
2. 所有功能与原版一致
3. 三栏布局正确
4. 构建通过

---

### CW-008：清理旧代码

- **优先级**: P1
- **估计耗时**: 15 分钟

#### 需要清理的文件

| 文件 | 处理 |
|------|------|
| `admin-chat/HandoverControls.tsx` | 删除（功能已迁移到 OperationsTab） |
| `admin-chat/ChatSidebar.tsx` | 删除（功能已迁移到 DetailTab + CustomerTab + HistoryTab） |
| `admin-chat/index.ts` | 更新导出列表 |

#### 验收标准

1. 旧文件已删除
2. index.ts 导出正确
3. 构建通过
4. 无 unused import 警告

---

## Phase 4：测试 + 验证

### CW-009：行为测试更新

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 更新 `frontend/src/pages/admin-chat.test.tsx`

更新测试以适配新组件结构：

1. **ConversationList 测试**
   - 分组渲染（传入 5 个不同模式的会话 → 验证分组标题数量）
   - 推荐转人工卡片有红色背景
   - 选中态有色条
   - 搜索过滤正确

2. **MessagePanel 测试**
   - 气泡布局（inbound 左 / outbound 右）
   - 日期分隔线正确显示
   - 空状态显示快捷键
   - AI 消息有角标

3. **ContextPanel 测试**
   - 4 个 Tab 可切换
   - 操作 Tab 有接管按钮
   - 未选中会话显示空状态

4. **QuickToolbar 测试**
   - 3 个按钮存在
   - 禁用态正确

#### 验收标准

1. 测试文件更新
2. 15+ 测试通过
3. 构建通过

---

### CW-010：全量验证

- **优先级**: P0
- **估计耗时**: 15 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend

# 构建
npm run build

# Chat 测试
npm run test -- src/pages/admin-chat.test.tsx

# 其他测试不退化
npm run test -- src/pages/templatePage.test.tsx
npm run test -- src/pages/metaAccountsPage.test.tsx
npm run test -- src/pages/dashboardPage.test.tsx
npm run test -- src/pages/loginPage.test.tsx
npm run test -- src/services/adminAuth.test.ts
npm run test -- src/services/chatRealtime.test.ts
npm run test -- src/services/operations.test.ts
npm run test -- src/pages/memberCustomerNavigation.test.tsx
```

#### 验收标准

| 项 | 预期 |
|----|------|
| npm run build | 通过 |
| ChatPage.tsx 行数 | < 200 |
| admin-chat/ 组件数 | 10+ (含 hooks) |
| admin-chat.test.tsx | 15+ 通过 |
| 其他测试 | 不退化 |
| HandoverControls.tsx | 已删除 |
| ChatSidebar.tsx | 已删除 |

---

## 3. 全局约束

1. **不碰 H5**: 不改 `h5-member/` 目录
2. **不改后端**: 不改 `app/` 目录
3. **保持 real/mock 分层**
4. **保持 prefill 跳转机制**
5. **保持 chatRealtime 集成**（SSE + 轮询降级）
6. **保持快捷键** Ctrl+1~9 切换标签 / Ctrl+W 关闭
7. **使用 useMemberStatus hook**: CustomerTab 必须复用
8. **进度文件**: `.codex-run/progress/CW-XXX.json`
9. **单任务最大执行 90 分钟**
10. **失败自动回滚 + 重试最多 3 次**
11. **每次改动后 `npm run build` 必须通过**
12. **一次性执行全部任务，不中途暂停确认**

---

## 4. 改动文件影响范围

| 文件 | 改动类型 |
|------|---------|
| `ChatPage.tsx` | **重写**（453→<200行） |
| `admin-chat/ConversationList.tsx` | **重写**（分组+紧凑） |
| `admin-chat/MessagePanel.tsx` | **重写**（气泡+分隔） |
| `admin-chat/HandoverControls.tsx` | **删除** |
| `admin-chat/ChatSidebar.tsx` | **删除** |
| `admin-chat/ContextPanel.tsx` | 新增 |
| `admin-chat/OperationsTab.tsx` | 新增 |
| `admin-chat/DetailTab.tsx` | 新增 |
| `admin-chat/CustomerTab.tsx` | 新增 |
| `admin-chat/HistoryTab.tsx` | 新增 |
| `admin-chat/QuickToolbar.tsx` | 新增 |
| `admin-chat/ChatTabs.tsx` | 新增 |
| `admin-chat/hooks/useWorkspaceState.ts` | 新增 |
| `admin-chat/hooks/useConversationDetail.ts` | 新增 |
| `admin-chat/hooks/useChatActions.ts` | 新增 |
| `admin-chat/hooks/index.ts` | 新增 |
| `admin-chat/index.ts` | 更新导出 |
| `admin-chat.test.tsx` | 更新测试 |
| `h5-member/` | **不动** |
| `app/` | **不动** |
