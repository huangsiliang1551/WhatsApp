"""Complete permission definitions for the unified permission system.

150 permissions grouped into 30 modules.
Each definition includes: code, module, label, description, super_admin_only
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# ── Permission definition shape ──────────────────────────────────────────────
# Each entry is a dict with:
#   code: str            – unique permission code like "conversations.view"
#   module: str          – module namespace
#   label: str           – human-readable label in Chinese
#   description: str     – brief description
#   super_admin_only: bool – True = only super admin can assign this


PERMISSION_DEFINITIONS: list[dict[str, Any]] = [
    # ═══════════════════════════════════════════════════════════════════════════
    # 1. 概览 dashboard (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "dashboard.view", "module": "dashboard", "label": "查看概览", "description": "访问概览仪表盘页面", "super_admin_only": False},
    {"code": "dashboard.performance", "module": "dashboard", "label": "性能监控", "description": "查看性能监控卡片", "super_admin_only": False},
    {"code": "dashboard.stats", "module": "dashboard", "label": "业务统计", "description": "查看业务统计卡片", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. 会话工作台 conversations (11)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "conversations.view", "module": "conversations", "label": "查看会话列表", "description": "查看所有会话列表", "super_admin_only": False},
    {"code": "conversations.detail", "module": "conversations", "label": "查看会话详情", "description": "查看单个会话的完整消息记录", "super_admin_only": False},
    {"code": "conversations.reply", "module": "conversations", "label": "发送回复", "description": "在会话中发送消息回复", "super_admin_only": False},
    {"code": "conversations.handover", "module": "conversations", "label": "人工接管", "description": "将会话切换到人工接待模式", "super_admin_only": False},
    {"code": "conversations.restore_ai", "module": "conversations", "label": "恢复 AI 托管", "description": "将会话恢复为 AI 自动回复", "super_admin_only": False},
    {"code": "conversations.close", "module": "conversations", "label": "关闭会话", "description": "关闭一个会话", "super_admin_only": False},
    {"code": "conversations.transfer", "module": "conversations", "label": "转接会话", "description": "将会话转接给其他客服", "super_admin_only": False},
    {"code": "conversations.block", "module": "conversations", "label": "拉黑客户", "description": "将客户加入黑名单", "super_admin_only": False},
    {"code": "conversations.batch", "module": "conversations", "label": "批量操作", "description": "对多个会话执行批量操作", "super_admin_only": False},
    {"code": "conversations.filter", "module": "conversations", "label": "高级筛选", "description": "使用多条件高级筛选会话", "super_admin_only": False},
    {"code": "conversations.notes", "module": "conversations", "label": "会话备注", "description": "查看和添加会话内部备注", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. 工单管理 tickets (6)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "tickets.view", "module": "tickets", "label": "查看工单列表", "description": "访问工单管理页面查看工单", "super_admin_only": False},
    {"code": "tickets.create", "module": "tickets", "label": "创建工单", "description": "创建新的工单", "super_admin_only": False},
    {"code": "tickets.status", "module": "tickets", "label": "变更状态", "description": "修改工单的处理状态", "super_admin_only": False},
    {"code": "tickets.reply", "module": "tickets", "label": "回复工单", "description": "在工单中回复消息", "super_admin_only": False},
    {"code": "tickets.close", "module": "tickets", "label": "关闭工单", "description": "关闭已完成或无需处理的工单", "super_admin_only": False},
    {"code": "tickets.assign", "module": "tickets", "label": "分配工单", "description": "将工单分配给特定处理人", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. 客户管理 customers (6)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "customers.view", "module": "customers", "label": "查看客户列表", "description": "访问客户管理页面查看客户", "super_admin_only": False},
    {"code": "customers.detail", "module": "customers", "label": "客户 360 详情", "description": "查看客户完整信息画像", "super_admin_only": False},
    {"code": "customers.edit_tags", "module": "customers", "label": "编辑客户标签", "description": "为客户添加或移除标签", "super_admin_only": False},
    {"code": "customers.timeline", "module": "customers", "label": "访问轨迹", "description": "查看客户的操作轨迹记录", "super_admin_only": False},
    {"code": "customers.finance", "module": "customers", "label": "财务信息", "description": "查看客户的财务与交易数据", "super_admin_only": False},
    {"code": "customers.conversations", "module": "customers", "label": "关联会话", "description": "查看客户相关的历史会话", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. 会话分配 assignments (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "assignments.view", "module": "assignments", "label": "查看分配队列", "description": "查看待分配的会话队列", "super_admin_only": False},
    {"code": "assignments.accept", "module": "assignments", "label": "接受分配", "description": "接受系统分配的会话", "super_admin_only": False},
    {"code": "assignments.reassign", "module": "assignments", "label": "重新分配", "description": "将会话重新分配给其他人", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. 审核队列 reviews (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "reviews.view", "module": "reviews", "label": "查看审核队列", "description": "访问审核队列页面查看待审项", "super_admin_only": False},
    {"code": "reviews.approve", "module": "reviews", "label": "审核通过", "description": "通过审核项", "super_admin_only": False},
    {"code": "reviews.reject", "module": "reviews", "label": "审核驳回", "description": "驳回审核项", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. 模板消息 templates (7)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "templates.view", "module": "templates", "label": "查看模板列表", "description": "访问消息模板页面", "super_admin_only": False},
    {"code": "templates.create", "module": "templates", "label": "创建模板", "description": "创建新的消息模板草稿", "super_admin_only": False},
    {"code": "templates.edit", "module": "templates", "label": "编辑模板", "description": "编辑消息模板内容", "super_admin_only": False},
    {"code": "templates.delete", "module": "templates", "label": "删除模板", "description": "删除消息模板", "super_admin_only": False},
    {"code": "templates.send", "module": "templates", "label": "发送模板", "description": "发送模板消息给客户", "super_admin_only": False},
    {"code": "templates.review", "module": "templates", "label": "审核模板", "description": "审核模板的 Meta 审批状态", "super_admin_only": False},
    {"code": "templates.sync_meta", "module": "templates", "label": "同步 Meta", "description": "与 Meta 平台同步模板", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 8. 媒体库 media (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "media.view", "module": "media", "label": "查看媒体库", "description": "访问媒体库页面", "super_admin_only": False},
    {"code": "media.upload", "module": "media", "label": "上传媒体", "description": "上传新的媒体文件", "super_admin_only": False},
    {"code": "media.delete", "module": "media", "label": "删除媒体", "description": "删除媒体库中的文件", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 9. 标签 tags (4)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "tags.view", "module": "tags", "label": "查看标签", "description": "查看标签列表", "super_admin_only": False},
    {"code": "tags.create", "module": "tags", "label": "创建标签", "description": "创建新的标签", "super_admin_only": False},
    {"code": "tags.edit", "module": "tags", "label": "编辑标签", "description": "编辑已有标签", "super_admin_only": False},
    {"code": "tags.delete", "module": "tags", "label": "删除标签", "description": "删除标签", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 10. 商城数据 ecommerce (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "ecommerce.view", "module": "ecommerce", "label": "查看商城", "description": "访问商城管理页面", "super_admin_only": False},
    {"code": "ecommerce.orders", "module": "ecommerce", "label": "订单管理", "description": "查看和管理商城订单", "super_admin_only": False},
    {"code": "ecommerce.logistics", "module": "ecommerce", "label": "物流查询", "description": "查询订单物流信息", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 11. 任务规则 task_rules (7)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "task_rules.view", "module": "task_rules", "label": "查看规则", "description": "查看营销任务规则列表", "super_admin_only": False},
    {"code": "task_rules.create", "module": "task_rules", "label": "创建规则", "description": "创建新的任务规则", "super_admin_only": False},
    {"code": "task_rules.edit", "module": "task_rules", "label": "编辑规则", "description": "编辑已有任务规则", "super_admin_only": False},
    {"code": "task_rules.delete", "module": "task_rules", "label": "删除规则", "description": "删除任务规则", "super_admin_only": False},
    {"code": "task_rules.toggle", "module": "task_rules", "label": "启停规则", "description": "启用或暂停任务规则", "super_admin_only": False},
    {"code": "task_rules.signin_config", "module": "task_rules", "label": "签到配置", "description": "配置签到任务的参数", "super_admin_only": False},
    {"code": "task_rules.invite_config", "module": "task_rules", "label": "邀请配置", "description": "配置邀请任务的参数", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 12. 任务管理 tasks (4)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "tasks.view", "module": "tasks", "label": "查看任务列表", "description": "查看营销任务实例列表", "super_admin_only": False},
    {"code": "tasks.push", "module": "tasks", "label": "手动推送", "description": "手动推送营销任务", "super_admin_only": False},
    {"code": "tasks.retry", "module": "tasks", "label": "重试任务", "description": "重试失败的任务", "super_admin_only": False},
    {"code": "tasks.detail", "module": "tasks", "label": "任务详情", "description": "查看单个任务的详细信息", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 13. 客服团队 members (4)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "members.view", "module": "members", "label": "查看团队", "description": "查看客服团队成员列表", "super_admin_only": False},
    {"code": "members.status", "module": "members", "label": "查看状态", "description": "查看客服在线/离线状态", "super_admin_only": False},
    {"code": "members.workload", "module": "members", "label": "查看负载", "description": "查看客服的工作负载情况", "super_admin_only": False},
    {"code": "members.manage", "module": "members", "label": "管理团队", "description": "添加/编辑/移除团队成员", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 14. 自动分配规则 automation (4)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "automation.view", "module": "automation", "label": "查看规则", "description": "查看自动分配规则", "super_admin_only": False},
    {"code": "automation.create", "module": "automation", "label": "创建规则", "description": "创建新的自动分配规则", "super_admin_only": False},
    {"code": "automation.edit", "module": "automation", "label": "编辑规则", "description": "编辑自动分配规则", "super_admin_only": False},
    {"code": "automation.delete", "module": "automation", "label": "删除规则", "description": "删除自动分配规则", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 15. 角色权限 roles (4)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "roles.view", "module": "roles", "label": "查看角色列表", "description": "查看系统的角色列表", "super_admin_only": False},
    {"code": "roles.create", "module": "roles", "label": "创建自定义角色", "description": "创建新的自定义角色", "super_admin_only": False},
    {"code": "roles.edit_perms", "module": "roles", "label": "编辑角色权限", "description": "修改角色的权限配置", "super_admin_only": False},
    {"code": "roles.delete", "module": "roles", "label": "删除角色", "description": "删除自定义角色", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 16. 报表中心 reports (5)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "reports.view", "module": "reports", "label": "查看报表中心", "description": "访问报表中心页面", "super_admin_only": False},
    {"code": "reports.whatsapp", "module": "reports", "label": "WhatsApp 统计", "description": "查看 WhatsApp 消息统计数据", "super_admin_only": False},
    {"code": "reports.operations", "module": "reports", "label": "运营报表", "description": "查看运营数据报表", "super_admin_only": False},
    {"code": "reports.finance", "module": "reports", "label": "财务报表", "description": "查看财务数据报表", "super_admin_only": False},
    {"code": "reports.export", "module": "reports", "label": "导出报表", "description": "导出报表数据为文件", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 17. 运营看板 operations (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "operations.view", "module": "operations", "label": "查看看板", "description": "访问运营看板页面", "super_admin_only": False},
    {"code": "operations.queue", "module": "operations", "label": "队列管理", "description": "管理运营队列", "super_admin_only": False},
    {"code": "operations.batch", "module": "operations", "label": "批量任务", "description": "执行批量运营任务", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 18. 站点管理 sites (10)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "sites.view", "module": "sites", "label": "查看站点列表", "description": "访问站点管理页面", "super_admin_only": False},
    {"code": "sites.create", "module": "sites", "label": "创建站点", "description": "创建新的 H5 站点", "super_admin_only": False},
    {"code": "sites.edit", "module": "sites", "label": "编辑站点", "description": "编辑站点配置", "super_admin_only": False},
    {"code": "sites.delete", "module": "sites", "label": "删除站点", "description": "删除站点", "super_admin_only": False},
    {"code": "sites.waba_assign", "module": "sites", "label": "WABA 分配", "description": "为站点分配 WABA", "super_admin_only": False},
    {"code": "sites.template", "module": "sites", "label": "模板管理", "description": "管理站点的 H5 模板", "super_admin_only": False},
    {"code": "sites.deploy", "module": "sites", "label": "部署管理", "description": "管理站点的部署版本", "super_admin_only": False},
    {"code": "sites.brand_config", "module": "sites", "label": "品牌配置", "description": "配置站点品牌信息", "super_admin_only": False},
    {"code": "sites.analytics", "module": "sites", "label": "站点分析", "description": "查看站点分析数据", "super_admin_only": False},
    {"code": "sites.clone", "module": "sites", "label": "克隆站点", "description": "克隆已有站点", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 19. 代理商管理 agents (10) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "agents.view", "module": "agents", "label": "查看代理商", "description": "查看代理商列表", "super_admin_only": True},
    {"code": "agents.create", "module": "agents", "label": "创建代理商", "description": "创建新的代理商", "super_admin_only": True},
    {"code": "agents.edit", "module": "agents", "label": "编辑代理商", "description": "编辑代理商信息", "super_admin_only": True},
    {"code": "agents.delete", "module": "agents", "label": "删除代理商", "description": "删除代理商", "super_admin_only": True},
    {"code": "agents.reset_password", "module": "agents", "label": "重置密码", "description": "重置代理商的登录密码", "super_admin_only": True},
    {"code": "agents.billing", "module": "agents", "label": "账单管理", "description": "查看代理商的账单列表", "super_admin_only": True},
    {"code": "agents.billing_verify", "module": "agents", "label": "核销账单", "description": "核销代理商的付款账单", "super_admin_only": True},
    {"code": "agents.members", "module": "agents", "label": "下属管理", "description": "管理代理商的下属成员", "super_admin_only": True},
    {"code": "agents.members_role", "module": "agents", "label": "下属角色", "description": "配置代理商下属的角色", "super_admin_only": True},
    {"code": "agents.permissions", "module": "agents", "label": "权限配置", "description": "配置代理商的权限", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 20. H5 模板市场 h5_templates (6)
    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # 21. Meta 账户 meta (6) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "meta.view", "module": "meta", "label": "查看账户", "description": "查看 Meta 账户列表", "super_admin_only": True},
    {"code": "meta.create", "module": "meta", "label": "创建账户", "description": "接入新的 Meta 账户", "super_admin_only": True},
    {"code": "meta.edit", "module": "meta", "label": "编辑账户", "description": "编辑 Meta 账户配置", "super_admin_only": True},
    {"code": "meta.delete", "module": "meta", "label": "删除账户", "description": "删除 Meta 账户", "super_admin_only": True},
    {"code": "meta.sync_phones", "module": "meta", "label": "同步号码", "description": "同步电话号码列表", "super_admin_only": True},
    {"code": "meta.webhook", "module": "meta", "label": "Webhook 管理", "description": "管理 Webhook 订阅", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 22. 系统设置 settings (6) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "settings.view", "module": "settings", "label": "查看设置", "description": "访问系统设置页面", "super_admin_only": True},
    {"code": "settings.ai_config", "module": "settings", "label": "AI 配置", "description": "配置 AI 提供方参数", "super_admin_only": True},
    {"code": "settings.translation", "module": "settings", "label": "翻译配置", "description": "配置翻译服务参数", "super_admin_only": True},
    {"code": "settings.languages", "module": "settings", "label": "语言管理", "description": "管理支持的语言列表", "super_admin_only": True},
    {"code": "settings.runtime", "module": "settings", "label": "运行时开关", "description": "控制系统运行时开关", "super_admin_only": True},
    {"code": "settings.secrets", "module": "settings", "label": "密钥管理", "description": "管理 API 密钥和凭证", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 23. 安全中心 security (3) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "security.view", "module": "security", "label": "查看安全中心", "description": "访问安全中心页面", "super_admin_only": True},
    {"code": "security.ip_blacklist", "module": "security", "label": "IP 黑名单", "description": "管理 IP 黑名单", "super_admin_only": True},
    {"code": "security.password_policy", "module": "security", "label": "密码策略", "description": "配置密码安全策略", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 24. 通知中心 notifications (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "notifications.view", "module": "notifications", "label": "查看通知", "description": "查看系统通知列表", "super_admin_only": False},
    {"code": "notifications.mark_read", "module": "notifications", "label": "标记已读", "description": "将通知标记为已读", "super_admin_only": False},
    {"code": "notifications.manage", "module": "notifications", "label": "管理通知规则", "description": "管理通知推送规则", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 25. 监控健康 monitoring (3) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "monitoring.view", "module": "monitoring", "label": "查看监控", "description": "访问系统监控页面", "super_admin_only": True},
    {"code": "monitoring.errors", "module": "monitoring", "label": "前端错误", "description": "查看前端错误报告", "super_admin_only": True},
    {"code": "monitoring.uptime", "module": "monitoring", "label": "Uptime 监控", "description": "查看服务 uptime 状态", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 26. 审计日志 audit (2)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "audit.view", "module": "audit", "label": "查看审计日志", "description": "查看系统审计日志", "super_admin_only": False},
    {"code": "audit.export", "module": "audit", "label": "导出审计数据", "description": "导出审计日志数据", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 27. 告警中心 alerts (2) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "alerts.view", "module": "alerts", "label": "查看告警", "description": "访问告警中心页面", "super_admin_only": True},
    {"code": "alerts.manage", "module": "alerts", "label": "管理告警规则", "description": "创建/编辑告警规则", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 28. 通道事件 provider_events (2) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "provider_events.view", "module": "provider_events", "label": "查看事件", "description": "查看通道事件记录", "super_admin_only": True},
    {"code": "provider_events.replay", "module": "provider_events", "label": "重放事件", "description": "重放通道事件", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 29. 导入导出 imports (3) — 仅超管
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "imports.view", "module": "imports", "label": "查看工具", "description": "访问导入导出工具页面", "super_admin_only": True},
    {"code": "imports.import", "module": "imports", "label": "导入数据", "description": "导入数据到系统", "super_admin_only": True},
    {"code": "imports.export", "module": "imports", "label": "导出数据", "description": "从系统导出数据", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 30. 个人中心 profile (3) — 所有角色默认拥有
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "profile.view", "module": "profile", "label": "查看个人信息", "description": "查看个人资料页面", "super_admin_only": False},
    {"code": "profile.edit", "module": "profile", "label": "修改个人信息", "description": "编辑个人资料", "super_admin_only": False},
    {"code": "profile.change_password", "module": "profile", "label": "修改密码", "description": "修改自己的登录密码", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 30. 备份管理 backups (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "backups.view", "module": "backups", "label": "查看备份", "description": "查看数据库备份列表", "super_admin_only": True},
    {"code": "backups.create", "module": "backups", "label": "创建备份", "description": "手动创建数据库备份", "super_admin_only": True},
    {"code": "backups.restore", "module": "backups", "label": "恢复备份", "description": "从备份恢复数据库", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 31. 批量操作 batch (4)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "batch.tags", "module": "batch", "label": "批量修改标签", "description": "批量修改客户/会话/工单标签", "super_admin_only": False},
    {"code": "batch.assign", "module": "batch", "label": "批量分配会话", "description": "批量分配会话给客服", "super_admin_only": False},
    {"code": "batch.send_template", "module": "batch", "label": "批量发送模板", "description": "批量发送模板消息", "super_admin_only": False},
    {"code": "batch.import", "module": "batch", "label": "批量导入商品", "description": "批量导入商品 CSV", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 32. 知识库 knowledge (3)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "knowledge.view", "module": "knowledge", "label": "查看知识库", "description": "查看知识库文章和分类", "super_admin_only": False},
    {"code": "knowledge.manage", "module": "knowledge", "label": "管理知识库", "description": "创建/编辑/删除知识库文章和分类", "super_admin_only": False},
    {"code": "knowledge.ai_test", "module": "knowledge", "label": "AI 回答测试", "description": "测试 AI 从知识库检索回答", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 33. 客户画像 customer_profile (1)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "customer_profile.view", "module": "customer_profile", "label": "查看客户画像", "description": "查看客户行为数据和标签", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 34. 自动打标 auto_tag (1)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "auto_tag.manage", "module": "auto_tag", "label": "管理打标规则", "description": "管理客户自动打标规则", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 35. API 调用统计 api_stats (1)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "api_stats.view", "module": "api_stats", "label": "查看 API 统计", "description": "查看 API 调用统计数据", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 36. 频率限制 rate_limits (1)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "rate_limits.manage", "module": "rate_limits", "label": "管理频率限制", "description": "管理 API 调用频率规则和 IP 封禁", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 37. 邮件配置 email_config (1)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "email_config.manage", "module": "email_config", "label": "管理邮件配置", "description": "管理 SMTP 邮件服务器配置", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 38. 健康检查 health_check (1)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "health_check.view", "module": "health_check", "label": "查看健康检查", "description": "查看系统健康检查结果", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 39. AI 聊天配置 ai_chat_config (8)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "ai_chat_config.view_system", "module": "ai_chat_config", "label": "查看系统配置", "description": "查看 AI 聊天系统默认配置", "super_admin_only": True},
    {"code": "ai_chat_config.edit_system", "module": "ai_chat_config", "label": "编辑系统配置", "description": "编辑 AI 聊天系统默认配置", "super_admin_only": True},
    {"code": "ai_chat_config.view_agency", "module": "ai_chat_config", "label": "查看代理商配置", "description": "查看代理商的 AI 聊天配置", "super_admin_only": False},
    {"code": "ai_chat_config.edit_agency", "module": "ai_chat_config", "label": "编辑代理商配置", "description": "编辑代理商的 AI 聊天配置", "super_admin_only": False},
    {"code": "ai_chat_config.reset_agency", "module": "ai_chat_config", "label": "重置代理商配置", "description": "将代理商配置恢复为系统默认", "super_admin_only": True},
    {"code": "ai_chat_config.test", "module": "ai_chat_config", "label": "测试聊天配置", "description": "使用真实数据测试 AI 聊天配置", "super_admin_only": False},
    {"code": "ai_chat_config.view_tools", "module": "ai_chat_config", "label": "查看工具列表", "description": "查看可用 AI 工具及说明", "super_admin_only": False},
    {"code": "ai_chat_config.edit_tools", "module": "ai_chat_config", "label": "编辑工具配置", "description": "配置 AI 工具的白名单和参数", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 40. AI 计费 ai_billing (6)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "ai_billing.view_rates", "module": "ai_billing", "label": "查看费率", "description": "查看 AI Provider 费率列表", "super_admin_only": False},
    {"code": "ai_billing.edit_rates", "module": "ai_billing", "label": "编辑费率", "description": "编辑 AI Provider 费率", "super_admin_only": True},
    {"code": "ai_billing.view_quotas", "module": "ai_billing", "label": "查看免费额度", "description": "查看代理商免费额度配置", "super_admin_only": False},
    {"code": "ai_billing.edit_quotas", "module": "ai_billing", "label": "编辑免费额度", "description": "编辑代理商免费额度", "super_admin_only": True},
    {"code": "ai_billing.view_usage", "module": "ai_billing", "label": "查看用量", "description": "查看 AI/翻译用量统计", "super_admin_only": False},
    {"code": "ai_billing.view_bills", "module": "ai_billing", "label": "查看账单", "description": "查看月度账单", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 41. 汇率管理 exchange_rate (2)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "exchange_rate.view", "module": "exchange_rate", "label": "查看汇率", "description": "查看汇率列表", "super_admin_only": False},
    {"code": "exchange_rate.edit", "module": "exchange_rate", "label": "编辑汇率", "description": "编辑汇率", "super_admin_only": True},

    # ═══════════════════════════════════════════════════════════════════════════
    # 42. 财务管理 finance (10)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "finance.view_channels", "module": "finance", "label": "查看渠道", "description": "查看支付渠道列表", "super_admin_only": False},
    {"code": "finance.edit_channels", "module": "finance", "label": "编辑渠道", "description": "创建/编辑/删除支付渠道", "super_admin_only": True},
    {"code": "finance.view_recharge", "module": "finance", "label": "查看充值", "description": "查看充值记录", "super_admin_only": False},
    {"code": "finance.view_withdrawal", "module": "finance", "label": "查看提现", "description": "查看提现记录", "super_admin_only": False},
    {"code": "finance.approve_withdrawal", "module": "finance", "label": "审批提现", "description": "审批/拒绝提现申请", "super_admin_only": False},
    {"code": "withdrawal.duplicate_account.view", "module": "withdrawal", "label": "查看重复提现账户", "description": "查看提现重复账户风险明细", "super_admin_only": False},
    {"code": "withdrawal.account_sensitive.view", "module": "withdrawal", "label": "查看敏感提现账户", "description": "查看提现账户敏感信息", "super_admin_only": False},
    {"code": "member.popover.view", "module": "member", "label": "查看会员浮层", "description": "允许在各列表中打开会员信息浮层", "super_admin_only": False},
    {"code": "member.sensitive.view", "module": "member", "label": "查看会员敏感信息", "description": "查看会员敏感字段", "super_admin_only": False},
    {"code": "member.finance_breakdown.view", "module": "member", "label": "查看会员财务拆分", "description": "查看会员余额与累计财务摘要", "super_admin_only": False},

    # ═══════════════════════════════════════════════════════════════════════════
    # 43. 财务设置 finance_settings (2)
    # ═══════════════════════════════════════════════════════════════════════════
    {"code": "finance_settings.view", "module": "finance_settings", "label": "查看财务设置", "description": "查看财务设置页面", "super_admin_only": False},
    {"code": "finance_settings.edit", "module": "finance_settings", "label": "编辑财务设置", "description": "编辑财务设置", "super_admin_only": True},
]

# ── Verify count ─────────────────────────────────────────────────────────

# ── Module grouping helper ────────────────────────────────────────────────────
MODULE_ORDER: list[str] = [
    "dashboard", "conversations", "tickets", "customers", "assignments",
    "reviews", "templates", "media", "tags", "ecommerce",
    "task_rules", "tasks", "members", "automation", "roles",
    "reports", "operations", "sites", "agents",
    "meta", "settings", "security", "notifications", "monitoring",
    "audit", "alerts", "provider_events", "imports", "profile",
    "backups", "batch", "knowledge", "customer_profile", "auto_tag",
    "api_stats", "rate_limits", "email_config", "health_check",
    "ai_chat_config",
    "ai_billing",
    "exchange_rate",
    "finance",
    "finance_settings",
    "runtime",
    "users",
    "audience_rules",
    "canned_responses",
    "ai_providers",
    "dev",
]


def get_permissions_by_module() -> dict[str, list[dict]]:
    """Group permission definitions by module name."""
    result: dict[str, list[dict]] = {}
    for module in MODULE_ORDER:
        result[module] = [p for p in PERMISSION_DEFINITIONS if p["module"] == module]
    return result


# ── Default templates ────────────────────────────────────────────────────────
DEFAULT_TEMPLATES: dict[str, dict[str, Any]] = {
    "standard_support": {
        "name": "标准客服",
        "description": "客服人员的基础权限，包含会话处理、工单管理和客户查看",
        "permissions": [
            "conversations.view", "conversations.detail", "conversations.reply",
            "conversations.handover", "conversations.transfer", "conversations.filter",
            "conversations.notes",
            "tickets.view", "tickets.create", "tickets.status", "tickets.reply",
            "customers.view", "customers.detail", "customers.timeline", "customers.conversations",
            "assignments.view", "assignments.accept",
            "profile.view", "profile.edit", "profile.change_password",
            "notifications.view", "notifications.mark_read",
            "batch.tags", "batch.assign", "batch.send_template",
            "knowledge.view", "knowledge.manage",
            "customer_profile.view",
            "api_stats.view", "health_check.view",
        ],
    },
    "standard_manager": {
        "name": "标准经理",
        "description": "经理级别的管理权限，可查看报表和审核",
        "permissions": [
            "dashboard.view", "dashboard.stats",
            "conversations.view", "conversations.detail", "conversations.filter", "conversations.notes",
            "tickets.view",
            "customers.view", "customers.detail", "customers.timeline", "customers.finance",
            "customers.conversations",
            "assignments.view",
            "reviews.view",
            "templates.view",
            "members.view", "members.status", "members.workload",
            "automation.view",
            "reports.view", "reports.whatsapp", "reports.operations", "reports.finance",
            "operations.view",
            "sites.view", "sites.template", "sites.analytics",
            "audit.view",
            "notifications.view", "notifications.mark_read",
            "profile.view", "profile.edit", "profile.change_password",
            "batch.tags", "batch.assign",
            "knowledge.view",
            "customer_profile.view",
            "api_stats.view", "health_check.view",
        ],
    },
    "finance_specialist": {
        "name": "财务专员",
        "description": "财务人员的权限，可查看报表和财务数据",
        "permissions": [
            "dashboard.view", "dashboard.stats",
            "customers.view",
            "reports.view", "reports.whatsapp", "reports.operations", "reports.finance",
            "operations.view",
            "notifications.view", "notifications.mark_read",
            "profile.view", "profile.edit", "profile.change_password",
        ],
    },
}

EXTENSION_PERMISSION_DEFINITIONS: list[dict[str, Any]] = [
    {"code": "runtime.view", "module": "runtime", "label": "View Runtime", "description": "View runtime state and diagnostics.", "super_admin_only": False},
    {"code": "runtime.edit", "module": "runtime", "label": "Edit Runtime", "description": "Change runtime state and replay runtime operations.", "super_admin_only": False},
    {"code": "users.view", "module": "users", "label": "View Users", "description": "List and inspect platform users.", "super_admin_only": False},
    {"code": "users.create", "module": "users", "label": "Create Users", "description": "Create platform users.", "super_admin_only": False},
    {"code": "users.edit", "module": "users", "label": "Edit Users", "description": "Review and edit platform user state.", "super_admin_only": False},
    {"code": "users.delete", "module": "users", "label": "Delete Users", "description": "Delete platform users.", "super_admin_only": False},
    {"code": "audience_rules.view", "module": "audience_rules", "label": "View Audience Rules", "description": "List audience rule sets.", "super_admin_only": False},
    {"code": "audience_rules.create", "module": "audience_rules", "label": "Create Audience Rules", "description": "Create audience rule sets.", "super_admin_only": False},
    {"code": "audience_rules.edit", "module": "audience_rules", "label": "Edit Audience Rules", "description": "Update audience rule sets.", "super_admin_only": False},
    {"code": "audience_rules.delete", "module": "audience_rules", "label": "Delete Audience Rules", "description": "Delete audience rule sets.", "super_admin_only": False},
    {"code": "tasks.create", "module": "tasks", "label": "Create Tasks", "description": "Create task instances from the platform task center.", "super_admin_only": False},
    {"code": "tasks.claim", "module": "tasks", "label": "Claim Tasks", "description": "Claim task instances for members in the H5 flow.", "super_admin_only": False},
    {"code": "tasks.submit", "module": "tasks", "label": "Submit Tasks", "description": "Submit task completion payloads for review.", "super_admin_only": False},
    {"code": "conversations.tags", "module": "conversations", "label": "Manage Conversation Tags", "description": "Add or remove tags from conversations.", "super_admin_only": False},
    {"code": "conversations.translate", "module": "conversations", "label": "Translate Conversations", "description": "Translate conversation content for agents.", "super_admin_only": False},
    {"code": "conversations.wake", "module": "conversations", "label": "Wake Conversations", "description": "Re-open or wake sleeping conversations back into the queue.", "super_admin_only": False},
    {"code": "conversations.ai_preview", "module": "conversations", "label": "Preview AI Replies", "description": "Preview AI-generated replies without sending them.", "super_admin_only": False},
    {"code": "conversations.reopen", "module": "conversations", "label": "Reopen Conversations", "description": "Reopen closed conversations.", "super_admin_only": False},
    {"code": "conversations.sentiment", "module": "conversations", "label": "View Conversation Sentiment", "description": "Inspect sentiment analysis for conversations.", "super_admin_only": False},
    {"code": "conversations.sla", "module": "conversations", "label": "View Conversation SLA", "description": "Inspect SLA diagnostics for conversations.", "super_admin_only": False},
    {"code": "customers.edit_lifecycle", "module": "customers", "label": "Edit Customer Lifecycle", "description": "Update lifecycle stage and related customer status fields.", "super_admin_only": False},
    {"code": "templates.rebuild_stats", "module": "templates", "label": "Rebuild Template Stats", "description": "Rebuild template delivery statistics.", "super_admin_only": False},
    {"code": "monitoring.manage", "module": "monitoring", "label": "Manage Monitoring", "description": "Acknowledge monitoring events and manage client-side diagnostics.", "super_admin_only": False},
    {"code": "backups.delete", "module": "backups", "label": "Delete Backups", "description": "Delete backup snapshots and metadata.", "super_admin_only": True},
    {"code": "canned_responses.view", "module": "canned_responses", "label": "View Canned Responses", "description": "List canned responses.", "super_admin_only": False},
    {"code": "canned_responses.create", "module": "canned_responses", "label": "Create Canned Responses", "description": "Create canned responses.", "super_admin_only": False},
    {"code": "canned_responses.edit", "module": "canned_responses", "label": "Edit Canned Responses", "description": "Edit canned responses.", "super_admin_only": False},
    {"code": "canned_responses.delete", "module": "canned_responses", "label": "Delete Canned Responses", "description": "Delete canned responses.", "super_admin_only": False},
    {"code": "ai_providers.view", "module": "ai_providers", "label": "View AI Providers", "description": "View AI provider configs and overrides.", "super_admin_only": False},
    {"code": "ai_providers.create", "module": "ai_providers", "label": "Create AI Providers", "description": "Create AI provider configs.", "super_admin_only": True},
    {"code": "ai_providers.edit", "module": "ai_providers", "label": "Edit AI Providers", "description": "Update AI provider configs.", "super_admin_only": True},
    {"code": "ai_providers.delete", "module": "ai_providers", "label": "Delete AI Providers", "description": "Delete AI provider configs.", "super_admin_only": True},
    {"code": "ai_providers.test", "module": "ai_providers", "label": "Test AI Providers", "description": "Test AI provider connectivity.", "super_admin_only": True},
    {"code": "ai_providers.override", "module": "ai_providers", "label": "Override AI Providers", "description": "Manage account-level AI provider overrides.", "super_admin_only": True},
    {"code": "dev.mock", "module": "dev", "label": "Use Dev Mock", "description": "Use mock and development-only routes.", "super_admin_only": True},
    # ── 归属 / AI 接待 / 入口链接 权限（spec 第 11 节） ──
    {"code": "entry_links.view", "module": "entry_links", "label": "查看入口链接", "description": "查看入口链接列表与统计", "super_admin_only": False},
    {"code": "entry_links.manage", "module": "entry_links", "label": "管理入口链接", "description": "创建 / 撤销 / 轮换入口链接", "super_admin_only": False},
    {"code": "entry_links.own", "module": "entry_links", "label": "查看自有入口链接", "description": "仅查看自己作为客服/AI 的入口链接", "super_admin_only": False},
    {"code": "ai_agents.view", "module": "ai_agents", "label": "查看 AI 主体", "description": "查看 AI Agent 列表与详情", "super_admin_only": False},
    {"code": "ai_agents.manage", "module": "ai_agents", "label": "管理 AI 主体", "description": "创建 / 修改 / 健康检查 AI Agent", "super_admin_only": False},
    {"code": "ai_agents.disable", "module": "ai_agents", "label": "停用 / 归档 AI 主体", "description": "禁用 / 归档 AI Agent 及其相关链接", "super_admin_only": False},
    {"code": "member_ownership.view", "module": "member_ownership", "label": "查看会员归属", "description": "查看会员当前 / 历史人力归属", "super_admin_only": False},
    {"code": "member_ownership.transfer", "module": "member_ownership", "label": "划转会员归属", "description": "将会员的人力归属从 A 划转给 B", "super_admin_only": False},
    {"code": "member_ownership.history", "module": "member_ownership", "label": "查看归属历史", "description": "查看会员 / 客服 / AI 归属历史与审计", "super_admin_only": False},
    {"code": "member_ai_ownership.view", "module": "member_ai_ownership", "label": "查看会员 AI 归属", "description": "查看会员当前 / 历史 AI 归属", "super_admin_only": False},
    {"code": "member_ai_ownership.transfer", "module": "member_ai_ownership", "label": "划转会员 AI 归属", "description": "批量划转会员的 AI 归属", "super_admin_only": False},
    {"code": "member_ai_ownership.failover", "module": "member_ai_ownership", "label": "执行 AI 永久迁移", "description": "触发 AI 永久迁移 / failover", "super_admin_only": False},
    {"code": "conversations.ai.view", "module": "conversation_ai", "label": "查看会话 AI 归属", "description": "查看会话当前 AI 接待归属与 failover 状态", "super_admin_only": False},
    {"code": "conversations.ai.switch", "module": "conversation_ai", "label": "切换会话 AI", "description": "手动切换会话的接待 AI", "super_admin_only": False},
    {"code": "conversations.ai.handover", "module": "conversation_ai", "label": "转人工 / AI 恢复", "description": "会话转人工或恢复 AI 托管", "super_admin_only": False},
    {"code": "conversations.ai.resume", "module": "conversation_ai", "label": "恢复 AI 接待", "description": "将会话从人工模式恢复到 AI 接待", "super_admin_only": False},
    {"code": "reports.ownership.view", "module": "reports_ownership", "label": "查看归属报表", "description": "查看人力 / AI 归属 / EntryLink 转化 / 异常报表", "super_admin_only": False},
    {"code": "reports.ai.view", "module": "reports_ai", "label": "查看 AI 报表", "description": "查看 AI 自动消息 / failover / handover 等报表", "super_admin_only": False},
    {"code": "reports.entry_links.view", "module": "reports_entry_links", "label": "查看入口链接报表", "description": "查看入口链接转化、注册、会话、消息数等报表", "super_admin_only": False},
    {"code": "site.registration_config.view", "module": "site_registration", "label": "查看站点注册配置", "description": "查看站点注册与归属配置", "super_admin_only": False},
    {"code": "site.registration_config.manage", "module": "site_registration", "label": "管理站点注册配置", "description": "编辑站点注册与归属配置", "super_admin_only": False},
    {"code": "ownership_audit.view", "module": "ownership_audit", "label": "查看归属审计", "description": "查看 OwnershipAuditEvent 审计事件", "super_admin_only": False},
]

PERMISSION_DEFINITIONS = [*PERMISSION_DEFINITIONS, *EXTENSION_PERMISSION_DEFINITIONS]

MODULE_PAGE_MAP: dict[str, str] = {
    "dashboard": "dashboard",
    "conversations": "conversations",
    "tickets": "tickets",
    "customers": "customers",
    "assignments": "assignments",
    "reviews": "reviews",
    "templates": "templates",
    "media": "media",
    "tags": "tags",
    "ecommerce": "ecommerce",
    "task_rules": "task_rules",
    "tasks": "tasks",
    "members": "members",
    "automation": "automation",
    "roles": "agents",
    "reports": "reports",
    "operations": "operations",
    "sites": "sites",
    "agents": "agents",
    "meta": "meta",
    "settings": "settings",
    "security": "security_settings",
    "notifications": "notifications",
    "monitoring": "monitoring",
    "runtime": "operations",
    "audit": "audit",
    "alerts": "alerts",
    "provider_events": "provider_events",
    "imports": "imports",
    "profile": "profile",
    "backups": "backups",
    "batch": "batch",
    "knowledge": "knowledge",
    "customer_profile": "customer_profile",
    "api_stats": "api_stats",
    "rate_limits": "rate_limits",
    "health_check": "health_check",
    "ai_chat_config": "ai_chat_config",
    "ai_billing": "ai_billing",
    "exchange_rate": "exchange_rate",
    "finance": "finance",
    "finance_settings": "finance_settings",
    "audience_rules": "audience_rules",
}

MODULE_ADDITIONAL_PAGE_MAP: dict[str, tuple[str, ...]] = {
    "task_rules": ("invite_management", "invite_relations", "invite_rewards"),
}

PERMISSION_REGISTRY: dict[str, dict[str, Any]] = {
    definition["code"]: definition for definition in PERMISSION_DEFINITIONS
}

assert len(PERMISSION_REGISTRY) == len(PERMISSION_DEFINITIONS), "Permission codes must be unique."


def get_permissions_by_module() -> dict[str, list[dict[str, Any]]]:
    """Group permission definitions by module name."""
    grouped: dict[str, list[dict[str, Any]]] = {module: [] for module in MODULE_ORDER}
    for definition in PERMISSION_DEFINITIONS:
        grouped.setdefault(definition["module"], []).append(definition)
    return grouped


def get_permissions_for_module(module: str) -> list[dict[str, Any]]:
    return list(get_permissions_by_module().get(module, []))


def permission_exists(permission_code: str) -> bool:
    normalized = permission_code.strip()
    return bool(normalized) and normalized in PERMISSION_REGISTRY


def get_permission_definition(permission_code: str) -> dict[str, Any]:
    normalized = permission_code.strip()
    definition = PERMISSION_REGISTRY.get(normalized)
    if definition is None:
        raise ValueError(f"Unknown permission code '{permission_code}'.")
    return definition


def normalize_permission_code(permission_code: str) -> str:
    normalized = permission_code.strip()
    if not normalized:
        raise ValueError("Permission code must not be empty.")
    if normalized not in PERMISSION_REGISTRY:
        raise ValueError(f"Unknown permission code '{permission_code}'.")
    return normalized


def partition_permission_codes(permission_codes: Iterable[str]) -> tuple[list[str], list[str]]:
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for permission_code in permission_codes:
        try:
            normalized = normalize_permission_code(permission_code)
        except ValueError:
            stripped = permission_code.strip()
            if stripped:
                invalid.append(stripped)
            continue
        if normalized in seen:
            continue
        valid.append(normalized)
        seen.add(normalized)
    return valid, invalid


def normalize_permission_codes(
    permission_codes: Iterable[str],
    *,
    ignore_unknown: bool = False,
) -> list[str]:
    normalized, invalid = partition_permission_codes(permission_codes)
    if invalid and not ignore_unknown:
        raise ValueError(f"Unknown permission codes: {', '.join(invalid)}")
    return normalized


def validate_permission_codes(permission_codes: Iterable[str]) -> list[str]:
    return normalize_permission_codes(permission_codes)


def normalize_template_permissions(permission_codes: Iterable[str]) -> list[str]:
    return normalize_permission_codes(permission_codes)


def get_page_for_permission(permission_code: str) -> str | None:
    module = get_permission_definition(permission_code)["module"]
    return MODULE_PAGE_MAP.get(module)


def derive_menu_pages(permission_codes: Iterable[str]) -> list[str]:
    pages: set[str] = set()
    for permission_code in normalize_permission_codes(permission_codes, ignore_unknown=True):
        definition = get_permission_definition(permission_code)
        module = definition["module"]
        page = MODULE_PAGE_MAP.get(module)
        if page:
            pages.add(page)
        for extra_page in MODULE_ADDITIONAL_PAGE_MAP.get(module, ()):
            pages.add(extra_page)
    return sorted(pages)


for _template in DEFAULT_TEMPLATES.values():
    _template["permissions"] = normalize_template_permissions(_template["permissions"])
