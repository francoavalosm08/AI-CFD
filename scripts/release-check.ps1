[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$FrontendBaseUrl = "http://127.0.0.1:5173",
    [switch]$SkipSmoke,
    [switch]$SkipE2E,
    [switch]$SkipLocalOpenFoamDryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$localVerifyScript = Join-Path $scriptRoot "local-verify.ps1"
$localOpenFoamBackendScript = Join-Path $scriptRoot "dev-openfoam-backend.ps1"
$localOpenFoamSmokeScript = Join-Path $scriptRoot "smoke-local-openfoam.ps1"
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path

function Test-PortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Get-FreeTcpPort {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
        $listener.Start()
        return $listener.LocalEndpoint.Port
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Get-Health {
    param([Parameter(Mandatory = $true)][string]$BaseUrl)

    try {
        return Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/health" -TimeoutSec 2
    } catch {
        return $null
    }
}

if (-not (Test-Path $localVerifyScript)) {
    throw "Missing script: $localVerifyScript"
}
if (-not $SkipLocalOpenFoamDryRun) {
    foreach ($requiredScript in @($localOpenFoamBackendScript, $localOpenFoamSmokeScript)) {
        if (-not (Test-Path $requiredScript)) {
            throw "Missing script: $requiredScript"
        }
    }
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $localVerifyScript,
    "-Scope", "full",
    "-ApiBaseUrl", $ApiBaseUrl,
    "-FrontendBaseUrl", $FrontendBaseUrl
)

if ($SkipSmoke) {
    $arguments += "-SkipSmoke"
}
if ($SkipE2E) {
    $arguments += "-SkipE2E"
}

Write-Host "Running release check (backend tests + frontend tests + smoke + browser E2E)..."
& powershell @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Release check failed."
}

if (-not $SkipLocalOpenFoamDryRun) {
    $localOpenFoamPort = Get-FreeTcpPort
    $localOpenFoamUrl = "http://127.0.0.1:$localOpenFoamPort"
    $logRoot = Join-Path $repoRoot ".local-data\verify-logs"
    New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
    $serverLog = Join-Path $logRoot "release-local-openfoam-dryrun-backend.log"
    Remove-Item $serverLog -ErrorAction SilentlyContinue

    if (-not (Test-PortAvailable -Port $localOpenFoamPort)) {
        throw "Port $localOpenFoamPort is already in use; cannot run local OpenFOAM dry-run release smoke."
    }

    Write-Host "Running local OpenFOAM dry-run release smoke on $localOpenFoamUrl ..."
    $backendJob = Start-Job -ScriptBlock {
        param($BackendScript, $Port, $ServerLog)
        $ErrorActionPreference = "Stop"
        & powershell -NoProfile -ExecutionPolicy Bypass -File $BackendScript -SkipDependencyInstall -DryRun -NoReload -BindHost "127.0.0.1" -Port $Port > $ServerLog 2>&1
    } -ArgumentList $localOpenFoamBackendScript, $localOpenFoamPort, $serverLog

    try {
        $deadline = (Get-Date).AddSeconds(45)
        $healthy = $false
        while ((Get-Date) -lt $deadline) {
            $health = Get-Health -BaseUrl $localOpenFoamUrl
            if ($health -and $health.status -eq "ok") {
                $runnerMode = $null
                if ($health.PSObject.Properties.Name -contains "runner_mode") {
                    $runnerMode = $health.runner_mode
                }
                if ([string]::IsNullOrWhiteSpace($runnerMode) -and ($health.PSObject.Properties.Name -contains "foam_agent_mode")) {
                    $runnerMode = $health.foam_agent_mode
                }
                if ($runnerMode -eq "local_openfoam") {
                    $healthy = $true
                    break
                }
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $healthy) {
            if (Test-Path $serverLog) {
                Get-Content $serverLog -Tail 80
            }
            throw "Timed out waiting for local OpenFOAM dry-run backend."
        }

        & powershell -NoProfile -ExecutionPolicy Bypass -File $localOpenFoamSmokeScript -ApiBaseUrl $localOpenFoamUrl -DryRun -TimeoutSeconds 60
        if ($LASTEXITCODE -ne 0) {
            throw "Local OpenFOAM dry-run smoke failed."
        }
    } finally {
        Stop-Job -Job $backendJob -ErrorAction SilentlyContinue | Out-Null
        Receive-Job -Job $backendJob -Keep -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $backendJob -ErrorAction SilentlyContinue | Out-Null
    }
} else {
    Write-Host "Skipping local OpenFOAM dry-run release smoke by request."
}

Write-Host "Release check passed." -ForegroundColor Green

