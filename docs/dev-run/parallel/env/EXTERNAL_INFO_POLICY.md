# 外部信息缺失处理策略

## 原则

外部第三方信息缺失，不得阻塞代码开发。

缺失时继续完成：

- 数据模型
- 配置项
- 加密存储
- API
- 后台表单
- dry-run
- fake provider
- mock webhook
- 单元测试
- 集成测试骨架

## 缺失信息登记

缺失项写入：

```text
docs/dev-run/parallel/env/EXTERNAL_BLOCKERS.md
```

格式：

```md
## <缺失项>
- 影响模块：
- 真实联调需要：
- 当前替代方案：
- 代码是否已完成：
- 测试是否已用 fake/dry-run 覆盖：
```

## 不允许因为这些缺失暂停

- B 服务器 SSH
- 域名 DNS
- CDN/WAF Token
- Meta App Secret / WABA / Phone Number
- 支付通道密钥
- 生产 JWT/加密密钥
- 对象存储地址

## 必须停下来的情况

- 缺失信息导致产品规则无法确定。
- 缺失信息会导致数据模型不可逆。
- 缺失信息会导致资金错账。
