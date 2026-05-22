import json
import math
from pathlib import Path

from app.openfoam.case_builder import build_openfoam_case
from app.schemas import SimulationSpec


def _spec() -> SimulationSpec:
    return SimulationSpec(
        upload_id="upload-1",
        units="m",
        length_scale=1,
        velocity=20,
        angle_of_attack=30,
    )


def test_case_builder_writes_expected_openfoam_files(tmp_path: Path) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    case_dir = tmp_path / "case"

    manifest = build_openfoam_case(spec=_spec(), mesh_path=mesh, case_dir=case_dir)

    expected = {
        "input.msh",
        "case-manifest.json",
        "0/U",
        "0/p",
        "0/k",
        "0/omega",
        "0/nut",
        "constant/transportProperties",
        "constant/turbulenceProperties",
        "system/controlDict",
        "system/fvSchemes",
        "system/fvSolution",
    }
    written = {path.relative_to(case_dir).as_posix() for path in case_dir.rglob("*") if path.is_file()}
    assert expected.issubset(written)
    assert "wallDist" in (case_dir / "system" / "fvSchemes").read_text()
    assert "dimensions      [0 2 -2 0 0 0 0];" in (case_dir / "0" / "k").read_text()
    assert "dimensions      [0 0 -1 0 0 0 0];" in (case_dir / "0" / "omega").read_text()
    assert "dimensions      [0 2 -1 0 0 0 0];" in (case_dir / "0" / "nut").read_text()
    assert "smoother        GaussSeidel;" in (case_dir / "system" / "fvSolution").read_text()
    assert manifest["solver"] == "simpleFoam"


def test_case_builder_computes_inlet_velocity_from_angle(tmp_path: Path) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    case_dir = tmp_path / "case"

    manifest = build_openfoam_case(spec=_spec(), mesh_path=mesh, case_dir=case_dir)

    ux, uy, uz = manifest["inlet_velocity"]
    assert math.isclose(ux, 17.320508, rel_tol=1e-6)
    assert math.isclose(uy, 10.0, rel_tol=1e-6)
    assert uz == 0
    assert "17.320508" in (case_dir / "0" / "U").read_text()


def test_case_builder_has_no_unresolved_template_tokens(tmp_path: Path) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    case_dir = tmp_path / "case"

    build_openfoam_case(spec=_spec(), mesh_path=mesh, case_dir=case_dir)

    for path in case_dir.rglob("*"):
        if path.is_file():
            text = path.read_text(errors="ignore")
            assert "{{" not in text
            assert "}}" not in text
    manifest = json.loads((case_dir / "case-manifest.json").read_text())
    assert manifest["assumptions"]["runner"] == "local_openfoam"


def test_case_builder_uses_2d_airfoil_boundaries_when_mesh_has_airfoil_patches(tmp_path: Path) -> None:
    mesh = tmp_path / "naca4412.msh"
    mesh.write_text(
        "\n".join(
            [
                "$MeshFormat",
                "2.2 0 8",
                "$EndMeshFormat",
                "$PhysicalNames",
                "6",
                '2 1 "inlet"',
                '2 2 "outlet"',
                '2 3 "farfield"',
                '2 4 "airfoil"',
                '2 5 "frontAndBack"',
                '3 6 "internal"',
                "$EndPhysicalNames",
            ]
        )
    )
    case_dir = tmp_path / "case"

    manifest = build_openfoam_case(
        spec=SimulationSpec(
            upload_id="upload-1",
            units="m",
            length_scale=1,
            velocity=25,
            angle_of_attack=2,
        ),
        mesh_path=mesh,
        case_dir=case_dir,
    )

    assert manifest["case_type"] == "airfoil_2d"
    assert manifest["reynolds_number"] == 1666666.666667
    assert manifest["chord_length_m"] == 1.0
    assert manifest["kinematic_viscosity_m2_s"] == 1.5e-05

    u_text = (case_dir / "0" / "U").read_text()
    p_text = (case_dir / "0" / "p").read_text()
    assert "airfoil" in u_text
    assert "type            noSlip;" in u_text
    assert "farfield" in u_text
    assert "type            slip;" in u_text
    assert "frontAndBack" in u_text
    assert "type            empty;" in u_text
    assert "frontAndBack" in p_text
    assert "type            empty;" in p_text
