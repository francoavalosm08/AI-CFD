# AI CFD Workbench

Automating CFD with a local browser app for external-aerodynamics runs through Foam-Agent and OpenFOAM.

## What V1 Does

- Upload `.msh`, `.stl`, `.step`, `.stp`, or `.zip` files.
- Ask for external-aero specifications: velocity, angle of attack, units, scale, mesh quality, and runtime.
- Build a deterministic Foam-Agent prompt and run the Foam-Agent MCP workflow.
- Show an HTML dashboard with status, run logs, PyVista images, residual/plot files, and downloads.

## Project Handoff And Docs

Fresh LLM/coding-agent pickup instructions are in `AGENTS.md`. The docs index is in `docs/README.md`, with the current next milestone in `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`.

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

## Real Foam-Agent/OpenFOAM Mode (Local Docker + MCP)

Use this when you want real solver execution. Fake mode remains the default fast regression path.

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

See `docs/REAL_MODE_RUNBOOK.md` and `docs/PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md` for troubleshooting and acceptance details.

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

Run one command for backend tests, frontend tests, fake-mode smoke flow, and browser E2E:

```powershell
.\scripts\release-check.ps1
```

## Run With Docker

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
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
| STEP/STL conversion fails | `gmsh` missing | Install Gmsh or use `.msh` upload |
| `dev-foamagent.ps1` fails immediately | Docker Desktop stopped | Start Docker Desktop and rerun `-CheckOnly` |
| `dev-real-backend.ps1` fails before startup | Foam-Agent MCP not reachable | Run `dev-foamagent.ps1`, then `smoke-mcp-health.ps1` |
| Real run fails before planning | Missing API key or shared runs path | Check `.env` and `data/foamagent-runs` |
| Real run completes with few artifacts | Mirroring or visualization issue | Inspect `data/runs/<run_id>/foamagent-*.json` |

## Notes

- `.msh` is the most reliable V1 input. STEP/STL conversion depends on Gmsh.
- Foam-Agent MCP writes OpenFOAM cases inside its own container; Compose mounts that `runs` directory into `./data/foamagent-runs` so the app can mirror visualization/log artifacts into each dashboard run.
- V1 intentionally excludes heat transfer, vibration, Ansys, and aeroelastic coupling.

