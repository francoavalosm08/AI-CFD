[CmdletBinding()]
param(
    [string]$OutputDir = ".local-data\naca4412",
    [double]$ChordMeters = 1.0,
    [double]$ThicknessMeters = 0.01,
    [switch]$SkipMesh
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Update-ProcessPathFromEnvironment {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machinePath, $userPath) | Where-Object { $_ }) -join ";"
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$backendPath = Join-Path $repoRoot "backend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $repoRoot $OutputDir }

if (-not (Test-Path $venvPython)) {
    throw "Missing venv Python at $venvPython. Run scripts/dev-check.ps1 first."
}

Update-ProcessPathFromEnvironment

New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$env:PYTHONPATH = $backendPath
$env:AI_CFD_NACA_OUTPUT = $resolvedOutput
$env:AI_CFD_NACA_CHORD = [string]$ChordMeters
$env:AI_CFD_NACA_THICKNESS = [string]$ThicknessMeters
$pythonCode = "import os; from pathlib import Path; from app.openfoam.naca4412 import build_naca4412_geo, build_naca4412_stl; out=Path(os.environ['AI_CFD_NACA_OUTPUT']); out.mkdir(parents=True, exist_ok=True); chord=float(os.environ['AI_CFD_NACA_CHORD']); thickness=float(os.environ['AI_CFD_NACA_THICKNESS']); (out / 'naca4412.geo').write_text(build_naca4412_geo(chord=chord, thickness=thickness), encoding='ascii'); (out / 'naca4412.stl').write_text(build_naca4412_stl(chord=chord, thickness=thickness), encoding='ascii'); print(out / 'naca4412.geo'); print(out / 'naca4412.stl')"
& $venvPython -c $pythonCode

if (-not $SkipMesh) {
    if (-not (Get-Command "gmsh" -ErrorAction SilentlyContinue)) {
        throw "gmsh was not found on PATH. Install Gmsh or rerun with -SkipMesh."
    }
    & gmsh (Join-Path $resolvedOutput "naca4412.geo") -3 -format msh2 -nopopup -o (Join-Path $resolvedOutput "naca4412.msh")
    if ($LASTEXITCODE -ne 0) {
        throw "Gmsh failed while generating NACA 4412 mesh."
    }
    Write-Host "Generated $(Join-Path $resolvedOutput 'naca4412.msh')"
}
