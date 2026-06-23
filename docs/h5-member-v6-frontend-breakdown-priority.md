# H5 会员端 v6 给前端开发的页面拆解与优先级清单

## 1. 文档目的

本清单面向前端开发，用于把 `H5 会员端 v6 页面级线框与文案整改稿` 转成可执行的页面拆解、组件边界、开发优先级和验收标准。

本轮目标不是新增业务范围，而是把现有 H5 会员端原型收敛成更适合上线验证的产品形态。

---

## 2. 当前实现基线

当前 H5 会员端的主要前端实现集中在以下文件：

- 页面入口：`frontend/src/pages/H5App.tsx`
- 会员端 mock / 接口封装：`frontend/src/services/h5Member.ts`
- 会员端样式：`frontend/src/styles.css`
- 前端回归：`frontend/src/services/h5Member.test.ts`

当前路由骨架已经具备：

- `/h5/login`
- `/h5/register`
- `/h5/home`
- `/h5/tasks`
- `/h5/tasks/:id`
- `/h5/messages`
- `/h5/me`
- `/h5/wallet`
- `/h5/orders`
- `/h5/tickets`
- `/h5/tickets/new`
- `/h5/tickets/:id`
- `/h5/fragments`
- `/h5/leaderboard`
- `/h5/whatsapp`

当前产品层面的 v6 页面要求已落在：

- [h5-member-v6-page-wireframe-copy-brief.md](/E:/codex/WhatsApp/docs/h5-member-v6-page-wireframe-copy-brief.md)

后端缺失边界参考：

- [h5-backend-gap-report.md](/E:/codex/WhatsApp/docs/h5-backend-gap-report.md)

---

## 3. 前端本轮目标

前端本轮只做 4 类事情：

1. 调整页面信息架构
2. 强化主链路的交互优先级
3. 收敛页面信息密度与状态表达
4. 为后端未完成能力保留 mock 和替换接口位

前端本轮不做：

- 新增真实后端依赖
- 推翻现有路由体系
- 引入新的状态管理框架
- 新增复杂桌面端适配

---

## 4. 页面拆解总表

## 4.1 一级页面

### A. 登录页 `/h5/login`

职责：

- 手机号 + 密码登录
- 密码可见切换
- 登录失败提示
- 登录后跳首页

本轮要求：

- 保持极简
- 忘记密码仅给“联系客服 / 提交工单”引导
- 不增加协议勾选

### B. 注册页 `/h5/register`

职责：

- 手机号注册
- 密码与确认密码
- 密码可见切换
- 注册成功后进入首页

本轮要求：

- 继续保持简单
- 强调“自动生成 8 位账号 ID”

### C. 首页 `/h5/home`

职责：

- 展示动态主动作
- 展示钱包摘要
- 展示任务摘要
- 展示工具入口
- 展示重要通知
- 展示提现排行榜

本轮要求：

- 首屏只能有一个主 CTA
- 钱包必须在首页前 2 屏可见
- 碎片、推广、排行榜都不能抢主视觉

### D. 任务页 `/h5/tasks`

职责：

- 展示任务包列表
- 提供状态筛选
- 支持领取和进入详情

本轮要求：

- 默认展示“进行中”
- 主筛选先按状态，不按类型
- 卡片信息主次分明

### E. 消息页 `/h5/messages`

职责：

- 展示重要通知与其他消息
- 支持未读标记
- 支持全部已读

本轮要求：

- 顶部浮动提示只给高优先级消息
- 页面内做“重要通知 / 其他消息”分层

### F. 我的页 `/h5/me`

职责：

- 展示账户信息
- 展示余额摘要
- 进入钱包、订单、工单、碎片等二级页

本轮要求：

- 首屏必须看到余额
- 入口排序按使用频率，不按功能平铺

---

## 4.2 二级页面

### G. 任务详情页 `/h5/tasks/:id`

职责：

- 展示任务包摘要
- 展示商品列表
- 触发 3 秒内购买流程
- 给失败补救动作

### H. 钱包页 `/h5/wallet`

职责：

- 展示系统余额、任务余额、提现门槛
- 支持充值、划转、提现
- 展示资金明细和提现状态

### I. 订单页 `/h5/orders`

职责：

- 只展示订单列表
- 支持状态筛选

### J. 工单列表页 `/h5/tickets`

职责：

- 展示工单列表
- 进入详情
- 跳新建工单

### K. 新建工单页 `/h5/tickets/new`

职责：

- 提交问题

### L. 工单详情页 `/h5/tickets/:id`

职责：

- 查看平台回复
- 继续补充

### M. 提现排行榜 `/h5/leaderboard`

职责：

- 展示脱敏账号与累计提现金额

### N. 碎片页 `/h5/fragments`

职责：

- 展示碎片背包、掉落记录、兑换、邮寄状态

### O. WhatsApp 绑定页 `/h5/whatsapp`

职责：

- 展示绑定状态
- 保留入口占位

---

## 5. 建议拆分的前端组件

当前 `H5App.tsx` 已经承担过多职责，本轮建议按“不改变业务结果、先收边界”的方式拆分。

## 5.1 壳层组件

- `H5MemberAppShell`
- `H5MemberTopbar`
- `H5MemberTabbar`
- `H5MemberSecondaryHeader`

职责：

- 页面骨架
- 顶部栏差异处理
- 底部 Tab 固定
- 二级页返回逻辑

## 5.2 通用状态组件

- `ToastStack`
- `SectionHeader`
- `EmptyStateCard`
- `LoadingState`
- `StatusBadge`
- `InlineStat`
- `ProgressBar`

职责：

- 统一提示
- 统一空态
- 统一状态标签
- 统一进度条表现

## 5.3 表单组件

- `PasswordField`
- `AmountPresetRow`
- `ConfirmActionModal`
- `SupportTicketForm`
- `ShippingAddressForm`

职责：

- 减少页内重复结构
- 把表单行为与页面文案分离

## 5.4 业务卡片组件

- `HomePrimaryActionCard`
- `WalletSummaryCard`
- `TaskPackageCard`
- `TaskPackageSummaryBar`
- `TaskProductItemCard`
- `MessageGroupCard`
- `ProfileAccountCard`
- `ProfileServiceList`
- `LeaderboardCard`
- `FragmentProgressCard`

职责：

- 提高首页、任务页、我的页的可维护性

---

## 6. 建议拆分的页面模块

如果本轮允许做轻量结构整理，建议从 `H5App.tsx` 中分出以下页面模块：

- `frontend/src/pages/h5-member/AuthPage.tsx`
- `frontend/src/pages/h5-member/HomePage.tsx`
- `frontend/src/pages/h5-member/TasksPage.tsx`
- `frontend/src/pages/h5-member/TaskPackageDetailPage.tsx`
- `frontend/src/pages/h5-member/MessagesPage.tsx`
- `frontend/src/pages/h5-member/ProfilePage.tsx`
- `frontend/src/pages/h5-member/WalletPage.tsx`
- `frontend/src/pages/h5-member/OrdersPage.tsx`
- `frontend/src/pages/h5-member/TicketsPage.tsx`
- `frontend/src/pages/h5-member/TicketDetailPage.tsx`
- `frontend/src/pages/h5-member/FragmentsPage.tsx`
- `frontend/src/pages/h5-member/LeaderboardPage.tsx`
- `frontend/src/pages/h5-member/WhatsAppBindingPage.tsx`

说明：

- 本轮不强制一次性全部拆完
- 允许先“组件拆分、页面不换路由”
- 优先把高频主链路页面拆出来

---

## 7. 接口与数据依赖拆解

## 7.1 当前可直接复用的前端数据入口

基于 `h5Member.ts`，当前前端可直接使用：

- 会员会话
- 首页 dashboard
- 任务包列表 / 详情
- 购买流程 mock
- 钱包摘要
- 订单列表
- 消息列表
- 工单列表 / 详情
- 提现榜
- 碎片信息
- WhatsApp 绑定状态

## 7.2 需要继续 mock 的能力

受后端能力限制，以下仍按前端 mock 处理：

- 正式登录会话稳定性
- 任务包正式发放与领取链路
- 充值 / 划转 / 提现真实账本
- 消息中心正式后端分类
- 推广任务统计
- 碎片掉落与邮寄闭环
- WhatsApp 正式绑定

## 7.3 页面与数据依赖映射

### 首页

依赖：

- `dashboard`
- `taskPackages`
- `messages`
- `leaderboard`

### 任务页

依赖：

- `taskPackages`

### 任务详情页

依赖：

- `taskPackageDetail`
- `purchaseStates`

### 消息页

依赖：

- `messages`

### 我的页

依赖：

- `dashboard.member`
- `dashboard.wallet`

### 钱包页

依赖：

- `walletSummary`
- `walletTransactions`
- `withdrawRequests`

### 订单页

依赖：

- `orders`

### 工单页

依赖：

- `tickets`
- `ticketDetail`

### 碎片页

依赖：

- `fragmentOverview`

---

## 8. 开发优先级

## P0：必须先做

这些项直接影响主链路转化和投诉率，优先级最高。

### P0-1 首页主动作收敛

目标：

- 首页首屏只保留一个主 CTA
- 按用户状态切换“立即领取 / 继续任务 / 去充值 / 去提现”

涉及页面：

- 首页

依赖：

- `dashboard`
- `taskPackages`

### P0-2 我的页余额首屏化

目标：

- 头像、账号、余额、提现状态放首屏
- 常用入口前置

涉及页面：

- 我的页

### P0-3 钱包规则极简化

目标：

- 系统余额与任务余额差异一眼可懂
- 提现不可用时给出原因

涉及页面：

- 首页钱包摘要
- 钱包页

### P0-4 领取确认弹层

目标：

- 用户领取任务包前确认倒计时与奖励规则

涉及页面：

- 任务页
- 任务详情页

### P0-5 购买失败补救动作

目标：

- 失败状态不能只有提示，必须给下一步动作

涉及页面：

- 任务详情页

### P0-6 消息分层

目标：

- 消息页拆成“重要通知 / 其他消息”
- 顶部浮动通知只给高优先级消息

涉及页面：

- 消息页
- 全局 toast

---

## P1：第二批完成

### P1-1 任务页卡片信息收敛

目标：

- 卡片主信息只保留：名称、倒计时、进度、总佣金、主按钮
- 副信息保留：商品数、奖励比例、类型标签

### P1-2 任务详情页顶部摘要条

目标：

- 固定展示完成度、剩余数、累计佣金、预计到账、倒计时

### P1-3 订单页状态筛选

目标：

- 补 `全部 / 成功 / 失败 / 处理中`

### P1-4 工单文案用户化

目标：

- 把 `工单 / 投诉` 外显文案改成 `联系客服 / 提交问题`

### P1-5 首页信息降噪

目标：

- 碎片、排行榜、动态全部后置
- 快捷入口降为工具区

---

## P2：第三批完成

### P2-1 推广任务说明补齐

目标：

- 明确统计口径、到账位置、有效期和延迟说明

### P2-2 碎片系统降权

目标：

- 弱化首页入口占位
- 强化任务完成后的掉落反馈

### P2-3 排行榜弱运营化

目标：

- 只强化信任感，不做强营销感滚动

### P2-4 页面拆分与文件整理

目标：

- 把高频页面从 `H5App.tsx` 中逐步拆出
- 降低单文件复杂度

---

## 9. 推荐开发顺序

## 第一轮

先完成主链路最低可用整改：

1. 首页主动作卡片
2. 我的页首屏余额摘要
3. 钱包摘要与规则说明
4. 领取确认弹层

交付结果：

- 用户知道先做什么
- 用户知道钱在哪里
- 用户知道领任务后会发生什么

## 第二轮

完成任务执行和失败闭环：

1. 任务页卡片收敛
2. 任务详情页摘要条
3. 购买失败补救动作
4. 消息分层

交付结果：

- 用户执行任务时更顺
- 失败后有明确去路

## 第三轮

完成工具页收口和体验细化：

1. 订单筛选
2. 工单文案调整
3. 推广任务说明
4. 碎片入口降权
5. 排行榜弱运营化

---

## 10. 页面级验收标准

## 10.1 首页验收

- 首屏只出现一个主 CTA
- 钱包摘要在前 2 屏内可见
- 工具入口不抢主视觉
- 排行榜不进入首屏核心区

## 10.2 任务页验收

- 默认展示“进行中”
- 领取前出现规则确认
- 卡片主次信息清晰

## 10.3 任务详情页验收

- 顶部固定任务摘要
- 点击购买后保留 3 秒内状态流
- 失败状态全部有动作按钮

## 10.4 消息页验收

- 页面内存在“重要通知 / 其他消息”分层
- 顶部浮动通知不下压页面
- 全部已读可用

## 10.5 我的页验收

- 首屏可见头像、账号、余额、提现状态
- 钱包 / 订单 / 客服入口前置

## 10.6 钱包页验收

- 用户能区分系统余额和任务余额
- 提现不可用时有明确原因
- 资金动作区有短说明

## 10.7 订单页验收

- 仅展示列表
- 不出现搜索和详情入口
- 存在状态筛选

## 10.8 工单页验收

- 外显文案更偏用户语言
- 支持新建、列表、详情、补充

---

## 11. 前端实现注意事项

- 所有按钮、标签、状态字段需预留英文长度
- Toast、Modal、Confirm 不能影响页面流布局
- 所有失败场景必须是“状态 + 原因 + 动作”
- 不要在首页叠加过多营销型文案
- 不要让钱相关信息隐藏在二级页后面
- 任务倒计时、进度、余额数值必须优先保证可读性

---

## 12. 建议补充的前端回归范围

本轮如继续加静态契约或组件测试，优先覆盖：

- 首页首屏单 CTA 逻辑
- 我的页首屏余额可见
- 领取确认弹层存在
- 任务详情失败动作按钮存在
- 消息分组存在
- 订单页无搜索、无详情入口
- 钱包页文案中明确区分两种余额

---

## 13. 一句话结论

前端本轮不是继续“铺页面”，而是要把现有页面按主链路重新排优先级。

具体执行顺序建议固定为：

1. 首页
2. 我的页
3. 钱包页
4. 任务页
5. 任务详情页
6. 消息页
7. 订单 / 工单 / 推广 / 碎片等工具页

