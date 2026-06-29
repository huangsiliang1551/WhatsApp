# Continuation and Resume Protocol

## 目标

确保 Codex 额度耗尽、会话关闭、浏览器刷新、线程中断后，可以继续未完成任务，不重做、不乱改、不停在外部信息上。

## 每个 Worker 必须遵守

1. 每完成一个小阶段，立刻更新 `docs/dev-run/parallel/status/Wx.md`。
2. 每次测试后追加 `docs/dev-run/TEST_LOG.md`。
3. 每次跨文件大改动后，写入已改文件列表。
4. 额度即将耗尽时，先写 checkpoint：
   - 当前阶段
   - 已完成
   - 未完成
   - 下一个具体动作
   - 失败测试
5. 新会话启动必须运行：
   ```bash
   python tools/codex/resume_preflight.py
   ```
6. 禁止从头重做已经 marked done 的小阶段。

## 外部信息缺失时

缺少以下信息不算阻塞：

- B服务器 SSH
- 真实域名 DNS
- CDN/WAF Token
- Meta/WABA/Phone Number
- 支付通道密钥
- 生产 secret
- 真实对象存储

处理方式：

1. 写入 `docs/dev-run/parallel/env/EXTERNAL_BLOCKERS.md`。
2. 完成接口、模型、service、fake provider、dry-run脚本、前端表单、测试。
3. 使用 placeholder / dummy / fake provider。
4. 不要停止开发。

## 允许停下来的情况

- 产品规则冲突。
- 破坏性 migration。
- 资金错账风险无法规避。
- 权限越权风险无法规避。
- 连续两轮合理修复后核心测试仍失败。
