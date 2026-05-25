# External-Aero V1 Roadmap

This is the active roadmap from the current NACA/OpenFOAM prototype to a usable local external-aerodynamics V1.

## Current Baseline

The local browser app already supports upload, simulation spec capture, run status, events, artifacts, fake mode, and local OpenFOAM through WSL2. The real validation path is a generated NACA 4412 2D airfoil mesh at `25 m/s`, `2 deg` angle of attack, `1 m` chord, and `nu=1.5e-5 m^2/s`.

The supported production input for V1 is a premeshed Gmsh `.msh` file. STEP/STL upload remains best-effort.

## Phase 3A: Aerodynamic Coefficients

Status: implemented.

The `airfoil_2d` OpenFOAM case writes a `system/forceCoeffs` function object and includes it from `system/controlDict`.

Settings:

- patch: `airfoil`
- `dragDir = (cos(AoA), sin(AoA), 0)`
- `liftDir = (-sin(AoA), cos(AoA), 0)`
- `pitchAxis = (0, 0, 1)`
- `CofR = (0.25, 0, 0)`
- `rhoInf = 1`
- `magUInf = spec.velocity`
- `lRef = 1`
- `Aref = 0.01`

Generated outputs:

- `forceCoeffs.dat`
- `forceCoeffs.csv`
- `force-coefficients.png`
- `RunRecord.summary.final_coefficients`

Acceptance:

- NACA run reaches `completed`.
- Coefficients come from OpenFOAM `postProcessing/forceCoeffs1/.../forceCoeffs.dat`.
- No external aerodynamic coefficient data is imported.

## Phase 3B: Mesh And Boundary Validation

Status: implemented.

Every local OpenFOAM run writes `mesh-validation.json` before case generation. If a mesh looks like an `airfoil_2d` case but is missing a required physical name, the run fails before `gmshToFoam`.

Required `airfoil_2d` Gmsh physical names:

- `airfoil`
- `inlet`
- `outlet`
- `farfield`
- `frontAndBack`
- `internal`

Generic `.msh` files are still accepted, but they are marked lower confidence because the deterministic case template cannot fully infer user intent from arbitrary patch names.

## Phase 3C: Dashboard Polish For Real Runs

Status: implemented for the V1 static dashboard.

The React dashboard displays real-run images from artifact discovery and adds compact metric cards when run metadata is available:

- cells
- Reynolds number
- `checkMesh` pass/fail
- `Cl`
- `Cd`
- `Cm`

The local HTML report includes force coefficient links and final coefficient values when available.

## Phase 3D: `.msh` Production Workflow Hardening

Status: implemented for V1; STL/snappyHexMesh reliability slice added.

Implemented:

- Frontend copy says premeshed `.msh` is the supported V1 path.
- Frontend names the expected `airfoil_2d` physical names.
- Backend records explicit mesh validation output.
- Bad patch sets fail with an actionable message.
- `docs/GMSH_AIRFOIL_2D_TEMPLATE.md` documents the required physical names and a known-good generation path.
- STEP/STL conversion failures distinguish missing Gmsh, missing volume mesh, missing physical names, and general geometry failures.
- Converted STEP/STL/CAD meshes without Gmsh `PhysicalNames` fail before the solver with an explicit premeshed `.msh` recommendation.
- STL uploads in local OpenFOAM mode now route to a dedicated `snappyHexMesh` case scaffold instead of being forced through weak Gmsh conversion.
- STEP/STP uploads in local OpenFOAM mode now use Gmsh to export an STL surface, then route through the same `snappyHexMesh` case scaffold.
- STL/STEP surface intake now runs a pre-solver geometry diagnostic using `trimesh` plus `networkx`. It writes `geometry-diagnostics.json`, checks watertightness, disconnected body count, winding consistency, enclosed volume, scale hints, and safe repair attempts, then stops before OpenFOAM if the surface is not solver-ready.
- `scripts\generate-snappy-stl-case.ps1` builds an inspectable local STL case under `.local-data\snappy-stl-case\` using `surfaceCheck`, `blockMesh`, `surfaceFeatures`, `snappyHexMesh`, and `checkMesh` commands.
- The tracked `samples\obstacle-box.stl` and `samples\obstacle-box.step` fixtures give repeatable local checks for both surface and CAD intake.

Important limit: this improves arbitrary STL/STEP reliability, but it does not make arbitrary user geometry 100% guaranteed. Bad scale, holes, self-intersections, non-manifold edges, multi-body geometry, and poor feature detail can still fail the diagnostic gate, `surfaceCheck`, `snappyHexMesh`, or `checkMesh`.

## Phase 3E: Visualization Upgrade Path

Status: static V1 visuals and image inspection implemented; richer VTK interactivity deferred.

The V1 viewer intentionally uses lightweight static PNGs:

- `pressure.png`
- `velocity-magnitude.png`
- `residuals.png`
- `force-coefficients.png`

Pressure and velocity previews are generated from ASCII OpenFOAM VTK point data as coarse binned heatmaps, with the solid airfoil/obstacle body filled from patch VTK points and the focus outline still visible.

The browser dashboard now lets users inspect those PNG artifacts in a larger preview dialog and open the raw image artifact directly.

Do not block V1 on interactive 3D. Add vtk.js or PyVista/ParaView-style viewing only after more real user `.msh` cases have been tested against the static OpenFOAM-derived outputs and metrics.

## Phase 4: Local Reproducibility

Status: implemented for the current Windows/WSL target.

Commands:

```powershell
.\scripts\runtime-report.ps1
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\generate-snappy-stl-case.ps1
.\scripts\dev-openfoam-backend.ps1 -DryRun
.\scripts\smoke-local-openfoam.ps1 -DryRun
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-naca-openfoam.ps1 -TimeoutSeconds 1200
.\scripts\smoke-stl-snappy-openfoam.ps1
.\scripts\smoke-step-snappy-openfoam.ps1
.\scripts\smoke-bad-mesh-validation.ps1
```

The NACA smoke regenerates the validation mesh and enforces:

- completed run
- `checkMesh` artifacts
- residual artifacts
- pressure/velocity PNGs
- force coefficient CSV/PNG/dat artifacts
- final `Cl/Cd/Cm`
- cell count at or above `40,000`

The bad-mesh smoke enforces clean failure before solver execution.

`dev-openfoam-wsl.ps1 -CheckOnly` also reports whether Windows `gmsh` is available, because NACA generation and STEP/STL conversion use the Windows Gmsh executable while OpenFOAM itself runs inside WSL.

`runtime-report.ps1` writes `.local-data/runtime-report.json` with Windows, Git, Python, Node, npm, Gmsh, WSL distro, OpenFOAM version, and required OpenFOAM command availability. Use this file to compare machines before debugging solver behavior.

The WSL/OpenFOAM preflight now checks the STL/snappy toolchain too: `surfaceCheck`, `blockMesh`, `surfaceFeatures`, and `snappyHexMesh`.

## Phase 5: Usable Local V1 Release

Status: usable local V1 candidate; rerun all gates after each solver-path change.

Release quality gates:

- backend tests pass
- frontend tests pass
- Playwright E2E passes
- `release-check.ps1` passes
- real NACA validation passes
- real STL/snappy validation passes
- real STEP-to-STL/snappy validation passes
- STL/STEP artifacts include `geometry-diagnostics.json`
- bad mesh validation fails clearly

One-command local V1 acceptance:

```powershell
.\scripts\release-v1-local.ps1
```

That script runs `runtime-report.ps1`, `release-check.ps1`, `dev-openfoam-wsl.ps1 -CheckOnly`, `smoke-naca-openfoam.ps1`, `smoke-stl-snappy-openfoam.ps1`, `smoke-step-snappy-openfoam.ps1`, and `smoke-bad-mesh-validation.ps1` against a temporary local OpenFOAM backend.

GitHub Actions now runs the fast release gate on `push` and `pull_request`: frontend production build, backend tests, frontend tests, fake-mode smoke, Playwright E2E, and local OpenFOAM dry-run smoke. Real NACA and bad-mesh OpenFOAM validation remain local/manual gates because they depend on this machine's WSL/OpenFOAM runtime.

V1 remains scoped to local external aerodynamics only. Heat transfer, vibrations, aeroelastic coupling, Ansys, cloud collaboration, and interactive 3D are later milestones.
