# Logging Agent – 系统日志与审计追踪

## 职责
- 记录所有关键操作（消息收发、API 调用、模板发送、客服转接、配置变更）
- 为合规审查提供不可篡改的审计轨迹
- 支持日志查询、筛选、导出功能（供管理后台使用）
- 实现日志轮转与归档，避免磁盘占满

## 日志分类

| 类别 | 说明 | 保留周期 |
| :--- | :--- | :--- |
| **消息日志** | 每条通过 WhatsApp 收发的消息（用户ID、方向、内容、时间戳） | 90 天 |
| **API 调用日志** | 调用电商后台、AI 服务的请求/响应（脱敏后） | 30 天 |
| **操作审计日志** | 管理员登录、模板创建/删除、客服转接、系统配置修改 | 180 天 |
| **错误日志** | 系统异常、接口超时、重试失败等 | 60 天 |

## 存储方案
- **结构化日志**：存入 PostgreSQL（表 `audit_logs`, `message_logs`）
- **详细请求/响应**：可写入对象存储（如阿里云 OSS、AWS S3）并保留链接
- **应用日志**：输出到 stdout，由 Docker 日志驱动收集（或使用 Loki）

## 数据库模型（示例）
```sql
-- 消息日志表
CREATE TABLE message_logs (
    id BIGSERIAL PRIMARY KEY,
    wa_id VARCHAR(50),
    direction VARCHAR(10),   -- inbound / outbound
    message_type VARCHAR(20),-- text / image / template / interactive
    content TEXT,            -- 脱敏后的内容
    template_id VARCHAR(255),-- 若为模板消息
    msg_id VARCHAR(255),     -- Meta 返回的消息 ID
    status VARCHAR(20),      -- sent / delivered / read / failed
    created_at TIMESTAMP DEFAULT NOW()
);
-- 为 wa_id + created_at 建立索引

-- 操作审计表
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50),     -- 操作者（管理员或客服ID）
    action VARCHAR(50),      -- CREATE_TEMPLATE, SEND_MESSAGE, TRANSFER_CONVERSATION
    target_type VARCHAR(50), -- template, conversation, agent
    target_id VARCHAR(255),
    details JSONB,           -- 操作详情
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW()
);