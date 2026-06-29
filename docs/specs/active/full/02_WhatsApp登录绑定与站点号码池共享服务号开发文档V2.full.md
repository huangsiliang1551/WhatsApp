# WhatsApp登录绑定与站点号码池共享服务号开发文档V2

> 适用仓库：`https://github.com/huangsiliang1551/WhatsApp`  
> 目标读者：Codex 开发线程、后端、前端、测试、部署人员  
> 重要性：P0 / S 级  
> 版本：V2  
> 基于：`WhatsApp登录绑定与Meta生产部署整合开发文档V1`  
> 核心变化：V1 默认“登录绑定号”和“AI聊天号”可分离；V2 改为默认使用**站点号码池共享服务号**。每个 H5 站点配置多个 WABA / Phone Number，系统按站点号码池为用户分配服务号，该服务号同时承担 WhatsApp 登录、绑定、AI咨询和人工客服接待。

---

## 0. 产品和架构结论

### 0.1 本期确定规则

1. **不再默认配置一个专门的绑定号。**
   - 登录、绑定、AI聊天、人工客服默认共用同一个站点服务号码池。
   - 不是全平台一个号，而是按 H5 站点配置一组 WABA / Phone Number。

2. **每个 H5 站点可配置几十个 WABA / Phone Number。**
   - 系统给用户生成 WhatsApp 登录/绑定/咨询链接时，从该站点号码池中选择一个健康号码。
   - 该号码会生成 `wa.me` 链接，内容自动预填在 WhatsApp 聊天窗口中，用户只需要点击发送。

3. **一个 `phone_number_id` 同一时间只能属于一个 active H5 站点号码池。**
   - 如果站点关闭或号码解绑，可以释放该号码。
   - 释放后可以迁移给其他站点使用。
   - 迁移必须有冷却期、审计和冲突检查。

4. **`wa_id` 全平台唯一绑定。**
   - 同一个 WhatsApp 用户 `wa_id` 在整个系统中只能绑定一个 H5 用户。
   - 用户 A 在 H5A 绑定后，再去 H5B 用同一个 WhatsApp 登录/注册/绑定，必须失败。
   - 失败提示：该 WhatsApp 已绑定其他站点账号，请联系客服。
   - 不创建 H5B 账号，不登录 H5B，不允许进入任务/资金链路。

5. **未绑定用户普通消息不进入正式 AI。**
   - 如果未绑定用户直接给某个站点服务号发普通消息，系统回复绑定引导链接。
   - 用户点击该链接后，H5 自动绑定这个 `wa_id`。
   - 如果该 `wa_id` 已绑定其他站点账号，则链接打开后也必须失败。

6. **已绑定用户发消息到同站点号码池其他号码，可以正常对话。**
   - 后台合并成同一个客户会话。
   - 消息记录保存本次 `inbound_phone_number_id`。
   - 回复时优先使用用户本次发来的 `phone_number_id`，避免 WhatsApp 聊天窗口跳号。

7. **号码被限制或失效时，绑定不失效。**
   - `wa_id -> user_id` 绑定关系保持。
   - 后续 H5 拉起链接重新分配到该站点号码池中的其他健康号码。
   - 如果旧号码还能收到消息，回复“服务窗口已更新，请返回 H5 重新打开”。
   - 如果旧号码完全不可用，只能靠 H5 页面引导进入新窗口。

8. **号码低质量时只停止新用户分配。**
   - 老客户主动咨询仍继续服务。
   - 停止新绑定、新登录、新自动注册分配。
   - 停止主动营销/外呼类消息。
   - 继续允许用户主动发来消息后的服务回复。

9. **后台必须支持号码池运营。**
   - 号码权重
   - 每日新绑定上限
   - 最大活跃会话数
   - 仅服务老客户
   - 暂停新用户分配
   - 强制迁移指定用户
   - 健康状态、质量状态、Webhook状态、Outbound状态

10. **所有 LOGIN / BIND / AUTO_BIND 命令必须在 AI 前处理。**
    - 命中认证/绑定命令后，不进入 AI。
    - 不写入普通聊天消息。
    - 只写 auth/binding attempt log 和客户时间线系统事件。

---

## 1. 官方机制说明

WhatsApp Cloud API 没有微信式 OAuth 登录页。本系统使用以下能力实现类微信体验：

```text
wa.me / Click-to-Chat 链接
+
预填文本 message
+
用户点击发送
+
Meta Webhook 收到入站消息
+
后端根据 token / wa_id 完成登录或绑定
+
H5 轮询状态或打开绑定链接确认
```

关键点：

```text
1. wa.me 链接可以打开指定 WhatsApp 号码的聊天窗口。
2. text 参数可以预填消息内容。
3. 用户必须点击发送，系统才会收到 webhook。
4. Webhook 中能拿到用户 wa_id、业务号码 phone_number_id、消息内容、message_id。
5. WhatsApp 不提供 OAuth 授权回调页，所以不能写成传统 OAuth。
```

官方参考：

```text
Meta WhatsApp Cloud API Get Started
https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started

WhatsApp Webhooks Overview
https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview/

Messages Webhook Reference
https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages

WhatsApp Click to Chat
https://faq.whatsapp.com/5913398998672934
```

---

## 2. 当前源码基础与改造方向

### 2.1 必须复用的现有代码

当前项目已有以下基础能力：

```text
app/api/routes/webhooks.py
app/services/meta_account_registry.py
app/providers/messaging/whatsapp_provider.py
app/services/chat.py
app/services/runtime_state.py
app/api/routes/h5_member_whatsapp_binding.py
app/services/h5_member_whatsapp_binding_service.py
frontend/src/pages/MetaAccountsPage.tsx
```

改造原则：

```text
1. 不新建第二套 WhatsApp Provider。
2. 不新增第二套 Webhook。
3. 不绕开现有 MetaAccountRegistry。
4. 不复制 AI 聊天链路。
5. 在现有 Webhook 入站处理前加命令分发层。
```

### 2.2 当前要替换的旧逻辑

当前 `h5_member_whatsapp_binding_service.py` 的 `start_binding()` 仍是 placeholder：

```text
placeholder: awaiting_meta_configuration
```

本期要替换为：

```text
根据 H5 站点号码池选择 phone_number_id
生成 BIND token
生成 wa.me 链接
返回 H5 轮询 session
Webhook 收到 BIND 后完成真实绑定
```

### 2.3 当前站点号码字段现状

当前 `H5Site` 已经存在类似：

```text
default_waba_id
default_phone_number_id
default_ai_agent_id
default_ai_entry_link_id
```

这些字段可以保留兼容，但 V2 需要升级为：

```text
一个站点对应多个 WhatsApp 服务号码
而不是一个 default_phone_number_id
```

因此新增：

```text
SiteWhatsAppPhonePool
UserWhatsAppServiceAssignment
WhatsAppIdentity
WhatsAppAuthSession
WhatsAppAutoBindInvite
```

---

## 3. 总体架构

### 3.1 站点号码池共享服务号模式

```text
H5 Site
  ↓
SiteWhatsAppPhonePool：几十个 WABA / Phone Number
  ↓
PhoneSelectionService 按健康状态/权重/负载选号码
  ↓
生成 wa.me 链接
  ↓
用户发送 LOGIN / BIND / AUTO_BIND
  ↓
Webhook
  ↓
WhatsAppInboundCommandRouter
  ↓
Auth / Binding / AutoBind 或 AI Chat
```

### 3.2 号码用途

每个站点号码池里的号码统一作为：

```text
登录号
绑定号
AI客服号
人工客服号
```

不再默认区分：

```text
auth_phone_number_id
ai_phone_number_id
```

可以保留高级模式：

```text
split_auth_ai
```

但默认必须是：

```text
shared_site_pool
```

### 3.3 Webhook 入站优先级

```text
1. 验签
2. 去重
3. 解析 WABA / phone_number_id / wa_id / text / message_id
4. 确认 phone_number_id 是否属于某个站点号码池
5. 判断 LOGIN / BIND / AUTO_BIND / 自动绑定链接回执
6. 如果是认证/绑定命令：认证绑定服务处理并短路
7. 如果不是：
   - wa_id 已绑定：进入 AI / 人工会话
   - wa_id 未绑定：回复绑定引导，不进入正式 AI
```

### 3.4 关键约束

```text
一个 wa_id 全平台只能绑定一个 user_id。
一个 phone_number_id 同一时间只能属于一个 active site pool。
同一个用户绑定后优先使用原 assigned phone_number_id。
同站点池内其他号码收到该用户消息，也合并到同一个客户会话。
```

---

## 4. 数据模型设计

### 4.1 SiteWhatsAppPhonePool

表示某个 H5 站点有哪些可用 WhatsApp 服务号码。

```python
class SiteWhatsAppPhonePool(Base, TimestampMixin):
    __tablename__ = "site_whatsapp_phone_pools"

    id = mapped_column(String(36), primary_key=True, default=new_id)

    account_id = mapped_column(String(64), nullable=False, index=True)
    site_id = mapped_column(String(64), nullable=False, index=True)

    waba_id = mapped_column(String(128), nullable=False, index=True)
    phone_number_id = mapped_column(String(128), nullable=False, index=True)
    display_phone_number = mapped_column(String(64), nullable=False)

    status = mapped_column(String(32), nullable=False, default="active")
    # active / disabled / restricted / cooling_down / released / migrated

    purpose_mode = mapped_column(String(32), nullable=False, default="shared_auth_ai")
    # shared_auth_ai / ai_only / auth_only / disabled

    weight = mapped_column(Integer, nullable=False, default=100)
    priority = mapped_column(Integer, nullable=False, default=100)

    allow_new_users = mapped_column(Boolean, nullable=False, default=True)
    allow_existing_users = mapped_column(Boolean, nullable=False, default=True)
    only_existing_users = mapped_column(Boolean, nullable=False, default=False)

    max_new_bindings_per_day = mapped_column(Integer, nullable=True)
    max_auth_sessions_per_hour = mapped_column(Integer, nullable=True)
    max_active_conversations = mapped_column(Integer, nullable=True)

    today_new_binding_count = mapped_column(Integer, nullable=False, default=0)
    today_auth_session_count = mapped_column(Integer, nullable=False, default=0)
    active_conversation_count = mapped_column(Integer, nullable=False, default=0)

    ready_for_webhook_delivery = mapped_column(Boolean, nullable=False, default=False)
    ready_for_outbound_messages = mapped_column(Boolean, nullable=False, default=False)
    webhook_runtime_status = mapped_column(String(32), nullable=True)
    outbound_runtime_status = mapped_column(String(32), nullable=True)

    quality_rating_snapshot = mapped_column(String(32), nullable=True)
    # high / medium / low / unknown
    phone_number_status_snapshot = mapped_column(String(64), nullable=True)
    messaging_limit_tier_snapshot = mapped_column(String(64), nullable=True)

    low_quality_stop_new_users = mapped_column(Boolean, nullable=False, default=True)
    restricted_stop_allocation = mapped_column(Boolean, nullable=False, default=True)

    last_webhook_at = mapped_column(DateTime(timezone=False), nullable=True)
    last_outbound_at = mapped_column(DateTime(timezone=False), nullable=True)
    last_error_at = mapped_column(DateTime(timezone=False), nullable=True)
    last_error_message = mapped_column(Text, nullable=True)

    assigned_at = mapped_column(DateTime(timezone=False), nullable=True)
    released_at = mapped_column(DateTime(timezone=False), nullable=True)
    released_reason = mapped_column(Text, nullable=True)

    metadata_json = mapped_column(JSON)
```

#### 唯一约束

同一时间一个 `phone_number_id` 只能属于一个 active 站点池：

```text
unique(phone_number_id) where status in ('active','restricted','cooling_down')
```

如果数据库不支持 partial unique index，则业务层强制：

```text
新增/启用 pool item 前，查询该 phone_number_id 是否已被其他 active site 使用。
```

#### 迁移规则

如果站点关闭：

```text
1. site pool item status -> released
2. 不再接收新用户分配
3. 已绑定用户如果还关联该号码，需要迁移 assignment 或保留历史记录
4. 释放后的 phone_number_id 可以分配给其他站点
5. 迁移必须写审计
```

---

### 4.2 WhatsAppIdentity

表示 WhatsApp 用户身份，全平台唯一。

```python
class WhatsAppIdentity(Base, TimestampMixin):
    __tablename__ = "whatsapp_identities"

    id = mapped_column(String(36), primary_key=True, default=new_id)

    wa_id = mapped_column(String(128), nullable=False, unique=True, index=True)
    phone_number = mapped_column(String(64), nullable=True, index=True)
    display_name = mapped_column(String(128), nullable=True)

    account_id = mapped_column(String(64), nullable=False, index=True)
    site_id = mapped_column(String(64), nullable=False, index=True)

    user_id = mapped_column(String(64), nullable=False, unique=True, index=True)
    member_profile_id = mapped_column(String(64), nullable=True, index=True)

    binding_status = mapped_column(String(32), nullable=False, default="bound")
    # bound / locked / unbound_by_admin / migrated

    first_bound_phone_number_id = mapped_column(String(128), nullable=True, index=True)
    current_assigned_phone_number_id = mapped_column(String(128), nullable=True, index=True)

    bound_at = mapped_column(DateTime(timezone=False), nullable=True)
    locked_at = mapped_column(DateTime(timezone=False), nullable=True)
    unbound_at = mapped_column(DateTime(timezone=False), nullable=True)

    first_seen_at = mapped_column(DateTime(timezone=False), nullable=True)
    last_seen_at = mapped_column(DateTime(timezone=False), nullable=True)

    metadata_json = mapped_column(JSON)
```

#### 强制规则

```text
wa_id 全平台唯一。
user_id 只能有一个 active WhatsAppIdentity。
wa_id 已绑定其他站点用户时，任何其他站点登录/注册/绑定必须失败。
```

---

### 4.3 UserWhatsAppServiceAssignment

表示绑定用户当前分配到哪个服务号码。

```python
class UserWhatsAppServiceAssignment(Base, TimestampMixin):
    __tablename__ = "user_whatsapp_service_assignments"

    id = mapped_column(String(36), primary_key=True, default=new_id)

    account_id = mapped_column(String(64), nullable=False, index=True)
    site_id = mapped_column(String(64), nullable=False, index=True)
    user_id = mapped_column(String(64), nullable=False, index=True)
    wa_id = mapped_column(String(128), nullable=False, index=True)

    assigned_waba_id = mapped_column(String(128), nullable=False, index=True)
    assigned_phone_number_id = mapped_column(String(128), nullable=False, index=True)
    assigned_display_phone_number = mapped_column(String(64), nullable=False)

    status = mapped_column(String(32), nullable=False, default="active")
    # active / migrated / disabled

    assignment_source = mapped_column(String(32), nullable=False)
    # bind / login / auto_bind_invite / admin / migration

    assigned_at = mapped_column(DateTime(timezone=False), nullable=False)
    migrated_at = mapped_column(DateTime(timezone=False), nullable=True)
    migrated_from_phone_number_id = mapped_column(String(128), nullable=True)
    migration_reason = mapped_column(Text, nullable=True)

    last_inbound_at = mapped_column(DateTime(timezone=False), nullable=True)
    last_inbound_phone_number_id = mapped_column(String(128), nullable=True, index=True)
    last_outbound_at = mapped_column(DateTime(timezone=False), nullable=True)

    metadata_json = mapped_column(JSON)
```

唯一：

```text
unique(user_id) where status = 'active'
unique(wa_id) where status = 'active'
```

---

### 4.4 WhatsAppAuthSession

用于 H5 登录 / 绑定按钮主动发起的 session。

```python
class WhatsAppAuthSession(Base, TimestampMixin):
    __tablename__ = "whatsapp_auth_sessions"

    id = mapped_column(String(36), primary_key=True, default=new_id)

    account_id = mapped_column(String(64), nullable=False, index=True)
    site_id = mapped_column(String(64), nullable=False, index=True)
    user_id = mapped_column(String(64), nullable=True, index=True)

    session_type = mapped_column(String(32), nullable=False)
    # login / bind

    token_hash = mapped_column(String(128), nullable=False, unique=True, index=True)
    token_last4 = mapped_column(String(8), nullable=False)
    command_prefix = mapped_column(String(32), nullable=False)

    selected_waba_id = mapped_column(String(128), nullable=False, index=True)
    selected_phone_number_id = mapped_column(String(128), nullable=False, index=True)
    selected_display_phone_number = mapped_column(String(64), nullable=False)

    wa_link = mapped_column(String(1024), nullable=False)
    command_text = mapped_column(String(256), nullable=False)

    status = mapped_column(String(32), nullable=False, default="pending")
    # pending / confirmed / consumed / expired / failed / cancelled

    wa_id = mapped_column(String(128), nullable=True, index=True)
    inbound_message_id = mapped_column(String(128), nullable=True, index=True)
    identity_id = mapped_column(String(36), nullable=True, index=True)

    browser_session_id = mapped_column(String(128), nullable=True, index=True)
    client_nonce_hash = mapped_column(String(128), nullable=True)

    expires_at = mapped_column(DateTime(timezone=False), nullable=False)
    confirmed_at = mapped_column(DateTime(timezone=False), nullable=True)
    consumed_at = mapped_column(DateTime(timezone=False), nullable=True)

    failure_code = mapped_column(String(64), nullable=True)
    failure_reason = mapped_column(Text, nullable=True)

    metadata_json = mapped_column(JSON)
```

#### 必须校验

Webhook 收到 LOGIN/BIND 时：

```text
incoming phone_number_id == selected_phone_number_id
```

否则拒绝，防止用户把 token 发到错误号码。

---

### 4.5 WhatsAppAutoBindInvite

未绑定用户直接给服务号发普通消息时，系统创建自动绑定邀请链接。

```python
class WhatsAppAutoBindInvite(Base, TimestampMixin):
    __tablename__ = "whatsapp_auto_bind_invites"

    id = mapped_column(String(36), primary_key=True, default=new_id)

    account_id = mapped_column(String(64), nullable=False, index=True)
    site_id = mapped_column(String(64), nullable=False, index=True)

    wa_id = mapped_column(String(128), nullable=False, index=True)
    inbound_phone_number_id = mapped_column(String(128), nullable=False, index=True)
    inbound_waba_id = mapped_column(String(128), nullable=False, index=True)
    inbound_message_id = mapped_column(String(128), nullable=True, index=True)

    token_hash = mapped_column(String(128), nullable=False, unique=True, index=True)
    token_last4 = mapped_column(String(8), nullable=False)

    status = mapped_column(String(32), nullable=False, default="pending")
    # pending / consumed / expired / failed

    invite_link = mapped_column(String(1024), nullable=False)
    expires_at = mapped_column(DateTime(timezone=False), nullable=False)
    consumed_at = mapped_column(DateTime(timezone=False), nullable=True)

    user_id = mapped_column(String(64), nullable=True, index=True)
    failure_code = mapped_column(String(64), nullable=True)
    failure_reason = mapped_column(Text, nullable=True)

    metadata_json = mapped_column(JSON)
```

#### 使用方式

未绑定用户发普通消息：

```text
你好
```

系统回复：

```text
请点击以下链接完成 WhatsApp 绑定后继续咨询：
https://h5a.com/whatsapp/auto-bind?token=xxxx
```

用户点击后：

```text
如果没有登录账号：自动创建/登录一个 H5 用户并绑定该 wa_id。
如果当前 H5 已登录且站点匹配：绑定当前账号。
如果当前登录账号不匹配或 wa_id 已绑定其他站点：失败。
```

---

### 4.6 WhatsAppAuthAttemptLog

```python
class WhatsAppAuthAttemptLog(Base, TimestampMixin):
    __tablename__ = "whatsapp_auth_attempt_logs"

    id = mapped_column(String(36), primary_key=True, default=new_id)

    account_id = mapped_column(String(64), nullable=True, index=True)
    site_id = mapped_column(String(64), nullable=True, index=True)

    session_id = mapped_column(String(36), nullable=True, index=True)
    auto_bind_invite_id = mapped_column(String(36), nullable=True, index=True)

    wa_id = mapped_column(String(128), nullable=True, index=True)
    inbound_phone_number_id = mapped_column(String(128), nullable=True, index=True)
    inbound_message_id = mapped_column(String(128), nullable=True, index=True)

    command_prefix = mapped_column(String(32), nullable=True)
    token_last4 = mapped_column(String(8), nullable=True)

    outcome = mapped_column(String(32), nullable=False)
    # success / token_not_found / expired / already_consumed / identity_conflict /
    # wrong_phone_number / site_conflict / disabled / invalid_scope / rate_limited

    reason = mapped_column(Text, nullable=True)
    raw_text_snapshot = mapped_column(String(256), nullable=True)

    metadata_json = mapped_column(JSON)
```

---

## 5. 站点号码池后台配置

### 5.1 页面位置

保留独立配置页，但内容改为站点号码池：

```text
系统设置 > WhatsApp登录绑定
```

或站点详情内增加 Tab：

```text
站点管理 > 站点详情 > WhatsApp服务号码池
```

建议两处都能进入：

```text
系统设置页：全局管理所有站点号码池
站点详情页：只管理当前站点号码池
```

### 5.2 页面模块

#### 站点号码池

表格字段：

```text
站点
WABA
Phone Number ID
显示号码
状态
Webhook状态
Outbound状态
质量
今日新绑定
今日登录/绑定会话
当前活跃会话
权重
优先级
是否允许新用户
是否仅服务老用户
最近错误
操作
```

操作：

```text
添加号码
停用
释放
迁移给其他站点
暂停新用户分配
恢复新用户分配
只服务老客户
更新健康状态
测试Webhook
测试发送
```

### 5.3 添加号码规则

添加 `phone_number_id` 到站点号码池时必须校验：

```text
1. 该号码存在于 MetaAccountRegistry。
2. 该号码 webhook ready。
3. 该号码 outbound ready。
4. 该号码当前未属于其他 active site pool。
5. 如果属于 closed/released site，可以迁移。
```

### 5.4 释放和迁移规则

号码从站点 A 释放：

```text
1. status -> released
2. stop new allocation
3. existing assignment 保留历史
4. 如果仍有 active users，提示是否迁移到其他号码
5. 写审计
```

迁移到站点 B：

```text
1. 必须确认站点 A 已关闭或号码已 released。
2. 不允许 active 状态直接转移。
3. 迁移后该号码属于站点 B。
4. 原站点用户的绑定不失效，但后续 H5 链接应使用新号码分配策略。
```

### 5.5 分配策略配置

字段：

```text
selection_strategy = quality_first_weighted_least_load
default_session_ttl_seconds
bind_command_prefix
login_command_prefix
auto_bind_link_ttl_seconds
unbound_message_reply_interval_minutes
global_wa_id_unique = true
```

---

## 6. 号码选择算法

### 6.1 新增服务

```text
app/services/site_whatsapp_phone_pool_service.py
app/services/whatsapp_phone_selection_service.py
```

### 6.2 选择号码输入

```python
select_phone_for_session(
    account_id: str,
    site_id: str,
    user_id: str | None,
    wa_id: str | None,
    session_type: Literal["login", "bind", "auto_bind", "contact"],
)
```

### 6.3 选择优先级

#### 已绑定用户

```text
1. 查 UserWhatsAppServiceAssignment.active。
2. 如果 assigned_phone_number_id 仍属于该站点池，并允许 existing users：
   - 使用 assigned_phone_number_id。
3. 如果 assigned phone 不可用：
   - 选择新的健康号码。
   - 创建 migration assignment。
   - 绑定关系不失效。
```

#### 未绑定用户

```text
1. 只从该 site_id 的 active phone pool 中选择。
2. 过滤 allow_new_users=false。
3. 过滤 only_existing_users=true。
4. 过滤 webhook/outbound 不可用。
5. 过滤 restricted / cooling_down。
6. 低质量号码如果 low_quality_stop_new_users=true，则过滤。
7. 过滤超过 max_new_bindings_per_day 的号码。
8. 按 priority、quality、weight、active_conversation_count、today_new_binding_count 排序。
```

### 6.4 推荐评分公式

```text
score =
  quality_score * 1000
  + priority_score * 100
  + weight_score
  - active_conversation_count * 5
  - today_new_binding_count * 3
  - today_auth_session_count
```

质量分：

```text
high = 3
medium = 2
unknown = 1
low = 0
restricted = 不可选
```

### 6.5 不可用处理

如果没有可用号码：

```text
返回 PHONE_POOL_UNAVAILABLE
H5 显示：当前 WhatsApp 服务繁忙，请稍后再试
后台告警：站点号码池无可用号码
```

不要 fallback 到其他站点号码池。

---

## 7. H5 登录/绑定流程

### 7.1 WhatsApp 登录 / 注册

接口：

```text
POST /api/h5/auth/whatsapp/start
```

流程：

```text
1. 根据 Host/site_key 解析 site_id。
2. 如果浏览器已有未过期 pending login session，直接返回原 session，不重新分配号码。
3. 调用 PhoneSelectionService 选择号码。
4. 生成 LOGIN token。
5. 创建 WhatsAppAuthSession，写 selected_phone_number_id。
6. 返回 wa.me 链接。
```

返回：

```json
{
  "session_id": "waas_123",
  "wa_link": "https://wa.me/821012345678?text=LOGIN%20ABCD1234EFGH",
  "command_text": "LOGIN ABCD1234EFGH",
  "display_phone_number": "821012345678",
  "expires_at": "2026-06-25T12:00:00Z",
  "instructions": "请点击按钮打开 WhatsApp，并发送预填登录消息。"
}
```

Webhook 收到 LOGIN：

```text
1. token_hash 查询 session。
2. 校验 incoming phone_number_id == selected_phone_number_id。
3. 检查 wa_id 是否全平台已绑定。
4. 如果已绑定且 site_id 相同：登录成功。
5. 如果已绑定但 site_id 不同：失败，禁止登录/注册。
6. 如果未绑定：按 auto_register 策略创建账号并绑定。
```

### 7.2 已登录账号绑定 WhatsApp

接口：

```text
POST /api/h5/whatsapp-binding/start
```

流程：

```text
1. 用户必须已登录。
2. 如果 user 已绑定 WhatsApp，返回 bound。
3. 如果已有未过期 pending bind session，返回原 session。
4. 按 site phone pool 选择号码。
5. 创建 BIND token session。
6. 返回 wa.me 链接。
```

Webhook 收到 BIND：

```text
1. token_hash 查询 session。
2. 校验 phone_number_id。
3. 检查 wa_id 全平台唯一。
4. 如果 wa_id 已绑定其他 user/site：失败。
5. 如果 wa_id 未绑定：绑定当前 user。
6. 创建 WhatsAppIdentity。
7. 创建 UserWhatsAppServiceAssignment。
8. 更新 user.has_whatsapp=true。
9. 发绑定奖励。
10. 激活新手任务入口。
```

---

## 8. 未绑定用户普通消息自动绑定链接

### 8.1 触发场景

用户直接给站点号码池中的号码发普通消息：

```text
你好
```

但该 `wa_id` 未绑定任何用户。

### 8.2 系统处理

```text
1. 根据 incoming phone_number_id 找 SiteWhatsAppPhonePool。
2. 如果该 phone_number_id 不属于任何 active site pool：
   - 不进入 AI。
   - 可回复通用错误或忽略。
3. 如果属于某个 site：
   - 创建 WhatsAppAutoBindInvite。
   - 生成 H5 auto-bind 链接。
   - 回复用户绑定引导。
```

### 8.3 绑定引导回复

示例：

```text
您好，请点击以下链接完成 WhatsApp 绑定后继续咨询：
https://h5a.com/whatsapp/auto-bind?token=xxxx
```

### 8.4 点击链接后行为

H5 路由：

```text
/whatsapp/auto-bind?token=xxxx
```

前端调用：

```text
POST /api/h5/auth/whatsapp/auto-bind/consume
```

规则：

```text
1. token 未过期。
2. wa_id 未全平台绑定。
3. token 对应 phone_number_id 仍属于该 site。
4. 如果当前 H5 未登录：
   - 自动创建/登录一个新 H5 用户。
   - 绑定 wa_id。
5. 如果当前 H5 已登录且未绑定：
   - 绑定当前用户。
6. 如果当前 H5 已登录但用户/站点不匹配：
   - 失败。
7. 如果 wa_id 已绑定其他站点：
   - 失败，禁止注册/登录。
```

### 8.5 限频

未绑定普通消息引导必须限频：

```text
同 wa_id + phone_number_id 10分钟最多回复一次。
同 phone_number_id 每分钟最多自动回复 N 次。
```

防止被刷导致号码质量下降。

---

## 9. 普通消息进入 AI / 人工会话

### 9.1 已绑定用户正常消息

Webhook 收到普通消息：

```text
wa_id 已绑定
phone_number_id 属于该用户 site 的号码池
```

处理：

```text
1. 查 WhatsAppIdentity。
2. 查 UserWhatsAppServiceAssignment。
3. 找到 user_id/site_id。
4. 合并到同一个客户会话。
5. 保存 inbound_phone_number_id 快照。
6. 进入 AI Chat。
```

### 9.2 发到同站点池其他号码

如果：

```text
wa_id 已绑定 h5a
incoming phone_number_id 属于 h5a 的 pool
incoming phone_number_id != assigned_phone_number_id
```

处理：

```text
允许接收。
合并同一个客户会话。
Message 保存 inbound_phone_number_id。
回复时使用 incoming phone_number_id。
更新 assignment.last_inbound_phone_number_id。
```

### 9.3 发到其他站点号码

如果：

```text
wa_id 已绑定 h5a
incoming phone_number_id 属于 h5b 的 pool
```

处理：

```text
不进入 h5b AI。
回复：该 WhatsApp 已绑定其他站点账号，请联系客服。
记录 attempt log。
```

### 9.4 发到未知号码

如果 phone_number_id 不在任何 active site pool：

```text
不进入正式 AI。
记录 unknown_phone_number inbound。
可按配置忽略或回复通用提示。
```

---

## 10. 号码限制、低质量与迁移

### 10.1 低质量号码

当号码质量变低：

```text
status 可保持 active
allow_new_users=false
only_existing_users=true
停止新绑定、新登录、新自动注册
继续服务老用户主动消息
停止主动营销/外呼
```

### 10.2 号码受限

当号码 restricted：

```text
status=restricted
allow_new_users=false
allow_existing_users=true 或 false 视限制类型
```

如果仍可 webhook：

```text
老用户主动消息继续服务。
```

如果 outbound 不可用：

```text
不能主动回复，标记会话异常，H5 后续链接迁移到新号码。
```

### 10.3 号码失效

当 webhook 不可用或 phone_number_id disabled：

```text
status=disabled
allow_new_users=false
allow_existing_users=false
```

处理：

```text
1. 绑定关系不失效。
2. 用户未来 H5 拉起链接重新分配新号码。
3. 创建 UserWhatsAppServiceAssignment migration。
4. 如果旧号码还收到消息，提示重新从 H5 打开新服务窗口。
```

### 10.4 强制迁移用户

后台可以选择：

```text
按号码迁移所有用户
按站点迁移
按单个用户迁移
```

迁移必须：

```text
1. 选择目标健康号码。
2. 不改变 wa_id -> user_id 绑定。
3. 只改变 assigned_phone_number_id。
4. 写审计。
5. 后续 H5 链接使用新号码。
```

---

## 11. 会话合并规则

### 11.1 Conversation Key

建议会话唯一键：

```text
account_id + user_id + channel = whatsapp
```

不要用：

```text
phone_number_id + wa_id
```

否则用户发到同站点其他号码会生成多个会话。

### 11.2 Message 快照字段

Message 需要保存：

```text
wa_id
inbound_waba_id
inbound_phone_number_id
outbound_waba_id
outbound_phone_number_id
site_id
user_id
conversation_id
```

### 11.3 回复号码选择

回复时：

```text
1. 如果当前消息来自某个有效 inbound_phone_number_id：
   - 使用这个 phone_number_id 回复。
2. 如果是系统主动从 H5 发起：
   - 使用 assignment.assigned_phone_number_id。
3. 如果 assigned 不可用：
   - 重新分配健康号码。
```

### 11.4 AI上下文

AI 不应看到：

```text
LOGIN token
BIND token
AUTO_BIND token
```

AI 可以看到系统事件摘要：

```text
用户已完成 WhatsApp 绑定。
用户来自 H5A。
用户当前服务号码为 xxxx。
```

---

## 12. 后台配置页面 V2

### 12.1 页面位置

```text
系统设置 > WhatsApp登录绑定
```

同时在：

```text
站点管理 > 站点详情 > WhatsApp服务号码池
```

### 12.2 主要 Tab

```text
1. 站点号码池
2. 号码健康
3. 登录/绑定配置
4. 自动绑定引导
5. 身份绑定记录
6. 会话路由
7. 迁移记录
8. 审计日志
```

### 12.3 站点号码池 Tab

功能：

```text
添加 WABA/Phone
移除/释放号码
暂停新用户分配
仅服务老用户
调整权重
调整每日上限
设置优先级
查看状态
同步 Meta 状态
测试 webhook
测试发送
```

### 12.4 自动绑定引导配置

字段：

```text
enable_auto_bind_invite
auto_bind_invite_ttl_seconds
auto_bind_reply_interval_minutes
auto_bind_reply_text
auto_bind_after_click_policy
```

`auto_bind_after_click_policy`：

```text
auto_create_user_and_bind
bind_current_logged_in_user
reject_if_logged_in_other_user
```

默认：

```text
auto_create_user_and_bind if no current user
bind_current_logged_in_user if current user matches site and unbound
reject if mismatch
```

### 12.5 号码迁移页面

功能：

```text
查看某号码绑定用户数
查看活跃会话数
选择目标号码
迁移所有用户
迁移部分用户
迁移后停止旧号码新分配
```

---

## 13. API 设计

### 13.1 H5 登录 / 绑定

```text
POST /api/h5/auth/whatsapp/start
GET  /api/h5/auth/whatsapp/sessions/{session_id}
POST /api/h5/auth/whatsapp/sessions/{session_id}/consume

GET  /api/h5/whatsapp-binding
POST /api/h5/whatsapp-binding/start
GET  /api/h5/whatsapp-binding/sessions/{session_id}

POST /api/h5/auth/whatsapp/auto-bind/consume
```

### 13.2 后台号码池

```text
GET    /api/admin/whatsapp-auth/sites/{site_id}/phone-pool
POST   /api/admin/whatsapp-auth/sites/{site_id}/phone-pool
PATCH  /api/admin/whatsapp-auth/phone-pool/{pool_id}
POST   /api/admin/whatsapp-auth/phone-pool/{pool_id}/pause-new-users
POST   /api/admin/whatsapp-auth/phone-pool/{pool_id}/resume-new-users
POST   /api/admin/whatsapp-auth/phone-pool/{pool_id}/only-existing-users
POST   /api/admin/whatsapp-auth/phone-pool/{pool_id}/release
POST   /api/admin/whatsapp-auth/phone-pool/{pool_id}/sync-health
POST   /api/admin/whatsapp-auth/phone-pool/{pool_id}/test
```

### 13.3 后台身份和迁移

```text
GET  /api/admin/whatsapp-auth/identities
GET  /api/admin/whatsapp-auth/assignments
POST /api/admin/whatsapp-auth/assignments/{assignment_id}/migrate
POST /api/admin/whatsapp-auth/phone-pool/{pool_id}/migrate-users

GET  /api/admin/whatsapp-auth/sessions
GET  /api/admin/whatsapp-auth/auto-bind-invites
GET  /api/admin/whatsapp-auth/attempt-logs
```

### 13.4 Webhook

继续使用当前统一入口：

```text
POST /webhooks/whatsapp
```

不要新增单独 auth webhook。

---

## 14. 后端服务文件

### 14.1 新增服务

```text
app/services/site_whatsapp_phone_pool_service.py
app/services/whatsapp_phone_selection_service.py
app/services/whatsapp_identity_service.py
app/services/whatsapp_auth_session_service.py
app/services/whatsapp_auto_bind_invite_service.py
app/services/whatsapp_inbound_command_router.py
app/services/whatsapp_binding_service.py
app/services/whatsapp_assignment_migration_service.py
app/services/whatsapp_message_routing_service.py
```

### 14.2 修改服务

```text
app/services/h5_member_whatsapp_binding_service.py
app/services/meta_account_registry.py
app/services/chat.py
app/services/runtime_state.py
app/services/ai_queue_processor.py
```

### 14.3 新增路由

```text
app/api/routes/whatsapp_auth_h5.py
app/api/routes/whatsapp_auth_admin.py
```

### 14.4 修改路由

```text
app/api/routes/webhooks.py
app/api/routes/h5_member_whatsapp_binding.py
```

### 14.5 新增 schema

```text
app/schemas/whatsapp_auth.py
app/schemas/whatsapp_phone_pool.py
app/schemas/whatsapp_identity.py
app/schemas/whatsapp_auto_bind.py
```

---

## 15. Webhook 分发详细逻辑

### 15.1 try_handle_inbound

```python
class WhatsAppInboundCommandRouter:
    async def route_inbound_text(
        self,
        *,
        account_id: str,
        waba_id: str,
        phone_number_id: str,
        display_phone_number: str,
        wa_id: str,
        message_id: str,
        text: str,
        signature_verified: bool,
        raw_payload: dict,
    ) -> InboundRouteResult:
        ...
```

### 15.2 逻辑

```text
1. 根据 phone_number_id 查询 SiteWhatsAppPhonePool。
2. 如果找不到 active pool：
   - 如果是 LOGIN/BIND：记录 invalid_scope。
   - 普通消息按 unknown_phone 策略处理。
3. 判断 text 是否匹配 LOGIN/BIND。
4. LOGIN/BIND：
   - token_hash 查询 session。
   - 校验 selected_phone_number_id。
   - 校验全平台 wa_id 唯一。
   - 处理 auth/bind。
   - return handled=True。
5. 非 LOGIN/BIND：
   - 查询 WhatsAppIdentity by wa_id。
   - 如果已绑定：
      a. 如果 incoming phone 属于该 user.site 的 pool：进入 AI。
      b. 如果属于其他 site：拒绝并提示已绑定其他站点。
   - 如果未绑定：
      创建/复用 AutoBindInvite。
      回复绑定引导。
      return handled=True。
```

### 15.3 普通消息进入 AI

传给 AI 时要携带：

```text
user_id
site_id
wa_id
inbound_phone_number_id
inbound_waba_id
reply_phone_number_id
```

---

## 16. 安全与限流

### 16.1 wa_id 全平台唯一

数据库层：

```text
whatsapp_identities.wa_id unique
```

业务层：

```text
任何 bind / login / auto-bind 前先查 wa_id。
```

### 16.2 Token 安全

```text
token 只显示一次
数据库只存 token_hash
token 单次使用
token 10-30分钟过期
token 必须绑定 site_id 和 selected_phone_number_id
```

### 16.3 自动绑定链接安全

```text
auto_bind token 绑定 wa_id + phone_number_id + site_id
点击链接时不能替换 wa_id
链接单次使用
链接短期过期
```

### 16.4 未绑定引导限频

```text
same wa_id + phone_number_id 10分钟最多一次
same phone_number_id 每分钟最多 N 次
same IP 每分钟最多 N 次
```

### 16.5 LOGIN/BIND 限频

```text
同 wa_id 错误 token 10分钟最多 5 次
同 phone_number_id 错误 token 10分钟最多 100 次
同 user 每小时最多 start bind N 次
同浏览器 session 未过期时返回原 session
```

---

## 17. H5 前端实现

### 17.1 登录页

按钮：

```text
WhatsApp 登录 / 注册
```

点击：

```text
POST /api/h5/auth/whatsapp/start
```

返回：

```text
wa_link
command_text
display_phone_number
session_id
```

前端显示：

```text
即将打开 WhatsApp 服务窗口
请直接点击发送预填消息
发送后返回本页面
```

### 17.2 绑定页

按钮：

```text
绑定 WhatsApp 领取奖励
```

点击：

```text
POST /api/h5/whatsapp-binding/start
```

前端不要自行改 bound 状态，必须轮询后端。

### 17.3 自动绑定链接页

新增路由：

```text
/whatsapp/auto-bind?token=xxx
```

页面逻辑：

```text
1. 调用 POST /api/h5/auth/whatsapp/auto-bind/consume。
2. 成功：显示绑定成功，进入首页或新手任务。
3. 失败：
   - token expired
   - wa_id already bound other site
   - site mismatch
   - phone pool disabled
```

---

## 18. 后台前端实现

### 18.1 页面

```text
frontend/src/pages/WhatsAppAuthConfigPage.tsx
```

重命名显示：

```text
WhatsApp登录绑定与服务号码池
```

### 18.2 新增组件

```text
frontend/src/components/whatsapp/SitePhonePoolTable.tsx
frontend/src/components/whatsapp/SitePhonePoolEditor.tsx
frontend/src/components/whatsapp/PhoneHealthBadge.tsx
frontend/src/components/whatsapp/WhatsAppAssignmentTable.tsx
frontend/src/components/whatsapp/WhatsAppAutoBindInviteTable.tsx
frontend/src/components/whatsapp/PhoneMigrationDrawer.tsx
```

### 18.3 站点页集成

`SitesPage.tsx` 站点详情增加：

```text
WhatsApp服务号码池
```

可快速：

```text
添加号码
暂停新用户
查看绑定用户
迁移号码
```

---

## 19. 与任务 V3 集成

绑定成功后：

```text
1. user.has_whatsapp = true
2. 发放 WhatsApp 绑定奖励
3. 激活新手任务
4. H5 entry-state 返回 newbie_task_available
```

必须幂等：

```text
whatsapp_binding_reward:{user_id}
```

如果用户通过 auto-bind invite 自动创建并绑定：

```text
同样触发绑定奖励和新手任务。
```

---

## 20. 与会话/AI归属集成

### 20.1 绑定后归属

绑定成功时：

```text
根据 site 默认规则分配：
current_ai_agent_id
current_owner_staff_id
current_supervisor_id
current_team_id
```

如果站点已有入口链接/AI归属规则，优先复用现有归属逻辑。

### 20.2 AI转人工

普通消息进入 AI 后，AI 异常转人工仍走现有会话归属和转接规则：

```text
当前客户归属客服
主管团队队列
代理商默认队列
waiting_human
```

---

## 21. Meta / WABA 健康同步

### 21.1 需要同步的数据

从现有 MetaAccountRegistry 或 Meta provider 同步：

```text
waba_id
phone_number_id
display_phone_number
webhook verification status
webhook subscription status
ready_for_webhook_delivery
ready_for_outbound_messages
phone_number_quality_rating
phone_number_status
messaging_limit_tier
```

### 21.2 同步频率

```text
手动同步
每小时自动同步
Webhook状态事件触发同步
```

### 21.3 低质量处理

如果 quality low：

```text
allow_new_users=false
only_existing_users=true
```

如果 restricted/disabled：

```text
status=restricted/disabled
停止新分配
必要时迁移 assigned users
```

---

## 22. 测试要求

### 22.1 号码池测试

```text
test_phone_number_can_belong_to_only_one_active_site_pool
test_released_phone_number_can_be_assigned_to_another_site
test_low_quality_phone_stops_new_user_allocation
test_existing_user_still_gets_low_quality_assigned_phone
test_restricted_phone_not_selected_for_new_session
test_health_weighted_selection_prefers_healthy_low_load_phone
```

### 22.2 登录绑定测试

```text
test_start_bind_selects_site_pool_phone_and_returns_wa_link
test_existing_pending_bind_session_returns_same_phone
test_bind_webhook_rejects_wrong_phone_number
test_bind_webhook_rejects_wa_id_bound_to_other_site
test_bind_success_creates_identity_and_assignment
test_global_wa_id_unique_blocks_h5b_login
```

### 22.3 未绑定普通消息测试

```text
test_unbound_normal_message_does_not_enter_ai
test_unbound_normal_message_creates_auto_bind_invite
test_auto_bind_link_creates_user_and_binds_wa_id
test_auto_bind_link_rejects_if_wa_id_bound_other_site
test_auto_bind_invite_rate_limited
```

### 22.4 会话合并测试

```text
test_bound_user_message_to_assigned_phone_enters_same_conversation
test_bound_user_message_to_other_phone_in_same_site_pool_merges_conversation
test_message_saves_inbound_phone_number_id_snapshot
test_reply_uses_current_inbound_phone_number
test_bound_user_message_to_other_site_pool_rejected
```

### 22.5 AI分流测试

```text
test_login_command_processed_before_ai
test_bind_command_processed_before_ai
test_auth_commands_not_saved_as_normal_messages
test_normal_bound_message_enters_ai
test_normal_unbound_message_binding_prompt_not_ai
```

### 22.6 迁移测试

```text
test_disabled_assigned_phone_does_not_unbind_user
test_future_wa_link_uses_new_phone_after_migration
test_old_phone_if_still_receives_message_replies_reopen_h5_instruction
```

---

## 23. 部署验收清单

### 23.1 Meta账号

```text
多个 WABA 已接入
多个 phone_number_id 已同步
Webhook 已验证
messages 字段已订阅
App Secret 签名开启
phone_number_id 能在 webhook payload 中正确解析
```

### 23.2 后台

```text
站点可配置几十个 WhatsApp 服务号码
号码池能显示健康状态
号码能暂停新用户
号码能只服务老用户
号码能迁移
wa_id 全平台唯一生效
```

### 23.3 H5

```text
点击 WhatsApp 登录/绑定会打开指定服务号
WhatsApp 输入框自动填入 LOGIN/BIND 内容
用户只需发送
H5 能轮询绑定/登录状态
auto-bind 链接能自动绑定
```

### 23.4 Webhook

```text
LOGIN/BIND 不进入 AI
未绑定普通消息不进入 AI
已绑定普通消息进入 AI
同站点其他号码消息合并会话
其他站点号码消息拒绝
```

---

## 24. 禁止事项

1. 禁止为绑定单独固定一个全平台专用号。
2. 禁止一个 `phone_number_id` 同时属于多个 active 站点。
3. 禁止一个 `wa_id` 绑定多个用户。
4. 禁止 H5B 自动接收已绑定 H5A 的 wa_id。
5. 禁止未绑定普通消息进入正式 AI。
6. 禁止 LOGIN/BIND 写入普通聊天记录。
7. 禁止 token 明文长期存储。
8. 禁止用户刷新绑定页导致重新分配不同号码。
9. 禁止低质量号码继续分配新用户。
10. 禁止号码失效时删除用户绑定。
11. 禁止同站点其他号码消息新建重复客户。
12. 禁止绕过 MetaAccountRegistry 直接硬编码号码。
13. 禁止前端 mock 绑定成功。
14. 禁止绑定奖励重复发放。

---

## 25. Definition of Done

完成必须同时满足：

1. 每个 H5 站点可以配置多个 WABA / Phone Number。
2. 一个 phone_number_id 同一时间只能属于一个 active 站点号码池。
3. 站点关闭后号码可以释放并迁移给其他站点。
4. H5 登录/绑定链接按站点号码池选择号码。
5. wa.me 链接能拉起指定服务号，并自动预填 LOGIN/BIND 内容。
6. 用户只需发送预填内容即可触发 Webhook。
7. 已绑定用户再次登录/联系优先使用 assigned phone。
8. wa_id 全平台唯一绑定。
9. H5A 绑定后，H5B 使用同 wa_id 登录/注册/绑定全部失败。
10. 未绑定普通消息只回复绑定引导，不进入 AI。
11. 未绑定绑定引导链接点击后可自动绑定该 wa_id。
12. 低质量号码停止新用户分配，但继续服务老客户主动咨询。
13. 号码失效不解除绑定，后续 H5 链接迁移到其他健康号码。
14. 已绑定用户发到同站点号码池其他号码，合并为同一客户会话。
15. 消息保存 inbound_phone_number_id 快照。
16. 回复优先使用本次 inbound phone_number_id。
17. LOGIN/BIND/AUTO_BIND 不进入 AI prompt。
18. 绑定成功触发绑定奖励和新手任务。
19. 后台可查看号码池、身份绑定、自动绑定邀请、迁移记录。
20. 所有关键操作有测试和审计。

---

## 26. 文件级开发清单

### 26.1 后端新增

```text
app/services/site_whatsapp_phone_pool_service.py
app/services/whatsapp_phone_selection_service.py
app/services/whatsapp_identity_service.py
app/services/whatsapp_auth_session_service.py
app/services/whatsapp_auto_bind_invite_service.py
app/services/whatsapp_inbound_command_router.py
app/services/whatsapp_binding_service.py
app/services/whatsapp_assignment_migration_service.py
app/services/whatsapp_message_routing_service.py

app/api/routes/whatsapp_auth_h5.py
app/api/routes/whatsapp_auth_admin.py

app/schemas/whatsapp_auth.py
app/schemas/whatsapp_phone_pool.py
app/schemas/whatsapp_identity.py
app/schemas/whatsapp_auto_bind.py
```

### 26.2 后端修改

```text
app/db/models.py
app/main.py
app/api/routes/webhooks.py
app/api/routes/h5_member_whatsapp_binding.py
app/services/h5_member_whatsapp_binding_service.py
app/services/meta_account_registry.py
app/services/chat.py
app/services/runtime_state.py
app/services/ai_queue_processor.py
app/core/permission_defs.py
```

### 26.3 前端新增

```text
frontend/src/pages/WhatsAppAuthConfigPage.tsx
frontend/src/components/whatsapp/SitePhonePoolTable.tsx
frontend/src/components/whatsapp/SitePhonePoolEditor.tsx
frontend/src/components/whatsapp/PhoneHealthBadge.tsx
frontend/src/components/whatsapp/WhatsAppAssignmentTable.tsx
frontend/src/components/whatsapp/WhatsAppAutoBindInviteTable.tsx
frontend/src/components/whatsapp/PhoneMigrationDrawer.tsx
frontend/src/services/whatsappAuthAdminApi.ts
frontend/src/types/whatsappAuth.ts
```

### 26.4 前端修改

```text
frontend/src/pages/h5-member/LoginPage.tsx
frontend/src/pages/h5-member/HomePage.tsx
frontend/src/pages/SitesPage.tsx
frontend/src/services/h5Member.ts
frontend/src/routes/consoleRoutes.ts
```

### 26.5 Migration

新增：

```text
alembic/versions/<timestamp>_whatsapp_site_phone_pool_shared_auth_ai.py
```

---

## 27. 与 V1 的差异摘要

V1 默认：

```text
登录绑定号和 AI聊天号可以分开配置。
```

V2 默认：

```text
按站点配置 WhatsApp 服务号码池。
号码池中的号码同时负责登录、绑定、AI、人工客服。
```

V1 主要配置：

```text
auth_waba_id
auth_phone_number_id
ai_waba_id
ai_phone_number_id
```

V2 主要配置：

```text
site_id
phone pool
selection strategy
global wa_id uniqueness
auto-bind invite
health-aware allocation
```

V1 处理未绑定普通消息：

```text
按 auth phone 策略回复或忽略。
```

V2：

```text
未绑定普通消息生成自动绑定链接。
用户点击链接后自动绑定该 wa_id。
```

V1 账号分离：

```text
适合高安全或专用 auth 号码模式。
```

V2 共享服务窗口：

```text
适合当前多 WABA、多号码、未验证号码分流业务。
```
