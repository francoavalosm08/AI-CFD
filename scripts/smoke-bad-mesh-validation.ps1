[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [int]$TimeoutSeconds = 120,
    [int]$PollIntervalSeconds = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
$workDir = Join-Path $repoRoot ".local-data\bad-mesh-validation"
$meshPath = Join-Path $workDir "bad-airfoil.msh"

function Fail {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "FAIL: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-JsonFileUpload {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$FilePath
    )

    $client = [System.Net.Http.HttpClient]::new()
    try {
        $multipart = [System.Net.Http.MultipartFormDataContent]::new()
        $stream = [System.IO.File]::OpenRead($FilePath)
        try {
            $streamContent = [System.Net.Http.StreamContent]::new($stream)
            $streamContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/octet-stream")
            $multipart.Add($streamContent, "file", [System.IO.Path]::GetFileName($FilePath))

            $response = $client.PostAsync($Uri, $multipart).GetAwaiter().GetResult()
            $bodyText = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            if (-not $response.IsSuccessStatusCode) {
                throw "HTTP $([int]$response.StatusCode): $bodyText"
            }
            return ($bodyText | ConvertFrom-Json)
        } finally {
            $stream.Dispose()
            $multipart.Dispose()
        }
    } finally {
        $client.Dispose()
    }
}

New-Item -ItemType Directory -Force -Path $workDir | Out-Null
@'
$MeshFormat
2.2 0 8
$EndMeshFormat
$PhysicalNames
5
2 1 "inlet"
2 2 "outlet"
2 3 "farfield"
2 4 "airfoil"
3 5 "internal"
$EndPhysicalNames
'@ | Set-Content -Path $meshPath -Encoding UTF8

Write-Host "Checking backend health at $ApiBaseUrl ..."
try {
    $health = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/health"
} catch {
    Fail ("Could not reach $ApiBaseUrl/api/health. Start backend first with scripts/dev-openfoam-backend.ps1. Details: {0}" -f $_.Exception.Message)
}

$runnerMode = $null
if ($health.PSObject.Properties.Name -contains "runner_mode") {
    $runnerMode = $health.runner_mode
}
if ([string]::IsNullOrWhiteSpace($runnerMode) -and ($health.PSObject.Properties.Name -contains "foam_agent_mode")) {
    $runnerMode = $health.foam_agent_mode
}
if ($runnerMode -ne "local_openfoam") {
    Fail "Bad-mesh validation smoke expects CFD_RUNNER_MODE=local_openfoam, but backend reported '$runnerMode'."
}

Write-Host "Uploading intentionally invalid airfoil mesh: $meshPath"
$upload = Invoke-JsonFileUpload -Uri "$ApiBaseUrl/api/uploads" -FilePath $meshPath

$runRequest = @{
    spec = @{
        upload_id = $upload.id
        units = "m"
        length_scale = 1
        velocity = 25
        angle_of_attack = 2
        mesh_quality = "balanced"
        max_runtime_minutes = 60
    }
} | ConvertTo-Json -Depth 6

$run = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/runs" -ContentType "application/json" -Body $runRequest
$runId = $run.id
Write-Host "[ok] Run id: $runId"

$finalStatuses = @("completed", "failed", "cancelled")
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ($true) {
    $run = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$runId"
    Write-Host ("Run status: {0}" -f $run.status)
    if ($finalStatuses -contains $run.status) {
        break
    }
    if ((Get-Date) -ge $deadline) {
        Fail "Timed out after $TimeoutSeconds seconds waiting for terminal run status."
    }
    Start-Sleep -Seconds $PollIntervalSeconds
}

if ($run.status -ne "failed") {
    Fail "Bad mesh validation expected run status 'failed', got '$($run.status)'."
}
if (-not ([string]$run.error).Contains("Missing required airfoil_2d physical names: frontAndBack")) {
    Fail "Bad mesh validation error was not readable or did not name the missing frontAndBack patch. Error: $($run.error)"
}

$artifactResponse = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$runId/artifacts"
$names = @($artifactResponse.artifacts | ForEach-Object { $_.display_name })
if (-not ($names -contains "mesh-validation.json")) {
    Fail "Bad mesh validation expected mesh-validation.json artifact."
}
if ($names -contains "solver.log") {
    Fail "Bad mesh validation should fail before solver execution; unexpected solver.log artifact found."
}

Write-Host "PASS: Bad airfoil mesh failed cleanly before OpenFOAM execution." -ForegroundColor Green
