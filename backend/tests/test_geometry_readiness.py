import json
from pathlib import Path

from app.openfoam.geometry_readiness import build_geometry_readiness, write_geometry_readiness


def test_geometry_readiness_marks_clean_surface_ready(tmp_path: Path) -> None:
    run_dir = tmp_path
    _write_json(
        run_dir / "geometry-diagnostics.json",
        {
            "passed": True,
            "is_watertight": True,
            "is_winding_consistent": True,
            "volume_before_repair": 1.0,
            "volume_after_repair": 1.0,
            "scale_hint": "ok",
            "body_count": 1,
            "body_count_after_repair": 1,
            "degenerate_faces_removed": 0,
            "vertices_merged": 0,
            "meshfix_attempted": False,
            "meshfix_success": False,
            "repair_mode": "basic",
            "recommendations": ["Surface passed basic watertightness, normals, and scale checks."],
        },
    )
    _write_json(run_dir / "checkMesh-summary.json", {"passed": True, "cells": 45000})

    readiness = build_geometry_readiness(run_dir=run_dir, command_results=[])

    assert readiness["status"] == "ready"
    assert readiness["passed"] is True
    assert readiness["repair_mode"] == "basic"
    assert readiness["check_mesh_passed"] is True
    assert "Surface geometry is solver-ready." in readiness["recommendations"]


def test_geometry_readiness_marks_repaired_surface_ready(tmp_path: Path) -> None:
    run_dir = tmp_path
    _write_json(
        run_dir / "geometry-diagnostics.json",
        {
            "passed": True,
            "is_watertight": False,
            "is_winding_consistent": False,
            "volume_before_repair": 0.0,
            "volume_after_repair": 1.0,
            "scale_hint": "ok",
            "body_count": 1,
            "body_count_after_repair": 1,
            "degenerate_faces_removed": 1,
            "vertices_merged": 0,
            "meshfix_attempted": True,
            "meshfix_success": True,
            "repair_mode": "meshfix",
            "recommendations": ["Surface passed basic watertightness, normals, and scale checks."],
        },
    )
    _write_json(run_dir / "checkMesh-summary.json", {"passed": True, "cells": 45000})

    readiness = write_geometry_readiness(run_dir=run_dir, command_results=[])

    assert readiness["status"] == "repaired_ready"
    assert readiness["passed"] is True
    assert readiness["meshfix_attempted"] is True
    assert (run_dir / "geometry-readiness.json").exists()


def test_geometry_readiness_marks_failed_geometry_with_recommendations(tmp_path: Path) -> None:
    run_dir = tmp_path
    _write_json(
        run_dir / "geometry-diagnostics.json",
        {
            "passed": False,
            "is_watertight": False,
            "is_winding_consistent": True,
            "volume_after_repair": 0.0,
            "scale_hint": "very_large_check_units",
            "body_count": 2,
            "body_count_after_repair": 2,
            "broken_face_count": 5,
            "repair_mode": "basic",
            "meshfix_attempted": False,
            "meshfix_success": False,
            "recommendations": ["Export or repair a watertight STL; close holes, remove non-manifold edges, and retry."],
        },
    )

    readiness = build_geometry_readiness(run_dir=run_dir, command_results=[])

    assert readiness["status"] == "failed_geometry"
    assert readiness["passed"] is False
    assert any("watertight" in item for item in readiness["recommendations"])
    assert any("single closed solid body" in item for item in readiness["recommendations"])
    assert any("units/scale" in item for item in readiness["recommendations"])


def test_geometry_readiness_marks_meshing_and_checkmesh_failures(tmp_path: Path) -> None:
    run_dir = tmp_path
    _write_json(run_dir / "geometry-diagnostics.json", {"passed": True, "repair_mode": "basic"})
    command_results = [
        {"name": "surface_check", "returncode": 0, "required": True},
        {"name": "snappy_hex_mesh", "returncode": 1, "required": True, "stderr_excerpt": "bad castellated mesh"},
    ]

    readiness = build_geometry_readiness(run_dir=run_dir, command_results=command_results)

    assert readiness["status"] == "failed_meshing"
    assert readiness["passed"] is False

    command_results = [
        {"name": "surface_check", "returncode": 0, "required": True},
        {"name": "snappy_hex_mesh", "returncode": 0, "required": True},
        {"name": "check_mesh", "returncode": 1, "required": True, "stderr_excerpt": "Failed 2 mesh checks"},
    ]
    readiness = build_geometry_readiness(run_dir=run_dir, command_results=command_results)

    assert readiness["status"] == "failed_solver_mesh_quality"
    assert readiness["passed"] is False


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
