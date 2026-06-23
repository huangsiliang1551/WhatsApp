# H5 会员端后端缺失能力报告

## 当前结论

当前仓库可以支撑 H5 会员端的前端原型，但还不具备正式上线所需的完整后端能力。首版 H5 已按 `前端原型优先` 实现，以下缺口需要由后端线程补齐。

## 已存在且可部分复用

- H5 任务/工单接口骨架：`/api/h5/tasks*`、`/api/h5/tickets*`
- 单任务模板 / 实例模型与后台管理
- 任务 `claim_deadline` / `expired` 字段
- 平台用户字段：
  - `public_user_id`
  - `has_whatsapp`
  - `is_invited_user`
  - `registration_invite_code`
- `invite_codes` 表与邀请码基础能力
- 后台订单 / 物流查询 mock 接口

## 必须新增的后端能力

- 正式 H5 认证：注册、登录、会话、登出、修改密码
- 8 位随机数字账号 ID 生成与唯一性校验
- 任务包模板、任务包商品项、任务包实例、用户领取动作
- 任务包领取后倒计时启动，24 小时内过期作废
- 点击购买即完成的订单创建与付款状态机
- 包级统一奖励比例与佣金计算
- 双余额钱包：系统余额、任务余额
- 充值订单、任务余额划转、提现申请与状态流转
- 提现门槛校验与累计提现排行榜
- 消息中心
- 推广任务配置、邀请关系统计、充值归因统计
- 碎片掉落、碎片背包、合成兑奖、邮寄地址、邮寄物流状态
- H5 专用订单列表接口
- WhatsApp 绑定正式能力

## 建议新增接口域

- `/api/h5/auth/*`
- `/api/h5/task-packages/*`
- `/api/h5/orders/*`
- `/api/h5/wallet/*`
- `/api/h5/withdraw-leaderboard`
- `/api/h5/messages/*`
- `/api/h5/promotion-tasks/*`
- `/api/h5/fragments/*`
- `/api/h5/rewards/shipping/*`

## 建议新增核心模型

- `h5_auth_sessions`
- `task_package_templates`
- `task_package_template_items`
- `task_package_instances`
- `task_package_instance_items`
- `wallet_accounts`
- `wallet_transactions`
- `wallet_recharge_orders`
- `wallet_transfer_requests`
- `wallet_withdraw_requests`
- `message_center_items`
- `promotion_task_templates`
- `promotion_task_instances`
- `fragment_definitions`
- `fragment_inventory`
- `fragment_drop_logs`
- `fragment_exchange_requests`
- `reward_shipping_addresses`
- `reward_shipping_orders`

## 业务规则实现要求

- 对外账号 ID 固定为 8 位随机数字，不得暴露自增趋势
- 任务包必须后台发放，但用户必须手动领取
- 任务包有效期必须在 24 小时内，并向前端返回倒计时字段
- 商品购买成功后：
  - 创建站内订单
  - 扣减系统余额
  - 标记商品完成
  - 推进任务包进度
  - 整包完成时一次性增加任务余额
- 商品购买失败后：
  - 订单状态失败
  - 不扣系统余额
  - 不记任务完成
- 提现只能从系统余额发起，任务余额不能提现
- 提现状态需要至少覆盖：
  - `submitted`
  - `reviewing`
  - `approved`
  - `rejected`
  - `paid`
- 提现排行榜口径固定为累计提现金额榜，账号 ID 需脱敏展示
- 订单查询首版只保留列表，不提供订单详情和搜索

## 前端当前的实现边界

以下能力目前仅为前端 mock / 原型，占位等待后端补齐：

- 正式 H5 auth session
- 任务包领取 / 购买 / 进度 / 倒计时
- 钱包账本、充值、划转、提现
- 提现排行榜
- 消息中心
- 推广任务统计
- 碎片系统与邮寄闭环
- WhatsApp 绑定入口
