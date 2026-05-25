[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [int]$TimeoutSeconds = 900,
    [int]$PollIntervalSeconds = 2,
    [int]$MaxRuntimeMinutes = 5,
    [switch]$SkipPreflight,
    [switch]$EnableAggressiveSurfaceRepair,
    [string]$ResultPath = ".local-data\verify-logs\surface-corpus-result.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Test-JsonProperty {
    param(
        $Object,
        [Parameter(Mandatory = $true)][string]$Name
    )
    return $null -ne $Object -and ($Object.PSObject.Properties.Name -contains $Name)
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

function Get-ArtifactJson {
    param(
        [Parameter(Mandatory = $true)][array]$Artifacts,
        [Parameter(Mandatory = $true)][string]$DisplayName
    )

    $artifact = @($Artifacts | Where-Object { $_.display_name -eq $DisplayName } | Select-Object -First 1)
    if ($artifact.Count -eq 0) {
        return $null
    }
    $text = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/artifacts/$($artifact[0].id)"
    if ($text -is [string]) {
        return ($text | ConvertFrom-Json)
    }
    return $text
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    if ($script:UsePyLauncher) {
        & py -3 $ScriptPath @Arguments
    } else {
        & $script:PythonExe $ScriptPath @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        Fail "Surface corpus fixture generation failed with exit code $LASTEXITCODE."
    }
}

function Invoke-SurfaceCase {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Case
    )

    $caseName = [string]$Case.name
    $filePath = [string]$Case.path
    $expected = [string]$Case.expected
    $expectedReadiness = [string]$Case.readiness

    Write-Host "Running surface corpus case: $caseName ($expected)"
    $upload = Invoke-JsonFileUpload -Uri "$ApiBaseUrl/api/uploads" -FilePath $filePath
    if (-not $upload.id) {
        throw "Upload response did not contain an upload id."
    }

    $runRequest = @{
        spec = @{
            upload_id = $upload.id
            units = "m"
            length_scale = 1
            velocity = 15
            angle_of_attack = 0
            mesh_quality = "balanced"
            max_runtime_minutes = $MaxRuntimeMinutes
        }
    } | ConvertTo-Json -Depth 6

    $run = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/runs" -ContentType "application/json" -Body $runRequest
    if (-not $run.id) {
        throw "Run response did not contain a run id."
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $finalStatuses = @("completed", "failed", "cancelled")
    while ($true) {
        $run = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$($run.id)"
        if ($finalStatuses -contains $run.status) {
            break
        }
        if ((Get-Date) -ge $deadline) {
            throw "Timed out after $TimeoutSeconds seconds waiting for '$caseName'."
        }
        Start-Sleep -Seconds $PollIntervalSeconds
    }

    $artifactResponse = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$($run.id)/artifacts"
    $artifacts = @($artifactResponse.artifacts)
    $artifactNames = @($artifacts | ForEach-Object { $_.display_name })
    $readiness = Get-ArtifactJson -Artifacts $artifacts -DisplayName "geometry-readiness.json"

    $problems = @()
    if (-not ($artifactNames -contains "geometry-readiness.json")) {
        $problems += "missing geometry-readiness.json"
    }
    if ($null -eq $readiness) {
        $problems += "could not read geometry-readiness.json"
    } elseif ($expectedReadiness) {
        $expectedReadinessOptions = @($expectedReadiness -split "\|")
        if (-not ($expectedReadinessOptions -contains [string]$readiness.status)) {
            $problems += "expected readiness '$expectedReadiness' but got '$($readiness.status)'"
        }
    }

    if ($expected -eq "completed") {
        if ($run.status -ne "completed") {
            $problems += "expected completed run but got '$($run.status)': $($run.error)"
        }
        foreach ($requiredName in @(
            "openfoam-report.html",
            "mesh-quality.png",
            "geometry-diagnostics.png",
            "surfaceCheck.log",
            "snappyHexMesh.log",
            "checkMesh.log"
        )) {
            if (-not ($artifactNames -contains $requiredName)) {
                $problems += "missing $requiredName"
            }
        }
    } elseif ($expected -eq "failed") {
        if ($run.status -ne "failed") {
            $problems += "expected failed run but got '$($run.status)'"
        }
        if ($readiness -and -not ($readiness.recommendations.Count -gt 0)) {
            $problems += "failure did not include readiness recommendations"
        }
    } else {
        throw "Unknown expected outcome '$expected' for $caseName."
    }

    $status = if ($problems.Count -eq 0) { "passed" } else { "failed" }
    [ordered]@{
        name = $caseName
        file = $filePath
        expected = $expected
        status = $status
        run_id = [string]$run.id
        run_status = [string]$run.status
        run_error = if ($run.error) { [string]$run.error } else { $null }
        readiness_status = if ($readiness) { [string]$readiness.status } else { $null }
        recommendations = if ($readiness) { @($readiness.recommendations) } else { @() }
        artifact_names = @($artifactNames)
        problems = @($problems)
    }
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$corpusRoot = Join-Path $repoRoot ".local-data\surface-corpus"
$logRoot = Join-Path $repoRoot ".local-data\verify-logs"
$resolvedResultPath = if ([System.IO.Path]::IsPathRooted($ResultPath)) { $ResultPath } else { Join-Path $repoRoot $ResultPath }
New-Item -ItemType Directory -Force -Path $corpusRoot, $logRoot | Out-Null

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$script:UsePyLauncher = $false
$script:PythonExe = $venvPython
if (-not (Test-Path $venvPython)) {
    if (-not (Get-Command "py" -ErrorAction SilentlyContinue)) {
        Fail "Could not find .venv Python or the 'py' launcher to generate the surface corpus."
    }
    $script:UsePyLauncher = $true
}

$generatorPath = Join-Path $corpusRoot "_generate_surface_corpus.py"
@'
from pathlib import Path
import shutil
import sys

import numpy as np
import trimesh


def export(mesh, path):
    mesh.export(path, file_type="stl")


def main():
    out = Path(sys.argv[1])
    repo = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    cube = trimesh.creation.box(extents=(0.25, 0.25, 0.25))
    export(cube, out / "clean-cube.stl")

    cylinder = trimesh.creation.cylinder(radius=0.12, height=0.35, sections=32)
    export(cylinder, out / "clean-cylinder.stl")

    step_source = repo / "samples" / "obstacle-box.step"
    if not step_source.exists():
        raise SystemExit(f"Missing STEP fixture: {step_source}")
    shutil.copyfile(step_source, out / "clean-box.step")

    hole = trimesh.Trimesh(vertices=cube.vertices.copy(), faces=cube.faces[:-1].copy(), process=False)
    export(hole, out / "repairable-hole.stl")

    degenerate_vertices = np.vstack([cube.vertices, [[0.0, 0.0, 0.0]]])
    degenerate_faces = np.vstack([cube.faces, [[0, 0, len(degenerate_vertices) - 1]]])
    degenerate = trimesh.Trimesh(vertices=degenerate_vertices, faces=degenerate_faces, process=False)
    export(degenerate, out / "degenerate-triangle.stl")

    dup_vertices = []
    dup_faces = []
    for face in cube.faces:
        indices = []
        for vertex_index in face:
            dup_vertices.append(cube.vertices[int(vertex_index)])
            indices.append(len(dup_vertices) - 1)
        dup_faces.append(indices)
    duplicate = trimesh.Trimesh(vertices=np.array(dup_vertices), faces=np.array(dup_faces), process=False)
    export(duplicate, out / "duplicate-vertices.stl")

    shifted = cube.copy()
    shifted.apply_translation([0.75, 0.0, 0.0])
    multiple = trimesh.util.concatenate([cube, shifted])
    export(multiple, out / "multiple-bodies.stl")

    sheet = trimesh.Trimesh(
        vertices=np.array([[0, 0, 0], [0.25, 0, 0], [0.25, 0.25, 0], [0, 0.25, 0]], dtype=float),
        faces=np.array([[0, 1, 2], [0, 2, 3]], dtype=int),
        process=False,
    )
    export(sheet, out / "open-sheet.stl")

    tiny = trimesh.creation.box(extents=(1e-6, 1e-6, 1e-6))
    export(tiny, out / "bad-scale.stl")


if __name__ == "__main__":
    main()
'@ | Set-Content -Path $generatorPath -Encoding utf8

Invoke-Python -ScriptPath $generatorPath -Arguments @($corpusRoot, $repoRoot)

if (-not $SkipPreflight) {
    $preflightScript = Join-Path $scriptRoot "dev-openfoam-wsl.ps1"
    if (-not (Test-Path $preflightScript)) {
        Fail "Missing WSL/OpenFOAM preflight script at '$preflightScript'."
    }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $preflightScript -CheckOnly
    if ($LASTEXITCODE -ne 0) {
        Fail "WSL/OpenFOAM preflight failed. Fix runtime setup before running surface corpus smoke."
    }
}

Write-Host "Checking backend health at $ApiBaseUrl ..."
$health = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/health"
if ($health.status -ne "ok") {
    Fail "Health endpoint returned unexpected status '$($health.status)'."
}
$runnerMode = $null
if (Test-JsonProperty -Object $health -Name "runner_mode") {
    $runnerMode = $health.runner_mode
}
if ([string]::IsNullOrWhiteSpace($runnerMode) -and (Test-JsonProperty -Object $health -Name "foam_agent_mode")) {
    $runnerMode = $health.foam_agent_mode
}
if ($runnerMode -ne "local_openfoam") {
    Fail "Surface corpus expects CFD_RUNNER_MODE=local_openfoam, but backend reported '$runnerMode'."
}

$cases = @(
    @{ name = "clean-cube.stl"; path = Join-Path $corpusRoot "clean-cube.stl"; expected = "completed"; readiness = "ready" },
    @{ name = "clean-cylinder.stl"; path = Join-Path $corpusRoot "clean-cylinder.stl"; expected = "completed"; readiness = "ready" },
    @{ name = "clean-box.step"; path = Join-Path $corpusRoot "clean-box.step"; expected = "completed"; readiness = "ready" },
    @{ name = "repairable-hole.stl"; path = Join-Path $corpusRoot "repairable-hole.stl"; expected = "completed"; readiness = "repaired_ready" },
    @{ name = "degenerate-triangle.stl"; path = Join-Path $corpusRoot "degenerate-triangle.stl"; expected = "completed"; readiness = "repaired_ready" },
    @{ name = "duplicate-vertices.stl"; path = Join-Path $corpusRoot "duplicate-vertices.stl"; expected = "completed"; readiness = "ready|repaired_ready" },
    @{ name = "multiple-bodies.stl"; path = Join-Path $corpusRoot "multiple-bodies.stl"; expected = "failed"; readiness = "failed_geometry" },
    @{ name = "open-sheet.stl"; path = Join-Path $corpusRoot "open-sheet.stl"; expected = "failed"; readiness = "failed_geometry" },
    @{ name = "bad-scale.stl"; path = Join-Path $corpusRoot "bad-scale.stl"; expected = "failed"; readiness = "failed_geometry" }
)

$caseResults = @()
foreach ($case in $cases) {
    try {
        $caseResults += Invoke-SurfaceCase -Case $case
    } catch {
        $caseResults += [ordered]@{
            name = [string]$case.name
            file = [string]$case.path
            expected = [string]$case.expected
            status = "failed"
            run_id = $null
            run_status = $null
            run_error = $_.Exception.Message
            readiness_status = $null
            recommendations = @()
            artifact_names = @()
            problems = @($_.Exception.Message)
        }
    }
}

$failedCases = @($caseResults | Where-Object { $_.status -ne "passed" })
$resultParent = Split-Path -Parent $resolvedResultPath
if (-not [string]::IsNullOrWhiteSpace($resultParent)) {
    New-Item -ItemType Directory -Force -Path $resultParent | Out-Null
}

$result = [ordered]@{
    status = if ($failedCases.Count -eq 0) { "passed" } else { "failed" }
    api_base_url = $ApiBaseUrl
    runner_mode = $runnerMode
    aggressive_surface_repair = [bool]$EnableAggressiveSurfaceRepair
    corpus_root = $corpusRoot
    generated_cases = @($cases | ForEach-Object { $_.name })
    cases = @($caseResults)
}
($result | ConvertTo-Json -Depth 30) | Set-Content -Path $resolvedResultPath -Encoding utf8
Write-Host "[ok] Wrote surface corpus result: $resolvedResultPath"

if ($failedCases.Count -gt 0) {
    foreach ($failed in $failedCases) {
        Write-Host ("[failed] {0}: {1}" -f $failed.name, (($failed.problems | ForEach-Object { [string]$_ }) -join "; ")) -ForegroundColor Red
    }
    Fail "$($failedCases.Count) surface corpus case(s) failed."
}

Write-Host "PASS: Surface corpus smoke passed. Results include geometry-readiness.json checks." -ForegroundColor Green
