param(
    [switch]$CheckCompose = $true,
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

function Test-CommandAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [string[]]$Arguments = @()
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $Arguments `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath
        $output = @(
            [System.IO.File]::ReadAllText($stdoutPath)
            [System.IO.File]::ReadAllText($stderrPath)
        ) -join ""
        $output = $output.Trim()
    }
    finally {
        Remove-Item $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    }
    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output   = $output
    }
}

function Write-CheckResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [bool]$Passed,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $prefix = if ($Passed) { "[OK]" } else { "[WARN]" }
    Write-Host "$prefix $Label - $Message"
}

if (-not (Test-CommandAvailable "docker")) {
    throw "docker command was not found."
}

$dockerDefaultVersion = Invoke-CapturedCommand -FilePath "docker" -Arguments @("--context", "default", "version")
$dockerDesktopVersion = Invoke-CapturedCommand -FilePath "docker" -Arguments @("version")
$dockerDesktopStatus = Invoke-CapturedCommand -FilePath "docker" -Arguments @("desktop", "status")
$dockerCurrentContext = Invoke-CapturedCommand -FilePath "docker" -Arguments @("context", "show")
$dockerDefaultInfo = Invoke-CapturedCommand -FilePath "docker" -Arguments @("--context", "default", "info", "--format", "{{.OSType}}")
$dockerDesktopContextList = Invoke-CapturedCommand -FilePath "docker" -Arguments @("context", "ls")
$dockerDesktopWslProbe = Invoke-CapturedCommand -FilePath "wsl" -Arguments @("-d", "docker-desktop", "-u", "root", "--exec", "/bin/true")
$dockerDesktopService = Get-Service com.docker.service -ErrorAction SilentlyContinue

Write-Host "Docker Desktop preflight"
Write-Host "Project root: $ProjectRoot"
Write-Host "Current docker context: $($dockerCurrentContext.Output)"

$defaultContextReady = $dockerDefaultVersion.ExitCode -eq 0
$defaultContextIsWindows = $dockerDefaultInfo.ExitCode -eq 0 -and $dockerDefaultInfo.Output -eq "windows"
$desktopLinuxReady = $dockerDesktopVersion.ExitCode -eq 0
$desktopLinuxPipeMissing = $dockerDesktopVersion.Output -match "dockerDesktopLinuxEngine"
$desktopStatusRunning = $dockerDesktopStatus.ExitCode -eq 0 -and $dockerDesktopStatus.Output -match "Status\s+running"
$desktopServiceRunning = $null -ne $dockerDesktopService -and $dockerDesktopService.Status -eq "Running"
$desktopServiceHealthy = $desktopServiceRunning -or $desktopStatusRunning
$dockerDesktopWslRunning = $dockerDesktopWslProbe.ExitCode -eq 0

$desktopServiceMessage = if ($desktopServiceHealthy) {
    if ($desktopServiceRunning) {
        "com.docker.service is running."
    } else {
        "Docker Desktop is running even though com.docker.service is not active."
    }
} else {
    "com.docker.service is not running."
}

$dockerDesktopWslMessage = if ($dockerDesktopWslRunning) {
    "docker-desktop distro responds inside WSL."
} else {
    "docker-desktop distro did not respond."
}

$defaultContextMessage = if ($defaultContextReady) {
    if ($defaultContextIsWindows) {
        "default context is reachable but points to Windows containers."
    } else {
        "default context is reachable."
    }
} else {
    "default context is not reachable."
}

$desktopLinuxMessage = if ($desktopLinuxReady) {
    "desktop-linux is reachable."
} elseif ($desktopLinuxPipeMissing) {
    "desktop-linux pipe is missing; Docker Desktop Linux engine is not ready."
} else {
    "desktop-linux is not reachable."
}

Write-CheckResult -Label "Docker CLI" -Passed $true -Message "docker command is available."
Write-CheckResult -Label "Docker Desktop service" -Passed $desktopServiceHealthy -Message $desktopServiceMessage
Write-CheckResult -Label "docker-desktop WSL distro" -Passed $dockerDesktopWslRunning -Message $dockerDesktopWslMessage
Write-CheckResult -Label "default context" -Passed $defaultContextReady -Message $defaultContextMessage
Write-CheckResult -Label "desktop-linux context" -Passed $desktopLinuxReady -Message $desktopLinuxMessage

if ($CheckCompose) {
    Push-Location $ProjectRoot
    try {
        $composeConfig = Invoke-CapturedCommand -FilePath "docker" -Arguments @("compose", "config")
    }
    finally {
        Pop-Location
    }

    $composeConfigMessage = if ($composeConfig.ExitCode -eq 0) {
        "Compose file parses successfully."
    } else {
        "Compose config validation failed."
    }
    Write-CheckResult -Label "docker compose config" -Passed ($composeConfig.ExitCode -eq 0) -Message $composeConfigMessage
}

$issues = New-Object System.Collections.Generic.List[string]
if (-not $desktopServiceHealthy) {
    $issues.Add("Start Docker Desktop or run: Start-Service com.docker.service")
}
if ($defaultContextIsWindows) {
    $issues.Add("Current fallback engine is Windows-only; this project needs Linux containers.")
}
if (-not $dockerDesktopWslRunning) {
    $issues.Add("Bring up the docker-desktop WSL distro by launching Docker Desktop and waiting for WSL initialization.")
}
if (-not $desktopLinuxReady) {
    $issues.Add("Wait for Docker Desktop Linux engine to expose //./pipe/dockerDesktopLinuxEngine, then rerun this script.")
}
if ($desktopLinuxReady -and $defaultContextIsWindows) {
    $issues.Add("Run: docker context use desktop-linux")
}
if (-not $desktopLinuxReady -and $dockerDesktopWslRunning) {
    $issues.Add("If the WSL distro is up but the pipe is still missing, restart Docker Desktop and enable WSL integration for your working distro.")
}

if ($issues.Count -eq 0) {
    Write-Host ""
    Write-Host "Docker Desktop Linux engine is ready for this repository."
    exit 0
}

Write-Host ""
Write-Host "Recommended next steps:"
foreach ($issue in $issues) {
    Write-Host "- $issue"
}

if ($desktopLinuxPipeMissing) {
    exit 3
}

exit 1
