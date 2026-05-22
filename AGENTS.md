# AI CFD Workbench Agent Handoff

This file is the handoff for any fresh LLM or coding agent starting work in this repository. Read this before editing code.

## Current State

The repository already contains a working V1 local web app for an AI CFD workflow:

- React + TypeScript + Vite frontend in `frontend/`.
- Python FastAPI backend in `backend/`.
- Local fake Foam-Agent mode for reliable development and testing.
- SQLite/local filesystem state under `.local-data/` during local development.
- Optional Docker/Foam-Agent files from the previous integration path.
- Planning and project docs under `docs/`.

Do not restart from a blank plan. Phase 3 has been pivoted to the no-runtime-API-key local OpenFOAM runner described in `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md` and `docs/LOCAL_OPENFOAM_NO_API_RUNBOOK.md`. The case-generation/dry-run slice is implemented, and the first real WSL/OpenFOAM sample smoke has completed on this machine. The Foam-Agent/MCP work remains in the repo as an optional advanced path, but it is no longer the primary V1 acceptance target.

## Current Product Direction (Updated 2026-05-22)

The user does not want the V1 real solver path to require `OPENAI_API_KEY`. The new primary direction is:

- Browser app stays the same.
- Backend generates deterministic OpenFOAM cases from local templates.
- OpenFOAM runs locally, with WSL2 Ubuntu as the first Windows target.
- Each run writes a command manifest so a human or IDE agent can inspect/run steps manually.
- Foam-Agent MCP stays optional and should not block V1.

Do not make `.env` or API keys mandatory for the next real-solver milestone.

## Latest Local OpenFOAM Acceptance (2026-05-22)

- WSL distro: `Ubuntu-22.04`.
- OpenFOAM: Foundation OpenFOAM 10 installed under `/opt/openfoam10` using `scripts/install-openfoam-wsl.ps1 -UseWslRoot`.
- OpenFOAM source line added to the WSL user's `~/.bashrc`: `source /opt/openfoam10/etc/bashrc`.
- `scripts/dev-openfoam-wsl.ps1 -CheckOnly` passes and finds `gmshToFoam`, `checkMesh`, `simpleFoam`, and `foamToVTK`.
- `samples/external_box.geo` is the committed source for the first valid real-smoke mesh. Generate the disposable mesh with:

```powershell
gmsh samples\external_box.geo -3 -format msh2 -o .local-data\external_box.msh
```

- Real local smoke was run against a non-dry-run backend with:

```powershell
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\external_box.msh -TimeoutSeconds 300
```

- The run reached `completed` and produced real OpenFOAM logs, residuals, VTK/case outputs, `openfoam-commands.json`, and `openfoam-case.zip`.
- Because this repo path contains a space (`AI CFD`), the WSL runner stages real execution in `/tmp/ai-cfd-workbench/<run_id>/case` and copies the case back into `.local-data/runs/<run_id>/case` before artifact packaging.

## Latest NACA 4412 Airfoil Acceptance (2026-05-22)

The NACA 4412 validation path is now implemented for local OpenFOAM mode:

- Generate local validation files with `.\scripts\generate-naca4412.ps1 -OutputDir .local-data\naca4412-improved`.
- The generated `.msh` uses named patches: `airfoil`, `inlet`, `outlet`, `farfield`, `frontAndBack`, and `internal`.
- Local OpenFOAM mode validates those names before `gmshToFoam` and writes `mesh-validation.json`.
- Backend case generation detects this patch set as `airfoil_2d`.
- The runner normalizes imported OpenFOAM patch types after `gmshToFoam`: `frontAndBack` becomes `empty`; `airfoil` becomes `wall`.
- Boundary conditions are airfoil-specific: no-slip/wall functions on `airfoil`, `empty` on `frontAndBack`, fixed freestream velocity at `inlet`, pressure outlet behavior at `outlet`, and slip/zero-gradient behavior at `farfield`.
- Run metadata records `chord_length_m=1.0`, `kinematic_viscosity_m2_s=1.5e-5`, `reynolds_number=1666666.666667`, parsed `checkMesh` summary, and final OpenFOAM-generated `Cl/Cd/Cm` when available.
- Airfoil cases enable OpenFOAM `forceCoeffs` on the `airfoil` patch.
- The latest real local run used `25 m/s`, `2 deg` angle of attack, `1 m` chord, and reached `completed` as run `ba226737-d4d3-4c5a-836c-23d14bdb2968`.
- OpenFOAM `checkMesh` passed with `57,292` cells.
- Final OpenFOAM-derived coefficients from that run: `Cl=0.4591685`, `Cd=0.02907224`, `Cm=0.09620507`.
- Required artifacts include: `mesh-validation.json`, `checkMesh.log`, `solver.log`, `residuals.csv`, `forceCoeffs.dat`, `forceCoeffs.csv`, `force-coefficients.png`, VTK output, `openfoam-case.zip`, and `openfoam-report.html`.
- The visual-preview milestone is implemented with lightweight PNG generation from OpenFOAM outputs:
  - `residuals.png` from `residuals.csv`
  - `velocity-magnitude.png` from ASCII VTK point data
  - `pressure.png` from ASCII VTK point data
  - `force-coefficients.png` from OpenFOAM `forceCoeffs.csv`
- The OpenFOAM runner exports VTK with `foamToVTK -ascii`; binary VTK is skipped by the lightweight parser instead of blocking a run.

Do not accept future NACA validation runs as successful if `checkMesh` fails, OpenFOAM reports fewer than `40,000` cells, or `forceCoeffs.dat` / `forceCoeffs.csv` / `force-coefficients.png` / final `Cl/Cd/Cm` are missing.

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

- `cd backend; ..\.venv\Scripts\python.exe -m pytest` -> **50 passed**
- `.\scripts\local-verify.ps1 -Scope backend` -> **PASS**
- `.\scripts\release-check.ps1` -> **PASS**
- `.\scripts\smoke-naca-openfoam.ps1 -ApiBaseUrl http://127.0.0.1:8012 -TimeoutSeconds 1200 -PollIntervalSeconds 5 -SkipPreflight` -> **PASS** (run `ba226737-d4d3-4c5a-836c-23d14bdb2968`)
- `.\scripts\smoke-bad-mesh-validation.ps1 -ApiBaseUrl http://127.0.0.1:8012` -> **PASS**
- `npm --prefix frontend run build` -> **PASS**
- `.\scripts\dev-foamagent.ps1 -CheckOnly` -> blocked before real acceptance because Docker Desktop daemon is not running
- `.\scripts\dev-real-backend.ps1 -SkipDependencyInstall` -> blocked before startup because `.env` is missing

### Not done yet (old Foam-Agent acceptance gate)

- Create `.env` from `.env.example` with a real `OPENAI_API_KEY`
- Start Docker Desktop, then run `.\scripts\dev-foamagent.ps1 -CheckOnly`
- `.\scripts\dev-foamagent.ps1` + `.\scripts\smoke-real-run.ps1` on a machine with Docker Desktop and real `OPENAI_API_KEY`
- Any MCP tool schema fixes discovered during first real run
- Full `.\scripts\release-check.ps1` after any follow-up changes; last fake-mode regression passed on 2026-05-22

This old gate is now optional. The primary no-API local OpenFOAM gate is:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\dev-openfoam-backend.ps1 -DryRun
.\scripts\smoke-local-openfoam.ps1 -DryRun
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-local-openfoam.ps1
.\scripts\smoke-naca-openfoam.ps1
.\scripts\smoke-bad-mesh-validation.ps1
```

For future real non-dry-run smokes, generate the committed sample mesh with `gmsh samples\external_box.geo -3 -format msh2 -o .local-data\external_box.msh`, then pass `-SampleMeshPath .local-data\external_box.msh`. For user meshes, make sure the `.msh` has valid external-aero volume/boundary patches before using it as acceptance evidence.

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
- Local OpenFOAM dry-run execution that creates a deterministic case, command manifest, logs, and case zip without an API key.
- Local OpenFOAM airfoil validation with pre-run patch validation and OpenFOAM-generated force coefficient artifacts.
- Browser E2E coverage for upload -> spec -> run -> dashboard artifacts.

## Important Docs

Start with these files:

- `README.md`: setup, local run, Docker notes, and verification commands.
- `docs/README.md`: docs index and reading order.
- `docs/PROJECT_OVERVIEW_AND_RUNBOOK.md`: full architecture and operating runbook.
- `docs/PHASES_SUMMARY.md`: what was completed and planned by phase.
- `docs/PHASE_2_PLANNING_DRAFT.md`: prior milestone planning detail.
- `docs/EXTERNAL_AERO_V1_ROADMAP.md`: active roadmap and acceptance gates from the current prototype to usable external-aero V1.
- `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`: next milestone plan, now rewritten around local OpenFOAM without API keys.
- `docs/LOCAL_OPENFOAM_NO_API_RUNBOOK.md`: no-API local OpenFOAM target runbook.
- `docs/REAL_MODE_RUNBOOK.md`: optional Foam-Agent/MCP startup, health checks, troubleshooting.

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

Optional Foam-Agent/MCP mode (requires Docker + `.env` API key):

```powershell
.\scripts\dev-foamagent.ps1
.\scripts\dev-real-backend.ps1
.\scripts\smoke-mcp-health.ps1
.\scripts\smoke-real-run.ps1
```

## Known Good Baseline

The latest verified baseline passed:

- Python/backend prerequisite check, including Gmsh 4.13.1.
- Backend pytest suite: **73 tests** (includes MCP, preflight, mirroring, local OpenFOAM, mesh validation, and force coefficients).
- Frontend Vitest suite: 6 tests.
- Fake-mode backend smoke flow (`local-verify.ps1 -Scope backend`).
- Playwright browser E2E workflow (via full `release-check.ps1`).
- Local OpenFOAM dry-run smoke flow (via full `release-check.ps1`).
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

**Harden local OpenFOAM for real user aircraft/vehicle meshes**, then proceed to Phases 4–5 per `docs/PHASES_SUMMARY.md`.

Phase 3 implemented steps:

1. Add local runner settings while preserving fake and optional MCP modes.
2. Add WSL2/OpenFOAM preflight and Windows-to-WSL path mapping.
3. Add deterministic OpenFOAM case templates for `.msh` external aero.
4. Add command manifest, dry-run, and real command runner.
5. Add parsers/artifact collection for logs, residuals, VTK, and case zip.
6. Add no-API smoke scripts and update UI copy away from Foam-Agent-only language.
7. Run `.\scripts\release-check.ps1` to confirm fake-mode regression still passes.

Phase 3 sample acceptance is complete on this machine. Remaining hardening steps:

1. Run fresh real NACA and bad-mesh smoke validation after solver-path changes.
2. Improve STEP/STL mesh-prep error messages and keep `.msh` as the first-class input.
3. Add user-facing Gmsh physical-name examples/templates.
4. Add richer visualization after VTK/log artifacts are reliable.
5. Keep `.\scripts\release-check.ps1` passing after every follow-up change.

Keep the API and UI stable unless the real run proves they need to change.

## Likely Failure Points

Watch these areas:

- WSL2/OpenFOAM may not be installed yet.
- Windows path handling can break WSL command execution; keep app paths and WSL-visible paths separate.
- Boundary names from `.msh` imports may not match deterministic template assumptions.
- STEP/STL meshing is best-effort; `.msh` should remain the reliable V1 input.
- Long-running CFD jobs need cancellation and timeout behavior to avoid stuck UI state.
- Browser E2E failures can be caused by stale dev servers on ports `8000` or `5173`; check listeners before debugging app code.

## Coding Guidance

- Preserve the existing frontend/backend boundary and API routes unless there is a concrete reason to change them.
- Keep fake mode working at all times; it is the fast regression path.
- Add tests around behavior before or with implementation changes.
- Prefer focused changes over broad refactors.
- Use the docs as source of intent, but trust code/tests for exact behavior.
- If changing runner architecture, update `README.md`, `docs/PROJECT_OVERVIEW_AND_RUNBOOK.md`, `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`, and `docs/LOCAL_OPENFOAM_NO_API_RUNBOOK.md` as needed.

## Git State Expectations

The `main` branch tracks `origin/main` at `https://github.com/francoavalosm08/AI-CFD.git`. Before pushing, run:

```powershell
git status --short --branch
git fetch origin main
git log --oneline --decorate --graph --all --max-count=8
```

Do not force-push unless the user explicitly asks for it.
