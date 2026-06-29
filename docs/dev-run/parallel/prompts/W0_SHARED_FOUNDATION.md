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

# W0 共享基础与迁移

## 目标

建立并行开发所需共享基础，避免 W1-W6 直接冲突。

## 允许修改

见 `FILE_OWNERSHIP.md` W0。

## 小阶段

### W0.1 当前源码复查
- 精确搜索现有模型、路由、权限码、settings、migration head。
- 更新 `docs/dev-run/parallel/status/W0.md` 到 10%。

### W0.2 共享模型占位
- 在不破坏现有模型的前提下加入或预留：
  - P0钱包/提现/支付必要字段
  - WhatsApp号码池必要模型
  - 权限漏斗必要模型
  - H5网关必要模型
- 新增 Alembic migration。
- 进度 45%。

### W0.3 设置与权限码
- settings 增加外部配置占位。
- permission_defs 增加新增模块权限码。
- 进度 65%。

### W0.4 路由注册占位
- app/main.py 只做安全可导入注册，不实现业务。
- 进度 80%。

### W0.5 基础测试
- 跑 import/migration/权限定义基础测试。
- 进度 100%。

## Full specs

必要时只读取四份 full specs 中的模型/权限章节，不要全量阅读。
