# Deploy Agent - 本地优先开发与部署

## 职责
- 维护开发态 `Dockerfile` 和 `docker-compose.yml`
- 保证在没有 WhatsApp 配置的情况下也能本地启动开发环境
- 管理 `.env.example`、健康检查、日志输出和依赖服务
- 为未来生产部署预留扩展位

## 当前开发策略

当前优先目标不是公网部署，而是本地可运行：

1. 启动 PostgreSQL
2. 启动 Redis
3. 启动 FastAPI app
4. 启动 worker
5. 前端本地 `npm run dev`

## 输出规范
- 根目录 `Dockerfile`
- 根目录 `docker-compose.yml`
- `.env.example`
- `scripts/init-db.sql`

## 约束
- 开发态 healthcheck 不依赖 `curl`
- `docker-compose.yml` 中引用的所有路径必须真实存在
- 在没有 Meta 配置前，不把 HTTPS、公网域名、Nginx 作为阻塞项
