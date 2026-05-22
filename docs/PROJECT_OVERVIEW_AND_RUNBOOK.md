# AI CFD Workbench Project Overview And Runbook

## What This Project Is

AI CFD Workbench is a local browser-based CFD workflow tool. The intended user flow is:

1. Open a local web app.
2. Drop in a geometry or mesh file.
3. Enter external-aerodynamics specifications.
4. Let the backend prepare a deterministic solver prompt/spec.
5. Run either a fake deterministic simulation path or the local OpenFOAM path.
6. View status, logs, images, residual data, and downloadable artifacts in the browser.

The current app is focused on **external aerodynamics**. Heat transfer, vibration, Ansys, and aeroelastic coupling are intentionally deferred.

## Current Architecture

```text
Browser UI (React + Vite)
  http://localhost:5173
        |
        | /api proxy
        v
FastAPI backend
  http://localhost:8000
        |
        | fake mode, local OpenFOAM mode, or optional MCP mode
        v
Fake runner; local OpenFOAM runner through WSL2 Ubuntu/native shell; optional Foam-Agent MCP
```

## What Has Been Built

### Frontend

Location: `frontend/`

Built with:

- React
- TypeScript
- Vite
- lucide-react icons
- Vitest unit tests
- Playwright browser E2E test

Main files:

- `frontend/src/App.tsx`
  - drag/drop upload UI
  - external-aero form
  - run controls
  - status display
  - visualization/log/download dashboard

- `frontend/src/client.ts`
  - API client helpers
  - default simulation spec
  - artifact URL builder
  - status formatting

- `frontend/src/types.ts`
  - shared frontend API types

- `frontend/tests/`
  - unit tests for client helpers and initial UI

- `frontend/e2e/workbench.spec.ts`
  - browser-level fake-mode workflow test

### Backend

Location: `backend/`

Built with:

- FastAPI
- Pydantic
- SQLite
- httpx
- pytest

Main files:

- `backend/app/main.py`
  - FastAPI app
  - upload endpoint
  - run endpoint
  - event stream endpoint
  - artifact endpoint
  - cancellation endpoint
  - static frontend mount for production builds

- `backend/app/schemas.py`
  - `SimulationSpec`
  - `RunStatus`
  - `UploadRecord`
  - `RunRecord`
  - `Artifact`

- `backend/app/files.py`
  - upload type detection for `.msh`, `.stl`, `.step`, `.stp`, `.zip`

- `backend/app/mesh.py`
  - Gmsh conversion helper for STEP/STL to `.msh`
  - clear conversion failure messages for missing Gmsh, missing volume meshes, missing physical names, and bad geometry

- `backend/app/prompt.py`
  - deterministic Foam-Agent prompt builder

- `backend/app/openfoam/`
  - deterministic OpenFOAM case builder
  - WSL path/preflight helpers
  - local command runner with dry-run mode
  - residual/log artifact helpers

- `backend/app/jobs.py`
  - run execution orchestration
  - preprocessing
  - status events
  - prompt recording
  - artifact discovery

- `backend/app/foam_agent.py`
  - fake runner
  - MCP runner for real Foam-Agent/OpenFOAM mode
  - JSON and SSE MCP response parsing
  - MCP provenance JSON writing
  - Foam-Agent artifact mirroring helpers

- `backend/app/preflight.py`
  - real-mode checks for `OPENAI_API_KEY`, MCP reachability, and shared run directory access

- `backend/app/errors.py`
  - shared Foam-Agent exception type

- `backend/app/store.py`
  - SQLite-backed repository for uploads and runs

### Scripts

Location: `scripts/`

Current workflow scripts:

- `scripts/dev-check.ps1`
  - checks Python, Node, npm, and Gmsh
  - refreshes PATH from Windows machine/user environment

- `scripts/dev-backend.ps1`
  - starts local backend in fake mode
  - uses `.local-data/` for local run data

- `scripts/dev-frontend.ps1`
  - starts Vite frontend

- `scripts/smoke-fake-run.ps1`
  - calls the real backend API
  - uploads sample `.msh`
  - creates a fake-mode run
  - verifies completed status, artifacts, events, and cancel endpoint

- `scripts/local-verify.ps1`
  - full local verification entrypoint
  - runs backend tests, frontend tests, smoke flow, and browser E2E

- `scripts/release-check.ps1`
  - release-readiness wrapper around `local-verify.ps1`

- `scripts/dev-openfoam-wsl.ps1`
  - checks WSL2 Ubuntu and OpenFOAM command availability

- `scripts/dev-openfoam-backend.ps1`
  - starts FastAPI in `CFD_RUNNER_MODE=local_openfoam`
  - supports `-DryRun` for no-solver case-generation acceptance

- `scripts/smoke-local-openfoam.ps1`
  - uploads a `.msh`, creates a local OpenFOAM run, and verifies command/case artifacts

- `scripts/dev-foamagent.ps1`
  - starts or preflights Foam-Agent Docker on port `7860`

- `scripts/dev-real-backend.ps1`
  - starts FastAPI in `FOAM_AGENT_MODE=mcp`

- `scripts/smoke-mcp-health.ps1`
  - checks the MCP `tools/list` endpoint

- `scripts/smoke-real-run.ps1`
  - opt-in real `.msh` solver acceptance flow

### Samples

Location: `samples/`

- `samples/wing.msh`
  - sample mesh used by smoke tests and browser E2E

- `samples/external_box.geo`
  - Gmsh source for the first real WSL/OpenFOAM acceptance mesh
  - generate the disposable `.msh` with `gmsh samples\external_box.geo -3 -format msh2 -o .local-data\external_box.msh`

### Docs

Location: `docs/`

- `docs/PHASES_SUMMARY.md`
  - high-level roadmap

- `docs/PHASE_2_PLANNING_DRAFT.md`
  - local workflow hardening plan

- `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`
  - local OpenFOAM no-API implementation plan

- `docs/PROJECT_OVERVIEW_AND_RUNBOOK.md`
  - this file

## Supported Inputs Today

The upload API accepts:

- `.msh`
  - treated as a Gmsh mesh
  - most reliable path today

- `.stl`
  - treated as a surface mesh
  - converted through Gmsh when creating a run

- `.step` / `.stp`
  - treated as CAD input
  - intended to be converted through Gmsh

- `.zip`
  - treated as a prebuilt OpenFOAM case import path
  - accepted by upload detection, but not the primary optimized path yet

## Current Modes

### Fake Mode

Fake mode is the current default.

Purpose:

- fast UI/backend development
- deterministic tests
- no Docker requirement
- no API cost
- no OpenFOAM runtime dependency

Environment:

```powershell
FOAM_AGENT_MODE=fake
AI_CFD_DATA_ROOT=.local-data
```

What it does:

- accepts the uploaded file
- builds the same style of run/prompt metadata
- writes fake `solver.log`
- writes fake `residuals.csv`
- writes fake `pressure.png`
- marks the run completed

### Local OpenFOAM Mode

Local OpenFOAM mode is now the Phase 3 primary path.

Purpose:

- generate real OpenFOAM cases from deterministic templates
- run real OpenFOAM solvers
- generate real logs and visualizations
- avoid runtime API keys

Environment:

```powershell
CFD_RUNNER_MODE=local_openfoam
OPENFOAM_RUNTIME=wsl
```

Status:

- deterministic case builder, command manifest, dry-run runner, parsers, and job wiring are implemented
- WSL preflight and local smoke scripts are implemented
- dry-run acceptance does not require WSL/OpenFOAM
- WSL2 Ubuntu/OpenFOAM 10 is installed and sourceable on this development machine
- the first real sample smoke passed using `.local-data/external_box.msh`
- does not require `.env` or `OPENAI_API_KEY`

Dry-run startup:

```powershell
.\scripts\dev-openfoam-backend.ps1 -DryRun
.\scripts\smoke-local-openfoam.ps1 -DryRun
```

Real local startup after OpenFOAM installation:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath <valid-external-aero-volume.msh>
```

Committed sample acceptance flow:

```powershell
gmsh samples\external_box.geo -3 -format msh2 -o .local-data\external_box.msh
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\external_box.msh -TimeoutSeconds 300
```

### Optional MCP Foam-Agent Mode

This mode was implemented during the earlier Phase 3 path. It remains optional.

Purpose:

- call Foam-Agent MCP
- let Foam-Agent/LLM plan and write cases
- mirror logs/provenance/artifacts

Status:

- backend MCP client, preflight, provenance, and artifact mirroring are implemented
- Docker/Foam-Agent helper scripts are implemented
- fake-mode regression remains the default automated release path
- optional real acceptance still requires Docker Desktop running and a real `.env` `OPENAI_API_KEY`

## How To Run The App Locally

### 1. Check prerequisites

```powershell
.\scripts\dev-check.ps1
```

Expected:

- Python launcher found
- Node.js found
- npm found
- Gmsh found

### 2. Start backend

```powershell
.\scripts\dev-backend.ps1
```

Backend URL:

```text
http://localhost:8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected response:

```json
{
  "status": "ok",
  "foam_agent_mode": "fake",
  "runner_mode": "fake"
}
```

### 3. Start frontend

```powershell
.\scripts\dev-frontend.ps1
```

Frontend URL:

```text
http://localhost:5173
```

### 4. Open the app

```powershell
Start-Process http://localhost:5173
```

## How To Verify Everything

### Full release check

```powershell
.\scripts\release-check.ps1
```

This runs:

- prerequisite checks
- backend pytest suite
- frontend Vitest suite
- fake-mode API smoke flow
- Playwright browser E2E workflow
- local OpenFOAM dry-run smoke flow

Expected final line:

```text
Release check passed.
```

### Frontend production build

```powershell
cd frontend
npm run build
```

Expected:

```text
✓ built
```

### Backend tests only

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```

Expected:

```text
50 passed
```

## Current Verified State

As of May 22, 2026:

- Gmsh installed through `winget`.
- `gmsh -version` reports `4.13.1`.
- WSL distro `Ubuntu-22.04` has OpenFOAM 10 installed under `/opt/openfoam10`.
- `scripts/dev-openfoam-wsl.ps1 -CheckOnly` passes and finds `gmshToFoam`, `checkMesh`, `simpleFoam`, and `foamToVTK`.
- A real local OpenFOAM sample smoke reached `completed` using a mesh generated from `samples/external_box.geo`.
- Real WSL runs stage execution under `/tmp/ai-cfd-workbench/<run_id>/case` and copy the case back into the Windows run directory before artifact packaging.
- `scripts/release-check.ps1` passes with backend tests, frontend tests, fake-mode smoke, Playwright E2E, and local OpenFOAM dry-run smoke.
- `npm --prefix frontend run build` passes.
- Optional Foam-Agent acceptance currently stops because Docker Desktop is not running and `.env` is missing.
- Local OpenFOAM case generation, dry-run acceptance, WSL preflight, and first real sample smoke are in place.

## API Surface

### Upload file

```http
POST /api/uploads
```

Returns an `UploadRecord` with:

- `id`
- `original_name`
- `stored_path`
- `kind`
- `created_at`

### Create run

```http
POST /api/runs
```

Body:

```json
{
  "spec": {
    "upload_id": "...",
    "units": "m",
    "length_scale": 1,
    "velocity": 25,
    "angle_of_attack": 4
  }
}
```

Returns a `RunRecord`.

### Get run

```http
GET /api/runs/{run_id}
```

### Stream run events

```http
GET /api/runs/{run_id}/events
```

Uses Server-Sent Events.

### List run artifacts

```http
GET /api/runs/{run_id}/artifacts
```

### Download artifact

```http
GET /api/artifacts/{artifact_id}
```

### Cancel run

```http
POST /api/runs/{run_id}/cancel
```

## Data Layout

Local fake-mode development writes to:

```text
.local-data/
```

Docker/real-mode shared data is intended to write to:

```text
data/
```

Important directories:

```text
.local-data/uploads/
.local-data/runs/
.local-data/workbench.sqlite3

data/uploads/
data/runs/
data/foamagent-runs/
```

Both `.local-data/` and `data/` are gitignored.

## Testing Strategy

The project uses layered verification:

1. **Unit tests**
   - file type detection
   - prompt generation
   - artifact discovery
   - repository persistence
   - API behavior
   - frontend helpers and initial UI

2. **Smoke test**
   - real backend API
   - sample mesh upload
   - run creation
   - terminal status polling
   - artifact presence
   - event stream behavior
   - cancel endpoint response

3. **Browser E2E**
   - opens Vite UI
   - uploads sample mesh
   - edits aero spec
   - starts run
   - verifies completed dashboard artifacts

4. **Production build**
   - TypeScript build
   - Vite bundle

## Important Risks Already Found And Fixed

### Native number input validation blocked valid values

Problem:

- `velocity` used `min="0.01"` and `step="0.1"`.
- Browser validation rejected values like `31.5` because valid values were offset from `0.01`.

Fix:

- changed engineering decimal fields to `step="any"` where appropriate.
- added Playwright E2E to catch this class of bug.

### Tool scripts used stale PATH after Gmsh install

Problem:

- Gmsh installed successfully, but existing shells could not see it.
- `dev-check` still warned that Gmsh was missing.

Fix:

- helper scripts now refresh process PATH from Windows Machine/User environment.
- `dev-check` reports `Gmsh: 4.13.1`.

### Optional Docker daemon may be unavailable

Current state:

- Docker CLI is installed.
- Docker daemon may not be running unless Docker Desktop is started.

Mitigation:

- Optional Foam-Agent/MCP scripts include Docker preflight checks.

## Operational Notes

- Use fake mode for UI/backend development unless actively testing real OpenFOAM.
- Use `.msh` for the most reliable workflow.
- Use STEP/STL only when Gmsh is available and geometry is clean enough to create a named volume mesh.
- For production V1 airfoil meshes, follow `docs/GMSH_AIRFOIL_2D_TEMPLATE.md`.
- Planned local OpenFOAM runs should not require an API key.
- Optional Foam-Agent/OpenFOAM runs require Docker Desktop and a valid model API key.
- Do not commit `.env`, `data/`, `.local-data/`, `node_modules/`, or build outputs.

## Roadmap

### Phase 1: Local Non-Docker Bootstrap

Complete.

Result:

- working local backend
- working local frontend
- fake-mode upload/run/artifact flow

### Phase 2: Solidify Local Workflow

Mostly complete.

Result:

- scripts for dev check, local backend, local frontend, smoke, local verify, release check
- Gmsh installed and detected
- browser E2E added

### Phase 3: Local OpenFOAM Real Solver Integration

V1 candidate complete for the current local NACA/OpenFOAM validation path. The plan has pivoted away from required Foam-Agent/API-key execution.

Goal:

- local OpenFOAM real runs without runtime API keys.

Implemented:

- add WSL2/OpenFOAM preflight
- add deterministic case generation
- add command manifest and dry-run mode
- add local OpenFOAM runner integration
- add no-API smoke scripts
- keep optional MCP mode passing but off the primary path
- install/source OpenFOAM 10 in WSL `Ubuntu-22.04`
- complete the first real `.msh` local OpenFOAM smoke using `samples/external_box.geo`
- complete NACA 4412 airfoil validation with `checkMesh`, pressure/velocity/residual/force coefficient artifacts, and OpenFOAM-derived `Cl/Cd/Cm`
- add production `.msh` physical-name guidance in `docs/GMSH_AIRFOIL_2D_TEMPLATE.md`
- improve STEP/STL mesh-prep error handling while keeping `.msh` as the first-class path
- add browser inspection for generated PNG artifacts

Remaining:

- test more real user-provided `.msh` files against the documented physical-name contract
- add richer vtk.js/PyVista-style browser visualization after VTK/log artifacts are stable

### Phase 4: Runtime Reproducibility

Goal:

- standardized WSL/OpenFOAM setup checks, Windows Gmsh visibility checks, and optional Docker/Compose parity once local real mode is stable.

### Phase 5: Release Readiness

Goal:

- CI, release checklist, operational runbook, known-limits documentation. GitHub Actions now runs the frontend build and fast `release-check.ps1` gate; local quality gates also include NACA smoke and bad-mesh smoke.

