[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$SampleMeshPath = "",
    [int]$TimeoutSeconds = 90,
    [int]$PollIntervalSeconds = 1
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

function Get-HttpText {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [int]$TimeoutSeconds = 30
    )

    $client = [System.Net.Http.HttpClient]::new()
    try {
        $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
        return $client.GetStringAsync($Uri).GetAwaiter().GetResult()
    } finally {
        $client.Dispose()
    }
}

if (-not (Test-Path $SampleMeshPath)) {
    Fail "Sample mesh not found at '$SampleMeshPath'."
}

try {
    $resolvedMesh = (Resolve-Path $SampleMeshPath).Path
} catch {
    Fail "Could not resolve sample mesh path '$SampleMeshPath'."
}

Write-Host "Checking backend health at $ApiBaseUrl ..."
try {
    $health = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/health"
} catch {
    Fail ("Could not reach $ApiBaseUrl/api/health. Start backend first with scripts/dev-backend.ps1. Details: {0}" -f $_.Exception.Message)
}

if ($health.status -ne "ok") {
    Fail "Health endpoint returned unexpected status '$($health.status)'."
}

if ($health.foam_agent_mode -ne "fake") {
    Fail "Smoke test expects FOAM_AGENT_MODE=fake, but backend reported '$($health.foam_agent_mode)'."
}
Write-Host "[ok] Health check passed (fake mode)."

Write-Host "Uploading sample mesh: $resolvedMesh"
try {
    $upload = Invoke-JsonFileUpload -Uri "$ApiBaseUrl/api/uploads" -FilePath $resolvedMesh
} catch {
    Fail ("Upload failed: {0}" -f $_.Exception.Message)
}

if (-not $upload.id) {
    Fail "Upload response did not contain an upload id."
}
Write-Host "[ok] Upload id: $($upload.id)"

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

Write-Host "Creating run..."
try {
    $run = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/runs" -ContentType "application/json" -Body $runRequest
} catch {
    Fail ("Create run failed: {0}" -f $_.Exception.Message)
}

if (-not $run.id) {
    Fail "Run response did not contain a run id."
}
$runId = $run.id
Write-Host "[ok] Run id: $runId"

$finalStatuses = @("completed", "failed", "cancelled")
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ($true) {
    try {
        $run = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$runId"
    } catch {
        Fail ("Failed to poll run status for '$runId': {0}" -f $_.Exception.Message)
    }

    Write-Host ("Run status: {0}" -f $run.status)
    if ($finalStatuses -contains $run.status) {
        break
    }

    if ((Get-Date) -ge $deadline) {
        Fail "Timed out after $TimeoutSeconds seconds waiting for terminal run status."
    }

    Start-Sleep -Seconds $PollIntervalSeconds
}

if ($run.status -ne "completed") {
    $errorText = if ($run.error) { [string]$run.error } else { "No run.error provided by backend." }
    Fail ("Run ended with status '{0}'. Detail: {1}" -f $run.status, $errorText)
}
Write-Host "[ok] Run reached completed status."

Write-Host "Verifying artifacts..."
try {
    $artifactResponse = Invoke-RestMethod -Method Get -Uri "$ApiBaseUrl/api/runs/$runId/artifacts"
} catch {
    Fail ("Could not fetch artifacts: {0}" -f $_.Exception.Message)
}

$artifacts = @($artifactResponse.artifacts)
if ($artifacts.Count -eq 0) {
    Fail "Run completed but returned zero artifacts."
}

$hasImage = @($artifacts | Where-Object { $_.type -eq "image" }).Count -gt 0
$hasLog = @($artifacts | Where-Object { $_.type -eq "log" }).Count -gt 0
if (-not $hasImage) {
    Fail "Artifacts did not include an image output."
}
if (-not $hasLog) {
    Fail "Artifacts did not include a log output."
}
Write-Host ("[ok] Artifacts found: {0} (image + log present)." -f $artifacts.Count)

Write-Host "Verifying event stream..."
try {
    $eventsContent = Get-HttpText -Uri "$ApiBaseUrl/api/runs/$runId/events" -TimeoutSeconds 30
} catch {
    Fail ("Could not read event stream: {0}" -f $_.Exception.Message)
}

$eventLines = @()
if ($eventsContent) {
    $eventLines = @(
        ($eventsContent -split "`r?`n") |
        Where-Object { $_ -like "data:*" }
    )
}

if ($eventLines.Count -eq 0) {
    Fail "Event stream returned no status events."
}
Write-Host ("[ok] Event stream returned {0} status messages." -f $eventLines.Count)

Write-Host "Verifying cancel endpoint responsiveness..."
try {
    $cancelResult = Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/runs/$runId/cancel"
} catch {
    Fail ("Cancel endpoint failed: {0}" -f $_.Exception.Message)
}

if (-not $cancelResult.id) {
    Fail "Cancel endpoint response was missing run id."
}
Write-Host ("[ok] Cancel endpoint responded with status '{0}'." -f $cancelResult.status)

Write-Host ("PASS: Fake-mode smoke flow succeeded for run {0}." -f $runId) -ForegroundColor Green
