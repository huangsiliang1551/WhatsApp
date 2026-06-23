# Superseded Notice

This planning document is retained for historical context only.

For the current completed backend permission-center contract, use:

- [permission-center-backend-final.md](/E:/codex/WhatsApp/docs/permission-center-backend-final.md)

The live backend surface now includes formal template CRUD, role summary `member_count`, super-admin explicit `agency_id` writes, and template provenance persistence rules that are newer than parts of this planning file.

# 统一后台 + 细粒度权限系统（UNIFIED-PERM）

> **执行角色**: api_agent（后端）+ frontend_agent（前端）
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-19
> **总架构师签发**
> **目标**: 统一三套后台为一套 + 实现 150 个细粒度功能权限 + 层级委派 + 权限模板

---

## 一、架构总览

```
统一后台 (/)
├── 登录: 统一 /login，自动识别角色
├── 菜单: 按权限配置过滤（看不到 = 不存在）
├── 页面: 所有角色共用同一套页面组件
├── 数据: 后端 API 按 agency_id 自动隔离
├── 操作: 页面内按钮按功能权限控制显示/隐藏
└── 配置: 超管在代理商详情页 Drawer 内勾选权限
          代理商在下属管理页 Drawer 内分配权限（子集）
```

### 权限委派链

```
超管（全部权限，不可限制）
  ↓ 在代理商详情 Drawer 内勾选
代理商（只看到被勾选的菜单+功能）
  ↓ 在下属管理 Drawer 内分配（只能分配自己拥有的子集）
下属（只看到代理商分配的菜单+功能）
```

### 角色体系

| 角色 | user_type | 说明 |
|------|-----------|------|
| 超级管理员 | `super_admin` | 全部权限，管理代理商/系统 |
| 代理商管理员 | `agent` | 管理自己的站点/下属/账单 |
| 下属-客服 | `agent_member` + role=`support` | 处理会话/查看客户 |
| 下属-财务 | `agent_member` + role=`finance` | 查看报表/处理账单 |
| 下属-经理 | `agent_member` + role=`manager` | 管理站点/查看数据 |
| 下属-自定义 | `agent_member` + role=`custom_xxx` | 代理商自定义角色 |

---

## 二、权限定义（全量 150 个）

### 权限码规范

```
格式: {module}.{action}
module: 页面标识（如 conversations, tickets, sites）
action: 操作标识（如 view, create, edit, delete, reply）
```

### 完整权限清单

#### 1. 概览 dashboard（3 个）

| 权限码 | 功能 | 默认给代理商 | 默认给下属 |
|--------|------|:----------:|:---------:|
| `dashboard.view` | 查看概览页面 | ✅ | ✅ |
| `dashboard.performance` | 性能监控卡片 | ❌ | ❌ |
| `dashboard.stats` | 业务统计卡片 | ✅ | ✅ |

#### 2. 会话工作台 conversations（11 个）

| 权限码 | 功能 | 默认给代理商 | 标准客服 | 标准经理 |
|--------|------|:----------:|:-------:|:-------:|
| `conversations.view` | 查看会话列表 | ✅ | ✅ | ✅ |
| `conversations.detail` | 查看会话详情 | ✅ | ✅ | ✅ |
| `conversations.reply` | 发送回复 | ✅ | ✅ | ❌ |
| `conversations.handover` | 人工接管 | ✅ | ✅ | ❌ |
| `conversations.restore_ai` | 恢复 AI 托管 | ✅ | ❌ | ❌ |
| `conversations.close` | 关闭会话 | ✅ | ❌ | ❌ |
| `conversations.transfer` | 转接会话 | ✅ | ✅ | ❌ |
| `conversations.block` | 拉黑客户 | ❌ | ❌ | ❌ |
| `conversations.batch` | 批量操作 | ❌ | ❌ | ❌ |
| `conversations.filter` | 高级筛选 | ✅ | ✅ | ✅ |
| `conversations.notes` | 会话备注 | ✅ | ✅ | ✅ |

#### 3. 工单管理 tickets（6 个）

| 权限码 | 功能 | 默认给代理商 | 标准客服 | 标准经理 |
|--------|------|:----------:|:-------:|:-------:|
| `tickets.view` | 查看工单列表 | ✅ | ✅ | ✅ |
| `tickets.create` | 创建工单 | ✅ | ✅ | ❌ |
| `tickets.status` | 变更状态 | ✅ | ✅ | ❌ |
| `tickets.reply` | 回复工单 | ✅ | ✅ | ❌ |
| `tickets.close` | 关闭工单 | ✅ | ❌ | ❌ |
| `tickets.assign` | 分配工单 | ✅ | ❌ | ❌ |

#### 4. 客户管理 customers（6 个）

| 权限码 | 功能 | 默认给代理商 | 标准客服 | 标准经理 |
|--------|------|:----------:|:-------:|:-------:|
| `customers.view` | 查看客户列表 | ✅ | ✅ | ✅ |
| `customers.detail` | 客户 360 详情 | ✅ | ✅ | ✅ |
| `customers.edit_tags` | 编辑客户标签 | ✅ | ❌ | ❌ |
| `customers.timeline` | 访问轨迹 | ✅ | ✅ | ✅ |
| `customers.finance` | 财务信息 | ❌ | ❌ | ✅ |
| `customers.conversations` | 关联会话 | ✅ | ✅ | ✅ |

#### 5. 会话分配 assignments（3 个）

| 权限码 | 功能 | 默认给代理商 | 标准客服 | 标准经理 |
|--------|------|:----------:|:-------:|:-------:|
| `assignments.view` | 查看分配队列 | ✅ | ✅ | ✅ |
| `assignments.accept` | 接受分配 | ✅ | ✅ | ❌ |
| `assignments.reassign` | 重新分配 | ✅ | ❌ | ❌ |

#### 6. 审核队列 reviews（3 个）

| 权限码 | 功能 | 默认给代理商 | 标准经理 |
|--------|------|:----------:|:-------:|
| `reviews.view` | 查看审核队列 | ✅ | ✅ |
| `reviews.approve` | 审核通过 | ✅ | ❌ |
| `reviews.reject` | 审核驳回 | ✅ | ❌ |

#### 7. 模板消息 templates（7 个）

| 权限码 | 功能 | 默认给代理商 | 标准经理 |
|--------|------|:----------:|:-------:|
| `templates.view` | 查看模板列表 | ✅ | ✅ |
| `templates.create` | 创建模板 | ✅ | ❌ |
| `templates.edit` | 编辑模板 | ✅ | ❌ |
| `templates.delete` | 删除模板 | ❌ | ❌ |
| `templates.send` | 发送模板 | ✅ | ❌ |
| `templates.review` | 审核模板 | ❌ | ❌ |
| `templates.sync_meta` | 同步 Meta | ❌ | ❌ |

#### 8. 媒体库 media（3 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `media.view` | 查看媒体库 | ✅ |
| `media.upload` | 上传媒体 | ✅ |
| `media.delete` | 删除媒体 | ❌ |

#### 9. 标签 tags（4 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `tags.view` | 查看标签 | ✅ |
| `tags.create` | 创建标签 | ✅ |
| `tags.edit` | 编辑标签 | ✅ |
| `tags.delete` | 删除标签 | ❌ |

#### 10. 商城数据 ecommerce（3 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `ecommerce.view` | 查看商城 | ✅ |
| `ecommerce.orders` | 订单管理 | ✅ |
| `ecommerce.logistics` | 物流查询 | ✅ |

#### 11. 任务规则 task_rules（7 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `task_rules.view` | 查看规则 | ✅ |
| `task_rules.create` | 创建规则 | ✅ |
| `task_rules.edit` | 编辑规则 | ✅ |
| `task_rules.delete` | 删除规则 | ❌ |
| `task_rules.toggle` | 启停规则 | ✅ |
| `task_rules.signin_config` | 签到配置 | ✅ |
| `task_rules.invite_config` | 邀请配置 | ✅ |

#### 12. 任务管理 tasks（4 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `tasks.view` | 查看任务列表 | ✅ |
| `tasks.push` | 手动推送 | ✅ |
| `tasks.retry` | 重试任务 | ✅ |
| `tasks.detail` | 任务详情 | ✅ |

#### 13. 客服团队 members（4 个）

| 权限码 | 功能 | 默认给代理商 | 标准经理 |
|--------|------|:----------:|:-------:|
| `members.view` | 查看团队 | ✅ | ✅ |
| `members.status` | 查看状态 | ✅ | ✅ |
| `members.workload` | 查看负载 | ✅ | ✅ |
| `members.manage` | 管理团队 | ✅ | ❌ |

#### 14. 自动分配规则 automation（4 个）

| 权限码 | 功能 | 默认给代理商 | 标准经理 |
|--------|------|:----------:|:-------:|
| `automation.view` | 查看规则 | ✅ | ✅ |
| `automation.create` | 创建规则 | ✅ | ❌ |
| `automation.edit` | 编辑规则 | ✅ | ❌ |
| `automation.delete` | 删除规则 | ❌ | ❌ |

#### 15. 角色权限 roles（4 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `roles.view` | 查看角色列表 | ✅ |
| `roles.create` | 创建自定义角色 | ✅ |
| `roles.edit_perms` | 编辑角色权限 | ✅ |
| `roles.delete` | 删除角色 | ❌ |

#### 16. 报表中心 reports（5 个）

| 权限码 | 功能 | 默认给代理商 | 财务专员 | 标准经理 |
|--------|------|:----------:|:-------:|:-------:|
| `reports.view` | 查看报表中心 | ✅ | ✅ | ✅ |
| `reports.whatsapp` | WhatsApp 统计 | ✅ | ✅ | ✅ |
| `reports.operations` | 运营报表 | ✅ | ✅ | ✅ |
| `reports.finance` | 财务报表 | ✅ | ✅ | ✅ |
| `reports.export` | 导出报表 | ❌ | ❌ | ❌ |

#### 17. 运营看板 operations（3 个）

| 权限码 | 功能 | 默认给代理商 | 财务专员 |
|--------|------|:----------:|:-------:|
| `operations.view` | 查看看板 | ✅ | ✅ |
| `operations.queue` | 队列管理 | ✅ | ❌ |
| `operations.batch` | 批量任务 | ❌ | ❌ |

#### 18. 站点管理 sites（10 个）

| 权限码 | 功能 | 默认给代理商 | 标准经理 |
|--------|------|:----------:|:-------:|
| `sites.view` | 查看站点列表 | ✅ | ✅ |
| `sites.create` | 创建站点 | ✅ | ❌ |
| `sites.edit` | 编辑站点 | ✅ | ❌ |
| `sites.delete` | 删除站点 | ❌ | ❌ |
| `sites.waba_assign` | WABA 分配 | ❌ | ❌ |
| `sites.template` | 模板管理 | ✅ | ✅ |
| `sites.deploy` | 部署管理 | ✅ | ❌ |
| `sites.brand_config` | 品牌配置 | ✅ | ❌ |
| `sites.analytics` | 站点分析 | ✅ | ✅ |
| `sites.clone` | 克隆站点 | ❌ | ❌ |

#### 19. 代理商管理 agents（10 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `agents.view` | 查看代理商 | ✅ |
| `agents.create` | 创建代理商 | ✅ |
| `agents.edit` | 编辑代理商 | ✅ |
| `agents.delete` | 删除代理商 | ✅ |
| `agents.reset_password` | 重置密码 | ✅ |
| `agents.billing` | 账单管理 | ✅ |
| `agents.billing_verify` | 核销账单 | ✅ |
| `agents.members` | 下属管理 | ✅ |
| `agents.members_role` | 下属角色 | ✅ |
| `agents.permissions` | 权限配置 | ✅ |

#### 20. H5 模板市场 h5_templates（6 个）

| 权限码 | 功能 | 默认给代理商 |
|--------|------|:----------:|
| `h5_templates.view` | 查看模板 | ✅ |
| `h5_templates.create` | 创建模板 | ❌ |
| `h5_templates.edit` | 编辑模板 | ❌ |
| `h5_templates.delete` | 删除模板 | ❌ |
| `h5_templates.preview` | 预览模板 | ✅ |
| `h5_templates.select` | 选择使用 | ✅ |

#### 21. Meta 账户 meta（6 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `meta.view` | 查看账户 | ✅ |
| `meta.create` | 创建账户 | ✅ |
| `meta.edit` | 编辑账户 | ✅ |
| `meta.delete` | 删除账户 | ✅ |
| `meta.sync_phones` | 同步号码 | ✅ |
| `meta.webhook` | Webhook 管理 | ✅ |

#### 22. 系统设置 settings（6 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `settings.view` | 查看设置 | ✅ |
| `settings.ai_config` | AI 配置 | ✅ |
| `settings.translation` | 翻译配置 | ✅ |
| `settings.languages` | 语言管理 | ✅ |
| `settings.runtime` | 运行时开关 | ✅ |
| `settings.secrets` | 密钥管理 | ✅ |

#### 23. 安全中心 security（3 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `security.view` | 查看安全中心 | ✅ |
| `security.ip_blacklist` | IP 黑名单 | ✅ |
| `security.password_policy` | 密码策略 | ✅ |

#### 24. 通知中心 notifications（3 个）

| 权限码 | 功能 | 默认给代理商 | 财务专员 |
|--------|------|:----------:|:-------:|
| `notifications.view` | 查看通知 | ✅ | ✅ |
| `notifications.mark_read` | 标记已读 | ✅ | ✅ |
| `notifications.manage` | 管理通知规则 | ❌ | ❌ |

#### 25. 监控健康 monitoring（3 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `monitoring.view` | 查看监控 | ✅ |
| `monitoring.errors` | 前端错误 | ✅ |
| `monitoring.uptime` | Uptime 监控 | ✅ |

#### 26. 审计日志 audit（2 个）

| 权限码 | 功能 | 默认给代理商 | 标准经理 |
|--------|------|:----------:|:-------:|
| `audit.view` | 查看审计日志 | ✅ | ✅ |
| `audit.export` | 导出审计数据 | ❌ | ❌ |

#### 27. 告警中心 alerts（2 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `alerts.view` | 查看告警 | ✅ |
| `alerts.manage` | 管理告警规则 | ✅ |

#### 28. 通道事件 provider_events（2 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `provider_events.view` | 查看事件 | ✅ |
| `provider_events.replay` | 重放事件 | ✅ |

#### 29. 导入导出 imports（3 个）— 仅超管

| 权限码 | 功能 | 超管 |
|--------|------|:---:|
| `imports.view` | 查看工具 | ✅ |
| `imports.import` | 导入数据 | ✅ |
| `imports.export` | 导出数据 | ✅ |

#### 30. 个人中心 profile（3 个）— 所有角色默认拥有

| 权限码 | 功能 | 全部角色 |
|--------|------|:-------:|
| `profile.view` | 查看个人信息 | ✅ |
| `profile.edit` | 修改个人信息 | ✅ |
| `profile.change_password` | 修改密码 | ✅ |

### 统计

| 类别 | 权限数 | 说明 |
|------|--------|------|
| 仅超管 | 35 个 | agents(10) + meta(6) + settings(6) + security(3) + monitoring(3) + alerts(2) + provider_events(2) + imports(3) |
| 可分配代理商 | 112 个 | 超管勾选后代理商可见 |
| 所有角色默认 | 3 个 | profile.view/edit/change_password |
| **总计** | **150 个** | |

---

## 三、权限模板（3 个预设）

### 模板 1: 标准客服

| 模块 | 权限 |
|------|------|
| conversations | view, detail, reply, handover, transfer, filter, notes |
| tickets | view, create, status, reply |
| customers | view, detail, timeline, conversations |
| assignments | view, accept |
| profile | view, edit, change_password |
| notifications | view, mark_read |
| **合计** | **20 个权限** |

### 模板 2: 标准经理

| 模块 | 权限 |
|------|------|
| dashboard | view, stats |
| conversations | view, detail, filter, notes |
| tickets | view |
| customers | view, detail, timeline, finance, conversations |
| assignments | view |
| reviews | view |
| templates | view |
| members | view, status, workload |
| automation | view |
| reports | view, whatsapp, operations, finance |
| operations | view |
| sites | view, template, analytics |
| audit | view |
| h5_templates | view, preview |
| notifications | view, mark_read |
| profile | view, edit, change_password |
| **合计** | **32 个权限** |

### 模板 3: 财务专员

| 模块 | 权限 |
|------|------|
| dashboard | view, stats |
| customers | view |
| reports | view, whatsapp, operations, finance |
| operations | view |
| notifications | view, mark_read |
| profile | view, edit, change_password |
| **合计** | **10 个权限** |

**说明**: 代理商可以在模板基础上自由修改（勾选/取消），保存为自定义配置。

---

## 四、后端任务（UP-BE）

### UP-BE-001：权限数据模型

**新增表**: `role_permissions`

```sql
CREATE TABLE role_permissions (
  id VARCHAR(36) PRIMARY KEY,
  agency_id VARCHAR(36) REFERENCES agencies(id),  -- NULL = 超管级模板
  role_name VARCHAR(50) NOT NULL,                 -- "agent" / "support" / "finance" / "manager" / "custom_xxx"
  is_template BOOLEAN DEFAULT FALSE,              -- 是否是预设模板
  template_name VARCHAR(100),                     -- 模板名称（如"标准客服"）
  permissions JSONB NOT NULL DEFAULT '[]',        -- ["conversations.view", "conversations.reply", ...]
  created_by VARCHAR(36),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(agency_id, role_name)
);
```

### UP-BE-002：权限定义注册

**新增**: `app/core/permission_defs.py`

```python
PERMISSION_DEFINITIONS = [
    # 概览
    {"code": "dashboard.view", "module": "dashboard", "label": "查看概览", "super_admin_only": False},
    {"code": "dashboard.performance", "module": "dashboard", "label": "性能监控", "super_admin_only": False},
    # ... 150 个权限定义
    # 仅超管
    {"code": "agents.view", "module": "agents", "label": "查看代理商", "super_admin_only": True},
    {"code": "meta.view", "module": "meta", "label": "查看 Meta 账户", "super_admin_only": True},
    {"code": "settings.view", "module": "settings", "label": "查看系统设置", "super_admin_only": True},
]

# 预设模板
DEFAULT_TEMPLATES = {
    "standard_support": {
        "name": "标准客服",
        "permissions": ["conversations.view", "conversations.detail", ...],
    },
    "standard_manager": {
        "name": "标准经理",
        "permissions": ["dashboard.view", "dashboard.stats", ...],
    },
    "finance_specialist": {
        "name": "财务专员",
        "permissions": ["dashboard.view", "dashboard.stats", ...],
    },
}
```

### UP-BE-003：权限 API

```python
# app/api/routes/permissions_api.py

# 获取权限定义列表
GET /api/permissions/definitions
→ 返回 150 个权限定义（按 module 分组）

# 获取当前用户权限
GET /api/auth/permissions
→ 返回 user_type + role + menus[] + permissions[]

# 获取代理商的权限配置
GET /api/permissions/agency/{agency_id}
→ 返回代理商的所有角色权限配置

# 更新代理商权限（超管调用）
PUT /api/permissions/agency/{agency_id}
Body: { "role_name": "agent", "permissions": ["conversations.view", ...] }
→ 更新指定角色的权限列表
→ 写入审计日志

# 获取权限模板列表
GET /api/permissions/templates
→ 返回预设模板 + 代理商自定义模板

# 从模板应用权限
POST /api/permissions/apply-template
Body: { "agency_id": "xxx", "template_id": "yyy", "target_role": "agent" }
→ 将模板权限应用到指定角色

# 复制其他代理商权限
POST /api/permissions/copy
Body: { "source_agency_id": "xxx", "target_agency_id": "yyy" }
→ 复制权限配置

# 代理商创建自定义角色
POST /api/permissions/custom-role
Body: { "role_name": "custom_xxx", "permissions": [...] }
→ 代理商创建自定义角色（只能分配自己拥有的子集）
```

### UP-BE-004：统一认证（合并三个登录）

```python
# 修改 app/api/routes/agent_auth.py

POST /api/auth/login
→ 自动识别 super_admin / agent / agent_member
→ 返回 token（含 user_type, agency_id, role）
→ 保留原有 3 个登录端点向后兼容

POST /api/auth/logout
→ 统一登出

GET /api/auth/permissions
→ 查询 role_permissions 表
→ 返回该用户可见的 menus[] + permissions[]
```

### UP-BE-005：数据隔离完善

确保所有 API 按 actor 自动过滤（大部分已在 AF-BE-001 中完成）：

```python
# 通用函数
def apply_data_scope(query, model, actor):
    if actor.is_super_admin:
        return query
    return query.where(model.agency_id == actor.agency_id)
```

---

## 五、前端任务（UP-FE）

### UP-FE-001：权限 Hook

**新增**: `frontend/src/hooks/usePermissions.ts`

```typescript
interface Permissions {
  user_type: "super_admin" | "agent" | "agent_member";
  role: string;
  agency_id: string | null;
  agency_name: string | null;
  menus: string[];        // 可见页面 ID
  permissions: string[];  // 功能权限码列表
}

export function usePermissions() {
  const [perms, setPerms] = useState<Permissions | null>(null);
  const can = (code: string) => perms?.permissions.includes(code) ?? false;
  const canSeePage = (pageId: string) => perms?.menus.includes(pageId) ?? false;
  const isSuperAdmin = perms?.user_type === "super_admin";
  return { perms, can, canSeePage, isSuperAdmin };
}
```

### UP-FE-002：菜单权限过滤

**修改**: `frontend/src/App.tsx`

```tsx
// 菜单渲染时按权限过滤
const { canSeePage } = usePermissions();
const visibleRoutes = consoleRoutes.filter(r => r.visibleInNav && canSeePage(r.id));
```

### UP-FE-003：页面内按钮权限控制

在每个页面中使用 `can()` 控制按钮：

```tsx
// ChatPage.tsx
const { can } = usePermissions();

{can("conversations.reply") && <Button>发送回复</Button>}
{can("conversations.handover") && <Button>人工接管</Button>}
{can("conversations.block") && <Button>拉黑</Button>}
```

### UP-FE-004：权限配置 Drawer（超管用）

**修改**: `frontend/src/pages/AgentDetailPage.tsx`

点击代理商详情的"权限配置"按钮，打开 Drawer：

```tsx
<Drawer title={`${agent.name} 权限配置`} width={640}>
  {/* 模板选择 */}
  <Select
    placeholder="从模板加载"
    options={[
      { label: "标准客服", value: "standard_support" },
      { label: "标准经理", value: "standard_manager" },
      { label: "财务专员", value: "finance_specialist" },
      { label: "复制其他代理商...", value: "copy" },
    ]}
    onChange={handleLoadTemplate}
  />

  {/* 权限树（按 module 分组的 Checkbox 列表） */}
  {permissionModules.map(module => (
    <Collapse key={module.name} title={module.label}>
      {module.permissions.map(perm => (
        <Checkbox
          key={perm.code}
          checked={selectedPerms.includes(perm.code)}
          disabled={perm.super_admin_only}
          onChange={(e) => togglePermission(perm.code, e.target.checked)}
        >
          {perm.label}
          <Typography.Text type="secondary"> ({perm.code})</Typography.Text>
        </Checkbox>
      ))}
    </Collapse>
  ))}

  <Space>
    <Button onClick={handleSelectAll}>全选</Button>
    <Button onClick={handleSelectNone}>全不选</Button>
    <Button type="primary" onClick={handleSave}>保存</Button>
  </Space>
</Drawer>
```

### UP-FE-005：下属权限配置 Drawer（代理商用）

**修改**: `frontend/src/pages/AgentsPage.tsx`（下属管理 Tab）

代理商给下属分配权限时，打开 Drawer：

```tsx
<Drawer title={`${member.name} 权限配置`} width={640}>
  <Alert message="只能分配自己拥有的权限" type="info" />

  {/* 角色选择 */}
  <Select
    value={member.role}
    options={[
      { label: "客服", value: "support" },
      { label: "财务", value: "finance" },
      { label: "经理", value: "manager" },
      ...customRoles.map(r => ({ label: r.name, value: r.id })),
    ]}
  />

  {/* 权限树（只显示代理商自己拥有的权限） */}
  {agentPermissions.map(module => (
    <Checkbox key={module.code} disabled={!agentHasPermission(module.code)}>
      {module.label}
    </Checkbox>
  ))}

  <Button type="primary" onClick={handleSave}>保存</Button>
</Drawer>
```

### UP-FE-006：统一登录 + 路由

**修改**: `frontend/src/pages/LoginPage.tsx`

```tsx
// 所有角色统一登录
POST /api/auth/login → 返回 token + user_type
// 统一跳转 /（主后台）
// 菜单自动按权限过滤
```

### UP-FE-007：删除独立页面

**删除 18 个文件**（~1,666 行）：
- `frontend/src/pages/agent/` 全部 12 个文件
- `frontend/src/pages/workspace/` 全部 6 个文件

### UP-FE-008：删除独立路由

**修改**: `frontend/src/App.tsx`
- 删除 `renderAgentPage` 函数
- 删除 `renderWorkspacePage` 函数
- 删除 `/agent/*` 和 `/workspace/*` 路由分支
- 删除所有 Agent/Workspace 懒加载 import

### UP-FE-009：顶部用户信息 + 登出

**修改**: `frontend/src/App.tsx`

```tsx
// 顶部右侧：角色标签 + 代理商名 + 下拉菜单
<Tag>{perms.role}</Tag>
{perms.agency_name && <Tag>{perms.agency_name}</Tag>}
<Dropdown menu={{ items: [
  { key: "profile", label: "个人中心" },
  { key: "password", label: "修改密码" },
  { key: "logout", label: "登出" },
]}}>
  <Avatar />
</Dropdown>
```

### UP-FE-010：个人中心页面

**新增**: `frontend/src/pages/ProfilePage.tsx`

```tsx
// 所有角色可访问
// 显示：用户名 + 角色 + 代理商 + 联系方式
// 修改：品牌名称/联系人/电话/邮箱
// 修改密码表单
```

---

## 六、任务清单

| # | 任务 | 类型 | 工作量 |
|---|------|------|--------|
| UP-BE-001 | 权限数据模型（role_permissions 表） | 后端 | 迁移 ~50 行 |
| UP-BE-002 | 权限定义注册（150 个权限） | 后端 | ~300 行 |
| UP-BE-003 | 权限 API（8 个端点） | 后端 | ~250 行 |
| UP-BE-004 | 统一认证（合并 3 个登录） | 后端 | ~80 行 |
| UP-BE-005 | 数据隔离完善 | 后端 | ~50 行 |
| UP-FE-001 | 权限 Hook | 前端 | ~60 行 |
| UP-FE-002 | 菜单权限过滤 | 前端 | ~20 行 |
| UP-FE-003 | 页面按钮权限控制 | 前端 | ~200 行（分散） |
| UP-FE-004 | 权限配置 Drawer（超管） | 前端 | ~250 行 |
| UP-FE-005 | 下属权限配置 Drawer（代理商） | 前端 | ~200 行 |
| UP-FE-006 | 统一登录 + 路由 | 前端 | ~50 行 |
| UP-FE-007 | 删除独立页面（18 个） | 前端 | 删除 ~1,666 行 |
| UP-FE-008 | 删除独立路由 | 前端 | 删除 ~100 行 |
| UP-FE-009 | 顶部用户信息 + 登出 | 前端 | ~50 行 |
| UP-FE-010 | 个人中心页面 | 前端 | ~150 行 |

**总计**: 15 个任务（5 后端 + 10 前端）
**净效果**: 新增 ~1,900 行 + 删除 ~1,766 行 = 净增 ~134 行（但功能翻倍）

---

## 发给后端 Agent 的文本

```
你是后端开发 Agent（统一权限轮）。请读取 docs/task-plan-unified-perm.md，一次性实现 UP-BE-001 ~ UP-BE-005 全部 5 个后端任务，不要中途暂停。

UP-BE-001（权限数据模型）：
- 迁移：role_permissions 表（agency_id, role_name, is_template, permissions JSONB）
- 预填 3 个默认模板（标准客服/标准经理/财务专员）

UP-BE-002（权限定义注册）：
- app/core/permission_defs.py：150 个权限定义 + 3 个预设模板
- 每个权限：code/module/label/super_admin_only

UP-BE-003（权限 API 8 个端点）：
- GET /api/permissions/definitions（全部权限定义）
- GET /api/auth/permissions（当前用户权限）
- GET /api/permissions/agency/{id}（代理商权限配置）
- PUT /api/permissions/agency/{id}（更新权限 + 审计日志）
- GET /api/permissions/templates（模板列表）
- POST /api/permissions/apply-template（应用模板）
- POST /api/permissions/copy（复制代理商权限）
- POST /api/permissions/custom-role（创建自定义角色）

UP-BE-004（统一认证）：POST /api/auth/login 自动识别角色
UP-BE-005（数据隔离）：确保所有 API 按 actor 过滤

约束：重启 Docker 验证 API。开始吧。
```

## 发给前端 Agent 的文本

```
你是前端 Agent（统一权限轮）。请读取 docs/task-plan-unified-perm.md，一次性实现 UP-FE-001 ~ UP-FE-010 全部 10 个前端任务，不要中途暂停。

UP-FE-001: usePermissions Hook（can/canSeePage/isSuperAdmin）
UP-FE-002: 菜单按 canSeePage 过滤
UP-FE-003: 页面内按钮用 can() 控制（重点：ChatPage/TicketsPage/CustomersPage/SitesPage）
UP-FE-004: 权限配置 Drawer（超管在 AgentDetailPage 内，Checkbox 树 + 模板选择 + 全选/全不选）
UP-FE-005: 下属权限配置 Drawer（代理商分配子集权限）
UP-FE-006: 统一登录（所有角色走 /login → /）
UP-FE-007: 删除 agent/ + workspace/ 下 18 个文件
UP-FE-008: 删除 App.tsx 中 renderAgentPage + renderWorkspacePage + 路由分支
UP-FE-009: 顶部用户信息（角色标签 + 代理商名 + 个人中心/改密/登出）
UP-FE-010: ProfilePage（个人信息 + 修改密码，所有角色可用）

约束：npm run build + 一次性完成。开始吧。
```
