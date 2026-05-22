# Optional Foam-Agent MCP Runbook

Use this optional path when you want Foam-Agent/OpenFOAM execution instead of fake-mode smoke runs. This path requires a model provider API key. It is no longer the primary V1 real-solver plan.

For the no-API-key local OpenFOAM direction, read `LOCAL_OPENFOAM_NO_API_RUNBOOK.md`.

## Startup Sequence

Terminal 1:

```powershell
.\scripts\dev-foamagent.ps1
```

Terminal 2:

```powershell
.\scripts\dev-real-backend.ps1
.\scripts\dev-frontend.ps1
```

Open `http://localhost:5173`. Backend API: `http://localhost:8000`.

## Preflight And Health Checks

```powershell
.\scripts\dev-foamagent.ps1 -CheckOnly
.\scripts\smoke-mcp-health.ps1
```

## Optional Real Solver Smoke

This uploads `samples/wing.msh`, creates a real MCP-backed run, and polls up to 20 minutes.

```powershell
.\scripts\smoke-real-run.ps1
```

## Required Environment

Copy `.env.example` to `.env` and set:

- `OPENAI_API_KEY`
- `FOAM_AGENT_MODE=mcp` (set automatically by `dev-real-backend.ps1`)
- `FOAM_AGENT_URL=http://127.0.0.1:7860/mcp`
- `FOAM_AGENT_APP_RUNS_ROOT` to your host `data/foamagent-runs` path when not using `dev-real-backend.ps1`

`dev-real-backend.ps1` reads `.env` and exports `OPENAI_API_KEY` for the backend preflight. It does not print the key.

## Current Acceptance Blockers

As of May 22, 2026, fake-mode regression is passing, but real-mode acceptance has not run because:

- Docker Desktop daemon is not running on this machine.
- `.env` is missing, so `OPENAI_API_KEY` is not available.

After those are fixed, run:

```powershell
.\scripts\dev-foamagent.ps1 -CheckOnly
.\scripts\dev-foamagent.ps1
.\scripts\dev-real-backend.ps1
.\scripts\smoke-mcp-health.ps1
.\scripts\smoke-real-run.ps1
```

## Troubleshooting

| Symptom | Likely Cause | What To Do |
| --- | --- | --- |
| `Docker daemon is not reachable` | Docker Desktop stopped | Start Docker Desktop, rerun `dev-foamagent.ps1 -CheckOnly` |
| `OPENAI_API_KEY is missing` | `.env` not configured | Copy `.env.example`, set a real key |
| `Foam-Agent MCP is not reachable` | Container not started or wrong port | Run `dev-foamagent.ps1`, then `smoke-mcp-health.ps1` |
| Run fails before planning | Real-mode preflight failed | Check backend run error and `.env` values |
| Completed run with no images | Visualization step failed or mirroring path mismatch | Inspect `data/runs/<run_id>/foamagent-*.json` and `data/foamagent-runs/` |
| Solver failure after review | OpenFOAM setup issue | Read `foamagent-run.json`, `foamagent-review.json`, mirrored logs |

## Fast Regression Path

Fake mode remains the default development path:

```powershell
.\scripts\dev-backend.ps1
.\scripts\dev-frontend.ps1
.\scripts\release-check.ps1
```
