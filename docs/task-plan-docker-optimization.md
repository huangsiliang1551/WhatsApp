# Docker 资源优化任务清单

> **执行角色**: deploy_agent + queue_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-12
> **总架构师签发**

---

## 0. 问题诊断数据

### docker stats 实测

| 容器 | CPU% | 内存 | 状态 |
|------|------|------|------|
| whatsapp_app | **10.09%** | **305.8 MiB** | 主要问题 |
| whatsapp_worker | 0.00% | 80.82 MiB | 空转浪费 |
| whatsapp_postgres | 0.00% | 49.84 MiB | 正常 |
| whatsapp_grafana | 0.05% | 44.47 MiB | 正常 |
| whatsapp_prometheus | 0.00% | 23.72 MiB | 正常 |
| whatsapp_redis | 0.27% | 6.20 MiB | 正常 |
| whatsapp_alertmanager | 0.07% | 14.71 MiB | 正常 |

### 项目文件分布（总计 110,033 文件）

| 目录 | 文件数 | 说明 |
|------|--------|------|
| frontend/ | 56,589 | 含 node_modules |
| .python/ | 24,344 | 完整 Python 发行版 |
| .venv_backup_* | 7,149 | 旧 venv 备份 |
| .venv/ | 7,021 | 当前 venv |
| .venv_rebuild_backup_* | 7,021 | 重建备份 |
| .venv_system_base_backup_* | 6,986 | 系统基准备份 |
| storage/ | 243 | task-proofs |
| 业务代码 | ~700 | app + tests + alembic |

### 根因定位

1. **CPU 10%+**：`docker-compose.yml` 第 56 行 `uvicorn --reload` + volume mount `.:/workspace` → uvicorn watchdog 监控 11 万文件变更
2. **内存 305 MiB**：`.dockerignore` 仅 7 行，缺失对 .python/、.venv_backup_*、frontend/ 等排除 → `COPY . /workspace` 打入 ~10 万无用文件
3. **Worker 80 MiB 空转**：`app/worker.py` 第 55 行 `asyncio.sleep(0.05)` → 每秒 20 次无意义 Redis 轮询
4. **无资源上限**：docker-compose.yml 未设 deploy.resources.limits

---

## 1. 执行编排

```
Phase A（3 个任务并行，无依赖）:
  TASK-001 (.dockerignore)  ── deploy_agent
  TASK-002 (worker.py)      ── queue_agent
  TASK-003 (Dockerfile)     ── deploy_agent

Phase B（串行，依赖 Phase A 全部完成）:
  TASK-004 (docker-compose.yml) ── deploy_agent

Phase C（验证，依赖全部修改完成）:
  TASK-005 (端到端验证) ── testing_agent
```

---

## 2. 任务详情

### TASK-001：补全 .dockerignore 排除项

- **角色**: deploy_agent
- **优先级**: P0 / critical
- **前置依赖**: 无
- **估计耗时**: 10 分钟

#### 问题

当前 `.dockerignore` 仅 7 行：

```
.venv
__pycache__
.pytest_cache
frontend/node_modules
frontend/dist
*.pyc
```

缺失排除 ~10 万个非业务文件，导致 `COPY . /workspace` 将 .python/（24,344 文件）、.venv_backup_*（21,156 文件）、storage/、monitoring/ 等全部打入镜像层。

#### 代码修改

**文件**: `E:\codex\WhatsApp\.dockerignore`
**动作**: 替换整个文件内容

新内容：

```dockerignore
# --- Python environments ---
.venv
.venv_backup_*
.venv_rebuild_backup_*
.venv_system_base_backup_*
.python
*.pyc
__pycache__
.pytest_cache
.mypy_cache
*.egg-info
whatsapp_support_platform.egg-info

# --- Test artifacts ---
.tmp_pytest
tests

# --- Frontend (built separately, not needed in backend image) ---
frontend

# --- IDE / editor / agent docs ---
.codex-run
.qoder
agents
.vscode
.idea

# --- Database / storage / monitoring config ---
storage
tmp_restore
tmp_media_debug*.db
*.db

# --- Monitoring stack (uses own images) ---
monitoring

# --- CI / scripts not needed at runtime ---
.github

# --- Docker itself ---
docker-compose.yml
.dockerignore
.env.example
.gitignore
.git
```

注意：**不要**排除 `.env`（容器启动需要）、`scripts/`（alembic 运行可能需要）、`*.md`（README 保留）。

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
docker compose down
docker compose build --no-cache app
docker images whatsapp_app
```

#### 验收标准

1. `.dockerignore` 文件包含对 .python/、.venv_backup_*、.venv_rebuild_backup_*、.venv_system_base_backup_*、.tmp_pytest/、storage/、frontend/、monitoring/、.codex-run/ 的排除规则
2. `docker compose build --no-cache app` 成功无报错
3. 新镜像大小相比旧镜像减少 50% 以上
4. 容器内 `/workspace` 不包含 .python/、.venv_backup_*、frontend/、storage/ 等目录

#### 重试策略

- 最大重试: 3 次
- 失败回滚: 恢复原始 7 行 .dockerignore 内容

#### 交付物

- 修改后的 `.dockerignore` 文件
- 修改前后镜像大小对比

---

### TASK-002：修复 worker.py 50ms 空转轮询

- **角色**: queue_agent
- **优先级**: P0 / critical
- **前置依赖**: 无
- **估计耗时**: 15 分钟

#### 问题

`app/worker.py` 第 51-55 行：

```python
async def run_worker() -> None:
    queue_service = QueueService(get_settings())
    while RUNNING:
        await process_reserved_job("ai_generation", queue_service)
        await asyncio.sleep(0.05)
```

`QueueService.reserve_next_job()` 内部已调用 `self._provider.reserve(timeout_seconds=settings.queue_poll_timeout_seconds)`（默认 5 秒阻塞），外层 `sleep(0.05)` 完全多余。

#### 代码修改

**文件**: `E:\codex\WhatsApp\app\worker.py`
**动作**: 替换第 51-55 行

原始内容：

```python
async def run_worker() -> None:
    queue_service = QueueService(get_settings())
    while RUNNING:
        await process_reserved_job("ai_generation", queue_service)
        await asyncio.sleep(0.05)
```

替换为：

```python
async def run_worker() -> None:
    settings = get_settings()
    queue_service = QueueService(settings)
    idle_backoff = settings.queue_poll_timeout_seconds
    while RUNNING:
        job = await process_reserved_job("ai_generation", queue_service)
        if job is None:
            await asyncio.sleep(idle_backoff)
```

逻辑说明：
- 有任务时（`job is not None`）：立即进入下一轮，零延迟
- 无任务时（`job is None`）：sleep `queue_poll_timeout_seconds`（默认 5 秒），而非 50ms
- `settings` 只获取一次，不每轮调用

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
.\.venv\Scripts\python.exe -m pytest tests\test_worker.py -v --tb=short
```

#### 单元测试

在 `tests/test_worker.py` 中新增测试用例：

测试名: `test_run_worker_uses_idle_backoff_when_no_job`
逻辑: mock `process_reserved_job` 返回 None，验证 `asyncio.sleep` 被调用时参数 >= `queue_poll_timeout_seconds`（默认 5），而非 0.05。

#### 验收标准

1. `run_worker()` 不再使用 `asyncio.sleep(0.05)`
2. 队列为空时 sleep 时长 = `settings.queue_poll_timeout_seconds`（默认 5）
3. 有任务时不额外 sleep，立即进入下一轮
4. 现有 `tests/test_worker.py` 全部通过
5. 新增 idle backoff 测试通过

#### 重试策略

- 最大重试: 3 次
- 失败回滚: 恢复 worker.py 原始内容

#### 交付物

- 修改后的 `app/worker.py`
- 新增测试用例
- pytest 全部通过输出

---

### TASK-003：优化 Dockerfile 构建层

- **角色**: deploy_agent
- **优先级**: P1 / high
- **前置依赖**: 无
- **估计耗时**: 10 分钟

#### 问题

当前 Dockerfile：

```dockerfile
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
WORKDIR /workspace
COPY . /workspace
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --upgrade pip && python -m pip install -e .[dev]
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

问题：
1. `COPY . /workspace` 在 .dockerignore 不全时打入大量无用文件
2. `pip install -e .[dev]` 使用可编辑安装 + dev 依赖，运行环境不需要
3. apt-get 在 COPY 之后，无法利用 Docker 层缓存

#### 代码修改

**文件**: `E:\codex\WhatsApp\Dockerfile`
**动作**: 替换整个文件

新内容：

```dockerfile
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /workspace

# System deps first (stable layer, rarely changes)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Python deps second (changes only when pyproject.toml changes)
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip && \
    python -m pip install .

# Business code last (changes frequently)
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

关键变化：
- apt-get 提前到 COPY 之前（利用层缓存）
- 先 COPY pyproject.toml + pip install（依赖层缓存）
- 再 COPY 业务代码（app/ + alembic/）
- 去掉 `-e`（可编辑模式）和 `[dev]`

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
docker compose build --no-cache app
docker images whatsapp_app
docker run --rm whatsapp-whatsapp_app-1 ls /workspace/
```

#### 验收标准

1. Dockerfile 使用分层 COPY
2. pip install 不使用 `-e` 和 `[dev]`
3. 容器内 /workspace 仅包含 pyproject.toml、alembic.ini、alembic/、app/
4. 容器内不存在 tests/、frontend/、.python/、.venv* 等目录
5. docker build 成功
6. 容器可正常启动

#### 重试策略

- 最大重试: 3 次
- 失败回滚: 恢复原始 Dockerfile

#### 交付物

- 修改后的 Dockerfile
- docker build 成功日志

---

### TASK-004：优化 docker-compose.yml

- **角色**: deploy_agent
- **优先级**: P0 / critical
- **前置依赖**: TASK-001, TASK-003
- **估计耗时**: 15 分钟

#### 问题

1. app 容器 command 用 `--reload` 监控 11 万文件 → CPU 10%+
2. app/worker 的 volume mount `.:/workspace` 挂载整个仓库
3. 所有服务无 deploy.resources.limits

#### 代码修改

**文件**: `E:\codex\WhatsApp\docker-compose.yml`

**修改 1 - app volumes + command（第 52-56 行）**

原始：
```yaml
    volumes:
      - .:/workspace
    ports:
      - "8000:8000"
    command: sh -c "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
```

替换为：
```yaml
    volumes:
      - ./app:/workspace/app
      - ./alembic:/workspace/alembic
      - ./alembic.ini:/workspace/alembic.ini
    ports:
      - "8000:8000"
    command: sh -c "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
```

**修改 2 - worker volumes（第 78-80 行）**

原始：
```yaml
    volumes:
      - .:/workspace
    command: sh -c "python -m app.worker"
```

替换为：
```yaml
    volumes:
      - ./app:/workspace/app
    command: sh -c "python -m app.worker"
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
```

**修改 3 - postgres 添加资源限制**

在 postgres 服务的 healthcheck 段之后添加：
```yaml
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
```

**修改 4 - redis 添加资源限制**

在 redis 服务的 healthcheck 段之后添加：
```yaml
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 64M
```

#### Shell 命令

```powershell
cd E:\codex\WhatsApp
docker compose config --quiet
docker compose down --remove-orphans
docker compose up -d --build
```

#### 验收标准

1. app 容器 command 不包含 `--reload`
2. app volumes 收窄为 ./app、./alembic、./alembic.ini
3. worker volumes 收窄为 ./app
4. app/worker/postgres/redis 均有 deploy.resources.limits
5. `docker compose config` 验证通过
6. `docker compose up -d` 所有服务正常启动

#### 重试策略

- 最大重试: 3 次
- 失败回滚: 恢复原始 docker-compose.yml

#### 交付物

- 修改后的 docker-compose.yml
- docker compose config 验证输出

---

### TASK-005：端到端集成验证

- **角色**: testing_agent
- **优先级**: P0 / critical
- **前置依赖**: TASK-001, TASK-002, TASK-003, TASK-004
- **估计耗时**: 20 分钟

#### 验证步骤

```powershell
cd E:\codex\WhatsApp

# 1. 重建镜像
docker compose down --remove-orphans
docker compose build --no-cache

# 2. 查看镜像大小
docker images | findstr whatsapp

# 3. 启动所有服务
docker compose up -d

# 4. 等待 30 秒后采集资源数据
# (PowerShell: Start-Sleep -Seconds 30)
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 5. 健康检查
docker compose exec app python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read())"

# 6. 验证容器内文件结构
docker compose exec app ls /workspace/
docker compose exec app ls /workspace/app/

# 7. 运行后端测试
.\.venv\Scripts\python.exe -m pytest tests\test_worker.py tests\test_queue_runtime.py tests\test_health.py -v --tb=short
```

#### 验收标准

| 指标 | 优化前 | 目标 |
|------|--------|------|
| whatsapp_app CPU | 10.09% | < 2% |
| whatsapp_app 内存 | 305.8 MiB | < 150 MiB |
| whatsapp_worker CPU | 0% (空转 20次/秒) | ~0% (5秒轮询) |
| 镜像文件数 | ~110,000 | < 1,000 |
| 资源限制 | 无 | 每服务独立上限 |

具体条目：
1. docker compose build 成功
2. 新镜像大小减少 50% 以上
3. 全部 7 个容器启动成功
4. /health 返回 200 OK
5. /metrics 返回 200 OK
6. whatsapp_app CPU < 2%
7. whatsapp_app 内存 < 150 MiB
8. 容器内 /workspace 不包含 .python/、.venv*、frontend/、storage/
9. pytest 全部通过
10. 所有容器未超出资源限制

#### 重试策略

- 最大重试: 3 次
- 失败处理: 分析失败原因 → 定位到具体 TASK → 回滚该 TASK → 重新执行

#### 交付物

- docker stats 优化前后对比表
- pytest 输出日志
- 容器内文件结构验证
- 最终验收报告

---

## 3. 全局约束

- **禁止无限循环**
- 进度文件: `.codex-run/progress/TASK-XXX.json`（每个任务完成后写入）
- 启动时检查进度文件，已完成的任务自动跳过（断点续跑）
- 单次任务执行上限 30 分钟
- 回滚命令: `git checkout -- .dockerignore Dockerfile docker-compose.yml app/worker.py`

---

## 4. 注意事项

1. **Dockerfile `pip install .` 需要 `pyproject.toml` 中 `[tool.setuptools.packages.find]` 配置正确** — 当前已有 `include = ["app*"]`
2. **volume mount 收窄后，Docker 内开发热重载将失效** — 这是预期行为。本地开发直接用 `uvicorn --reload`（不经 Docker）
3. **TASK-002 的 `idle_backoff`** — 使用 `settings.queue_poll_timeout_seconds`（settings.py 第 35 行已有，默认 5 秒）
4. **postgres/redis 资源限制** — 当前为保守上限，生产环境应基于监控数据调整
