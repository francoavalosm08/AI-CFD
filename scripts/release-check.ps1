[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$FrontendBaseUrl = "http://127.0.0.1:5173",
    [switch]$SkipSmoke,
    [switch]$SkipE2E
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$localVerifyScript = Join-Path $scriptRoot "local-verify.ps1"

if (-not (Test-Path $localVerifyScript)) {
    throw "Missing script: $localVerifyScript"
}

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $localVerifyScript,
    "-Scope", "full",
    "-ApiBaseUrl", $ApiBaseUrl,
    "-FrontendBaseUrl", $FrontendBaseUrl
)

if ($SkipSmoke) {
    $arguments += "-SkipSmoke"
}
if ($SkipE2E) {
    $arguments += "-SkipE2E"
}

Write-Host "Running release check (backend tests + frontend tests + smoke + browser E2E)..."
& powershell @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Release check failed."
}

Write-Host "Release check passed." -ForegroundColor Green

