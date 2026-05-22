[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunDir,
    [string]$OutputPath = "",
    [string]$Title = "OpenFOAM Solver Output",
    [string]$Velocity = "25 m/s",
    [string]$AngleOfAttack = "2 deg",
    [string]$ReynoldsNumber = "1.67e6"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$backendPath = Join-Path $repoRoot "backend"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$resolvedRunDir = (Resolve-Path $RunDir).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $resolvedRunDir "openfoam-report.html"
}
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $repoRoot $OutputPath }

$env:PYTHONPATH = $backendPath
$env:AI_CFD_REPORT_RUN_DIR = $resolvedRunDir
$env:AI_CFD_REPORT_OUTPUT = $resolvedOutput
$env:AI_CFD_REPORT_TITLE = $Title
$env:AI_CFD_REPORT_VELOCITY = $Velocity
$env:AI_CFD_REPORT_AOA = $AngleOfAttack
$env:AI_CFD_REPORT_RE = $ReynoldsNumber
$pythonCode = "import os; from pathlib import Path; from app.openfoam.report import write_run_report; report=write_run_report(run_dir=Path(os.environ['AI_CFD_REPORT_RUN_DIR']), output_path=Path(os.environ['AI_CFD_REPORT_OUTPUT']), title=os.environ['AI_CFD_REPORT_TITLE'], inputs={'Velocity': os.environ['AI_CFD_REPORT_VELOCITY'], 'Angle of attack': os.environ['AI_CFD_REPORT_AOA'], 'Reynolds number': os.environ['AI_CFD_REPORT_RE']}); print(report)"
& $venvPython -c $pythonCode
if ($LASTEXITCODE -ne 0) {
    throw "OpenFOAM report generation failed."
}
