# 管理后台上线级任务清单（AF3-001 ~ AF3-25）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: 管理后台达到**可上线标准**，全部功能闭环

---

## 0. 项目现状摘要

### 已完成（R1 + R2）

| 模块 | 状态 | 关键产出 |
|------|------|---------|
| Chat 工作台 | ✅ | 人工接管 UI + AI 三级开关 + 4 子组件拆分（ChatPage 309行） |
| 模板管理 | ✅ | CRUD + 审核 + 发送 + 统计 |
| Meta 账户 | ✅ | Embedded Signup + AI 开关 + Token/Webhook 健康 |
| 系统治理 | ✅ | Notifications / OrgSettings / AccessControl / Security / IdentitySync / MemberAccess / Roles |
| 协同页面 | ✅ | Assignments / Tickets / Members / Reviews |
| Dashboard | ✅ | 5+ 可视化面板（饼图/折线/Gauge/面积） |
| 运营中心 | ✅ | 跨页联动 + 时间维度 + 告警摘要 |
| 证据中心 | ✅ | 筛选 + 详情 + 导出 |
| 测试覆盖 | ✅ | 4 个测试文件 36 用例 |
| Chunk 优化 | ✅ | vendor 拆分（react/antd/pro-table/axios/dayjs） |

### 未完成 / 待上线加固

| 缺失项 | 影响 |
|--------|------|
| 无登录页面 | 无法与 Admin JWT 对接 |
| 无 Token 管理（Axios interceptor） | 后台 API 无法认证 |
| 各页面大量 mock/hybrid 状态 | 数据不真实 |
| Chat 无实时推送 | 需手动刷新 |
| 无 WebSocket / SSE | 新消息延迟 |
| 无批量操作（模板/会话/用户） | 运营效率低 |
| 无数据导出（CSV/Excel） | 无法离线分析 |
| 无全局搜索 | 大量页面难以定位 |
| vendor-antd 1,387 KB（gzip 437 KB） | 首屏慢 |
| 无暗色模式 | 可选功能 |
| 无响应式适配 | 平板/大屏体验差 |
| 无错误上报 | 前端错误不可见 |
| 无操作确认防误触 | 危险操作无二次确认 |

---

## 1. 执行编排（7 Phase，预计 3-4 天）

```
Day 1:
  Phase 1（认证体系，P0）: AF3-001~004
  Phase 2（Chat 实时对接，P0）: AF3-005~007

Day 2:
  Phase 3（业务页面 API 对接，P0）: AF3-008~012
  Phase 4（运营效率工具，P1）: AF3-013~016

Day 3:
  Phase 5（用户体验加固，P1）: AF3-017~020
  Phase 6（性能优化，P1）: AF3-021~022

Day 4:
  Phase 7（测试 + 验证，P0）: AF3-023~025
```

---

## Phase 1：认证体系（P0）

### AF3-001：登录页面

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

管理后台登录页，与后端 Admin JWT 认证对接。

#### 实现要求

1. **新增 `frontend/src/pages/LoginPage.tsx`**
   - 蓝灰主题（与现有管理后台一致）
   - 居中卡片布局
   - 用户名 + 密码表单
   - 「记住登录」checkbox
   - 登录按钮 + loading 状态
   - 错误提示（密码错误/账号锁定/网络错误）
   - Logo + 系统名称

2. **新增 `frontend/src/services/adminAuth.ts`**
   ```typescript
   class AdminAuthService {
     async login(username: string, password: string): Promise<AdminTokens>
     async refresh(): Promise<AdminTokens>
     async logout(): Promise<void>
     async getMe(): Promise<AdminUser>
     isAuthenticated(): boolean
     getAccessToken(): string | null
   }
   ```

3. **路由配置**
   - `/login` → LoginPage
   - 未认证访问其他页面 → 重定向 `/login?redirect=xxx`
   - 登录成功 → 跳转 redirect 或 `/`

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/LoginPage.tsx` | 新增 |
| `frontend/src/services/adminAuth.ts` | 新增 |
| `frontend/src/App.tsx` | 修改（路由守卫 + 登录重定向） |

#### 验收标准

1. 登录页面渲染正确
2. 登录成功跳转 Dashboard
3. 登录失败显示错误
4. 未认证自动跳转登录

---

### AF3-002：Token 拦截器

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 实现要求

1. **`frontend/src/services/api.ts`（2755 行）** Axios interceptor 增强
   - 请求拦截: 附加 `Authorization: Bearer {token}`
   - 响应拦截: 401 → 尝试 refresh → 重试 → 失败跳 `/login`
   - 并发 401 只触发一次 refresh
   - refresh 期间其他请求排队

2. **Token 存储**
   - access_token: 内存（不持久化，防止 XSS）
   - refresh_token: HttpOnly cookie（后端设置）
   - 「记住登录」: access_token 存 localStorage（可选）

3. **登出清理**
   - 清除 access_token
   - 调用 `POST /api/admin/auth/logout`
   - 跳转 `/login`

#### 验收标准

1. 所有请求带 Authorization header
2. 401 自动续期
3. 并发请求只触发一次 refresh

---

### AF3-003：路由守卫 + 权限控制

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 实现要求

1. **`frontend/src/App.tsx`** 增强
   - 全局路由守卫: 检查认证状态
   - 公开路由白名单: `/login`, `/health`
   - 角色检查: 根据 AdminUser.role 控制页面访问
     - `admin`: 全部页面
     - `operator`: 排除 Settings / OrgSettings / AccessControl / Security
     - `agent`: 仅 Chat / Conversations / Customers / Tickets

2. **无权限页面**
   - 显示「您没有权限访问此页面」+ 返回按钮

#### 验收标准

1. 未认证跳登录
2. 无权限显示提示
3. 角色控制生效

---

### AF3-004：用户信息 Header

- **优先级**: P1
- **估计耗时**: 20 分钟

#### 实现要求

1. **ProLayout rightContentRender** 增强
   - 显示当前用户名 + 角色标签
   - 头像（默认头像）
   - 下拉菜单: 个人信息 / 修改密码 / 退出登录
   - 退出登录 → 清除 token → 跳 `/login`

#### 验收标准

1. Header 显示用户信息
2. 退出登录可用
3. 修改密码弹窗可用

---

## Phase 2：Chat 实时对接（P0）

### AF3-005：Chat API 对接（替换 mock）

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 替换清单

| 功能 | 当前状态 | 替换为 |
|------|---------|--------|
| 会话列表 | hybrid/mock | `GET /api/conversations?account_id=X&status=Y` |
| 消息历史 | mock | `GET /api/conversations/{id}/messages` |
| 发送消息 | mock | `POST /api/conversations/{id}/messages` |
| 人工接管 | mock | `POST /api/conversations/{id}/handover` |
| 恢复 AI | mock | `POST /api/conversations/{id}/restore-ai` |
| AI 开关 | mock | `PUT /api/runtime/ai-switch/{account_id}/{conversation_id}` |
| 坐席列表 | mock | `GET /api/agents?account_id=X` |
| 坐席在线状态 | mock | `GET /api/agents/presence?account_id=X` |

#### 实现要求

1. 保持 mock fallback（`VITE_API_MODE=mock`）
2. 真实 API 优先
3. 错误处理: 网络错误 → toast 提示 + 重试按钮
4. 加载状态: 骨架屏 / spinner

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/ChatPage.tsx` | 修改（API 对接） |
| `frontend/src/pages/admin-chat/*.tsx` | 修改（API 对接） |
| `frontend/src/services/api.ts` | 新增会话/消息相关 API 函数 |

#### 验收标准

1. 会话列表从后端加载
2. 消息收发通过后端
3. 接管/恢复 AI 后端生效
4. mock 模式仍可用

---

### AF3-006：Chat WebSocket / SSE 实时推送

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 目标

新消息实时推送到前端，无需手动刷新。

#### 实现要求

1. **新增 `frontend/src/services/chatRealtime.ts`**
   ```typescript
   class ChatRealtimeService {
     connect(token: string): void
     disconnect(): void
     onMessage(callback: (msg: NewMessageEvent) => void): void
     onStatusChange(callback: (event: StatusChangeEvent) => void): void
     onHandover(callback: (event: HandoverEvent) => void): void
   }
   ```

2. **连接方式**: SSE（Server-Sent Events）优先
   - 连接: `GET /api/conversations/stream` (EventSource)
   - 事件类型: `new_message`, `status_change`, `handover`, `ai_reply`
   - 断线自动重连（指数退避 1s→2s→4s→8s→max 30s）

3. **集成到 ChatPage**
   - 新消息到达 → 追加到消息列表
   - 状态变化 → 更新会话卡片
   - 接管事件 → 更新 HandoverControls

4. **后端依赖**
   - 如果后端尚未实现 SSE，先用轮询（5 秒间隔）作为 fallback
   - 检测到 SSE 可用后自动切换

#### 验收标准

1. 新消息实时显示
2. 断线自动重连
3. 轮询 fallback 可用

---

### AF3-007：Chat 多会话并发

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

支持客服人员同时处理多个会话。

#### 实现要求

1. **会话标签页**
   - 可打开多个会话标签（类似浏览器标签页）
   - 标签显示: 用户名 + 模式标签（AI/人工）+ 未读计数
   - 活跃标签高亮
   - 关闭标签

2. **新消息通知**
   - 非活跃标签有新消息 → 标签显示红点 + 未读数
   - 全局通知 badge

3. **快捷键**
   - `Ctrl+1/2/3` 切换标签
   - `Ctrl+W` 关闭当前标签
   - `Enter` 发送消息（Shift+Enter 换行）

#### 验收标准

1. 多标签可切换
2. 未读计数正确
3. 快捷键可用

---

## Phase 3：业务页面 API 对接（P0）

### AF3-008：模板管理 API 对接

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 替换清单

| 功能 | 当前 | 替换为 |
|------|------|--------|
| 模板列表 | mock | `GET /api/templates?account_id=X` |
| 创建模板 | mock | `POST /api/templates` |
| 编辑模板 | mock | `PUT /api/templates/{id}` |
| 删除模板 | mock | `DELETE /api/templates/{id}` |
| 审核模板 | mock | `POST /api/templates/{id}/approve` |
| 发送模板 | mock | `POST /api/templates/{id}/send` |
| 发送记录 | mock | `GET /api/templates/{id}/send-logs` |
| 模板统计 | mock | `GET /api/templates/{id}/stats` |
| Meta 同步 | mock | `POST /api/templates/{id}/sync-meta` |

#### 验收标准

1. CRUD 全链路后端生效
2. 发送记录从后端加载
3. mock 模式仍可用

---

### AF3-009：Meta 账户 API 对接

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 替换清单

| 功能 | 当前 | 替换为 |
|------|------|--------|
| 账户列表 | mock | `GET /api/meta/accounts` |
| 创建账户 | mock | `POST /api/meta/accounts` |
| 账户详情 | mock | `GET /api/meta/accounts/{id}` |
| AI 开关 | mock | `PUT /api/meta/accounts/{id}/ai-switch` |
| Embedded Signup | mock | `POST /api/meta/embedded-signup/start` |
| Webhook 状态 | mock | `GET /api/meta/accounts/{id}/webhooks` |
| Token 状态 | mock | `GET /api/meta/accounts/{id}/health` |

#### 验收标准

1. 账户管理后端生效
2. AI 开关后端生效
3. Token/Webhook 健康真实数据

---

### AF3-010：会话管理 + 客户页面 API 对接

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 替换清单

| 页面 | 替换内容 |
|------|---------|
| ConversationsPage | 会话列表/详情/筛选从后端加载 |
| CustomersPage | 客户列表/详情/统计从后端加载 |
| MembersPage | 会员列表/详情从后端加载 |

#### 验收标准

1. 各列表页真实数据
2. 筛选/搜索/分页后端驱动
3. 客户详情聚合数据正确

---

### AF3-011：坐席 + 分配页面 API 对接

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 替换清单

| 功能 | 当前 | 替换为 |
|------|------|--------|
| 坐席列表 | mock | `GET /api/agents?account_id=X` |
| 创建坐席 | mock | `POST /api/agents` |
| 坐席在线状态 | mock | `GET /api/agents/presence` |
| 分配规则 | mock | `GET /api/assignments/rules` |
| 修改规则 | mock | `PUT /api/assignments/rules/{id}` |

#### 验收标准

1. 坐席管理后端生效
2. 在线状态实时可见

---

### AF3-012：工单 + 审核页面 API 对接

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 替换清单

| 页面 | 替换内容 |
|------|---------|
| TicketsPage | 工单 CRUD + 状态流转后端驱动 |
| ReviewsPage | 审核列表/操作后端驱动 |
| AssignmentsPage | 分配操作后端驱动 |

#### 验收标准

1. 工单状态流转正确
2. 审核操作后端生效

---

## Phase 4：运营效率工具（P1）

### AF3-013：批量操作

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 实现要求

1. **模板批量操作**
   - 批量删除（多选 + 确认弹窗）
   - 批量审核通过/拒绝
   - 批量 Meta 同步

2. **会话批量操作**
   - 批量关闭
   - 批量恢复 AI 托管
   - 批量分配坐席

3. **UI 规范**
   - 表格左侧 checkbox 列
   - 顶部操作栏: 选中 X 项 → 操作按钮组
   - 操作确认弹窗（显示即将操作的数量）

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/TemplatePage.tsx` | 修改（批量选择 + 操作） |
| `frontend/src/pages/ChatPage.tsx` | 修改（批量操作） |
| `frontend/src/components/BatchActionBar.tsx` | 新增 |

#### 验收标准

1. 批量选择可用
2. 批量操作后端生效
3. 确认弹窗显示数量

---

### AF3-014：数据导出

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 实现要求

1. **CSV 导出组件**
   ```typescript
   // frontend/src/components/DataExporter.tsx
   interface DataExporterProps {
     columns: ExportColumn[]
     fetchData: (page: number) => Promise<PageData>
     filename: string
     maxRows?: number
   }
   ```

2. **导出功能覆盖**
   - 会话列表 → CSV
   - 消息记录 → CSV
   - 模板发送记录 → CSV
   - 客户列表 → CSV
   - 运营统计 → CSV

3. **导出方式**
   - 前端生成（小数据 < 1000 行）: 直接 Blob 下载
   - 后端生成（大数据 > 1000 行）: `POST /api/exports` → 轮询状态 → 下载

4. **进度显示**
   - 导出按钮 + 进度条
   - 导出完成 → 自动下载

#### 验收标准

1. CSV 格式正确
2. 大数据异步导出可用
3. 进度可见

---

### AF3-015：全局搜索

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 实现要求

1. **新增 `frontend/src/components/GlobalSearch.tsx`**
   - `Ctrl+K` 唤起搜索框
   - 搜索范围: 会话、客户、模板、工单
   - 结果分组展示
   - 点击结果跳转对应页面

2. **搜索 API**
   - `GET /api/search?q=keyword&type=conversation|customer|template|ticket`
   - 后端全文搜索（或简单的 LIKE 查询）

3. **UI**
   - 居中模态框
   - 输入框 + 结果列表
   - 键盘导航（上下键 + Enter 选择）
   - 最近搜索记录（localStorage）

#### 验收标准

1. Ctrl+K 唤起搜索
2. 搜索结果显示
3. 点击跳转正确

---

### AF3-016：Dashboard 实时更新

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. **定时刷新**
   - Dashboard 数据每 30 秒自动刷新
   - 右上角显示「最后更新: HH:mm:ss」
   - 手动刷新按钮

2. **实时指标**
   - 在线坐席数（实时）
   - 当前排队会话数（实时）
   - AI 处理中会话数（实时）

#### 验收标准

1. 30 秒自动刷新
2. 最后更新时间可见

---

## Phase 5：用户体验加固（P1）

### AF3-017：全局错误上报

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. **ErrorBoundary**
   - 全局 React Error Boundary
   - 捕获渲染错误 → 显示友好错误页 + 上报后端

2. **API 错误统一处理**
   - Axios interceptor 增强
   - 5xx → 全局 toast「服务器错误，请稍后重试」
   - 403 → 「您没有权限执行此操作」
   - 422 → 表单字段级错误高亮
   - 429 → 「操作过于频繁，请稍后」

3. **错误上报**
   - `POST /api/client-errors` — 上报前端错误
   - 包含: 错误信息、堆栈、页面路径、浏览器信息

#### 验收标准

1. 渲染错误不白屏
2. API 错误有友好提示
3. 错误上报到后端

---

### AF3-018：操作确认 + 防误触

- **优先级**: P1
- **估计耗时**: 20 分钟

#### 实现要求

1. **危险操作确认**
   - 删除: 「确定删除 XXX 吗？此操作不可恢复。」
   - 关闭会话: 「确定关闭此会话吗？」
   - 恢复 AI: 「恢复后 AI 将自动回复，是否继续？」
   - 批量操作: 「确定对 X 个项目执行此操作？」

2. **防重复提交**
   - 按钮 loading 态（点击后 disabled + spinner）
   - 表单提交后禁用按钮直到响应

3. **实现方式**
   - 使用 AntD `Popconfirm` 或 `Modal.confirm`
   - 统一封装 `useConfirmAction` hook

#### 验收标准

1. 所有危险操作有二次确认
2. 按钮不会重复提交

---

### AF3-019：加载状态一致性

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. **统一加载组件**
   ```typescript
   // frontend/src/components/PageLoading.tsx
   function PageLoading({ tip?: string }): JSX.Element
   
   // frontend/src/components/TableLoading.tsx  
   function TableLoading(): JSX.Element  // 表格骨架
   ```

2. **应用范围**
   - 所有列表页: 首次加载 → PageLoading，刷新 → TableLoading
   - 所有详情页: 首次加载 → PageLoading
   - 所有按钮: loading 态

3. **空状态**
   - 统一 `EmptyState` 组件
   - 各页面自定义空状态文案

#### 验收标准

1. 加载状态一致
2. 空状态友好

---

### AF3-020：通知中心增强

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. **Header 通知铃铛**
   - 未读数量 badge
   - 点击展开下拉面板（最近 10 条通知）
   - 通知类型图标（系统/AI/人工/模板）
   - 点击通知跳转相关页面

2. **通知类型**
   - AI 回复失败
   - 队列积压
   - 新会话分配
   - 模板审核结果
   - 系统告警

3. **定时轮询**
   - 每 60 秒检查未读通知
   - 或 WebSocket 推送

#### 验收标准

1. 通知铃铛显示未读数
2. 下拉面板可用
3. 点击跳转正确

---

## Phase 6：性能优化（P1）

### AF3-021：首屏加载优化

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 当前问题

- `vendor-antd`: 1,387 KB（gzip 437 KB）— **最大瓶颈**
- `vendor-pro-table`: 334 KB（gzip 104 KB）
- `vendor-pro-layout`: 331 KB（gzip 106 KB）

#### 优化方案

1. **AntD 按需加载**
   - 确认 tree-shaking 生效
   - 移除未使用的 AntD 组件引用
   - 考虑拆分: 常用组件 vs 不常用组件

2. **ProTable/ProLayout 拆分**
   - 只在需要的页面 import ProTable
   - ProLayout 考虑替换为更轻量的 Layout

3. **路由懒加载**
   - 所有页面 `React.lazy`
   - 首屏仅加载 Dashboard + Layout

4. **预加载**
   - 鼠标 hover 侧边菜单时预加载对应页面 chunk
   - `link rel="prefetch"` 用于可能访问的页面

#### 目标

- vendor-antd < 800 KB（gzip < 250 KB）
- 首屏 LCP < 3s（本地网络）

#### 验收标准

1. npm run build 产物减小
2. 路由懒加载生效

---

### AF3-022：列表页虚拟滚动

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

大数据量列表（会话 1000+，模板 500+）不卡顿。

#### 实现要求

1. **ProTable 虚拟滚动**
   - 超过 100 行启用虚拟滚动
   - 使用 `rc-virtual-list` 或 AntD Table `virtual` prop
   - 保持筛选/排序功能

2. **大数据分页**
   - 默认每页 20 条
   - 可选 50/100 条
   - 总数显示

#### 验收标准

1. 1000 行列表流畅
2. 虚拟滚动可用

---

## Phase 7：测试 + 验证（P0）

### AF3-023：Login + Auth 测试

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 新增测试

1. **`frontend/src/pages/loginPage.test.tsx`**
   - 渲染不崩溃
   - 表单验证（空用户名/密码）
   - 登录按钮可点击
   - 登录成功跳转
   - 登录失败错误提示

2. **`frontend/src/services/adminAuth.test.ts`**
   - login/refresh/logout/getMe 各场景
   - token 存储/读取/清除
   - 过期检测

#### 验收标准

1. 10+ 测试通过

---

### AF3-024：Chat 实时 + API 对接测试

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 新增测试

1. **`frontend/src/services/chatRealtime.test.ts`**
   - 连接/断开
   - 消息回调触发
   - 断线重连

2. **更新 `frontend/src/pages/admin-chat.test.tsx`**
   - 新增 API 对接场景测试
   - WebSocket 连接状态

#### 验收标准

1. 8+ 测试通过

---

### AF3-025：全量验证

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend

# 构建
npm run build

# 全部测试
npm run test -- src/services/operations.test.ts
npm run test -- src/pages/admin-chat.test.tsx
npm run test -- src/pages/templatePage.test.tsx
npm run test -- src/pages/metaAccountsPage.test.tsx
npm run test -- src/pages/dashboardPage.test.tsx
npm run test -- src/pages/loginPage.test.tsx
npm run test -- src/services/adminAuth.test.ts
npm run test -- src/services/chatRealtime.test.ts

# 现有测试不退化
npm run test -- src/pages/memberCustomerNavigation.test.tsx
```

#### 验收标准

| 项 | 预期 |
|----|------|
| npm run build | 通过 |
| 全部测试 | 60+ 通过 |
| LoginPage 存在 | 确认 |
| adminAuth service 存在 | 确认 |
| chatRealtime service 存在 | 确认 |
| GlobalSearch 组件 | 存在 |
| BatchActionBar 组件 | 存在 |
| DataExporter 组件 | 存在 |
| ErrorBoundary | 存在 |
| admin-chat/ 4 组件 | 存在 |
| vendor-antd gzip | < 400 KB（如未优化则不退化即可） |

---

## 2. 全局约束

1. **严格不碰 H5**: 不修改 `h5-member/` 目录下任何文件
2. **不改后端**: 不改 `app/` 目录
3. **保持 real/mock 分层**: 所有 API 支持 `VITE_API_MODE=mock|real` 切换
4. **保持 prefill 跳转机制**
5. **保持蓝灰主题一致**
6. **不新增说明型运营文案**
7. **使用 useMemberStatus hook**: 涉及客户状态的地方必须复用
8. **进度文件**: `.codex-run/progress/AF3-XXX.json`
9. **单任务最大执行 90 分钟**
10. **失败自动回滚 + 重试最多 3 次**
11. **每次改动后 `npm run build` 必须通过**
12. **一次性执行全部任务，不中途暂停确认**

