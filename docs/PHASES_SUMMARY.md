# AI CFD Workbench: Phase Summary

This is a simplified roadmap for non-software stakeholders, while keeping the key technical keywords.

## Phase 1: Local Non-Docker Bootstrap (Complete)

**Goal:** Make daily development fast on Windows without using Docker first.

**What it does:**
- Runs `FastAPI` backend on `:8000`.
- Runs `Vite` + `React` frontend on `:5173`.
- Uses `FOAM_AGENT_MODE=fake` so testing is fast and deterministic.
- Includes PowerShell scripts:
  - `scripts/dev-check.ps1`
  - `scripts/dev-backend.ps1`
  - `scripts/dev-frontend.ps1`
  - `scripts/smoke-fake-run.ps1`
- Verifies full flow: upload mesh, create run, view artifacts/events, check cancel endpoint.

**Business outcome:** Team can build and demo core workflow quickly without waiting for full solver infrastructure.

## Phase 2: Solidify Local Workflow (Complete)

**Goal:** Make Phase 1 reliable for repeated use by more people.

**What it did:**
- Improve error handling and troubleshooting messages in scripts/docs.
- Add stronger local acceptance checks (repeatable smoke scenarios).
- Add one-command verification (`release check`) for backend + frontend + smoke.
- Reduce setup friction for first-time contributors.
- Keep API behavior stable while improving developer reliability.

**Keywords:** `smoke test`, `PowerShell`, `FastAPI`, `Vite`, `fake mode`, `local onboarding`.

## Phase 3: Local OpenFOAM Real Solver Integration (No API Key) (Sample Acceptance Complete; Hardening In Progress)

**Goal:** Move from fake execution to real CFD runs.

**Decision update:**
- The primary V1 real-solver path should not require `OPENAI_API_KEY`.
- Use deterministic OpenFOAM case templates and local command execution.
- Use WSL2 Ubuntu as the first Windows OpenFOAM target.
- Keep Foam-Agent/MCP as optional advanced mode, not the default V1 path.

**What is implemented now from the old MCP path:**
- MCP client hardening, provenance JSON, and artifact mirroring tests in `backend/tests/`.
- Real-mode preflight checks for API key, MCP reachability, and shared run directories.
- Local scripts: `dev-foamagent.ps1`, `dev-real-backend.ps1`, `smoke-mcp-health.ps1`, `smoke-real-run.ps1`.
- Runbook: `docs/REAL_MODE_RUNBOOK.md`.

**Implemented for the new primary path:**
- Local runner settings and scripts.
- WSL2/OpenFOAM preflight.
- Deterministic `.msh` case builder.
- OpenFOAM command manifest and dry-run mode.
- Log/residual/artifact parsing.
- Automatic local HTML report generation from OpenFOAM run files.
- No-API dry-run smoke script.
- OpenFOAM 10 installed and sourceable in WSL `Ubuntu-22.04`.
- Committed sample geometry source: `samples/external_box.geo`.
- First real WSL/OpenFOAM smoke reached `completed` using a `.msh` generated from that sample.
- NACA 4412 validation generator for `.geo`, `.stl`, and `.msh` files.
- 2D airfoil OpenFOAM patch handling for `airfoil`, `inlet`, `outlet`, `farfield`, and `frontAndBack`.
- Real NACA 4412 WSL/OpenFOAM validation reached `completed` at `25 m/s`, `2 deg`, `1 m` chord, `Re=1.666666e6`; `checkMesh` passed with `57,292` cells.
- WSL-native staging under `/tmp/ai-cfd-workbench/<run_id>/case` for real runs, with copy-back to the Windows run directory.

**Still required for user-mesh hardening:**
- Add force coefficient setup and richer visualization based on the validated airfoil patch model.
- Validate uploaded `.msh` boundary patches before solver execution.
- Improve STEP/STL mesh-prep failure handling while keeping `.msh` first-class.

**Keywords:** `OpenFOAM`, `WSL2`, `no API key`, `deterministic templates`, `real run`, `artifacts`.

## Phase 4: Runtime Reproducibility

**Goal:** Make the local OpenFOAM workflow reproducible across machines.

**What it should do:**
- Standardize WSL2/OpenFOAM setup checks.
- Decide whether Docker stays as optional parity/testing infrastructure.
- Keep local non-Docker workflow for fast iteration.

**Keywords:** `WSL2`, `OpenFOAM`, `integration testing`, `environment parity`.

## Phase 5: Release Readiness

**Goal:** Prepare for wider internal/external usage.

**What it should do:**
- Add CI checks (`pytest`, frontend tests, smoke checks where possible).
- Define quality gates and release checklist.
- Document operational runbook and known limits.

**Keywords:** `CI`, `quality gates`, `release checklist`, `runbook`.
