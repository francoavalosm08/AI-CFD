# Mesh Validation Corpus

This project now separates two different mesh needs:

- **Downloaded corpus meshes**: public `.msh` files used to prove parser, provenance, checksum, and compatibility reporting.
- **Working solver meshes**: deterministic `.msh` files generated locally with the exact OpenFOAM V1 boundary contract.

## Downloaded Public `.msh` Corpus

Run:

```powershell
.\scripts\download-mesh-corpus.ps1
```

This downloads three public Gmsh `.msh` files from John Burkardt / FSU:

- `cylinder_2d.msh`
- `rectangle.msh`
- `step_2d.msh`

The files are written under `.local-data\external-mesh-corpus\`, with a `manifest.json` containing source URL, source label, license note, SHA-256 checksum, detected format, node/element counts, and V1 solver-readiness classification.

These files are not assumed to be solver-ready. The manifest records whether each mesh has the required OpenFOAM physical names. If it does not, the app reports that directly instead of forcing fake boundary conditions.

## Working Local Solver Meshes

Run:

```powershell
.\scripts\generate-validation-meshes.ps1
```

This creates three local working `.msh` files under `.local-data\validation-meshes\`:

- `naca0012.msh`: new airfoil case using the `airfoil_2d` contract.
- `cylinder.msh`: simple cylinder obstacle using the `external_2d_obstacle` contract.
- `box.msh`: simple square obstacle using the `external_2d_obstacle` contract.

The required physical names are:

- `airfoil_2d`: `inlet`, `outlet`, `farfield`, `airfoil`, `frontAndBack`, `internal`
- `external_2d_obstacle`: `inlet`, `outlet`, `farfield`, `obstacle`, `frontAndBack`, `internal`

To generate and run all three working meshes through real OpenFOAM in one command:

```powershell
.\scripts\smoke-validation-mesh-suite.ps1
```

The suite writes `.local-data\validation-meshes\validation-suite-report.json` with each case name, mesh path, run id, upload id, case type, cell count, artifact count, event count, artifact names, and final `Cl/Cd/Cm` values when OpenFOAM produced force coefficients.

To include that heavier gate inside the full local V1 release acceptance:

```powershell
.\scripts\release-v1-local.ps1 -IncludeValidationMeshSuite
```

## Acceptance Rule

Do not claim a mesh works unless the real local OpenFOAM smoke reaches `completed` and returns solver artifacts from actual OpenFOAM output. Static preview images must be generated from solver VTK/CSV output, not hand-drawn to match an expected look.
