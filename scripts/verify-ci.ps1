Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found."
    }
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @()
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        $argumentText = if ($Arguments.Count -gt 0) {
            " $($Arguments -join ' ')"
        } else {
            ""
        }
        throw "Command '$FilePath$argumentText' failed with exit code $LASTEXITCODE."
    }
}

function Resolve-PythonCommand {
    $workspacePython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    if (Test-Path $workspacePython) {
        return (Resolve-Path $workspacePython).Path
    }

    Require-Command python
    return "python"
}

Require-Command npm
Require-Command docker
$pythonCommand = Resolve-PythonCommand

Write-Host "[1/6] Running backend tests..."
Invoke-CheckedCommand -FilePath $pythonCommand -Arguments @("-m", "pytest")

Write-Host "[2/6] Building frontend..."
Push-Location frontend
try {
    Invoke-CheckedCommand -FilePath "npm" -Arguments @("run", "build")
}
finally {
    Pop-Location
}

Write-Host "[3/6] Validating Docker Compose..."
$null = & docker compose config
if ($LASTEXITCODE -ne 0) {
    throw "Command 'docker compose config' failed with exit code $LASTEXITCODE."
}

Write-Host "[4/6] Validating Grafana dashboard JSON..."
Get-Content -Path "monitoring/grafana/dashboards/whatsapp-platform-overview.json" -Raw |
    ConvertFrom-Json | Out-Null

Write-Host "[5/6] Validating Alertmanager config..."
Invoke-CheckedCommand -FilePath "docker" -Arguments @(
    "run",
    "--rm",
    "-v",
    "${PWD}/monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro",
    "prom/alertmanager:v0.28.1",
    "amtool",
    "check-config",
    "/etc/alertmanager/alertmanager.yml"
)

Write-Host "[6/6] Validating PowerShell deployment scripts..."
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile("scripts/backup-postgres.ps1", [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    throw ($errors | ForEach-Object { $_.Message } | Out-String)
}
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile("scripts/restore-postgres.ps1", [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    throw ($errors | ForEach-Object { $_.Message } | Out-String)
}
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile("scripts/check-launch-readiness.ps1", [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    throw ($errors | ForEach-Object { $_.Message } | Out-String)
}
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile("scripts/check-docker-desktop.ps1", [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) {
    throw ($errors | ForEach-Object { $_.Message } | Out-String)
}

Write-Host "CI verification completed successfully."
