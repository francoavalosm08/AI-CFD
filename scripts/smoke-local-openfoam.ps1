[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$SampleMeshPath = "",
    [double]$Velocity = 25,
    [double]$AngleOfAttack = 3,
    [double]$LengthScale = 1,
    [int]$MaxRuntimeMinutes = 60,
    [int]$TimeoutSeconds = 120,
    [int]$PollIntervalSeconds = 1,
    [switch]$DryRun,
    [switch]$SkipPreflight,
    [string]$ResultPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($SampleMeshPath)) {
    $SampleMeshPath = Join-Path $repoRoot "samples\wing.msh"
}

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-JsonFileUpload {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$FilePath
    )

    $client = [System.Net.Http.HttpClient]::new()
    try {
        $multipart = [System.Net.Http.MultipartFormDataContent]::new()
        $stream = [System.IO.File]::OpenRead($FilePath)
        try {
            $streamContent = [System.Net.Http.StreamContent]::new($stream)
            $streamContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/octet-stream")
            $multipart.Add($streamContent, "file", [System.IO.Path]::GetFileName($FilePath))

            $response = $client.PostAsync($Uri, $multipart).GetAwaiter().GetResult()
            $bodyText = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) {
                throw "HTTP $([int]$response.StatusCode): $bodyText"
            }
            return ($bodyText | ConvertFrom-Json)
        } finally {
            $stream.Dispose()
            $multipart.Dispose()
        }
    } finally {
        $client.Dispose()
    }
}

function Get-HttpText {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [int]$TimeoutSeconds = 30
    )

    $client = [System.Net.Http.HttpClient]::new()
    try {
        $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
        return $client.GetStringAsync($Uri).GetAwaiter().GetResult()
    } finally {
        $client.Dispose()
    }
}

function Test-JsonProperty {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name
    )
    return $null -ne $Object -and ($Object.PSObject.Properties.Name -contains $Name)
}

if (-not (Test-Path $SampleMeshPath)) {
    Fail "Sample mesh not found at '$SampleMeshPath'."
}

try {
    $resolvedMesh = (Resolve-Path $SampleMeshPath).Path
} catch {
    Fail "Could not resolve sample mesh path '$SampleMeshPath'."
}

if (-not $DryRun -and -not $SkipPreflight) {
    $preflightScript = Join-Path $scriptRoot "dev-openfoam-wsl.ps1"
    if (-not (Test-Path $preflightScript)) {
        Fail "Missing WSL/OpenFOAM preflight script at '$preflightScript'."
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $preflightScript -CheckOnly
    if ($LASTEXITCODE -ne 0) {
        Fail "WSL/OpenFOAM preflight failed. Fix runtime setup before running real local OpenFOAM smoke."
    }
}

Write-Host "Checking backend health at $ApiBaseUrl ..."
try {
    $health = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/health"
} catch {
    Fail ("Could not reach $ApiBaseUrl/api/health. Start backend first with scripts/dev-openfoam-backend.ps1{0}. Details: {1}" -f $(if ($DryRun) { " -DryRun" } else { "" }), $_.Exception.Message)
}

if ($health.status -ne "ok") {
    Fail "Health endpoint returned unexpected status '$($health.status)'."
}

$runnerMode = $null
if ($health.PSObject.Properties.Name -contains "runner_mode") {
    $runnerMode = $health.runner_mode
}
if ([string]::IsNullOrWhiteSpace($runnerMode) -and ($health.PSObject.Properties.Name -contains "foam_agent_mode")) {
    $runnerMode = $health.foam_agent_mode
}
if ($runnerMode -ne "local_openfoam") {
    Fail "Smoke test expects CFD_RUNNER_MODE=local_openfoam, but backend reported '$runnerMode'."
}
Write-Host "[ok] Health check passed (local OpenFOAM mode)."

Write-Host "Uploading sample mesh: $resolvedMesh"
try {
    $upload = Invoke-JsonFileUpload -Uri "$ApiBaseUrl/api/uploads" -FilePath $resolvedMesh
} catch {
    Fail ("Upload failed: {0}" -f $_.Exception.Message)
}

if (-not $upload.id) {
    Fail "Upload response did not contain an upload id."
}
Write-Host "[ok] Upload id: $($upload.id)"

$runRequest = @{
    spec = @{
        upload_id = $upload.id
        units = "m"
        length_scale = $LengthScale
        velocity = $Velocity
        angle_of_attack = $AngleOfAttack
        mesh_quality = "balanced"
        max_runtime_minutes = $MaxRuntimeMinutes
    }
} | ConvertTo-Json -Depth 6

Write-Host "Creating local OpenFOAM run..."
try {
    $run = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/runs" -ContentType "application/json" -Body $runRequest
} catch {
    Fail ("Create run failed: {0}" -f $_.Exception.Message)
}

if (-not $run.id) {
    Fail "Run response did not contain a run id."
}
$runId = $run.id
Write-Host "[ok] Run id: $runId"

$finalStatuses = @("completed", "failed", "cancelled")
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ($true) {
    try {
        $run = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$runId"
    } catch {
        Fail ("Failed to poll run status for '$runId': {0}" -f $_.Exception.Message)
    }

    Write-Host ("Run status: {0}" -f $run.status)
    if ($finalStatuses -contains $run.status) {
        break
    }

    if ((Get-Date) -ge $deadline) {
        Fail "Timed out after $TimeoutSeconds seconds waiting for terminal run status."
    }

    Start-Sleep -Seconds $PollIntervalSeconds
}

if ($run.status -ne "completed") {
    $errorText = if ($run.error) { [string]$run.error } else { "No run.error provided by backend." }
    Fail ("Run ended with status '{0}'. Detail: {1}" -f $run.status, $errorText)
}
Write-Host "[ok] Run reached completed status."

Write-Host "Verifying artifacts..."
try {
    $artifactResponse = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$runId/artifacts"
} catch {
    Fail ("Could not fetch artifacts: {0}" -f $_.Exception.Message)
}

$artifacts = @($artifactResponse.artifacts)
if ($artifacts.Count -eq 0) {
    Fail "Run completed but returned zero artifacts."
}

$names = @($artifacts | ForEach-Object { $_.display_name })
foreach ($requiredName in @("openfoam-commands.json", "case-manifest.json", "mesh-validation.json", "openfoam-case.zip")) {
    if (-not ($names -contains $requiredName)) {
        Fail "Artifacts did not include required local OpenFOAM output '$requiredName'."
    }
}
if ($DryRun -and -not ($names -contains "openfoam-dry-run.log")) {
    Fail "Dry-run smoke expected openfoam-dry-run.log."
}
if (-not $DryRun) {
    foreach ($requiredName in @("solver.log", "checkMesh.log", "checkMesh-summary.json", "residuals.csv", "openfoam-report.html")) {
        if (-not ($names -contains $requiredName)) {
            Fail "Real local OpenFOAM smoke expected '$requiredName'. Use -DryRun if OpenFOAM is not installed yet."
        }
    }

    $caseType = ""
    if (Test-JsonProperty -Object $run.summary -Name "manifest") {
        $manifest = $run.summary.manifest
        if (Test-JsonProperty -Object $manifest -Name "case_type") {
            $caseType = [string]$manifest.case_type
        }
    }

    if ($caseType -eq "airfoil_2d") {
        if (-not (Test-JsonProperty -Object $run.summary -Name "check_mesh_summary")) {
            Fail "Airfoil OpenFOAM smoke expected check_mesh_summary in run summary."
        }
        $checkMesh = $run.summary.check_mesh_summary
        if (-not (Test-JsonProperty -Object $checkMesh -Name "cells")) {
            Fail "Airfoil OpenFOAM smoke expected check_mesh_summary.cells."
        }
        if ([int]$checkMesh.cells -lt 40000) {
            Fail ("Airfoil mesh cell count is below V1 acceptance threshold: {0}." -f $checkMesh.cells)
        }
    }

    $forceEnabled = $false
    if (Test-JsonProperty -Object $run.summary -Name "force_coefficients") {
        $forceConfig = $run.summary.force_coefficients
        if (Test-JsonProperty -Object $forceConfig -Name "enabled") {
            $forceEnabled = [bool]$forceConfig.enabled
        }
    }
    if ($forceEnabled) {
        foreach ($requiredName in @("forceCoeffs.dat", "forceCoeffs.csv", "force-coefficients.png", "pressure.png", "velocity-magnitude.png")) {
            if (-not ($names -contains $requiredName)) {
                Fail "Force-coefficient OpenFOAM smoke expected '$requiredName'."
            }
        }

        if (-not (Test-JsonProperty -Object $run.summary -Name "final_coefficients")) {
            Fail "Force-coefficient OpenFOAM smoke expected final_coefficients in run summary."
        }
        $finalCoefficients = $run.summary.final_coefficients
        foreach ($coefficient in @("Cl", "Cd", "Cm")) {
            if (-not (Test-JsonProperty -Object $finalCoefficients -Name $coefficient)) {
                Fail "Force-coefficient OpenFOAM smoke expected final coefficient '$coefficient'."
            }
        }
    }
}
Write-Host ("[ok] Artifacts found: {0}." -f $artifacts.Count)

Write-Host "Verifying event stream..."
try {
    $eventsContent = Get-HttpText -Uri "$ApiBaseUrl/api/runs/$runId/events" -TimeoutSeconds 30
} catch {
    Fail ("Could not read event stream: {0}" -f $_.Exception.Message)
}

$eventLines = @()
if ($eventsContent) {
    $eventLines = @(
        ($eventsContent -split "`r?`n") |
        Where-Object { $_ -like "data:*" }
    )
}

if ($eventLines.Count -eq 0) {
    Fail "Event stream returned no status events."
}
Write-Host ("[ok] Event stream returned {0} status messages." -f $eventLines.Count)

$modeText = if ($DryRun) { "dry-run" } else { "real" }
if (-not [string]::IsNullOrWhiteSpace($ResultPath)) {
    $resolvedResultPath = if ([System.IO.Path]::IsPathRooted($ResultPath)) { $ResultPath } else { Join-Path $repoRoot $ResultPath }
    $resultParent = Split-Path -Parent $resolvedResultPath
    if (-not [string]::IsNullOrWhiteSpace($resultParent)) {
        New-Item -ItemType Directory -Force -Path $resultParent | Out-Null
    }
    $result = [ordered]@{
        status = "passed"
        mode = $modeText
        dry_run = [bool]$DryRun
        api_base_url = $ApiBaseUrl
        runner_mode = $runnerMode
        mesh_path = $resolvedMesh
        upload_id = [string]$upload.id
        run_id = [string]$runId
        run_status = [string]$run.status
        artifact_count = [int]$artifacts.Count
        event_count = [int]$eventLines.Count
        artifact_names = @($names)
        summary = $run.summary
    }
    ($result | ConvertTo-Json -Depth 20) | Set-Content -Path $resolvedResultPath -Encoding utf8
    Write-Host "[ok] Wrote smoke result: $resolvedResultPath"
}
Write-Host ("PASS: Local OpenFOAM {0} smoke flow succeeded for run {1}." -f $modeText, $runId) -ForegroundColor Green
