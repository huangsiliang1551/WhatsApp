# 动态 AI 提供商管理 — 前端任务（AIPF-001 ~ AIPF-004）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-13
> **总架构师签发**
> **目标**: 在系统设置页实现 AI 提供商管理 UI（CRUD + 测试连接 + 优先级排序 + 账号覆盖）

---

## 背景

后端已实现 AI 提供商动态管理 API（`/api/ai-providers/*`）。前端需要在 SettingsPage 的 "AI 配置" Tab 中替换只读展示为完整管理界面。

支持的提供商类型: openai / deepseek / groq / ollama / together / custom（任何 OpenAI 兼容 API）。

---

## AIPF-001：类型定义 + API 封装（P0）

- **估计耗时**: 20 分钟

### 1.1 新增 `frontend/src/types/aiProviders.ts` (~60行)

```typescript
export interface AIProviderConfig {
  id: string;
  name: string;
  provider_type: string;     // openai | deepseek | groq | ollama | together | custom
  api_base_url: string | null;
  model: string;
  priority: number;
  is_enabled: boolean;
  timeout_seconds: number;
  use_responses_api: boolean;
  has_api_key: boolean;      // 仅 true/false，不暴露密钥
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAIProviderRequest {
  name: string;
  provider_type: string;
  api_base_url?: string | null;
  api_key?: string | null;
  model: string;
  priority?: number;
  is_enabled?: boolean;
  timeout_seconds?: number;
  use_responses_api?: boolean;
  metadata_json?: Record<string, unknown> | null;
}

export interface UpdateAIProviderRequest {
  name?: string;
  api_base_url?: string | null;
  api_key?: string | null;    // 不传则保留原密钥
  model?: string;
  priority?: number;
  is_enabled?: boolean;
  timeout_seconds?: number;
  use_responses_api?: boolean;
  metadata_json?: Record<string, unknown> | null;
}

export interface TestConnectionRequest {
  config_id?: string;         // 测试已有配置
  provider_type?: string;     // 或测试临时配置
  api_base_url?: string | null;
  api_key?: string | null;
  model?: string;
  timeout_seconds?: number;
}

export interface TestConnectionResponse {
  status: "ok" | "error";
  latency_ms: number | null;
  model_echoed: string | null;
  error_type: string | null;
  message: string | null;
}

export interface AccountOverride {
  account_id: string;
  provider_config_id: string;
  provider_name: string;
  model: string;
  is_active: boolean;
}
```

### 1.2 新增 `frontend/src/services/aiProviderApi.ts` (~80行)

```typescript
import { api } from "./api";

export async function listAIProviderConfigs(): Promise<AIProviderConfig[]>
export async function createAIProviderConfig(data: CreateAIProviderRequest): Promise<AIProviderConfig>
export async function updateAIProviderConfig(id: string, data: UpdateAIProviderRequest): Promise<AIProviderConfig>
export async function deleteAIProviderConfig(id: string): Promise<void>
export async function testAIProviderConnection(data: TestConnectionRequest): Promise<TestConnectionResponse>
export async function reorderAIProviders(orderedIds: string[]): Promise<void>
export async function listAccountOverrides(): Promise<AccountOverride[]>
export async function setAccountOverride(accountId: string, configId: string): Promise<void>
export async function clearAccountOverride(accountId: string): Promise<void>
```

### 验收标准

1. 类型文件存在且导出正确
2. API 函数可调用
3. `npm run build` 通过

---

## AIPF-002：AI 提供商管理 Tab 组件（P0）

- **估计耗时**: 90 分钟

### 新增 `frontend/src/pages/AIProvidersSettingsTab.tsx` (~400行)

#### UI 布局

```
┌─ AI 提供商管理 ─────────────────────────────────────────────┐
│                                                              │
│  ┌── Fallback 链 (按优先级排序) ──────────────────────────┐  │
│  │  1. 🟢 生产 DeepSeek    deepseek-chat    priority=0    │  │
│  │     base: https://api.deepseek.com/v1                  │  │
│  │     [编辑] [测试连接] [禁用]                            │  │
│  │                                                        │  │
│  │  2. 🟢 备用 OpenAI      gpt-5.4-mini    priority=10   │  │
│  │     base: (OpenAI 默认)                                │  │
│  │     [编辑] [测试连接] [禁用]                            │  │
│  │                                                        │  │
│  │  3. ⚫ 本地 Ollama       llama-3.3       priority=20   │  │
│  │     base: http://localhost:11434/v1                    │  │
│  │     [编辑] [测试连接] [启用]                            │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [+ 添加 AI 提供商]   [↻ 刷新]                              │
│                                                              │
│  ┌── 账号级覆盖 ─────────────────────────────────────────┐  │
│  │  acct-h5-daily-cn    → 生产 DeepSeek     [清除]       │  │
│  │  acct-h5-flash-sale  → 全局 Fallback      [设置]      │  │
│  │  acct-h5-mall-cn     → 全局 Fallback      [设置]      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

#### 添加/编辑 Modal

```
┌── 添加 AI 提供商 ────────────────────────┐
│                                           │
│  类型:  [deepseek ▼]                      │  ← 预设自动填充 base_url + model
│         (openai/deepseek/groq/ollama/     │
│          together/custom)                 │
│                                           │
│  名称:  [________________]               │
│  API Base URL: [https://api.deepseek.com/v1] │
│  API Key: [••••••••••••] (密码输入框)     │
│  模型:  [deepseek-chat]                   │
│  超时(秒): [30]                           │
│  优先级: [0]                              │
│  启用:  [✓]                               │
│  使用 Responses API: [☐] (仅OpenAI官方)   │
│                                           │
│  [🔌 测试连接]  结果: ✅ 成功 (230ms)      │
│                                           │
│              [取消]  [保存]               │
└───────────────────────────────────────────┘
```

#### 预设模板

```typescript
const PROVIDER_PRESETS: Record<string, { api_base_url: string; model: string; use_responses_api: boolean }> = {
  openai:   { api_base_url: "",                                    model: "gpt-5.4-mini",                  use_responses_api: true },
  deepseek: { api_base_url: "https://api.deepseek.com/v1",        model: "deepseek-chat",                 use_responses_api: false },
  groq:     { api_base_url: "https://api.groq.com/openai/v1",     model: "llama-3.3-70b-versatile",       use_responses_api: false },
  ollama:   { api_base_url: "http://localhost:11434/v1",          model: "llama3.3",                      use_responses_api: false },
  together: { api_base_url: "https://api.together.xyz/v1",        model: "meta-llama/Llama-3.3-70B-Instruct-Turbo", use_responses_api: false },
  custom:   { api_base_url: "",                                    model: "",                               use_responses_api: false },
};
```

选择类型时自动填充对应的 `api_base_url`、`model`、`use_responses_api`，用户仍可手动修改。

#### 组件结构

```
AIProvidersSettingsTab
├── ProviderChainList          — 按 priority 排序的卡片列表
│   └── ProviderCard           — 单个提供商: 状态灯 + 信息 + 操作按钮
├── AddProviderModal           — antd Modal + Form (创建/编辑复用)
│   ├── PresetSelector         — 类型下拉(自动填充)
│   ├── ConnectionTestButton   — 点击测试 + 内联结果显示
│   └── FormFields             — 其余表单字段
├── AccountOverrideSection     — 账号覆盖列表
│   └── OverrideRow            — 账号名 + 当前提供商 + 设置/清除按钮
└── EmptyState                 — 首次使用引导文案
```

#### 交互细节

1. **编辑**: 点击 [编辑] → 打开 Modal，回显所有字段（API Key 显示为 `••••••••`，placeholder "留空保留原密钥"）
2. **测试连接**: 点击 [测试连接] → 按钮 loading → 内联显示结果（✅ 成功 230ms / ❌ 失败: auth_failed）
3. **禁用/启用**: Popconfirm 确认后调用 PATCH
4. **删除**: DangerButton + Popconfirm "确认删除此 AI 提供商？"
5. **排序**: 通过 priority 数值控制，Modal 中可修改 priority 值
6. **账号覆盖**: [设置] 弹出 Select 选择提供商 → PUT；[清除] → DELETE

#### 数据加载

使用 `usePageData` Hook 加载 `listAIProviderConfigs()` + `listAccountOverrides()` + `listRuntimeState()`（获取账号列表）。

### 验收标准

1. 组件渲染正确
2. CRUD 操作可用
3. 测试连接按钮可点击并显示结果
4. 预设模板自动填充
5. 账号覆盖可设置/清除
6. `npm run build` 通过

---

## AIPF-003：SettingsPage 集成（P0）

- **估计耗时**: 15 分钟

### 修改 `frontend/src/pages/SettingsPage.tsx`

替换 "AI 配置" Tab 的内容：

**改动前** (当前):
```tsx
{
  key: "ai",
  label: "AI 配置",
  children: (
    <Row gutter={[16, 16]}>
      <Col span={12}><Card size="small" title="AI 提供商">...只读 Tag...</Card></Col>
      <Col span={12}><Card size="small" title="翻译配置">...只读 Tag...</Card></Col>
    </Row>
  ),
},
```

**改动后**:
```tsx
{
  key: "ai",
  label: "AI 配置",
  children: <AIProvidersSettingsTab />,
},
```

**保留**: 翻译配置卡片可以移入 "系统信息" Tab 或作为 AI 配置 Tab 底部的小卡片保留。

### 验收标准

1. SettingsPage "AI 配置" Tab 显示管理界面
2. 翻译配置信息仍可查看
3. `npm run build` 通过

---

## AIPF-004：全量验证（P0）

- **估计耗时**: 15 分钟

```powershell
cd E:\codex\WhatsApp\frontend

# 类型检查
npx tsc --noEmit

# 构建
npm run build

# 现有测试不退化
npx vitest run --environment jsdom src/pages/admin-chat.test.tsx
npx vitest run --environment jsdom src/pages/dashboardPage.test.tsx
npx vitest run --environment jsdom src/services/operations.test.ts
npx vitest run --environment jsdom src/pages/loginPage.test.tsx
```

### 最终验收清单

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | tsc --noEmit | 0 errors |
| 2 | npm run build | 通过 |
| 3 | 现有测试 | 不退化 |
| 4 | AI 配置 Tab | CRUD 可用 |
| 5 | 预设模板 | 6 种类型自动填充 |
| 6 | 测试连接 | 按钮可用 + 结果显示 |
| 7 | 账号覆盖 | 设置/清除可用 |

---

## 全局约束

1. **不碰后端代码**: 不改 `app/` 目录
2. **不碰 H5**: 不改 `h5-member/` 目录
3. **保持 real/mock 分层**
4. **使用现有组件模式**: PageShell, usePageData, DangerButton
5. **API Key 不存储在前端**: 仅传 `has_api_key: bool`
6. **每次改动后 `npm run build` 必须通过**
7. **进度文件**: `.codex-run/progress/AIPF-XXX.json`
8. **一次性执行全部任务，不中途暂停**

---

## 文件清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `frontend/src/types/aiProviders.ts` | 新增 | ~60 |
| `frontend/src/services/aiProviderApi.ts` | 新增 | ~80 |
| `frontend/src/pages/AIProvidersSettingsTab.tsx` | 新增 | ~400 |
| `frontend/src/pages/SettingsPage.tsx` | 修改 | ~20 |
| **总计** | | **~560** |
