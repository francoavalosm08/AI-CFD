[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$SampleStlPath = "samples\obstacle-box.stl",
    [double]$Velocity = 15,
    [double]$AngleOfAttack = 0,
    [double]$LengthScale = 1,
    [int]$MaxRuntimeMinutes = 5,
    [int]$TimeoutSeconds = 600,
    [int]$PollIntervalSeconds = 2,
    [switch]$SkipPreflight,
    [string]$ResultPath = ".local-data\verify-logs\stl-snappy-result.json"
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
$resolvedStl = if ([System.IO.Path]::IsPathRooted($SampleStlPath)) { $SampleStlPath } else { Join-Path $repoRoot $SampleStlPath }
$resolvedResultPath = if ([System.IO.Path]::IsPathRooted($ResultPath)) { $ResultPath } else { Join-Path $repoRoot $ResultPath }

if (-not (Test-Path $smokeLocalScript)) {
    Fail "Missing smoke-local-openfoam.ps1 at '$smokeLocalScript'."
}
if (-not (Test-Path $resolvedStl)) {
    Fail "STL fixture not found at '$resolvedStl'."
}

$arguments = @(
    "-ApiBaseUrl", $ApiBaseUrl,
    "-SampleMeshPath", $resolvedStl,
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
    Fail "Expected external_3d_stl_snappy case type, got '$caseType'."
}

foreach ($requiredName in @(
    "surfaceCheck.log",
    "blockMesh.log",
    "surfaceFeatures.log",
    "snappyHexMesh.log",
    "checkMesh.log",
    "checkMesh-strict.log",
    "snappy-manifest.json"
)) {
    if (-not ($artifactNames -contains $requiredName)) {
        Fail "STL snappy smoke expected artifact '$requiredName'."
    }
}

Write-Host "PASS: STL snappyHexMesh local OpenFOAM smoke succeeded for run $($result.run_id)." -ForegroundColor Green
