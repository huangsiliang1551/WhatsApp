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

# W5 前端页面

## 目标

实现后台/H5前端页面和 API service。只接真实 API，不 mock 成功。

## 不允许

- 不修改 `frontend/src/routes/consoleRoutes.ts`，W9统一接线。
- 不用 mock 数据作为正式成功状态。
- 不先做菜单大重构。

## 小阶段

1. W5.1 WhatsApp号码池后台组件，进度 20%。
2. W5.2 H5登录/绑定/auto-bind页面，进度 35%。
3. W5.3 H5网关节点页面和Job时间线，进度 55%。
4. W5.4 权限中心四级授权基础页面，进度 70%。
5. W5.5 财务/提现风控页面增强，进度 85%。
6. W5.6 typecheck/build，进度 100%。

## 外部缺失处理

真实 API 尚未完成时，先写 typed client 和 loading/error UI；不要假成功。
