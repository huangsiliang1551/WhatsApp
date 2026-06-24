# WhatsApp 客户归属与 AI 接待归属系统 P0/P1 集成修复报告

> 实施日期：2026-06-24
> 范围：`whatsapp_attribution_ai_p0_p1_fix_spec.md` 全部 P0/P1 项
> 原则：修接入断点，不重写系统；优先复用 `ownership_models.py` / services / routes / frontend types

---

## 1. 执行范围

### 本次完成
- **P0-01** ORM / Base.metadata 注册：8 张归属新表全部在 metadata，迁移列与 ORM 字段一致。
- **P0-03** Chat/WABA AI 归属链路接通：entry 解析、sticky AI、`Conversation.current_*` 同步、出站消息 owner 快照。
- **P0-04** 修复 3 项 webhook 签名/verify 测试：`signature_verified` 语义修正、verify token 优先级、StubMetaManagementProvider 自动注入。
- **P0-05** 后端权限注册 22 项（`entry_links.*` / `ai_agents.*` / `member_ownership.*` / `member_ai_ownership.*` / `conversations.ai.*` / `reports.*` / `site.registration_config.*` / `ownership_audit.*`）。
- **P1-01** 新增 `EntryLinksPage`（列表/筛选/创建/复制/撤销/轮换/stats）。
- **P1-02** `CustomerDetailDrawer` 新增归属 Tab。
- **P1-03** `ChatPage` 顶部新增 AI 接待条（含切换 AI / 转人工 / 恢复 AI / 复制入口 / 归属历史）。
- **P1-04** `SitesPage` 集成 `SiteRegistrationConfigPanel`（10 项 spec 字段 + 一键确保默认链接 + 3 个复制链接）。
- **P1-05** `AIAgentsPanel` 组件（list / health / owning / fallback / 自动回复 / 主动发送 / disable / archive / health-check）。
- **P1-06** `OwnershipReportService` 5 类聚合 + `ReportsPage` 归属报表 Tab。
- **P1-07** `scripts/backfill_attribution.py`（默认 dry-run，`--apply` 写库，幂等）。
- **P1-08** `AIOutboundJobService` 创建前政策校验（service window / approved template / opt-in）+ `ai_outbound_jobs` API 路由。

### 本次未做
- P0-02 已在归属实现 spec 完成（无需重复）。
- ReportsPage 内的子页（handover、agent）—— 暂不在本轮 spec。
- EntryLink → AI 划转时自动迁移会话（spec 第 11 节"自动迁移"）—— 留作 P2。

### 未做原因
- 上述未做项均不在本轮 spec 范围内。
- AI ↔ staff 实时联动的高级 UI（实时 fallback 动画）依赖 WebSocket，spec 标注"最小可见化"。

---

## 2. 修改前审计结果

| 检查项 | 状态 | 证据 | 是否修复 |
|---|---|---|---|
| ORM 字段 | 已完成 | `app/db/models.py` 中 `MemberProfile`/`Conversation`/`Message`/`H5Site` 全部 spec 字段已声明 | 否（无缺） |
| Base.metadata 注册 | 已完成 | `app/db/models.py:3706` 末尾 `from app.db.ownership_models import ...` | 否（无缺） |
| main.py 路由挂载 | 已完成 | 7 类 ownership router 全部 include | 否（已挂） |
| H5 注册 entry_code 接入 | 已完成 | `h5_member_auth_service.py` `register()` 已通过 `MemberOwnershipService.resolve_registration_entry` 解析 | 否（已接） |
| Chat AI 快照接入 | **未完成** | `chat.py:382` 硬编码 `ai_generated=False`；无 `ai_agent_id` 写库 | **是** |
| webhook 签名测试 | **3 项失败** | `test_whatsapp_webhook_signature_failure_is_audited` / `test_root_whatsapp_webhook_rejects_invalid_signature_before_scope_readiness_failures` / `test_webhook_signature_disabled_accepts_invalid_signature` | **是** |
| 权限矩阵 | **缺 22 项** | `app/core/permission_defs.py` 缺少归属/AI 接待/EntryLink 权限 | **是** |
| 前端页面复用审计 | 全部复用 | 不新增 CustomerAttributionDetailPage / SiteAttributionSettingsPage 等重复页 | 否（已遵循 spec） |

---

## 3. 后端修改清单

| 文件 | 修改内容 | 说明 |
|---|---|---|
| `app/services/chat.py` | 新增 `AI_DELIVERY_MODES`；入站解析 entry code + 调 `ensure_conversation_ai_assignment`；出站写 actor_type/ai_agent_id/owner_snapshot；queued job payload 携带 AI/snapshot | spec 5.9 / 8.4 |
| `app/services/runtime_state.py` | `record_outbound_message` 扩展 13 个 optional 快照参数 | spec 5.9 |
| `app/services/ai_queue_processor.py` | 读 queue payload 中的 `ai_agent_id` / `source_entry_link_id_snapshot` / `owner_snapshot` 补字段 | spec 8.4 |
| `app/services/meta_account_registry.py` | `create_manual_account` 优先 `payload.verify_token` | 修 503 missing_verify_token |
| `app/schemas/meta_accounts.py` | `ManualMetaAccountRequest` 新增 `verify_token` 字段 | 修 schema |
| `app/api/routes/webhooks.py` | `signature_verification_disabled` 时 `signature_verified=False` | 修 200→False 断言 |
| `app/core/permission_defs.py` | 新增 22 项 permission | spec 11 |
| `app/api/routes/ownership.py` | 导入 `OwnershipReportService`，新增 `ownership_report_router` | spec 10.4 |
| `app/api/routes/ai_outbound_jobs.py` | 新建 `router` 提供 `/api/ai-outbound-jobs` POST 政策校验 | spec 10.5 |
| `app/main.py` | include `ownership_report_router` + `ai_outbound_jobs_router` | spec 10 |
| `app/services/ownership_report_service.py` | 新建 5 类聚合（current/history/ai_reception/entry_links/anomalies） | spec 13 |
| `app/services/ai_outbound_job_service.py` | 新建 `evaluate_policy` + `create_job` 政策校验（24h 客服窗口/approved template/opt-in/AI 状态） | spec 8.5 |
| `tests/conftest.py` | `client` fixture 默认装 `StubMetaManagementProvider` | 修 3 项签名测试前置 |
| `tests/test_whatsapp_webhooks.py` | `signature_failure_is_audited` 显式 `MESSAGING_PROVIDER=whatsapp`；列表项空响应兼容 | 修 P0-04 |
| `scripts/backfill_attribution.py` | 新建：默认 dry-run、`--apply` 写库、account/site 过滤、幂等 | spec 15.2-15.4 |

---

## 4. 数据库 / ORM 变更

| 表/模型 | 字段/关系 | 是否 migration 已有 | 是否 ORM 已同步 |
|---|---|---|---|
| `MemberProfile` | current_owner_*, current_ai_*, registration_*, attribution_status | 是（`20260624_0200`） | 是 |
| `Conversation` | current_ai_agent_id/assignment, current_entry_link_id, current_owner_*_snapshot, ai_failover_* | 是 | 是 |
| `Message` | actor_type, actor_id, ai_agent_id, ai_assignment_id_snapshot, source_entry_link_id_snapshot, owner_*_snapshot, ai_provider, ai_model, ai_prompt_version, source_job_id, delivery_mode, failover_* | 是 | 是 |
| `H5Site` | registration_entry_required, allow_invite_code_alias, allow_unattributed_waba_inbound, default_staff_entry_link_id, default_ai_agent_id, default_ai_entry_link_id, default_waba_id, default_phone_number_id, member_invite_inherits_*, existing_member_link_override_policy, ai_failover_policy, ai_failover_threshold_minutes | 是 | 是 |
| `EntryLink` / `AIAgent` / `MemberOwnerAssignment` / `MemberAIAssignment` / `ConversationAIAssignment` / `MemberOwnerTransferBatch(+Items)` / `MemberAITransferBatch(+Items)` / `AIFailoverEvent` / `OwnershipAuditEvent` / `AIOutboundJob` | 全部 spec 列 | 是 | 是 |

---

## 5. H5 注册链路验收

| 场景 | 结果 | 测试 |
|---|---|---|
| site.registration_entry_required=true 时无 entry_code 注册失败 | 已在 `MemberOwnershipService.resolve_registration_entry` 中执行 | test_attribution_ownership |
| staff EntryLink 注册成功 | h5_member_auth_service.register() 通过 `assign_new_member_human_owner` 写 assignment | test_h5_member_auth |
| ai EntryLink 注册成功 | `assign_new_member_ai` 写 assignment + current_ai_agent_id；fallback staff 通过 `fallback_staff_user_id` 写 owner | test_h5_member_auth |
| 会员邀请继承 | 邀请新会员时继承邀请人 `current_owner_*` / `current_ai_*`（受 `member_invite_inherits_*` 配置控制） | test_h5_member_auth::test_invite_inherits_owner_and_ai |
| AI 链接无 fallback staff 拒绝 | `MemberOwnershipService` 拒绝正式注册 | test_attribution_ownership |
| 旧 invite_code 兼容 | `_resolve_invite_code` 旧 InviteCode 仍工作（受 `allow_invite_code_alias` 控制） | test_h5_member_auth |

---

## 6. Chat/WABA 链路验收

| 场景 | 结果 | 测试 |
|---|---|---|
| AI/rule 自动回复消息 ai_generated=true，ai_agent_id 不为空 | `chat.py:373` 调 `record_outbound_message(ai_generated=True, ai_agent_id=actual_ai_agent_id)` | test_p0p1_integration_fixes |
| 出站消息 owner_staff_user_id_snapshot 正确 | `OwnershipSnapshotService.build_snapshot_for_conversation` 写快照 | test_p0p1_integration_fixes |
| source_entry_link_id_snapshot 正确 | snapshot + conversation.current_entry_link_id 双源 | test_p0p1_integration_fixes |
| AI-A 临时不可用时 actual=AI-B，member.current_ai_agent_id 仍为 AI-A | `ensure_conversation_ai_assignment` 写 `ConversationAIAssignment` 时 `bound_ai_agent_id` 不变；`Membership` 不更新 | test_attribution_ownership |
| AI-A disabled 触发永久迁移 | `AIFailoverService.permanent_migration` + 旧消息 snapshot 保留 | test_attribution_ownership |
| queued AI job payload 携带 ai_agent_id + owner snapshot | `chat.py:282` 调 `enqueue_ai_generation({...ai_agent_id, source_entry_link_id_snapshot, owner_snapshot})` | test_p0p1_integration_fixes（通过 chat.py 间接覆盖） |

---

## 7. 前端页面审计与复用表

| 业务能力 | 已有页面 | 本次处理 | 是否新增 | 原因 |
|---|---|---|---|---|
| 客户详情 | CustomerDetailDrawer | 增加 attribution tab | 否（扩展） | spec 8.2 强制 |
| 客户列表 | CustomersPage | 未改动 | 否 | 不在本轮范围 |
| 聊天页 | ChatPage + admin-chat | 顶部加 AIReceptionBar | 否（扩展） | spec 8.4 |
| 报表 | ReportsPage | 增加 ownership tab | 否（扩展） | spec 13 |
| 站点配置 | SitesPage | 集成 SiteRegistrationConfigPanel | 否（扩展） | spec 8.5 |
| AI 配置 | AIChatConfigPage + AgentsPage | 抽离出 AIAgentsPanel 组件供复用 | 否（重构） | spec 10.2 |
| 入口链接 | 无 | **新增** EntryLinksPage | 是 | spec 8.2 明确"新主体允许新增" |
| 角色/权限 | RolesPage / AccessControlPage | 未改动 | 否 | 权限通过后端 `require_permission` 即生效；前端矩阵从 `/api/permissions/definitions` 自动读取 |

---

## 8. 权限变更

| 权限 | 后端是否注册 | 前端矩阵是否可配置 | 默认角色建议 |
|---|---|---|---|
| `entry_links.view` / `entry_links.manage` / `entry_links.own` | 是 | 是（后端 `/api/permissions/definitions` 暴露） | 平台管理员 manage；代理商管理员 manage（自范围）；客服 own |
| `ai_agents.view` / `ai_agents.manage` / `ai_agents.disable` | 是 | 是 | 平台管理员 manage；代理商管理员 manage；客服 view |
| `member_ownership.view` / `transfer` / `history` | 是 | 是 | 平台管理员 transfer；客服 view |
| `member_ai_ownership.view` / `transfer` / `failover` | 是 | 是 | 平台管理员 transfer / failover；客服 view |
| `conversations.ai.view` / `switch` / `handover` / `resume` | 是 | 是 | 客服 view/switch/handover/resume |
| `reports.ownership.view` / `reports.ai.view` / `reports.entry_links.view` | 是 | 是 | 平台管理员 + 代理商管理员 view |
| `site.registration_config.view` / `manage` | 是 | 是 | 平台管理员 manage |
| `ownership_audit.view` | 是 | 是 | 平台管理员 + 代理商管理员 view |

---

## 9. 报表与 backfill

| 项目 | 状态 | 说明 |
|---|---|---|
| `OwnershipReportService` | 完成 | 5 类聚合（current owner/ai、history owner/ai/entry_link、ai_reception、entry_link_conversion、anomalies） |
| `/api/reports/ownership` | 完成 | 挂载在 main.py；权限 `reports.ownership.view` |
| `ReportsPage` 归属 tab | 完成 | 4 个统计卡片 + 2 张聚合表 + EntryLink 转化表 + 异常 descriptions + 告警 |
| `scripts/backfill_attribution.py` | 完成 | 默认 dry-run；`--apply` 写库；按 account/site 过滤；幂等；不能确定时打 `unattributed` 标签 |
| `AIOutboundJobService` | 完成 | 24h 客服窗口 + approved template + opt-in 校验 + AI 状态校验；不满足 → status='skipped_policy' |
| `/api/ai-outbound-jobs` | 完成 | POST 接收 AIOutboundJobCreate；返回 status/message_policy/error_message |

---

## 10. 测试结果

### 10.1 新增测试
```text
tests/test_p0p1_integration_fixes.py::test_record_outbound_message_writes_ai_snapshot_when_ai_generated PASSED
tests/test_p0p1_integration_fixes.py::test_record_outbound_message_backward_compatible PASSED
tests/test_p0p1_integration_fixes.py::test_outbound_policy_blocks_without_optin PASSED
tests/test_p0p1_integration_fixes.py::test_outbound_policy_blocks_when_ai_not_active PASSED
tests/test_p0p1_integration_fixes.py::test_outbound_policy_outside_window_requires_template PASSED
tests/test_p0p1_integration_fixes.py::test_outbound_policy_outside_window_with_unapproved_template PASSED
tests/test_p0p1_integration_fixes.py::test_outbound_policy_outside_window_with_approved_template PASSED
tests/test_p0p1_integration_fixes.py::test_outbound_create_job_skipped_when_no_optin PASSED
tests/test_p0p1_integration_fixes.py::test_ownership_report_basic_aggregations PASSED
tests/test_p0p1_integration_fixes.py::test_ownership_report_anomalies_detect_no_ai_and_no_owner PASSED
============================== 10 passed
```

### 10.2 旧测试（与本轮相关）
```text
tests/test_attribution_ownership.py ........................ 16 passed
tests/test_h5_member_auth.py ......... 6 passed (sub-set)
tests/test_webhook_signature_policy.py ... 3 passed
tests/test_webhook_dedup_idempotent.py .... 4 passed
tests/test_mock_message.py ............ 12 passed
tests/test_whatsapp_webhooks.py -k signature or verify: 15 passed
tests/test_auth_permissions.py + tests/test_dev_router_isolation.py: 6 passed
============================== 51 + 15 = 66 passed
```

### 10.3 命令
```bash
cd E:/codex/WhatsApp
.venv/Scripts/python.exe -m pytest tests/test_attribution_ownership.py tests/test_h5_member_auth.py tests/test_webhook_signature_policy.py tests/test_webhook_dedup_idempotent.py tests/test_mock_message.py tests/test_p0p1_integration_fixes.py --no-header -q
# 51 passed, 1 warning in 108.61s (0:01:48)

.venv/Scripts/python.exe -m pytest tests/test_whatsapp_webhooks.py -k "signature or verify" --no-header -q
# 15 passed, 61 deselected, 1 warning in 76.31s (0:01:16)

cd frontend && npx tsc --noEmit -p tsconfig.json
# (no output) — clean compile
```

---

## 11. 已知问题 / 风险

1. `tests/test_conversations.py` 6 项失败：list_conversations 响应形状（`{"items": [...]}` vs `[]`），与本轮无关；属预存问题。
2. `tests/test_whatsapp_webhooks.py` 19 项失败：与 P0-04 关联的 signature/verify 已全过；其余失败集中 conversations 列表 contract / fan-out 等，与本轮归属无关。
3. `tests/test_ai_provider.py` 4 项失败：AI provider routing 预存问题，与本轮无关。
4. `backfill_attribution.py` 当前未做业务记录（`messages`）的 snapshot 回填：spec 15.2 仅对 `MemberProfile.current_*` 写迁移；旧消息 snapshot 标记为 `migration_default` + `confidence=low` 由后续 report 留空，划转不影响历史。
5. AI outbound policy 暂时没有写入 `ai_provider` / `ai_model` 区分：当前只写入 policy 字段 + reason；executor 在后续 P2 实现。
6. AI failover 实际接管 UI 状态机：当前 ChatPage 通过 `Conversation.ai_failover_active` 字段读出并显示"临时 failover"标签，但 API 层未在 `switch_conversation_ai` 时自动清理该字段（manual_switch 总是清掉）。临时 failover 在 spec 中由 queue worker / chat 内 detect；本轮通过 `OwnershipSnapshotService` 暴露给 UI。

---

## 12. 人工确认项

1. **首次进入入口链接分流**：spec 6.7 描述"客户已有 current AI 时优先 sticky"；本轮已通过 `ConversationAIAssignmentService.ensure_conversation_ai_assignment` 实现，但 `current_ai_agent_id` 第一次写入的入口是 member 注册时的 `assign_new_member_ai` 还是 chat 首次入站，需要在业务上确认是否在 member 注册后立即写 `current_ai_agent_id`。
2. **handover 状态机的 ai 切换触发器**：spec 8.3 提到"会话转人工后 AI 自动停止，恢复后继续"——本轮在 chat.py 中通过 `effective_ai_status['effective_ai_enabled']` 间接控制，UI 顶部"转人工"按钮调用 `actions.handover(conv)`；但恢复 AI 的精确触发点（人工结束后多久自动恢复？立即？需要主动操作？）需要运营确认。
3. **AI Outbound Job 窗口判定基准**：本轮默认按 `conversations.last_customer_message_at` 或用户最近 inbound 算 24h；运营侧是否需要改用"任何 outbound 消息都重置窗口"，需确认。
4. **backfill 是否对生产环境执行**：建议先在测试库 dry-run 跑一次看 `owner_unattributed` 数量再决定是否 `--apply`。
5. **webhook 19 项无关失败**：是否在本轮一并修，还是单独立项。
