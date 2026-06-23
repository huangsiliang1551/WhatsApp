# H5 会员端上线级任务清单（H52-001 ~ H52-25）

> **执行角色**: frontend_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**
> **目标**: H5 会员端达到**可上线标准**，全部功能闭环

---

## 0. 项目现状摘要

### 已完成（上一轮）

| 模块 | 状态 | 关键产出 |
|------|------|---------|
| 组件拆分 | ✅ | 17 个独立页面组件 |
| i18n | ✅ | zh-CN.ts(773行) + en.ts(745行) + index.ts(37行) |
| 样式独立 | ✅ | h5-member.css(2895行) + styles.css 4486→274行 |
| UX 收口 | ✅ | useAsync hook + RetryBar + 统一风格 |
| H5App.tsx | ✅ | 367 行 |

### 未完成 / 待上线加固

| 缺失项 | 影响 |
|--------|------|
| 所有 API 调用走 mock/localStorage | 无法联调后端 |
| 无 Session 管理（cookie 认证） | 刷新页面即登出 |
| 无路由守卫（未登录可访问受保护页） | 安全漏洞 |
| 无错误边界组件 | 单页面崩溃白屏 |
| 无离线检测 | 弱网体验差 |
| 无骨架屏全页覆盖 | 加载体验不一致 |
| 无 PWA / Service Worker | 离线不可用 |
| WhatsApp 聊天页纯 mock | 无法真实对话 |
| 无媒体上传 | 无法发送图片 |
| 无推送通知 | 无法主动触达 |
| 无埋点/统计 | 不知用户行为 |
| h5.ts (2174行) + h5Member.ts (2753行) 超大 | 维护困难 |
| shared.tsx (837行) 仍偏大 | 可进一步拆分 |

---

## 1. 执行编排（7 Phase，预计 3-4 天）

```
Day 1:
  Phase 1（Session 管理 + 路由守卫，P0）: H52-001~004
  Phase 2（API 对接 — 认证链路，P0）: H52-005~007

Day 2:
  Phase 3（API 对接 — 业务链路，P0）: H52-008~012
  Phase 4（API 对接 — 商城 + 提现，P1）: H52-013~015

Day 3:
  Phase 5（WhatsApp 聊天 + 媒体上传，P0）: H52-016~018
  Phase 6（UX 加固，P1）: H52-019~022

Day 4:
  Phase 7（性能 + 测试 + 验证，P0）: H52-023~025
```

---

## Phase 1：Session 管理 + 路由守卫（P0）

### H52-001：Session Manager

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

统一管理 H5 会员的登录态，支持 cookie + localStorage 双写。

#### 实现要求

1. **新增 `frontend/src/services/h5SessionManager.ts`**
   ```typescript
   class H5SessionManager {
     isAuthenticated(): boolean
     getAccessToken(): string | null
     getRefreshToken(): string | null
     setSession(accessToken: string, refreshToken: string, expiresIn: number): void
     clearSession(): void
     isTokenExpired(): boolean
     shouldRefresh(): boolean  // 过期前 5 分钟
     getUserInfo(): H5MemberInfo | null
     setUserInfo(info: H5MemberInfo): void
   }
   ```

2. **Cookie 存储**
   - Cookie 名称从后端配置读取（`h5_member_session` / `h5_member_refresh`）
   - 开发态: localStorage fallback（cookie 不可用时）
   - 生产态: 仅 cookie（HttpOnly + Secure + SameSite）

3. **Token 自动续期**
   - Axios interceptor: 请求前检查 token 是否即将过期
   - 自动调用 `/api/h5/auth/refresh`
   - 续期失败 → 清除 session → 跳转登录

4. **单例导出**
   - `export const sessionManager = new H5SessionManager()`

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/services/h5SessionManager.ts` | 新增 |
| `frontend/src/services/h5Member.ts` | 修改（Axios interceptor 集成） |

#### 验收标准

1. Session 设置/读取/清除正常
2. Token 过期自动续期
3. 续期失败自动登出

---

### H52-002：路由守卫

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 目标

未登录用户访问受保护页面时，自动跳转登录页。

#### 实现要求

1. **新增 `frontend/src/pages/h5-member/useAuthGuard.ts`**
   ```typescript
   function useAuthGuard(redirectToLogin?: boolean): {
     isAuthenticated: boolean
     isLoading: boolean  // 检查 session 中
     user: H5MemberInfo | null
   }
   ```

2. **H5App.tsx 集成**
   - 受保护页面: Home, Tasks, Orders, Profile, Settings, Messages, WhatsApp, Tickets, Recharge, Withdraw, Verification, Promotion, Fragments
   - 公开页面: Login, Register（不需要认证）
   - 未认证 → 重定向到 `/h5/login?redirect={originalPath}`

3. **登录成功后**
   - 自动跳回 redirect 路径
   - 无 redirect → 跳 Home

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/h5-member/useAuthGuard.ts` | 新增 |
| `frontend/src/pages/H5App.tsx` | 修改（集成路由守卫） |
| `frontend/src/pages/h5-member/LoginPage.tsx` | 修改（redirect 参数） |

#### 验收标准

1. 未登录访问 Tasks → 跳转 Login
2. 登录后回到 Tasks
3. 公开页面不受影响

---

### H52-003：Token 拦截器加固

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 实现要求

1. **`frontend/src/services/h5Member.ts`** Axios interceptor 增强
   - 请求拦截: 自动附加 Authorization header（Bearer token）
   - 响应拦截: 401 → 尝试 refresh → 重试原请求 → 失败则清除 session 跳登录
   - 并发请求: 多个 401 只触发一次 refresh，其他请求排队等待
   - 网络错误: 显示 toast 提示「网络连接失败」

2. **请求重试**
   - 5xx 错误: 自动重试 1 次（延迟 2 秒）
   - 非幂等操作（POST/PUT/DELETE）不重试

#### 验收标准

1. 401 自动续期
2. 并发请求只触发一次 refresh
3. 网络错误有提示

---

### H52-004：登录/注册页面完善

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 实现要求

1. **LoginPage.tsx (246行)** 增强
   - 手机号 + 密码登录
   - 手机号 + 验证码登录（预留接口）
   - 记住登录态（7天）
   - 忘记密码链接
   - 登录失败: 错误提示（密码错误/账号不存在/已锁定）

2. **注册流程**（如尚未实现）
   - 手机号 + 验证码 + 密码
   - 密码强度提示
   - 手机号格式验证

3. **表单验证**
   - 手机号: 中国大陆 11 位 或 国际格式
   - 密码: 8-32 位，至少包含字母和数字

#### 验收标准

1. 登录/注册/忘记密码流程完整
2. 表单验证正确
3. 错误提示友好

---

## Phase 2：API 对接 — 认证链路（P0）

### H52-005：替换 localStorage mock → 真实 Auth API

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

`h5Member.ts` 中所有 mock 认证逻辑替换为真实 API 调用。

#### 当前 mock 机制

- `h5Member.ts`（2753 行）中大量 localStorage 读写
- 登录/注册/刷新 token 全部本地模拟

#### 替换清单

| 功能 | Mock 方式 | 替换为 |
|------|----------|--------|
| 登录 | localStorage | `POST /api/h5/auth/login` |
| 注册 | localStorage | `POST /api/h5/auth/register` |
| 刷新 | localStorage | `POST /api/h5/auth/refresh` |
| 登出 | localStorage.clear | `POST /api/h5/auth/logout` |
| 获取用户信息 | localStorage | `GET /api/h5/auth/me` |

#### 实现方式

- 保留 mock 层作为 fallback（`VITE_API_MODE=mock` 时启用）
- 真实 API 层优先
- 通过 `apiMode` 环境变量切换

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/services/h5Member.ts` | 大幅修改 |
| `frontend/src/services/h5SessionManager.ts` | 集成 |

#### 验收标准

1. `VITE_API_MODE=real` 时走真实 API
2. `VITE_API_MODE=mock` 时走 localStorage
3. 登录/注册/刷新/登出全链路可用

---

### H52-006：首页 API 对接

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 今日任务数 | localStorage | `GET /api/h5/tasks?status=available&limit=5` |
| 钱包余额 | localStorage | `GET /api/h5/wallet/balance` |
| 通知数 | 固定值 | `GET /api/h5/notifications?unread=true&count_only=true` |
| 用户等级 | localStorage | `GET /api/h5/auth/me` |

#### 验收标准

1. 首页展示真实数据
2. mock 模式仍可正常显示

---

### H52-007：任务列表 + 任务提交 API 对接

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 任务列表 | 硬编码数组 | `GET /api/h5/tasks?page=1&size=20` |
| 任务详情 | 本地查找 | `GET /api/h5/tasks/{id}` |
| 任务提交 | localStorage 写入 | `POST /api/h5/tasks/{id}/submit` |
| 任务状态 | localStorage | `GET /api/h5/tasks/{id}/status` |
| 证据上传 | 本地 FileReader | `POST /api/h5/tasks/{id}/proof` (multipart) |

#### 实现要求

1. 分页加载（无限滚动或加载更多按钮）
2. 任务筛选（可用/进行中/已完成）
3. 提交时表单验证
4. 证据上传进度条
5. 大文件压缩（图片 > 1MB 时压缩到 500KB）

#### 验收标准

1. 任务列表从后端加载
2. 提交任务后端可收到
3. 证据上传成功

---

## Phase 3：API 对接 — 业务链路（P0）

### H52-008：钱包 + 充值 API 对接

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 余额查询 | localStorage | `GET /api/h5/wallet/balance` |
| 交易记录 | 本地数组 | `GET /api/h5/wallet/transactions?page=1` |
| 充值发起 | 模拟 | `POST /api/h5/wallet/recharge` |
| 充值状态 | 模拟 | `GET /api/h5/wallet/recharge/{id}/status` |

#### 实现要求

1. 余额实时更新（提交任务审核通过后余额变化）
2. 交易记录分页 + 时间筛选
3. 充值金额输入验证
4. 充值状态轮询（每 3 秒，最多 30 秒）

#### 验收标准

1. 余额从后端读取
2. 交易记录分页可用
3. 充值流程完整

---

### H52-009：提现 API 对接

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 可提现金额 | localStorage | `GET /api/h5/wallet/balance` |
| 提现申请 | 模拟 | `POST /api/h5/withdrawals` |
| 提现记录 | 本地数组 | `GET /api/h5/withdrawals?page=1` |
| 提现状态 | 模拟 | `GET /api/h5/withdrawals/{id}` |

#### 实现要求

1. 金额验证: 不能超过可提现余额
2. 最低提现金额提示
3. 手续费计算展示
4. 提现状态追踪（待审核 → 处理中 → 已完成/已拒绝）

#### 验收标准

1. 提现申请后端可收到
2. 金额验证正确
3. 状态追踪可用

---

### H52-010：个人中心 API 对接

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 用户信息 | localStorage | `GET /api/h5/auth/me` |
| 修改昵称 | localStorage | `PUT /api/h5/profile` |
| 修改头像 | localStorage | `POST /api/h5/profile/avatar` |
| 修改密码 | 模拟 | `PUT /api/h5/profile/password` |

#### 验收标准

1. 个人信息从后端读取
2. 修改操作后端生效

---

### H52-011：认证 + WhatsApp 绑定 API 对接

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 认证状态 | localStorage | `GET /api/h5/verifications/status` |
| 提交认证 | localStorage | `POST /api/h5/verifications` |
| 认证照片上传 | 模拟 | `POST /api/h5/verifications/{id}/photos` |
| WhatsApp 绑定状态 | localStorage | `GET /api/h5/whatsapp-bindings/status` |
| 发起绑定 | 模拟 | `POST /api/h5/whatsapp-bindings` |

#### 实现要求

1. 认证表单完整（姓名、证件号、证件照片）
2. 照片上传 + 预览 + 压缩
3. 认证状态: 未认证 → 审核中 → 已通过/已拒绝
4. WhatsApp 绑定: 输入手机号 → 发送验证码 → 确认绑定

#### 验收标准

1. 认证全流程可用
2. WhatsApp 绑定全流程可用
3. 照片上传正确

---

### H52-012：通知 + 工单 API 对接

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 通知列表 | 硬编码 | `GET /api/h5/notifications?page=1` |
| 标记已读 | localStorage | `PUT /api/h5/notifications/{id}/read` |
| 全部已读 | localStorage | `PUT /api/h5/notifications/read-all` |
| 工单列表 | 硬编码 | `GET /api/h5/tickets?page=1` |
| 创建工单 | 模拟 | `POST /api/h5/tickets` |
| 工单详情 | 本地 | `GET /api/h5/tickets/{id}` |
| 工单回复 | 模拟 | `POST /api/h5/tickets/{id}/messages` |

#### 验收标准

1. 通知从后端加载
2. 工单 CRUD 可用
3. 已读/未读状态正确

---

## Phase 4：API 对接 — 商城 + 片段（P1）

### H52-013：商城页面 API 对接

- **优先级**: P1
- **估计耗时**: 45 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 商品列表 | 硬编码 | `GET /api/h5/commerce/products` |
| 商品详情 | 本地 | `GET /api/h5/commerce/products/{id}` |
| 下单 | 模拟 | `POST /api/h5/commerce/orders` |
| 订单列表 | localStorage | `GET /api/h5/commerce/orders` |
| 订单详情 | 本地 | `GET /api/h5/commerce/orders/{id}` |
| 物流查询 | 模拟 | `GET /api/h5/commerce/orders/{id}/logistics` |

#### 验收标准

1. 商品列表展示
2. 下单→订单→物流全链路

---

### H52-014：片段 + 邮件 API 对接

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 片段列表 | localStorage | `GET /api/h5/fragments` |
| 片段详情 | 本地 | `GET /api/h5/fragments/{id}` |
| 订阅邮件 | 模拟 | `POST /api/h5/mailing/subscribe` |
| 退订 | 模拟 | `POST /api/h5/mailing/unsubscribe` |

#### 验收标准

1. 片段展示
2. 邮件订阅/退订可用

---

### H52-015：排行榜 + 推广任务 API 对接

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 替换清单

| 功能 | Mock | 替换为 |
|------|------|--------|
| 排行榜 | 硬编码 | `GET /api/h5/leaderboard` |
| 推广任务列表 | 硬编码 | `GET /api/h5/promotions` |
| 推广参与 | 模拟 | `POST /api/h5/promotions/{id}/join` |

#### 验收标准

1. 排行榜从后端加载
2. 推广任务可参与

---

## Phase 5：WhatsApp 聊天 + 媒体上传（P0）

### H52-016：WhatsApp 聊天页真实对接

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 当前状态

`WhatsAppPage.tsx`（39 行）仅一个占位页面。

#### 实现要求

1. **重写 `WhatsAppPage.tsx`**
   - 接入后端消息 API: `GET /api/h5/messages`
   - 实时消息轮询（5 秒间隔）或 WebSocket
   - 发送消息: `POST /api/h5/messages`
   - 消息气泡 UI（用户消息右对齐，客服消息左对齐）
   - 消息状态: 已发送 / 已送达 / 已读

2. **消息类型**
   - 文本消息
   - 图片消息（缩略图 + 点击放大）
   - 系统通知（居中灰色小字）

3. **输入区域**
   - 文本输入框 + 发送按钮
   - 图片上传按钮（调用相机或相册）
   - 输入框自动高度调整

4. **消息历史**
   - 分页加载（向上滚动加载更多）
   - 新消息自动滚动到底部
   - 未读消息数量提示

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/h5-member/WhatsAppPage.tsx` | 重写（39→300+行） |
| `frontend/src/services/h5Member.ts` | 新增消息 API |

#### 验收标准

1. 可发送/接收文本消息
2. 可发送/接收图片
3. 消息历史可加载
4. 新消息实时显示

---

### H52-017：媒体上传组件

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 目标

通用媒体上传组件，任务证据/认证照片/聊天图片共用。

#### 实现要求

1. **新增 `frontend/src/pages/h5-member/MediaUploader.tsx`**
   ```typescript
   interface MediaUploaderProps {
     accept: string         // image/*, video/*, etc.
     maxSizeMB: number      // 最大文件大小
     multiple: boolean      // 是否多选
     onUpload: (files: UploadedFile[]) => void
     onError: (error: string) => void
     preview?: boolean      // 是否显示预览
     compress?: boolean     // 是否压缩图片
   }
   ```

2. **图片压缩**
   - > 1MB: 自动压缩到 ~500KB（Canvas API）
   - 保持原始比例
   - 显示压缩前后大小

3. **上传进度**
   - 进度条
   - 取消上传

4. **文件类型验证**
   - 仅允许指定类型
   - 超大小拒绝 + 友好提示

#### 涉及文件

| 文件 | 动作 |
|------|------|
| `frontend/src/pages/h5-member/MediaUploader.tsx` | 新增 |
| `frontend/src/pages/h5-member/TasksPage.tsx` | 修改（使用 MediaUploader） |
| `frontend/src/pages/h5-member/VerificationPage.tsx` | 修改（使用 MediaUploader） |

#### 验收标准

1. 图片上传带进度
2. 大图片自动压缩
3. 类型/大小验证正确

---

### H52-018：图片查看器

- **优先级**: P1
- **估计耗时**: 20 分钟

#### 实现要求

1. **新增 `frontend/src/pages/h5-member/ImageViewer.tsx`**
   - 全屏查看
   - 手势缩放（pinch-to-zoom）
   - 左右滑动切换（多图模式）
   - 长按保存提示

#### 验收标准

1. 图片全屏查看
2. 手势缩放可用

---

## Phase 6：UX 加固（P1）

### H52-019：错误边界组件

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. **新增 `frontend/src/pages/h5-member/ErrorBoundary.tsx`**
   - React Error Boundary
   - 捕获子组件渲染错误
   - 显示友好错误页面:「页面遇到问题，请刷新重试」
   - 上报错误到后端: `POST /api/h5/client-errors`
   - 刷新按钮

2. **应用范围**
   - 每个路由页面包裹 ErrorBoundary
   - H5App 顶层也加一个兜底 ErrorBoundary

#### 验收标准

1. 子组件崩溃不白屏
2. 错误信息上报
3. 可刷新恢复

---

### H52-020：离线检测 + 弱网提示

- **优先级**: P1
- **估计耗时**: 20 分钟

#### 实现要求

1. **新增 `frontend/src/pages/h5-member/useNetworkStatus.ts`**
   ```typescript
   function useNetworkStatus(): {
     isOnline: boolean
     isWeakNetwork: boolean  // RTT > 3s
   }
   ```

2. **H5PageShell 集成**
   - 离线时: 顶部红色横幅「您已离线，部分功能不可用」
   - 弱网时: 顶部黄色横幅「网络较慢，请耐心等待」
   - 恢复在线: 自动刷新数据

#### 验收标准

1. 断网时显示离线横幅
2. 恢复后自动刷新

---

### H52-021：骨架屏全页覆盖

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 目标

所有页面首次加载时显示骨架屏，而非空白或 spinner。

#### 实现要求

1. **新增 `frontend/src/pages/h5-member/skeletons/`**
   - `HomeSkeleton.tsx` — 统计卡片 + 任务列表骨架
   - `ListSkeleton.tsx` — 通用列表骨架（复用）
   - `DetailSkeleton.tsx` — 详情页骨架
   - `ProfileSkeleton.tsx` — 个人中心骨架

2. **集成到各页面**
   - 数据加载中显示骨架屏
   - 数据加载完成切换为真实内容
   - 使用 CSS animation 做闪烁效果

#### 验收标准

1. 每个页面有对应骨架屏
2. 加载→完成切换流畅

---

### H52-022：下拉刷新 + 无限滚动

- **优先级**: P1
- **估计耗时**: 30 分钟

#### 实现要求

1. **下拉刷新**
   - 所有列表页面支持下拉刷新
   - 使用 touch 事件实现
   - 刷新动画（旋转 + 下拉回弹）

2. **无限滚动**
   - 任务列表、订单列表、通知列表、交易记录
   - 滚动到底部自动加载更多
   - 加载中显示 spinner
   - 没有更多数据时显示「没有更多了」

#### 验收标准

1. 下拉刷新可用
2. 无限滚动加载正确

---

## Phase 7：性能 + 测试 + 验证（P0）

### H52-023：性能优化

- **优先级**: P0
- **估计耗时**: 45 分钟

#### 实现要求

1. **路由懒加载**
   - H5App.tsx 中所有 `import` 改为 `React.lazy`
   - 减少首屏加载体积

2. **图片优化**
   - 列表页缩略图使用 `loading="lazy"`
   - 使用 WebP 格式（如后端支持）
   - 占位图使用 SVG placeholder

3. **API 请求优化**
   - 首页并发请求（任务数 + 余额 + 通知数 同时请求）
   - 请求去重（同一 URL 5 秒内不重复请求）
   - 分页请求取消（切换页面时取消上一个请求）

4. **Bundle 分析**
   - `npm run build` 检查 H5 chunk 大小
   - 目标: H5App chunk < 150 KB (gzip)

#### 验收标准

1. 路由懒加载生效
2. H5 chunk < 150 KB gzip
3. 首页并发请求

---

### H52-024：前端测试套件

- **优先级**: P0
- **估计耗时**: 60 分钟

#### 测试文件

1. **`frontend/src/pages/h5-member/h5Session.test.ts`**
   - Session 设置/读取/清除
   - Token 过期检测
   - 续期逻辑

2. **`frontend/src/pages/h5-member/h5Auth.test.tsx`**
   - 路由守卫: 未登录跳转
   - 登录成功后跳转
   - 登出清除 session

3. **`frontend/src/pages/h5-member/h5Pages.test.tsx`**
   - 各页面渲染不崩溃（冒烟测试）
   - API mock 后数据正确展示
   - 表单验证正确

4. **`frontend/src/pages/h5-member/h5Media.test.tsx`**
   - MediaUploader 渲染
   - 文件类型验证
   - 图片压缩逻辑

#### 验收标准

1. 20+ 测试用例
2. 全部通过

---

### H52-025：全量验证

- **优先级**: P0
- **估计耗时**: 30 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp\frontend

# 构建
npm run build

# H5 测试
npm run test -- src/pages/h5-member/h5Session.test.ts
npm run test -- src/pages/h5-member/h5Auth.test.tsx
npm run test -- src/pages/h5-member/h5Pages.test.tsx
npm run test -- src/pages/h5-member/h5Media.test.tsx

# 现有测试不退化
npm run test -- src/services/h5.test.ts
npm run test -- src/services/h5Member.test.ts
```

#### 验收标准

| 项 | 预期 |
|----|------|
| npm run build | 通过 |
| H5 chunk gzip | < 150 KB |
| H5 测试 | 20+ 通过 |
| 现有 H5 测试 | 不退化 |
| i18n 文件 | zh-CN + en + index 存在 |
| 样式独立 | h5-member.css 存在 |
| 17 页面 tsx | 全部存在 |
| MediaUploader | 存在 |
| ImageViewer | 存在 |
| ErrorBoundary | 存在 |
| useNetworkStatus | 存在 |
| useAuthGuard | 存在 |
| h5SessionManager | 存在 |

---

## 2. 全局约束

1. **严格不碰管理后台**: 不修改 `frontend/src/pages/` 下非 `h5-member/` 目录的文件
2. **不改后端**: 不改 `app/` 目录
3. **保持 mock fallback**: `VITE_API_MODE=mock` 时所有页面仍可用 localStorage
4. **保持 i18n**: 所有新增文案必须走 i18n（t() 调用 + zh-CN/en 更新）
5. **保持样式独立**: 所有 H5 样式写 `h5-member.css`，不碰 `styles.css`
6. **保持 prefill 跳转机制**
7. **进度文件**: `.codex-run/progress/H52-XXX.json`
8. **单任务最大执行 90 分钟**
9. **失败自动回滚 + 重试最多 3 次**
10. **每次改动后 `npm run build` 必须通过**
11. **一次性执行全部任务，不中途暂停确认**
12. **新增组件必须与现有 useAsync hook + RetryBar 模式一致**
