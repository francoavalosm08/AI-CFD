from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.openfoam.case_builder import (
    _foam_number,
    _foam_tuple,
    _fv_schemes,
    _fv_solution,
    _transport_properties,
    _turbulence_properties,
    force_coefficient_directions,
)
from app.openfoam.templates import foam_header, vector
from app.schemas import SimulationSpec


SURFACE_PATCH = "obstacle"


def snappy_openfoam_commands() -> list[dict]:
    return [
        {
            "name": "surface_check",
            "command": "surfaceCheck constant/triSurface/obstacle.stl",
            "required": True,
        },
        {"name": "block_mesh", "command": "blockMesh", "required": True},
        {
            "name": "surface_features",
            "command": "surfaceFeatures",
            "required": True,
        },
        {
            "name": "snappy_hex_mesh",
            "command": "snappyHexMesh -overwrite",
            "required": True,
        },
        {
            "name": "check_mesh",
            "command": "checkMesh",
            "required": True,
        },
        {
            "name": "check_mesh_strict",
            "command": "checkMesh -allGeometry -allTopology",
            "required": False,
        },
        {"name": "solve", "command": "simpleFoam", "required": True},
        {"name": "export_vtk", "command": "foamToVTK -ascii", "required": False},
    ]


def build_snappy_stl_case(*, spec: SimulationSpec, stl_path: Path, case_dir: Path) -> dict:
    case_dir.mkdir(parents=True, exist_ok=True)
    for child in ("0", "constant", "constant/triSurface", "system"):
        (case_dir / child).mkdir(exist_ok=True)

    shutil.copy2(stl_path, case_dir / "constant" / "triSurface" / "obstacle.stl")
    domain = _domain(spec.length_scale)
    cells = _base_cells(spec.mesh_quality)
    force_coefficients = _force_coefficients_config(spec)
    files = {
        "0/U": _u_file(spec),
        "0/p": _p_file(),
        "0/k": _scalar_field("k", "volScalarField", "0.01", "[0 2 -2 0 0 0 0]", "kqRWallFunction"),
        "0/omega": _scalar_field("omega", "volScalarField", "1", "[0 0 -1 0 0 0 0]", "omegaWallFunction"),
        "0/nut": _scalar_field("nut", "volScalarField", "0", "[0 2 -1 0 0 0 0]", "nutkWallFunction"),
        "constant/transportProperties": _transport_properties(),
        "constant/turbulenceProperties": _turbulence_properties(),
        "system/blockMeshDict": _block_mesh_dict(domain, cells),
        "system/controlDict": _control_dict(spec),
        "system/fvSchemes": _fv_schemes(),
        "system/fvSolution": _fv_solution(),
        "system/forceCoeffs": _force_coeffs_file(force_coefficients),
        "system/meshQualityDict": _mesh_quality_dict(),
        "system/snappyHexMeshDict": _snappy_hex_mesh_dict(domain, spec.mesh_quality),
        "system/surfaceFeaturesDict": _surface_features_dict(),
    }
    for relative_path, content in files.items():
        (case_dir / relative_path).write_text(content, encoding="utf-8")

    manifest = {
        "runner": "local_openfoam",
        "case_type": "external_3d_stl_snappy",
        "mesh_source": "snappyHexMesh",
        "solver": "simpleFoam",
        "input_surface": str(stl_path),
        "surface_file": "constant/triSurface/obstacle.stl",
        "surface_patch": SURFACE_PATCH,
        "units": spec.units,
        "length_scale": spec.length_scale,
        "velocity": spec.velocity,
        "angle_of_attack": spec.angle_of_attack,
        "kinematic_viscosity_m2_s": 1.5e-05,
        "reynolds_number": round(spec.velocity * spec.length_scale / 1.5e-05, 6),
        "domain": domain,
        "base_cells": cells,
        "flow_assumption": "steady incompressible external aerodynamics",
        "force_coefficients": force_coefficients,
        "commands": snappy_openfoam_commands(),
        "files": sorted(["constant/triSurface/obstacle.stl", *files.keys()]),
        "limitations": [
            "STL must be closed/watertight and consistently scaled before snappyHexMesh can make a reliable volume mesh.",
            "This V1 STL path creates a conservative external flow box automatically; inspect snappyHexMesh.log and checkMesh.log before trusting results.",
            "STEP/CAD cleanup is not handled by this path yet; use a premeshed .msh when exact boundary control matters.",
        ],
    }
    (case_dir / "snappy-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (case_dir / "case-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def _domain(length_scale: float) -> dict[str, list[float]]:
    length = float(length_scale)
    return {
        "x": [_round_domain(-5 * length), _round_domain(10 * length)],
        "y": [_round_domain(-5 * length), _round_domain(5 * length)],
        "z": [_round_domain(-5 * length), _round_domain(5 * length)],
        "locationInMesh": [_round_domain(-2 * length), 0.0, 0.0],
    }


def _round_domain(value: float) -> float:
    rounded = round(value, 6)
    return 0.0 if abs(rounded) < 0.0000005 else rounded


def _base_cells(mesh_quality: str) -> list[int]:
    return {
        "coarse": [30, 20, 20],
        "balanced": [45, 30, 30],
        "fine": [70, 45, 45],
    }.get(mesh_quality, [45, 30, 30])


def _refinement_levels(mesh_quality: str) -> tuple[int, int]:
    return {
        "coarse": (1, 2),
        "balanced": (2, 3),
        "fine": (3, 4),
    }.get(mesh_quality, (2, 3))


def _block_mesh_dict(domain: dict[str, list[float]], cells: list[int]) -> str:
    x0, x1 = domain["x"]
    y0, y1 = domain["y"]
    z0, z1 = domain["z"]
    nx, ny, nz = cells
    return f"""{foam_header("dictionary", "blockMeshDict")}
scale 1;

vertices
(
    ({x0:g} {y0:g} {z0:g})
    ({x1:g} {y0:g} {z0:g})
    ({x1:g} {y1:g} {z0:g})
    ({x0:g} {y1:g} {z0:g})
    ({x0:g} {y0:g} {z1:g})
    ({x1:g} {y0:g} {z1:g})
    ({x1:g} {y1:g} {z1:g})
    ({x0:g} {y1:g} {z1:g})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges ();

boundary
(
    inlet
    {{
        type patch;
        faces ((0 4 7 3));
    }}
    outlet
    {{
        type patch;
        faces ((1 2 6 5));
    }}
    farfield
    {{
        type patch;
        faces
        (
            (0 1 5 4)
            (3 7 6 2)
            (0 3 2 1)
            (4 5 6 7)
        );
    }}
);

mergePatchPairs ();
"""


def _snappy_hex_mesh_dict(domain: dict[str, list[float]], mesh_quality: str) -> str:
    min_level, max_level = _refinement_levels(mesh_quality)
    location = domain["locationInMesh"]
    return f"""{foam_header("dictionary", "snappyHexMeshDict")}
castellatedMesh true;
snap            true;
addLayers       false;

geometry
{{
    obstacle.stl
    {{
        type triSurfaceMesh;
        name {SURFACE_PATCH};
    }}
}}

castellatedMeshControls
{{
    maxLocalCells 1000000;
    maxGlobalCells 2000000;
    minRefinementCells 0;
    maxLoadUnbalance 0.10;
    nCellsBetweenLevels 3;

    features
    (
        {{
            file "obstacle.eMesh";
            level {min_level};
        }}
    );

    refinementSurfaces
    {{
        {SURFACE_PATCH}
        {{
            level ({min_level} {max_level});
            patchInfo
            {{
                type wall;
            }}
        }}
    }}

    resolveFeatureAngle 30;
    refinementRegions {{}}
    locationInMesh ({location[0]:g} {location[1]:g} {location[2]:g});
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 30;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes true;
    layers {{}}
    expansionRatio 1.0;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 0;
    featureAngle 60;
    nRelaxIter 5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}

meshQualityControls
{{
    #include "meshQualityDict"
}}

mergeTolerance 1e-6;
"""


def _surface_features_dict() -> str:
    return f"""{foam_header("dictionary", "surfaceFeaturesDict")}
surfaces ("obstacle.stl");
includedAngle 150;

subsetFeatures
{{
    nonManifoldEdges no;
    openEdges yes;
}}

writeObj no;
"""


def _mesh_quality_dict() -> str:
    return """maxNonOrtho 70;
maxBoundarySkewness 20;
maxInternalSkewness 4;
maxConcave 80;
minVol 1e-13;
minTetQuality 1e-30;
minArea -1;
minTwist 0.02;
minDeterminant 0.001;
minFaceWeight 0.02;
minVolRatio 0.01;
minTriangleTwist -1;
nSmoothScale 4;
errorReduction 0.75;
"""


def _u_file(spec: SimulationSpec) -> str:
    inlet_velocity = _inlet_velocity(spec.velocity, spec.angle_of_attack)
    return f"""{foam_header("volVectorField", "U")}
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform {vector(inlet_velocity)};
boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {vector(inlet_velocity)};
    }}
    outlet
    {{
        type            zeroGradient;
    }}
    farfield
    {{
        type            slip;
    }}
    {SURFACE_PATCH}
    {{
        type            noSlip;
    }}
}}
"""


def _p_file() -> str:
    return f"""{foam_header("volScalarField", "p")}
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{{
    inlet
    {{
        type            zeroGradient;
    }}
    outlet
    {{
        type            fixedValue;
        value           uniform 0;
    }}
    farfield
    {{
        type            zeroGradient;
    }}
    {SURFACE_PATCH}
    {{
        type            zeroGradient;
    }}
}}
"""


def _scalar_field(
    name: str,
    class_name: str,
    internal_value: str,
    dimensions: str,
    wall_type: str,
) -> str:
    return f"""{foam_header(class_name, name)}
dimensions      {dimensions};
internalField   uniform {internal_value};
boundaryField
{{
    inlet
    {{
        type            fixedValue;
        value           uniform {internal_value};
    }}
    outlet
    {{
        type            zeroGradient;
    }}
    farfield
    {{
        type            zeroGradient;
    }}
    {SURFACE_PATCH}
    {{
        type            {wall_type};
        value           uniform {internal_value};
    }}
}}
"""


def _control_dict(spec: SimulationSpec) -> str:
    end_time = max(50, min(spec.max_runtime_minutes * 10, 1000))
    return f"""{foam_header("dictionary", "controlDict")}
application     simpleFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         {end_time};
deltaT          1;
writeControl    timeStep;
writeInterval   25;
purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{{
    #include "forceCoeffs"
}}
"""


def _force_coefficients_config(spec: SimulationSpec) -> dict:
    directions = force_coefficient_directions(spec.angle_of_attack)
    reference_length = spec.length_scale
    return {
        "enabled": True,
        "patches": [SURFACE_PATCH],
        "dragDir": list(directions["dragDir"]),
        "liftDir": list(directions["liftDir"]),
        "pitchAxis": list(directions["pitchAxis"]),
        "CofR": [0.0, 0.0, 0.0],
        "rhoInf": 1.0,
        "magUInf": spec.velocity,
        "lRef": reference_length,
        "Aref": reference_length * reference_length,
    }


def _force_coeffs_file(config: dict) -> str:
    return f"""{foam_header("dictionary", "forceCoeffs")}
forceCoeffs1
{{
    type            forceCoeffs;
    libs            ("libforces.so");
    writeControl    timeStep;
    timeInterval    1;
    log             yes;
    patches         ({config["patches"][0]});
    rho             rhoInf;
    rhoInf          {_foam_number(config["rhoInf"])};
    liftDir         {_foam_tuple(config["liftDir"])};
    dragDir         {_foam_tuple(config["dragDir"])};
    CofR            {_foam_tuple(config["CofR"])};
    pitchAxis       {_foam_tuple(config["pitchAxis"])};
    magUInf         {_foam_number(config["magUInf"])};
    lRef            {_foam_number(config["lRef"])};
    Aref            {_foam_number(config["Aref"])};
}}
"""


def _inlet_velocity(speed: float, angle_degrees: float) -> tuple[float, float, float]:
    import math

    angle = math.radians(angle_degrees)
    return (speed * math.cos(angle), speed * math.sin(angle), 0.0)
