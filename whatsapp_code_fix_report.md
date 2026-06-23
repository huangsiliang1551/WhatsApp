# WhatsApp 项目代码修复报告（whatsapp_code_fix_spec.md 执行）

执行时间：2026-06-24
执行范围：严格按 `whatsapp_code_fix_spec.md` 顺序，仅做正确性/安全性/稳定性修复，未做仓库清理、未重构前端大文件、未新增业务功能。

---

## 已完成修复

### 1. P0-01 strict permission actor（权限边界）
- **修改文件**：`app/api/deps.py`、`tests/test_auth.py`、新增 `tests/test_auth_permissions.py`
- **要点**：
  - `require_permission()` 改为依赖 `get_strict_request_actor`。
  - 新增 `_allows_header_actor(settings)`：仅 `test_mode` / `auth_required=false` / `app_env ∈ {development,local,dev}` 时允许 `X-Actor-*` header。
  - strict bearer 检查门控为 `require_bearer_token and auth_required and not _allows_header_actor`，并增加 header-actor 拒绝门（production 拒绝伪造身份）。这样既保证 production 强制 bearer、伪造 `X-Actor-Role: super_admin` 被拒，又不击穿 `test_mode=true` 的常规测试套件。
  - 调整 `test_permission_center_rejects_header_only_actor_when_auth_is_required` 改用 `APP_ENV=production` 验证生产拒绝。
- **测试**：`tests/test_auth_permissions.py`（3 用例：production 拒绝伪造 header、production 无 bearer 返 401、test mode 放行）。

### 2. P0-02 conversation stats SQL comparator
- **修改文件**：`app/api/routes/conversations.py`、新增 `tests/test_conversation_stats.py`
- **要点**：新增 `_apply_equal_filter`：bool/None 用 `.is_()`，字符串/数字用 `==`；`_count` 改用该 helper。
- **测试**：插入 open/closed/sleeping 三条会话，断言 active/closed/sleeping 计数正确。

### 3. P0-03 sleeping scanner worker bug
- **修改文件**：`app/worker.py`、新增 `tests/test_sleeping_scanner.py`
- **要点**：移除 `db.execute(Query.update())` 错误用法（`Query.update()` 直接调用）；offset 翻页改为"每次取首批直到没有"，避免在会被更新的数据集上跳批；每批 commit。
- **测试**：3 用例——标记所有符合条件会话（防跳批）、旧消息标 is_cold、可重复运行不报错。

### 4. P1-01 Redis dead-letter 读取
- **修改文件**：`app/providers/queue/redis_provider.py`、新增 `tests/test_redis_dead_letter.py`
- **要点**：`list_dead_letter_jobs` 改用 `lrange` 读 list key（原先用 `GET` 会触发 WRONGTYPE）；scan pattern 由 `queue:dead:*` 改为 `queue:*:dead_letter`；缺失 job payload 时跳过不崩溃。
- **测试**：3 用例（指定 queue、全部 queue、缺失 payload 容错），用自带的 fake 同步 redis 客户端（无需真实 Redis）。

### 5. P1-02 Webhook 去重生产化幂等
- **修改文件**：`app/api/routes/webhooks.py`、`app/services/chat.py`、新增 `tests/test_webhook_dedup_idempotent.py`
- **要点**：
  - 生产路径不再依赖进程内 `_deduplicated_message_ids`（helper 保留为测试辅助）。
  - service 层新增 `_build_deduplicated_result`，并捕获 `IntegrityError` 处理"预检查与 commit 之间"的竞态，回滚后返回已存在消息。
  - DB 最终防线复用既有 `messages.provider_message_id` 全局唯一约束（初始迁移 `20260606_0001` 已存在，未新增迁移）。
  - webhook 路由对 `process_inbound_message` 返回的 `deduplicated` 结果不计入 `accepted_messages`。
- **测试**：重复 mock 入站只产生一条消息行；IntegrityError 竞态坍缩为已存在消息。
- **附带**：修复 `tests/conftest.py` 的 `StubMetaManagementProvider` 未实现基类新增抽象方法（`health_check` 等）导致无法实例化的预存问题，解锁了 `test_webhook_dedup_skips_duplicate_message` 等此前无法运行的测试。

### 6. P1-03 AI_CONFIG_ENCRYPTION_KEY 兼容
- **修改文件**：`app/core/settings.py`、新增 `tests/test_ai_config_encryption_key.py`
- **要点**：`ai_config_encryption_key` 改用 `AliasChoices("AI_CONFIG_ENCRYPTION_KEY","AI_CONFIG_ENCRY_KEY")`，新名优先、旧拼写兼容（Pydantic v2）。
- **测试**：4 用例（新名生效、旧名兼容、新旧并存优先新名、template root 可配置）。

### 7. P1-04 webhook_signature_enabled 真正生效
- **修改文件**：`app/api/routes/webhooks.py`、新增 `tests/test_webhook_signature_policy.py`
- **要点**：新增 `_should_verify_webhook_signature`：`APP_ENV=production` 强制验证（即使 `WEBHOOK_SIGNATURE_ENABLED=false`），dev/test 可关闭；scoped 与 root 两条接收路径均接入，关闭时记 warning 日志。
- **测试**：4 用例（production 强制开/关均验证、development 可关闭、development 默认开启）。

### 8. P2-01 dev/mock 路由生产隔离
- **修改文件**：`app/main.py`、新增 `tests/test_dev_router_isolation.py`
- **要点**：`if settings.app_env != "production" or settings.test_mode: app.include_router(dev_router)`；production 返回 404。
- **测试**：3 用例（development 可用、production 不可用、TEST_MODE 覆盖 production 仍可用），用子进程隔离验证 fresh app。

### 9. P2-02 DB session 自动 commit 收敛（渐进）
- **修改文件**：`app/api/deps.py`
- **要点**：仅新增 `get_readonly_db_session`（不自动 commit）与 `get_transactional_db_session`（显式 commit/rollback），未大范围替换，避免引入"写接口不落库"回归（按 spec 渐进策略）。

### 10. P2-03 main.py 静态路径配置化
- **修改文件**：`app/main.py`、`app/core/settings.py`
- **要点**：新增 `TEMPLATE_STATIC_ROOT` / `TEMPLATE_UPLOAD_ROOT` 配置项（默认值兼容 Docker/生产布局），`main.py` 从 settings 读取并 `Path().expanduser()`，不再硬编码 `/opt/whatsapp/...`。未新增 upload 公开 mount。

---

## 未完成 / 延后
- **P3-01 main.py / 前端大文件拆分**：按 spec 明确"本轮暂缓"，未做。
- **P2-02 DB session 全量迁移**：按 spec 渐进策略，本轮仅新增 dependency，未替换全项目读写接口。

---

## 测试结果

- `python -m py_compile`（全部修改文件 + conftest）：**通过**
- `python -c "from app.main import app; print(app.title)"`：**通过**（WhatsApp Support Platform）
- 新增 8 个测试文件：**全部通过**（共 26 个用例）
- `tests/test_worker.py`：**通过**（P0-03 无回归）
- `tests/test_queue_runtime.py`：**通过**（P1-01 无回归）
- `tests/test_mock_message.py`：**通过**（P1-02 无回归）
- `tests/test_auth.py` 关键用例（含修改的 `test_permission_center_rejects_header_only_actor_when_auth_is_required`、`test_account_scope_blocks_cross_account_read` 等 4 个）：**通过**（P0-01 无回归）
- `alembic upgrade head`：**未运行**——本轮未新增 migration（P1-02 复用既有 `messages.provider_message_id` 唯一约束）。

### 预存失败（与本轮修复无关，已用 `git show HEAD:<file>` 还原后复现确认）
- `tests/test_conversations.py` 11 个失败：`list_conversations` 响应形状不匹配（`string indices must be integers`），还原 `conversations.py` 至 HEAD 后仍同样失败。与 P0-02（仅改 stats）无关。
- `tests/test_whatsapp_webhooks.py` 4 个失败（`test_webhook_signature_disabled_accepts_invalid_signature`、`test_whatsapp_webhook_signature_failure_is_audited`、`test_root_whatsapp_webhook_rejects_invalid_signature_before_scope_readiness_failures`、`test_webhook_error_isolation_continues_on_failure`）：均在 setup 步骤（400/503）或预存 `raise` 行为失败，还原 `webhooks.py` 至 HEAD 后仍同样失败。其中 conftest Stub 修复已使 `test_webhook_dedup_skips_duplicate_message` 等此前无法实例化的测试恢复运行并通过。

---

## 需要人工确认
1. **是否接受 production 环境禁止 header actor**：本轮已按"禁止"实现（production 强制 bearer，伪造 header 被拒）。
2. **是否接受 production 强制 webhook 签名验证**：本轮已按"强制"实现（`APP_ENV=production` 时即使 `WEBHOOK_SIGNATURE_ENABLED=false` 也验证）。
3. **Webhook 去重唯一键**：复用既有 `messages.provider_message_id` 全局唯一约束（比 `(account_id, provider_message_id)` 更严，符合 spec"已有约束不重复创建"）。如需改为按账户作用域的部分唯一索引，请确认。
4. **预存失败的 test_conversations.py / test_whatsapp_webhooks.py**：本轮未处理（out of scope，且还原原始代码后仍失败）。是否需要单独开任务修复这些预存测试基础设施问题。
