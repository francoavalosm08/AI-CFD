# Local OpenFOAM No-API Runbook

This is the target V1 real-solver path. It is planned, not fully implemented yet.

## Purpose

Run OpenFOAM locally without a runtime LLM API key. The backend should generate deterministic OpenFOAM cases from the browser-provided simulation spec, execute OpenFOAM commands, and publish logs/artifacts to the existing dashboard.

## Runtime Shape

```text
React/Vite browser
  -> FastAPI backend
  -> deterministic OpenFOAM case builder
  -> WSL2 Ubuntu OpenFOAM commands
  -> logs, residuals, VTK/case artifacts
```

## Why No API Key Is Needed

OpenFOAM does not need an API key. The previous key requirement came from Foam-Agent using an LLM provider to generate and review case files.

The no-API path generates case files using local templates and known V1 assumptions:

- incompressible external aerodynamics
- `.msh` input first
- `simpleFoam` first
- conservative turbulence defaults
- local command execution

## Planned Commands

After implementation, the intended workflow is:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\dev-openfoam-backend.ps1
.\scripts\dev-frontend.ps1
.\scripts\smoke-local-openfoam.ps1 -DryRun
.\scripts\smoke-local-openfoam.ps1
```

None of these should require `.env` or `OPENAI_API_KEY`.

## What Must Be Installed

On Windows, OpenFOAM should run through WSL2 Ubuntu for V1 because OpenFOAM is Linux-native.

Required runtime tools:

- WSL2
- Ubuntu distro
- OpenFOAM installed inside Ubuntu
- OpenFOAM environment sourceable from bash
- `gmshToFoam`
- `checkMesh`
- `simpleFoam`
- `foamToVTK` if VTK export is enabled

## Manual Step-By-Step Mode

Each run should write `openfoam-commands.json` before executing commands. That file lets an IDE agent or human run the same steps manually:

```text
1. import mesh with gmshToFoam
2. run checkMesh
3. run simpleFoam
4. export VTK/artifacts
5. parse logs and update dashboard
```

Dry-run mode should create the case folder and command manifest without executing solver commands.

## Expected Artifacts

The dashboard should show or offer:

- `openfoam-commands.json`
- `case-manifest.json`
- `checkMesh.log`
- `solver.log`
- `residuals.csv`
- `openfoam-case.zip`
- VTK files when available
- force/force coefficient logs when configured
- PNG images later if local visualization dependencies are installed

## Current Status

The repo currently has:

- fake-mode workflow passing
- optional Foam-Agent MCP path implemented and tested
- no-API local OpenFOAM path planned in `PHASE_3_REAL_FOAMAGENT_OPENFOAM_PLAN.md`

Next implementation work:

1. Add local runner settings.
2. Add WSL path adapter and OpenFOAM preflight.
3. Add deterministic case builder.
4. Add command runner and dry-run mode.
5. Add log/artifact parsers.
6. Wire the runner into `/api/runs`.
7. Add no-API smoke scripts.

## Troubleshooting Targets

| Symptom | Likely Cause | Planned Handling |
| --- | --- | --- |
| WSL command fails | WSL2 or distro missing | Preflight fails before run |
| OpenFOAM command missing | OpenFOAM not installed or bashrc not sourced | Preflight reports missing command |
| Path with spaces fails | Windows-to-WSL quoting issue | Unit-tested path adapter |
| `checkMesh` fails | Mesh invalid or boundary mismatch | Run fails with `checkMesh.log` artifact |
| Solver diverges | Bad case defaults or mesh quality | Run fails with `solver.log` and zipped case |
| No visualization | `foamToVTK` or PyVista missing | Still return logs/case zip; PNGs are optional |

