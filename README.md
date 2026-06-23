# WhatsApp Support Platform Skeleton

This repository is currently in the "build without Meta credentials first" stage. The system is designed around FastAPI, React, multi-account WhatsApp models, provider abstractions, AI/human handover, and Docker Compose.

## Current Scope

- Backend: FastAPI
- Frontend: React + Vite + TypeScript
- Database: SQLAlchemy + Alembic
- Queue: Redis runtime backend, in-memory backend in test mode
- AI: OpenAI primary, DeepSeek compatible fallback, mock provider in test mode
- Messaging: `MessagingProvider` abstraction with `MockMessagingProvider` and `WhatsAppProvider` skeleton
- Runtime model: multi-account, multi-WABA, multi-phone-number, conversation-level handover and AI controls

## Local Setup

### Backend

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .[dev]
Copy-Item .env.example .env
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

### Worker

```powershell
.venv\Scripts\python -m app.worker
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

### Docker Compose

```powershell
docker compose up --build
```

Detached mode:

```powershell
docker compose up -d --build
```

Docker Desktop preflight:

```powershell
.\scripts\check-docker-desktop.ps1
```

Current services:

- `postgres`
- `redis`
- `app`
- `frontend`
- `worker`
- `prometheus`
- `alertmanager`
- `grafana`

Compose URLs after startup:

- Admin / fixed H5 SPA: `http://127.0.0.1:5173`
- Fixed H5 login preview example: `http://127.0.0.1:5173/h5/login?site_key=mall-cn`
- Backend API: `http://127.0.0.1:8000`

Local verification bundle:

```powershell
.\scripts\verify-ci.ps1
```

If `docker compose up` is blocked by Desktop / WSL state instead of project config, run:

```powershell
.\scripts\check-docker-desktop.ps1
```

Launch readiness probe:

```powershell
.\scripts\check-launch-readiness.ps1
```

Scoped readiness for a single account:

```powershell
.\scripts\check-launch-readiness.ps1 -AccountId demo-account-cn -ShowChecks
```

Override Alertmanager target if the monitoring stack is exposed on another host or port:

```powershell
.\scripts\check-launch-readiness.ps1 -AlertmanagerUrl http://127.0.0.1:19093
```

## Mock Inbound Flow

Use `POST /dev/mock/inbound-message` to test the main message pipeline before real Meta credentials are available.

PowerShell example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/dev/mock/inbound-message `
  -ContentType 'application/json' `
  -Body '{
    "account_id": "mock-account-1",
    "conversation_id": "conv-1",
    "user_id": "user-1",
    "text": "hello from mock",
    "mode": "ai"
  }'
```

Current behavior:

- `mode=echo` replies immediately
- `mode=ai` can resolve FAQ, support knowledge, order lookup, and tracking lookup through rules before LLM
- `mode=ai` queues async AI generation when automation is effectively enabled
- strong human-handover intent suppresses AI auto-reply
- account, conversation, and handover controls are respected before AI sends anything

Translation assist defaults:

- inbound messages keep original text first; AI-managed conversations do not auto-translate for display
- conversation view translation is only generated on demand or when explicit human-side flags are enabled
- operator outbound translation remains available for Chinese-to-customer replies
- translation failures degrade to original text and do not block the main message chain

## Key API

### Health and Metrics

- `GET /health`
- `GET /metrics`
- `GET /api/metrics/summary`
- `GET /api/runtime/launch-readiness`
- `GET /api/runtime/launch-readiness?account_id={account_id}`

All HTTP responses include `X-Request-ID`. Error responses also include `request_id` in the JSON body.

### Runtime, AI Toggles, and Handover

- `GET /api/runtime/state`
- `GET /api/runtime/audit-logs`
- `GET /api/runtime/accounts`
- `POST /api/runtime/accounts`
- `POST /api/runtime/ai/global`
- `POST /api/runtime/accounts/{account_id}/ai`
- `POST /api/runtime/conversations/{conversation_id}/ai?account_id={account_id}`
- `POST /api/runtime/conversations/{conversation_id}/handover?account_id={account_id}`
- `GET /api/runtime/agents`
- `POST /api/runtime/agents`
- `POST /api/runtime/agents/{agent_id}/status`

### Conversations

- `GET /api/conversations`
- `GET /api/conversations/{account_id}/{conversation_id}/messages`
- `GET /api/conversations/{account_id}/{conversation_id}/timeline`
- `POST /api/conversations/{account_id}/{conversation_id}/messages/outbound`
- `POST /api/conversations/{account_id}/{conversation_id}/assignment`
- `POST /api/conversations/{account_id}/{conversation_id}/close`

### Meta Account Skeleton

- `GET /api/meta/accounts`
- `POST /api/meta/accounts/manual`
- `POST /api/meta/accounts/embedded-signup/session`
- `GET /api/meta/accounts/embedded-signup/sessions`
- `POST /api/meta/accounts/embedded-signup/session/{session_id}/complete`
- `POST /api/meta/accounts/embedded-signup/session/{session_id}/fail`
- `GET /api/meta/accounts/{account_id}/phone-numbers`
- `GET /api/meta/accounts/{account_id}/wabas/{waba_id}/phone-numbers`
- `POST /api/meta/accounts/{account_id}/wabas/{waba_id}/webhook-subscription`

### WhatsApp Webhook Skeleton

- `POST /webhooks/whatsapp`
- `GET /webhooks/whatsapp/{account_id}/wabas/{waba_id}`
- `POST /webhooks/whatsapp/{account_id}/wabas/{waba_id}`

Current webhook behavior:

- official root webhook POST resolves the internal account from payload `entry.id` (WABA ID)
- scoped webhook paths remain available for local verification and compatibility
- verify token challenge validation
- optional signature verification through `X-Hub-Signature-256`
- inbound message normalization
- status callback normalization for `sent`, `delivered`, `read`, and `failed` style events
- matched provider status callbacks update `message_events` and template send logs
- default WABA subscription fields are configured by `META_WEBHOOK_SUBSCRIBED_FIELDS`
- current defaults cover `messages`, template status/quality updates, and phone-number quality/name/status updates

### Templates

- `GET /api/templates?account_id=&status=&language=`
- `POST /api/templates/drafts`
- `POST /api/templates/{template_id}/status`
- `GET /api/templates/send-logs?account_id=&conversation_id=&limit=`
- `POST /api/templates/{template_id}/send`

Current template behavior:

- preserves `account_id`, `waba_id`, `template_name`, `language`, `category`, and `components`
- supports local `submit` / `sync` lifecycle skeleton before full Meta review integration
- send path goes through `MessagingProvider`
- variables, rendered text, provider result, and provider message ID are persisted
- `template_send_logs` track delivery lifecycle and can be updated by WhatsApp webhook status callbacks

### Queue and Worker

- `GET /api/queue/stats`
- worker entrypoint: `python -m app.worker`

Current worker behavior:

- jobs first recheck rule router matches
- AI replies also send through `MessagingProvider`
- provider failures degrade to translated fallback replies
- queue stats expose queued, processing, completed, failed, retried, and recent failed jobs

### Mock Ecommerce API

Minimal ecommerce scope is intentionally frozen behind the abstraction layer.

- `GET /api/ecommerce/orders?account_id=...`
- `GET /api/ecommerce/orders/{order_id}?account_id=...`
- `GET /api/ecommerce/shipments/{tracking_number}?account_id=...`

## Monitoring

### Prometheus

- URL: `http://127.0.0.1:9090`
- scrape config: [monitoring/prometheus/prometheus.yml](/C:/Users/ZhuanZ1/Documents/WhatsApp api/monitoring/prometheus/prometheus.yml)
- alert rules: [monitoring/prometheus/alerts.yml](/C:/Users/ZhuanZ1/Documents/WhatsApp api/monitoring/prometheus/alerts.yml)

### Alertmanager

- URL: `http://127.0.0.1:9093`
- config: [monitoring/alertmanager/alertmanager.yml](/C:/Users/ZhuanZ1/Documents/WhatsApp api/monitoring/alertmanager/alertmanager.yml)
- current mode: local null receiver placeholder, used to keep the Prometheus alert delivery path valid before real Slack / WeCom / DingTalk wiring

Current alert skeleton:

- `WhatsAppAppDown`
- `AIQueueBacklogHigh`
- `AIQueueFailuresPresent`
- `ProviderStatusBufferStuck`

### Grafana

- URL: `http://127.0.0.1:3000`
- default login: `${GRAFANA_ADMIN_USER:-admin}` / `${GRAFANA_ADMIN_PASSWORD:-admin}`
- datasource provisioning: [monitoring/grafana/provisioning/datasources/prometheus.yml](/C:/Users/ZhuanZ1/Documents/WhatsApp api/monitoring/grafana/provisioning/datasources/prometheus.yml)
- dashboard provisioning: [monitoring/grafana/provisioning/dashboards/dashboards.yml](/C:/Users/ZhuanZ1/Documents/WhatsApp api/monitoring/grafana/provisioning/dashboards/dashboards.yml)
- dashboard JSON: [monitoring/grafana/dashboards/whatsapp-platform-overview.json](/C:/Users/ZhuanZ1/Documents/WhatsApp api/monitoring/grafana/dashboards/whatsapp-platform-overview.json)

Initial dashboard focus:

- app health
- AI queue backlog and failed jobs
- inbound / outbound business outcomes
- AI success, routed, and fallback outcomes
- template sends, failures, and delivery events
- translation outcomes and fallback visibility
- WhatsApp webhook inbound throughput, status callbacks, and signature failures

Verify the monitoring stack:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/metrics
Invoke-WebRequest http://127.0.0.1:9090/-/ready
Invoke-WebRequest http://127.0.0.1:9093/-/ready
Invoke-WebRequest http://127.0.0.1:3000/api/health
```

## Backup and Recovery

- backup script: [scripts/backup-postgres.ps1](/C:/Users/ZhuanZ1/Documents/WhatsApp api/scripts/backup-postgres.ps1)
- restore script: [scripts/restore-postgres.ps1](/C:/Users/ZhuanZ1/Documents/WhatsApp api/scripts/restore-postgres.ps1)
- recovery runbook: [docs/recovery-runbook.md](/C:/Users/ZhuanZ1/Documents/WhatsApp api/docs/recovery-runbook.md)
- deployment checklist: [docs/deployment-checklist.md](/C:/Users/ZhuanZ1/Documents/WhatsApp api/docs/deployment-checklist.md)

Create a PostgreSQL backup:

```powershell
.\scripts\backup-postgres.ps1
```

Restore from a backup directory:

```powershell
.\scripts\restore-postgres.ps1 -BackupDir .\backups\postgres-20260607-020000
```

Current recovery position:

- PostgreSQL is the primary recovery asset
- Redis queue state is treated as rebuildable for now
- post-restore validation should include `/health`, `/metrics`, Prometheus, Grafana, and frontend console checks

## CI

- GitHub Actions workflow: [.github/workflows/ci.yml](/C:/Users/ZhuanZ1/Documents/WhatsApp api/.github/workflows/ci.yml)

Current CI gates:

- backend `pytest`
- frontend `npm ci && npm run build`
- `docker compose config`
- Grafana dashboard JSON validation
- PowerShell deployment script syntax validation

## Testing

Run the full suite:

```powershell
.venv\Scripts\python -m pytest
```

Focused examples:

```powershell
.venv\Scripts\python -m pytest tests\test_whatsapp_webhooks.py tests\test_templates.py
.venv\Scripts\python -m pytest tests\test_queue_runtime.py tests\test_worker.py
.venv\Scripts\python -m pytest tests\test_ecommerce.py tests\test_ecommerce_contract.py
```

Current test coverage includes:

- mock inbound pipeline
- AI queueing and worker processing
- WhatsApp webhook verify, inbound normalization, and status callbacks
- multi-account Meta account registry
- handover authorization and manual reply controls
- template draft, send, and send-log lifecycle
- monitoring-safe queue statistics

## Current Limits

- Real WhatsApp Business API credentials are still missing
- PyWa is not yet wired into the production provider
- real Meta template review and sync are not implemented yet
- the worker currently handles only the `ai_generation` queue
- permissions and role models are still reserved as interface positions rather than a complete auth system
