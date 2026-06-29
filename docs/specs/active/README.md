# Active Specs 执行入口

本目录是当前唯一 active 开发规格。不要读取 `docs/archive/**`。

## 默认读取顺序

1. `docs/specs/active/IMPLEMENTATION_INDEX.md`
2. `docs/dev-run/parallel/FILE_OWNERSHIP.md`
3. 当前 Worker prompt
4. 必要时读取 `full/` 中对应完整规格

## Full specs

```text
full/01_P0剩余模块代码级开发拆解文档V1.full.md
full/02_WhatsApp登录绑定与站点号码池共享服务号开发文档V2.full.md
full/03_四级权限漏斗与数据漏斗架构开发文档V2.full.md
full/04_H5多域名防攻击隔离与AB服务器后台控制部署方案V2.full.md
```

## Worker顺序

1. W0 共享基础与迁移
2. W1 P0资金/支付/提现/生产安全
3. W2 WhatsApp站点号码池
4. W3 四级权限与数据漏斗
5. W4 H5网关与B服务器控制
6. W5 前端页面
7. W6 测试与E2E
8. W9 集成合并
