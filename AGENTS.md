# AI CFD Workbench Agent Handoff

This file is the handoff for any fresh LLM or coding agent starting work in this repository. Read this before editing code.

## Current State

The repository already contains a working V1 local web app for an AI CFD workflow:

- React + TypeScript + Vite frontend in `frontend/`.
- Python FastAPI backend in `backend/`.
- Local fake Foam-Agent mode for reliable development and testing.
- SQLite/local filesystem state under `.local-data/` during local development.
- Docker files for the intended Foam-Agent/OpenFOAM integration path.
- Planning and project docs under `docs/`.

Do not restart from a blank plan. The immediate next engineering milestone is to **finish Phase 3 acceptance**: run `scripts/smoke-real-run.ps1` against Docker-hosted Foam-Agent with a valid `OPENAI_API_KEY`, then fix any MCP schema or solver issues that appear. After that, move to Phase 4 (Docker parity) and Phase 5 (release readiness). See `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md` and `docs/REAL_MODE_RUNBOOK.md`.

## Recent Work (Phase 3 — 2026-05-22)

A prior agent session implemented most of Phase 3 code and docs. Fake mode was preserved; no API/UI contract changes.

### Backend

- **`backend/app/foam_agent.py`**: Hardened `FoamAgentMcpClient` — JSON and SSE MCP responses, tool-level HTTP/MCP errors, configurable run timeout, provenance JSON per tool call (`foamagent-plan.json`, `foamagent-input-writer.json`, `foamagent-run.json`, optional `foamagent-review.json` / `foamagent-run-rerun.json`, visualization JSON), artifact mirroring into app run dirs, `openfoam-case.zip`.
- **`backend/app/preflight.py`**: Real-mode preflight (API key, shared `foamagent-runs` directory, MCP `tools/list` reachability).
- **`backend/app/errors.py`**: `FoamAgentError` extracted to break circular imports with preflight.
- **`backend/app/settings.py`**: Default `FOAM_AGENT_MODE=fake`; `foam_agent_run_timeout_seconds`; local MCP URL default `http://127.0.0.1:7860/mcp`; `FOAM_AGENT_APP_RUNS_ROOT` env support.
- **`backend/app/jobs.py`**: Calls `foam_agent.preflight()` before MCP run when the runner supports it (`real_preflight` event).

### Tests (28 total, was 16)

- `backend/tests/test_foam_agent_mcp.py` — decode, errors, provenance
- `backend/tests/test_real_mode_preflight.py`
- `backend/tests/test_artifact_mirroring.py`

### Scripts

- `scripts/dev-foamagent.ps1` — start/check Foam-Agent Docker (`-CheckOnly`)
- `scripts/dev-real-backend.ps1` — FastAPI in `FOAM_AGENT_MODE=mcp`
- `scripts/smoke-mcp-health.ps1` — MCP endpoint health
- `scripts/smoke-real-run.ps1` — opt-in real `.msh` acceptance (not in `release-check.ps1`)

### Docs / config

- `README.md` — real-mode startup and troubleshooting
- `.env.example` — full real-mode variables
- `docs/REAL_MODE_RUNBOOK.md`, `docs/PHASES_SUMMARY.md`, `docs/README.md`

### Verified in that session

- `cd backend; ..\.venv\Scripts\python.exe -m pytest` → **28 passed**
- `.\scripts\local-verify.ps1 -Scope backend` → **PASS** (fake-mode smoke)

### Verified in current session (2026-05-22)

- `cd backend; ..\.venv\Scripts\python.exe -m pytest` -> **28 passed**
- `.\scripts\local-verify.ps1 -Scope backend` -> **PASS**
- `.\scripts\release-check.ps1` -> **PASS**
- `npm --prefix frontend run build` -> **PASS**
- `.\scripts\dev-foamagent.ps1 -CheckOnly` -> blocked before real acceptance because Docker Desktop daemon is not running
- `.\scripts\dev-real-backend.ps1 -SkipDependencyInstall` -> blocked before startup because `.env` is missing

### Not done yet (Phase 3 acceptance gate)

- Create `.env` from `.env.example` with a real `OPENAI_API_KEY`
- Start Docker Desktop, then run `.\scripts\dev-foamagent.ps1 -CheckOnly`
- `.\scripts\dev-foamagent.ps1` + `.\scripts\smoke-real-run.ps1` on a machine with Docker Desktop and real `OPENAI_API_KEY`
- Any MCP tool schema fixes discovered during first real run
- Full `.\scripts\release-check.ps1` after any follow-up changes; last fake-mode regression passed on 2026-05-22

## User Goal

The user wants a local browser-based CFD workbench where they can drop in a geometry or mesh file, answer simulation specification questions, have the system run the CFD workflow, then view logs, images, plots, and downloadable artifacts in the browser.

V1 scope is external aerodynamics only. Heat transfer, motor/prop vibration, turbulent gust response, Ansys, and aeroelastic coupling are intentionally out of scope until the external-aero workflow is reliable.

## What Is Already Built

The app currently supports:

- Uploading `.msh`, `.stl`, `.step`, `.stp`, and `.zip` files.
- Detecting file type on the backend.
- Building a structured `SimulationSpec` from the frontend wizard.
- Creating runs through `POST /api/runs`.
- Streaming run events through `GET /api/runs/{run_id}/events`.
- Discovering and serving run artifacts.
- Fake Foam-Agent execution that creates representative image/log/download artifacts.
- Browser E2E coverage for upload -> spec -> run -> dashboard artifacts.

## Important Docs

Start with these files:

- `README.md`: setup, local run, Docker notes, and verification commands.
- `docs/README.md`: docs index and reading order.
- `docs/PROJECT_OVERVIEW_AND_RUNBOOK.md`: full architecture and operating runbook.
- `docs/PHASES_SUMMARY.md`: what was completed and planned by phase.
- `docs/PHASE_2_PLANNING_DRAFT.md`: prior milestone planning detail.
- `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`: next milestone plan for real Foam-Agent/OpenFOAM.
- `docs/REAL_MODE_RUNBOOK.md`: real-mode startup, health checks, troubleshooting.

## Verification Commands

Before claiming work is complete, run the smallest relevant verification command and report the result.

Full local verification:

```powershell
.\scripts\release-check.ps1
```

Backend-only verification:

```powershell
.\scripts\local-verify.ps1 -Scope backend
```

Manual local development:

```powershell
.\scripts\dev-backend.ps1
.\scripts\dev-frontend.ps1
```

Fake-mode smoke test against a running backend:

```powershell
.\scripts\smoke-fake-run.ps1
```

Real-mode (opt-in; requires Docker + `.env` API key):

```powershell
.\scripts\dev-foamagent.ps1
.\scripts\dev-real-backend.ps1
.\scripts\smoke-mcp-health.ps1
.\scripts\smoke-real-run.ps1
```

## Known Good Baseline

The latest verified baseline passed:

- Python/backend prerequisite check, including Gmsh 4.13.1.
- Backend pytest suite: **28 tests** (includes MCP, preflight, mirroring).
- Frontend Vitest suite: 4 tests.
- Fake-mode backend smoke flow (`local-verify.ps1 -Scope backend`).
- Playwright browser E2E workflow (via full `release-check.ps1`).
- Frontend production build (`npm --prefix frontend run build`).

The verification script starts temporary backend/frontend servers and writes their logs under `.local-data/verify-logs/`, which is gitignored.

## Local Runtime Notes

- Frontend dev server: `http://localhost:5173`.
- Backend API: `http://localhost:8000`.
- Vite proxy targets `http://127.0.0.1:8000` to avoid Windows localhost IPv4/IPv6 issues.
- Fake mode is controlled by `FOAM_AGENT_MODE=fake`.
- Local run data is disposable and lives under `.local-data/`.
- Do not commit `.local-data/`, `.venv/`, `frontend/node_modules/`, `frontend/test-results/`, or generated run data.

## Next Milestone

**Close Phase 3**, then proceed to Phases 4–5 per `docs/PHASES_SUMMARY.md`.

Phase 3 remaining steps:

1. Copy `.env.example` → `.env` and set `OPENAI_API_KEY`.
2. Run `.\scripts\dev-foamagent.ps1 -CheckOnly`, then start Foam-Agent without `-CheckOnly`.
3. Run `.\scripts\dev-real-backend.ps1` and `.\scripts\smoke-mcp-health.ps1`.
4. Run opt-in `.\scripts\smoke-real-run.ps1` with `samples/wing.msh`.
5. If MCP tools or paths fail, adjust `backend/app/foam_agent.py` and re-run; inspect `data/runs/<run_id>/foamagent-*.json`.
6. Run `.\scripts\release-check.ps1` to confirm fake-mode regression still passes.

Keep the API and UI stable unless the real run proves they need to change.

## Likely Failure Points

Watch these areas:

- Docker Desktop may not be running, even if the Docker CLI exists.
- Foam-Agent MCP tool names or request schemas may differ from assumptions.
- Windows path handling can break container volume mapping; keep app paths and agent-visible paths separate.
- STEP/STL meshing is best-effort; `.msh` should remain the reliable V1 input.
- Long-running CFD jobs need cancellation and timeout behavior to avoid stuck UI state.
- Browser E2E failures can be caused by stale dev servers on ports `8000` or `5173`; check listeners before debugging app code.

## Coding Guidance

- Preserve the existing frontend/backend boundary and API routes unless there is a concrete reason to change them.
- Keep fake mode working at all times; it is the fast regression path.
- Add tests around behavior before or with implementation changes.
- Prefer focused changes over broad refactors.
- Use the docs as source of intent, but trust code/tests for exact behavior.
- If changing Docker or Foam-Agent integration, update `README.md`, `docs/PROJECT_OVERVIEW_AND_RUNBOOK.md`, and `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md` as needed.

## Git State Expectations

The `main` branch tracks `origin/main` at `https://github.com/francoavalosm08/AI-CFD.git`. Before pushing, run:

```powershell
git status --short --branch
git fetch origin main
git log --oneline --decorate --graph --all --max-count=8
```

Do not force-push unless the user explicitly asks for it.
