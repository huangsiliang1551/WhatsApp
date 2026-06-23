# PostgreSQL + Redis 优化任务（DBOPT-001 ~ DBOPT-004）

> **执行角色**: deploy_agent + testing_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-13
> **总架构师签发**
> **目标**: 优化数据库和缓存配置，修复参数错误，提升查询性能和运行安全性

---

## 背景

诊断发现 5 个 🔴 P0 问题和 5 个 🟡 P1 问题：

**P0**:
- Redis `maxmemory=0`（无限制，可能 OOM 宿主机）
- Redis `maxmemory-policy=noeviction`（满时拒绝写入）
- PG `effective_cache_size=4GB`（容器仅 256MB，导致查询规划错误）
- PG `random_page_cost=4`（机械硬盘默认值，SSD 应为 1.1）
- PG `effective_io_concurrency=1`（SSD 应为 200）

**P1**:
- PG `max_connections=100`（实际只需 30，每连接浪费 ~10MB）
- PG `work_mem=4MB` / `wal_buffers=4MB`（偏低）
- PG 慢查询日志未启用（`log_min_duration_statement=-1`）
- App 连接池 pool_size=10 + overflow=20 与 max_connections=30 不匹配
- Redis `timeout=0`（客户端永不超时，可能积累僵尸连接）

---

## DBOPT-001：PostgreSQL 参数优化（P0）

- **估计耗时**: 15 分钟

### 修改 `docker-compose.yml` 的 postgres 服务

在 `command` 字段添加优化参数（如果没有 command 字段则新增）：

```yaml
postgres:
  image: postgres:16
  # ... 保留现有配置 ...
  command: >
    postgres
    -c shared_buffers=128MB
    -c random_page_cost=1.1
    -c effective_io_concurrency=200
    -c effective_cache_size=192MB
    -c max_connections=30
    -c work_mem=8MB
    -c wal_buffers=16MB
    -c log_min_duration_statement=1000
    -c log_lock_waits=on
    -c log_connections=on
    -c log_temp_files=0
```

### 参数说明

| 参数 | 改前 | 改后 | 理由 |
|------|------|------|------|
| `random_page_cost` | 4 | **1.1** | SSD 环境索引扫描成本修正 |
| `effective_io_concurrency` | 1 | **200** | SSD 并发 I/O 能力提升 |
| `effective_cache_size` | 4GB | **192MB** | 容器 256MB，取 75% |
| `max_connections` | 100 | **30** | App pool=5×2+overflow=10×2=30 |
| `work_mem` | 4MB | **8MB** | 复杂排序/JOIN 性能 |
| `wal_buffers` | 4MB | **16MB** | WAL 写入效率 |
| `log_min_duration_statement` | -1 | **1000** | 记录 >1s 的慢查询 |
| `log_lock_waits` | off | **on** | 锁等待可追踪 |
| `log_connections` | off | **on** | 连接事件可追踪 |
| `log_temp_files` | -1 | **0** | 记录所有临时文件使用 |

### 验收标准

1. `docker compose up -d postgres` 成功启动
2. `SHOW random_page_cost` = 1.1
3. `SHOW effective_cache_size` = 192MB
4. `SHOW max_connections` = 30
5. `SHOW log_min_duration_statement` = 1s
6. App 和 Worker 服务健康连接

---

## DBOPT-002：Redis 参数优化（P0）

- **估计耗时**: 10 分钟

### 修改 `docker-compose.yml` 的 redis 服务

将现有 `command` 替换为：

```yaml
redis:
  image: redis:7-alpine
  # ... 保留现有配置 ...
  command: >
    redis-server
    --appendonly yes
    --maxmemory 48mb
    --maxmemory-policy allkeys-lru
    --timeout 300
    --tcp-keepalive 300
    --save 3600 1
    --save 300 100
```

### 参数说明

| 参数 | 改前 | 改后 | 理由 |
|------|------|------|------|
| `maxmemory` | 0 (无限制) | **48mb** | 容器 64MB，留 16MB 给系统 |
| `maxmemory-policy` | noeviction | **allkeys-lru** | 内存满时淘汰最久未使用的键 |
| `timeout` | 0 (永不超时) | **300** | 5 分钟无活动断开，防僵尸连接 |
| `appendonly` | yes | yes | 保持 AOF 持久化 |
| `tcp-keepalive` | 300 | 300 | 保持 |
| `save` | 3600 1 300 100 60 10000 | 3600 1 300 100 | 移除过于频繁的 60s/10000 规则 |

### 验收标准

1. `docker compose up -d redis` 成功启动
2. `redis-cli CONFIG GET maxmemory` → 50331648 (48MB)
3. `redis-cli CONFIG GET maxmemory-policy` → allkeys-lru
4. `redis-cli CONFIG GET timeout` → 300
5. `redis-cli DBSIZE` 正常
6. App 和 Worker 服务健康连接

---

## DBOPT-003：App 连接池优化（P1）

- **估计耗时**: 10 分钟

### 修改 `app/core/settings.py`

```python
# 改动前:
db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")

# 改动后:
db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
```

### 理由

- `max_connections=30`（DBOPT-001 设置）
- App 服务: pool_size=5 + overflow=10 = 最多 15 连接
- Worker 服务: pool_size=5 + overflow=10 = 最多 15 连接
- 总计: 30 = max_connections ✅

### 同时更新 `.env.example`

```
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
```

### 验收标准

1. App 服务正常启动
2. Worker 服务正常启动
3. API 端点响应正常
4. 无连接池耗尽错误

---

## DBOPT-004：全量验证 + 手动 VACUUM（P0）

- **估计耗时**: 15 分钟

### 4.1 重启所有受影响服务

```powershell
cd E:\codex\WhatsApp
docker compose up -d postgres redis app worker
```

等待 20 秒让服务启动。

### 4.2 PostgreSQL 验证

```powershell
# 参数验证
docker exec whatsapp_postgres psql -U whatsapp_user -d whatsapp_bot -c "
  SHOW random_page_cost;
  SHOW effective_io_concurrency;
  SHOW effective_cache_size;
  SHOW max_connections;
  SHOW work_mem;
  SHOW wal_buffers;
  SHOW log_min_duration_statement;
  SHOW log_lock_waits;
"

# 手动 VACUUM ANALYZE（更新统计信息）
docker exec whatsapp_postgres psql -U whatsapp_user -d whatsapp_bot -c "VACUUM ANALYZE;"
```

### 4.3 Redis 验证

```powershell
docker exec whatsapp_redis redis-cli CONFIG GET maxmemory
docker exec whatsapp_redis redis-cli CONFIG GET maxmemory-policy
docker exec whatsapp_redis redis-cli CONFIG GET timeout
docker exec whatsapp_redis redis-cli PING
```

### 4.4 服务健康验证

```powershell
# 所有容器 healthy
docker ps --format "table {{.Names}}\t{{.Status}}" | Select-String "whatsapp"

# API 可用
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# 数据库连接正常
Invoke-WebRequest -Uri "http://localhost:8000/api/conversations" -Headers @{"X-Actor-Id"="admin"; "X-Actor-Role"="super_admin"} -UseBasicParsing
```

### 最终验收清单

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | PG random_page_cost | 1.1 |
| 2 | PG effective_cache_size | 192MB |
| 3 | PG max_connections | 30 |
| 4 | PG slow query log | 1000ms |
| 5 | Redis maxmemory | 48mb (50331648) |
| 6 | Redis maxmemory-policy | allkeys-lru |
| 7 | Redis timeout | 300 |
| 8 | 7 服务 healthy | 全部 |
| 9 | /health 200 | ✅ |
| 10 | /api/conversations 200 | ✅ |
| 11 | VACUUM ANALYZE 成功 | 无错误 |
| 12 | App 连接池 | pool_size=5, overflow=10 |

---

## 全局约束

1. **不碰前端代码**
2. **不碰 H5 相关**
3. **保留现有 volume 数据**（不能删 postgres_data / redis_data）
4. **docker-compose.yml 改动最小化**（仅修改 command / 新增参数）
5. **一次性执行全部任务，不中途暂停**
