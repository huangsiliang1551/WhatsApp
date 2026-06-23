param(
    [string]$OutputDir = ".\backups",
    [string]$ContainerName = "whatsapp_postgres",
    [string]$DatabaseName = "whatsapp_bot",
    [string]$DatabaseUser = "whatsapp_user"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "docker command was not found."
    }
}

function Ensure-ContainerRunning {
    param([string]$Name)

    $isRunning = docker inspect -f "{{.State.Running}}" $Name 2>$null
    if ($LASTEXITCODE -ne 0 -or $isRunning.Trim() -ne "true") {
        throw "Container '$Name' is not running."
    }
}

Require-Docker
Ensure-ContainerRunning -Name $ContainerName

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$resolvedOutputDir = Resolve-Path -Path $OutputDir -ErrorAction SilentlyContinue
if ($null -eq $resolvedOutputDir) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    $resolvedOutputDir = Resolve-Path -Path $OutputDir
}

$backupDir = Join-Path $resolvedOutputDir "postgres-$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$archiveName = "postgres.dump"
$containerArchivePath = "/tmp/$archiveName"
$localArchivePath = Join-Path $backupDir $archiveName
$manifestPath = Join-Path $backupDir "manifest.json"

Write-Host "Creating PostgreSQL backup from container '$ContainerName'..."
docker exec $ContainerName pg_dump -U $DatabaseUser -d $DatabaseName -Fc -f $containerArchivePath
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed."
}

docker cp "${ContainerName}:$containerArchivePath" $localArchivePath
if ($LASTEXITCODE -ne 0) {
    throw "docker cp for backup archive failed."
}

docker exec $ContainerName rm -f $containerArchivePath | Out-Null

$manifest = @{
    created_at = (Get-Date).ToString("o")
    container_name = $ContainerName
    database_name = $DatabaseName
    database_user = $DatabaseUser
    archive = $archiveName
    restore_hint = "Use scripts/restore-postgres.ps1 with this backup directory."
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding utf8

Write-Host "Backup completed:" $backupDir
