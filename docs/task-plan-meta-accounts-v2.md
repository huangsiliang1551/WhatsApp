# Meta 账户管理页面 V2 开发计划

> 一次性完整交付。覆盖：表单简化、自动发现、错误处理、详情面板、列表行、页面布局、备注字段、大规模账号。

---

## 一、手动添加表单简化

### 1.1 字段精简

| # | 字段 | 之前 | 之后 | 来源 |
|---|------|:--:|:--:|------|
| 1 | 账户 ID | ✏️ 手动填 | 🎲 自动生成 `acc-{8位uuid}` | 后端 |
| 2 | 显示名称 | ✏️ | ✏️ | 自定义 |
| 3 | WABA ID | ✏️ | ✏️ | Meta 后台 |
| 4 | Access Token | ✏️ | ✏️ | Meta 后台 |
| 5 | Verify Token | ✏️ | ❌ 删 | → 全局 Webhook 配置 |
| 6 | App Secret | ✏️ | ❌ 删 | → 全局 Webhook 配置 |
| 7 | Business Portfolio ID | ✏️ | 🔍 自动发现 | Meta API |
| 8 | 号码列表 | ✏️ 逐条填 | 🔍 自动发现 | Meta API |
| 9 | Token 来源 | ✏️ 选择 | ✏️ 选择 | 不变 |
| 10 | 备注 | 无 | ✏️ 新增 | 填所属FB账号 |

**最终表单只需填 4 个字段**：显示名称、WABA ID、Access Token、备注。

### 1.2 自动发现按钮

填完 WABA ID + Access Token 后，点击「从 Meta 加载」：

```
┌─────────────────────────────────────────┐
│  从 Meta 加载结果                        │
│                                         │
│  ┌─ WABA 基本信息 ────────────────────┐ │
│  │  ✅ 名称          My Business       │ │
│  │  ✅ Portfolio ID  111222333         │ │
│  │  ✅ 时区           Asia/Shanghai     │ │
│  └────────────────────────────────────┘ │
│  ┌─ App 关联 ─────────────────────────┐ │
│  │  ✅ App ID       987654321         │ │
│  └────────────────────────────────────┘ │
│  ┌─ 号码列表 (3个) ───────────────────┐ │
│  │  ✅ +8613800138001  GREEN  已注册   │ │
│  │  ⚠️ +8613800138002  RED    未注册   │ │
│  └────────────────────────────────────┘ │
│                                         │
│  [ 确认无误，保存 ]                       │
└─────────────────────────────────────────┘
```

**内部调用**：`GET /{waba_id}` + `GET /{waba_id}/phone_numbers` + `GET /{waba_id}/subscribed_apps`


## 二、后端 API

### 2.1 新增端点：`POST /api/meta/accounts/discover`

**Request:**
```json
{ "waba_id": "123456789012345", "access_token": "EAAxxxxx..." }
```

**Response (成功):**
```json
{
  "ok": true,
  "fields": {
    "waba_name":      { "status": "ok", "value": "My Business" },
    "business_portfolio_id": { "status": "ok", "value": "111222333" },
    "app_id":         { "status": "ok", "value": "987654321" },
    "phone_numbers":  { "status": "ok", "value": [
      { "phone_number_id": "99887", "display_phone_number": "+8613800138001",
        "verified_name": "主客服号", "quality_rating": "GREEN", "is_registered": true }
    ]}
  },
  "errors": [],
  "warnings": []
}
```

**字段级 status:**
| status | 含义 | 前端 |
|--------|------|------|
| `ok` | 获取成功 | 绿色 ✅ |
| `partial` | 部分成功 | 黄色 ⚠️ + 警告 |
| `not_found` | 不存在 | 灰色 — |
| `error` | 失败 | 红色 ❌ + 错误码+消息 |
| `skipped` | 跳过 | 不展示 |

### 2.2 错误码映射

```python
META_ERROR_MAP = {
    190: "Access Token 无效或已过期，请重新生成",
    200: "权限不足，需 whatsapp_business_management 权限",
    100: "参数错误，请检查 WABA ID 格式",
    80007: "速率限制，请稍后重试",
    4: "请求过于频繁",
    10: "API 暂时不可用",
}
```

### 2.3 修改 ManifestAccountRequest

```python
class ManualMetaAccountRequest(BaseModel):
    account_id: str | None = None          # 可选，留空自动生成
    display_name: str
    meta_business_portfolio_id: str        # 可从发现结果预填
    waba_id: str
    access_token: str
    token_source: Literal["system_user", "user_access_token"] = "system_user"
    notes: str | None = None               # 新增：备注
    phone_numbers: list[MetaPhoneNumber] = []
    # ❌ 删除: verify_token, app_secret
```

### 2.4 全局 Webhook 配置新增 App Secret

```python
# settings.py
meta_global_webhook_callback_url: str
meta_global_webhook_verify_token: str
meta_global_webhook_app_secret: str       # 新增

# GlobalWebhookConfigResponse
{ "callback_url": "...", "verify_token": "...", "app_secret": "..." }

# GlobalWebhookConfigUpdateRequest
{ "callback_url": "...", "verify_token": "...", "app_secret": "..." }
```

新建账户时自动从全局配置读取 verify_token/app_secret，允许多账号共享。


## 三、账号行（列表）设计

### 3.1 5 列布局

```
┌──┬────────────────────────────────┬──────┬──────────┬────────┐
│🟢│ 主客服账户         手动·已启用  │ 2/3  │ ● 正常   │ 2小时前 │
│  │ waba:123456789012             │      │          │        │
└──┴────────────────────────────────┴──────┴──────────┴────────┘
```

| # | 列 | 宽度 | 内容 |
|---|-------|:--:|------|
| 1 | 综合状态灯 | 40px | 单色圆点，综合 account_active + waba_active + has_token + wh_healthy |
| 2 | 账户信息 | flex | 第一行：名称 + 接入方式标签 + 启停标签 + 备注(如有)；第二行：WABA ID 小字 |
| 3 | 号码 | 60px | `2/3` 绿色=全注册，黄色=部分，灰色=全未注册 |
| 4 | Webhook | 90px | 圆点+状态标签；异常时显示原因（如"签名失败3"） |
| 5 | 最后活动 | 80px | 相对时间（2小时前/3天前），空显示"—" |

**悬浮操作**：检测 / 订阅 / 编辑（hover 时出现，不占列宽）

### 3.2 综合状态灯规则

| 灯 | 条件 |
|:--:|------|
| 🟢 | account_active && waba_active && has_token && wh_healthy |
| 🟡 | active 但 token 缺失 / wh 异常 / 号码全未注册 |
| 🔴 | 已禁用 / wh 失败 / blocking_reasons 非空 |
| ⚪ | has_token=false（未对接） |


## 四、详情面板

### 4.1 卡片式分层（从上到下 = 关注度从高到低）

```
┌──380px───────────────────────────────────────┐
│ 🟢 主客服账户        [编辑] [检测] [🔗测试] [删除] │ ← 头部
│ 手动接入 · System User · 备注: fb-zhangsan     │
├──────────────────────────────────────────────┤
│ 账户启停 [🔘]   WABA启停 [🔘]   同步号码 [📥]    │ ← 快速操作条
├──────────────────────────────────────────────┤
│ 🟢 连接状态 — 链路畅通                          │ ← 连接状态
│ DB ✅ Token ✅ 号码 2/3 出站 ✅  WH 🟡 验证中   │
├──────────────────────────────────────────────┤
│ 凭证: Token ●●●●...aBcD  全局Verify(vl***)     │ ← 凭证
│ App ID: 987654321  [复制]                     │
├──────────────────────────────────────────────┤
│ 📱 号码 (3)                                   │ ← 号码列表
│ +86138001 🟢GREEN 已注册 启用 [🔘]            │
│ +86138002 🟢GREEN 已注册 启用 [🔘]            │
├──────────────────────────────────────────────┤
│ 🔔 Webhook ● healthy  最后事件 06-12 14:30    │ ← Webhook
│ 回调: https://xxx/webhooks/whatsapp          │
│ [管理 Webhook]                                │
├──────────────────────────────────────────────┤
│ Account ID  acc-5a6c80ef  [复制]              │ ← ID 信息（底部收起）
│ WABA ID     123456789012  [复制]              │
│ Portfolio   111222333     [复制]              │
└──────────────────────────────────────────────┘
```

### 4.2 检测按钮行为变化

点击「检测」→ 连接状态卡片内嵌刷新（不弹 toast），子项逐个变 ✅/❌。


## 五、全页面布局重构

### 5.1 页面结构

```
┌─ 工具栏(单行) ───────────────────────────────────────────────────┐
│  [🔍 搜索…]  [🟢全部 ▾]  [添加账户 ▾]  [刷新]  [⚙全局配置]      │
├─ 状态横条 ───────────────────────────────────────────────────────┤
│  🟢 3正常  🟡 1需关注  🔴 0异常  ⚪ 2未配置                       │
├─ 列表 ──────────────────────────┬─ 详情面板(380px, 选中后显示) ──┤
│  (虚拟滚动)                      │                                 │
│  🟢 主客服账户  手·启  2/3 ●正常 │  选中账户的卡片式详情            │
│  ⚪ 测试账户    手·停  0/1 —    │                                 │
│  🟡 营销账户    S·启  1/1 ●异常 │                                 │
│                                 │                                 │
└─────────────────────────────────┴─────────────────────────────────┘
```

### 5.2 改动项

| # | 改动 | 说明 |
|---|------|------|
| 1 | **删除 4 个 Tab** | 号码/Webhook/Signup 内容归入详情面板卡片，不再独立 Tab |
| 2 | **删除账户筛选下拉** | 搜索框 + 状态横条可点击筛选替代 |
| 3 | **合并添加按钮** | "接入新账户"+"添加" → `[添加账户 ▾]` 下拉二选一 |
| 4 | **新增状态横条** | 4 色数字，可点击筛选；替代原 StatsRow 卡片 |
| 5 | **表格虚拟滚动** | 几百行不卡顿，无分页器 |
| 6 | **搜索框增强** | 支持搜索名称/WABA ID/Account ID/备注 |
| 7 | **详情面板加宽** | 340px → 380px |
| 8 | **状态筛选下拉** | 全部/正常/需关注/异常/未配置/手动接入/Embedded Signup |

### 5.3 空态升级

```
┌─────────────────────────────────────────────────────┐
│  📡                                                 │
│  尚未接入 WhatsApp Business 账户                     │
│  接入后可管理 WABA、号码、Webhook，支持多账户并存      │
│                                                     │
│  ┌──────────────┐  ┌────────────────┐              │
│  │ 📋 手动添加   │  │ 🔗 接入新账户   │              │
│  │ 填WABA ID+Token│ │ Embedded Signup│              │
│  └──────────────┘  └────────────────┘              │
│                                                     │
│  也可以先去 [WhatsApp API 测试] 验证 Token            │
└─────────────────────────────────────────────────────┘
```


## 六、备注字段

### 6.1 DB 层

```python
# app/db/models.py → Account
notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

### 6.2 透传路径

```
ensure_account(notes=payload.notes)
  → Account.notes = notes
  → create_manual_account / update_account
  → MetaWabaAccount.notes
  → API 响应
```

### 6.3 前端展示

- **表单**：备注文本框，placeholder "如：归属FB账号 zhangsan@meta.com"
- **列表行**：名称行右侧小字灰色显示（有备注时）
- **详情面板**：头部名称下方显示"备注: fb-zhangsan"
- **搜索**：纳入搜索范围


## 七、大规模账号场景

| 策略 | 实现 |
|------|------|
| 搜索框 | 支持名称/WABA ID/Account ID/备注，输入即过滤 |
| 状态横条 | 点击数字自动筛选（如点击"🔴 2"→ 只看异常） |
| 状态筛选下拉 | 全部/正常/需关注/异常/未配置/手动/Signup |
| 虚拟滚动 | `<Table virtual scroll={{ y: calc }} />`，无分页 |
| 后端分页 | 如果超过 500 个，`listMetaAccounts` 加 `limit/offset` |


## 八、实施顺序

```
Phase A: 后端
  A1. Account model 加 notes → Alembic 迁移
  A2. settings.py 加 meta_global_webhook_app_secret
  A3. ManualMetaAccountRequest 精简字段 + notes
  A4. create_manual_account 自动生成 account_id，从 settings 读 verify_token/app_secret
  A5. 新增 POST /api/meta/accounts/discover 端点
  A6. GlobalWebhookConfigResponse 加 app_secret
  A7. provider 层三个新方法（已有 send_test_message/query_phone_detail/query_business_profile）

Phase B: 前端
  B1. CreateManualModal 改为两段式（填 WABA ID+Token → 加载 → 审阅保存）+ 备注字段
  B2. AccountListTab 重构为 5 列 + 综合灯 + 悬浮操作 + 虚拟滚动
  B3. AccountDetailPanel 重构为卡片式分层 + 连接状态 + 备注
  B4. MetaAccountsPage 重构：删 Tab + 删下拉 + 合并按钮 + 状态横条 + 空态
  B5. api.ts 类型更新：ManualMetaAccountPayload / GlobalWebhookConfig / MetaWabaAccount
  B6. AccountListTab 全局 Webhook Popover 加 app_secret

Phase C: 验证
  C1. npx tsc --noEmit
  C2. Python 创建流程测试（含备注 + 自动生成 account_id）
  C3. discover 端点测试（含 error 场景）
```


## 九、风险与决策

| 决策 | 理由 |
|------|------|
| 删除独立 Tab（号码/Webhook/Signup） | 数据在详情面板已展示，独立列表重复且增加认知负担 |
| 全局共享 Verify Token + App Secret | 同一 Meta App 下所有 WABA 共享，符合 Meta 架构 |
| 自动生成 account_id | 减少填写负担，避免冲突 |
| 不设分页器，用虚拟滚动 | 列表浏览体验更好，几百行不卡 |

