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

Status: partially implemented.

Implemented:

- Frontend copy says `.msh` is the reliable V1 path.
- Frontend names the expected `airfoil_2d` physical names.
- Backend records explicit mesh validation output.
- Bad patch sets fail with an actionable message.

Remaining:

- Add a sample `.geo` template document for user-provided 2D airfoil meshes.
- Improve STEP/STL conversion failures so they distinguish surface-only meshes, missing physical names, and bad geometry.
- Add a short UI link or inline help panel for expected Gmsh physical names.

## Phase 3E: Visualization Upgrade Path

Status: static V1 visuals implemented; richer interactivity deferred.

The V1 viewer intentionally uses lightweight static PNGs:

- `pressure.png`
- `velocity-magnitude.png`
- `residuals.png`
- `force-coefficients.png`

Do not block V1 on interactive 3D. Add vtk.js or PyVista/ParaView-style viewing only after the static OpenFOAM-derived outputs and metrics are stable.

## Phase 4: Local Reproducibility

Status: scripts added; run the real acceptance scripts after each solver-path change.

Commands:

```powershell
.\scripts\dev-openfoam-wsl.ps1 -CheckOnly
.\scripts\dev-openfoam-backend.ps1 -DryRun
.\scripts\smoke-local-openfoam.ps1 -DryRun
.\scripts\dev-openfoam-backend.ps1
.\scripts\smoke-naca-openfoam.ps1 -TimeoutSeconds 1200
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

## Phase 5: Usable Local V1 Release

Status: close, pending fresh full verification and real NACA acceptance after each solver-path change.

Release quality gates:

- backend tests pass
- frontend tests pass
- Playwright E2E passes
- `release-check.ps1` passes
- real NACA validation passes
- bad mesh validation fails clearly

V1 remains scoped to local external aerodynamics only. Heat transfer, vibrations, aeroelastic coupling, Ansys, cloud collaboration, and interactive 3D are later milestones.
