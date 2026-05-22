[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$OutputDir = "",
    [int]$TimeoutSeconds = 1200,
    [int]$PollIntervalSeconds = 5,
    [switch]$SkipPreflight
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $repoRoot ".local-data\naca4412-improved"
}

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

$generator = Join-Path $scriptRoot "generate-naca4412.ps1"
if (-not (Test-Path $generator)) {
    Fail "Missing NACA generator at '$generator'."
}

Write-Host "Generating NACA 4412 validation mesh in $OutputDir ..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $generator -OutputDir $OutputDir
if ($LASTEXITCODE -ne 0) {
    Fail "NACA 4412 mesh generation failed."
}

$meshPath = Join-Path $OutputDir "naca4412.msh"
if (-not (Test-Path $meshPath)) {
    Fail "NACA mesh generator did not create '$meshPath'."
}

$smoke = Join-Path $scriptRoot "smoke-local-openfoam.ps1"
$smokeArgs = @(
    "-ApiBaseUrl", $ApiBaseUrl,
    "-SampleMeshPath", $meshPath,
    "-Velocity", "25",
    "-AngleOfAttack", "2",
    "-LengthScale", "1",
    "-TimeoutSeconds", $TimeoutSeconds,
    "-PollIntervalSeconds", $PollIntervalSeconds
)
if ($SkipPreflight) {
    $smokeArgs += "-SkipPreflight"
}

Write-Host "Running local OpenFOAM NACA 4412 acceptance smoke ..."
& powershell -NoProfile -ExecutionPolicy Bypass -File $smoke @smokeArgs
if ($LASTEXITCODE -ne 0) {
    Fail "NACA 4412 OpenFOAM acceptance smoke failed."
}

Write-Host "PASS: NACA 4412 local OpenFOAM validation completed." -ForegroundColor Green
