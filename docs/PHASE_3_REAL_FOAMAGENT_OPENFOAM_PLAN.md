# Phase 3 Real Foam-Agent/OpenFOAM Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` if available, or `superpowers:executing-plans` to implement this task-by-task. Use TDD for code changes and verify every task before marking it complete.

**Goal:** Move AI CFD Workbench from fake-mode execution to a real Docker-hosted Foam-Agent/OpenFOAM solver path while keeping local IDE development fast.

**Architecture:** React stays on `localhost:5173`, FastAPI stays on `localhost:8000`, and Foam-Agent/OpenFOAM runs in Docker on `localhost:7860`. The backend switches from `FOAM_AGENT_MODE=fake` to `FOAM_AGENT_MODE=mcp` for real runs, calls Foam-Agent MCP tools, and mirrors generated case artifacts into the app run directory for the existing HTML dashboard.

**Tech Stack:** FastAPI, React/Vite, SQLite, PowerShell, Docker Desktop, Foam-Agent Docker image `leoyue123/foamagent:v2.0.0`, Foundation OpenFOAM v10, Gmsh, OpenAI API.

---

## Decisions Locked

- Use Docker for Foam-Agent/OpenFOAM real execution.
- Keep the app itself IDE-first: backend and frontend run locally for development.
- Keep `FOAM_AGENT_MODE=fake` as the default fast regression path.
- Add `FOAM_AGENT_MODE=mcp` as the real solver path.
- Start real acceptance with `.msh` input only. STEP/STL remain supported by the app, but are not the first real-solver acceptance target.
- Use OpenAI as the first real-mode model provider through `OPENAI_API_KEY`.
- Use the existing HTML artifact dashboard. Do not build a full 3D viewer in Phase 3.

## Target Runtime

Run three processes/services:

1. **Frontend**
   - Command: `.scripts\dev-frontend.ps1`
   - URL: `http://localhost:5173`
   - Role: upload form, external-aero specification form, run progress, result dashboard.

2. **Backend**
   - Fake command: `.scripts\dev-backend.ps1`
   - Real command to add: `.scripts\dev-real-backend.ps1`
   - URL: `http://localhost:8000`
   - Role: upload storage, run orchestration, MCP calls, SQLite metadata, event stream, artifact serving.

3. **Foam-Agent/OpenFOAM**
   - Command to add: `.scripts\dev-foamagent.ps1`
   - URL: `http://localhost:7860/mcp`
   - Role: plan case, write OpenFOAM inputs, run OpenFOAM, review/fix failures once, generate visualizations.

## Environment Variables

Required real-mode environment:

```powershell
OPENAI_API_KEY=sk-...
FOAM_AGENT_MODE=mcp
FOAM_AGENT_URL=http://127.0.0.1:7860/mcp
FOAM_AGENT_SHARED_AGENT_ROOT=/workspace/data
FOAM_AGENT_AGENT_RUNS_ROOT=/home/openfoam/Foam-Agent/runs
FOAM_AGENT_APP_RUNS_ROOT=C:\Users\franc\OneDrive\Desktop\AI CFD\data\foamagent-runs
FOAM_AGENT_RUN_TIMEOUT_SECONDS=900
FOAMAGENT_MODEL_PROVIDER=openai
FOAMAGENT_MODEL_VERSION=gpt-5.4
```

Keep `.env.example` updated with these values and comments. Do not commit a real `.env`.

## Files To Create Or Modify

Create:

- `scripts/dev-foamagent.ps1`
  - Starts or checks the Foam-Agent Docker container.
  - Supports `-CheckOnly` for preflight validation.
  - Verifies Docker daemon, `.env`, `OPENAI_API_KEY`, port `7860`, and shared directories.

- `scripts/dev-real-backend.ps1`
  - Starts the local FastAPI backend in real MCP mode.
  - Refreshes Windows PATH like the existing scripts.
  - Fails clearly if Foam-Agent MCP is not reachable.

- `scripts/smoke-mcp-health.ps1`
  - Verifies the Foam-Agent MCP endpoint responds before a real run.
  - Does not start a solver run.

- `scripts/smoke-real-run.ps1`
  - Optional, not part of the fast release check.
  - Uploads `samples/wing.msh`, creates a real run, polls until terminal status, and reports artifacts/logs.

- `backend/tests/test_foam_agent_mcp.py`
  - Tests JSON-RPC parsing, SSE parsing, tool errors, and retry/review/fix paths with fake HTTP responses.

- `backend/tests/test_real_mode_preflight.py`
  - Tests missing API key, unreachable MCP server, and invalid shared paths.

- `backend/tests/test_artifact_mirroring.py`
  - Tests mapping Foam-Agent container paths to host paths and copying logs/images/case archives.

Modify:

- `backend/app/foam_agent.py`
  - Harden MCP HTTP parsing and error reporting.
  - Write MCP tool provenance JSON into the run directory.
  - Support configurable run timeout.

- `backend/app/jobs.py`
  - Add a `real_preflight` event before `planning` when in MCP mode.
  - Ensure `.msh` paths are mapped to the container-visible shared path.

- `backend/app/settings.py`
  - Add `foam_agent_run_timeout_seconds` and explicit `foam_agent_app_runs_root` support from environment.

- `backend/app/main.py`
  - Add or expose a real-mode preflight helper through internal service code or an API endpoint if needed by scripts.

- `README.md`
  - Document fake mode vs real mode.
  - Add real-mode startup sequence.
  - Add known limitations and troubleshooting.

- `.env.example`
  - Add real-mode variables.

## Implementation Tasks

### Task 1: Add MCP Client Unit Coverage

**Files:**
- Create: `backend/tests/test_foam_agent_mcp.py`
- Modify: `backend/app/foam_agent.py`

Steps:

- [ ] Add a test that feeds `FoamAgentMcpClient._decode_response()` a JSON-RPC success response and verifies the structured payload is returned.
- [ ] Add a test that feeds a `text/event-stream` response containing `data: {...}` and verifies the same payload is returned.
- [ ] Add a test for HTTP 500 where the raised error includes the tool name, status code, and response excerpt.
- [ ] Add a test for JSON-RPC `error` where the raised error includes the MCP error message.
- [ ] Implement the smallest changes in `FoamAgentMcpClient` to pass those tests.
- [ ] Run: `cd backend; ..\.venv\Scripts\python.exe -m pytest tests/test_foam_agent_mcp.py -v`.

Expected result: all new MCP client parsing/error tests pass.

### Task 2: Add Real-Mode Preflight

**Files:**
- Create: `backend/tests/test_real_mode_preflight.py`
- Modify: `backend/app/settings.py`
- Modify: `backend/app/foam_agent.py` or create `backend/app/preflight.py`

Steps:

- [ ] Add a `RealModePreflightResult` model or simple dict shape with `ok`, `checks`, and `errors`.
- [ ] Test that missing `OPENAI_API_KEY` returns `ok=false` with a clear API key error.
- [ ] Test that an unreachable MCP endpoint returns `ok=false` with the URL included.
- [ ] Test that missing shared run directory returns `ok=false` with the host path included.
- [ ] Implement preflight logic without starting a solver run.
- [ ] Run: `cd backend; ..\.venv\Scripts\python.exe -m pytest tests/test_real_mode_preflight.py -v`.

Expected result: real-mode prerequisites fail early with actionable messages.

### Task 3: Add Foam-Agent Docker Script

**Files:**
- Create: `scripts/dev-foamagent.ps1`
- Create: `scripts/smoke-mcp-health.ps1`
- Modify: `.env.example`
- Modify: `README.md`

Steps:

- [ ] Write `scripts/dev-foamagent.ps1` with parameters `-CheckOnly`, `-Port 7860`, and `-Image leoyue123/foamagent:v2.0.0`.
- [ ] In `-CheckOnly`, verify Docker daemon with `docker info`, verify `.env` exists, verify `OPENAI_API_KEY` is not empty, verify port `7860` is free or already serving Foam-Agent, and verify `data/foamagent-runs` exists or can be created.
- [ ] In normal mode, run the Foam-Agent container with volumes:

```powershell
-v "$repoRoot\data:/workspace/data"
-v "$repoRoot\data\foamagent-runs:/home/openfoam/Foam-Agent/runs"
```

- [ ] Use command:

```powershell
foamagent-mcp --transport http --host 0.0.0.0 --port 7860
```

- [ ] Add `scripts/smoke-mcp-health.ps1` to make a minimal MCP tools/list or health-style request and fail clearly if the endpoint is not reachable.
- [ ] Run `scripts/dev-foamagent.ps1 -CheckOnly` with Docker Desktop stopped and verify the error is readable.
- [ ] Run it again with Docker Desktop started and verify it reaches the MCP endpoint.

Expected result: user can start Foam-Agent/OpenFOAM Docker independently from the app.

### Task 4: Add Real Backend Startup Script

**Files:**
- Create: `scripts/dev-real-backend.ps1`
- Modify: `README.md`

Steps:

- [ ] Copy the structure of `scripts/dev-backend.ps1`.
- [ ] Set `FOAM_AGENT_MODE=mcp` instead of `fake`.
- [ ] Set real-mode MCP and shared-path environment variables.
- [ ] Check `http://127.0.0.1:7860/mcp` before starting FastAPI.
- [ ] Print the exact real-mode config at startup, excluding secrets.
- [ ] Fail if port `8000` is occupied by a non-healthy backend.
- [ ] Run `scripts/dev-real-backend.ps1` with Foam-Agent stopped and verify it fails before starting the backend.
- [ ] Run it with Foam-Agent running and verify `/api/health` returns `foam_agent_mode=mcp`.

Expected result: real backend startup is explicit and hard to confuse with fake mode.

### Task 5: Add Artifact Mirroring Tests And Hardening

**Files:**
- Create: `backend/tests/test_artifact_mirroring.py`
- Modify: `backend/app/foam_agent.py`
- Modify: `backend/app/artifacts.py` if needed

Steps:

- [ ] Add a test with a fake Foam-Agent case directory under `data/foamagent-runs/case-1` containing `.png`, `.log`, `.foam`, and `.vtk` files.
- [ ] Verify `_map_agent_path('/home/openfoam/Foam-Agent/runs/case-1')` maps to the host run path.
- [ ] Verify `_mirror_case_artifacts()` copies known artifact types into `data/runs/{run_id}`.
- [ ] Verify it creates `openfoam-case.zip`.
- [ ] Verify missing visualization artifacts do not crash the run if logs/case files exist.
- [ ] Run: `cd backend; ..\.venv\Scripts\python.exe -m pytest tests/test_artifact_mirroring.py -v`.

Expected result: generated OpenFOAM outputs appear in the existing dashboard artifact API.

### Task 6: Add Real Run Provenance

**Files:**
- Modify: `backend/app/foam_agent.py`
- Modify: `backend/tests/test_foam_agent_mcp.py`

Steps:

- [ ] Write each MCP response into the app run directory as JSON:
  - `foamagent-plan.json`
  - `foamagent-input-writer.json`
  - `foamagent-run.json`
  - `foamagent-review.json` only if review runs
  - `foamagent-visualization-pressure.json`
  - `foamagent-visualization-velocity.json`
- [ ] Add tests verifying these files are written for a successful fake MCP run.
- [ ] Add tests verifying review provenance is written only when the first run fails.
- [ ] Include paths to provenance files in discovered artifacts as downloads if useful.

Expected result: when a real run fails, the user can inspect what Foam-Agent planned and did.

### Task 7: Add Opt-In Real Smoke Run

**Files:**
- Create: `scripts/smoke-real-run.ps1`
- Modify: `README.md`

Steps:

- [ ] Use `samples/wing.msh` as the only required acceptance input.
- [ ] Confirm backend health reports `foam_agent_mode=mcp` before running.
- [ ] Upload the mesh through `/api/uploads`.
- [ ] Create a run through `/api/runs` with a small external-aero spec.
- [ ] Poll for terminal status with a long timeout, default `20` minutes.
- [ ] On success, verify at least one log artifact exists and print artifact names.
- [ ] On failure, print `run.error`, artifact names, and where to find provenance JSON.
- [ ] Do not add this script to `release-check.ps1`; it is opt-in because it costs time and model/API usage.

Expected result: real solver validation can be run intentionally without slowing normal development.

### Task 8: Update Documentation And Workflow

**Files:**
- Modify: `README.md`
- Modify: `docs/PHASES_SUMMARY.md`
- Create: `docs/REAL_MODE_RUNBOOK.md` if the README section becomes too large

Steps:

- [ ] Document fake-mode startup:

```powershell
.\scripts\dev-backend.ps1
.\scripts\dev-frontend.ps1
```

- [ ] Document real-mode startup:

```powershell
.\scripts\dev-foamagent.ps1
.\scripts\dev-real-backend.ps1
.\scripts\dev-frontend.ps1
```

- [ ] Document real-mode verification:

```powershell
.\scripts\smoke-mcp-health.ps1
.\scripts\smoke-real-run.ps1
```

- [ ] Add troubleshooting entries for Docker stopped, missing API key, port conflicts, MCP schema errors, no artifacts, and solver failure.

Expected result: another engineer can run fake mode or real mode without guessing.

## Test And Review Gates

Run these before claiming Phase 3 complete:

```powershell
.\scripts\dev-check.ps1
.\scripts\release-check.ps1
npm --prefix frontend run build
.\scripts\dev-foamagent.ps1 -CheckOnly
.\scripts\smoke-mcp-health.ps1
.\scripts\smoke-real-run.ps1
```

Expected results:

- `dev-check` reports Python, Node, npm, and Gmsh.
- `release-check` passes existing fake-mode regression tests.
- frontend production build passes.
- Foam-Agent Docker preflight passes.
- MCP health check passes.
- Real smoke run reaches `completed`, or fails with clear logs/provenance that identify the solver/setup issue.

## Risks And Mitigations

| Risk | Why It Matters | Mitigation | Verification |
| --- | --- | --- | --- |
| Docker Desktop is not running | Real solver cannot start | `dev-foamagent.ps1 -CheckOnly` fails early | Stop Docker and confirm readable failure |
| Missing `OPENAI_API_KEY` | Foam-Agent cannot call model | preflight checks `.env` before starting | Run preflight with empty key |
| MCP response shape differs | FastMCP may return JSON or SSE | unit-test both response types | `test_foam_agent_mcp.py` |
| Mesh path not used by Foam-Agent | MCP does not expose CLI `custom_mesh_path` directly | include mounted path in prompt and store plan JSON | inspect `foamagent-plan.json` |
| OpenFOAM case fails | Solver errors are common early | one review/fix cycle, then fail with artifacts | fake MCP failure tests + real smoke run |
| Artifacts stay in container | Dashboard would show nothing | shared volume plus mirroring | `test_artifact_mirroring.py` |
| Real runs are slow or costly | Bad for normal dev loop | keep real smoke opt-in | `release-check` remains fake-only |
| Wrong OpenFOAM variant | Foam-Agent targets Foundation OpenFOAM v10 | use Foam-Agent Docker image only | preflight reports Docker image |

## Acceptance Criteria

Phase 3 is complete when:

- Fake mode still passes `scripts/release-check.ps1`.
- `scripts/dev-foamagent.ps1` starts Foam-Agent Docker or reports clear preflight failures.
- `scripts/dev-real-backend.ps1` starts FastAPI in `FOAM_AGENT_MODE=mcp` only after Foam-Agent is reachable.
- A `.msh` upload can create a real MCP-backed run.
- Run events show MCP progress in the dashboard.
- Logs/provenance are saved for every real run.
- At least one real run produces mirrored artifacts, or a failed real run gives enough logs/provenance to diagnose the solver/setup failure.

## Out Of Scope For Phase 3

- Ansys integration.
- Heat transfer.
- vibration/aeroelastic analysis.
- Full browser-native 3D viewer.
- Making STEP/STL real-mode acceptance mandatory.
- Cloud deployment or multi-user collaboration.

