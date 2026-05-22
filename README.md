# AI CFD Workbench

Automating CFD with a local browser app for external-aerodynamics runs through OpenFOAM.

## What V1 Does

- Upload `.msh`, `.stl`, `.step`, `.stp`, or `.zip` files.
- Ask for external-aero specifications: velocity, angle of attack, units, scale, mesh quality, and runtime.
- Build a deterministic simulation spec and run fake mode or the local OpenFOAM case-generation path.
- Show an HTML dashboard with status, run logs, static OpenFOAM-derived images, residual/coefficient plots, summary metrics, and downloads.

## Project Handoff And Docs

Fresh LLM/coding-agent pickup instructions are in `AGENTS.md`. The docs index is in `docs/README.md`, with the current roadmap in `docs/EXTERNAL_AERO_V1_ROADMAP.md`. The local OpenFOAM implementation plan is in `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md` and does not require a runtime API key.

## Local Non-Docker Development (Windows + Fake Mode)

This workflow avoids Docker for day-to-day development and defaults to fake-mode runs.

1. First-day baseline check (recommended before starting dev terminals):

```powershell
.\scripts\local-verify.ps1
```

2. Start backend in one terminal:

```powershell
.\scripts\dev-backend.ps1
```

3. Start frontend in a second terminal:

```powershell
.\scripts\dev-frontend.ps1
```

4. Run fake-mode smoke test in a third terminal:

```powershell
.\scripts\smoke-fake-run.ps1
```

Open the app at `http://localhost:5173`. Backend API runs at `http://localhost:8000`.

Local backend run data is written under `.local-data/` (gitignored).

## No-API Local OpenFOAM Mode

The V1 real-solver path now has a deterministic local OpenFOAM runner. It does not require `.env` or `OPENAI_API_KEY`.

Dry-run mode is the first acceptance path: it writes an OpenFOAM case folder, command manifest, and downloadable zip without executing solver binaries.

Commands:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\dev-openfoam-backend.ps1 -DryRun
.\scripts\dev-frontend.ps1
.\scripts\smoke-local-openfoam.ps1 -DryRun
```

If OpenFOAM is not installed in WSL yet, install and verify the expected Ubuntu 22.04/OpenFOAM 10 runtime:

```powershell
.\scripts\install-openfoam-wsl.ps1 -UseWslRoot
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
```

After WSL2 Ubuntu and OpenFOAM are installed, start the backend without `-DryRun` and use a real external-aero `.msh`. The repo includes a simple Gmsh source file for this acceptance smoke:

```powershell
gmsh samples\external_box.geo -3 -format msh2 -o .local-data\external_box.msh
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\external_box.msh -TimeoutSeconds 300
```

The backend stages real WSL runs under `/tmp/ai-cfd-workbench/<run_id>/case` and copies the finished case back into `.local-data/runs/<run_id>/case`. This avoids OpenFOAM path issues when the Windows repo path contains spaces.

The repo also includes a generated NACA 4412 validation mesh path for the current airfoil hardening work. It creates `.geo`, `.stl`, and `.msh` files locally, then the backend recognizes the airfoil-specific patch names and writes a 2D OpenFOAM case with `frontAndBack` empty boundaries:

```powershell
.\scripts\generate-naca4412.ps1 -OutputDir .local-data\naca4412-improved
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\naca4412-improved\naca4412.msh -TimeoutSeconds 900
```

The NACA 4412 validation path uses `25 m/s`, `2 deg` angle of attack, `1 m` chord, and `nu=1.5e-5 m^2/s` (`Re=1.666666e6`). OpenFOAM `checkMesh` must pass with at least `40,000` cells. The V1 acceptance outputs are `mesh-validation.json`, `checkMesh.log`, `solver.log`, `residuals.csv`, `forceCoeffs.dat`, `forceCoeffs.csv`, VTK files, `openfoam-case.zip`, `openfoam-report.html`, and PNG previews for residuals, velocity magnitude, pressure, and force coefficients.

Latest accepted local NACA run: `57,292` cells, `Cl=0.4591685`, `Cd=0.02907224`, `Cm=0.09620507`, all parsed from OpenFOAM-generated files.

Dedicated real-solver validation scripts:

```powershell
.\scripts\smoke-naca-openfoam.ps1 -TimeoutSeconds 1200
.\scripts\smoke-bad-mesh-validation.ps1
```

For your own meshes:

```powershell
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-local-openfoam.ps1
```

For dependable V1 airfoil runs, use a premeshed Gmsh 2.2 ASCII `.msh` with physical names `airfoil`, `inlet`, `outlet`, `farfield`, `frontAndBack`, and `internal`. See `docs/GMSH_AIRFOIL_2D_TEMPLATE.md`, `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`, and `docs/LOCAL_OPENFOAM_NO_API_RUNBOOK.md`.

## Optional Foam-Agent/OpenFOAM Mode (Local Docker + MCP)

This path exists from the earlier Phase 3 work. It is now optional because it requires a model provider API key. Fake mode remains the default fast regression path, and local OpenFOAM is the next primary real-solver path.

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. Start Foam-Agent Docker:

```powershell
.\scripts\dev-foamagent.ps1
```

3. Start backend in MCP mode and frontend:

```powershell
.\scripts\dev-real-backend.ps1
.\scripts\dev-frontend.ps1
```

4. Verify MCP health:

```powershell
.\scripts\smoke-mcp-health.ps1
```

5. Optional real solver acceptance (slow, uses model/API credits):

```powershell
.\scripts\smoke-real-run.ps1
```

See `docs/REAL_MODE_RUNBOOK.md` for optional Foam-Agent/MCP troubleshooting and acceptance details.

## First Day Setup (Windows)

If this is your first run on a machine:

1. Run prerequisite check:

```powershell
.\scripts\dev-check.ps1
```

2. Run baseline local verification:

```powershell
.\scripts\local-verify.ps1
```

If you only need backend progress right now:

```powershell
.\scripts\local-verify.ps1 -Scope backend
```

## Release Check (Single Command)

Run one command for backend tests, frontend tests, fake-mode smoke flow, browser E2E, and local OpenFOAM dry-run smoke:

```powershell
.\scripts\release-check.ps1
```

## Optional Docker/Compose Validation

This is secondary infrastructure from the Foam-Agent/MCP path. It is not the primary no-API OpenFOAM plan.

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` only if using Foam-Agent/MCP.
2. Start Docker Desktop.
3. Run:

```bash
docker compose up --build
```

Open `http://localhost:8000`.

Set `FOAM_AGENT_MODE=fake` in `.env` for a fast UI/backend smoke test that does not call Foam-Agent.

## Optional Docker Validation (Secondary Path)

Local non-Docker remains the primary development path. Use Docker only for parity/integration checks:

```bash
docker compose up --build
```

Then verify health:

```bash
curl http://localhost:8000/api/health
```

## Local Backend Tests

```bash
cd backend
py -m pip install -e ".[test]"
py -m pytest
```

## Local Frontend Development

Use Node 22+:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000` to avoid Windows localhost IPv4/IPv6 mismatches.

## Common Setup Issues

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `dev-check.ps1` reports missing `node`/`npm` | Node.js not installed or not on `PATH` | Install Node 22+ and restart terminal |
| `dev-backend.ps1` fails with port in use | Another process already using backend port | Stop process on `:8000` or run `.\scripts\dev-backend.ps1 -Port <new-port>` |
| `smoke-fake-run.ps1` cannot reach `/api/health` | Backend not running | Start backend with `.\scripts\dev-backend.ps1` |
| Smoke test fails on upload/run | Backend dependencies incomplete | Rerun `.\scripts\local-verify.ps1` and check error output |
| STEP/STL conversion fails | `gmsh` missing, surface-only geometry, missing volume mesh, or missing physical names | Install Gmsh, repair the geometry into a cleaner closed STL/STEP, or use a premeshed Gmsh `.msh` upload |
| `.msh` airfoil run fails before OpenFOAM | Missing required Gmsh physical names | Use `airfoil`, `inlet`, `outlet`, `farfield`, `frontAndBack`, and `internal` |
| Local OpenFOAM preflight fails | WSL2/OpenFOAM missing | Install WSL2 Ubuntu and OpenFOAM, then rerun `.\scripts\dev-openfoam-wsl.ps1 -CheckOnly` |
| Real OpenFOAM run fails in a path containing spaces | OpenFOAM utilities can be brittle with mounted Windows paths | Use the built-in backend runner, which stages execution in WSL `/tmp` before copying artifacts back |
| `smoke-local-openfoam.ps1 -DryRun` reports wrong mode | Backend is still in fake mode | Start backend with `.\scripts\dev-openfoam-backend.ps1 -DryRun` |
| `dev-foamagent.ps1` fails immediately | Docker Desktop stopped | Start Docker Desktop and rerun `-CheckOnly` |
| `dev-real-backend.ps1` fails before startup | Foam-Agent MCP not reachable | Run `dev-foamagent.ps1`, then `smoke-mcp-health.ps1` |
| Real run fails before planning | Missing API key or shared runs path | Check `.env` and `data/foamagent-runs` |
| Real run completes with few artifacts | Mirroring or visualization issue | Inspect `data/runs/<run_id>/foamagent-*.json` |

## Notes

- `.msh` is the most reliable V1 input. STEP/STL conversion depends on Gmsh.
- Optional Foam-Agent MCP writes OpenFOAM cases inside its own container; Compose mounts that `runs` directory into `./data/foamagent-runs` so the app can mirror visualization/log artifacts into each dashboard run.
- V1 intentionally excludes heat transfer, vibration, Ansys, and aeroelastic coupling.

