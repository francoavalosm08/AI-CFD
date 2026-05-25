[CmdletBinding()]
param(
    [switch]$SkipReleaseCheck,
    [switch]$SkipRuntimeReport,
    [switch]$SkipRealOpenFoam,
    [switch]$IncludeValidationMeshSuite,
    [int]$NacaTimeoutSeconds = 1200,
    [int]$StlTimeoutSeconds = 600,
    [int]$StepTimeoutSeconds = 600,
    [int]$ValidationMeshTimeoutSeconds = 900,
    [int]$ValidationMeshNacaTimeoutSeconds = 1800,
    [int]$BadMeshTimeoutSeconds = 120,
    [int]$PollIntervalSeconds = 5,
    [string]$BindHost = "127.0.0.1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
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

function Stop-PortProcess {
    param([Parameter(Mandatory = $true)][int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -ne 0 }
    foreach ($connection in $connections) {
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
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

function Run-FileScript {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$Arguments = @()
    )

    & powershell -NoProfile -ExecutionPolicy Bypass -File $Path @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Script failed ($Path) with exit code $LASTEXITCODE."
    }
}

function Start-LocalOpenFoamBackend {
    param(
        [Parameter(Mandatory = $true)][string]$BackendScript,
        [Parameter(Mandatory = $true)][int]$Port,
        [Parameter(Mandatory = $true)][string]$StdoutLog,
        [Parameter(Mandatory = $true)][string]$StderrLog
    )

    Stop-PortProcess -Port $Port
    Remove-Item $StdoutLog, $StderrLog -ErrorAction SilentlyContinue
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $BackendScript,
        "-SkipDependencyInstall",
        "-NoReload",
        "-BindHost", $BindHost,
        "-Port", [string]$Port
    )
    return Start-Process -FilePath "powershell.exe" -ArgumentList $args -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
}

function Wait-LocalOpenFoamBackend {
    param(
        [Parameter(Mandatory = $true)][string]$BaseUrl,
        [Parameter(Mandatory = $true)]$Process,
        [Parameter(Mandatory = $true)][string]$StdoutLog,
        [Parameter(Mandatory = $true)][string]$StderrLog,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $health = Get-Health -BaseUrl $BaseUrl
        if ($health -and $health.status -eq "ok") {
            $runnerMode = $null
            if ($health.PSObject.Properties.Name -contains "runner_mode") {
                $runnerMode = $health.runner_mode
            }
            if ([string]::IsNullOrWhiteSpace($runnerMode) -and ($health.PSObject.Properties.Name -contains "foam_agent_mode")) {
                $runnerMode = $health.foam_agent_mode
            }
            if ($runnerMode -eq "local_openfoam") {
                return
            }
        }
        if ($Process.HasExited) {
            if (Test-Path $StdoutLog) { Get-Content $StdoutLog -Tail 120 }
            if (Test-Path $StderrLog) { Get-Content $StderrLog -Tail 120 }
            throw "Local OpenFOAM backend exited before becoming healthy."
        }
        Start-Sleep -Seconds 2
    }

    if (Test-Path $StdoutLog) { Get-Content $StdoutLog -Tail 120 }
    if (Test-Path $StderrLog) { Get-Content $StderrLog -Tail 120 }
    throw "Timed out waiting for local OpenFOAM backend at $BaseUrl."
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$logRoot = Join-Path $repoRoot ".local-data\verify-logs"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$runtimeReportScript = Join-Path $scriptRoot "runtime-report.ps1"
$releaseCheckScript = Join-Path $scriptRoot "release-check.ps1"
$preflightScript = Join-Path $scriptRoot "dev-openfoam-wsl.ps1"
$backendScript = Join-Path $scriptRoot "dev-openfoam-backend.ps1"
$nacaSmokeScript = Join-Path $scriptRoot "smoke-naca-openfoam.ps1"
$stlSnappySmokeScript = Join-Path $scriptRoot "smoke-stl-snappy-openfoam.ps1"
$stepSnappySmokeScript = Join-Path $scriptRoot "smoke-step-snappy-openfoam.ps1"
$badMeshSmokeScript = Join-Path $scriptRoot "smoke-bad-mesh-validation.ps1"
$validationMeshSuiteScript = Join-Path $scriptRoot "smoke-validation-mesh-suite.ps1"

foreach ($requiredScript in @($runtimeReportScript, $releaseCheckScript, $preflightScript, $backendScript, $nacaSmokeScript, $stlSnappySmokeScript, $stepSnappySmokeScript, $badMeshSmokeScript, $validationMeshSuiteScript)) {
    if (-not (Test-Path $requiredScript)) {
        Fail "Missing required V1 acceptance script: $requiredScript"
    }
}

Write-Host "Running local V1 release acceptance gate..."

if (-not $SkipRuntimeReport) {
    Run-FileScript -Path $runtimeReportScript
} else {
    Write-Host "Skipping runtime report by request."
}

if (-not $SkipReleaseCheck) {
    Run-FileScript -Path $releaseCheckScript
} else {
    Write-Host "Skipping fast release check by request."
}

if ($SkipRealOpenFoam) {
    Write-Host "Skipping real OpenFOAM gates by request."
    Write-Host "PASS: Local V1 acceptance gate completed without real OpenFOAM gates." -ForegroundColor Green
    exit 0
}

Run-FileScript -Path $preflightScript -Arguments @("-CheckOnly")

$port = Get-FreeTcpPort
$baseUrl = "http://127.0.0.1:$port"
$stdoutLog = Join-Path $logRoot "release-v1-openfoam-backend.out.log"
$stderrLog = Join-Path $logRoot "release-v1-openfoam-backend.err.log"
$backendProcess = $null

try {
    Write-Host "Starting local OpenFOAM backend for real V1 gates on $baseUrl ..."
    $backendProcess = Start-LocalOpenFoamBackend -BackendScript $backendScript -Port $port -StdoutLog $stdoutLog -StderrLog $stderrLog
    Wait-LocalOpenFoamBackend -BaseUrl $baseUrl -Process $backendProcess -StdoutLog $stdoutLog -StderrLog $stderrLog

    Run-FileScript -Path $nacaSmokeScript -Arguments @(
        "-ApiBaseUrl", $baseUrl,
        "-TimeoutSeconds", [string]$NacaTimeoutSeconds,
        "-PollIntervalSeconds", [string]$PollIntervalSeconds
    )
    Run-FileScript -Path $stlSnappySmokeScript -Arguments @(
        "-ApiBaseUrl", $baseUrl,
        "-TimeoutSeconds", [string]$StlTimeoutSeconds,
        "-PollIntervalSeconds", [string]$PollIntervalSeconds,
        "-SkipPreflight"
    )
    Run-FileScript -Path $stepSnappySmokeScript -Arguments @(
        "-ApiBaseUrl", $baseUrl,
        "-TimeoutSeconds", [string]$StepTimeoutSeconds,
        "-PollIntervalSeconds", [string]$PollIntervalSeconds,
        "-SkipPreflight"
    )
    Run-FileScript -Path $badMeshSmokeScript -Arguments @(
        "-ApiBaseUrl", $baseUrl,
        "-TimeoutSeconds", [string]$BadMeshTimeoutSeconds,
        "-PollIntervalSeconds", [string]$PollIntervalSeconds
    )
    if ($IncludeValidationMeshSuite) {
        Run-FileScript -Path $validationMeshSuiteScript -Arguments @(
            "-ApiBaseUrl", $baseUrl,
            "-TimeoutSeconds", [string]$ValidationMeshTimeoutSeconds,
            "-NacaTimeoutSeconds", [string]$ValidationMeshNacaTimeoutSeconds,
            "-PollIntervalSeconds", [string]$PollIntervalSeconds,
            "-SkipPreflight"
        )
    }
} finally {
    Stop-PortProcess -Port $port
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "PASS: Local V1 release acceptance gate passed." -ForegroundColor Green
