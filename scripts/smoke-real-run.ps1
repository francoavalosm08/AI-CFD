[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$SampleMeshPath = "",
    [int]$TimeoutSeconds = 1200,
    [int]$PollIntervalSeconds = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($SampleMeshPath)) {
    $SampleMeshPath = Join-Path $repoRoot "samples\wing.msh"
}

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

if (-not (Test-Path $SampleMeshPath)) {
    Fail "Sample mesh not found at '$SampleMeshPath'."
}

$resolvedMesh = (Resolve-Path $SampleMeshPath).Path

Write-Host "Checking backend health at $ApiBaseUrl ..."
try {
    $health = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/health"
} catch {
    Fail ("Could not reach $ApiBaseUrl/api/health. Start scripts/dev-real-backend.ps1 first. Details: {0}" -f $_.Exception.Message)
}

if ($health.foam_agent_mode -ne "mcp") {
    Fail "Real smoke test expects FOAM_AGENT_MODE=mcp, but backend reported '$($health.foam_agent_mode)'."
}
Write-Host "[ok] Backend is in MCP mode."

Write-Host "Uploading sample mesh: $resolvedMesh"
$upload = Invoke-JsonFileUpload -Uri "$ApiBaseUrl/api/uploads" -FilePath $resolvedMesh
$runRequest = @{
    spec = @{
        upload_id = $upload.id
        units = "m"
        length_scale = 1
        velocity = 25
        angle_of_attack = 3
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

$artifactResponse = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$runId/artifacts"
$artifacts = @($artifactResponse.artifacts)
$artifactNames = @($artifacts | ForEach-Object { $_.display_name })

if ($run.status -ne "completed") {
    $errorText = if ($run.error) { [string]$run.error } else { "No run.error provided by backend." }
    Write-Host "Run failed. Error: $errorText"
    Write-Host ("Artifacts: {0}" -f (($artifactNames -join ", ")))
    Write-Host "Inspect provenance JSON under data/runs/$runId (foamagent-*.json)."
    Fail ("Run ended with status '{0}'." -f $run.status)
}

$hasLog = @($artifacts | Where-Object { $_.type -eq "log" }).Count -gt 0
if (-not $hasLog) {
    Fail "Run completed but no log artifacts were discovered."
}

Write-Host ("PASS: Real-mode smoke run succeeded. Artifacts: {0}" -f ($artifactNames -join ", ")) -ForegroundColor Green
