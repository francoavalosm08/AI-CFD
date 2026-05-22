# AI CFD Workbench Project Overview And Runbook

## What This Project Is

AI CFD Workbench is a local browser-based CFD workflow tool. The intended user flow is:

1. Open a local web app.
2. Drop in a geometry or mesh file.
3. Enter external-aerodynamics specifications.
4. Let the backend prepare a deterministic solver prompt/spec.
5. Run either a fake deterministic simulation path or a real Foam-Agent/OpenFOAM path.
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
        | fake mode or MCP mode
        v
Fake runner today, Foam-Agent/OpenFOAM Docker in Phase 3
  http://localhost:7860/mcp
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

- `backend/app/prompt.py`
  - deterministic Foam-Agent prompt builder

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

### Docs

Location: `docs/`

- `docs/PHASES_SUMMARY.md`
  - high-level roadmap

- `docs/PHASE_2_PLANNING_DRAFT.md`
  - local workflow hardening plan

- `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`
  - real Foam-Agent/OpenFOAM implementation plan

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

### MCP Real Mode

Real mode is the Phase 3 target.

Purpose:

- call Foam-Agent MCP
- generate real OpenFOAM cases
- run real OpenFOAM solvers
- generate real logs and visualizations

Environment:

```powershell
FOAM_AGENT_MODE=mcp
FOAM_AGENT_URL=http://127.0.0.1:7860/mcp
```

Status:

- backend MCP client, preflight, provenance, and artifact mirroring are implemented
- Docker/Foam-Agent helper scripts are implemented
- fake-mode regression remains the default automated release path
- real acceptance still requires Docker Desktop running and a real `.env` `OPENAI_API_KEY`

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
  "foam_agent_mode": "fake"
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
28 passed
```

## Current Verified State

As of May 22, 2026:

- Gmsh installed through `winget`.
- `gmsh -version` reports `4.13.1`.
- `scripts/release-check.ps1` passes with 28 backend tests, 4 frontend tests, fake-mode smoke, and Playwright E2E.
- `npm --prefix frontend run build` passes.
- `scripts/dev-foamagent.ps1 -CheckOnly` currently stops because Docker Desktop is not running.
- `scripts/dev-real-backend.ps1 -SkipDependencyInstall` currently stops because `.env` is missing.
- Phase 3 real solver acceptance is pending a real `.env` API key and Docker Desktop.

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

### Docker daemon may be unavailable

Current state:

- Docker CLI is installed.
- Docker daemon may not be running unless Docker Desktop is started.

Mitigation:

- Phase 3 plan adds Docker preflight scripts before any real solver run.

## Operational Notes

- Use fake mode for UI/backend development unless actively testing real OpenFOAM.
- Use `.msh` for the most reliable workflow.
- Use STEP/STL only when Gmsh is available and geometry is clean enough to mesh.
- Real Foam-Agent/OpenFOAM runs will require Docker Desktop and a valid model API key.
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

### Phase 3: Real Solver Integration

In progress. Most code and local scripts are implemented; final acceptance is blocked on environment setup.

Goal:

- Docker-hosted Foam-Agent/OpenFOAM real runs through MCP.

Remaining:

- create `.env` from `.env.example` with a real `OPENAI_API_KEY`
- start Docker Desktop
- run `scripts/dev-foamagent.ps1 -CheckOnly`
- run `scripts/smoke-mcp-health.ps1`
- run `scripts/smoke-real-run.ps1`
- fix any MCP schema or solver issues discovered by the real run

### Phase 4: Docker Reproducibility

Goal:

- standardized Docker/Compose integration path once real mode is stable.

### Phase 5: Release Readiness

Goal:

- CI, release checklist, operational runbook, known-limits documentation.

