[CmdletBinding()]
param(
    [string]$Distro = $(if ($env:OPENFOAM_WSL_DISTRO) { $env:OPENFOAM_WSL_DISTRO } else { "Ubuntu" }),
    [switch]$UseWslRoot,
    [switch]$LaunchInteractive,
    [switch]$InteractiveChild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Get-CleanWslDistros {
    return @(& wsl.exe -l -q 2>$null | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
}

function Resolve-UbuntuDistro {
    param([Parameter(Mandatory = $true)][string]$Requested)

    $distros = Get-CleanWslDistros
    $exact = @($distros | Where-Object { $_.ToLowerInvariant() -eq $Requested.ToLowerInvariant() })
    if ($exact.Count -gt 0) {
        return $exact[0]
    }
    if ($Requested.ToLowerInvariant() -eq "ubuntu") {
        $ubuntu = @($distros | Where-Object { $_.ToLowerInvariant().StartsWith("ubuntu") } | Select-Object -First 1)
        if ($ubuntu.Count -gt 0) {
            return $ubuntu[0]
        }
    }
    $available = if ($distros.Count -gt 0) { $distros -join ", " } else { "none" }
    Fail "WSL distro '$Requested' was not found. Available distros: $available"
}

function ConvertTo-WslPath {
    param([Parameter(Mandatory = $true)][string]$WindowsPath)

    $resolved = (Resolve-Path $WindowsPath).Path
    $drive = $resolved.Substring(0, 1).ToLowerInvariant()
    $rest = $resolved.Substring(2).Replace("\", "/")
    return "/mnt/$drive$rest"
}

if (-not (Get-Command "wsl.exe" -ErrorAction SilentlyContinue)) {
    Fail "wsl.exe was not found. Install WSL2 before running this script."
}

$resolvedDistro = Resolve-UbuntuDistro -Requested $Distro
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$self = $MyInvocation.MyCommand.Path
$defaultWslUser = (& wsl.exe -d $resolvedDistro bash -lc "whoami").Trim()

if ($LaunchInteractive -and -not $InteractiveChild) {
    Write-Host "Opening an interactive PowerShell window for WSL sudo password entry..."
    $argumentList = @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$self`"",
        "-Distro", "`"$resolvedDistro`"",
        "-InteractiveChild"
    )
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $argumentList -PassThru
    Write-Host "Interactive installer started in a new window. Enter your Ubuntu sudo password there."
    Write-Host "After it finishes, run: .\scripts\dev-openfoam-wsl.ps1 -CheckOnly"
    exit 0
}

if (-not $UseWslRoot) {
    $sudoCheck = @(& wsl.exe -d $resolvedDistro bash -lc "sudo -n true >/dev/null 2>&1; echo `$?")
    $sudoExit = [string]($sudoCheck | Select-Object -Last 1)
    if ($sudoExit.Trim() -ne "0" -and -not $InteractiveChild) {
        Fail "Sudo requires your Ubuntu password. Rerun this script with -LaunchInteractive so WSL can prompt you, or use -UseWslRoot."
    }
}

$bashInstaller = Join-Path $scriptRoot "install-openfoam-wsl.sh"
if (-not (Test-Path $bashInstaller)) {
    Fail "Missing bash installer script: $bashInstaller"
}
$wslInstaller = ConvertTo-WslPath -WindowsPath $bashInstaller

Write-Host "Installing OpenFOAM 10 in WSL distro '$resolvedDistro'..."
if ($UseWslRoot) {
    & wsl.exe -d $resolvedDistro -u root env TARGET_USER=$defaultWslUser bash $wslInstaller
} else {
    & wsl.exe -d $resolvedDistro env TARGET_USER=$defaultWslUser bash $wslInstaller
}
if ($LASTEXITCODE -ne 0) {
    Fail "OpenFOAM installation failed. Review the apt/sudo output above and rerun after fixing the reported issue."
}

Write-Host "PASS: OpenFOAM install script completed." -ForegroundColor Green
