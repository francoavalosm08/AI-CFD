# AI Agent Clone And Verification Runbook

Use this when a fresh AI agent, IDE agent, or new machine needs to download the repo and prove it runs cleanly.

## Goal

Clone the project into a stable local path, install normal local dependencies, run the fast fake-mode gate, then run the real local OpenFOAM gate only when WSL/OpenFOAM is available.

Do not use Docker as the first path. Docker/Foam-Agent is optional legacy infrastructure.

## Recommended Windows Location

Use a non-OneDrive path with no spaces:

```powershell
New-Item -ItemType Directory -Force C:\dev | Out-Null
git clone https://github.com/francoavalosm08/AI-CFD.git C:\dev\AI-CFD
Set-Location C:\dev\AI-CFD
git status --short --branch
```

If the repo already exists:

```powershell
Set-Location C:\dev\AI-CFD
git fetch origin main
git pull --ff-only origin main
git status --short --branch
```

Do not copy files through OneDrive as a setup method. Clone or pull from Git.

## Required Tools

The local development path expects:

- Windows PowerShell
- Python launcher `py`
- Node.js 22+ and `npm`
- Gmsh for STEP/STL conversion and mesh generation
- WSL2 Ubuntu + OpenFOAM 10 for real solver runs

Run:

```powershell
.\scripts\dev-check.ps1
```

If Node/npm are missing, install Node 22+ and restart the terminal. If Gmsh is missing, `.msh` uploads can still work, but STEP/STL conversion will fail until Gmsh is installed.

## Fast Clean Verification

Run this first on every fresh clone:

```powershell
.\scripts\local-verify.ps1
```

Then run the broader fast release gate:

```powershell
.\scripts\release-check.ps1
```

This proves backend tests, frontend tests, fake-mode smoke, browser E2E, and local OpenFOAM dry-run smoke.

If browser E2E is not available in the current environment, use:

```powershell
.\scripts\release-check.ps1 -SkipE2E
```

When using `-SkipE2E`, report that browser E2E was skipped. Do not describe that as the full release check.

## Frontend Node Path Note

If `npm` resolves to a blocked bundled Node binary, prepend the installed Node 22 path for that command:

```powershell
cmd /c "set PATH=C:\Program Files\nodejs;%PATH%&& npm run test -- --run"
cmd /c "set PATH=C:\Program Files\nodejs;%PATH%&& npm run build"
```

The project scripts already try to refresh PATH and prefer `C:\Program Files\nodejs`.

## Real OpenFOAM Verification

Check WSL/OpenFOAM first:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
```

If WSL/OpenFOAM is missing on this machine, install the expected local runtime:

```powershell
.\scripts\install-openfoam-wsl.ps1 -UseWslRoot
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
```

Then run the real local acceptance gate:

```powershell
.\scripts\release-v1-local.ps1
```

For the stronger surface-geometry gate:

```powershell
.\scripts\release-v1-local.ps1 -IncludeSurfaceCorpus
.\scripts\release-v1-local.ps1 -IncludeSurfaceCorpus -EnableAggressiveSurfaceRepair
```

These commands prove the current `.msh`, STL, STEP, surface-corpus, and bad-mesh failure paths against local WSL/OpenFOAM.

## Manual App Startup

Fake-mode development:

```powershell
.\scripts\dev-backend.ps1
.\scripts\dev-frontend.ps1
```

Open:

```text
http://localhost:5173
```

Real local OpenFOAM backend:

```powershell
.\scripts\dev-openfoam-backend.ps1
.\scripts\dev-frontend.ps1
```

Use `.msh` for highest reliability. STL/STEP is best effort with geometry preflight and clear failure diagnostics.

## Current Acceptance Expectations

A clean local handoff should be able to report:

- `py -m pytest backend -q`
- frontend Vitest
- frontend production build
- `.\scripts\release-check.ps1` or explicit reason for `-SkipE2E`
- `.\scripts\release-v1-local.ps1 -IncludeSurfaceCorpus` when WSL/OpenFOAM is available
- `.\scripts\release-v1-local.ps1 -IncludeSurfaceCorpus -EnableAggressiveSurfaceRepair` when validating optional MeshFix behavior

Do not claim arbitrary STL/STEP is guaranteed. The target is usable best effort: clean single-body geometry should run, bad geometry should fail with actionable diagnostics.

## Failure Discipline

If a verification command fails:

1. Keep the planned path.
2. Read the generated logs under `.local-data\verify-logs\` and `.local-data\runs\`.
3. Fix the direct cause.
4. Rerun the same failed command.
5. Only claim success after the command exits cleanly.

Do not replace a real OpenFOAM gate with fake mode. Do not hide missing WSL, Gmsh, Node, or OpenFOAM setup behind fake data.
