from pathlib import Path

import pytest

from app.mesh import (
    MeshConversionError,
    conversion_failure_message,
    conversion_unavailable_message,
    validate_converted_mesh,
)


def test_missing_gmsh_message_points_to_production_msh_path() -> None:
    message = conversion_unavailable_message("wing.stl", "gmsh")

    assert "Could not convert wing.stl to a Gmsh .msh file" in message
    assert "STEP/STL conversion is best-effort" in message
    assert "pre-meshed Gmsh .msh" in message
    assert "airfoil, inlet, outlet, farfield, frontAndBack, and internal" in message


def test_conversion_failure_message_explains_missing_volume_mesh() -> None:
    message = conversion_failure_message("surface.stl", "No elements in volume 1")

    assert "missing volume mesh" in message
    assert "cleaner closed STL/STEP" in message
    assert "pre-meshed Gmsh .msh" in message


def test_converted_mesh_without_physical_names_fails_with_actionable_message(tmp_path: Path) -> None:
    mesh = tmp_path / "input.msh"
    mesh.write_text(
        "\n".join(
            [
                "$MeshFormat",
                "2.2 0 8",
                "$EndMeshFormat",
                "$Elements",
                "0",
                "$EndElements",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(MeshConversionError) as exc_info:
        validate_converted_mesh(mesh, "body.step")

    message = str(exc_info.value)
    assert "Converted body.step to .msh, but the result has no Gmsh PhysicalNames" in message
    assert "airfoil, inlet, outlet, farfield, frontAndBack, and internal" in message
    assert "pre-meshed Gmsh .msh" in message
