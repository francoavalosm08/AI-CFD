# AI CFD Workbench: Phase Summary

This is a simplified roadmap for non-software stakeholders, while keeping the key technical keywords.

## Phase 1: Local Non-Docker Bootstrap (Current)

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

## Phase 2: Solidify Local Workflow (Next)

**Goal:** Make Phase 1 reliable for repeated use by more people.

**What it should do:**
- Improve error handling and troubleshooting messages in scripts/docs.
- Add stronger local acceptance checks (repeatable smoke scenarios).
- Add one-command verification (`release check`) for backend + frontend + smoke.
- Reduce setup friction for first-time contributors.
- Keep API behavior stable while improving developer reliability.

**Keywords:** `smoke test`, `PowerShell`, `FastAPI`, `Vite`, `fake mode`, `local onboarding`.

## Phase 3: Real Solver Integration (MCP/OpenFOAM)

**Goal:** Move from fake execution to real CFD runs.

**What it should do:**
- Connect backend to real `Foam-Agent MCP` endpoint.
- Run real `OpenFOAM` cases.
- Validate artifact mirroring and run status behavior under real workloads.

**Keywords:** `MCP`, `OpenFOAM`, `Foam-Agent`, `real run`, `artifacts`.

## Phase 4: Docker for Testing and Reproducibility

**Goal:** Use Docker at the right time for controlled testing and shared environments.

**What it should do:**
- Reconfirm `docker-compose` path for integration testing.
- Standardize environment parity across machines.
- Keep local non-Docker workflow for fast iteration, and Docker for repeatable verification.

**Keywords:** `Docker`, `docker-compose`, `integration testing`, `environment parity`.

## Phase 5: Release Readiness

**Goal:** Prepare for wider internal/external usage.

**What it should do:**
- Add CI checks (`pytest`, frontend tests, smoke checks where possible).
- Define quality gates and release checklist.
- Document operational runbook and known limits.

**Keywords:** `CI`, `quality gates`, `release checklist`, `runbook`.
