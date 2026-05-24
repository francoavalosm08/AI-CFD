[CmdletBinding()]
param(
    [string]$OutputDir = ".local-data\validation-meshes",
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
$env:AI_CFD_VALIDATION_OUTPUT = $resolvedOutput
$env:AI_CFD_VALIDATION_THICKNESS = [string]$ThicknessMeters
$pythonCode = @'
import os
from pathlib import Path
from app.openfoam.naca4412 import build_naca4_geo, build_naca4_stl
from app.openfoam.validation_meshes import build_box_obstacle_geo, build_cylinder_obstacle_geo

out = Path(os.environ["AI_CFD_VALIDATION_OUTPUT"])
thickness = float(os.environ["AI_CFD_VALIDATION_THICKNESS"])
out.mkdir(parents=True, exist_ok=True)
cases = {
    "naca0012": (build_naca4_geo(code="0012", thickness=thickness), build_naca4_stl(code="0012", thickness=thickness)),
    "cylinder": (build_cylinder_obstacle_geo(thickness=thickness), None),
    "box": (build_box_obstacle_geo(thickness=thickness), None),
}
for name, (geo, stl) in cases.items():
    (out / f"{name}.geo").write_text(geo, encoding="ascii")
    if stl is not None:
        (out / f"{name}.stl").write_text(stl, encoding="ascii")
    print(out / f"{name}.geo")
'@
$pythonFile = Join-Path $resolvedOutput "_generate_validation_meshes.py"
Set-Content -Path $pythonFile -Value $pythonCode -Encoding UTF8
& $venvPython $pythonFile

if (-not $SkipMesh) {
    if (-not (Get-Command "gmsh" -ErrorAction SilentlyContinue)) {
        throw "gmsh was not found on PATH. Install Gmsh or rerun with -SkipMesh."
    }
    foreach ($caseName in @("naca0012", "cylinder", "box")) {
        $geoPath = Join-Path $resolvedOutput "$caseName.geo"
        $meshPath = Join-Path $resolvedOutput "$caseName.msh"
        & gmsh $geoPath -3 -format msh2 -nopopup -o $meshPath
        if ($LASTEXITCODE -ne 0) {
            throw "Gmsh failed while generating $caseName mesh."
        }
        Write-Host "Generated $meshPath"
    }
}
