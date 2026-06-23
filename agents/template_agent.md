# Template Agent – WhatsApp 模板消息管理

## 职责
- 与 Meta Cloud API 交互，管理消息模板（创建、编辑、删除、审核状态查询）
- 维护本地模板缓存（PostgreSQL），同步 Meta 侧状态变化
- 提供发送模板消息的接口（支持变量替换）
- 记录模板发送日志（用于统计和问题排查）

## 输入信息
- Meta Business Account ID
- Access Token（具有 `whatsapp_business_management` 权限）

## 核心功能

### 1. 模板创建
- 接收模板名称、语言、类别（营销/交易/身份验证）、组件（标题、正文、按钮、页脚）
- 调用 Meta API：`POST /{business_id}/message_templates`
- 保存模板 ID 和审核状态到数据库

### 2. 模板审核状态同步
- Webhook 接收 `message_template_quality_update` 事件
- 定时轮询（如每 2 小时）同步所有模板状态

### 3. 发送模板消息
- 接口：`POST /api/send-template`
  - 参数：`wa_id`, `template_name`, `language`, `components` (变量值)
- 调用 Meta Cloud API：`POST /{phone_id}/messages`，body 包含 `template` 对象
- 返回消息 ID 并记录发送日志

## 数据库模型（示例）
```sql
CREATE TABLE message_templates (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100),
    language VARCHAR(10),
    category VARCHAR(20),
    status VARCHAR(20), -- PENDING, APPROVED, REJECTED, PAUSED
    components JSONB,
    created_at TIMESTAMP,
    rejected_reason TEXT
);

CREATE TABLE template_send_logs (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(255),
    wa_id VARCHAR(50),
    message_id VARCHAR(255),
    status VARCHAR(20), -- SENT, FAILED, DELIVERED
    error_code VARCHAR(50),
    sent_at TIMESTAMP
);