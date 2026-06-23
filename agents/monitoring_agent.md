# Monitoring Agent – 系统可观测性与告警

## 职责
- 收集系统指标：请求数、延迟、错误率、数据库连接数、队列长度
- 暴露 Prometheus 格式的 `/metrics` 端点
- 配置告警规则（如错误率 >10%、队列积压 >500）
- 对接钉钉/企业微信/Slack 发送告警通知

## 输入信息
- 服务端口、告警接收 Webhook URL
- 期望的阈值配置（可配置化）

## 输出规范
- FastAPI 路由 `/metrics` 返回 Prometheus 格式数据
- 告警规则文件 `alerts.yml`（用于 Prometheus）
- 可选：Grafana 仪表板 JSON 配置

## 数据模型（指标示例）
HELP webhook_requests_total Total webhook requests
TYPE webhook_requests_total counter
webhook_requests_total{status="200"} 12345

HELP queue_length Current length of task queues
TYPE queue_length gauge
queue_length{queue="ai_generation"} 12

## 协作方式
- `queue_agent` 提供队列长度查询接口，`monitoring_agent` 定期拉取
- `api_agent` 在 Webhook 处理时递增计数器
- 告警触发时调用 `logging_agent` 记录审计事件

## 开发顺序建议
1. 集成 `prometheus_client` 库，暴露 `/metrics`
2. 在关键路径埋点（Webhook、数据库查询、AI 调用）
3. 部署 Prometheus + Grafana（可用 Docker Compose 附加）
4. 配置 Alertmanager 并测试告警通知