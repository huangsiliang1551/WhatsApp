# H5 多租户系统 — 生产部署完整方案（PROD-DEPLOY-FINAL）

> **执行角色**: deploy_agent + api_agent + frontend_agent
> **项目目录**: `E:\codex\WhatsApp`
> **创建时间**: 2026-06-16
> **总架构师签发**
> **目标**: 实现自托管生产环境完整部署，全部能力后台管理

---

## 一、架构决策确认

| 维度 | 决策 |
|------|------|
| 后端服务器 | 1 台（业务量大时扩展） |
| 数据库 | PostgreSQL 单点（无主从） |
| Redis | 单点（无 Sentinel） |
| WAF | Nginx ModSecurity（自托管） |
| 密钥管理 | 后台管理 + DB 加密存储 |
| 错误追踪 | 自建错误日志表 + 后台 UI |
| Uptime 监控 | 后台心跳检测 + 告警 |
| CI/CD | GitHub Actions（免费） |
| 数据保留 | 消息 90 天，日志 90 天 |
| 计费模块 | 不需要 |
| 运维手册 | 不需要 |
| GDPR | 不需要 |

---

## 二、安全加固（PROD-SEC）

### PROD-SEC-001：Nginx ModSecurity WAF

- **估计耗时**: 30 分钟

修改 `scripts/deploy-h5-site.sh`，增加 ModSecurity 安装和配置：

```bash
# 在 "安装依赖" 步骤增加
apt-get install -y libapache2-mod-security2 modsecurity-crs

# 启用 ModSecurity
cp /etc/modsecurity/modsecurity.conf-recommended /etc/modsecurity/modsecurity.conf
sed -i 's/SecRuleEngine DetectionOnly/SecRuleEngine On/' /etc/modsecurity/modsecurity.conf

# 在 Nginx 配置中启用
# 在 server block 中增加：
# modsecurity on;
# modsecurity_rules_file /etc/modsecurity/modsecurity.conf;
```

### PROD-SEC-002：密钥管理服务（后台 UI）

- **估计耗时**: 60 分钟

**新增表：secrets**

```python
# alembic/versions/20260616_0084_secrets.py

class Secret(Base, TimestampMixin):
    __tablename__ = "secrets"
    
    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(100), nullable=False, unique=True)  # "OPENAI_API_KEY"
    encrypted_value = Column(Text, nullable=False)  # Fernet 加密
    description = Column(String(500), nullable=True)
    created_by = Column(String(36), nullable=True)
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
```

**后台 UI**: SettingsPage 新增"密钥管理" Tab
- 列表：名称 / 描述 / 创建时间 / 操作
- 操作：查看（解密显示）/ 编辑 / 删除
- 新增密钥 Modal

### PROD-SEC-003：IP 黑名单管理

- **估计耗时**: 30 分钟

**新增表：ip_blacklist**

```python
# alembic/versions/20260616_0085_ip_blacklist.py

class IPBlacklist(Base, TimestampMixin):
    __tablename__ = "ip_blacklist"
    
    id = Column(String(36), primary_key=True, default=new_id)
    ip_address = Column(String(45), nullable=False, unique=True)
    reason = Column(String(500), nullable=True)
    blocked_until = Column(DateTime(timezone=False), nullable=True)  # null=永久
    created_by = Column(String(36), nullable=True)
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
```

**后台 UI**: SecuritySettingsPage 新增"IP 黑名单" Tab
- 列表：IP / 原因 / 封禁时间 / 操作
- 操作：解封
- 新增 IP Modal

**Nginx 集成**: 定时从 DB 读取黑名单，生成 Nginx deny 配置

### PROD-SEC-004：API 限流

- **估计耗时**: 30 分钟

**Nginx rate limiting 配置**:

```nginx
# /etc/nginx/conf.d/rate-limit.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

# 在 server block 中应用
location /api/ {
    limit_req zone=api_limit burst=50 nodelay;
    # ... proxy 配置
}

location /api/admin/auth/login {
    limit_req zone=login_limit burst=3 nodelay;
    # ... proxy 配置
}
```

---

## 三、自托管监控（PROD-MON）

### PROD-MON-001：错误追踪（前端 JS 错误上报）

- **估计耗时**: 45 分钟

**新增表：client_errors**

```python
# alembic/versions/20260616_0086_client_errors.py

class ClientError(Base):
    __tablename__ = "client_errors"
    
    id = Column(String(36), primary_key=True, default=new_id)
    site_key = Column(String(50), nullable=True)
    error_type = Column(String(50), nullable=False)  # "javascript" / "resource" / "promise"
    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
```

**API**:
```python
# app/api/routes/client_errors.py

@router.post("/client-errors")
async def report_client_error(payload: ClientErrorReportRequest):
    """前端 JS 错误上报"""
    error = ClientError(
        id=str(uuid.uuid4()),
        site_key=payload.site_key,
        error_type=payload.error_type,
        message=payload.message,
        stack_trace=payload.stack_trace,
        url=payload.url,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host,
    )
    session.add(error)
    session.commit()
    return {"status": "ok"}
```

**后台 UI**: MonitoringPage 新增"前端错误" Tab
- 列表：时间 / 站点 / 错误类型 / 消息 / 操作
- 操作：查看详情（stack_trace）

**前端集成**:
```typescript
// frontend/src/utils/errorTracker.ts

window.addEventListener("error", (event) => {
  reportClientError({
    error_type: "javascript",
    message: event.message,
    stack_trace: event.error?.stack,
    url: window.location.href,
  });
});

window.addEventListener("unhandledrejection", (event) => {
  reportClientError({
    error_type: "promise",
    message: event.reason?.message || "Unhandled promise rejection",
    stack_trace: event.reason?.stack,
    url: window.location.href,
  });
});
```

### PROD-MON-002：Uptime 监控（心跳检测）

- **估计耗时**: 45 分钟

**新增表：uptime_checks**

```python
# alembic/versions/20260616_0087_uptime_checks.py

class UptimeCheck(Base, TimestampMixin):
    __tablename__ = "uptime_checks"
    
    id = Column(String(36), primary_key=True, default=new_id)
    site_id = Column(String(36), ForeignKey("h5_sites.id"), nullable=False)
    status = Column(String(20), nullable=False)  # "up" / "down" / "timeout"
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=False), server_default=func.now())
```

**后台服务**:
```python
# app/services/uptime_service.py

class UptimeService:
    async def check_site(self, site: H5Site, config: H5SiteConfig) -> UptimeCheck:
        """检测站点是否在线"""
        import httpx
        import time
        
        start = time.time()
        try:
            resp = await httpx.get(f"https://{config.domain}", timeout=10)
            elapsed = int((time.time() - start) * 1000)
            
            status = "up" if resp.status_code == 200 else "down"
            check = UptimeCheck(
                id=str(uuid.uuid4()),
                site_id=site.id,
                status=status,
                response_time_ms=elapsed,
                status_code=resp.status_code,
            )
        except Exception as e:
            check = UptimeCheck(
                id=str(uuid.uuid4()),
                site_id=site.id,
                status="timeout",
                error_message=str(e),
            )
        
        session.add(check)
        session.commit()
        
        # 如果 down，发送通知
        if check.status != "up":
            self._send_alert(site, check)
        
        return check
```

**定时任务**:
```python
# app/worker.py 增加定时检测

async def uptime_monitor_loop():
    """每 5 分钟检测所有 H5 站点"""
    while True:
        try:
            session = SessionLocal()
            sites = session.scalars(select(H5Site).where(H5Site.status == "active")).all()
            uptime_service = UptimeService(session)
            
            for site in sites:
                config = session.scalar(
                    select(H5SiteConfig).where(H5SiteConfig.site_id == site.id)
                )
                if config and config.domain:
                    await uptime_service.check_site(site, config)
            
            session.close()
        except Exception as e:
            logger.error("uptime_monitor_error", error=str(e))
        
        await asyncio.sleep(300)  # 5 分钟
```

**后台 UI**: MonitoringPage 新增"Uptime 监控" Tab
- 列表：站点 / 状态 / 响应时间 / 最后检测时间
- 状态指示器：🟢 up / 🔴 down / 🟡 timeout

---

## 四、CI/CD（PROD-CICD）

### PROD-CICD-001：GitHub Actions 流水线

- **估计耗时**: 30 分钟

**新增 `.github/workflows/deploy.yml`**:

```yaml
name: Deploy H5 Sites

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
      - 'app/**'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Build Frontend
        run: |
          cd frontend
          npm ci
          npm run build
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'
      
      - name: Install Backend Dependencies
        run: |
          pip install -e .[dev]
      
      - name: Run Tests
        run: |
          pytest tests/ -x
      
      - name: Deploy to Server
        env:
          SSH_PRIVATE_KEY: ${{ secrets.SSH_PRIVATE_KEY }}
          SERVER_HOST: ${{ secrets.SERVER_HOST }}
          SERVER_USER: ${{ secrets.SERVER_USER }}
        run: |
          # 上传前端构建文件
          scp -i $SSH_PRIVATE_KEY -r frontend/dist/* $SERVER_USER@$SERVER_HOST:/var/www/default/
          
          # 重启后端
          ssh -i $SSH_PRIVATE_KEY $SERVER_USER@$SERVER_HOST "cd /opt/whatsapp && docker compose restart app worker"
```

---

## 五、数据保留策略（PROD-DATA）

### PROD-DATA-001：自动归档 + 清理

- **估计耗时**: 45 分钟

**新增服务：data_retention_service.py**

```python
# app/services/data_retention_service.py

class DataRetentionService:
    def __init__(self, session: Session):
        self._session = session

    def cleanup_old_messages(self, days: int = 90) -> int:
        """清理 90 天前的消息"""
        cutoff = datetime.now() - timedelta(days=days)
        
        # 删除消息
        result = self._session.execute(
            delete(Message).where(Message.created_at < cutoff)
        )
        
        # 删除消息事件
        self._session.execute(
            delete(MessageEvent).where(MessageEvent.created_at < cutoff)
        )
        
        self._session.commit()
        return result.rowcount

    def cleanup_old_logs(self, days: int = 90) -> int:
        """清理 90 天前的日志"""
        cutoff = datetime.now() - timedelta(days=days)
        
        # 审计日志
        result1 = self._session.execute(
            delete(AuditLog).where(AuditLog.created_at < cutoff)
        )
        
        # 客户端错误
        result2 = self._session.execute(
            delete(ClientError).where(ClientError.created_at < cutoff)
        )
        
        # Uptime 检查
        result3 = self._session.execute(
            delete(UptimeCheck).where(UptimeCheck.created_at < cutoff)
        )
        
        self._session.commit()
        return result1.rowcount + result2.rowcount + result3.rowcount
```

**定时任务**:
```python
# app/worker.py 增加每日清理

async def data_retention_loop():
    """每天凌晨 3 点清理过期数据"""
    while True:
        now = datetime.now()
        if now.hour == 3 and now.minute == 0:
            try:
                session = SessionLocal()
                retention_service = DataRetentionService(session)
                
                msg_count = retention_service.cleanup_old_messages(days=90)
                log_count = retention_service.cleanup_old_logs(days=90)
                
                logger.info("data_retention_completed", messages=msg_count, logs=log_count)
                session.close()
            except Exception as e:
                logger.error("data_retention_error", error=str(e))
        
        await asyncio.sleep(60)  # 每分钟检查一次
```

---

## 六、任务清单

| 任务 | 文件 | 行数 |
|------|------|------|
| PROD-SEC-001 ModSecurity WAF | scripts/deploy-h5-site.sh 修改 | +20 行 |
| PROD-SEC-002 密钥管理 | 迁移 0084 + service + API + UI | ~200 行 |
| PROD-SEC-003 IP 黑名单 | 迁移 0085 + service + API + UI | ~150 行 |
| PROD-SEC-004 API 限流 | Nginx 配置 | +20 行 |
| PROD-MON-001 错误追踪 | 迁移 0086 + service + API + UI | ~200 行 |
| PROD-MON-002 Uptime 监控 | 迁移 0087 + service + worker + UI | ~250 行 |
| PROD-CICD-001 GitHub Actions | .github/workflows/deploy.yml | ~50 行 |
| PROD-DATA-001 数据保留 | service + worker | ~150 行 |
| **总计** | | ~800 行 |

---

## 发给各 Agent 的文本

### 后端 Agent

```
你是后端开发 Agent（生产部署轮）。请读取 docs/task-plan-prod-deploy-final.md 的 PROD-SEC + PROD-MON + PROD-DATA 部分，一次性实现全部后端任务，不要中途暂停。

核心任务：
1. 安全加固（3 个迁移 + 3 个服务）：
   - 0084 secrets 表 + SecretService（密钥管理）
   - 0085 ip_blacklist 表 + IPBlacklistService
   - 0086 client_errors 表 + ClientErrorService
   - 0087 uptime_checks 表 + UptimeService + worker 定时检测

2. 数据保留（1 个服务）：
   - DataRetentionService（90 天清理消息/日志）+ worker 定时任务

约束：重启 Docker 验证 API。开始吧。
```

### 前端 Agent

```
你是前端 Agent（生产部署轮）。请读取 docs/task-plan-prod-deploy-final.md 的 PROD-SEC + PROD-MON 部分，一次性实现全部前端任务，不要中途暂停。

核心任务：
1. SettingsPage 新增"密钥管理" Tab（CRUD + 查看解密）
2. SecuritySettingsPage 新增"IP 黑名单" Tab（CRUD）
3. MonitoringPage 新增"前端错误" Tab（错误列表 + stack_trace）
4. MonitoringPage 新增"Uptime 监控" Tab（站点状态 + 响应时间）
5. 前端错误追踪集成（window.addEventListener error/unhandledrejection）

约束：不改后端 + 不碰 H5 + npm run build + 一次性完成。开始吧。
```

### 部署 Agent

```
你是部署 Agent（生产部署轮）。请读取 docs/task-plan-prod-deploy-final.md 的 PROD-SEC-001 + PROD-SEC-004 + PROD-CICD-001 部分，一次性实现全部部署脚本，不要中途暂停。

核心任务：
1. 修改 scripts/deploy-h5-site.sh 增加 ModSecurity WAF 安装
2. 修改 scripts/deploy-h5-site.sh 增加 Nginx rate limiting 配置
3. 新增 .github/workflows/deploy.yml（GitHub Actions CI/CD）

约束：Ubuntu/Debian 服务器可执行，一次性完成。开始吧。
```

---

## 总结

| 维度 | 任务数 | 预估行数 |
|------|--------|---------|
| 后端安全+监控+数据保留 | 8 个任务 | ~800 行 |
| 前端 UI（密钥/IP/错误/Uptime） | 5 个任务 | ~400 行 |
| 部署脚本（WAF/限流/CI/CD） | 3 个任务 | ~100 行 |
| **总计** | 16 个任务 | ~1500 行 |

3 份文档可并行发给 3 个 Agent 执行。
