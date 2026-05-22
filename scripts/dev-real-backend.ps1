[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall,
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [string]$McpUrl = "http://127.0.0.1:7860/mcp"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Update-ProcessPathFromEnvironment {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machinePath, $userPath) | Where-Object { $_ }) -join ";"
}

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Test-McpEndpoint {
    param([Parameter(Mandatory = $true)][string]$Url)

    try {
        $payload = @{
            jsonrpc = "2.0"
            id = 1
            method = "tools/list"
            params = @{}
        } | ConvertTo-Json -Depth 4 -Compress
        $null = Invoke-RestMethod -Method Post -Uri $Url -ContentType "application/json" -Body $payload -TimeoutSec 10
        return $true
    } catch {
        return $false
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

function Read-DotEnv {
    param([Parameter(Mandatory = $true)][string]$Path)

    $values = @{}
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }
        $parts = $line -split "=", 2
        if ($parts.Count -eq 2) {
            $values[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
        }
    }
    return $values
}

Update-ProcessPathFromEnvironment

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$backendPath = Join-Path $repoRoot "backend"
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$dataRoot = Join-Path $repoRoot "data"
$foamAgentRunsRoot = Join-Path $dataRoot "foamagent-runs"
$envFile = Join-Path $repoRoot ".env"

if (-not (Test-Path $envFile)) {
    Fail "Missing .env at '$repoRoot\.env'. Copy .env.example and set OPENAI_API_KEY."
}

$envMap = Read-DotEnv -Path $envFile
$openAiKey = $envMap["OPENAI_API_KEY"]
if ([string]::IsNullOrWhiteSpace($openAiKey) -or $openAiKey -eq "sk-your-key-here") {
    Fail "OPENAI_API_KEY is missing or still set to the placeholder in .env."
}

if (-not (Test-McpEndpoint -Url $McpUrl)) {
    Fail "Foam-Agent MCP is not reachable at $McpUrl. Start it first with scripts/dev-foamagent.ps1."
}

if (-not (Test-PortAvailable -Port $Port)) {
    try {
        $health = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        if ($health.foam_agent_mode -eq "mcp") {
            Write-Host "Backend already running in MCP mode on port $Port."
            exit 0
        }
        Fail "Port $Port is occupied by another service. Stop it or choose another port."
    } catch {
        Fail "Port $Port is already in use and does not look like this backend."
    }
}

if (-not (Get-Command "py" -ErrorAction SilentlyContinue)) {
    Fail "Python launcher 'py' was not found. Run scripts/dev-check.ps1 first."
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath"
    & py -3 -m venv $venvPath
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

New-Item -ItemType Directory -Path $foamAgentRunsRoot -Force | Out-Null

$env:OPENAI_API_KEY = $openAiKey
$env:FOAM_AGENT_MODE = "mcp"
$env:AI_CFD_DATA_ROOT = $dataRoot
$env:FOAM_AGENT_URL = $McpUrl
$env:FOAM_AGENT_SHARED_AGENT_ROOT = "/workspace/data"
$env:FOAM_AGENT_AGENT_RUNS_ROOT = "/home/openfoam/Foam-Agent/runs"
$env:FOAM_AGENT_APP_RUNS_ROOT = $foamAgentRunsRoot
$env:FOAM_AGENT_RUN_TIMEOUT_SECONDS = "900"

Write-Host "Starting real-mode backend on http://localhost:$Port"
Write-Host "FOAM_AGENT_MODE=mcp"
Write-Host "FOAM_AGENT_URL=$McpUrl"
Write-Host "AI_CFD_DATA_ROOT=$dataRoot"
Write-Host "FOAM_AGENT_APP_RUNS_ROOT=$foamAgentRunsRoot"

Push-Location $backendPath
try {
    & $venvPython -m uvicorn app.main:app --reload --host $BindHost --port $Port
} finally {
    Pop-Location
}
