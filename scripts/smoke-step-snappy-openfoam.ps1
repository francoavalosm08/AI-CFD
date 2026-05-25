[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$SampleStepPath = "samples\obstacle-box.step",
    [double]$Velocity = 15,
    [double]$AngleOfAttack = 0,
    [double]$LengthScale = 1,
    [int]$MaxRuntimeMinutes = 5,
    [int]$TimeoutSeconds = 600,
    [int]$PollIntervalSeconds = 2,
    [switch]$SkipPreflight,
    [string]$ResultPath = ".local-data\verify-logs\step-snappy-result.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$smokeLocalScript = Join-Path $scriptRoot "smoke-local-openfoam.ps1"
$resolvedStep = if ([System.IO.Path]::IsPathRooted($SampleStepPath)) { $SampleStepPath } else { Join-Path $repoRoot $SampleStepPath }
$resolvedResultPath = if ([System.IO.Path]::IsPathRooted($ResultPath)) { $ResultPath } else { Join-Path $repoRoot $ResultPath }

if (-not (Test-Path $smokeLocalScript)) {
    Fail "Missing smoke-local-openfoam.ps1 at '$smokeLocalScript'."
}
if (-not (Test-Path $resolvedStep)) {
    Fail "STEP fixture not found at '$resolvedStep'."
}

$arguments = @(
    "-ApiBaseUrl", $ApiBaseUrl,
    "-SampleMeshPath", $resolvedStep,
    "-Velocity", [string]$Velocity,
    "-AngleOfAttack", [string]$AngleOfAttack,
    "-LengthScale", [string]$LengthScale,
    "-MaxRuntimeMinutes", [string]$MaxRuntimeMinutes,
    "-TimeoutSeconds", [string]$TimeoutSeconds,
    "-PollIntervalSeconds", [string]$PollIntervalSeconds,
    "-ResultPath", $resolvedResultPath
)
if ($SkipPreflight) {
    $arguments += "-SkipPreflight"
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $smokeLocalScript @arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$result = Get-Content $resolvedResultPath -Raw | ConvertFrom-Json
$artifactNames = @($result.artifact_names)
$caseType = ""
if ($result.summary -and ($result.summary.PSObject.Properties.Name -contains "manifest")) {
    $caseType = [string]$result.summary.manifest.case_type
}
if ($caseType -ne "external_3d_stl_snappy") {
    Fail "Expected external_3d_stl_snappy case type after STEP conversion, got '$caseType'."
}

foreach ($requiredName in @(
    "surfaceCheck.log",
    "geometry-diagnostics.json",
    "geometry-readiness.json",
    "blockMesh.log",
    "surfaceFeatures.log",
    "snappyHexMesh.log",
    "checkMesh.log",
    "checkMesh-strict.log",
    "snappy-manifest.json"
)) {
    if (-not ($artifactNames -contains $requiredName)) {
        Fail "STEP snappy smoke expected artifact '$requiredName'."
    }
}

Write-Host "PASS: STEP-to-STL snappyHexMesh local OpenFOAM smoke succeeded for run $($result.run_id)." -ForegroundColor Green
