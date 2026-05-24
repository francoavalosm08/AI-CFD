from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from app.openfoam.mesh_validation import read_msh_physical_names
from app.openfoam.templates import foam_header, vector
from app.schemas import SimulationSpec


EXTERNAL_2D_CASE_TYPES = {"airfoil_2d", "external_2d_obstacle"}


def build_openfoam_case(*, spec: SimulationSpec, mesh_path: Path, case_dir: Path) -> dict:
    case_dir.mkdir(parents=True, exist_ok=True)
    for child in ("0", "constant", "system"):
        (case_dir / child).mkdir(exist_ok=True)
    shutil.copy2(mesh_path, case_dir / "input.msh")

    physical_names = read_msh_physical_names(mesh_path)
    case_type = _case_type_from_physical_names(physical_names)
    inlet_velocity = _inlet_velocity(spec.velocity, spec.angle_of_attack)
    files = {
        "0/U": _u_file(inlet_velocity, case_type),
        "0/p": _scalar_field("p", "volScalarField", "0", "[0 2 -2 0 0 0 0]", case_type),
        "0/k": _scalar_field("k", "volScalarField", "0.01", "[0 2 -2 0 0 0 0]", case_type),
        "0/omega": _scalar_field("omega", "volScalarField", "1", "[0 0 -1 0 0 0 0]", case_type),
        "0/nut": _scalar_field("nut", "volScalarField", "0", "[0 2 -1 0 0 0 0]", case_type),
        "constant/transportProperties": _transport_properties(),
        "constant/turbulenceProperties": _turbulence_properties(),
        "system/controlDict": _control_dict(spec, case_type),
        "system/fvSchemes": _fv_schemes(),
        "system/fvSolution": _fv_solution(),
    }
    force_coefficients = _force_coefficients_config(spec, case_type)
    if force_coefficients["enabled"]:
        files["system/forceCoeffs"] = _force_coeffs_file(force_coefficients)
    for relative, content in files.items():
        (case_dir / relative).write_text(content, encoding="utf-8")

    manifest = {
        "runner": "local_openfoam",
        "case_type": case_type,
        "solver": "simpleFoam",
        "mesh": "input.msh",
        "units": spec.units,
        "length_scale": spec.length_scale,
        "velocity": spec.velocity,
        "angle_of_attack": spec.angle_of_attack,
        "chord_length_m": 1.0 if case_type == "airfoil_2d" else None,
        "kinematic_viscosity_m2_s": 1.5e-05,
        "reynolds_number": (
            round(spec.velocity * (1.0 if case_type == "airfoil_2d" else spec.length_scale) / 1.5e-05, 6)
            if case_type in EXTERNAL_2D_CASE_TYPES
            else None
        ),
        "inlet_velocity": [round(value, 6) for value in inlet_velocity],
        "force_coefficients": force_coefficients,
        "files": sorted(["input.msh", *files.keys()]),
        "assumptions": {
            "runner": "local_openfoam",
            "flow": "steady incompressible external aerodynamics",
            "solver": "simpleFoam",
            "boundary_names": (
                "2D external aero patches: inlet, outlet, farfield, airfoil/obstacle, frontAndBack"
                if case_type in EXTERNAL_2D_CASE_TYPES
                else "generic inlet/outlet/wall placeholders; inspect imported mesh patches before real use"
            ),
        },
    }
    (case_dir / "case-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def _case_type_from_physical_names(physical_names: set[str]) -> str:
    if {"airfoil", "farfield", "frontAndBack"}.issubset(physical_names):
        return "airfoil_2d"
    if {"obstacle", "farfield", "frontAndBack"}.issubset(physical_names):
        return "external_2d_obstacle"
    return "generic_external"


def _inlet_velocity(speed: float, angle_degrees: float) -> tuple[float, float, float]:
    angle = math.radians(angle_degrees)
    return (speed * math.cos(angle), speed * math.sin(angle), 0)


def force_coefficient_directions(angle_degrees: float) -> dict[str, tuple[float, float, float]]:
    angle = math.radians(angle_degrees)
    return {
        "dragDir": (_rounded(math.cos(angle)), _rounded(math.sin(angle)), 0.0),
        "liftDir": (_rounded(-math.sin(angle)), _rounded(math.cos(angle)), 0.0),
        "pitchAxis": (0.0, 0.0, 1.0),
    }


def _rounded(value: float) -> float:
    rounded = round(value, 6)
    return 0.0 if abs(rounded) < 0.0000005 else rounded


def _u_file(inlet_velocity: tuple[float, float, float], case_type: str) -> str:
    if case_type in EXTERNAL_2D_CASE_TYPES:
        wall_patch = _wall_patch(case_type)
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
    {wall_patch}
    {{
        type            noSlip;
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
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


def _scalar_field(name: str, class_name: str, internal_value: str, dimensions: str, case_type: str) -> str:
    if case_type in EXTERNAL_2D_CASE_TYPES:
        wall_patch = _wall_patch(case_type)
        wall_type = "zeroGradient"
        if name == "nut":
            wall_type = "nutkWallFunction"
        elif name == "omega":
            wall_type = "omegaWallFunction"
        elif name == "k":
            wall_type = "kqRWallFunction"
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
    {wall_patch}
    {{
        type            {wall_type};
        value           uniform {internal_value};
    }}
    frontAndBack
    {{
        type            empty;
    }}
}}
"""
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


def _control_dict(spec: SimulationSpec, case_type: str) -> str:
    end_time = max(50, min(spec.max_runtime_minutes * 10, 1000))
    functions = (
        """
functions
{
    #include "forceCoeffs"
}
"""
        if case_type in EXTERNAL_2D_CASE_TYPES
        else ""
    )
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
{functions}"""


def _force_coefficients_config(spec: SimulationSpec, case_type: str) -> dict:
    if case_type not in EXTERNAL_2D_CASE_TYPES:
        return {"enabled": False}
    directions = force_coefficient_directions(spec.angle_of_attack)
    patch = _wall_patch(case_type)
    reference_length = 1.0 if case_type == "airfoil_2d" else spec.length_scale
    return {
        "enabled": True,
        "patches": [patch],
        "dragDir": list(directions["dragDir"]),
        "liftDir": list(directions["liftDir"]),
        "pitchAxis": list(directions["pitchAxis"]),
        "CofR": [0.25, 0.0, 0.0],
        "rhoInf": 1.0,
        "magUInf": spec.velocity,
        "lRef": reference_length,
        "Aref": reference_length * 0.01,
        "span_m": 0.01,
    }


def _wall_patch(case_type: str) -> str:
    return "airfoil" if case_type == "airfoil_2d" else "obstacle"


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


def _foam_tuple(values: list[float] | tuple[float, float, float]) -> str:
    return "(" + " ".join(_foam_number(float(value)) for value in values) + ")"


def _foam_number(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


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
wallDist {{ method meshWave; }}
"""


def _fv_solution() -> str:
    return f"""{foam_header("dictionary", "fvSolution")}
solvers
{{
    p
    {{
        solver          GAMG;
        tolerance       1e-7;
        relTol          0.01;
        smoother        GaussSeidel;
    }}
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
