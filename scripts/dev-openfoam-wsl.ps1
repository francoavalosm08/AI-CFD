[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [string]$Distro = $(if ($env:OPENFOAM_WSL_DISTRO) { $env:OPENFOAM_WSL_DISTRO } else { "Ubuntu" }),
    [string]$Bashrc = $(if ($env:OPENFOAM_BASHRC) { $env:OPENFOAM_BASHRC } else { "/opt/openfoam*/etc/bashrc" })
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command "wsl.exe" -ErrorAction SilentlyContinue)) {
    Fail "wsl.exe was not found. Install WSL2 and Ubuntu before running local OpenFOAM."
}
Write-Host "[ok] wsl.exe found."

$distros = @(& wsl.exe -l -q 2>$null | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
if ($LASTEXITCODE -ne 0) {
    Fail "Could not list WSL distros. Run 'wsl.exe -l -v' manually to inspect WSL."
}

$matchingDistro = @($distros | Where-Object { $_.ToLowerInvariant() -eq $Distro.ToLowerInvariant() })
if ($matchingDistro.Count -eq 0 -and $Distro.ToLowerInvariant() -eq "ubuntu") {
    $matchingDistro = @($distros | Where-Object { $_.ToLowerInvariant().StartsWith("ubuntu") } | Select-Object -First 1)
    if ($matchingDistro.Count -gt 0) {
        Write-Host "[info] Using detected Ubuntu distro '$($matchingDistro[0])'."
        $Distro = $matchingDistro[0]
    }
}
if ($matchingDistro.Count -eq 0) {
    $available = ($distros -join ", ")
    if ([string]::IsNullOrWhiteSpace($available)) {
        $available = "none"
    }
    Fail "WSL distro '$Distro' was not found. Available distros: $available"
}
Write-Host "[ok] WSL distro '$Distro' found."

$windowsGmsh = Get-Command "gmsh" -ErrorAction SilentlyContinue
if ($windowsGmsh) {
    $gmshVersion = (& gmsh -version 2>$null | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($gmshVersion)) {
        $gmshVersion = $windowsGmsh.Source
    }
    Write-Host "[ok] Windows Gmsh found: $gmshVersion"
} else {
    Write-Warning "Windows Gmsh was not found on PATH. Existing premeshed .msh uploads can still run, but NACA generation and STEP/STL conversion need Gmsh."
}

$requiredCommands = @("gmshToFoam", "checkMesh", "simpleFoam")
$optionalCommands = @("foamToVTK")
$requiredCheck = (($requiredCommands + $optionalCommands) | ForEach-Object { "command -v $_" }) -join " && "
$bashCommand = "set +u; source $Bashrc >/dev/null 2>&1 || true; $requiredCheck"

Write-Host "Checking OpenFOAM environment in WSL ($Distro) ..."
$checkOutput = & wsl.exe -d $Distro bash -lc $bashCommand 2>&1
if ($LASTEXITCODE -ne 0) {
    $requiredOnly = ($requiredCommands | ForEach-Object { "command -v $_" }) -join " && "
    $requiredCommand = "set +u; source $Bashrc >/dev/null 2>&1 || true; $requiredOnly"
    $requiredOutput = & wsl.exe -d $Distro bash -lc $requiredCommand 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail ("OpenFOAM is not ready. Could not source '{0}' and find required commands: {1}. Output: {2}" -f $Bashrc, ($requiredCommands -join ", "), ($requiredOutput -join "`n"))
    }

    Write-Warning ("Required OpenFOAM commands are available, but optional commands are missing: {0}. VTK export may be skipped. Output: {1}" -f ($optionalCommands -join ", "), ($checkOutput -join "`n"))
} else {
    Write-Host "[ok] Required and optional OpenFOAM commands found."
}

Write-Host "PASS: WSL/OpenFOAM preflight completed for distro '$Distro'." -ForegroundColor Green

if (-not $CheckOnly) {
    Write-Host "This script only performs preflight checks today. Start the backend with scripts/dev-openfoam-backend.ps1."
}
