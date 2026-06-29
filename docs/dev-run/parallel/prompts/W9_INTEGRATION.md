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

# W9 集成合并

## 目标

完成共享文件接线、冲突合并、最终测试。

## 可修改

见 `FILE_OWNERSHIP.md` W9。

## 小阶段

1. W9.1 合并 migration 顺序，进度 15%。
2. W9.2 app/main.py 注册所有新 route，进度 25%。
3. W9.3 webhooks.py 接入 WhatsAppInboundCommandRouter，进度 40%。
4. W9.4 permission_defs.py 最终合并，进度 55%。
5. W9.5 frontend consoleRoutes.ts 接线，进度 65%。
6. W9.6 运行后端关键测试并修导入/注册问题，进度 80%。
7. W9.7 前端 typecheck/build，进度 90%。
8. W9.8 最终报告，进度 100%。

## 不允许

- 不改变 W1-W6 已确认业务口径。
- 不把测试失败简单跳过。
- 不删除 migration 解决冲突；必须合并。
