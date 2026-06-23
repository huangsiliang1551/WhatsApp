# 数据清理与全链路测试方案（DATA-TEST）

> **执行角色**: api_agent（数据脚本）+ testing_agent（全链路验证）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-19
> **总架构师签发**
> **目标**: 清理脏数据 → 种子数据 → 三级全链路测试

---

## 一、数据清理策略

### 当前问题

- 多轮开发产生大量脏数据（mock 数据、测试残留、不匹配的外键）
- 代理商/站点/用户/WABA 关系混乱
- 旧表数据与新三级租户架构不兼容

### 清理方案：重建种子数据库

**不用逐个清理，直接清空重建**（开发环境安全操作）：

```python
# app/scripts/seed_clean_data.py
"""
数据清理 + 种子数据脚本
用法: docker exec whatsapp_app python -m app.scripts.seed_clean_data
"""

# ── Step 1: 清空所有业务表（保留系统表） ──
TABLES_TO_CLEAN = [
    # 通知/审计
    "notifications", "audit_logs", "client_errors", "uptime_checks",
    # 营销/任务
    "mkt_task_instances", "task_rules", "product_packages", "products",
    "sign_in_records", "invite_records",
    # 钱包/交易
    "wallet_ledger_entries", "wallet_accounts",
    # 会话/消息
    "message_events", "messages", "conversations",
    # 工单
    "tickets", "ticket_replies",
    # 会员
    "member_auth_sessions", "member_verification_requests",
    "member_whatsapp_binding_requests", "member_notifications",
    "member_profiles", "app_users",
    # 站点/代理商
    "site_waba_bindings", "agency_templates", "agent_templates",
    "agency_billing", "agency_members",
    # WABA/Meta
    "whatsapp_phone_numbers", "whatsapp_business_accounts",
    "webhook_subscriptions", "embedded_signup_sessions",
    "meta_business_portfolios",
    # 站点/代理商
    "h5_site_configs", "h5_sites", "h5_translations",
    "site_permissions", "agencies",
    # 模板
    "h5_templates",
    # 密钥/黑名单
    "secrets", "ip_blacklist",
]

# ── Step 2: 种子数据 ──
```

---

## 二、种子数据设计

### 完整数据模型

```
超级管理员: admin / admin123

H5 模板（2 套）:
  TPL-1: "默认商城版" (默认模板)
  TPL-2: "简约商务版"

代理商 A: "上海锦囊"
  管理员: agent_sh / Agent@2026
  品牌: 锦囊科技
  站点 1: wechat-01 (微信渠道)
    域名: h5-wechat.example.com
    模板: TPL-1
    WABA: waba-sh-01 (绑定号码 +86-138-0001)
    用户: 5 个会员
    会话: 3 个活跃会话
    工单: 1 个待处理工单
  站点 2: douyin-01 (抖音渠道)
    域名: h5-douyin.example.com
    模板: TPL-1
    WABA: waba-sh-02 (绑定号码 +86-138-0002)
    用户: 3 个会员
    会话: 2 个活跃会话
  下属: 3 人
    - 财务: finance_sh / Finance@2026
    - 经理: manager_sh / Manager@2026
    - 客服: support_sh / Support@2026
  账单: 2 条（1 已付 + 1 待付）

代理商 B: "深圳启航"
  管理员: agent_sz / Agent@2026
  品牌: 启航网络
  站点 3: xiaohongshu-01 (小红书渠道)
    域名: h5-xhs.example.com
    模板: TPL-2
    WABA: waba-sz-01 (绑定号码 +86-139-0001)
    用户: 4 个会员
    会话: 2 个活跃会话
  下属: 2 人
    - 财务: finance_sz / Finance@2026
    - 客服: support_sz / Support@2026
  账单: 1 条（待付）

语言: 3 种（中文/英文/日文）
翻译: 每个站点 5 条翻译
通知: 每个代理商 3 条通知
审计日志: 自动记录
```

### 数据量统计

| 数据类型 | 数量 | 说明 |
|---------|------|------|
| 超级管理员 | 1 | admin |
| 代理商 | 2 | 上海锦囊 + 深圳启航 |
| 代理商管理员 | 2 | agent_sh + agent_sz |
| 代理商下属 | 5 | 3 + 2 |
| H5 模板 | 2 | 默认商城版 + 简约商务版 |
| H5 站点 | 3 | 微信 + 抖音 + 小红书 |
| WABA 账号 | 3 | 每站点 1 个 |
| 会员 | 12 | 5 + 3 + 4 |
| 会话 | 7 | 3 + 2 + 2 |
| 消息 | ~35 | 每会话 5 条 |
| 工单 | 2 | 1 待处理 + 1 已解决 |
| 商品 | 5 | 测试商品 |
| 商品包 | 3 | 每站点 1 个 |
| 任务规则 | 3 | 签到 + 邀请 + 手动推送 |
| 任务实例 | 6 | 每站点 2 个 |
| 签到记录 | 6 | 部分会员签到 |
| 邀请记录 | 3 | 部分会员邀请 |
| 钱包 | 12 | 每会员 1 个 |
| 交易记录 | ~20 | 充值 + 奖励 |
| 账单 | 3 | 2 + 1 |
| 通知 | 6 | 每代理商 3 条 |
| 语言 | 3 | 中/英/日 |
| 翻译 | 15 | 每站点 5 条 |
| 密钥 | 2 | OpenAI + DeepSeek |

---

## 三、种子数据脚本实现

### DT-SEED-001：数据清理 + 种子脚本

**新增**: `app/scripts/seed_clean_data.py` (~500 行)

```python
"""
种子数据脚本 - 清理脏数据并创建完整测试数据集
用法: docker exec whatsapp_app python -m app.scripts.seed_clean_data
"""
import uuid, json
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text
from app.db.session import SessionLocal
from app.db.models import *

def clean_all(session):
    """清空所有业务表"""
    for table in TABLES_TO_CLEAN:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    # 重置序列
    session.execute(text("ALTER SEQUENCE accounts_id_seq RESTART WITH 1"))
    session.commit()

def seed_super_admin(session):
    """创建超级管理员（如已存在则跳过）"""
    ...

def seed_templates(session):
    """创建 2 套 H5 模板"""
    tpl1 = H5Template(id=new_id(), name="默认商城版", ...)
    tpl2 = H5Template(id=new_id(), name="简约商务版", ...)
    return tpl1, tpl2

def seed_agency_a(session, tpl1):
    """创建代理商 A: 上海锦囊"""
    agency = Agency(id=new_id(), name="上海锦囊", brand_name="锦囊科技", ...)
    # 管理员账号
    agent_user = create_admin_user("agent_sh", "Agent@2026", "agent", agency.id)
    # 站点 1: 微信渠道
    site1 = H5Site(id=new_id(), site_key="wechat-01", domain="h5-wechat.example.com", ...)
    # 站点 2: 抖音渠道
    site2 = H5Site(id=new_id(), site_key="douyin-01", domain="h5-douyin.example.com", ...)
    # WABA
    waba1 = create_waba("waba-sh-01", "+86-138-0001", site1.id, agency.id)
    waba2 = create_waba("waba-sh-02", "+86-138-0002", site2.id, agency.id)
    # 下属
    finance = create_admin_user("finance_sh", "Finance@2026", "agent_member", agency.id)
    manager = create_admin_user("manager_sh", "Manager@2026", "agent_member", agency.id)
    support = create_admin_user("support_sh", "Support@2026", "agent_member", agency.id)
    # 会员 + 会话 + 消息 + 工单
    users_site1 = create_users(session, site1, 5)
    users_site2 = create_users(session, site2, 3)
    conversations_site1 = create_conversations(session, users_site1[:3], site1)
    conversations_site2 = create_conversations(session, users_site2[:2], site2)
    create_messages(session, conversations_site1 + conversations_site2, 5)
    create_tickets(session, users_site1[:1], site1)
    # 钱包 + 交易
    create_wallets(session, users_site1 + users_site2)
    # 账单
    create_billing(session, agency, [
        {"type": "monthly", "amount": 2999, "status": "paid"},
        {"type": "per_site", "amount": 5000, "status": "pending"},
    ])
    # 模板绑定
    bind_template(session, agency, tpl1)

def seed_agency_b(session, tpl2):
    """创建代理商 B: 深圳启航"""
    ...  # 类似代理商 A

def seed_products_and_tasks(session, sites):
    """创建商品 + 商品包 + 任务规则 + 任务实例"""
    ...

def seed_languages_and_translations(session, sites):
    """创建语言 + 翻译"""
    ...

def seed_notifications(session, agencies):
    """创建通知"""
    ...

def seed_secrets(session):
    """创建密钥"""
    ...

def main():
    session = SessionLocal()
    try:
        clean_all(session)
        seed_super_admin(session)
        tpl1, tpl2 = seed_templates(session)
        seed_agency_a(session, tpl1)
        seed_agency_b(session, tpl2)
        seed_products_and_tasks(session, [...])
        seed_languages_and_translations(session, [...])
        seed_notifications(session, [...])
        seed_secrets(session)
        session.commit()
        print("✅ 种子数据创建完成！")
    except Exception as e:
        session.rollback()
        print(f"❌ 种子数据创建失败: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()
```

---

## 四、超管端全页面验证（DT-ADMIN）

### DT-ADMIN-001：超管端页面验证清单

| # | 页面 | 路径 | 验证项 | 预期数据 |
|---|------|------|--------|---------|
| 1 | 概览 | `/` | 性能监控卡片 + 统计数字 | CPU/内存/DB 显示真实值 |
| 2 | 会话工作台 | `/conversations` | 会话列表 | 显示 7 个会话（跨站点） |
| 3 | 会话分配 | `/collaboration/assignments` | 分配列表 | 显示已分配的会话 |
| 4 | 工单 | `/collaboration/tickets` | 工单列表 | 显示 2 个工单 |
| 5 | 客户 | `/collaboration/customers` | 客户列表 | 显示 12 个会员 |
| 6 | 审核队列 | `/collaboration/reviews` | 审核列表 | 显示待审核项 |
| 7 | 模板消息 | `/templates` | 模板列表 | 显示模板 |
| 8 | 媒体库 | `/assets/media` | 媒体列表 | 显示媒体 |
| 9 | 标签 | `/assets/tags` | 标签列表 | 显示标签 |
| 10 | 商城数据 | `/ecommerce` | 订单列表 | 显示订单 |
| 11 | 任务规则 | `/marketing/task-rules` | 规则列表 | 显示 3 条规则 |
| 12 | 客服团队 | `/collaboration/members` | 成员列表 | 显示客服成员 |
| 13 | 任务 | `/collaboration/tasks` | 任务列表 | 显示 6 个任务实例 |
| 14 | 自动化规则 | `/collaboration/automation` | 规则列表 | 显示规则 |
| 15 | 角色权限 | `/system/roles` | 角色列表 | 显示角色 |
| 16 | WhatsApp 统计 | `/analytics/whatsapp` | 统计图表 | 显示统计数据 |
| 17 | 报表中心 | `/system/reports` | 报表列表 | 显示报表 |
| 18 | 运营看板 | `/system/operations` | 运营数据 | 显示运营指标 |
| 19 | Meta 账户 | `/meta/accounts` | Meta 账户列表 | 显示账户 |
| 20 | 系统设置 | `/settings` | AI/运行时/语言 | 显示配置 |
| 21 | 集成管理 | `/system/integrations` | 站点/集成 | 显示 3 个站点 |
| 22 | 安全中心 | `/system/security-settings` | 安全配置 | 显示安全设置 |
| 23 | 通知中心 | `/system/notifications` | 通知列表 | 显示 6 条通知 |
| 24 | 监控健康 | `/monitoring` | 系统状态 | 显示健康指标 |
| 25 | 审计日志 | `/audit` | 审计列表 | 显示操作记录 |
| 26 | 告警中心 | `/system/alerts` | 告警列表 | 显示告警 |
| 27 | 通道事件 | `/system/provider-events` | 事件列表 | 显示事件 |
| 28 | 导入导出 | `/system/import-export` | 导入导出 | 显示工具 |
| 29 | 代理商管理 | `/system/agents` | 代理商列表 | 显示 2 个代理商 |
| 30 | H5 模板市场 | `/system/h5-templates` | 模板列表 | 显示 2 套模板 |
| 31 | 站点管理 | `/system/sites` | 站点卡片 | 显示 3 个站点 |
| 32 | WhatsApp API 测试 | `/whatsapp-api-test` | API 测试工具 | 工具可用 |
| 33 | 链路调试 | `/debug` | 调试面板 | 面板可用 |

### 超管端重点验证

| 验证项 | 检查点 |
|--------|--------|
| **代理商管理** | 创建代理商时用户名+密码必填，列表显示 2 个代理商 |
| **代理商详情** | 点击进入详情，显示下属列表 + 站点列表 |
| **站点管理** | 3 个站点卡片，显示代理商归属 + WABA 分配 + 统计数据 |
| **WABA 分配** | 点击"分配 WABA"显示可用 WABA 列表，分配后站点卡片更新 |
| **H5 模板** | 2 套模板显示，可创建/编辑/删除 |
| **性能监控** | Dashboard 显示 CPU/内存/DB/Redis 真实数据 |
| **审计日志** | 显示种子数据创建后的操作记录 |
| **通知中心** | 显示 6 条通知（每代理商 3 条） |
| **数据隔离** | 超管能看到所有代理商+所有站点+所有会话 |

---

## 五、代理商端全页面验证（DT-AGENT）

### DT-AGENT-001：代理商 A 登录验证

| # | 步骤 | 预期 |
|---|------|------|
| 1 | 访问 `/agent/login` | 显示代理商登录页面 |
| 2 | 输入 agent_sh / Agent@2026 | 登录成功 |
| 3 | 跳转 `/agent/` | 显示代理商仪表盘 |

### DT-AGENT-002：代理商端页面验证

| # | 页面 | 路径 | 验证项 | 预期数据 |
|---|------|------|--------|---------|
| 1 | 仪表盘 | `/agent/` | 数据概览 + 审计日志 Tab | 站点统计（锦囊科技的 2 个站点汇总）|
| 2 | 站点管理 | `/agent/sites` | 站点列表 | 只显示锦囊科技的 2 个站点（wechat-01 + douyin-01） |
| 3 | 下属管理 | `/agent/members` | 下属列表 | 显示 3 个下属（财务/经理/客服） |
| 4 | 账单管理 | `/agent/billing` | 账单列表 | 显示 2 条账单（1 已付 + 1 待付） |
| 5 | H5 模板 | `/agent/templates` | 模板选择 | 显示可选模板 + 当前选中模板 |
| 6 | 个人中心 | `/agent/profile` | 修改密码 + 修改信息 | 表单可用 |

### 代理商端重点验证

| 验证项 | 检查点 |
|--------|--------|
| **数据隔离** | 代理商 A 只能看到自己的 2 个站点，看不到代理商 B 的站点 |
| **站点操作** | 编辑站点 / 更换模板 / 管理 WABA 功能可用 |
| **下属管理** | 添加/修改角色/移除下属功能可用 |
| **账单明细** | 点击查看账单详情，显示费用明细（项目/数量/单价/小计） |
| **审计日志** | 只显示自己站点的审计日志 |
| **自助修改** | 修改品牌名称/联系人/密码成功 |
| **模板选择** | 预览模板 + 选择使用 + 生成部署脚本 |
| **登出** | 点击登出 → 跳转 /agent/login |

### DT-AGENT-003：代理商 B 登录验证

| # | 步骤 | 预期 |
|---|------|------|
| 1 | 登出代理商 A | 返回登录页 |
| 2 | 输入 agent_sz / Agent@2026 | 登录成功 |
| 3 | 验证数据隔离 | 只显示启航网络的 1 个站点（xiaohongshu-01） |
| 4 | 下属列表 | 显示 2 个下属（财务 + 客服） |
| 5 | 账单列表 | 显示 1 条账单 |

---

## 六、下属工作台全页面验证（DT-WS）

### DT-WS-001：客服角色验证

| # | 步骤 | 预期 |
|---|------|------|
| 1 | 登录 support_sh / Support@2026 | 跳转 /workspace/ |
| 2 | 工作台首页 | 显示今日概览 |
| 3 | 会话处理 | 显示分配给客服的会话列表 |
| 4 | 发消息 | 可以回复客户消息 |
| 5 | 不能访问财务/站点页面 | 404 或重定向 |
| 6 | 登出 | 跳转登录页 |

### DT-WS-002：财务角色验证

| # | 步骤 | 预期 |
|---|------|------|
| 1 | 登录 finance_sh / Finance@2026 | 跳转 /workspace/ |
| 2 | 资金明细 | 显示会员资金列表 + 提现记录 |
| 3 | 处理提现 | 可以审批提现请求 |
| 4 | 不能访问会话/站点页面 | 404 或重定向 |
| 5 | 登出 | 跳转登录页 |

### DT-WS-003：经理角色验证

| # | 步骤 | 预期 |
|---|------|------|
| 1 | 登录 manager_sh / Manager@2026 | 跳转 /workspace/ |
| 2 | 站点管理 | 显示站点只读列表 |
| 3 | 不能访问会话/财务页面 | 404 或重定向 |
| 4 | 登出 | 跳转登录页 |

---

## 七、H5 客户端验证（DT-H5）

### DT-H5-001：H5 会员端验证

| # | 步骤 | 预期 |
|---|------|------|
| 1 | 访问 H5 登录页 | 显示登录界面 |
| 2 | 会员登录 | 使用种子数据中的会员账号登录 |
| 3 | 首页 | 显示签到卡片 + 任务列表 + 余额 |
| 4 | 任务列表 | 显示任务实例（站点归属正确） |
| 5 | 签到 | 签到成功 + 连续天数 |
| 6 | 邀请好友 | 显示邀请链接 + 统计 |
| 7 | 充值 | 充值页面可用 |
| 8 | 提现 | 提现页面可用 |
| 9 | 个人中心 | 显示个人信息 |
| 10 | 消息 | 显示消息列表 |

---

## 八、跨层级 E2E 测试（DT-E2E）

### DT-E2E-001：超管 → 代理商 → 会员 全链路

| # | 操作 | 角色 | 预期 |
|---|------|------|------|
| 1 | 超管登录 | 超管 | 跳转 `/` |
| 2 | 创建新代理商 | 超管 | 代理商 C 创建成功 |
| 3 | 创建代理商管理员 | 超管 | agent_c 账号创建 |
| 4 | 代理商 C 登录 | 代理商 | 跳转 `/agent/` |
| 5 | 创建新站点 | 代理商 C | 站点创建成功 |
| 6 | 选择 H5 模板 | 代理商 C | 模板绑定成功 |
| 7 | 部署 H5 站点 | 部署 | 站点上线 |
| 8 | 会员注册 | 会员 | 会员注册到该站点 |
| 9 | 会员签到 | 会员 | 签到成功 |
| 10 | 超管查看数据 | 超管 | 超管能看到新代理商 + 新站点 + 新会员 |
| 11 | 代理商查看数据 | 代理商 C | 只能看到自己的站点 + 会员 |

### DT-E2E-002：WABA 分配/收回/重分配

| # | 操作 | 角色 | 预期 |
|---|------|------|------|
| 1 | 超管查看 WABA | 超管 | 显示 3 个 WABA |
| 2 | 分配 WABA 给站点 | 超管 | WABA 绑定成功 |
| 3 | 代理商查看站点 WABA | 代理商 | 显示已绑定的 WABA |
| 4 | 收回 WABA | 超管 | WABA 解绑成功 |
| 5 | 重新分配给另一个站点 | 超管 | WABA 绑定到新站点 |
| 6 | 验证不能一号多人 | 超管 | 尝试分配已绑定的 WABA → 拒绝 |

### DT-E2E-003：会话跨层级流转

| # | 操作 | 角色 | 预期 |
|---|------|------|------|
| 1 | 会员发送消息 | 会员 (H5) | 消息发送成功 |
| 2 | 超管查看会话 | 超管 | 会话出现在会话工作台 |
| 3 | 代理商查看站点会话 | 代理商 | 只能看到自己站点的会话 |
| 4 | 客服处理会话 | 客服 (工作台) | 可以回复消息 |
| 5 | 超管查看消息记录 | 超管 | 可以看到客服的回复 |

### DT-E2E-004：账单生命周期

| # | 操作 | 角色 | 预期 |
|---|------|------|------|
| 1 | 超管创建账单 | 超管 | 账单创建成功（含费用明细） |
| 2 | 代理商查看账单 | 代理商 | 显示新账单 + 费用明细 |
| 3 | 财务查看账单 | 财务 (工作台) | 显示账单列表 |
| 4 | 超管标记已支付 | 超管 | 账单状态变更 |
| 5 | 代理商验证状态 | 代理商 | 账单显示"已支付" |

### DT-E2E-005：模板同步

| # | 操作 | 角色 | 预期 |
|---|------|------|------|
| 1 | 超管更新模板 | 超管 | 模板更新成功 |
| 2 | 验证自动同步 | 系统 | 使用该模板的站点标记需要重新部署 |
| 3 | 代理商查看模板 | 代理商 | 显示模板更新提示 |
| 4 | 代理商重新部署 | 代理商 | 生成新的部署脚本 |

---

## 九、任务清单

| # | 任务 | 类型 | 工作量 |
|---|------|------|--------|
| DT-SEED-001 | 数据清理 + 种子脚本 | 后端 | ~500 行 |
| DT-ADMIN-001 | 超管端 33 页面验证 | 测试 | 逐项验证 |
| DT-AGENT-001 | 代理商 A 登录验证 | 测试 | 逐项验证 |
| DT-AGENT-002 | 代理商端 6 页面验证 | 测试 | 逐项验证 |
| DT-AGENT-003 | 代理商 B 登录验证 | 测试 | 数据隔离验证 |
| DT-WS-001 | 客服角色验证 | 测试 | 逐项验证 |
| DT-WS-002 | 财务角色验证 | 测试 | 逐项验证 |
| DT-WS-003 | 经理角色验证 | 测试 | 逐项验证 |
| DT-H5-001 | H5 会员端验证 | 测试 | 逐项验证 |
| DT-E2E-001 | 超管→代理商→会员全链路 | 测试 | 11 步 |
| DT-E2E-002 | WABA 分配/收回/重分配 | 测试 | 6 步 |
| DT-E2E-003 | 会话跨层级流转 | 测试 | 5 步 |
| DT-E2E-004 | 账单生命周期 | 测试 | 5 步 |
| DT-E2E-005 | 模板同步 | 测试 | 4 步 |

---

## 十、执行顺序

```
Phase 1: 数据准备
  DT-SEED-001  清理脏数据 + 创建种子数据

Phase 2: 超管端验证
  DT-ADMIN-001  33 个页面逐项验证

Phase 3: 代理商端验证
  DT-AGENT-001 ~ 003  代理商 A + B 登录 + 页面验证

Phase 4: 下属工作台验证
  DT-WS-001 ~ 003  客服 + 财务 + 经理 角色验证

Phase 5: H5 客户端验证
  DT-H5-001  会员端 10 项功能验证

Phase 6: 跨层级 E2E
  DT-E2E-001 ~ 005  全链路测试
```

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（数据种子轮）。请读取 docs/task-plan-data-test.md 的 DT-SEED-001 部分，实现完整的数据清理 + 种子数据脚本。

核心要求：
1. 清空所有业务表（保留系统表）
2. 创建完整种子数据：
   - 1 超级管理员 (admin/admin123)
   - 2 套 H5 模板
   - 2 个代理商（上海锦囊 + 深圳启航）
   - 每个代理商：管理员账号 + 下属 + 站点 + WABA + 会员 + 会话 + 消息 + 工单 + 钱包 + 账单 + 通知
   - 商品 + 商品包 + 任务规则 + 任务实例
   - 签到记录 + 邀请记录
   - 3 种语言 + 翻译
   - 2 个密钥
3. 脚本可重复执行（先清理再创建）
4. 执行后验证数据完整性

约束：Docker 内执行，一次性完成。开始吧。
```

## 发给测试 Agent 的文本

```
你是测试 Agent（全链路验证轮）。种子数据就绪后，请读取 docs/task-plan-data-test.md，按 Phase 2~6 顺序逐项验证。

验证顺序：
Phase 2: 超管端 33 页面（重点：代理商管理/站点管理/WABA分配/模板市场/性能监控）
Phase 3: 代理商 A 登录 → 6 页面 → 数据隔离 → 代理商 B 登录验证
Phase 4: 客服/财务/经理 3 个角色分别登录验证
Phase 5: H5 会员端 10 项功能
Phase 6: 5 个跨层级 E2E 流程

每个验证项记录：实际结果 + 截图路径 + 通过/失败。开始吧。
```
