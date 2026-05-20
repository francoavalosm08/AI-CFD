[CmdletBinding()]
param(
    [ValidateSet("backend", "full")]
    [string]$Scope = "full",
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$FrontendBaseUrl = "http://127.0.0.1:5173",
    [int]$BackendStartupTimeoutSeconds = 45,
    [int]$FrontendStartupTimeoutSeconds = 45,
    [switch]$SkipBackendTests,
    [switch]$SkipSmoke,
    [switch]$SkipE2E
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

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
        if ((Test-Path (Join-Path $candidate "node.exe")) -and (Test-Path (Join-Path $candidate "npm.cmd"))) {
            if (-not (($env:Path -split ";") -contains $candidate)) {
                $env:Path = "$candidate;$($env:Path)"
            }
            return
        }
    }
}

function Run-FileScript {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$Arguments = @()
    )

    & powershell -NoProfile -ExecutionPolicy Bypass -File $Path @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Script failed ($Path) with exit code $LASTEXITCODE."
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
        if ($listener) { $listener.Stop() }
    }
}

function Get-Health {
    param([Parameter(Mandatory = $true)][string]$BaseUrl)

    try {
        return Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/health" -TimeoutSec 2
    } catch {
        return $null
    }
}

function Test-HttpOk {
    param([Parameter(Mandatory = $true)][string]$Url)

    try {
        $response = Invoke-WebRequest -Method Get -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400)
    } catch {
        return $false
    }
}

Update-ProcessPathFromEnvironment
Add-NodePathIfPresent

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$backendPath = Join-Path $repoRoot "backend"
$frontendPath = Join-Path $repoRoot "frontend"
$venvPath = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$dataRoot = Join-Path $repoRoot ".local-data"
$devCheckScript = Join-Path $scriptRoot "dev-check.ps1"
$smokeScript = Join-Path $scriptRoot "smoke-fake-run.ps1"

foreach ($requiredScript in @($devCheckScript, $smokeScript)) {
    if (-not (Test-Path $requiredScript)) {
        Fail "Missing helper script: $requiredScript"
    }
}

try {
    $apiUri = [Uri]$ApiBaseUrl
    $frontendUri = [Uri]$FrontendBaseUrl
} catch {
    Fail "ApiBaseUrl or FrontendBaseUrl is not a valid URI."
}

$apiPort = if ($apiUri.IsDefaultPort) { if ($apiUri.Scheme -eq "https") { 443 } else { 80 } } else { $apiUri.Port }
$frontendPort = if ($frontendUri.IsDefaultPort) { if ($frontendUri.Scheme -eq "https") { 443 } else { 80 } } else { $frontendUri.Port }
$bindHost = if ($apiUri.Host -in @("localhost", "127.0.0.1")) { "127.0.0.1" } else { $apiUri.Host }

if ($Scope -eq "full") {
    Write-Host "Step 1/6: Running prerequisite checks (scope: $Scope)..."
    Run-FileScript -Path $devCheckScript
} else {
    Write-Host "Step 1/4: Running prerequisite checks (scope: $Scope)..."
    Run-FileScript -Path $devCheckScript -Arguments @("-BackendOnly")
}

if (-not (Get-Command "py" -ErrorAction SilentlyContinue)) {
    Fail "Python launcher 'py' was not found."
}

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath"
    & py -3 -m venv $venvPath
}

if (-not (Test-Path $venvPython)) {
    Fail "Could not find venv python at $venvPython."
}

Write-Host "Installing backend dependencies..."
Push-Location $backendPath
try {
    & $venvPython -m pip install -e ".[test]"
} finally {
    Pop-Location
}

if (-not $SkipBackendTests) {
    if ($Scope -eq "full") { Write-Host "Step 2/6: Running backend tests..." } else { Write-Host "Step 2/4: Running backend tests..." }
    Push-Location $backendPath
    try {
        & $venvPython -m pytest
        if ($LASTEXITCODE -ne 0) { Fail "Backend tests failed. Fix failing tests before continuing." }
    } finally {
        Pop-Location
    }
} else {
    if ($Scope -eq "full") { Write-Host "Step 2/6: Skipping backend tests by request." } else { Write-Host "Step 2/4: Skipping backend tests by request." }
}

if ($Scope -eq "full") {
    Write-Host "Step 3/6: Running frontend tests..."
    if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) { Fail "Node.js was not found. Run scripts/dev-check.ps1 for installation guidance." }
    if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) { Fail "npm was not found. Run scripts/dev-check.ps1 for installation guidance." }

    Push-Location $frontendPath
    try {
        Write-Host "Installing frontend dependencies..."
        & npm install
        if ($LASTEXITCODE -ne 0) { Fail "npm install failed in frontend. Fix dependency issues and rerun." }

        & npm run test -- --run
        if ($LASTEXITCODE -ne 0) { Fail "Frontend tests failed. Fix tests before continuing." }
    } finally {
        Pop-Location
    }
}

$startedBackend = $false
$backendJob = $null
$startedFrontend = $false
$frontendJob = $null

try {
    if ($Scope -eq "full") { Write-Host "Step 4/6: Ensuring fake-mode backend is available at $ApiBaseUrl ..." } else { Write-Host "Step 3/4: Ensuring fake-mode backend is available at $ApiBaseUrl ..." }
    $health = Get-Health -BaseUrl $ApiBaseUrl
    if ($health -and $health.status -eq "ok" -and $health.foam_agent_mode -eq "fake") {
        Write-Host "[ok] Reusing existing fake-mode backend."
    } else {
        if (-not (Test-PortAvailable -Port $apiPort)) {
            if ($health -and $health.status -eq "ok") {
                Fail "Backend is reachable but not in fake mode (reported '$($health.foam_agent_mode)'). Restart with scripts/dev-backend.ps1."
            }
            Fail "Port $apiPort is in use and $ApiBaseUrl is not healthy. Free the port or pass a different -ApiBaseUrl."
        }

        $backendJob = Start-Job -ScriptBlock {
            param($BackendPath, $DataRoot, $VenvPython, $BindHost, $Port, $PathValue)
            $ErrorActionPreference = "Stop"
            $env:Path = $PathValue
            $env:FOAM_AGENT_MODE = "fake"
            $env:AI_CFD_DATA_ROOT = $DataRoot
            Set-Location $BackendPath
            & $VenvPython -m uvicorn app.main:app --host $BindHost --port $Port
        } -ArgumentList $backendPath, $dataRoot, $venvPython, $bindHost, $apiPort, $env:Path
        $startedBackend = $true

        $deadline = (Get-Date).AddSeconds($BackendStartupTimeoutSeconds)
        while ((Get-Date) -lt $deadline) {
            $health = Get-Health -BaseUrl $ApiBaseUrl
            if ($health -and $health.status -eq "ok" -and $health.foam_agent_mode -eq "fake") { break }
            Start-Sleep -Milliseconds 500
        }

        if (-not ($health -and $health.status -eq "ok" -and $health.foam_agent_mode -eq "fake")) {
            Fail "Timed out waiting for backend health on $ApiBaseUrl. Check backend logs and rerun."
        }

        Write-Host "[ok] Temporary backend started for verification."
    }

    if (-not $SkipSmoke) {
        if ($Scope -eq "full") { Write-Host "Step 5/6: Running fake-mode smoke flow..." } else { Write-Host "Step 4/4: Running fake-mode smoke flow..." }
        Run-FileScript -Path $smokeScript -Arguments @("-ApiBaseUrl", $ApiBaseUrl)
    } else {
        if ($Scope -eq "full") { Write-Host "Step 5/6: Skipping smoke flow by request." } else { Write-Host "Step 4/4: Skipping smoke flow by request." }
    }

    if ($Scope -eq "full" -and -not $SkipE2E) {
        Write-Host "Step 6/6: Running browser E2E workflow..."
        $frontendHealthy = Test-HttpOk -Url $FrontendBaseUrl
        if ($frontendHealthy) {
            Write-Host "[ok] Reusing existing frontend at $FrontendBaseUrl."
        } else {
            if (-not (Test-PortAvailable -Port $frontendPort)) {
                Fail "Frontend port $frontendPort is in use and $FrontendBaseUrl is not healthy. Free the port or pass a different -FrontendBaseUrl."
            }

            $frontendJob = Start-Job -ScriptBlock {
                param($FrontendPath, $Port, $PathValue)
                $ErrorActionPreference = "Stop"
                $env:Path = $PathValue
                Set-Location $FrontendPath
                & npm run dev -- --host 127.0.0.1 --port $Port
            } -ArgumentList $frontendPath, $frontendPort, $env:Path
            $startedFrontend = $true

            $deadline = (Get-Date).AddSeconds($FrontendStartupTimeoutSeconds)
            while ((Get-Date) -lt $deadline) {
                if (Test-HttpOk -Url $FrontendBaseUrl) { $frontendHealthy = $true; break }
                Start-Sleep -Milliseconds 500
            }

            if (-not $frontendHealthy) {
                Fail "Timed out waiting for frontend on $FrontendBaseUrl. Check Vite logs and rerun."
            }
            Write-Host "[ok] Temporary frontend started for browser E2E."
        }

        Push-Location $frontendPath
        try {
            $env:PLAYWRIGHT_BASE_URL = $FrontendBaseUrl
            & npm run test:e2e
            if ($LASTEXITCODE -ne 0) { Fail "Browser E2E tests failed. Fix UI workflow issues before continuing." }
        } finally {
            Remove-Item Env:\PLAYWRIGHT_BASE_URL -ErrorAction SilentlyContinue
            Pop-Location
        }
    } elseif ($Scope -eq "full") {
        Write-Host "Step 6/6: Skipping browser E2E by request."
    }

    Write-Host ("PASS: local verification completed (scope={0})." -f $Scope) -ForegroundColor Green
} finally {
    if ($startedFrontend -and $frontendJob) {
        Stop-Job -Job $frontendJob -ErrorAction SilentlyContinue | Out-Null
        Receive-Job -Job $frontendJob -Keep -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $frontendJob -ErrorAction SilentlyContinue | Out-Null
    }
    if ($startedBackend -and $backendJob) {
        Stop-Job -Job $backendJob -ErrorAction SilentlyContinue | Out-Null
        Receive-Job -Job $backendJob -Keep -ErrorAction SilentlyContinue | Out-Null
        Remove-Job -Job $backendJob -ErrorAction SilentlyContinue | Out-Null
    }
}
