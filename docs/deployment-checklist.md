# Deployment Checklist

## Preflight

```powershell
.\scripts\verify-ci.ps1
.\scripts\check-launch-readiness.ps1
.\scripts\check-launch-readiness.ps1 -AccountId demo-account-cn -ShowChecks
.\scripts\check-launch-readiness.ps1 -FailOnWarnings
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/launch-readiness
Invoke-WebRequest "http://127.0.0.1:8000/api/runtime/launch-readiness?account_id=demo-account-cn"
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/provider-status-buffer?limit=20
Invoke-WebRequest http://127.0.0.1:9093/-/ready
```

## Release Gate

- Confirm `blocker_count = 0` before switching traffic.
- If validation fails, follow `recovery-runbook.md` before retrying deployment.
