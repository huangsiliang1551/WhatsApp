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

# W3 四级权限与数据漏斗

## Full spec

`docs/specs/active/full/03_四级权限漏斗与数据漏斗架构开发文档V2.full.md`

## 目标

实现四级权限漏斗和数据漏斗后端核心能力。

## 不允许

- 不用 created_by 判断主管数据范围。
- 不把会话转接等同于客户永久归属转移。
- 不只做前端隐藏菜单。
- 不用单纯 account_id 替代团队/成员过滤。

## 小阶段

1. W3.1 EffectiveAccessService / PermissionGrant，进度 25%。
2. W3.2 StaffTeam / StaffTeamAssignment / DataScopeGrant 服务，进度 45%。
3. W3.3 CustomerOwnershipAssignment / DataScopeFilterService，进度 65%。
4. W3.4 ConversationAssignment / HandoverQueue / AIHandoverPolicy，进度 80%。
5. W3.5 财务/客户/会话/报表过滤接入点，进度 90%。
6. W3.6 tests，进度 100%。
