from __future__ import annotations

from pathlib import Path
from typing import Any

from app.artifacts import ARTIFACT_EXTENSIONS
from app.geometry_diagnostics import prepare_surface_for_snappy
from app.mesh import MeshConversionError, convert_cad_to_stl_surface
from app.openfoam.geometry_readiness import write_geometry_readiness
from app.schemas import UploadRecord


async def run_geometry_preflight(
    *, upload: UploadRecord, data_root: Path, gmsh_command: str = "gmsh"
) -> dict[str, Any]:
    preflight_dir = data_root / "preflights" / upload.id
    preflight_dir.mkdir(parents=True, exist_ok=True)
    source = Path(upload.stored_path)

    if upload.kind == "gmsh_mesh":
        return {
            "upload_id": upload.id,
            "status": "not_applicable",
            "passed": True,
            "recommendations": ["Premeshed .msh files are validated when the run starts."],
            "artifacts": _artifact_refs(preflight_dir),
        }
    if upload.kind not in {"surface_mesh", "cad"}:
        return {
            "upload_id": upload.id,
            "status": "not_applicable",
            "passed": False,
            "recommendations": ["Geometry preflight is only available for STL, STEP, and STP uploads."],
            "artifacts": _artifact_refs(preflight_dir),
        }

    try:
        stl_path = source
        if upload.kind == "cad":
            stl_path = await convert_cad_to_stl_surface(
                source,
                preflight_dir / "input.stl",
                gmsh_command=gmsh_command,
                log_path=preflight_dir / "step-conversion.log",
            )
        diagnostics = prepare_surface_for_snappy(
            source_path=stl_path,
            target_path=preflight_dir / "constant" / "triSurface" / "obstacle.stl",
            diagnostics_path=preflight_dir / "geometry-diagnostics.json",
        )
        readiness = write_geometry_readiness(run_dir=preflight_dir, command_results=[])
        readiness["diagnostics"] = diagnostics
    except MeshConversionError as exc:
        (preflight_dir / "step-conversion.log").write_text(str(exc), encoding="utf-8")
        readiness = {
            "status": "failed_geometry",
            "passed": False,
            "repair_mode": None,
            "recommendations": [str(exc)],
        }
        (preflight_dir / "geometry-readiness.json").write_text(
            _json_dumps(readiness),
            encoding="utf-8",
        )
    except RuntimeError:
        readiness = write_geometry_readiness(run_dir=preflight_dir, command_results=[])

    return {
        "upload_id": upload.id,
        "status": readiness.get("status", "failed_geometry"),
        "passed": bool(readiness.get("passed", False)),
        "repair_mode": readiness.get("repair_mode"),
        "meshfix_attempted": bool(readiness.get("meshfix_attempted", False)),
        "recommendations": readiness.get("recommendations", []),
        "readiness": readiness,
        "artifacts": _artifact_refs(preflight_dir),
    }


def _artifact_refs(preflight_dir: Path) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for path in sorted(p for p in preflight_dir.rglob("*") if p.is_file()):
        artifact_type = ARTIFACT_EXTENSIONS.get(path.suffix.lower())
        if artifact_type:
            refs.append(
                {
                    "display_name": path.name,
                    "type": artifact_type,
                    "path": str(path),
                }
            )
    return refs


def _json_dumps(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, indent=2)
