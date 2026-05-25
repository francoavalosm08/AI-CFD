from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import trimesh
from trimesh import repair


def prepare_surface_for_snappy(
    *,
    source_path: Path,
    target_path: Path,
    diagnostics_path: Path,
    repair_mode: str | None = None,
) -> dict[str, Any]:
    repair_mode = (repair_mode or os.environ.get("AI_CFD_SURFACE_REPAIR", "basic")).lower()
    mesh = _load_mesh(source_path)
    diagnostics = _diagnostics(mesh, source_path)
    diagnostics.update(
        {
            "repair_mode": repair_mode,
            "repair_stages": [],
            "meshfix_attempted": False,
            "meshfix_success": False,
            "meshfix_error": None,
        }
    )

    basic_repair = _apply_trimesh_repair(mesh)
    _add_stage(diagnostics, "trimesh_basic", mesh)

    if not _mesh_passed(mesh) and repair_mode in {"meshfix", "aggressive"}:
        diagnostics["meshfix_attempted"] = True
        repaired_mesh, meshfix_error = _repair_with_meshfix(source_path, diagnostics_path)
        diagnostics["meshfix_error"] = meshfix_error
        if repaired_mesh is not None:
            mesh = repaired_mesh
            meshfix_repair = _apply_trimesh_repair(mesh)
            basic_repair["fill_holes_changed"] = (
                basic_repair["fill_holes_changed"] or meshfix_repair["fill_holes_changed"]
            )
            basic_repair["degenerate_faces_removed"] += meshfix_repair["degenerate_faces_removed"]
            basic_repair["vertices_merged"] += meshfix_repair["vertices_merged"]
            diagnostics["meshfix_success"] = _mesh_passed(mesh)
            _add_stage(diagnostics, "meshfix", mesh)

    diagnostics.update(
        {
            "repair_attempted": True,
            "fill_holes_changed": basic_repair["fill_holes_changed"],
            "degenerate_faces_removed": basic_repair["degenerate_faces_removed"],
            "vertices_merged": basic_repair["vertices_merged"],
            "watertight_after_repair": bool(mesh.is_watertight),
            "volume_after_repair": _mesh_volume(mesh),
            "broken_face_count": _broken_face_count(mesh),
            "face_count_after_repair": int(len(mesh.faces)),
            "vertex_count_after_repair": int(len(mesh.vertices)),
            "body_count_after_repair": _body_count(mesh),
        }
    )
    diagnostics["passed"] = _surface_passed(mesh, diagnostics)
    diagnostics["recommendations"] = _recommendations(diagnostics)

    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")

    if diagnostics["passed"]:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(target_path, file_type="stl")

    return diagnostics


def _apply_trimesh_repair(mesh: trimesh.Trimesh) -> dict[str, Any]:
    faces_before = int(len(mesh.faces))
    if faces_before:
        mesh.update_faces(mesh.nondegenerate_faces())
    degenerate_faces_removed = faces_before - int(len(mesh.faces))
    vertices_before_merge = int(len(mesh.vertices))
    mesh.merge_vertices()
    repair.fix_winding(mesh)
    repair.fix_normals(mesh, multibody=True)
    fill_holes_changed = bool(repair.fill_holes(mesh))
    # Hole filling can create a closed but inward-oriented mesh; normalize again after topology changes.
    repair.fix_winding(mesh)
    repair.fix_normals(mesh, multibody=True)
    mesh.remove_unreferenced_vertices()
    return {
        "fill_holes_changed": fill_holes_changed,
        "degenerate_faces_removed": degenerate_faces_removed,
        "vertices_merged": vertices_before_merge - int(len(mesh.vertices)),
    }


def _repair_with_meshfix(
    source_path: Path, diagnostics_path: Path
) -> tuple[trimesh.Trimesh | None, str | None]:
    try:
        import pymeshfix
    except Exception as exc:
        return None, f"PyMeshFix is not installed or could not be imported: {exc}"

    try:
        with tempfile.TemporaryDirectory(prefix="meshfix-", dir=diagnostics_path.parent) as repair_dir:
            repaired_path = Path(repair_dir) / "repaired.stl"
            pymeshfix.clean_from_file(str(source_path), str(repaired_path))
            return _load_mesh(repaired_path), None
    except Exception as exc:
        return None, f"PyMeshFix repair failed: {exc}"


def _mesh_passed(mesh: trimesh.Trimesh) -> bool:
    return bool(mesh.is_watertight and len(mesh.faces) > 0 and _mesh_volume(mesh) > 0)


def _surface_passed(mesh: trimesh.Trimesh, diagnostics: dict[str, Any]) -> bool:
    return bool(
        _mesh_passed(mesh)
        and diagnostics.get("body_count_after_repair") == 1
        and diagnostics.get("scale_hint") == "ok"
    )


def _add_stage(diagnostics: dict[str, Any], name: str, mesh: trimesh.Trimesh) -> None:
    diagnostics["repair_stages"].append(
        {
            "name": name,
            "face_count": int(len(mesh.faces)),
            "vertex_count": int(len(mesh.vertices)),
            "body_count": _body_count(mesh),
            "watertight": bool(mesh.is_watertight),
            "winding_consistent": bool(mesh.is_winding_consistent),
            "volume": _mesh_volume(mesh),
            "passed": _mesh_passed(mesh),
        }
    )


def _load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load_mesh(path, file_type=path.suffix.lower().lstrip("."))
    if isinstance(loaded, trimesh.Scene):
        meshes = [geometry for geometry in loaded.geometry.values() if isinstance(geometry, trimesh.Trimesh)]
        if not meshes:
            return trimesh.Trimesh()
        return trimesh.util.concatenate(meshes)
    return loaded


def _diagnostics(mesh: trimesh.Trimesh, source_path: Path) -> dict[str, Any]:
    raw_extents = getattr(mesh, "extents", None)
    extents = [float(value) for value in raw_extents] if raw_extents is not None else []
    return {
        "source_path": str(source_path),
        "face_count": int(len(mesh.faces)),
        "vertex_count": int(len(mesh.vertices)),
        "body_count": _body_count(mesh),
        "is_watertight": bool(mesh.is_watertight),
        "is_winding_consistent": bool(mesh.is_winding_consistent),
        "euler_number": int(mesh.euler_number) if mesh.faces.size else 0,
        "volume_before_repair": _mesh_volume(mesh),
        "volume_after_repair": _mesh_volume(mesh),
        "extents": extents,
        "scale_hint": _scale_hint(extents),
    }


def _safe_float(value: float) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _mesh_volume(mesh: trimesh.Trimesh) -> float:
    if not mesh.is_watertight:
        return 0.0
    return _safe_float(mesh.volume)


def _body_count(mesh: trimesh.Trimesh) -> int:
    if len(mesh.faces) == 0:
        return 0

    parent: dict[int, int] = {}

    def find(value: int) -> int:
        parent.setdefault(value, value)
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    used_vertices: set[int] = set()
    for face in mesh.faces:
        vertices = [int(index) for index in face]
        used_vertices.update(vertices)
        union(vertices[0], vertices[1])
        union(vertices[1], vertices[2])
        union(vertices[2], vertices[0])

    return len({find(vertex) for vertex in used_vertices})


def _broken_face_count(mesh: trimesh.Trimesh) -> int:
    count = int(len(repair.broken_faces(mesh)))
    if count == 0 and not mesh.is_watertight:
        return int(len(mesh.faces))
    return count


def _scale_hint(extents: list[float]) -> str:
    if not extents:
        return "unknown"
    largest = max(extents)
    if largest <= 0:
        return "invalid"
    if largest < 0.001:
        return "very_small_check_units"
    if largest > 1000:
        return "very_large_check_units"
    return "ok"


def _recommendations(diagnostics: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    if diagnostics["face_count"] == 0:
        recommendations.append("The surface has no triangles; export a triangulated watertight STL.")
    if not diagnostics["watertight_after_repair"]:
        recommendations.append(
            "Export or repair a watertight STL; close holes, remove non-manifold edges, and retry."
        )
    if diagnostics["body_count"] > 1:
        recommendations.append(
            "The file has multiple disconnected bodies; use one closed solid body for the V1 external-aero path."
        )
    if diagnostics["volume_after_repair"] <= 0:
        recommendations.append("The surface has no positive enclosed volume; check normals, scale, and closedness.")
    if diagnostics["scale_hint"] != "ok":
        recommendations.append("Check geometry units/scale before running CFD.")
    if not recommendations:
        recommendations.append("Surface passed basic watertightness, normals, and scale checks.")
    return recommendations
