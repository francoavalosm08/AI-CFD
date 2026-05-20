from app.prompt import build_foam_agent_prompt
from app.schemas import SimulationSpec


def test_simulation_spec_applies_external_aero_defaults():
    spec = SimulationSpec(
        upload_id="upload-1",
        units="m",
        length_scale=1.0,
        velocity=25.0,
        angle_of_attack=4.0,
    )

    assert spec.fluid_preset == "air_15c"
    assert spec.turbulence_preset == "steady_rans_sst"
    assert spec.mesh_quality == "balanced"
    assert spec.requested_outputs == ["residuals", "pressure", "velocity", "forces"]
    assert spec.max_runtime_minutes == 60


def test_build_foam_agent_prompt_is_deterministic_and_complete():
    spec = SimulationSpec(
        upload_id="upload-1",
        units="mm",
        length_scale=0.001,
        velocity=42.5,
        mach=0.12,
        angle_of_attack=7.5,
        fluid_preset="air_15c",
        turbulence_preset="steady_rans_sst",
        mesh_quality="fine",
        requested_outputs=["residuals", "pressure", "velocity", "forces"],
        max_runtime_minutes=30,
    )

    prompt = build_foam_agent_prompt(spec, agent_visible_mesh_path="/workspace/data/uploads/wing.msh")

    assert prompt == build_foam_agent_prompt(spec, agent_visible_mesh_path="/workspace/data/uploads/wing.msh")
    assert "external aerodynamics" in prompt
    assert "Velocity: 42.5 m/s" in prompt
    assert "Mach number: 0.12" in prompt
    assert "Angle of attack: 7.5 degrees" in prompt
    assert "Geometry units: mm" in prompt
    assert "Length scale to meters: 0.001" in prompt
    assert "Turbulence model preset: steady_rans_sst" in prompt
    assert "Mesh quality target: fine" in prompt
    assert "Maximum runtime: 30 minutes" in prompt
    assert "/workspace/data/uploads/wing.msh" in prompt
