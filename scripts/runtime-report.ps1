[CmdletBinding()]
param(
    [string]$OutputPath = "",
    [string]$Distro = $(if ($env:OPENFOAM_WSL_DISTRO) { $env:OPENFOAM_WSL_DISTRO } else { "" }),
    [string]$Bashrc = $(if ($env:OPENFOAM_BASHRC) { $env:OPENFOAM_BASHRC } else { "/opt/openfoam*/etc/bashrc" })
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Update-ProcessPathFromEnvironment {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machinePath, $userPath) | Where-Object { $_ }) -join ";"
}

function Get-ToolReport {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string[]]$VersionArguments = @("--version")
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        return @{
            available = $false
            path = $null
            version = $null
        }
    }

    $version = $null
    try {
        $raw = & $command.Source @VersionArguments 2>$null
        if (-not $raw -and $Name -eq "gmsh") {
            $raw = & $command.Source "--version" 2>$null
            if (-not $raw) {
                $stdoutPath = Join-Path ([System.IO.Path]::GetTempPath()) "ai-cfd-gmsh-version.out"
                $stderrPath = Join-Path ([System.IO.Path]::GetTempPath()) "ai-cfd-gmsh-version.err"
                Remove-Item $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
                $process = Start-Process -FilePath $command.Source -ArgumentList "--version" -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -Wait -PassThru -WindowStyle Hidden
                if ($process.ExitCode -eq 0 -and (Test-Path $stdoutPath)) {
                    $raw = (Get-Content $stdoutPath -Raw).Trim()
                }
                Remove-Item $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
            }
        }
        if ($raw -is [Array]) {
            $version = [string]($raw | Select-Object -First 1)
        } else {
            $version = [string]$raw
        }
    } catch {
        $version = "unknown"
    }

    return @{
        available = $true
        path = [string]$command.Source
        version = $version
    }
}

function Get-DetectedUbuntuDistro {
    if (-not (Get-Command "wsl.exe" -ErrorAction SilentlyContinue)) {
        return ""
    }
    $distros = @(& wsl.exe -l -q 2>$null | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
    $ubuntu = @($distros | Where-Object { $_.ToLowerInvariant().StartsWith("ubuntu") } | Select-Object -First 1)
    if ($ubuntu.Count -gt 0) {
        return $ubuntu[0]
    }
    return ""
}

function Invoke-GitText {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
        return $null
    }
    try {
        $raw = & git @Arguments 2>$null
        return (($raw | Out-String).Trim())
    } catch {
        return $null
    }
}

function Get-WslOpenFoamReport {
    param(
        [string]$SelectedDistro,
        [string]$OpenFoamBashrc
    )

    $wsl = Get-Command "wsl.exe" -ErrorAction SilentlyContinue
    if (-not $wsl) {
        return @{
            available = $false
            distro = $SelectedDistro
            distros = @()
            openfoam = @{ available = $false; version = $null; commands = @{} }
            raw = ""
        }
    }

    $distros = @(& wsl.exe -l -q 2>$null | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
    if ([string]::IsNullOrWhiteSpace($SelectedDistro)) {
        $SelectedDistro = Get-DetectedUbuntuDistro
    }

    $commands = @(
        "gmshToFoam",
        "checkMesh",
        "simpleFoam",
        "surfaceCheck",
        "blockMesh",
        "surfaceFeatures",
        "snappyHexMesh",
        "foamToVTK"
    )
    $bash = @"
set +u
source $OpenFoamBashrc >/dev/null 2>&1 || true
printf 'WM_PROJECT_VERSION='
printenv WM_PROJECT_VERSION 2>/dev/null || printf 'unknown'
printf '\n'
if command -v gmshToFoam >/dev/null 2>&1; then printf 'gmshToFoam=available\n'; else printf 'gmshToFoam=missing\n'; fi
if command -v checkMesh >/dev/null 2>&1; then printf 'checkMesh=available\n'; else printf 'checkMesh=missing\n'; fi
if command -v simpleFoam >/dev/null 2>&1; then printf 'simpleFoam=available\n'; else printf 'simpleFoam=missing\n'; fi
if command -v surfaceCheck >/dev/null 2>&1; then printf 'surfaceCheck=available\n'; else printf 'surfaceCheck=missing\n'; fi
if command -v blockMesh >/dev/null 2>&1; then printf 'blockMesh=available\n'; else printf 'blockMesh=missing\n'; fi
if command -v surfaceFeatures >/dev/null 2>&1; then printf 'surfaceFeatures=available\n'; else printf 'surfaceFeatures=missing\n'; fi
if command -v snappyHexMesh >/dev/null 2>&1; then printf 'snappyHexMesh=available\n'; else printf 'snappyHexMesh=missing\n'; fi
if command -v foamToVTK >/dev/null 2>&1; then printf 'foamToVTK=available\n'; else printf 'foamToVTK=missing\n'; fi
"@

    $raw = ""
    if (-not [string]::IsNullOrWhiteSpace($SelectedDistro)) {
        try {
            $raw = ((& wsl.exe -d $SelectedDistro -- bash -lc $bash 2>&1 | Out-String).Trim())
        } catch {
            $raw = [string]$_
        }
    }

    $openfoamCommands = @{}
    foreach ($command in $commands) {
        $openfoamCommands[$command] = @{ available = $false; path = $null }
    }
    $version = $null
    foreach ($line in ($raw -split "`r?`n")) {
        if ($line -match "^WM_PROJECT_VERSION=(?<version>.+)$") {
            $version = $Matches["version"]
        }
        foreach ($command in $commands) {
            if ($line -match "^$command=available(?::(?<path>.+))?$") {
                $path = if ($Matches["path"]) { $Matches["path"] } else { $null }
                $openfoamCommands[$command] = @{ available = $true; path = $path }
            } elseif ($line -match "^$command=missing$") {
                $openfoamCommands[$command] = @{ available = $false; path = $null }
            }
        }
    }

    $openfoamAvailable = @($openfoamCommands.Values | Where-Object { $_.available }).Count -ge 3
    return @{
        available = $true
        path = [string]$wsl.Source
        distro = $SelectedDistro
        distros = $distros
        openfoam = @{
            available = $openfoamAvailable
            bashrc = $OpenFoamBashrc
            version = $version
            commands = $openfoamCommands
        }
        raw = $raw
    }
}

Update-ProcessPathFromEnvironment

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $repoRoot ".local-data\runtime-report.json"
}
$resolvedOutputPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $repoRoot $OutputPath }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedOutputPath) | Out-Null

$report = @{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    repo = @{
        root = $repoRoot
        branch = Invoke-GitText -Arguments @("branch", "--show-current")
        commit = Invoke-GitText -Arguments @("rev-parse", "HEAD")
        status_short = Invoke-GitText -Arguments @("status", "--short")
    }
    windows = @{
        os = (Get-CimInstance Win32_OperatingSystem | Select-Object -First 1 -ExpandProperty Caption)
        version = [Environment]::OSVersion.VersionString
        powershell = $PSVersionTable.PSVersion.ToString()
        machine = $env:COMPUTERNAME
    }
    tools = @{
        py = Get-ToolReport -Name "py" -VersionArguments @("--version")
        node = Get-ToolReport -Name "node" -VersionArguments @("--version")
        npm = Get-ToolReport -Name "npm" -VersionArguments @("--version")
        gmsh = Get-ToolReport -Name "gmsh" -VersionArguments @("--version")
        git = Get-ToolReport -Name "git" -VersionArguments @("--version")
    }
    wsl = Get-WslOpenFoamReport -SelectedDistro $Distro -OpenFoamBashrc $Bashrc
}

$report | ConvertTo-Json -Depth 12 | Set-Content -Path $resolvedOutputPath -Encoding UTF8
Write-Host "Runtime report written to $resolvedOutputPath"
