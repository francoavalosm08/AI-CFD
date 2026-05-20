[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [int]$Port = 5173
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Update-ProcessPathFromEnvironment {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machinePath, $userPath) | Where-Object { $_ }) -join ";"
}

function Add-NodePathIfPresent {
    $candidatePaths = @(
        "C:\Program Files\nodejs",
        (Join-Path $env:ProgramFiles "nodejs")
    ) | Select-Object -Unique

    foreach ($candidate in $candidatePaths) {
        if (
            (Test-Path (Join-Path $candidate "node.exe")) -and
            (Test-Path (Join-Path $candidate "npm.cmd"))
        ) {
            if (-not (($env:Path -split ";") -contains $candidate)) {
                $env:Path = "$candidate;$($env:Path)"
            }
            return
        }
    }
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
Add-NodePathIfPresent

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$frontendPath = Join-Path $repoRoot "frontend"
$nodeModulesPath = Join-Path $frontendPath "node_modules"

if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) {
    throw "Node.js was not found on PATH. Run scripts/dev-check.ps1 first."
}

if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    throw "npm was not found on PATH. Run scripts/dev-check.ps1 first."
}

$shouldInstall = -not $SkipInstall
if ($shouldInstall -and -not (Test-Path $nodeModulesPath)) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $frontendPath
    try {
        & npm install
    } finally {
        Pop-Location
    }
} elseif ($shouldInstall) {
    Write-Host "node_modules already exists; skipping npm install. Use -SkipInstall to silence this message."
}

if (-not (Test-PortAvailable -Port $Port)) {
    throw "Port $Port is already in use. Stop the existing service or rerun with -Port <free-port>."
}

Write-Host "Starting Vite dev server on http://localhost:$Port"
Push-Location $frontendPath
try {
    & npm run dev -- --port $Port
} finally {
    Pop-Location
}
