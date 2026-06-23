# Recovery Runbook

## Scope

This runbook covers the minimum recovery workflow currently supported in the local-first phase:

- PostgreSQL backup
- PostgreSQL restore
- Redis recovery guidance for queue state
- Monitoring checks after recovery

The system is intentionally designed so Redis queue state is rebuildable. PostgreSQL remains the primary recovery asset for conversations, messages, templates, audits, and Meta account records.

## PostgreSQL Backup

Create a backup from the running Docker container:

```powershell
.\scripts\backup-postgres.ps1
```

Optional parameters:

```powershell
.\scripts\backup-postgres.ps1 -OutputDir .\backups -ContainerName whatsapp_postgres -DatabaseName whatsapp_bot -DatabaseUser whatsapp_user
```

Expected result:

- a new timestamped directory under `.\backups`
- `postgres.dump`
- `manifest.json`

## Redis Backup

Create a backup from the running Redis container:

```powershell
.\scripts\backup-redis.ps1
```

Optional parameters:

```powershell
.\scripts\backup-redis.ps1 -OutputDir .\backups -ContainerName whatsapp_redis
```

Expected result:

- a new timestamped directory under `.\backups`
- `redis.rdb`
- `manifest.json`

Redis backup performs:

1. `redis-cli BGSAVE` to trigger asynchronous RDB snapshot
2. Wait for `rdb_bgsave_in_progress` to become 0
3. `docker cp` the RDB file from the container

Note: Redis queue state is rebuildable and PostgreSQL remains the primary recovery asset.

## PostgreSQL Restore

Restore a previously created backup:

```powershell
.\scripts\restore-postgres.ps1 -BackupDir .\backups\postgres-20260607-020000
```

Non-interactive restore:

```powershell
.\scripts\restore-postgres.ps1 -BackupDir .\backups\postgres-20260607-020000 -Force
```

The restore script runs:

- `docker cp` to copy the archive into the PostgreSQL container
- `pg_restore --clean --if-exists --no-owner --no-privileges`

## Redis Guidance

Redis currently serves queue and transient runtime support functions.

Current guidance:

- do not overwrite a live Redis volume with ad-hoc file copies while the container is running
- if Redis data is lost, the primary business data in PostgreSQL remains intact
- queue jobs can be rebuilt from new inbound traffic or re-triggered manually during operations review

### Redis Restore

To restore from a Redis RDB backup:

```powershell
# 1. Stop the Redis container
docker compose stop redis

# 2. Identify the backup RDB file
$backupDir = ".\backups\redis-20260612-120000"

# 3. Create a temporary restore container
#    Mount the backup RDB file and a fresh data volume
docker run --rm -v redis_data:/restore-target -v "${PWD}\${backupDir}:/backup:ro" alpine sh -c "
  cp /backup/redis.rdb /restore-target/dump.rdb
"

# 4. Restart Redis
docker compose up -d redis
```

Or for a full volume swap approach:

```powershell
# Stop the stack
docker compose down
# Create a new volume from backup
docker volume rm whatsapp_redis_data_backup 2>$null
docker run --rm -v redis_data:/source -v whatsapp_redis_data_backup:/dest alpine sh -c "cp -a /source/. /dest/"
docker run --rm -v whatsapp_redis_data_backup:/data -v "${PWD}\backups\redis-20260612-120000:/backup:ro" alpine sh -c "cp /backup/redis.rdb /data/dump.rdb"
# Update docker-compose.yml to use whatsapp_redis_data_backup instead of redis_data
# Then start the stack
docker compose up -d
```

## Recovery Validation

After PostgreSQL restore, run:

```powershell
docker compose up -d
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/metrics
Invoke-WebRequest http://127.0.0.1:8000/api/worker/health
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/launch-readiness
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/provider-status-buffer?limit=20
Invoke-WebRequest http://127.0.0.1:9090/-/ready
Invoke-WebRequest http://127.0.0.1:9093/-/ready
Invoke-WebRequest http://127.0.0.1:3000/api/health
```

Then run the rollout probe again so recovery validation uses the same gate as formal activation:

```powershell
.\scripts\check-launch-readiness.ps1 -ShowChecks
```

Then validate in the web console:

- monitoring page loads
- conversations page loads
- template page loads
- Meta accounts page loads
- recent audit logs are visible

## Recovery Checklist

1. Confirm Docker containers are healthy.
2. Restore PostgreSQL from the latest valid backup.
3. Restore Redis RDB if queue state recovery is required.
4. Re-run `docker compose up -d` if services were restarted.
5. Verify `/health`, `/metrics`, `/api/worker/health`, `/api/runtime/launch-readiness`, `/api/runtime/provider-status-buffer`, Prometheus, and Grafana.
6. Check recent audit logs and conversation listing in the frontend.
7. Re-enable manual operations only after these checks pass.

## Worker Failure Recovery

If the worker container is unhealthy or crashing:

1. Check worker logs:

```powershell
docker compose logs worker --tail=50
```

2. Check worker health endpoint:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/worker/health
```

A stale heartbeat (over 60 seconds) indicates the worker process is not updating its health status.

3. Restart the worker:

```powershell
docker compose restart worker
```

4. Verify worker health returns `healthy` status:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/worker/health | ConvertFrom-Json | Format-List
```

5. If the worker repeatedly fails, check for:
   - Database connectivity issues
   - Redis connectivity issues
   - AI provider API failures causing consecutive job failures (worker auto-pauses after 10 consecutive failures)

6. To manually resume a paused worker, restart the container:

```powershell
docker compose restart worker
```
