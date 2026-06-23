# 监控、CI/CD 与部署运维任务清单（DevOps Agent 专用）

> **执行角色**: deploy_agent + monitoring_agent + logging_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**

---

## 0. 当前状态总览

### 已有资产

| 文件 | 行数 | 状态 |
|------|------|------|
| `.github/workflows/ci.yml` | 120 | 有 3 个 job，基本可用 |
| `monitoring/prometheus/prometheus.yml` | 20 | 仅配 1 个 scrape target |
| `monitoring/prometheus/alerts.yml` | 39 | 4 条告警规则，缺业务告警 |
| `monitoring/alertmanager/alertmanager.yml` | 15 | 仅 default-null receiver，无真实通知 |
| `monitoring/grafana/dashboards/whatsapp-platform-overview.json` | 955 | 已有基础 dashboard |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | 11 | 已配 Prometheus 数据源 |
| `monitoring/grafana/provisioning/dashboards/dashboards.yml` | 13 | 已配 dashboard provider |
| `app/core/metrics.py` | 623 | 丰富：30+ Counter/Gauge，含 build_metrics_summary() |
| `scripts/backup-postgres.ps1` | 68 | 可用 |
| `scripts/restore-postgres.ps1` | 68 | 可用（需手动输入 RESTORE） |
| `scripts/check-launch-readiness.ps1` | 118 | 可用（5 步检查） |
| `scripts/verify-ci.ps1` | 未读 | 待验证 |
| `.env.example` | 67 | 基本完整 |
| `docs/deployment-checklist.md` | 存在 | 待验证内容 |
| `docs/recovery-runbook.md` | 存在 | 待验证内容 |

### 已有 Prometheus 指标（metrics.py 中已定义）

**消息类**: mock_inbound, business_inbound, business_outbound, message_processing_failures, message_delivery_events
**Webhook 类**: whatsapp_webhook_messages/status_updates/signature_failures (含 scoped 版本), template_updates, phone_number_updates, phone_scope_rejections
**AI 类**: business_ai_replies (queued/success/routed/fallback/disabled/skipped_handover)
**模板类**: business_template_sends, business_template_send_failures
**队列类**: queue_jobs_total, queue_jobs_current
**翻译类**: translation_operations
**业务类**: task_submissions, task_reviews, tickets_created, tickets_status_transition
**Provider 类**: provider_status_event_buffer (pending_current, oldest_age, events_total)

### 已有告警规则（alerts.yml 4 条）

1. WhatsAppAppDown — app 宕机 1 分钟
2. AIQueueBacklogHigh — AI 队列积压 > 50 持续 10 分钟
3. AIQueueFailuresPresent — AI 队列有失败任务 > 5 分钟
4. ProviderStatusBufferStuck — WhatsApp status buffer 不排空 > 5 分钟

### 已有 CI 流水线（ci.yml 3 个 job）

1. backend-tests — Python 3.14 + pytest
2. backend-postgres-concurrency — PG 17 + 并发测试
3. frontend-and-config — Node 22 + npm build + docker compose config + Grafana JSON + Alertmanager + PS1 脚本校验

---

## 1. 差距分析

| 能力 | 当前 | 目标 | 优先级 |
|------|------|------|--------|
| 业务告警规则 | 仅 4 条基础设施告警 | 覆盖错误率、会话无响应、Worker 异常、模板失败率 | P0 |
| Alertmanager 通知 | default-null（不通知） | Webhook 通知（企业微信/钉钉/Slack） | P0 |
| Grafana Dashboard | 1 个 overview | 增加运维专用面板（AI 管道、模板、会话、H5） | P1 |
| CI 流水线 | 3 个 job | 增加 lint job + docker build job + 并行优化 | P1 |
| .env.example | 67 行，基本完整 | 补齐 H5 member session 配置 + Grafana 配置 | P1 |
| 备份脚本 | PG 备份/恢复可用 | 增加 Redis 备份 + 自动清理旧备份 | P2 |
| 部署文档 | 有文件 | 验证并更新为最新配置 | P2 |
| 健康探针 | /health + /metrics 已有 | Worker 健康端点缺失 | P1 |

---

## 2. 执行编排

```
Phase 1（可并行，无依赖）:
  DO-001 (告警规则补全)          ── monitoring_agent
  DO-002 (Alertmanager 通知)     ── monitoring_agent
  DO-003 (CI 流水线优化)         ── deploy_agent
  DO-004 (.env.example 更新)     ── deploy_agent

Phase 2（依赖 Phase 1）:
  DO-005 (Grafana 面板补全)      ── monitoring_agent     ← 依赖 DO-001
  DO-006 (Worker 健康端点)       ── logging_agent

Phase 3（运维脚本）:
  DO-007 (Redis 备份脚本)        ── deploy_agent
  DO-008 (部署文档更新)          ── deploy_agent

Phase 4（验证）:
  DO-009 (CI 验证)               ── testing_agent         ← 依赖 DO-003
  DO-010 (端到端验证)            ── testing_agent         ← 依赖所有
```

---

## 3. 任务详情

### DO-001：Prometheus 告警规则补全

- **角色**: monitoring_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 当前状态

`monitoring/prometheus/alerts.yml` 仅 4 条规则（39 行），只覆盖 app 宕机 + AI 队列 + provider buffer。

#### 需要新增的告警规则

在现有 `whatsapp-platform` group 中追加以下规则：

**1. 高错误率告警**
```yaml
- alert: HighErrorRate
  expr: |
    sum(rate(message_processing_failures_total[5m]))
    / sum(rate(business_inbound_messages_total[5m])) > 0.1
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "消息处理错误率超过 10%"
    description: "过去 5 分钟消息处理错误率为 {{ $value | humanizePercentage }}，超过 10% 阈值。"
```

**2. 签名失败告警**
```yaml
- alert: WebhookSignatureFailuresHigh
  expr: rate(whatsapp_webhook_signature_failures_total[10m]) > 0
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Webhook 签名验证持续失败"
    description: "过去 10 分钟内有签名验证失败，可能是 app_secret 不匹配。"
```

**3. AI 回复降级率告警**
```yaml
- alert: AIFallbackRateHigh
  expr: |
    sum(rate(business_ai_replies_total{outcome="fallback"}[10m]))
    / sum(rate(business_ai_replies_total[10m])) > 0.3
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "AI 回复降级率超过 30%"
    description: "过去 10 分钟 AI 降级回复占比 {{ $value | humanizePercentage }}。"
```

**4. 模板发送失败率告警**
```yaml
- alert: TemplateSendFailureHigh
  expr: |
    sum(rate(business_template_send_failures_total[10m])) > 0
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "模板消息发送持续失败"
    description: "过去 10 分钟内存在模板发送失败事件。"
```

**5. Worker 宕机告警**
```yaml
- alert: WhatsAppWorkerDown
  expr: up{job="whatsapp_worker"} == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "WhatsApp worker 进程不在线"
    description: "Worker 进程超过 1 分钟不可达。"
```

**6. 翻译失败率告警**
```yaml
- alert: TranslationFailureHigh
  expr: |
    sum(rate(translation_operations_total{outcome="fallback"}[10m]))
    / sum(rate(translation_operations_total[10m])) > 0.5
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "翻译降级率超过 50%"
    description: "过去 10 分钟翻译操作降级占比过高。"
```

#### 涉及文件

- **修改**: `monitoring/prometheus/alerts.yml`（从 39 行 → ~120 行）

#### 同时修改 prometheus.yml

在 `scrape_configs` 中为 worker 容器添加 scrape target（如果 worker 未来暴露 /metrics 的话），当前暂不添加，等 DO-006 完成 Worker 健康端点后再配。

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
docker compose restart prometheus alertmanager
```

#### 验收标准

1. alerts.yml 包含 10 条告警规则（原 4 + 新 6）
2. 规则语法正确（可通过 `promtool check rules` 验证）
3. CI 中 Alertmanager 校验步骤仍通过
4. Grafana Alerts 页面可见新规则

#### 重试策略

- 最大重试: 3 次
- 失败回滚: 恢复原始 alerts.yml

#### 交付物

- 修改后的 alerts.yml
- promtool 验证输出

---

### DO-002：Alertmanager 通知配置

- **角色**: monitoring_agent
- **优先级**: P0
- **前置依赖**: 无
- **估计耗时**: 15 分钟

#### 当前状态

`monitoring/alertmanager/alertmanager.yml` 仅 15 行，receiver 为 `default-null`（丢弃所有告警）。

#### 需要修改

替换为真实通知配置：

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: default-webhook
  group_by:
    - alertname
    - job
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: critical-webhook
      group_wait: 10s
      repeat_interval: 1h
    - match:
        severity: warning
      receiver: default-webhook
      repeat_interval: 4h

receivers:
  - name: default-webhook
    webhook_configs:
      - url: "http://placeholder-webhook:5000/alert"
        send_resolved: true
        http_config:
          follow_redirects: true

  - name: critical-webhook
    webhook_configs:
      - url: "http://placeholder-webhook:5000/critical-alert"
        send_resolved: true
        http_config:
          follow_redirects: true

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal:
      - alertname
      - job
```

**说明**:
- Webhook URL 使用 `placeholder-webhook:5000` 占位（CI 验证只需要 YAML 语法正确）
- `.env` 中已有 `ALERT_WEBHOOK_URL` 配置，可在 docker-compose.yml 中通过环境变量注入
- 保留 `default-null` 作为无通知时的 fallback receiver（在 inhibit_rules 中引用）

#### 涉及文件

- **修改**: `monitoring/alertmanager/alertmanager.yml`

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
docker compose restart alertmanager
```

#### 验收标准

1. alertmanager.yml 语法正确（CI 中 amtool check-config 通过）
2. 有 critical 和 warning 两级路由
3. 有 inhibit_rules（critical 抑制同名 warning）
4. Webhook URL 可通过环境变量覆盖

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 修改后的 alertmanager.yml

---

### DO-003：CI 流水线优化

- **角色**: deploy_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 30 分钟

#### 当前状态

`.github/workflows/ci.yml` 有 3 个 job，但缺少：
1. Python lint 检查（type hints 验证）
2. Docker image build 验证
3. 并发限制（3 个 job 可能不够并行）

#### 需要优化

**1. 新增 `lint` job**（在其他 job 之前运行）

```yaml
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.14"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e .[dev]

      - name: Python syntax check
        run: python -m py_compile app/main.py

      - name: Import check
        run: python -c "from app.main import app; print(f'FastAPI app loaded: {app.title}')"
```

**2. 新增 `docker-build` job**

```yaml
  docker-build:
    runs-on: ubuntu-latest
    needs: [lint]
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Build Docker image
        run: docker compose build app

      - name: Verify container starts
        run: |
          docker compose up -d app
          sleep 10
          docker compose exec app python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"
          docker compose down
```

**3. 优化并行度**

```yaml
  backend-tests:
    needs: [lint]
    # ...

  backend-postgres-concurrency:
    needs: [lint]
    # ...

  frontend-and-config:
    needs: [lint]
    # ...
```

#### 涉及文件

- **修改**: `.github/workflows/ci.yml`（从 120 行 → ~180 行）

#### 验收标准

1. CI 有 5 个 job: lint → (backend-tests | backend-postgres-concurrency | frontend-and-config | docker-build)
2. lint job 在所有其他 job 之前运行
3. docker-build job 验证镜像可构建、容器可启动
4. YAML 语法正确
5. CI 中所有验证步骤通过

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 修改后的 ci.yml

---

### DO-004：.env.example 更新

- **角色**: deploy_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 10 分钟

#### 当前状态

`.env.example` 有 67 行，基本完整。但缺失：
1. H5 member session 配置（settings.py 中已有对应字段）
2. Grafana 配置
3. 告警 Webhook URL
4. 注释不够清晰

#### 需要补充的配置项

```ini
# ==============================
# H5 Member Session
# ==============================
H5_MEMBER_SESSION_COOKIE_NAME=h5_member_session
H5_MEMBER_SESSION_TTL_HOURS=12
H5_MEMBER_REFRESH_COOKIE_NAME=h5_member_refresh
H5_MEMBER_REFRESH_TTL_DAYS=30
H5_MEMBER_COOKIE_SECURE=false
H5_MEMBER_COOKIE_DOMAIN=
H5_MEMBER_COOKIE_SAMESITE=lax

# ==============================
# Grafana
# ==============================
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# ==============================
# Alerting
# ==============================
# Webhook URL for alert notifications (DingTalk / WeCom / Slack)
ALERT_WEBHOOK_URL=
# Queue backlog alert threshold
QUEUE_LENGTH_ALERT_THRESHOLD=500
# Error rate alert threshold (percentage)
ERROR_RATE_ALERT_THRESHOLD=10
```

#### 涉及文件

- **修改**: `.env.example`（从 67 行 → ~95 行）

#### 验收标准

1. 所有 settings.py 中的配置项在 .env.example 中都有对应条目
2. 每个配置项有注释说明
3. 默认值合理（开发环境可用）
4. 不包含真实密钥（敏感值为空）

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 修改后的 .env.example

---

### DO-005：Grafana Dashboard 补全

- **角色**: monitoring_agent
- **优先级**: P1
- **前置依赖**: DO-001
- **估计耗时**: 45 分钟

#### 当前状态

`monitoring/grafana/dashboards/whatsapp-platform-overview.json` 已有 955 行基础 dashboard。

#### 需要新增的面板

在现有 dashboard JSON 中追加以下 panel：

**1. AI 管道面板**
- AI 回复成功率（时间序列图）
- AI 降级率（时间序列图）
- AI 回复延迟（如果有 histogram）
- AI 队列深度（Gauge）

**2. 模板消息面板**
- 模板发送量（时间序列图）
- 模板发送成功率（时间序列图）
- 模板失败原因分布（饼图）

**3. 会话面板**
- 活跃会话数（按模式分布：ai_managed / human_managed / paused）
- 人工接管频率（时间序列图）
- 平均接管时长

**4. H5 面板**
- H5 认证请求量
- H5 任务提交量
- H5 工单创建量

**5. 系统面板**
- Worker 健康状态
- 队列处理速率
- 翻译降级率

#### 涉及文件

- **修改**: `monitoring/grafana/dashboards/whatsapp-platform-overview.json`

#### 验收标准

1. Dashboard JSON 语法正确（CI 中 ConvertFrom-Json 通过）
2. 面板引用的指标在 metrics.py 中存在
3. 面板布局合理，不重叠
4. Grafana 启动后 Dashboard 自动加载

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 修改后的 dashboard JSON

---

### DO-006：Worker 健康端点

- **角色**: logging_agent
- **优先级**: P1
- **前置依赖**: 无
- **估计耗时**: 20 分钟

#### 当前状态

Worker 进程（`app/worker.py`）没有健康检查端点。Docker Compose 中 worker 服务也没有 healthcheck。

#### 需要实现

1. **Worker 状态文件**
   - Worker 定期写入状态到 Redis（或本地文件）
   - 状态内容：最后处理时间、处理任务数、错误数、运行时长

2. **健康检查 API**（挂载在 app 服务）
   - `GET /api/worker/health`
   - 返回 Worker 最后活动时间
   - 如果超过 60 秒无活动，返回 unhealthy

3. **docker-compose.yml worker healthcheck**
   ```yaml
   healthcheck:
     test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://app:8000/api/worker/health').read()"]
     interval: 30s
     timeout: 5s
     retries: 3
   ```

#### 涉及文件

- **新增**: `app/services/worker_health.py`（Worker 状态管理）
- **新增**: `app/api/routes/worker_health.py`（健康检查端点）
- **修改**: `app/worker.py`（定期写入状态）
- **修改**: `app/main.py`（注册路由）
- **修改**: `docker-compose.yml`（worker healthcheck）

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_worker.py tests\test_health.py -v --tb=short
```

#### 验收标准

1. `GET /api/worker/health` 返回 Worker 状态
2. Worker 不活跃超过 60 秒时返回 unhealthy
3. docker-compose.yml 中 worker 有 healthcheck
4. 现有 test_worker.py、test_health.py 通过

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 新增的 worker_health 服务和路由
- 修改后的 worker.py 和 docker-compose.yml

---

### DO-007：Redis 备份脚本

- **角色**: deploy_agent
- **优先级**: P2
- **前置依赖**: 无
- **估计耗时**: 20 分钟

#### 需要新增

`scripts/backup-redis.ps1`

功能：
1. 触发 Redis BGSAVE
2. 等待 RDB 文件生成
3. 从容器中复制 RDB 文件到本地备份目录
4. 生成 manifest.json（与 backup-postgres.ps1 格式一致）

```powershell
param(
    [string]$OutputDir = ".\backups",
    [string]$ContainerName = "whatsapp_redis"
)
# ... 触发 BGSAVE → 等待 → docker cp → 生成 manifest
```

#### 涉及文件

- **新增**: `scripts/backup-redis.ps1`

#### 验收标准

1. 脚本语法正确（PowerShell parser 通过）
2. 可从运行中的 Redis 容器备份
3. 输出目录结构与 backup-postgres.ps1 一致

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 新增 backup-redis.ps1

---

### DO-008：部署文档更新

- **角色**: deploy_agent
- **优先级**: P2
- **前置依赖**: DO-004
- **估计耗时**: 20 分钟

#### 需要更新

1. **docs/deployment-checklist.md**
   - 确保反映最新 docker-compose.yml 配置（资源限制、volume 收窄）
   - 确保 .env.example 中所有配置项都有说明
   - 增加部署前检查清单

2. **docs/recovery-runbook.md**
   - 确保反映最新备份/恢复脚本
   - 增加 Redis 恢复步骤
   - 增加 Worker 故障恢复步骤

3. **scripts/check-launch-readiness.ps1**
   - 验证是否与最新后端 API 一致
   - 如有不匹配则更新

#### 涉及文件

- **修改**: `docs/deployment-checklist.md`
- **修改**: `docs/recovery-runbook.md`
- **验证/修改**: `scripts/check-launch-readiness.ps1`

#### 验收标准

1. 部署清单与当前 docker-compose.yml 一致
2. 恢复手册覆盖 PG + Redis + Worker
3. check-launch-readiness.ps1 语法正确
4. CI 中 PS1 校验通过

#### 重试策略

- 最大重试: 3 次

#### 交付物

- 更新后的文档和脚本

---

### DO-009：CI 验证

- **角色**: testing_agent
- **优先级**: P1
- **前置依赖**: DO-003
- **估计耗时**: 15 分钟

#### 验证命令

```powershell
cd E:\codex\WhatsApp

# 验证 CI YAML 语法
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# 验证 alerts.yml 语法
docker run --rm -v "$PWD/monitoring/prometheus/alerts.yml:/alerts.yml:ro" prom/prometheus:v2.54.1 promtool check rules /alerts.yml

# 验证 Alertmanager 配置
docker run --rm -v "$PWD/monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro" prom/alertmanager:v0.28.1 amtool check-config /etc/alertmanager/alertmanager.yml

# 验证 Grafana Dashboard JSON
powershell -Command "Get-Content monitoring/grafana/dashboards/whatsapp-platform-overview.json -Raw | ConvertFrom-Json | Out-Null"

# 验证 PS1 脚本
powershell -Command "$null = [System.Management.Automation.Language.Parser]::ParseFile('scripts/backup-redis.ps1', [ref]$null, [ref]$errors); if ($errors.Count) { throw ($errors | ForEach-Object { $_.Message }) }"

# 验证 docker-compose
docker compose config --quiet
```

#### 验收标准

1. 所有验证命令通过
2. CI YAML 有 5 个 job
3. alerts.yml 有 10 条规则
4. Grafana JSON 可解析
5. 所有 PS1 脚本语法正确

---

### DO-010：端到端验证

- **角色**: testing_agent
- **优先级**: P0
- **前置依赖**: 所有 DO 任务完成
- **估计耗时**: 20 分钟

#### 验证步骤

```powershell
cd E:\codex\WhatsApp

# 1. 重启监控栈
docker compose restart prometheus alertmanager grafana

# 2. 验证 Prometheus targets
curl http://127.0.0.1:9090/api/v1/targets

# 3. 验证 Prometheus rules
curl http://127.0.0.1:9090/api/v1/rules

# 4. 验证 Alertmanager
curl http://127.0.0.1:9093/api/v2/status

# 5. 验证 Grafana dashboards
curl -u admin:admin http://127.0.0.1:3000/api/search

# 6. 验证 Worker 健康端点
curl http://127.0.0.1:8000/api/worker/health

# 7. 验证 /health 和 /metrics
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/metrics

# 8. 运行相关测试
.\.venv\Scripts\python.exe -m pytest tests\test_health.py tests\test_metrics.py tests\test_worker.py -v --tb=short
```

#### 验收标准

| 项目 | 预期 |
|------|------|
| Prometheus targets | app:8000 状态为 UP |
| Prometheus rules | 10 条告警规则可见 |
| Alertmanager | status 为 ready |
| Grafana dashboards | whatsapp-platform-overview 可见 |
| Worker health | 返回 JSON 状态 |
| /health | 返回 200 |
| /metrics | 返回 Prometheus 格式指标 |
| pytest | 全部通过 |

---

## 4. 全局约束

1. **不修改 app/ 业务代码**（DO-006 Worker 健康端点除外）
2. **不修改 frontend/**
3. **不修改 alembic/**
4. **监控配置必须与现有 metrics.py 指标匹配** — 不要引用不存在的指标
5. **CI 配置必须可在 GitHub Actions ubuntu-latest 上运行**
6. **所有 PS1 脚本必须通过 PowerShell Parser 语法检查**
7. 进度文件: `.codex-run/progress/DO-XXX.json`
8. 单任务最大执行 60 分钟
9. 失败自动回滚 + 重试最多 3 次
10. 所有任务一次性完成，不中途暂停确认

---

## 5. 修改文件清单汇总

| 文件 | 动作 | 任务 |
|------|------|------|
| `monitoring/prometheus/alerts.yml` | 修改（4→10 条规则） | DO-001 |
| `monitoring/alertmanager/alertmanager.yml` | 修改（null→webhook） | DO-002 |
| `.github/workflows/ci.yml` | 修改（3→5 job） | DO-003 |
| `.env.example` | 修改（67→~95 行） | DO-004 |
| `monitoring/grafana/dashboards/whatsapp-platform-overview.json` | 修改（追加面板） | DO-005 |
| `app/services/worker_health.py` | 新增 | DO-006 |
| `app/api/routes/worker_health.py` | 新增 | DO-006 |
| `app/worker.py` | 修改（写状态） | DO-006 |
| `app/main.py` | 修改（注册路由） | DO-006 |
| `docker-compose.yml` | 修改（worker healthcheck） | DO-006 |
| `scripts/backup-redis.ps1` | 新增 | DO-007 |
| `docs/deployment-checklist.md` | 修改 | DO-008 |
| `docs/recovery-runbook.md` | 修改 | DO-008 |
