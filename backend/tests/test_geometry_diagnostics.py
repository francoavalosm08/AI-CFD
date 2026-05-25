from pathlib import Path

import pytest
import trimesh

from app.geometry_diagnostics import prepare_surface_for_snappy


def _closed_tetra_stl(path: Path) -> None:
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


def _open_triangle_stl(path: Path) -> None:
    path.write_text(
        """solid open
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid open
""",
        encoding="ascii",
    )


def _cube_with_missing_top_stl(path: Path) -> None:
    path.write_text(
        """solid open_cube
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 1 1 0
    endloop
  endfacet
  facet normal 0 0 -1
    outer loop
      vertex 0 0 0
      vertex 1 1 0
      vertex 0 1 0
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 0 0 1
      vertex 1 0 1
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 1 0 1
      vertex 1 0 0
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 1 0 0
      vertex 1 0 1
      vertex 1 1 1
    endloop
  endfacet
  facet normal 1 0 0
    outer loop
      vertex 1 0 0
      vertex 1 1 1
      vertex 1 1 0
    endloop
  endfacet
  facet normal 0 1 0
    outer loop
      vertex 1 1 0
      vertex 1 1 1
      vertex 0 1 1
    endloop
  endfacet
  facet normal 0 1 0
    outer loop
      vertex 1 1 0
      vertex 0 1 1
      vertex 0 1 0
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 1 0
      vertex 0 1 1
      vertex 0 0 1
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 1 0
      vertex 0 0 1
      vertex 0 0 0
    endloop
  endfacet
endsolid open_cube
""",
        encoding="ascii",
    )


def _degenerate_tetra_stl(path: Path) -> None:
    vertices = [
        (0, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
        (0, 0, 0),
    ]
    faces = [
        (0, 1, 2),
        (0, 3, 1),
        (1, 3, 2),
        (0, 2, 3),
        (0, 0, 0),
    ]
    trimesh.Trimesh(vertices=vertices, faces=faces, process=False).export(path)


def test_prepare_surface_accepts_watertight_stl_and_writes_diagnostics(tmp_path: Path) -> None:
    source = tmp_path / "closed.stl"
    target = tmp_path / "case" / "constant" / "triSurface" / "obstacle.stl"
    diagnostics_path = tmp_path / "geometry-diagnostics.json"
    _closed_tetra_stl(source)

    result = prepare_surface_for_snappy(
        source_path=source,
        target_path=target,
        diagnostics_path=diagnostics_path,
    )

    assert result["passed"] is True
    assert result["watertight_after_repair"] is True
    assert result["face_count"] == 4
    assert result["repair_mode"] == "basic"
    assert result["repair_stages"][0]["name"] == "trimesh_basic"
    assert target.exists()
    assert diagnostics_path.exists()


def test_prepare_surface_repairs_small_hole_and_reorients_normals(tmp_path: Path) -> None:
    source = tmp_path / "open-cube.stl"
    target = tmp_path / "case" / "constant" / "triSurface" / "obstacle.stl"
    diagnostics_path = tmp_path / "geometry-diagnostics.json"
    _cube_with_missing_top_stl(source)

    result = prepare_surface_for_snappy(
        source_path=source,
        target_path=target,
        diagnostics_path=diagnostics_path,
    )

    assert result["passed"] is True
    assert result["fill_holes_changed"] is True
    assert result["watertight_after_repair"] is True
    assert result["volume_after_repair"] > 0
    assert target.exists()


def test_prepare_surface_removes_degenerate_faces_before_snappy(tmp_path: Path) -> None:
    source = tmp_path / "degenerate-tetra.stl"
    target = tmp_path / "case" / "constant" / "triSurface" / "obstacle.stl"
    diagnostics_path = tmp_path / "geometry-diagnostics.json"
    _degenerate_tetra_stl(source)

    result = prepare_surface_for_snappy(
        source_path=source,
        target_path=target,
        diagnostics_path=diagnostics_path,
    )

    assert result["passed"] is True
    assert result["degenerate_faces_removed"] == 1
    assert result["face_count_after_repair"] == 4
    assert target.exists()


def test_prepare_surface_attempts_meshfix_when_explicitly_enabled(tmp_path: Path) -> None:
    pytest.importorskip("pymeshfix")
    source = tmp_path / "open.stl"
    target = tmp_path / "case" / "constant" / "triSurface" / "obstacle.stl"
    diagnostics_path = tmp_path / "geometry-diagnostics.json"
    _open_triangle_stl(source)

    result = prepare_surface_for_snappy(
        source_path=source,
        target_path=target,
        diagnostics_path=diagnostics_path,
        repair_mode="meshfix",
    )

    assert result["passed"] is False
    assert result["repair_mode"] == "meshfix"
    assert result["meshfix_attempted"] is True
    assert result["meshfix_success"] is False
    assert result["repair_stages"][-1]["name"] == "meshfix"
    assert not target.exists()


def test_prepare_surface_fails_open_stl_before_snappy(tmp_path: Path) -> None:
    source = tmp_path / "open.stl"
    target = tmp_path / "case" / "constant" / "triSurface" / "obstacle.stl"
    diagnostics_path = tmp_path / "geometry-diagnostics.json"
    _open_triangle_stl(source)

    result = prepare_surface_for_snappy(
        source_path=source,
        target_path=target,
        diagnostics_path=diagnostics_path,
    )

    assert result["passed"] is False
    assert result["watertight_after_repair"] is False
    assert result["broken_face_count"] >= 1
    assert "watertight STL" in " ".join(result["recommendations"])
    assert diagnostics_path.exists()
