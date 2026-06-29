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

# W6 测试与E2E

## 目标

补测试矩阵和E2E，不主动重写业务实现。

## 不允许

- 不直接改业务主逻辑，除非只是 fixture/import 修复。
- 不用 mock 钱包替代钱包真实 service。
- WhatsApp/payment 可以 fake provider，但必须走真实 route/service。

## 小阶段

1. W6.1 建测试矩阵，进度 15%。
2. W6.2 P0完整链路E2E骨架，进度 35%。
3. W6.3 WhatsApp号码池E2E，进度 50%。
4. W6.4 权限数据漏斗测试，进度 65%。
5. W6.5 H5网关dry-run/agent tests，进度 80%。
6. W6.6 汇总失败归属，进度 100%。

## 测试失败处理

先判断失败属于 W1/W2/W3/W4/W5/W9 哪个所有者，并写入对应 status。
