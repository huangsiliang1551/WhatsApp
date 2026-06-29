# PROJECT_STRUCTURE_NOTES

根据用户提供的 `all_files_full_list.txt`，项目目录中存在大量生成/缓存/历史运行文件。

## 不应默认扫描的目录

```text
.git/**
.venv/**
.python/**
frontend/dist/**
frontend/.vite/**
.codex-artifacts/**
```

## 可用于恢复续跑的目录

```text
.codex-run/progress/**
docs/dev-run/**
docs/progress/**
```

## 重要提醒

- `.codex-run/progress` 已经存在大量历史 progress JSON，不要删除。
- 清理脚本默认不会删除 progress。
- `frontend/dist` 和 `frontend/.vite` 是生成产物，不要作为源码依据。
- 旧 `docs/` 应归档，不应让 Codex 默认读取。
