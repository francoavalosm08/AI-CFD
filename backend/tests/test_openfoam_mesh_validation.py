from pathlib import Path

from app.openfoam.mesh_validation import validate_msh_physical_names


def _mesh_with_names(path: Path, names: list[str]) -> None:
    lines = [
        "$MeshFormat",
        "2.2 0 8",
        "$EndMeshFormat",
        "$PhysicalNames",
        str(len(names)),
    ]
    for index, name in enumerate(names, start=1):
        dimension = 3 if name == "internal" else 2
        lines.append(f'{dimension} {index} "{name}"')
    lines.extend(["$EndPhysicalNames"])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_airfoil_2d_mesh_validation_passes_when_required_physical_names_exist(tmp_path: Path) -> None:
    mesh = tmp_path / "naca4412.msh"
    _mesh_with_names(mesh, ["inlet", "outlet", "farfield", "airfoil", "frontAndBack", "internal"])

    validation = validate_msh_physical_names(mesh)

    assert validation == {
        "case_type": "airfoil_2d",
        "confidence": "high",
        "passed": True,
        "physical_names": ["airfoil", "farfield", "frontAndBack", "inlet", "internal", "outlet"],
        "required_physical_names": ["airfoil", "farfield", "frontAndBack", "inlet", "internal", "outlet"],
        "missing_required_physical_names": [],
        "warnings": [],
    }


def test_airfoil_2d_mesh_validation_fails_when_expected_patch_is_missing(tmp_path: Path) -> None:
    mesh = tmp_path / "bad-airfoil.msh"
    _mesh_with_names(mesh, ["inlet", "outlet", "farfield", "airfoil", "internal"])

    validation = validate_msh_physical_names(mesh)

    assert validation["case_type"] == "airfoil_2d"
    assert validation["passed"] is False
    assert validation["missing_required_physical_names"] == ["frontAndBack"]
    assert "Missing required airfoil_2d physical names: frontAndBack" in validation["warnings"]


def test_generic_mesh_validation_passes_with_lower_confidence(tmp_path: Path) -> None:
    mesh = tmp_path / "generic.msh"
    _mesh_with_names(mesh, ["inlet", "outlet", "wall"])

    validation = validate_msh_physical_names(mesh)

    assert validation["case_type"] == "generic_external"
    assert validation["confidence"] == "low"
    assert validation["passed"] is True
    assert validation["required_physical_names"] == []
    assert "Mesh does not match a known V1 patch template" in validation["warnings"][0]
