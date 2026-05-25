from __future__ import annotations

import json
from pathlib import Path
from typing import Any


READY_STATUSES = {"ready", "repaired_ready"}


def write_geometry_readiness(
    *, run_dir: Path, command_results: list[dict[str, Any]]
) -> dict[str, Any]:
    readiness = build_geometry_readiness(run_dir=run_dir, command_results=command_results)
    (run_dir / "geometry-readiness.json").write_text(
        json.dumps(readiness, indent=2),
        encoding="utf-8",
    )
    return readiness


def build_geometry_readiness(
    *, run_dir: Path, command_results: list[dict[str, Any]]
) -> dict[str, Any]:
    diagnostics = _read_json(run_dir / "geometry-diagnostics.json")
    check_mesh_summary = _read_json(run_dir / "checkMesh-summary.json")
    snappy_manifest = _read_json(run_dir / "case" / "snappy-manifest.json")
    by_name = {str(result.get("name")): result for result in command_results}

    surface_check_passed = _command_passed(by_name.get("surface_check"))
    snappy_passed = _command_passed(by_name.get("snappy_hex_mesh"))
    check_mesh_passed = _check_mesh_passed(by_name.get("check_mesh"), check_mesh_summary)

    status = _status(
        diagnostics=diagnostics,
        surface_check_passed=surface_check_passed,
        snappy_passed=snappy_passed,
        check_mesh_passed=check_mesh_passed,
    )
    recommendations = _recommendations(
        status=status,
        diagnostics=diagnostics,
        command_results=by_name,
        check_mesh_summary=check_mesh_summary,
    )
    readiness = {
        "status": status,
        "passed": status in READY_STATUSES,
        "repair_mode": diagnostics.get("repair_mode"),
        "meshfix_attempted": bool(diagnostics.get("meshfix_attempted", False)),
        "meshfix_success": bool(diagnostics.get("meshfix_success", False)),
        "surface_check_passed": surface_check_passed,
        "snappy_hex_mesh_passed": snappy_passed,
        "check_mesh_passed": check_mesh_passed,
        "scale_hint": diagnostics.get("scale_hint"),
        "body_count": diagnostics.get("body_count_after_repair", diagnostics.get("body_count")),
        "watertight": diagnostics.get("watertight_after_repair", diagnostics.get("is_watertight")),
        "volume": diagnostics.get("volume_after_repair"),
        "snappy_profile": snappy_manifest.get("snappy_profile"),
        "recommendations": recommendations,
    }
    return readiness


def _status(
    *,
    diagnostics: dict[str, Any],
    surface_check_passed: bool | None,
    snappy_passed: bool | None,
    check_mesh_passed: bool | None,
) -> str:
    if diagnostics and diagnostics.get("passed") is False:
        return "failed_geometry"
    if surface_check_passed is False:
        return "failed_geometry"
    if snappy_passed is False:
        return "failed_meshing"
    if check_mesh_passed is False:
        return "failed_solver_mesh_quality"
    if _was_repaired(diagnostics):
        return "repaired_ready"
    return "ready"


def _was_repaired(diagnostics: dict[str, Any]) -> bool:
    if not diagnostics:
        return False
    return bool(
        diagnostics.get("is_watertight") is False
        or diagnostics.get("is_winding_consistent") is False
        or float(diagnostics.get("volume_before_repair") or 0) <= 0
        or int(diagnostics.get("degenerate_faces_removed") or 0) > 0
        or int(diagnostics.get("vertices_merged") or 0) > 0
        or diagnostics.get("meshfix_success") is True
    )


def _recommendations(
    *,
    status: str,
    diagnostics: dict[str, Any],
    command_results: dict[str, dict[str, Any]],
    check_mesh_summary: dict[str, Any],
) -> list[str]:
    recommendations: list[str] = []
    if status in READY_STATUSES:
        recommendations.append("Surface geometry is solver-ready.")
        if status == "repaired_ready":
            recommendations.append("Review geometry-diagnostics.json because repair or reorientation changed the submitted surface.")
        return recommendations

    recommendations.extend(str(item) for item in diagnostics.get("recommendations", []) if item)
    if diagnostics.get("watertight_after_repair") is False:
        recommendations.append("Export a closed/watertight STL or repair holes/non-manifold edges before rerunning.")
    if int(diagnostics.get("body_count_after_repair") or diagnostics.get("body_count") or 0) > 1:
        recommendations.append("Use one single closed solid body for this V1 external-aero STL/STEP path.")
    if diagnostics.get("scale_hint") not in {None, "ok"}:
        recommendations.append("Check geometry units/scale; the detected size is suspicious for the selected units.")
    if int(diagnostics.get("broken_face_count") or 0) > 0:
        recommendations.append("Inspect the STL for broken faces, self-intersections, or non-manifold topology.")
    if status == "failed_meshing":
        recommendations.append(_command_detail(command_results.get("snappy_hex_mesh")) or "snappyHexMesh failed; inspect snappyHexMesh.log.")
    if status == "failed_solver_mesh_quality":
        recommendations.append(_command_detail(command_results.get("check_mesh")) or "checkMesh failed; inspect checkMesh.log.")
        if check_mesh_summary.get("failed_checks"):
            recommendations.append(f"OpenFOAM reported {check_mesh_summary['failed_checks']} failed mesh checks.")
    if not recommendations:
        recommendations.append("Inspect geometry-diagnostics.json, surfaceCheck.log, snappyHexMesh.log, and checkMesh.log.")
    return _dedupe(recommendations)


def _command_passed(result: dict[str, Any] | None) -> bool | None:
    if result is None:
        return None
    return int(result.get("returncode", 1)) == 0


def _check_mesh_passed(result: dict[str, Any] | None, summary: dict[str, Any]) -> bool | None:
    if result is not None:
        return _command_passed(result)
    if "passed" in summary:
        return bool(summary["passed"])
    return None


def _command_detail(result: dict[str, Any] | None) -> str | None:
    if not result:
        return None
    detail = str(result.get("stderr_excerpt") or result.get("stdout_excerpt") or "").strip()
    return detail or None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
