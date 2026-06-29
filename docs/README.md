# docs 目录说明

当前执行文档只在：

```text
docs/specs/active/
docs/dev-run/
docs/progress/
```

旧文档归档在：

```text
docs/archive/
```

Codex 默认禁止读取 `docs/archive/**`。如需查历史，只能读取当前 active spec 明确引用的文件。

## 续跑入口

每次启动先运行：

```bash
python tools/codex/resume_preflight.py
```

然后读取：

```text
docs/dev-run/parallel/MASTER_PROGRESS.md
docs/dev-run/parallel/status/*.md
docs/dev-run/TEST_LOG.md
```
