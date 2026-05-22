# Gmsh Airfoil 2D Template

This is the user-facing contract for production-quality V1 `.msh` uploads.

## Supported V1 Mesh Shape

For dependable local OpenFOAM runs, upload a Gmsh 2.2 ASCII `.msh` volume mesh with a thin 3D extrusion of a 2D external-aerodynamics domain.

Required physical names:

- `airfoil`
- `inlet`
- `outlet`
- `farfield`
- `frontAndBack`
- `internal`

The backend treats this patch set as `airfoil_2d`, validates it before `gmshToFoam`, sets `frontAndBack` to `empty`, sets `airfoil` to `wall`, enables OpenFOAM `forceCoeffs` on `airfoil`, and reports `Cl`, `Cd`, and `Cm` from OpenFOAM output files.

## Minimal Physical Name Pattern

Use this pattern at the end of your `.geo` file after defining the curves, surfaces, and volume:

```c
// Boundary surfaces
Physical Surface("airfoil") = {airfoilSurfaceIds[]};
Physical Surface("inlet") = {inletSurfaceId};
Physical Surface("outlet") = {outletSurfaceId};
Physical Surface("farfield") = {topSurfaceId, bottomSurfaceId};
Physical Surface("frontAndBack") = {frontSurfaceId, backSurfaceId};

// Fluid volume
Physical Volume("internal") = {fluidVolumeId};
```

Those identifiers are placeholders. Replace them with the actual surface and volume ids created by your Gmsh geometry.

## Generate The Mesh

Generate a version 2 ASCII mesh:

```powershell
gmsh your_airfoil.geo -3 -format msh2 -o your_airfoil.msh
```

The V1 runner expects a volume mesh. A surface-only STL or 2D-only mesh may convert, but it will not be a dependable OpenFOAM input.

## Known-Good Local Example

Use the built-in NACA 4412 generator as a reference:

```powershell
.\scripts\generate-naca4412.ps1 -OutputDir .local-data\naca4412-improved
.\scripts\smoke-naca-openfoam.ps1 -TimeoutSeconds 1200
```

That generator creates `.geo`, `.stl`, and `.msh` files with the required physical names and a cell count above the current `40,000` acceptance floor.

## Common Failure Modes

| Failure | Meaning | Fix |
| --- | --- | --- |
| Missing `PhysicalNames` | The backend cannot map OpenFOAM boundaries reliably | Add the six required physical names or upload a premeshed `.msh` that already has them |
| Missing `frontAndBack` | The mesh cannot be treated as a 2D OpenFOAM case | Add both thin extrusion faces to `Physical Surface("frontAndBack")` |
| Surface-only conversion | Gmsh did not create a fluid volume | Repair the geometry into a closed domain or build the `.msh` directly in Gmsh |
| Bad patch names | The deterministic V1 template cannot infer boundary roles | Rename patches to the required V1 names |

STEP/STL upload remains best-effort. The production V1 path is a premeshed Gmsh `.msh` with the physical names above.
