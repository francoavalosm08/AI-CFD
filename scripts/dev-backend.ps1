[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall,
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000
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

Update-ProcessPathFromEnvironment

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
        & $venvPython -m pip install -e ".[test]"
    } finally {
        Pop-Location
    }
}

if (-not (Test-PortAvailable -Port $Port)) {
    throw "Port $Port is already in use. Stop the existing service or rerun with -Port <free-port>."
}

$env:FOAM_AGENT_MODE = "fake"
$env:AI_CFD_DATA_ROOT = $dataRoot

Write-Host "Starting backend on http://localhost:$Port (FOAM_AGENT_MODE=fake, AI_CFD_DATA_ROOT=$dataRoot)"
Push-Location $backendPath
try {
    & $venvPython -m uvicorn app.main:app --reload --host $BindHost --port $Port
} finally {
    Pop-Location
}
