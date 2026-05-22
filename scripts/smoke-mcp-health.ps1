[CmdletBinding()]
param(
    [string]$McpUrl = "http://127.0.0.1:7860/mcp",
    [int]$TimeoutSeconds = 15
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "Checking Foam-Agent MCP health at $McpUrl ..."
try {
    $payload = @{
        jsonrpc = "2.0"
        id = 1
        method = "tools/list"
        params = @{}
    } | ConvertTo-Json -Depth 4 -Compress
    $response = Invoke-RestMethod -Method Post -Uri $McpUrl -ContentType "application/json" -Body $payload -TimeoutSec $TimeoutSeconds
} catch {
    Fail ("Foam-Agent MCP is not reachable. Start scripts/dev-foamagent.ps1 first. Details: {0}" -f $_.Exception.Message)
}

if (-not $response) {
    Fail "Foam-Agent MCP returned an empty response."
}

Write-Host "PASS: Foam-Agent MCP health check succeeded." -ForegroundColor Green
