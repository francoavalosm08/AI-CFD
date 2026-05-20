from __future__ import annotations

from app.schemas import SimulationSpec


FLUID_PRESETS = {
    "air_15c": "Air at 15 C, density 1.225 kg/m^3, dynamic viscosity 1.81e-5 Pa*s",
    "air_25c": "Air at 25 C, density 1.184 kg/m^3, dynamic viscosity 1.85e-5 Pa*s",
}


def build_foam_agent_prompt(
    spec: SimulationSpec, *, agent_visible_mesh_path: str | None = None
) -> str:
    outputs = ", ".join(spec.requested_outputs)
    fluid = FLUID_PRESETS.get(spec.fluid_preset, spec.fluid_preset)
    mach_line = f"Mach number: {spec.mach}\n" if spec.mach is not None else ""
    mesh_line = (
        f"Uploaded mesh path visible to Foam-Agent: {agent_visible_mesh_path}\n"
        if agent_visible_mesh_path
        else "No uploaded mesh path is available; generate a suitable external-aerodynamics mesh.\n"
    )

    return (
        "Run an external aerodynamics CFD simulation using Foundation OpenFOAM v10 conventions.\n"
        "Use a steady RANS setup appropriate for an external airflow case unless the solver planning "
        "requires a more stable equivalent.\n"
        f"{mesh_line}"
        f"Geometry units: {spec.units}\n"
        f"Length scale to meters: {spec.length_scale}\n"
        f"Velocity: {spec.velocity} m/s\n"
        f"{mach_line}"
        f"Angle of attack: {spec.angle_of_attack} degrees\n"
        f"Fluid preset: {spec.fluid_preset} ({fluid})\n"
        f"Turbulence model preset: {spec.turbulence_preset}\n"
        f"Mesh quality target: {spec.mesh_quality}\n"
        f"Requested outputs: {outputs}\n"
        f"Maximum runtime: {spec.max_runtime_minutes} minutes\n"
        "Generate residual history, pressure and velocity visualizations, and force coefficients if "
        "the case setup supports them. Keep the output case directory self-contained."
    )
