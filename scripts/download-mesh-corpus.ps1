[CmdletBinding()]
param(
    [string]$OutputDir = ".local-data\external-mesh-corpus"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$backendPath = Join-Path $repoRoot "backend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $repoRoot $OutputDir }

if (-not (Test-Path $venvPython)) {
    throw "Missing venv Python at $venvPython. Run scripts/dev-check.ps1 first."
}

New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$sources = @(
    @{
        name = "cylinder_2d.msh"
        url = "https://people.sc.fsu.edu/~jburkardt/data/msh/cylinder_2d.msh"
        source = "John Burkardt / FSU Gmsh MSH sample data"
        license = "GNU LGPL, per source page"
    },
    @{
        name = "rectangle.msh"
        url = "https://people.sc.fsu.edu/~jburkardt/data/msh/rectangle.msh"
        source = "John Burkardt / FSU Gmsh MSH sample data"
        license = "GNU LGPL, per source page"
    },
    @{
        name = "step_2d.msh"
        url = "https://people.sc.fsu.edu/~jburkardt/data/msh/step_2d.msh"
        source = "John Burkardt / FSU Gmsh MSH sample data"
        license = "GNU LGPL, per source page"
    },
    @{
        name = "airfoil_exterior.msh"
        url = "https://people.sc.fsu.edu/~jburkardt/examples/gmsh/airfoil_exterior.msh"
        source = "John Burkardt / FSU Gmsh example data"
        license = "GNU LGPL, per source page"
    }
)

foreach ($source in $sources) {
    $target = Join-Path $resolvedOutput $source.name
    Write-Host "Downloading $($source.url)"
    Invoke-WebRequest -Uri $source.url -OutFile $target -TimeoutSec 60
}

$env:PYTHONPATH = $backendPath
$env:AI_CFD_CORPUS_OUTPUT = $resolvedOutput
$sourceJson = $sources | ConvertTo-Json -Depth 4 -Compress
$env:AI_CFD_CORPUS_SOURCES = $sourceJson
$pythonCode = @'
import hashlib
import json
import os
from pathlib import Path

from app.openfoam.mesh_corpus import classify_msh_file

out = Path(os.environ["AI_CFD_CORPUS_OUTPUT"])
sources = json.loads(os.environ["AI_CFD_CORPUS_SOURCES"])
entries = []
for source in sources:
    path = out / source["name"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    classification = classify_msh_file(path)
    entries.append({
        **source,
        "path": str(path),
        "sha256": digest,
        "classification": classification,
    })
manifest = {
    "description": "Downloaded public .msh corpus for parser/provenance validation. Solver-ready status is recorded per file.",
    "entries": entries,
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(out / "manifest.json")
'@
$pythonFile = Join-Path $resolvedOutput "_classify_corpus.py"
Set-Content -Path $pythonFile -Value $pythonCode -Encoding UTF8
& $venvPython $pythonFile
