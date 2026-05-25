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

## Phase 3: Local OpenFOAM Real Solver Integration (No API Key) (V1 Candidate)

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
- Automatic PNG visual previews from OpenFOAM outputs: residual plot, velocity magnitude binned heatmap, pressure binned heatmap, and filled solid-body masks for airfoil/obstacle patches.
- No-API dry-run smoke script.
- OpenFOAM 10 installed and sourceable in WSL `Ubuntu-22.04`.
- Committed sample geometry source: `samples/external_box.geo`.
- First real WSL/OpenFOAM smoke reached `completed` using a `.msh` generated from that sample.
- NACA 4412 validation generator for `.geo`, `.stl`, and `.msh` files.
- 2D airfoil OpenFOAM patch handling for `airfoil`, `inlet`, `outlet`, `farfield`, and `frontAndBack`.
- Real NACA 4412 WSL/OpenFOAM validation reached `completed` at `25 m/s`, `2 deg`, `1 m` chord, `Re=1.666666e6`; `checkMesh` passed with `57,292` cells and generated residual, velocity, pressure, and force coefficient PNG previews.
- Latest accepted OpenFOAM-derived NACA coefficients: `Cl=0.4591685`, `Cd=0.02907224`, `Cm=0.09620507`.
- WSL-native staging under `/tmp/ai-cfd-workbench/<run_id>/case` for real runs, with copy-back to the Windows run directory.
- Pre-run `.msh` physical-name validation with `mesh-validation.json`.
- Downloaded public `.msh` corpus script with provenance manifest and solver-readiness classification.
- Generated working validation meshes for NACA 0012, cylinder obstacle, and square-box obstacle.
- Repeatable three-mesh real solver gate through `scripts\smoke-validation-mesh-suite.ps1`.
- New `external_2d_obstacle` mesh contract for simple non-airfoil geometries.
- Airfoil-specific `forceCoeffs` setup and parser for OpenFOAM-generated `Cl`, `Cd`, and `Cm`.
- Force coefficient artifacts: `forceCoeffs.dat`, `forceCoeffs.csv`, and `force-coefficients.png`.
- Dashboard summary cards for cells, Reynolds number, `checkMesh`, `Cl`, `Cd`, and `Cm`.
- Dedicated smoke scripts for NACA validation and bad mesh validation.
- User-facing production `.msh` mesh contract in `docs/GMSH_AIRFOIL_2D_TEMPLATE.md`.
- Clearer STEP/STL conversion failures for missing Gmsh, missing volume meshes, missing physical names, and bad geometry.
- Dedicated local OpenFOAM STL path using `snappyHexMesh` scaffolding, `surfaceCheck`, `blockMesh`, `surfaceFeatures`, `snappyHexMesh`, and `checkMesh`.
- Manual STL case helper: `scripts/generate-snappy-stl-case.ps1`.
- WSL/OpenFOAM preflight now also reports Windows Gmsh availability for NACA generation and STEP/STL conversion.
- Browser image inspection for OpenFOAM-generated PNG artifacts.

**Remaining after the current V1 candidate:**
- Upgrade from PNG inspection to richer contour/interactivity when PyVista/vtk.js is introduced.
- Keep running fresh real NACA and bad-mesh smoke validation after solver-path changes.
- Broaden user-mesh examples after real third-party `.msh` files are tested.

**Keywords:** `OpenFOAM`, `WSL2`, `no API key`, `deterministic templates`, `real run`, `artifacts`.

## Phase 4: Runtime Reproducibility

**Goal:** Make the local OpenFOAM workflow reproducible across machines.

**What is implemented now:**
- WSL2/OpenFOAM setup checks through `scripts/dev-openfoam-wsl.ps1 -CheckOnly`.
- Windows Gmsh visibility check in the same preflight.
- STL/snappyHexMesh command checks in the same preflight.
- Machine/runtime snapshot through `scripts\runtime-report.ps1`, which writes `.local-data/runtime-report.json`.
- Dry-run, real NACA, and bad-mesh smoke scripts.
- Docker/Foam-Agent remains optional parity/advanced infrastructure, not a V1 requirement.
- Local non-Docker workflow stays the primary iteration path.

**Keywords:** `WSL2`, `OpenFOAM`, `integration testing`, `environment parity`.

## Phase 5: Release Readiness

**Goal:** Prepare for wider internal/external usage.

**What is implemented locally:**
- Backend pytest, frontend Vitest, Playwright E2E, fake smoke, dry-run OpenFOAM smoke, real NACA smoke, and bad-mesh smoke quality gates.
- Release checklist through `scripts/release-check.ps1` plus the real-solver acceptance scripts.
- Full local V1 acceptance through `scripts\release-v1-local.ps1`, which runs the runtime report, fast release check, WSL/OpenFOAM preflight, real NACA validation, and bad-mesh validation.
- Optional heavier local V1 acceptance through `scripts\release-v1-local.ps1 -IncludeValidationMeshSuite`, which also runs NACA 0012, cylinder, and square-box generated mesh smokes.
- GitHub Actions CI for the frontend build and fast release gate on `push` and `pull_request`.
- Operational runbooks and known limits in `README.md`, `docs/LOCAL_OPENFOAM_NO_API_RUNBOOK.md`, `docs/EXTERNAL_AERO_V1_ROADMAP.md`, and `AGENTS.md`.

**Remaining before wider release:**
- Real OpenFOAM smoke tests remain local through `scripts\release-v1-local.ps1` unless the CI runner is later provisioned with WSL/OpenFOAM or a Linux OpenFOAM image.

**Keywords:** `CI`, `quality gates`, `release checklist`, `runbook`.
