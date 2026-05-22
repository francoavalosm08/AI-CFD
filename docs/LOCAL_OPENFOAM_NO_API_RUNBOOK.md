# Local OpenFOAM No-API Runbook

This is the V1 real-solver path that avoids runtime LLM/API keys. The case-generation path, dry-run path, WSL preflight, and first real WSL/OpenFOAM sample smoke are implemented.

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

Install/verify WSL OpenFOAM runtime:

```powershell
.\scripts\install-openfoam-wsl.ps1 -UseWslRoot
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
```

Real solver workflow after WSL/OpenFOAM setup:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\dev-openfoam-backend.ps1
.\scripts\dev-frontend.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath <valid-external-aero-volume.msh>
```

First committed sample mesh generator:

```powershell
gmsh samples\external_box.geo -3 -format msh2 -o .local-data\external_box.msh
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\external_box.msh -TimeoutSeconds 300
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
- OpenFOAM 10 installed and sourceable in WSL `Ubuntu-22.04` on this development machine
- first real smoke mesh source in `samples/external_box.geo`
- WSL-native staging under `/tmp/ai-cfd-workbench/<run_id>/case` for real runs, with copy-back into `.local-data/runs/<run_id>/case`

Next implementation work:

1. Improve boundary detection and force coefficient setup based on real OpenFOAM logs.
2. Validate `.msh` boundary patches before solver execution and return a clear API/UI error if required patches are missing.
3. Improve STEP/STL mesh-prep failures while keeping `.msh` the most reliable first-class input.
4. Add richer visualization after VTK/log artifacts are reliable.

## Troubleshooting Targets

| Symptom | Likely Cause | Planned Handling |
| --- | --- | --- |
| WSL command fails | WSL2 or distro missing | Preflight fails before run |
| OpenFOAM command missing | OpenFOAM not installed or bashrc not sourced | Preflight reports missing command |
| Path with spaces fails | Windows-to-WSL quoting issue | Unit-tested path adapter |
| `checkMesh` fails | Mesh invalid or boundary mismatch | Run fails with `checkMesh.log` artifact |
| Solver diverges | Bad case defaults or mesh quality | Run fails with `solver.log` and zipped case |
| No visualization | `foamToVTK` or PyVista missing | Still return logs/case zip; PNGs are optional |
