# H5 会员端前端任务清单（H5 Frontend Agent 专用）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**

---

## 0. 当前 H5 会员端状态

### 代码规模

| 文件 | 行数 | 说明 |
|------|------|------|
| `frontend/src/pages/H5App.tsx` | 3626 | 核心巨石页面，包含所有 H5 页面 |
| `frontend/src/services/h5Member.ts` | 2753 | H5 服务层（API + mock fallback） |
| `frontend/src/services/h5.ts` | 2174 | 旧 H5 服务层（任务/工单） |
| `frontend/src/styles.css` | - | H5 + 其他混合样式 |

### 已实现的 18+ 路由

| 路由 | 页面 | 状态 |
|------|------|------|
| `/h5/login` | 登录 | 可用（手机号+密码） |
| `/h5/register` | 注册 | 可用 |
| `/h5/home` | 首页 | 可用（金额总览+高频入口） |
| `/h5/tasks` | 任务列表 | 可用（任务包中心） |
| `/h5/tasks/:id` | 任务详情 | 可用（3秒购买状态流） |
| `/h5/messages` | 消息中心 | 可用（顶部浮动 toast） |
| `/h5/me` | 我的 | 可用（紧凑双余额+常用入口） |
| `/h5/me/settings` | 个人设置 | 可用（头像/手机/密码） |
| `/h5/recharge` | 充值 | 可用（充值渠道弹层） |
| `/h5/withdraw` | 提现 | 可用（一键转入） |
| `/h5/orders` | 订单列表 | 可用 |
| `/h5/tickets` | 工单列表 | 可用 |
| `/h5/tickets/new` | 新建工单 | 可用 |
| `/h5/tickets/:id` | 工单详情 | 可用 |
| `/h5/fragments` | 碎片背包 | 可用（mock 为主） |
| `/h5/leaderboard` | 排行榜 | 可用 |
| `/h5/promotion` | 推广 | 可用（mock 为主） |
| `/h5/verification` | 会员认证 | 可用 |
| `/h5/whatsapp` | WhatsApp 绑定 | 占位 |

### 已定的产品决策（不要回退）

1. **原生 App 型** — 底部固定四菜单（首页/任务/消息/我的），不要网页大 Hero
2. **钱包分离** — 充值页/提现页独立，不是"钱包中心"
3. **个人页结构** — 头像点进设置、认证从状态按钮进入、去重入口
4. **通知体验** — 顶部浮出 toast，不下压页面，带进度条，自动消失
5. **双余额** — 系统余额（充值/购买/提现）+ 任务余额（任务入账→转系统余额）
6. **商务蓝 + 浅灰白** 色调
7. **H5 正式身份由服务端会话推导** — 不信任前端传作用域

### 已知问题

1. `H5App.tsx` 3626 行 — 路由解析、状态、视图、表单、动画全混一起
2. `styles.css` 混合 H5 和后台样式
3. 大量中文文案硬编码在 JSX 中
4. 部分能力仍依赖 mock/localStorage fallback
5. 产品方向要支持英文（中文更短，布局要预留）

### 已知约束（不要违反）

1. **不改后台页面**: 不动非 H5 的后台页面
2. **不改后端代码**: 不改 app/ 目录
3. **保持 mock fallback**: 后端不可用时仍能开发
4. **保持底部四菜单**: 不改回顶部一级导航
5. **保持 prefill 跳转**: 不破坏已有机制
6. **构建验证**: 每次改动后 `npm run build` 必须通过
7. **`/h5/wallet` 兼容**: 映射到 recharge，不要删除兼容

---

## 1. 执行编排

```
Phase 1 - H5App.tsx 组件拆分（P0，最高优先）:
  H5-001 (拆 ProfilePage/SettingsPage)     ── frontend_agent
  H5-002 (拆 RechargePage/WithdrawPage)    ── frontend_agent    ← 依赖 H5-001
  H5-003 (拆 PromotionPage/FragmentsPage)  ── frontend_agent    ← 依赖 H5-002
  H5-004 (拆 AuthPages/TicketsPage)        ── frontend_agent    ← 依赖 H5-003
  H5-005 (拆分验证)                         ── testing_agent     ← 依赖 H5-004

Phase 2 - i18n 文案抽取（P1）:
  H5-006 (抽取中文文案常量)                 ── frontend_agent
  H5-007 (i18n 基础框架)                    ── frontend_agent    ← 依赖 H5-006

Phase 3 - 样式整理（P1）:
  H5-008 (H5 样式独立)                      ── frontend_agent

Phase 4 - 后端 API 对接（P1，配合后端完成）:
  H5-009 (认证对接加固)                     ── frontend_agent
  H5-010 (钱包/交易对接)                    ── frontend_agent    ← 依赖后端
  H5-011 (碎片/邮寄对接)                    ── frontend_agent    ← 依赖后端

Phase 5 - UX 收口（P2）:
  H5-012 (二级页统一风格)                    ── frontend_agent
  H5-013 (错误处理与空状态)                  ── frontend_agent

Phase 6 - 最终验证:
  H5-014 (全量验证)                         ── testing_agent     ← 依赖所有
```

---

## 2. 任务详情

### H5-001：拆分 ProfilePage + SettingsPage

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 45 分钟

#### 目标

从 `H5App.tsx` 中抽出"我的"页和"个人设置"页为独立组件，保持功能不变。

#### 操作步骤

1. **新建目录**: `frontend/src/pages/h5-member/`

2. **新建 `frontend/src/pages/h5-member/ProfilePage.tsx`**
   - 从 H5App.tsx 中提取 `/h5/me` 对应的视图代码
   - 包含：左对齐头像信息区、紧凑双余额区、常用入口、退出登录
   - Props 接收所需状态和回调

3. **新建 `frontend/src/pages/h5-member/SettingsPage.tsx`**
   - 从 H5App.tsx 中提取 `/h5/me/settings` 对应的视图代码
   - 包含：头像上传、手机号修改、密码修改

4. **修改 `H5App.tsx`**
   - import 新组件
   - 在对应路由处渲染新组件
   - 删除已提取的内联代码
   - 保留路由解析和全局状态

#### 涉及文件

- **新增**: `frontend/src/pages/h5-member/ProfilePage.tsx`
- **新增**: `frontend/src/pages/h5-member/SettingsPage.tsx`
- **新增**: `frontend/src/pages/h5-member/index.ts`（导出汇总）
- **修改**: `frontend/src/pages/H5App.tsx`（减少 ~400 行）

#### Shell 命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
```

#### 验收标准

1. `/h5/me` 页面功能不变
2. `/h5/me/settings` 页面功能不变
3. H5App.tsx 减少约 400 行
4. 新组件有清晰 Props 定义
5. 构建通过

#### 重试策略

- 最大重试: 3 次
- 失败回滚: 恢复 H5App.tsx 原始内容

---

### H5-002：拆分 RechargePage + WithdrawPage

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: H5-001
- **估计耗时**: 45 分钟

#### 目标

从 H5App.tsx 中抽出充值页和提现页。

#### 操作

1. **新建 `frontend/src/pages/h5-member/RechargePage.tsx`**
   - 输入充值金额、金额快捷选择、充值渠道弹层、历史充值明细

2. **新建 `frontend/src/pages/h5-member/WithdrawPage.tsx`**
   - 双余额展示、一键转入确认弹层、提现金额输入、历史提现明细

3. **修改 H5App.tsx**
   - 替换内联代码为组件引用

#### 涉及文件

- **新增**: `frontend/src/pages/h5-member/RechargePage.tsx`
- **新增**: `frontend/src/pages/h5-member/WithdrawPage.tsx`
- **修改**: `frontend/src/pages/H5App.tsx`（减少 ~500 行）

#### 验收标准

1. `/h5/recharge` 功能不变
2. `/h5/withdraw` 功能不变
3. `/h5/wallet` 兼容映射不变
4. H5App.tsx 再减约 500 行
5. 构建通过

---

### H5-003：拆分 PromotionPage + FragmentsPage

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: H5-002
- **估计耗时**: 45 分钟

#### 操作

1. **新建 `frontend/src/pages/h5-member/PromotionPage.tsx`**
   - 推广码复制、推广人数列表

2. **新建 `frontend/src/pages/h5-member/FragmentsPage.tsx`**
   - 背包、掉落记录、合成进度、兑换、邮寄状态

3. **修改 H5App.tsx**

#### 涉及文件

- **新增**: `frontend/src/pages/h5-member/PromotionPage.tsx`
- **新增**: `frontend/src/pages/h5-member/FragmentsPage.tsx`
- **修改**: `frontend/src/pages/H5App.tsx`（减少 ~400 行）

#### 验收标准

1. `/h5/promotion` 功能不变
2. `/h5/fragments` 功能不变
3. 构建通过

---

### H5-004：拆分 AuthPages + TicketsPage

- **角色**: frontend_agent
- **优先级**: P0
- **前置依赖**: H5-003
- **估计耗时**: 45 分钟

#### 操作

1. **新建 `frontend/src/pages/h5-member/LoginPage.tsx`**
2. **新建 `frontend/src/pages/h5-member/RegisterPage.tsx`**
3. **新建 `frontend/src/pages/h5-member/TicketsPage.tsx`**
   - 工单列表、新建工单、工单详情
4. **新建 `frontend/src/pages/h5-member/HomePage.tsx`**
   - 金额总览、高频入口、会员认证摘要、次级入口、最近动态
5. **新建 `frontend/src/pages/h5-member/TasksPage.tsx`**
   - 任务包列表、任务详情、3秒购买状态流
6. **新建 `frontend/src/pages/h5-member/MessagesPage.tsx`**
   - 消息流、全部已读、浮动 toast

#### 涉及文件

- **新增**: 6 个新页面组件
- **修改**: `frontend/src/pages/H5App.tsx`（目标减少到 < 1000 行，只保留路由壳和全局状态）

#### 验收标准

1. 所有路由功能不变
2. H5App.tsx 最终 < 1000 行
3. 只保留：路由解析、底部 Tab、全局状态管理、toast 容器
4. 构建通过

---

### H5-005：拆分验证

- **角色**: testing_agent
- **前置依赖**: H5-004
- **估计耗时**: 20 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
npm run test -- src/services/h5Member.test.ts
npm run test -- src/services/h5.test.ts
```

#### 验收标准

1. 构建通过
2. h5Member.test.ts 全部通过
3. h5.test.ts 全部通过
4. 所有 18+ 路由可访问（如果可本地运行）
5. H5App.tsx 行数 < 1000

---

### H5-006：抽取中文文案常量

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: H5-005（拆分完成后）
- **估计耗时**: 45 分钟

#### 目标

将 H5 页面中硬编码的中文文案抽取为常量文件，为后续 i18n 做准备。

#### 操作步骤

1. **新建 `frontend/src/pages/h5-member/i18n/zh-CN.ts`**

```typescript
// 示例结构
export const zhCN = {
  common: {
    confirm: '确认',
    cancel: '取消',
    loading: '加载中...',
    error: '出错了',
    retry: '重试',
    back: '返回',
  },
  auth: {
    login: '登录',
    register: '注册',
    phone: '手机号',
    password: '密码',
    confirmPassword: '确认密码',
    logout: '退出登录',
  },
  home: {
    systemBalance: '系统余额',
    taskBalance: '任务余额',
    recharge: '充值',
    withdraw: '提现',
    transferIn: '一键转入',
    // ...
  },
  tasks: {
    taskCenter: '任务中心',
    purchase: '购买',
    creatingOrder: '创建订单',
    paying: '正在付款',
    paymentSuccess: '付款成功',
    taskComplete: '任务完成',
    // ...
  },
  // ... 其他页面
};
```

2. **新建 `frontend/src/pages/h5-member/i18n/index.ts`**
   - 导出当前语言对应的文案
   - 预留英文接口

3. **修改各拆分后的页面组件**
   - 将 JSX 中的中文替换为文案常量引用

#### 涉及文件

- **新增**: `frontend/src/pages/h5-member/i18n/zh-CN.ts`
- **新增**: `frontend/src/pages/h5-member/i18n/en.ts`（占位）
- **新增**: `frontend/src/pages/h5-member/i18n/index.ts`
- **修改**: 各拆分后的页面组件

#### 验收标准

1. JSX 中不再有硬编码中文（除少量注释）
2. 所有文案集中在 zh-CN.ts
3. 页面显示文案不变
4. en.ts 有基础结构（可留空值）
5. 构建通过

---

### H5-007：i18n 基础框架

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: H5-006
- **估计耗时**: 30 分钟

#### 目标

建立基础的 i18n 切换能力，当前默认中文，后期可切英文。

#### 操作

1. 新增 i18n context/hook
2. 支持通过 URL 参数或 localStorage 切换语言
3. 组件宽度、间距考虑英文更长的情况
4. 按钮长度预留英文空间

#### 验收标准

1. 默认中文显示不变
2. 切换机制可用（即使英文翻译未完善）
3. 布局不会因英文文案而溢出
4. 构建通过

---

### H5-008：H5 样式独立

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: H5-005
- **估计耗时**: 45 分钟

#### 当前问题

`frontend/src/styles.css` 混合了 H5 样式和后台样式。H5 相关类包括：
- `.h5-member-toast-stack`
- `.h5-member-password-field`
- `.h5-member-profile-overview`
- `.h5-member-tabbar`
- 等

#### 操作

1. **新建 `frontend/src/styles/h5-member.css`**
   - 将所有 `.h5-*` 前缀的类移入此文件
   - 清理已无用的旧 H5 选择器

2. **修改 `frontend/src/styles.css`**
   - 删除已迁移的 H5 样式

3. **修改 `H5App.tsx` 或 `main.tsx`**
   - import 新样式文件

#### 涉及文件

- **新增**: `frontend/src/styles/h5-member.css`
- **修改**: `frontend/src/styles.css`
- **修改**: `frontend/src/pages/H5App.tsx` 或 `frontend/src/main.tsx`

#### 验收标准

1. H5 样式独立文件
2. styles.css 中不再有 `.h5-*` 选择器
3. H5 页面显示不变
4. 后台页面显示不变
5. 构建通过

---

### H5-009：认证对接加固

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 后端完成
- **估计耗时**: 30 分钟

#### 需要加固的内容

1. **登录/注册流程**
   - 确保走正式后端 API（`/api/h5/auth/login`、`/api/h5/auth/register`）
   - Cookie/session 处理
   - 401 时 refresh retry
   - 网络错误时 fallback 到 mock

2. **认证态保持**
   - `credentials: include` 确认
   - 刷新页面后认证态恢复
   - 登出清理

3. **Token 过期处理**
   - 自动 refresh
   - refresh 失败 → 跳登录页

#### 涉及文件

- **修改**: `frontend/src/services/h5Member.ts`
- **修改**: 拆分后的 LoginPage / RegisterPage

#### 验收标准

1. 后端可用时走真实 API
2. 后端不可用时走 mock
3. Token 过期自动刷新
4. 构建通过

---

### H5-010：钱包/交易对接

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 后端完成
- **估计耗时**: 30 分钟

#### 需要对接的 API

- `/api/h5/wallet` — 余额查询
- `/api/h5/wallet/transactions` — 交易记录
- `/api/h5/wallet/recharges` — 充值
- `/api/h5/wallet/transfers` — 余额划转
- `/api/h5/withdrawals` — 提现
- `/api/h5/withdraw-leaderboard` — 排行榜

#### 验收标准

1. 后端可用时展示真实数据
2. 充值/提现操作可完成
3. 交易记录分页加载
4. 构建通过

---

### H5-011：碎片/邮寄对接

- **角色**: frontend_agent
- **优先级**: P1
- **前置依赖**: 后端完成
- **估计耗时**: 20 分钟

#### 需要对接的 API

- `/api/h5/fragments` — 碎片背包
- `/api/h5/fragments/check-in` — 签到
- `/api/h5/fragments/exchanges` — 兑换
- `/api/h5/rewards/shipping` — 邮寄状态

#### 验收标准

1. 碎片数据从后端获取
2. 签到/兑换操作可完成
3. 邮寄状态可查
4. 构建通过

---

### H5-012：二级页统一风格

- **角色**: frontend_agent
- **优先级**: P2
- **前置依赖**: H5-005
- **估计耗时**: 30 分钟

#### 需要统一的页面

- 充值页
- 提现页
- 设置页
- 认证页
- WhatsApp 绑定页
- 工单页

#### 统一项

1. 顶部信息栏高度、间距、字号
2. 返回按钮样式
3. 操作按钮风格
4. 空状态展示
5. 加载状态展示

#### 验收标准

1. 所有二级页顶部栏一致
2. 按钮风格统一
3. 构建通过

---

### H5-013：错误处理与空状态

- **角色**: frontend_agent
- **优先级**: P2
- **前置依赖**: H5-009 ~ H5-011
- **估计耗时**: 30 分钟

#### 需要处理

1. **网络错误**
   - 统一错误提示（toast 而非 alert）
   - 重试按钮

2. **空状态**
   - 无订单 → 空状态插图
   - 无消息 → 空状态
   - 无碎片 → 空状态
   - 无工单 → 空状态

3. **表单验证**
   - 手机号格式
   - 密码强度
   - 金额范围
   - 实时验证反馈

#### 验收标准

1. 网络错误有友好提示
2. 空状态有占位图/文案
3. 表单有实时验证
4. 构建通过

---

### H5-014：全量验证

- **角色**: testing_agent
- **前置依赖**: 所有 H5 任务完成
- **估计耗时**: 30 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend
npm run build
npm run test -- src/services/h5Member.test.ts
npm run test -- src/services/h5.test.ts
```

#### 验收标准

1. **构建通过** — `npm run build` 无错误
2. **测试通过** — h5Member.test.ts、h5.test.ts 全部 PASS
3. **H5App.tsx 行数 < 1000**
4. **H5 样式独立文件存在**
5. **i18n 文案文件存在**
6. **所有 18+ 路由可访问**
7. **mock fallback 仍可用**
8. **无新增 TypeScript 错误**

---

## 3. 拆分后目标文件结构

```
frontend/src/pages/
├── H5App.tsx                    # < 1000 行：路由壳 + 底部 Tab + 全局状态 + toast
├── h5-member/
│   ├── index.ts                 # 导出汇总
│   ├── HomePage.tsx             # 首页
│   ├── LoginPage.tsx            # 登录
│   ├── RegisterPage.tsx         # 注册
│   ├── ProfilePage.tsx          # 我的
│   ├── SettingsPage.tsx         # 个人设置
│   ├── RechargePage.tsx         # 充值
│   ├── WithdrawPage.tsx         # 提现
│   ├── TasksPage.tsx            # 任务列表 + 详情
│   ├── MessagesPage.tsx         # 消息中心
│   ├── TicketsPage.tsx          # 工单（列表+新建+详情）
│   ├── FragmentsPage.tsx        # 碎片
│   ├── PromotionPage.tsx        # 推广
│   ├── VerificationPage.tsx     # 认证
│   ├── WhatsAppPage.tsx         # WhatsApp 绑定
│   ├── OrdersPage.tsx           # 订单
│   ├── LeaderboardPage.tsx      # 排行榜
│   └── i18n/
│       ├── index.ts             # i18n 入口
│       ├── zh-CN.ts             # 中文文案
│       └── en.ts                # 英文文案（占位）

frontend/src/styles/
├── admin.css                    # 后台样式（已有）
├── h5-member.css                # H5 样式（新增）
```

---

## 4. 全局约束

1. **不改后台页面**: 不动 DashboardPage、ChatPage 等后台组件
2. **不改后端代码**: 不改 app/ 目录
3. **保持 mock fallback**: `h5Member.ts` 的后端优先 + 本地 fallback 机制不删
4. **保持底部四菜单**: 不改导航结构
5. **保持已定的产品决策**: 钱包分离、个人页结构、通知 toast
6. **保持 `/h5/wallet` → recharge 兼容映射**
7. **H5 身份由服务端推导**: 不在前端硬编码身份
8. **考虑英文长度**: 布局预留空间
9. 进度文件: `.codex-run/progress/H5-XXX.json`
10. 单任务最大执行 60 分钟
11. 失败自动回滚 + 重试最多 3 次
12. 每次改动后 `npm run build` 必须通过
