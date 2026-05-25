from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import trimesh
from trimesh import repair


def prepare_surface_for_snappy(
    *,
    source_path: Path,
    target_path: Path,
    diagnostics_path: Path,
) -> dict[str, Any]:
    mesh = _load_mesh(source_path)
    diagnostics = _diagnostics(mesh, source_path)

    repair.fix_winding(mesh)
    repair.fix_normals(mesh, multibody=True)
    fill_holes_changed = bool(repair.fill_holes(mesh))
    mesh.remove_unreferenced_vertices()

    diagnostics.update(
        {
            "repair_attempted": True,
            "fill_holes_changed": fill_holes_changed,
            "watertight_after_repair": bool(mesh.is_watertight),
            "volume_after_repair": _mesh_volume(mesh),
            "broken_face_count": _broken_face_count(mesh),
        }
    )
    diagnostics["passed"] = bool(
        diagnostics["watertight_after_repair"]
        and diagnostics["face_count"] > 0
        and diagnostics["volume_after_repair"] > 0
    )
    diagnostics["recommendations"] = _recommendations(diagnostics)

    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")

    if diagnostics["passed"]:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(target_path, file_type="stl")

    return diagnostics


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
