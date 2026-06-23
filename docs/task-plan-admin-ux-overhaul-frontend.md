# 管理后台全面 UX 重构 — 前端任务（PR-001 ~ PR-025）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 每个页面做到「不用看教程、不用问技术、不重复劳动、找数据快、操作简单、不会误操作」

---

## 0. 全局问题诊断

### 跨页面通病（每个页面都存在）

| # | 问题 | 影响 | 解决方案 |
|---|------|------|---------|
| 1 | **每页 15-30 个 useState** | 代码混乱，状态不同步 | 统一 `usePageData` Hook |
| 2 | **每页手写加载逻辑** | 重复代码 500+ 行/页 | 统一数据加载模式 |
| 3 | **ProTable 每页重复配置** | columns/filter/sort 散落各处 | 统一 `useProTablePage` 模式 |
| 4 | **无统一错误处理** | 每页自定义 Alert，风格不一致 | 全局 `useApiError` + toast |
| 5 | **无空结果引导** | 空表格只显示"暂无数据" | 空状态 + 引导操作按钮 |
| 6 | **确认对话框文案不一致** | 有的有确认有的没有 | 统一 `DangerButton` 组件 |
| 7 | **搜索能力弱** | 仅当前页过滤，无法跨页搜索 | 后端搜索 API + 前端高亮 |
| 8 | **操作反馈不明确** | 操作成功无明确提示 | 统一 success/error toast |
| 9 | **页面间跳转无上下文** | 跳转后不知道从哪来 | URL state 保持 + 面包屑 |
| 10 | **数据源标识干扰** | 每页顶部 AdminDataSourceLegend | 移除或缩为小图标 |

### 页面行数统计（> 700 行的巨石页面）

| 页面 | 行数 | 问题严重度 |
|------|------|-----------|
| MetaAccountsPage | 1208 | 🔴 严重 |
| TemplatePage | 1055 | 🔴 严重 |
| UsersPage | 1000 | 🔴 严重 |
| MediaLibraryPage | 941 | 🔴 严重 |
| IdentitySyncPage | 888 | 🟡 中等 |
| ReviewsPage | 875 | 🟡 中等 |
| DashboardPage | 877 | 🟡 中等 |
| SettingsPage | 853 | 🟡 中等 |
| WhatsAppStatsPage | 826 | 🟡 中等 |
| EvidenceCenterPage | 794 | 🟡 中等 |
| AssignmentsPage | 794 | 🟡 中等 |
| CustomersPage | 779 | 🟡 中等 |
| AccessControlPage | 778 | 🟡 中等 |
| OperationsCenterPage | 764 | 🟡 中等 |

---

## 1. 执行编排（6 Phase，预计 4-5 天）

```
Day 1:
  Phase 1（共享基础设施，P0）: PR-001~004
  Phase 2（Dashboard 重设计，P0）: PR-005~006

Day 2:
  Phase 3（高频操作页，P0）: PR-007~010

Day 3:
  Phase 4（内容管理页，P1）: PR-011~014

Day 4:
  Phase 5（系统/运维页，P1）: PR-015~018

Day 5:
  Phase 6（收尾验证，P0）: PR-019~025
```

---

## Phase 1：共享基础设施（P0 — 所有后续页面的基础）

### PR-001：统一数据加载 Hook — `usePageData`

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

替换每页重复的 `useState + useEffect + loading/error` 模式。

#### 新增 `frontend/src/hooks/usePageData.ts`

```typescript
interface PageDataOptions<T> {
  fetcher: () => Promise<T>;
  deps?: unknown[];           // 依赖变化时重新加载
  immediate?: boolean;        // 是否立即加载（默认 true）
  onSuccess?: (data: T) => void;
  onError?: (error: string) => void;
}

interface PageDataResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  setData: (updater: (prev: T | null) => T | null) => void;
}

function usePageData<T>(options: PageDataOptions<T>): PageDataResult<T>
```

#### 用法示例（改造前 vs 改造后）

```typescript
// 改造前（每个页面都这样写 ~10 行）
const [data, setData] = useState<T | null>(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState<string | null>(null);
useEffect(() => {
  setLoading(true); setError(null);
  fetchData().then(setData).catch(e => setError(e.message)).finally(() => setLoading(false));
}, [dep1, dep2]);

// 改造后（3 行）
const { data, loading, error, reload } = usePageData({
  fetcher: () => fetchData(dep1, dep2),
  deps: [dep1, dep2],
});
```

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/hooks/usePageData.ts` | 新增 |

#### 验收标准

1. Hook 存在且有类型定义
2. 构建通过

---

### PR-002：统一 ProTable 页面模式 — `useTablePage`

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

为所有 ProTable 页面提供统一的分页/筛选/排序/选择模式。

#### 新增 `frontend/src/hooks/useTablePage.ts`

```typescript
interface TablePageOptions<T, F extends Record<string, unknown>> {
  fetcher: (params: { page: number; size: number; filters: F; sort?: string }) => Promise<{ items: T[]; total: number }>;
  defaultFilters: F;
  defaultPageSize?: number;  // 默认 20
}

interface TablePageResult<T, F> {
  items: T[];
  total: number;
  loading: boolean;
  error: string | null;
  filters: F;
  page: number;
  pageSize: number;
  selectedKeys: string[];
  setFilters: (f: Partial<F>) => void;
  setPage: (p: number) => void;
  setPageSize: (s: number) => void;
  setSelectedKeys: (keys: string[]) => void;
  reload: () => Promise<void>;
  clearSelection: () => void;
}

function useTablePage<T, F extends Record<string, unknown>>(
  options: TablePageOptions<T, F>
): TablePageResult<T, F>
```

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/hooks/useTablePage.ts` | 新增 |
| `frontend/src/hooks/index.ts` | 新增（汇总导出） |

#### 验收标准

1. Hook 存在
2. 构建通过

---

### PR-003：统一操作反馈 + 危险操作组件

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 新增 `frontend/src/components/Feedback.tsx`

```typescript
// 操作成功提示
function showSuccess(msg: string): void   // message.success + 可选刷新

// 操作失败提示
function showError(msg: string): void     // message.error

// 危险操作按钮（自动带 Popconfirm）
interface DangerButtonProps {
  label: string;
  confirmTitle: string;
  confirmDescription?: string;
  onConfirm: () => Promise<void>;
  disabled?: boolean;
  loading?: boolean;
  type?: "primary" | "default" | "dashed" | "text" | "link";
  danger?: boolean;
}
function DangerButton(props: DangerButtonProps): JSX.Element
```

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/components/Feedback.tsx` | 新增 |

#### 验收标准

1. showSuccess/showError 可用
2. DangerButton 自动弹出确认
3. 构建通过

---

### PR-004：统一空状态 + 页面容器组件

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 新增 `frontend/src/components/PageShell.tsx`

```typescript
// 页面容器（统一标题 + 工具栏 + 数据源标识）
interface PageShellProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;      // 右侧操作按钮
  stats?: React.ReactNode;        // 顶部统计条（可选）
  children: React.ReactNode;
}
function PageShell(props: PageShellProps): JSX.Element

// 空状态引导
interface EmptyGuideProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actions?: { label: string; onClick: () => void; type?: "primary" | "default" }[];
}
function EmptyGuide(props: EmptyGuideProps): JSX.Element
```

#### 设计效果

```
┌─────────────────────────────────────────────┐
│ 📋 模板消息                    [创建] [同步] │  ← PageShell 标题行
│ 管理模板草稿、审核状态、发送日志和统计        │  ← subtitle
├─────────────────────────────────────────────┤
│ [统计条: 总数 45 | 已通过 30 | 待审核 5]     │  ← stats (可选)
├─────────────────────────────────────────────┤
│                                             │
│  children (ProTable / 内容区)                │
│                                             │
└─────────────────────────────────────────────┘
```

移除每页的 `AdminDataSourceLegend`（统一在 PageShell 内以小图标代替）。

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/components/PageShell.tsx` | 新增 |
| `frontend/src/components/EmptyGuide.tsx` | 新增 |

#### 验收标准

1. PageShell 渲染正确
2. EmptyGuide 显示引导按钮
3. 构建通过

---

## Phase 2：Dashboard 重设计（P0）

### PR-005：Dashboard 重构 — 运营决策中心

- **优先级**: P0
- **估计耗时**: 90 分钟
- **当前**: 877 行，信息堆砌

#### 重设计目标

Dashboard 是操作员每天打开的第一个页面，必须在 5 秒内回答：
1. **系统健康吗？** → 顶部状态指示灯
2. **我需要处理什么？** → 待办事项列表
3. **今天表现如何？** → 核心指标卡片
4. **有问题需要关注吗？** → 告警摘要

#### 布局设计

```
┌──────────────────────────────────────────────────────┐
│ 系统状态: ✅ 全部正常   最后检查: 14:32   [刷新]      │
├────────┬────────┬────────┬────────┬───────────────────┤
│总会话   │待处理   │人工接管  │AI托管   │ 今日消息量       │
│  128   │  12 🔴 │  8     │  108   │  1,247 ↑12%     │
├────────┴────────┴────────┴────────┴───────────────────┤
│ ┌─ 我的待办 ──────────────────┐ ┌─ 快捷操作 ────────┐│
│ │ ⚡ 12 条推荐转人工           │ │ [进入工作台]      ││
│ │ 📋 5 个待审核模板           │ │ [创建模板]        ││
│ │ 🎫 3 个未处理工单           │ │ [查看告警]        ││
│ │ 💰 2 个待审核提现           │ │ [发送群发]        ││
│ └────────────────────────────┘ └───────────────────┘│
│ ┌─ 消息趋势 (24h) ──────────┐ ┌─ AI 表现 ──────────┐│
│ │  入站 ──╲                  │ │ 回复率: 94.2%      ││
│ │  出站 ── ╲──               │ │ 降级率: 2.1%       ││
│ │           ╲──              │ │ 人工转接率: 5.7%   ││
│ └────────────────────────────┘ └───────────────────┘│
└──────────────────────────────────────────────────────┘
```

#### 关键改进

| 当前 | 重设计后 |
|------|---------|
| 大量指标堆叠无优先级 | 5 个核心指标 + 待办驱动 |
| 无待办事项 | "我的待办"列表（聚合各模块待处理数） |
| 无快捷操作 | 4 个一键操作按钮 |
| 指标来源分散 | 统一从 /api/dashboard/summary 获取 |
| 877 行 | < 300 行（逻辑移入 useDashboardData hook） |

#### 新增后端依赖

需要后端提供 `GET /api/dashboard/summary`（详见后端文档 DBE-001）。

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/DashboardPage.tsx` | 重写（877→<300行） |
| `frontend/src/hooks/useDashboardData.ts` | 新增 |

#### 验收标准

1. Dashboard < 300 行
2. 5 秒内可看到系统状态 + 待办数
3. 待办列表可点击跳转
4. 快捷操作按钮可用
5. 构建通过

---

### PR-006：Dashboard 测试

- **优先级**: P0
- **估计耗时**: 15 分钟

更新 `dashboardPage.test.tsx` 适配新结构。5+ 测试通过。

---

## Phase 3：高频操作页（P0）

### PR-007：我的队列（AssignmentsPage）重构

- **当前**: 794 行
- **目标**: < 350 行
- **估计耗时**: 60 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 使用 useTablePage | 统一分页/筛选/选择 |
| 卡片式视图 | 每个待分配会话一张卡片（客户名/最后消息/等待时间/推荐等级） |
| 一键认领 | 卡片上"认领"按钮，无需打开详情 |
| 排序优先级 | 等待时间长的在前、推荐转人工的在前 |
| 批量认领 | 勾选多个 → "批量认领" |
| 使用 PageShell + EmptyGuide | 统一外观 |

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/AssignmentsPage.tsx` | 重写 |

---

### PR-008：工单页面（TicketsPage）重构

- **当前**: 673 行
- **目标**: < 300 行
- **估计耗时**: 45 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 使用 useTablePage | 统一分页/筛选 |
| 状态看板视图 | 4 列: 待处理 / 处理中 / 等待用户 / 已解决（可切换列表/看板） |
| 快捷操作 | 每行右侧: [回复] [转派] [关闭] — 不用打开详情 |
| SLA 倒计时 | 超过 24h 未处理显示红色倒计时 |
| 使用 DangerButton | 关闭工单有确认 |

---

### PR-009：客户页面（CustomersPage）重构

- **当前**: 779 行
- **目标**: < 350 行
- **估计耗时**: 45 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 使用 useTablePage | 统一分页/筛选 |
| 搜索增强 | 支持手机号/昵称/ID 模糊搜索 |
| 快速预览 | 点击行展开内联预览（最近会话/会员状态/工单数） |
| 跳转优化 | 点击客户名 → 工作台并预选该客户的会话 |

---

### PR-010：审核队列（ReviewsPage）重构

- **当前**: 875 行
- **目标**: < 300 行
- **估计耗时**: 45 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 使用 useTablePage | 统一分页/筛选 |
| 审核效率 | 每行直接显示[通过✅] [驳回❌] 按钮，无需打开详情 |
| 批量审核 | 勾选多个 → "批量通过" / "批量驳回" |
| 预览弹窗 | 点击查看证据截图/文本，不离开列表 |
| 使用 DangerButton | 驳回操作有确认 |

---

## Phase 4：内容管理页（P1）

### PR-011：模板消息（TemplatePage）重构

- **当前**: 1055 行
- **目标**: < 400 行
- **估计耗时**: 60 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 使用 useTablePage | 统一分页/筛选 |
| Tab 视图 | [全部模板] [待审核] [已通过] [已拒绝] — 顶部 Tab 切换 |
| 创建向导 | 创建模板改为 Step 向导（基本信息 → 内容 → 预览 → 提交） |
| 发送面板 | 行内展开发送面板（选账号/号码/变量 → 发送） |
| 统计摘要 | 每行末尾显示发送量/成功率（小字） |

---

### PR-012：Meta 账户（MetaAccountsPage）重构

- **当前**: 1208 行（最大页面）
- **目标**: < 500 行
- **估计耗时**: 60 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 账户卡片视图 | 默认用卡片网格展示（每个账户一张卡），点击切换列表视图 |
| 健康指示 | 每张卡片顶部: Token 状态灯 + Webhook 状态灯 + AI 开关 |
| 快速操作 | 卡片上: [接入号码] [AI 开关] [查看号码] |
| 详情 Tab | 点击卡片展开详情: 号码列表 / Webhook / 统计 / 日志 |
| Embedded Signup | 单独 Tab 页，简化为"一键接入"按钮 |

---

### PR-013：媒体库（MediaLibraryPage）重构

- **当前**: 941 行
- **目标**: < 350 行
- **估计耗时**: 45 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 缩略图网格 | 图片类资产用网格缩略图展示（3-4 列） |
| 筛选简化 | 类型下拉 + 账号下拉 + 搜索框 |
| 上传改进 | 拖拽上传区域固定在页面顶部 |
| 详情弹窗 | 点击缩略图 → Modal 显示大图 + 元数据 + 引用列表 |

---

### PR-014：系统设置（SettingsPage）重构

- **当前**: 853 行
- **目标**: < 400 行
- **估计耗时**: 45 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| Tab 分区 | [AI 配置] [知识库] [运行时开关] [账号配置] |
| AI 配置 | 三级开关可视化: 全局→账号→会话（树状展示） |
| 知识库 | 表格 + 内联编辑（不用弹窗） |
| 运行时开关 | 开关矩阵（账号 × 开关项），一目了然 |

---

## Phase 5：系统/运维页（P1）

### PR-015：监控健康（MonitoringPage）重构

- **当前**: 505 行
- **目标**: < 250 行
- **估计耗时**: 30 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 状态灯 | 5 个服务状态灯（App/Worker/DB/Redis/Queue） |
| 指标卡片 | 6 个关键指标（QPS/错误率/队列深度/AI延迟/DB连接/内存） |
| 告警列表 | 最近 10 条告警（彩色标记严重程度） |

---

### PR-016：用户管理（UsersPage）重构

- **当前**: 1000 行
- **目标**: < 400 行
- **估计耗时**: 45 分钟

#### 重设计要点

| 改进 | 说明 |
|------|------|
| 使用 useTablePage | 统一分页/筛选 |
| 创建简化 | 创建用户改为 Modal（不再全页表单） |
| 用户卡片 | 点击展开: 会员状态 / 关联会话 / 工单 / 提现 |
| 批量操作 | 批量禁用/启用 |

---

### PR-017：其余系统页统一套壳

- **估计耗时**: 60 分钟
- **覆盖页面**: AlertsPage, AuditPage, ProviderEventsPage, ReportsPage, ImportExportPage, OperationsCenterPage, WhatsAppStatsPage

#### 统一改造

对每个页面执行最小改动：
1. 用 `PageShell` 替换页面顶部
2. 用 `usePageData` 替换 useState+useEffect
3. 用 `showSuccess/showError` 替换自定义 Alert
4. 移除 `AdminDataSourceLegend`
5. 添加 `EmptyGuide` 空状态

每个页面减少 50-100 行。

---

### PR-018：安全/治理页统一套壳

- **估计耗时**: 45 分钟
- **覆盖页面**: SecuritySettingsPage, IdentitySyncPage, MemberAccessPage, AccessControlPage, OrganizationSettingsPage, RolesPage, RiskCenterPage, SitesPage

#### 统一改造

同 PR-017 模式：PageShell + usePageData + showSuccess/showError + EmptyGuide。

---

## Phase 6：收尾 + 测试（P0）

### PR-019~024：各页面测试更新

| 任务 | 测试文件 | 预期用例数 |
|------|---------|-----------|
| PR-019 | dashboardPage.test.tsx | 8+ |
| PR-020 | assignmentsPage.test.tsx（新增） | 6+ |
| PR-021 | ticketsPage.test.tsx（新增） | 6+ |
| PR-022 | templatePage.test.tsx（更新） | 6+ |
| PR-023 | metaAccountsPage.test.tsx（更新） | 6+ |
| PR-024 | usersPage.test.tsx（新增） | 5+ |

### PR-025：全量验证

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
npm run test -- --environment jsdom
```

#### 验收标准

| 项 | 预期 |
|----|------|
| npm run build | 通过 |
| 全部测试 | 不退化 |
| 所有页面使用 PageShell | 确认 |
| 所有 ProTable 页使用 useTablePage | 确认 |
| 所有危险操作使用 DangerButton | 确认 |
| 最大页面行数 | < 500 |
| AdminDataSourceLegend | 全部移除 |

---

## 2. 全局约束

1. **不碰 H5**: 不改 `h5-member/` 目录
2. **不改后端**: 不改 `app/` 目录
3. **保持 real/mock 分层**
4. **保持 prefill 跳转机制**
5. **保持 chatRealtime 集成**
6. **ChatPage 不改动**（已在 CW 轮完成重构）
7. **进度文件**: `.codex-run/progress/PR-XXX.json`
8. **单任务最大执行 90 分钟**
9. **每次改动后 `npm run build` 必须通过**
10. **一次性执行全部任务，不中途暂停确认**
