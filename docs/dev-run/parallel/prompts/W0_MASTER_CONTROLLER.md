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

# W0_MASTER_CONTROLLER 主控线程

## 目标

协调 W0-W9，并维护总体进度百分比。

## 执行步骤

1. 运行：
   ```bash
   python tools/codex/resume_preflight.py
   ```
2. 读取：
   - `docs/dev-run/parallel/MASTER_PROGRESS.md`
   - `docs/dev-run/parallel/status/*.md`
3. 如果 W0 未完成，先执行 `W0_SHARED_FOUNDATION.md`。
4. W0完成后，启动或指导 W1-W6 并行执行。
5. W1-W6完成后，执行 W9 集成。
6. 每个 Worker 更新后，重算总体百分比。

## 百分比计算

总进度 = Σ(worker权重 * worker进度) / 100。

## 汇报格式

```text
[进度汇报]
总体进度：xx%
W0：xx%
W1：xx%
W2：xx%
W3：xx%
W4：xx%
W5：xx%
W6：xx%
W9：xx%

本阶段完成：
阻塞：
下一步：
```

## 不要

- 不要亲自实现所有代码。
- 不要让多个 Worker 修改同一共享文件。
- 不要因为外部环境未填而停止。
