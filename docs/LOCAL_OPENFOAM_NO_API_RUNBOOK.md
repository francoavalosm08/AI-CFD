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

Capture a reproducibility report for this machine:

```powershell
.\scripts\runtime-report.ps1
```

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

NACA 4412 validation and bad-mesh validation:

```powershell
.\scripts\smoke-naca-openfoam.ps1 -TimeoutSeconds 1200
.\scripts\smoke-bad-mesh-validation.ps1
```

Downloaded mesh corpus and generated working validation meshes:

```powershell
.\scripts\download-mesh-corpus.ps1
.\scripts\generate-validation-meshes.ps1
.\scripts\smoke-validation-mesh-suite.ps1
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\validation-meshes\cylinder.msh -TimeoutSeconds 900
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\validation-meshes\box.msh -TimeoutSeconds 900
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\validation-meshes\naca0012.msh -TimeoutSeconds 1800
```

The validation suite writes `.local-data\validation-meshes\validation-suite-report.json` so run IDs, artifact counts, event counts, case types, cell counts, and final coefficients can be reviewed later.

Generate an inspectable snappyHexMesh STL case:

```powershell
.\scripts\generate-snappy-stl-case.ps1 -StlPath samples\obstacle-box.stl -OutputDir .local-data\snappy-stl-case
```

That script writes a case folder plus `openfoam-commands.json` with the manual sequence:

```text
surfaceCheck constant/triSurface/obstacle.stl
blockMesh
surfaceFeatures
snappyHexMesh -overwrite
checkMesh -allGeometry -allTopology
simpleFoam
```

Use this path for STL reliability work. It is stricter and more OpenFOAM-native than forcing arbitrary STL through Gmsh, but it still depends on closed/watertight geometry and passing `checkMesh`. The backend treats default `checkMesh` as the required STL gate and keeps `checkMesh -allGeometry -allTopology` as optional strict diagnostics because strict geometry can flag concave snapped cells even when the baseline mesh is usable.

Run real surface/CAD intake gates:

```powershell
.\scripts\smoke-stl-snappy-openfoam.ps1
.\scripts\smoke-step-snappy-openfoam.ps1
```

The STEP path first converts CAD to an STL surface with Gmsh, then uses the same `snappyHexMesh` case builder as direct STL uploads. This is a real improvement over requiring STEP to become a Gmsh `.msh` with physical names, but complex CAD can still need cleanup before Gmsh can export a watertight surface.

Full local V1 release acceptance:

```powershell
.\scripts\release-v1-local.ps1
```

This runs the runtime report, fast release check, WSL/OpenFOAM preflight, real NACA validation, and bad-mesh validation against a temporary local OpenFOAM backend.

For the heavier three-mesh solver gate, use:

```powershell
.\scripts\release-v1-local.ps1 -IncludeValidationMeshSuite
```

CI note: GitHub Actions runs the frontend production build and fast `release-check.ps1` gate, including fake-mode smoke, browser E2E, and local OpenFOAM dry-run smoke. Real NACA and bad-mesh validation stay local/manual unless a CI runner is provisioned with OpenFOAM.

First committed sample mesh generator:

```powershell
gmsh samples\external_box.geo -3 -format msh2 -o .local-data\external_box.msh
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\external_box.msh -TimeoutSeconds 300
```

NACA 4412 airfoil validation generator:

```powershell
.\scripts\generate-naca4412.ps1 -OutputDir .local-data\naca4412-improved
.\scripts\smoke-local-openfoam.ps1 -SampleMeshPath .local-data\naca4412-improved\naca4412.msh -TimeoutSeconds 900
```

The NACA generator creates `naca4412.geo`, `naca4412.stl`, and a Gmsh 2.2 `.msh` with these named patches:

- `airfoil`
- `inlet`
- `outlet`
- `farfield`
- `frontAndBack`
- `internal`

The backend validates that patch set before `gmshToFoam`, records the result in `mesh-validation.json`, and treats it as a 2D airfoil case. It sets `frontAndBack` to `empty`, sets the imported `airfoil` patch type to `wall`, applies no-slip/wall-compatible turbulence fields on the airfoil, enables OpenFOAM `forceCoeffs` on the `airfoil` patch, and records chord, kinematic viscosity, Reynolds number, mesh cell count, `checkMesh` summary, and final `Cl/Cd/Cm` when available.

For user-created meshes, follow `docs/GMSH_AIRFOIL_2D_TEMPLATE.md`. A production V1 `.msh` should be a Gmsh 2.2 ASCII volume mesh with physical names `airfoil`, `inlet`, `outlet`, `farfield`, `frontAndBack`, and `internal`.

Simple non-airfoil obstacle meshes can use the `external_2d_obstacle` contract with physical names `obstacle`, `inlet`, `outlet`, `farfield`, `frontAndBack`, and `internal`. See `docs/MESH_VALIDATION_CORPUS.md`.

None of these should require `.env` or `OPENAI_API_KEY`.

## What Must Be Installed

On Windows, OpenFOAM should run through WSL2 Ubuntu for V1 because OpenFOAM is Linux-native.

Required runtime tools:

- WSL2
- Ubuntu distro
- OpenFOAM installed inside Ubuntu
- OpenFOAM environment sourceable from bash
- Windows `gmsh` on PATH for NACA generation and STEP/STL conversion
- `gmshToFoam`
- `checkMesh`
- `simpleFoam`
- `surfaceCheck`
- `blockMesh`
- `surfaceFeatures`
- `snappyHexMesh`
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
- `mesh-validation.json`
- `checkMesh.log`
- `solver.log`
- `residuals.csv`
- `residuals.png`
- `forceCoeffs.dat`
- `forceCoeffs.csv`
- `force-coefficients.png`
- `velocity-magnitude.png`
- `pressure.png`
- `openfoam-case.zip`
- `openfoam-report.html`
- VTK files when available
- final `Cl`, `Cd`, and `Cm` when an `airfoil_2d` run generates `forceCoeffs`

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
- generated NACA 4412 validation mesh/report scripts
- 2D airfoil patch handling for `airfoil`, `inlet`, `outlet`, `farfield`, and `frontAndBack`
- automatic PNG previews from OpenFOAM outputs: residual plot from `residuals.csv`, and pressure/velocity binned heatmap previews from ASCII VTK with the solid airfoil/obstacle body filled from patch VTK points
- WSL-native staging under `/tmp/ai-cfd-workbench/<run_id>/case` for real runs, with copy-back into `.local-data/runs/<run_id>/case`
- pre-run `.msh` physical-name validation for the `airfoil_2d` template
- dedicated STL/snappyHexMesh case generation for local OpenFOAM mode
- STEP/STP-to-STL conversion for the same snappyHexMesh path
- OpenFOAM `forceCoeffs` setup for `airfoil_2d` and final coefficient parsing
- force coefficient CSV/PNG/report/dashboard outputs
- production `.msh` guidance in `docs/GMSH_AIRFOIL_2D_TEMPLATE.md`
- clearer STEP/STL conversion failures for missing Gmsh, missing volume meshes, missing physical names, and geometry failures
- browser image inspection for generated pressure, velocity, residual, and force coefficient PNGs
- runtime reproducibility reporting with `scripts\runtime-report.ps1`
- one-command local V1 release acceptance with `scripts\release-v1-local.ps1`

Latest NACA 4412 validation result on this machine:

- Inputs: `25 m/s`, `2 deg` angle of attack, `1 m` chord, `nu=1.5e-5 m^2/s`.
- Computed metadata: `Re=1.666666e6`.
- OpenFOAM result: run reached `completed`.
- `checkMesh`: passed.
- Cell count: `57,292`.
- Final OpenFOAM-derived coefficients from latest accepted run: `Cl=0.4591685`, `Cd=0.02907224`, `Cm=0.09620507`.
- Artifacts: `mesh-validation.json`, `checkMesh.log`, `solver.log`, `residuals.csv`, `residuals.png`, `forceCoeffs.dat`, `forceCoeffs.csv`, `force-coefficients.png`, `velocity-magnitude.png`, `pressure.png`, VTK files, `openfoam-case.zip`, and `openfoam-report.html`.

Next implementation work:

1. Run fresh real NACA and bad-mesh smoke validation after each solver-path change.
2. Test more user-provided `.msh` files against the documented physical-name contract.
3. Upgrade from static binned heatmap PNG inspection to PyVista/vtk.js contours when interactive visualization is needed.

## Troubleshooting Targets

| Symptom | Likely Cause | Planned Handling |
| --- | --- | --- |
| WSL command fails | WSL2 or distro missing | Preflight fails before run |
| OpenFOAM command missing | OpenFOAM not installed or bashrc not sourced | Preflight reports missing command |
| Path with spaces fails | Windows-to-WSL quoting issue | Unit-tested path adapter |
| `checkMesh` fails | Mesh invalid or boundary mismatch | Run fails with `checkMesh.log` artifact |
| STEP conversion fails before OpenFOAM | Missing Gmsh or CAD geometry that cannot export to a clean STL surface | Error recommends CAD cleanup, watertight STL export, or premeshed `.msh` |
| STL snappy meshing fails | Open STL, self-intersections, bad scale, or inadequate refinement | Inspect `surfaceCheck.log`, `surfaceFeatures.log`, `snappyHexMesh.log`, `checkMesh.log`, and use `scripts\generate-snappy-stl-case.ps1` |
| Solver diverges | Bad case defaults or mesh quality | Run fails with `solver.log` and zipped case |
| No visualization | `foamToVTK` or PyVista missing | Still return logs/case zip; PNGs are optional |
