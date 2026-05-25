import json
from pathlib import Path

from app.openfoam.snappy import build_snappy_stl_case, snappy_openfoam_commands
from app.schemas import SimulationSpec


def _spec() -> SimulationSpec:
    return SimulationSpec(
        upload_id="upload-1",
        units="m",
        length_scale=2,
        velocity=30,
        angle_of_attack=5,
        mesh_quality="balanced",
    )


def _closed_box_stl(path: Path) -> None:
    path.write_text(
        """solid tetra
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 0 0 1
      vertex 1 0 0
    endloop
  endfacet
  facet normal 1 1 1
    outer loop
      vertex 1 0 0
      vertex 0 0 1
      vertex 0 1 0
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 1 0
      vertex 0 0 1
    endloop
  endfacet
endsolid tetra
""",
        encoding="ascii",
    )


def test_snappy_builder_creates_external_3d_obstacle_case(tmp_path: Path) -> None:
    source = tmp_path / "body.stl"
    _closed_box_stl(source)

    manifest = build_snappy_stl_case(spec=_spec(), stl_path=source, case_dir=tmp_path / "case")

    case_dir = tmp_path / "case"
    copied_stl = case_dir / "constant" / "triSurface" / "obstacle.stl"
    assert copied_stl.exists()
    assert copied_stl.stat().st_size > 0
    assert (case_dir / "system" / "blockMeshDict").exists()
    assert (case_dir / "system" / "snappyHexMeshDict").exists()
    assert (case_dir / "system" / "surfaceFeaturesDict").exists()
    surface_features = (case_dir / "system" / "surfaceFeaturesDict").read_text()
    assert 'surfaces ("obstacle.stl");' in surface_features
    assert "constant/triSurface/constant/triSurface" not in surface_features
    assert (case_dir / "0" / "U").exists()
    assert manifest["case_type"] == "external_3d_stl_snappy"
    assert manifest["mesh_source"] == "snappyHexMesh"
    assert manifest["surface_patch"] == "obstacle"
    assert manifest["domain"]["x"] == [-10.0, 20.0]
    assert manifest["limitations"]
    assert json.loads((case_dir / "case-manifest.json").read_text())["case_type"] == "external_3d_stl_snappy"


def test_snappy_commands_include_surface_and_mesh_quality_gates() -> None:
    commands = snappy_openfoam_commands()

    assert [command["name"] for command in commands] == [
        "surface_check",
        "block_mesh",
        "surface_features",
        "snappy_hex_mesh",
        "check_mesh",
        "check_mesh_strict",
        "solve",
        "export_vtk",
    ]
    assert commands[0]["command"] == "surfaceCheck constant/triSurface/obstacle.stl"
    assert commands[2]["command"] == "surfaceFeatures"
    assert commands[3]["command"] == "snappyHexMesh -overwrite"
    assert commands[4]["command"] == "checkMesh"
    assert commands[4]["required"] is True
    assert commands[5]["command"] == "checkMesh -allGeometry -allTopology"
    assert commands[5]["required"] is False
    assert commands[-1]["required"] is False


def test_snappy_manifest_is_written_for_manual_ide_inspection(tmp_path: Path) -> None:
    source = tmp_path / "body.stl"
    _closed_box_stl(source)

    build_snappy_stl_case(spec=_spec(), stl_path=source, case_dir=tmp_path / "case")

    manifest = json.loads((tmp_path / "case" / "snappy-manifest.json").read_text())
    assert manifest["commands"][0]["name"] == "surface_check"
    assert manifest["flow_assumption"] == "steady incompressible external aerodynamics"
    assert "STL must be closed/watertight" in " ".join(manifest["limitations"])
