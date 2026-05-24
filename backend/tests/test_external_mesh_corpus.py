from pathlib import Path

from app.openfoam.mesh_corpus import classify_msh_file


def test_classify_gmsh_file_without_physical_names_as_format_only(tmp_path: Path) -> None:
    mesh = tmp_path / "cylinder_2d.msh"
    mesh.write_text(
        "$MeshFormat\n"
        "2.2 0 8\n"
        "$EndMeshFormat\n"
        "$Nodes\n"
        "2\n"
        "1 0 0 0\n"
        "2 1 0 0\n"
        "$EndNodes\n"
        "$Elements\n"
        "1\n"
        "1 1 0 1 2\n"
        "$EndElements\n",
        encoding="utf-8",
    )

    classification = classify_msh_file(mesh)

    assert classification["format"] == "gmsh_msh_2.2_ascii"
    assert classification["nodes"] == 2
    assert classification["elements"] == 1
    assert classification["openfoam_v1_ready"] is False
    assert classification["support_status"] == "format_only_not_solver_ready"
    assert "PhysicalNames" in classification["warnings"][0]


def test_classify_fluent_msh_as_unsupported_for_gmshtofoam_path(tmp_path: Path) -> None:
    mesh = tmp_path / "naca0012.msh"
    mesh.write_text(
        '(0 "FOAM to Fluent Mesh File")\n'
        '(0 "Dimension:")\n'
        "(2 3)\n",
        encoding="utf-8",
    )

    classification = classify_msh_file(mesh)

    assert classification["format"] == "fluent_msh"
    assert classification["openfoam_v1_ready"] is False
    assert classification["support_status"] == "unsupported_format"
    assert "Fluent" in classification["warnings"][0]


def test_classify_airfoil_contract_mesh_as_solver_ready(tmp_path: Path) -> None:
    mesh = tmp_path / "naca0012-gmsh.msh"
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
                "$Nodes",
                "0",
                "$EndNodes",
                "$Elements",
                "0",
                "$EndElements",
            ]
        ),
        encoding="utf-8",
    )

    classification = classify_msh_file(mesh)

    assert classification["format"] == "gmsh_msh_2.2_ascii"
    assert classification["openfoam_v1_ready"] is True
    assert classification["support_status"] == "ready_airfoil_2d"
    assert classification["case_type"] == "airfoil_2d"


def test_classify_external_obstacle_contract_mesh_as_solver_ready(tmp_path: Path) -> None:
    mesh = tmp_path / "cylinder.msh"
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
                '2 4 "obstacle"',
                '2 5 "frontAndBack"',
                '3 6 "internal"',
                "$EndPhysicalNames",
                "$Nodes",
                "0",
                "$EndNodes",
                "$Elements",
                "0",
                "$EndElements",
            ]
        ),
        encoding="utf-8",
    )

    classification = classify_msh_file(mesh)

    assert classification["openfoam_v1_ready"] is True
    assert classification["support_status"] == "ready_external_2d_obstacle"
    assert classification["case_type"] == "external_2d_obstacle"
