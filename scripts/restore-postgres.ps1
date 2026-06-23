param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDir,
    [string]$ContainerName = "whatsapp_postgres",
    [string]$DatabaseName = "whatsapp_bot",
    [string]$DatabaseUser = "whatsapp_user",
    [switch]$Force
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

$resolvedBackupDir = Resolve-Path -Path $BackupDir -ErrorAction Stop
$archivePath = Join-Path $resolvedBackupDir "postgres.dump"
if (-not (Test-Path -LiteralPath $archivePath)) {
    throw "Backup archive '$archivePath' was not found."
}

if (-not $Force) {
    $confirmation = Read-Host "This will overwrite database '$DatabaseName' inside container '$ContainerName'. Type RESTORE to continue"
    if ($confirmation -ne "RESTORE") {
        throw "Restore cancelled."
    }
}

$containerArchivePath = "/tmp/postgres-restore.dump"

Write-Host "Copying backup archive into container '$ContainerName'..."
docker cp $archivePath "${ContainerName}:$containerArchivePath"
if ($LASTEXITCODE -ne 0) {
    throw "docker cp for restore archive failed."
}

Write-Host "Restoring PostgreSQL backup into '$DatabaseName'..."
docker exec $ContainerName pg_restore `
    -U $DatabaseUser `
    -d $DatabaseName `
    --clean `
    --if-exists `
    --no-owner `
    --no-privileges `
    $containerArchivePath
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore failed."
}

docker exec $ContainerName rm -f $containerArchivePath | Out-Null

Write-Host "Restore completed from:" $resolvedBackupDir
