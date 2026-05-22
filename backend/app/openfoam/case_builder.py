from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from app.openfoam.templates import foam_header, vector
from app.schemas import SimulationSpec


def build_openfoam_case(*, spec: SimulationSpec, mesh_path: Path, case_dir: Path) -> dict:
    case_dir.mkdir(parents=True, exist_ok=True)
    for child in ("0", "constant", "system"):
        (case_dir / child).mkdir(exist_ok=True)
    shutil.copy2(mesh_path, case_dir / "input.msh")

    inlet_velocity = _inlet_velocity(spec.velocity, spec.angle_of_attack)
    files = {
        "0/U": _u_file(inlet_velocity),
        "0/p": _scalar_field("p", "volScalarField", "0"),
        "0/k": _scalar_field("k", "volScalarField", "0.01"),
        "0/omega": _scalar_field("omega", "volScalarField", "1"),
        "0/nut": _scalar_field("nut", "volScalarField", "0"),
        "constant/transportProperties": _transport_properties(),
        "constant/turbulenceProperties": _turbulence_properties(),
        "system/controlDict": _control_dict(spec),
        "system/fvSchemes": _fv_schemes(),
        "system/fvSolution": _fv_solution(),
    }
    for relative, content in files.items():
        (case_dir / relative).write_text(content, encoding="utf-8")

    manifest = {
        "runner": "local_openfoam",
        "solver": "simpleFoam",
        "mesh": "input.msh",
        "units": spec.units,
        "length_scale": spec.length_scale,
        "velocity": spec.velocity,
        "angle_of_attack": spec.angle_of_attack,
        "inlet_velocity": [round(value, 6) for value in inlet_velocity],
        "files": sorted(["input.msh", *files.keys()]),
        "assumptions": {
            "runner": "local_openfoam",
            "flow": "steady incompressible external aerodynamics",
            "solver": "simpleFoam",
            "boundary_names": "generic inlet/outlet/wall placeholders; inspect imported mesh patches before real use",
        },
    }
    (case_dir / "case-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def _inlet_velocity(speed: float, angle_degrees: float) -> tuple[float, float, float]:
    angle = math.radians(angle_degrees)
    return (speed * math.cos(angle), speed * math.sin(angle), 0)


def _u_file(inlet_velocity: tuple[float, float, float]) -> str:
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
    wall
    {{
        type            noSlip;
    }}
    defaultFaces
    {{
        type            zeroGradient;
    }}
}}
"""


def _scalar_field(name: str, class_name: str, internal_value: str) -> str:
    return f"""{foam_header(class_name, name)}
dimensions      [0 0 0 0 0 0 0];
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
    wall
    {{
        type            zeroGradient;
    }}
    defaultFaces
    {{
        type            zeroGradient;
    }}
}}
"""


def _transport_properties() -> str:
    return f"""{foam_header("dictionary", "transportProperties")}
transportModel  Newtonian;
nu              [0 2 -1 0 0 0 0] 1.5e-05;
"""


def _turbulence_properties() -> str:
    return f"""{foam_header("dictionary", "turbulenceProperties")}
simulationType RAS;
RAS
{{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
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
"""


def _fv_schemes() -> str:
    return f"""{foam_header("dictionary", "fvSchemes")}
ddtSchemes {{ default steadyState; }}
gradSchemes {{ default Gauss linear; }}
divSchemes
{{
    default none;
    div(phi,U) bounded Gauss upwind;
    div(phi,k) bounded Gauss upwind;
    div(phi,omega) bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}
laplacianSchemes {{ default Gauss linear corrected; }}
interpolationSchemes {{ default linear; }}
snGradSchemes {{ default corrected; }}
"""


def _fv_solution() -> str:
    return f"""{foam_header("dictionary", "fvSolution")}
solvers
{{
    p {{ solver GAMG; tolerance 1e-7; relTol 0.01; }}
    U {{ solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }}
    "(k|omega)" {{ solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }}
}}
SIMPLE
{{
    nNonOrthogonalCorrectors 0;
    consistent yes;
}}
relaxationFactors
{{
    fields {{ p 0.3; }}
    equations {{ U 0.7; k 0.7; omega 0.7; }}
}}
"""
