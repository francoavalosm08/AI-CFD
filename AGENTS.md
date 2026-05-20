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

Do not restart from a blank plan. The immediate next engineering milestone is to replace or extend fake-mode execution with the real Docker/Foam-Agent/OpenFOAM path described in `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`.

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

## Known Good Baseline

The latest verified baseline passed:

- Python/backend prerequisite check, including Gmsh 4.13.1.
- Backend pytest suite: 16 tests.
- Frontend Vitest suite: 4 tests.
- Fake-mode backend smoke flow.
- Playwright browser E2E workflow.

The verification script starts temporary backend/frontend servers and writes their logs under `.local-data/verify-logs/`, which is gitignored.

## Local Runtime Notes

- Frontend dev server: `http://localhost:5173`.
- Backend API: `http://localhost:8000`.
- Vite proxy targets `http://127.0.0.1:8000` to avoid Windows localhost IPv4/IPv6 issues.
- Fake mode is controlled by `FOAM_AGENT_MODE=fake`.
- Local run data is disposable and lives under `.local-data/`.
- Do not commit `.local-data/`, `.venv/`, `frontend/node_modules/`, `frontend/test-results/`, or generated run data.

## Next Milestone

Implement real Foam-Agent/OpenFOAM execution behind the existing backend interface.

Recommended sequence:

1. Confirm the real Foam-Agent Docker image, command, exposed MCP/HTTP endpoint, and mounted run paths.
2. Add a real integration configuration path that preserves fake mode as the default test path.
3. Implement the real Foam-Agent client call sequence in `backend/app/foam_agent.py` or an adjacent module.
4. Map uploaded `.msh` paths into the Foam-Agent container using the configured app/agent data roots.
5. Copy or discover real generated artifacts into the run dashboard artifact model.
6. Add integration tests with a fake MCP server before testing a real CFD run.
7. Only after the fake MCP tests pass, run a manual known `.msh` external-aero case through Docker.

Keep the API and UI stable unless the next milestone proves they need to change.

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