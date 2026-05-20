[CmdletBinding()]
param(
    [switch]$BackendOnly
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

function Get-ToolVersion {
    param([Parameter(Mandatory = $true)][string]$CommandName)

    try {
        $raw = & $CommandName --version 2>$null
        if ($raw -is [Array]) {
            return ($raw | Select-Object -First 1)
        }
        return [string]$raw
    } catch {
        return "unknown"
    }
}

Update-ProcessPathFromEnvironment

$requiredTools = @(
    @{ Name = "py"; Label = "Python launcher (py)" }
)

if (-not $BackendOnly) {
    Add-NodePathIfPresent
    $requiredTools += @(
        @{ Name = "node"; Label = "Node.js" },
        @{ Name = "npm"; Label = "npm" }
    )
} else {
    Write-Host "Backend-only mode enabled: skipping Node.js and npm checks."
}

$missing = @()
foreach ($tool in $requiredTools) {
    $command = Get-Command $tool.Name -ErrorAction SilentlyContinue
    if (-not $command) {
        Write-Host "[missing] $($tool.Label): '$($tool.Name)' is not on PATH." -ForegroundColor Red
        $missing += $tool.Name
        continue
    }

    $version = Get-ToolVersion -CommandName $tool.Name
    Write-Host "[ok] $($tool.Label): $version"
}

if ($missing.Count -gt 0) {
    Write-Error ("Missing required tools: {0}. Install them and rerun this check." -f ($missing -join ", "))
    exit 1
}

if (-not $BackendOnly) {
    $nodeVersionRaw = Get-ToolVersion -CommandName "node"
    if ($nodeVersionRaw -match "v?(?<major>\d+)") {
        $major = [int]$Matches["major"]
        if ($major -lt 22) {
            Write-Error "Node.js 22+ is required for local development. Found: $nodeVersionRaw"
            exit 1
        }
    }
}

$gmsh = Get-Command "gmsh" -ErrorAction SilentlyContinue
if ($gmsh) {
    $gmshVersion = (& gmsh -version 2>$null | Select-Object -First 1)
    Write-Host "[ok] Gmsh: $gmshVersion"
} else {
    Write-Warning "Gmsh not found. .msh uploads still work, but STEP/STL conversion will fail until Gmsh is installed."
}

Write-Host "Environment check passed." -ForegroundColor Green

