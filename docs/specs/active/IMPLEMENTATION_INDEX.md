# Implementation Index：低 Token 执行索引

本文件是执行索引，不替代 full specs。执行时优先读本文件；只有当前阶段需要细节时才读对应 full spec。

## 绝对全局规则

- 不修改任务 V3 业务规则。
- 不绕过 `WalletLedgerService` 改余额。
- 不新增第二套 WhatsApp Provider。
- 不新增第二套 WhatsApp Webhook。
- `LOGIN / BIND / AUTO_BIND` 必须在 AI 前处理。
- 未绑定普通消息不进入正式 AI。
- `wa_id` 全平台唯一绑定。
- 一个 `phone_number_id` 同一时间只能属于一个 active H5 站点池。
- B服务器只跑H5网关/静态H5/Agent，不跑A后端。
- H5域名不得访问后台管理API。
- 四级权限：超级管理员 → 代理商 → 主管 → 成员。
- 数据范围不得只用 account_id 代替团队/成员过滤。

## Full spec 路由

| 模块 | 当前Worker | Full spec |
|---|---|---|
| P0剩余模块 | W1 | `full/01_P0剩余模块代码级开发拆解文档V1.full.md` |
| WhatsApp站点号码池 | W2 | `full/02_WhatsApp登录绑定与站点号码池共享服务号开发文档V2.full.md` |
| 四级权限漏斗 | W3 | `full/03_四级权限漏斗与数据漏斗架构开发文档V2.full.md` |
| H5网关B服务器 | W4 | `full/04_H5多域名防攻击隔离与AB服务器后台控制部署方案V2.full.md` |

## W0 共享基础

只做共享底座，避免并行冲突：

- `app/db/models.py`
- `alembic/versions/**`
- `app/core/settings.py`
- `app/core/permission_defs.py`
- `pyproject.toml`
- `.github/workflows/**`
- `app/main.py` router占位

W0 不实现业务细节，只创建安全可扩展的共享表、配置、权限码、空路由注册点。

## W1 P0资金安全

Full spec：`01_P0...`

核心任务：

- production_guard
- CI test collection
- wallet invariant guard
- wallet reconciliation
- payment callback processor
- recharge repair race safety
- withdrawal risk policy
- payout state machine
- P0 E2E骨架

外部信息缺失处理：

- 支付通道真实密钥缺失时，实现 provider abstraction + fake/generic_hmac provider + tests。
- 不暂停。

## W2 WhatsApp站点号码池

Full spec：`02_WhatsApp...`

核心任务：

- SiteWhatsAppPhonePool
- UserWhatsAppServiceAssignment
- WhatsAppIdentity
- WhatsAppAuthSession
- WhatsAppAutoBindInvite
- PhoneSelectionService
- Webhook command router
- 未绑定普通消息绑定引导
- 同站点多号码会话合并

外部信息缺失处理：

- Meta真实 WABA/Phone 缺失时，使用 MetaAccountRegistry mock/stub 数据与 fake webhook payload 测试。
- 不暂停。

## W3 权限与数据漏斗

Full spec：`03_四级权限...`

核心任务：

- PermissionGrant
- DataScopeGrant
- StaffTeam / StaffTeamAssignment
- CustomerOwnershipAssignment
- ConversationAssignment
- HandoverQueue / AIHandoverPolicy
- EffectiveAccessService
- DataScopeFilterService
- 财务、客户、会话、任务、报表数据过滤

## W4 H5网关B服务器

Full spec：`04_H5多域名...`

核心任务：

- H5GatewayNode
- H5GatewayCredential
- H5GatewayJob / Step
- H5FrontendRelease
- H5GatewayAgent
- SSH white-list service
- deploy/h5-gateway/scripts
- Nginx config render/apply
- cert issue/renew dry-run
- firewall/CDN allowlist dry-run
- block/unblock domain
- health check

外部信息缺失处理：

- 没有真实 B 服务器时，完成 dry-run、mock SSH、fake agent、脚本单元测试。
- 不暂停。

## W5 前端

核心任务：

- WhatsApp号码池后台页
- H5登录/绑定/auto-bind页
- H5网关节点页
- 权限中心四级授权页
- 财务/提现风控页
- SitesPage集成

W5 不改 `frontend/src/routes/consoleRoutes.ts`，最终由 W9 统一接线。

## W6 测试与E2E

核心任务：

- 补充服务/API测试
- E2E骨架
- smoke脚本
- 测试矩阵
- 失败归属给对应Worker

W6 默认不改业务实现，除非是测试辅助或 fixture。

## W9 集成

核心任务：

- 合并 migration 顺序
- app/main.py 注册
- webhooks.py 接线
- permission_defs.py 最终合并
- consoleRoutes.ts 接线
- 全量测试
- 最终报告
