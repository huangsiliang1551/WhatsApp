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

# W4 H5网关B服务器控制

## Full spec

`docs/specs/active/full/04_H5多域名防攻击隔离与AB服务器后台控制部署方案V2.full.md`

## 目标

实现 A后台控制 B服务器的后端、Agent、脚本、dry-run 和测试。

## 不允许

- 不让 B服务器跑 A 后端。
- 不开放任意 SSH 命令执行。
- 不保存明文 SSH 私钥。
- 不让 H5 域名访问后台 API。
- 不每个 H5 单独占端口。
- 不因为没有真实 B服务器暂停。

## 小阶段

1. W4.1 H5GatewayNode/Credential/Job/Step service，进度 20%。
2. W4.2 SSH white-list service + fake ssh tests，进度 35%。
3. W4.3 B Agent poll/heartbeat/job step API，进度 50%。
4. W4.4 deploy/h5-gateway scripts dry-run/json-output，进度 70%。
5. W4.5 Nginx config render/apply + cert/firewall/block scripts，进度 85%。
6. W4.6 tests，进度 100%。

## 外部缺失处理

没有真实 B 服务器时，完成 fake SSH、dry-run、脚本单元测试、后台接口，不暂停。
