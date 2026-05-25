[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "",
    [string]$OutputDir = ".local-data\validation-meshes",
    [string]$ReportPath = "",
    [int]$TimeoutSeconds = 900,
    [int]$NacaTimeoutSeconds = 1800,
    [int]$PollIntervalSeconds = 5,
    [string]$BindHost = "127.0.0.1",
    [switch]$SkipGenerate,
    [switch]$SkipPreflight
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

function Test-JsonProperty {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name
    )
    return $null -ne $Object -and ($Object.PSObject.Properties.Name -contains $Name)
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
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $repoRoot $OutputDir }
$resolvedReportPath = if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    Join-Path $resolvedOutput "validation-suite-report.json"
} elseif ([System.IO.Path]::IsPathRooted($ReportPath)) {
    $ReportPath
} else {
    Join-Path $repoRoot $ReportPath
}
$logRoot = Join-Path $repoRoot ".local-data\verify-logs"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

$generatorScript = Join-Path $scriptRoot "generate-validation-meshes.ps1"
$preflightScript = Join-Path $scriptRoot "dev-openfoam-wsl.ps1"
$backendScript = Join-Path $scriptRoot "dev-openfoam-backend.ps1"
$smokeScript = Join-Path $scriptRoot "smoke-local-openfoam.ps1"

foreach ($requiredScript in @($generatorScript, $preflightScript, $backendScript, $smokeScript)) {
    if (-not (Test-Path $requiredScript)) {
        Fail "Missing required validation suite script: $requiredScript"
    }
}

if (-not $SkipGenerate) {
    Run-FileScript -Path $generatorScript -Arguments @("-OutputDir", $resolvedOutput)
} else {
    Write-Host "Skipping validation mesh generation by request."
}

if (-not $SkipPreflight) {
    Run-FileScript -Path $preflightScript -Arguments @("-CheckOnly")
} else {
    Write-Host "Skipping WSL/OpenFOAM preflight by request."
}

$startedBackend = $false
$port = $null
$backendProcess = $null
$baseUrl = $ApiBaseUrl

if ([string]::IsNullOrWhiteSpace($baseUrl)) {
    $port = Get-FreeTcpPort
    $baseUrl = "http://127.0.0.1:$port"
    $stdoutLog = Join-Path $logRoot "validation-mesh-suite-backend.out.log"
    $stderrLog = Join-Path $logRoot "validation-mesh-suite-backend.err.log"
    Write-Host "Starting local OpenFOAM backend for validation mesh suite on $baseUrl ..."
    $backendProcess = Start-LocalOpenFoamBackend -BackendScript $backendScript -Port $port -StdoutLog $stdoutLog -StderrLog $stderrLog
    $startedBackend = $true
    Wait-LocalOpenFoamBackend -BaseUrl $baseUrl -Process $backendProcess -StdoutLog $stdoutLog -StderrLog $stderrLog
}

try {
    $cases = @(
        @{ name = "cylinder"; mesh = "cylinder.msh"; timeout = $TimeoutSeconds; velocity = "15"; angle = "0"; length = "1" },
        @{ name = "box"; mesh = "box.msh"; timeout = $TimeoutSeconds; velocity = "15"; angle = "0"; length = "1" },
        @{ name = "naca0012"; mesh = "naca0012.msh"; timeout = $NacaTimeoutSeconds; velocity = "25"; angle = "0"; length = "1" }
    )
    $caseReports = @()

    foreach ($case in $cases) {
        $meshPath = Join-Path $resolvedOutput $case.mesh
        if (-not (Test-Path $meshPath)) {
            Fail "Validation mesh '$($case.name)' not found at '$meshPath'."
        }
        $caseResultPath = Join-Path $logRoot ("validation-suite-{0}-result.json" -f $case.name)
        Remove-Item $caseResultPath -ErrorAction SilentlyContinue
        Write-Host "Running validation mesh smoke: $($case.name)"
        Run-FileScript -Path $smokeScript -Arguments @(
            "-ApiBaseUrl", $baseUrl,
            "-SampleMeshPath", $meshPath,
            "-Velocity", $case.velocity,
            "-AngleOfAttack", $case.angle,
            "-LengthScale", $case.length,
            "-TimeoutSeconds", [string]$case.timeout,
            "-PollIntervalSeconds", [string]$PollIntervalSeconds,
            "-SkipPreflight",
            "-ResultPath", $caseResultPath
        )
        if (-not (Test-Path $caseResultPath)) {
            Fail "Validation smoke for '$($case.name)' did not write result JSON at '$caseResultPath'."
        }

        $smokeResult = Get-Content $caseResultPath -Raw | ConvertFrom-Json
        $summary = $smokeResult.summary
        $manifest = if (Test-JsonProperty -Object $summary -Name "manifest") { $summary.manifest } else { $null }
        $checkMesh = if (Test-JsonProperty -Object $summary -Name "check_mesh_summary") { $summary.check_mesh_summary } else { $null }
        $caseType = if (Test-JsonProperty -Object $manifest -Name "case_type") { [string]$manifest.case_type } else { "" }
        $cells = if (Test-JsonProperty -Object $checkMesh -Name "cells") { $checkMesh.cells } else { $null }
        $finalCoefficients = if (Test-JsonProperty -Object $summary -Name "final_coefficients") { $summary.final_coefficients } else { $null }

        $caseReports += [ordered]@{
            name = [string]$case.name
            mesh_path = $meshPath
            status = "passed"
            run_id = [string]$smokeResult.run_id
            upload_id = [string]$smokeResult.upload_id
            case_type = $caseType
            artifact_count = [int]$smokeResult.artifact_count
            event_count = [int]$smokeResult.event_count
            cells = $cells
            final_coefficients = $finalCoefficients
            artifact_names = @($smokeResult.artifact_names)
        }
    }

    $reportParent = Split-Path -Parent $resolvedReportPath
    if (-not [string]::IsNullOrWhiteSpace($reportParent)) {
        New-Item -ItemType Directory -Force -Path $reportParent | Out-Null
    }
    $suiteReport = [ordered]@{
        generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        api_base_url = $baseUrl
        output_dir = $resolvedOutput
        cases = @($caseReports)
    }
    ($suiteReport | ConvertTo-Json -Depth 30) | Set-Content -Path $resolvedReportPath -Encoding utf8
    Write-Host "[ok] Wrote validation suite report: $resolvedReportPath"
} finally {
    if ($startedBackend -and $port) {
        Stop-PortProcess -Port $port
    }
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "PASS: Validation mesh suite completed for cylinder, box, and NACA 0012." -ForegroundColor Green
