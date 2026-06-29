# Recovery Runbook

## Post-Restore Validation

Run the scoped readiness probes again after restoring data or services:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/launch-readiness
Invoke-WebRequest http://127.0.0.1:8000/api/runtime/provider-status-buffer?limit=20
.\scripts\check-launch-readiness.ps1 -ShowChecks
```

Do not reopen traffic until the readiness and provider-status checks are clean.
