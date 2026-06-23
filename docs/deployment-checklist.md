# Deployment Checklist

## Scope

This checklist is the current minimum deployment gate for the local-first phase before full Meta production credentials are wired in.

It covers:

- environment readiness
- CI verification
- Docker Compose rollout
- monitoring validation
- rollback and recovery references

## Pre-Deploy

1. Confirm `.env` contains the intended deployment values.
2. Confirm PostgreSQL and Redis volume strategy is understood.
3. Confirm the latest database migration is included:

```powershell
.venv\Scripts\python -m alembic upgrade head
```

4. Run the local verification bundle:

```powershell
.\scripts\verify-ci.ps1
```

5. Run the launch readiness probe:

```powershell
.\scripts\check-launch-readiness.ps1
```

For multi-account rollout, run the scoped probe for each target account before formal activation:

```powershell
.\scripts\check-launch-readiness.ps1 -AccountId demo-account-cn -ShowChecks
```

If you want the probe to fail on residual warnings such as pending provider status buffer events, use:

```powershell
.\scripts\check-launch-readiness.ps1 -FailOnWarnings
```

The launch readiness probe now also prints:

- the oldest pending provider status event
- the account ranking for pending provider status events

Use that output to decide which account and message scope should be replayed or investigated first before formal activation.

## Required Environment Checks

Before rollout, verify at minimum:

- `DATABASE_URL`
- `REDIS_URL`
- `QUEUE_REDIS_URL`
- `MESSAGING_PROVIDER`
- `AI_PROVIDER`
- `OPENAI_API_KEY` when using OpenAI
- `DEEPSEEK_API_KEY` when using DeepSeek
- `TRANSLATION_PROVIDER`
- `LIVE_TRANSLATION_ENABLED`
- `CONSOLE_LANGUAGE`
- `AUTO_TRANSLATE_ON_HUMAN_HANDOVER`
- `AUTO_TRANSLATE_ON_CONVERSATION_OPEN`
- `AUTO_TRANSLATE_OPERATOR_OUTBOUND`

Translation notes for the current product strategy:

- leave `TRANSLATION_PROVIDER` empty to follow `AI_PROVIDER`, or set it explicitly to `openai` / `deepseek`
- keep `AUTO_TRANSLATE_ON_HUMAN_HANDOVER=false` and `AUTO_TRANSLATE_ON_CONVERSATION_OPEN=false` unless operator workflows require automatic assist translation
- `AUTO_TRANSLATE_OPERATOR_OUTBOUND=true` is the default assistive path for human replies in Chinese

If real WhatsApp rollout is enabled later, also verify:

- the persisted Meta account registry contains the target `Business Portfolio`, `WABA`, `Phone Number`, and webhook subscription rows
- scoped webhook verify / receive paths are reachable for each active WABA
- `META_WEBHOOK_SUBSCRIBED_FIELDS` matches the fields expected by the current rollout
- the following `WA_*` variables are treated only as legacy single-account fallback for non-formal or compatibility flows:
- `WA_ACCESS_TOKEN`
- `WA_VERIFY_TOKEN`
- `WA_APP_SECRET`
- `WA_PHONE_ID`
- `WA_BUSINESS_ACCOUNT_ID`

The webhook subscribed fields should include at least:

- `messages`
- `message_template_status_update`
- `message_template_quality_update`
- `phone_number_quality_update`
- `phone_number_name_update`
- `phone_number_status_update`

## Compose Rollout

Start or update the stack:

```powershell
docker compose up -d --build
```

Confirm containers:

```powershell
docker compose ps
```

## Post-Deploy Validation

Validate core endpoints:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8000/metrics
Invoke-WebRequest http://127.0.0.1:8000/api/metrics/summary
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/launch-readiness
Invoke-WebRequest http://127.0.0.1:8000/api/worker/health
Invoke-WebRequest "http://127.0.0.1:8000/api/runtime/launch-readiness?account_id=demo-account-cn"
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/provider-status-buffer?limit=20
Invoke-WebRequest http://127.0.0.1:9090/-/ready
Invoke-WebRequest http://127.0.0.1:9093/-/ready
Invoke-WebRequest http://127.0.0.1:3000/api/health
```

The readiness endpoint should report `blocker_count = 0` before formal rollout.
The provider status buffer should not retain unexplained pending events before formal activation, especially in WhatsApp mode.
When pending provider status events exist, use the probe output to confirm the oldest pending event and the highest-pending accounts are being actively drained.

Then validate in the frontend console:

1. Monitoring page loads and shows metrics summary.
2. Conversations page loads and can list existing conversations.
3. Meta accounts page loads.
4. Template page loads and can show send logs.
5. Recent audit logs are visible.

## Rollback

Current rollback path:

1. Stop traffic or pause operators if needed.
2. Restore PostgreSQL using [recovery-runbook.md](/C:/Users/ZhuanZ1/Documents/WhatsApp api/docs/recovery-runbook.md).
3. Re-run `docker compose up -d`.
4. Re-validate health, metrics, and frontend console pages.

For now, Redis queue state is treated as rebuildable and is not the primary rollback asset.
