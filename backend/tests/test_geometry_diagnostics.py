from pathlib import Path

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
    assert target.exists()
    assert diagnostics_path.exists()


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
