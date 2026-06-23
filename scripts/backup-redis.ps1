param(
    [string]$OutputDir = ".\backups",
    [string]$ContainerName = "whatsapp_redis"
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

$backupDir = Join-Path $resolvedOutputDir "redis-$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$archiveName = "redis.rdb"
$localArchivePath = Join-Path $backupDir $archiveName
$manifestPath = Join-Path $backupDir "manifest.json"

Write-Host "Triggering BGSAVE on Redis container '$ContainerName'..."
$bgsaveResult = docker exec $ContainerName redis-cli BGSAVE
if ($LASTEXITCODE -ne 0) {
    throw "BGSAVE command failed."
}
Write-Host "BGSAVE: $bgsaveResult"

Write-Host "Waiting for BGSAVE to complete..."
$maxWaitSeconds = 30
$waited = 0
while ($waited -lt $maxWaitSeconds) {
    $persistenceInfo = docker exec $ContainerName redis-cli INFO persistence
    $rdbBgsaveInProgress = ($persistenceInfo | Select-String -Pattern "rdb_bgsave_in_progress:1").Count -gt 0
    if (-not $rdbBgsaveInProgress) {
        Write-Host "BGSAVE completed after ${waited}s."
        break
    }
    Start-Sleep -Seconds 2
    $waited += 2
}
if ($waited -ge $maxWaitSeconds) {
    throw "BGSAVE did not complete within ${maxWaitSeconds}s."
}

# Retrieve the last RDB save path
$rdbDir = docker exec $ContainerName redis-cli CONFIG GET dir | Select-Object -Last 1
$rdbFilename = docker exec $ContainerName redis-cli CONFIG GET dbfilename | Select-Object -Last 1
$rdbSourcePath = "$rdbDir/$rdbFilename"
$containerRdbSource = "${ContainerName}:$rdbSourcePath"

Write-Host "Copying RDB file from '$containerRdbSource'..."
docker cp $containerRdbSource $localArchivePath
if ($LASTEXITCODE -ne 0) {
    throw "docker cp for RDB file failed."
}

$manifest = @{
    created_at = (Get-Date).ToString("o")
    container_name = $ContainerName
    rdb_file = $archiveName
    rdb_source_path = $rdbSourcePath
    restore_hint = "Stop the Redis container, restore the RDB file to a new volume, then restart."
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding utf8

Write-Host "Redis backup completed:" $backupDir
