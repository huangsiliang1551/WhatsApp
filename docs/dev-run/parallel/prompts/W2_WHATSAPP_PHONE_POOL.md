# Codex Worker Prompt

## 必读

- `AGENTS.md`
- `docs/README.md`
- `docs/specs/active/IMPLEMENTATION_INDEX.md`
- `docs/dev-run/parallel/CONTINUATION_AND_RESUME_PROTOCOL.md`
- `docs/dev-run/parallel/FILE_OWNERSHIP.md`
- `docs/dev-run/parallel/env/EXTERNAL_INFO_POLICY.md`

## 执行规则

- 不读取 `docs/archive/**`。
- 不扫描 `.git/**`、`.venv/**`、`.python/**`、`frontend/dist/**`、`frontend/.vite/**`。
- 缺少外部第三方信息时，不暂停，写入 `EXTERNAL_BLOCKERS.md` 并继续 dry-run/mock 实现。
- 每完成小阶段更新本 Worker status。
- 额度即将用完时先写 checkpoint。
- 输出必须包含百分比。

# W2 WhatsApp站点号码池

## Full spec

`docs/specs/active/full/02_WhatsApp登录绑定与站点号码池共享服务号开发文档V2.full.md`

## 目标

实现站点号码池共享服务号后端主链路。

## 不允许

- 不新增第二套 WhatsApp Provider。
- 不新增第二套 Webhook。
- 不直接改 `app/api/routes/webhooks.py`；提供 `WhatsAppInboundCommandRouter`，由 W9 接线。
- `LOGIN/BIND/AUTO_BIND` 不进入 AI。

## 小阶段

1. W2.1 号码池 service + 选择算法，进度 20%。
2. W2.2 identity/session/auto-bind service，进度 45%。
3. W2.3 H5 login/bind/auto-bind API，进度 60%。
4. W2.4 inbound command router service，进度 75%。
5. W2.5 message routing service：同站点多号码会话合并，进度 90%。
6. W2.6 tests，进度 100%。

## 外部缺失处理

Meta/WABA/Phone真实信息缺失时，使用 MetaAccountRegistry stub 和 fake webhook payload 测试，不暂停。
