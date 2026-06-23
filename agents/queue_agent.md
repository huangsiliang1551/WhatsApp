# Queue Agent – 异步任务处理

## 职责
- 管理 Redis 队列，将耗时任务（AI 调用、电商查询、模板消息发送）放入后台异步执行
- 提供 Worker 进程，支持任务重试、超时控制和死信队列
- 暴露队列长度指标，供监控 Agent 采集
- 确保 Webhook 能在 15 秒内返回 200 OK，避免 Meta 超时

## 输入信息
- Redis 连接地址（环境变量 `REDIS_URL`，例如 `redis://redis:6379/0`）
- 需要异步执行的任务函数（由 `ai_agent`、`api_agent`、`template_agent` 提供）
- 任务配置：超时时间（默认 30 秒）、重试次数（默认 3 次）、重试间隔（指数退避）

## 输出规范
- 提供统一入队函数：`enqueue(queue_name: str, func_path: str, *args, **kwargs) -> job_id`
- 提供 `worker.py` 启动脚本，监听以下队列：
  - `ai_generation`：调用 LLM 生成回复
  - `ecommerce_query`：查询订单/商品/物流
  - `template_send`：发送模板消息
- 每个任务执行失败时，记录错误日志并将任务推入死信队列 `failed_jobs`
- 提供 `/queue/stats` 端点，返回各队列长度、正在处理数、失败数（JSON 格式）

## 数据模型（Redis 中的任务元数据）
```json
{
  "job_id": "uuid",
  "queue": "ai_generation",
  "status": "queued|processing|completed|failed",
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:01Z",
  "retry_count": 0,
  "result": null,
  "error": null
}