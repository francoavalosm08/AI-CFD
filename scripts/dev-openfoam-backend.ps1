[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall,
    [switch]$DryRun,
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [string]$Runtime = $(if ($env:OPENFOAM_RUNTIME) { $env:OPENFOAM_RUNTIME } else { "wsl" }),
    [string]$Distro = $(if ($env:OPENFOAM_WSL_DISTRO) { $env:OPENFOAM_WSL_DISTRO } else { "" }),
    [string]$Bashrc = $(if ($env:OPENFOAM_BASHRC) { $env:OPENFOAM_BASHRC } else { "/opt/openfoam*/etc/bashrc" }),
    [switch]$EnableAggressiveSurfaceRepair,
    [switch]$NoReload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Update-ProcessPathFromEnvironment {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machinePath, $userPath) | Where-Object { $_ }) -join ";"
}

function Test-PortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

function Get-DetectedUbuntuDistro {
    if (-not (Get-Command "wsl.exe" -ErrorAction SilentlyContinue)) {
        return "Ubuntu"
    }
    $distros = @(& wsl.exe -l -q 2>$null | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
    $ubuntu = @($distros | Where-Object { $_.ToLowerInvariant().StartsWith("ubuntu") } | Select-Object -First 1)
    if ($ubuntu.Count -gt 0) {
        return $ubuntu[0]
    }
    return "Ubuntu"
}

Update-ProcessPathFromEnvironment
if ([string]::IsNullOrWhiteSpace($Distro)) {
    $Distro = Get-DetectedUbuntuDistro
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$backendPath = Join-Path $repoRoot "backend"
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$dataRoot = Join-Path $repoRoot ".local-data"

if (-not (Get-Command "py" -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Run scripts/dev-check.ps1 first."
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath"
    & py -3 -m venv $venvPath
}

if (-not (Test-Path $venvPython)) {
    throw "Could not find venv python at $venvPython."
}

if (-not $SkipDependencyInstall) {
    Write-Host "Installing backend dependencies..."
    Push-Location $backendPath
    try {
        $backendExtras = if ($EnableAggressiveSurfaceRepair) { ".[test,surface-repair]" } else { ".[test]" }
        & $venvPython -m pip install -e $backendExtras
    } finally {
        Pop-Location
    }
}

if (-not (Test-PortAvailable -Port $Port)) {
    throw "Port $Port is already in use. Stop the existing service or rerun with -Port <free-port>."
}

$env:CFD_RUNNER_MODE = "local_openfoam"
$env:FOAM_AGENT_MODE = "local_openfoam"
$env:OPENFOAM_RUNTIME = $Runtime
$env:OPENFOAM_WSL_DISTRO = $Distro
$env:OPENFOAM_BASHRC = $Bashrc
$env:AI_CFD_DATA_ROOT = $dataRoot
if ($DryRun) {
    $env:OPENFOAM_DRY_RUN = "1"
} else {
    Remove-Item Env:\OPENFOAM_DRY_RUN -ErrorAction SilentlyContinue
}
if ($EnableAggressiveSurfaceRepair) {
    $env:AI_CFD_SURFACE_REPAIR = "meshfix"
} else {
    Remove-Item Env:\AI_CFD_SURFACE_REPAIR -ErrorAction SilentlyContinue
}

$dryRunText = if ($DryRun) { "enabled" } else { "disabled" }
$surfaceRepairText = if ($EnableAggressiveSurfaceRepair) { "meshfix" } else { "basic" }
Write-Host "Starting backend on http://localhost:$Port (CFD_RUNNER_MODE=local_openfoam, runtime=$Runtime, dry-run=$dryRunText, surface-repair=$surfaceRepairText, AI_CFD_DATA_ROOT=$dataRoot)"
Push-Location $backendPath
try {
    $uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", $BindHost, "--port", [string]$Port)
    if (-not $NoReload) {
        $uvicornArgs += "--reload"
    }
    & $venvPython @uvicornArgs
} finally {
    Pop-Location
}
