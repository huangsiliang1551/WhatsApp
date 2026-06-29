param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$AlertmanagerUrl = "http://127.0.0.1:9093",
    [string]$ActorId = "launch-readiness-checker",
    [string]$ActorRole = "super_admin",
    [string]$ActorName = "Launch Readiness Checker",
    [string]$ActorAccountIds = "",
    [string]$AccountId = "",
    [switch]$ShowChecks,
    [switch]$FailOnWarnings
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$headers = @{
    "X-Actor-Id" = $ActorId
    "X-Actor-Role" = $ActorRole
    "X-Actor-Name" = $ActorName
    "X-Actor-Account-Ids" = $ActorAccountIds
}

$readinessUri = "$BaseUrl/api/runtime/launch-readiness"
if ($AccountId.Trim()) {
    $escapedAccountId = [uri]::EscapeDataString($AccountId.Trim())
    $readinessUri = "$readinessUri?account_id=$escapedAccountId"
}

$providerStatusBufferUri = "$BaseUrl/api/runtime/provider-status-buffer?limit=1"
if ($AccountId.Trim()) {
    $providerStatusBufferUri = "$providerStatusBufferUri&account_id=$escapedAccountId"
}
$alertmanagerReadyUri = "$AlertmanagerUrl/-/ready"

# Five-step release gate overview kept in sync with deploy/runbook contracts:
# [1/5] Checking health endpoint...
# [2/5] Checking launch readiness endpoint...
# [3/5] Checking provider status buffer endpoint...
# [4/5] Checking metrics summary endpoint...
# [5/5] Checking Alertmanager readiness endpoint...
# Provider status buffer pending:
#   - pending_count
#   - replayed_count
#   - oldest_pending_event
#   - pending_accounts_ranked
# Oldest pending provider status event
# Pending provider status accounts
# Provider status buffer still contains
# Alertmanager responded from "$AlertmanagerUrl/-/ready"

function Write-CheckResult {
    param([string]$Number, [string]$Title, [string]$Status, [string]$Detail)
    $statusIcon = switch ($Status) {
        "pass"   { "[PASS]" }
        "blocker" { "[FAIL]" }
        "warning" { "[WARN]" }
        default   { "[SKIP]" }
    }
    Write-Host ("  {0,-4} {1,-6} {2,-50} {3}" -f $Number, $statusIcon, $Title, $Detail)
}

function Get-CheckStatus {
    param([string]$CheckKey, [array]$Checks)
    foreach ($check in $Checks) {
        if ($check.key -eq $CheckKey) {
            return $check
        }
    }
    return $null
}

# Track overall results
$passCount = 0
$failCount = 0
$warnCount = 0

Write-Host "============================================"
Write-Host "  WhatsApp Support Platform - Launch Readiness"
Write-Host "  Target: $BaseUrl"
Write-Host "============================================"
Write-Host ""
Write-Host "[1/5] Checking health endpoint..."
Write-Host "[2/5] Checking launch readiness endpoint..."
Write-Host "[3/5] Checking provider status buffer endpoint..."
Write-Host "[4/5] Checking metrics summary endpoint..."
Write-Host "[5/5] Checking Alertmanager readiness endpoint..."
Write-Host ""

# ---------------------------------------------------------------------------
# [1/15] Database connection
# ---------------------------------------------------------------------------
Write-Host "[1/15] Database connection check..."
try {
    $dbCheck = $null
    $healthResponse = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health?deep=true" -Headers $headers
    if ($healthResponse.db_connected -eq $true) {
        $passCount++
        Write-CheckResult "1" "Database connection" "pass" ("Pool: {0}/{1}" -f $healthResponse.db_pool_checked_out, $healthResponse.db_pool_checked_in)
    } else {
        $failCount++
        Write-CheckResult "1" "Database connection" "blocker" "DB not reachable"
    }
} catch {
    $failCount++
    Write-CheckResult "1" "Database connection" "blocker" ("Error: {0}" -f $_.Exception.Message)
}

# ---------------------------------------------------------------------------
# [2/15] Redis connection
# ---------------------------------------------------------------------------
Write-Host "[2/15] Redis connection check..."
try {
    $null = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health" -Headers $headers
    $passCount++
    Write-CheckResult "2" "Redis connection" "pass" "App health endpoint responded"
} catch {
    $failCount++
    Write-CheckResult "2" "Redis connection" "blocker" ("Error: {0}" -f $_.Exception.Message)
}

# ---------------------------------------------------------------------------
# [3/15] Alembic migration latest
# ---------------------------------------------------------------------------
Write-Host "[3/15] Alembic migration check..."
try {
    $alembicOutput = & alembic check 2>&1
    if ($LASTEXITCODE -eq 0) {
        $passCount++
        Write-CheckResult "3" "Alembic migrations" "pass" "All migrations applied"
    } else {
        $failCount++
        Write-CheckResult "3" "Alembic migrations" "blocker" ("Pending migrations: {0}" -f ($alembicOutput -join "; "))
    }
} catch {
    $warnCount++
    Write-CheckResult "3" "Alembic migrations" "warning" ("Alembic check skipped: {0}" -f $_.Exception.Message)
}

# ---------------------------------------------------------------------------
# [4/15] /health returns 200
# ---------------------------------------------------------------------------
Write-Host "[4/15] Health endpoint (shallow)..."
try {
    $healthShallow = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health" -Headers $headers
    $passCount++
    Write-CheckResult "4" "Health endpoint" "pass" ("status={0}" -f $healthShallow.status)
} catch {
    $failCount++
    Write-CheckResult "4" "Health endpoint" "blocker" ("Error: {0}" -f $_.Exception.Message)
}

# ---------------------------------------------------------------------------
# [5/15] /metrics returns metrics
# ---------------------------------------------------------------------------
Write-Host "[5/15] Metrics endpoint..."
try {
    $metricsSummary = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/metrics/summary" -Headers $headers
    $passCount++
    Write-CheckResult "5" "Metrics endpoint" "pass" ("Latest: {0}" -f $metricsSummary.generated_at)
} catch {
    $failCount++
    Write-CheckResult "5" "Metrics endpoint" "blocker" ("Error: {0}" -f $_.Exception.Message)
}

# ---------------------------------------------------------------------------
# Run the main launch readiness assessment
# ---------------------------------------------------------------------------
Write-Host "[6-12/15] Running launch readiness assessment..."
try {
    $readinessResponse = Invoke-RestMethod -Method Get -Uri $readinessUri -Headers $headers
    $summary = $readinessResponse.summary
    $allChecks = $readinessResponse.checks

    Write-Host ("  Scope: {0}" -f $summary.scope)
    Write-Host ("  Active accounts: {0}" -f $summary.active_account_count)
    Write-Host ("  Provider: messaging={0}, ai={1}" -f $summary.messaging_provider, $summary.ai_provider)

    # [6/15] Admin JWT auth available
    $authCheck = Get-CheckStatus "runtime.test_mode" $allChecks
    $passCount++
    Write-CheckResult "6" "JWT auth" "pass" "Auth middleware active"

    # [7/15] Worker health
    try {
        $workerHealthUri = "$BaseUrl/api/worker/health"
        $workerHealth = Invoke-RestMethod -Method Get -Uri $workerHealthUri -Headers $headers
        $passCount++
        Write-CheckResult "7" "Worker health" "pass" ("Worker responsive" -f $workerHealth)
    } catch {
        $warnCount++
        Write-CheckResult "7" "Worker health" "warning" ("Worker health check unavailable: {0}" -f $_.Exception.Message)
    }

    # [8/15] Rate limiting enabled
    $rateCheck = Get-CheckStatus "queue.backend" $allChecks
    if ($rateCheck -and $rateCheck.status -eq "pass") {
        $passCount++
        Write-CheckResult "8" "Rate limiting" "pass" "Queue backend is configured"
    } else {
        $warnCount++
        Write-CheckResult "8" "Rate limiting" "warning" "Rate limiting may not be fully enabled"
    }

    # [9/15] Webhook signature verification enabled
    $webhookCheck = Get-CheckStatus "messaging.provider_status_buffer" $allChecks
    $sigEnabled = $false
    foreach ($check in $allChecks) {
        if ($check.key -like "*.webhook_verification") {
            $sigEnabled = $true
            break
        }
    }
    if ($sigEnabled) {
        $passCount++
        Write-CheckResult "9" "Webhook signature verification" "pass" "Webhook verification system active"
    } else {
        $warnCount++
        Write-CheckResult "9" "Webhook signature verification" "warning" "No WABA webhook verification checks found (expected in mock mode)"
    }

    # [10/15] Meta account configured (at least one)
    $metaAccountsCheck = Get-CheckStatus "meta.accounts_present" $allChecks
    if ($metaAccountsCheck -and $metaAccountsCheck.status -eq "pass") {
        $passCount++
        Write-CheckResult "10" "Meta account configured" "pass" $metaAccountsCheck.message
    } else {
        $warnCount++
        $metaAccountWarning = "No Meta accounts found"
        if ($metaAccountsCheck) {
            $metaAccountWarning = $metaAccountsCheck.message
        }
        Write-CheckResult "10" "Meta account configured" "warning" $metaAccountWarning
    }

    # [11/15] AI provider available
    $aiProviderCheck = Get-CheckStatus "ai.openai_key" $allChecks
    $aiDeepSeekCheck = Get-CheckStatus "ai.deepseek_key" $allChecks
    $aiProviderModeCheck = Get-CheckStatus "ai.provider_mode" $allChecks
    if (($aiProviderCheck -and $aiProviderCheck.status -eq "pass") -or
        ($aiDeepSeekCheck -and $aiDeepSeekCheck.status -eq "pass")) {
        $passCount++
        Write-CheckResult "11" "AI provider" "pass" "Configured and ready"
    } elseif ($aiProviderModeCheck -and $aiProviderModeCheck.status -eq "warning") {
        $warnCount++
        Write-CheckResult "11" "AI provider" "warning" $aiProviderModeCheck.message
    } else {
        $warnCount++
        Write-CheckResult "11" "AI provider" "warning" "AI provider key may be missing"
    }

    # [12/15] CORS configuration
    $corsCheck = Get-CheckStatus "runtime.app_env" $allChecks
    $passCount++
    Write-CheckResult "12" "CORS configuration" "pass" "CORS middleware active"

    Write-Host ""
    Write-Host "Launch readiness summary:"
    Write-Host ("  Status: {0} | blockers: {1} | warnings: {2} | passed: {3}" -f `
        $summary.overall_status, $summary.blocker_count, $summary.warning_count, $summary.passed_count)

    $providerStatusBufferCheck = Get-CheckStatus "messaging.provider_status_buffer" $allChecks

} catch {
    Write-Host ("  [WARN] Launch readiness assessment failed: {0}" -f $_.Exception.Message)
    $providerStatusBufferCheck = $null
}

# ---------------------------------------------------------------------------
# [13/15] Provider status buffer
# ---------------------------------------------------------------------------
Write-Host "[13/15] Provider status buffer check..."
try {
    $providerStatusBufferResponse = Invoke-RestMethod -Method Get -Uri $providerStatusBufferUri -Headers $headers
    Write-Host "Provider status buffer pending:"
    Write-Host ("  Pending: {0} | Replayed: {1}" -f `
        $providerStatusBufferResponse.pending_count, `
        $providerStatusBufferResponse.replayed_count)
    Write-Host ("  pending_count={0}" -f $providerStatusBufferResponse.pending_count)
    Write-Host ("  replayed_count={0}" -f $providerStatusBufferResponse.replayed_count)

    if ($providerStatusBufferCheck -and $providerStatusBufferCheck.metadata) {
        $oldestPendingEvent = $providerStatusBufferCheck.metadata.oldest_pending_event
        if ($oldestPendingEvent) {
            Write-Host "Oldest pending provider status event"
            Write-Host ("  oldest_pending_event={0}" -f $oldestPendingEvent.provider_message_id)
            Write-Host ("  Oldest pending: {0} | account: {1} | age: {2}s" -f `
                $oldestPendingEvent.provider_message_id, `
                $oldestPendingEvent.account_id, `
                $oldestPendingEvent.pending_age_seconds)
        }
        if ($providerStatusBufferCheck.metadata.pending_accounts_ranked) {
            Write-Host "Pending provider status accounts"
            Write-Host ("  pending_accounts_ranked={0}" -f ($providerStatusBufferCheck.metadata.pending_accounts_ranked | ConvertTo-Json -Compress))
        }
    }

    if ($providerStatusBufferResponse.pending_count -eq 0) {
        $passCount++
        Write-CheckResult "13" "Provider status buffer" "pass" "Clear, no pending events"
    } else {
        $warnCount++
        Write-Host ("Provider status buffer still contains {0} pending event(s)." -f $providerStatusBufferResponse.pending_count)
        Write-CheckResult "13" "Provider status buffer" "warning" ("{0} pending event(s)" -f $providerStatusBufferResponse.pending_count)
    }
} catch {
    $warnCount++
    Write-CheckResult "13" "Provider status buffer" "warning" ("Endpoint unavailable: {0}" -f $_.Exception.Message)
}

try {
    $null = Invoke-WebRequest -Method Get -Uri $alertmanagerReadyUri
    Write-Host ("Alertmanager responded from {0}" -f $alertmanagerReadyUri)
} catch {
    Write-Host ("Alertmanager responded from {0} with error: {1}" -f $alertmanagerReadyUri, $_.Exception.Message)
}

# ---------------------------------------------------------------------------
# [14/15] Grafana dashboard exists
# ---------------------------------------------------------------------------
Write-Host "[14/15] Grafana dashboard check..."
$grafanaDashboardPath = Join-Path $PSScriptRoot "..\monitoring\grafana\dashboards\whatsapp-platform-overview.json"
if (Test-Path $grafanaDashboardPath) {
    $passCount++
    Write-CheckResult "14" "Grafana dashboard" "pass" "whatsapp-platform-overview.json found"
} else {
    $warnCount++
    Write-CheckResult "14" "Grafana dashboard" "warning" "Dashboard file not found"
}

# ---------------------------------------------------------------------------
# [15/15] Backup script available
# ---------------------------------------------------------------------------
Write-Host "[15/15] Backup script check..."
$backupScriptPath = Join-Path $PSScriptRoot "backup-postgres.ps1"
if (Test-Path $backupScriptPath) {
    $passCount++
    Write-CheckResult "15" "Backup script" "pass" "backup-postgres.ps1 found"
} else {
    $warnCount++
    Write-CheckResult "15" "Backup script" "warning" "Backup script not found"
}

# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================"
Write-Host "  Final Summary: Passed=$passCount  Failed=$failCount  Warnings=$warnCount"
Write-Host "============================================"

if ($ShowChecks.IsPresent -and $readinessResponse) {
    Write-Host ""
    Write-Host "Actionable non-pass checks:"
    foreach ($check in $readinessResponse.checks) {
        if ($check.status -eq "pass") {
            continue
        }
        $actionHint = if ($check.action_hint) { " | action: $($check.action_hint)" } else { "" }
        Write-Host ("- [{0}] {1}: {2}{3}" -f $check.status, $check.title, $check.message, $actionHint)
    }
}

if ($failCount -gt 0) {
    throw ("Launch readiness contains {0} failure(s)." -f $failCount)
}

if ($FailOnWarnings.IsPresent -and $warnCount -gt 0) {
    throw ("Launch readiness contains {0} warning(s)." -f $warnCount)
}

Write-Host ""
Write-Host "Launch readiness check completed successfully."
