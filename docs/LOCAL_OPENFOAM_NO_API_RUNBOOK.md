# Local OpenFOAM No-API Runbook

This is the V1 real-solver path that avoids runtime LLM/API keys. The case-generation and dry-run path is implemented; real solver acceptance depends on WSL2/OpenFOAM being installed on the machine.

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

## Commands

Dry-run workflow, no WSL/OpenFOAM required:

```powershell
.\scripts\dev-openfoam-backend.ps1 -DryRun
.\scripts\dev-frontend.ps1
.\scripts\smoke-local-openfoam.ps1 -DryRun
```

Real solver workflow after WSL/OpenFOAM setup:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\dev-openfoam-backend.ps1
.\scripts\dev-frontend.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath <valid-external-aero-volume.msh>
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

Each run writes `openfoam-commands.json` before executing commands. That file lets an IDE agent or human run the same steps manually:

```text
1. import mesh with gmshToFoam
2. run checkMesh
3. run simpleFoam
4. export VTK/artifacts
5. parse logs and update dashboard
```

Dry-run mode creates the case folder and command manifest without executing solver commands.

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
- local OpenFOAM runner settings
- WSL path adapter and preflight script
- deterministic `.msh` case builder
- command manifest and dry-run mode
- log/residual/artifact helpers
- local runner wired into `/api/runs`
- no-API smoke scripts

Next implementation work:

1. Run dry-run smoke in local verification after script validation is stable.
2. Install/verify WSL2 Ubuntu and OpenFOAM.
3. Run a real external-aero `.msh` through `smoke-local-openfoam.ps1`.
4. Improve boundary detection and force coefficient setup based on real OpenFOAM logs.

## Troubleshooting Targets

| Symptom | Likely Cause | Planned Handling |
| --- | --- | --- |
| WSL command fails | WSL2 or distro missing | Preflight fails before run |
| OpenFOAM command missing | OpenFOAM not installed or bashrc not sourced | Preflight reports missing command |
| Path with spaces fails | Windows-to-WSL quoting issue | Unit-tested path adapter |
| `checkMesh` fails | Mesh invalid or boundary mismatch | Run fails with `checkMesh.log` artifact |
| Solver diverges | Bad case defaults or mesh quality | Run fails with `solver.log` and zipped case |
| No visualization | `foamToVTK` or PyVista missing | Still return logs/case zip; PNGs are optional |
