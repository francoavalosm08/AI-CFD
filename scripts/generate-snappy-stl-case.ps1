[CmdletBinding()]
param(
    [string]$StlPath = "samples\obstacle-box.stl",
    [string]$OutputDir = ".local-data\snappy-stl-case",
    [double]$LengthScale = 1.0,
    [double]$Velocity = 25.0,
    [double]$AngleOfAttack = 0.0,
    [ValidateSet("coarse", "balanced", "fine")]
    [string]$MeshQuality = "coarse"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$backendPath = Join-Path $repoRoot "backend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$resolvedStl = if ([System.IO.Path]::IsPathRooted($StlPath)) { $StlPath } else { Join-Path $repoRoot $StlPath }
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $repoRoot $OutputDir }

if (-not (Test-Path $resolvedStl)) {
    throw "STL file was not found at '$resolvedStl'."
}

$pythonExe = $venvPython
if (-not (Test-Path $pythonExe)) {
    $py = Get-Command "py" -ErrorAction SilentlyContinue
    if (-not $py) {
        throw "Missing Python. Run scripts/dev-check.ps1 first."
    }
    $pythonExe = $py.Source
}

New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$env:PYTHONPATH = $backendPath
$env:AI_CFD_SNAPPY_STL = (Resolve-Path $resolvedStl).Path
$env:AI_CFD_SNAPPY_OUTPUT = $resolvedOutput
$env:AI_CFD_SNAPPY_LENGTH = [string]$LengthScale
$env:AI_CFD_SNAPPY_VELOCITY = [string]$Velocity
$env:AI_CFD_SNAPPY_AOA = [string]$AngleOfAttack
$env:AI_CFD_SNAPPY_QUALITY = $MeshQuality

$pythonCode = @'
import json
import os
from pathlib import Path

from app.openfoam.snappy import build_snappy_stl_case, snappy_openfoam_commands
from app.schemas import SimulationSpec

output = Path(os.environ["AI_CFD_SNAPPY_OUTPUT"])
case_dir = output / "case"
spec = SimulationSpec(
    upload_id="manual-stl",
    units="m",
    length_scale=float(os.environ["AI_CFD_SNAPPY_LENGTH"]),
    velocity=float(os.environ["AI_CFD_SNAPPY_VELOCITY"]),
    angle_of_attack=float(os.environ["AI_CFD_SNAPPY_AOA"]),
    mesh_quality=os.environ["AI_CFD_SNAPPY_QUALITY"],
)
manifest = build_snappy_stl_case(
    spec=spec,
    stl_path=Path(os.environ["AI_CFD_SNAPPY_STL"]),
    case_dir=case_dir,
)
(output / "openfoam-commands.json").write_text(
    json.dumps(
        {
            "case_dir": str(case_dir),
            "commands": snappy_openfoam_commands(),
            "manual_wsl_sequence": [
                "surfaceCheck constant/triSurface/obstacle.stl",
                "blockMesh",
                "surfaceFeatures",
                "snappyHexMesh -overwrite",
                "checkMesh",
                "checkMesh -allGeometry -allTopology",
                "simpleFoam",
            ],
            "manifest": manifest,
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(case_dir)
print(output / "openfoam-commands.json")
'@

$tempScript = Join-Path ([System.IO.Path]::GetTempPath()) ("ai-cfd-snappy-case-{0}.py" -f ([System.Guid]::NewGuid().ToString("N")))
try {
    Set-Content -Path $tempScript -Value $pythonCode -Encoding UTF8
    & $pythonExe $tempScript
    if ($LASTEXITCODE -ne 0) {
        throw "Could not generate snappyHexMesh STL case."
    }
} finally {
    Remove-Item $tempScript -ErrorAction SilentlyContinue
}

Write-Host "Generated snappyHexMesh STL case in $resolvedOutput"
Write-Host "Manual mesh checks from the case folder:"
Write-Host "  surfaceCheck constant/triSurface/obstacle.stl"
Write-Host "  blockMesh"
Write-Host "  surfaceFeatures"
Write-Host "  snappyHexMesh -overwrite"
Write-Host "  checkMesh"
Write-Host "  checkMesh -allGeometry -allTopology   # optional strict diagnostics"
