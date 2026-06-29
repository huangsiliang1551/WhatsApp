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

# W1 P0资金/支付/提现/生产安全

## Full spec

`docs/specs/active/full/01_P0剩余模块代码级开发拆解文档V1.full.md`

## 目标

完成 P0-01、P0-02、P0-03、P0-04、P0-05 的后端主链路和基础测试；P0-07 E2E交给 W6/W9。

## 不允许

- 不改任务 V3 业务规则。
- 不绕过 WalletLedgerService。
- 不删除错误流水。
- 不只改前端。

## 小阶段

1. W1.1 production_guard + readiness，进度 15%。
2. W1.2 CI test collection / pytest-timeout / norecursedirs 修复，进度 25%。
3. W1.3 WalletInvariantGuard + idempotency，进度 45%。
4. W1.4 PaymentCallbackProcessor + provider abstraction + repair race safety，进度 65%。
5. W1.5 WithdrawalRiskService + payout state machine，进度 85%。
6. W1.6 相关 tests 跑通，进度 100%。

## 外部缺失处理

真实支付通道密钥缺失时，使用 fake/generic_hmac provider 完成接口和测试，不暂停。
