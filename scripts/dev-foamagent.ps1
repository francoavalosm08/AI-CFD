[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [int]$Port = 7860,
    [string]$Image = "leoyue123/foamagent:v2.0.0",
    [string]$ContainerName = "ai-cfd-foamagent"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Test-DockerDaemon {
    $null = docker info 2>&1
    return ($LASTEXITCODE -eq 0)
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
        $response = Invoke-RestMethod -Method Post -Uri $Url -ContentType "application/json" -Body $payload -TimeoutSec 10
        return [bool]$response
    } catch {
        return $false
    }
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$envFile = Join-Path $repoRoot ".env"
$dataRoot = Join-Path $repoRoot "data"
$sharedRuns = Join-Path $dataRoot "foamagent-runs"
$mcpUrl = "http://127.0.0.1:$Port/mcp"

Write-Host "Foam-Agent preflight (image=$Image, port=$Port)"

if (-not (Test-DockerDaemon)) {
    Fail "Docker daemon is not reachable. Start Docker Desktop and rerun this script."
}

if (-not (Test-Path $envFile)) {
    Fail "Missing .env at '$envFile'. Copy .env.example to .env and set OPENAI_API_KEY."
}

$envLines = Get-Content $envFile | Where-Object { $_ -and -not $_.Trim().StartsWith("#") }
$envMap = @{}
foreach ($line in $envLines) {
    $parts = $line -split "=", 2
    if ($parts.Count -eq 2) {
        $envMap[$parts[0].Trim()] = $parts[1].Trim()
    }
}

$openAiKey = $envMap["OPENAI_API_KEY"]
if ([string]::IsNullOrWhiteSpace($openAiKey) -or $openAiKey -eq "sk-your-key-here") {
    Fail "OPENAI_API_KEY is missing or still set to the placeholder in .env."
}

if (-not (Test-Path $sharedRuns)) {
    New-Item -ItemType Directory -Path $sharedRuns -Force | Out-Null
    Write-Host "[ok] Created shared runs directory at $sharedRuns"
} else {
    Write-Host "[ok] Shared runs directory exists at $sharedRuns"
}

if (Test-McpEndpoint -Url $mcpUrl) {
    Write-Host "[ok] Foam-Agent MCP endpoint is already reachable at $mcpUrl"
    if ($CheckOnly) {
        Write-Host "PASS: Foam-Agent preflight checks passed." -ForegroundColor Green
        exit 0
    }
    Write-Host "Using existing Foam-Agent endpoint."
    exit 0
}

$portListener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portListener) {
    Fail "Port $Port is in use but Foam-Agent MCP is not responding at $mcpUrl."
}

if ($CheckOnly) {
    Write-Host "[ok] Docker, .env, API key, and shared directories are ready."
    Write-Host "INFO: Foam-Agent is not running yet. Start it without -CheckOnly when ready."
    Write-Host "PASS: Foam-Agent preflight checks passed (not currently running)." -ForegroundColor Green
    exit 0
}

Write-Host "Starting Foam-Agent container '$ContainerName' ..."
docker rm -f $ContainerName 2>$null | Out-Null
docker run --name $ContainerName `
    -p "${Port}:7860" `
    -v "${dataRoot}:/workspace/data" `
    -v "${sharedRuns}:/home/openfoam/Foam-Agent/runs" `
    --env-file $envFile `
    -e FOAMAGENT_MODEL_PROVIDER=$($envMap["FOAMAGENT_MODEL_PROVIDER"]) `
    -e FOAMAGENT_MODEL_VERSION=$($envMap["FOAMAGENT_MODEL_VERSION"]) `
    $Image `
    foamagent-mcp --transport http --host 0.0.0.0 --port 7860
