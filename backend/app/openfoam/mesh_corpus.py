from __future__ import annotations

from pathlib import Path

from app.openfoam.mesh_validation import validate_msh_physical_names


def classify_msh_file(mesh_path: Path) -> dict:
    text = mesh_path.read_text(errors="ignore")
    lines = text.splitlines()
    first_line = lines[0].strip() if lines else ""

    if first_line.startswith("(0") or "Fluent Mesh File" in text[:512]:
        return {
            "path": str(mesh_path),
            "format": "fluent_msh",
            "nodes": None,
            "elements": None,
            "physical_names": [],
            "case_type": "unsupported",
            "openfoam_v1_ready": False,
            "support_status": "unsupported_format",
            "warnings": [
                "Fluent .msh is not accepted by the current V1 gmshToFoam path; keep as an incompatibility fixture."
            ],
        }

    if "$MeshFormat" not in text[:512]:
        return {
            "path": str(mesh_path),
            "format": "unknown",
            "nodes": None,
            "elements": None,
            "physical_names": [],
            "case_type": "unsupported",
            "openfoam_v1_ready": False,
            "support_status": "unsupported_format",
            "warnings": ["File does not look like a Gmsh MSH file."],
        }

    mesh_format = _read_mesh_format(lines)
    validation = validate_msh_physical_names(mesh_path)
    physical_names = validation["physical_names"]
    ready = validation["case_type"] in {"airfoil_2d", "external_2d_obstacle"} and validation["passed"]
    warnings: list[str] = []
    if not physical_names:
        warnings.append("No $PhysicalNames section found; cannot map stable OpenFOAM boundary conditions.")
    warnings.extend(validation["warnings"])

    return {
        "path": str(mesh_path),
        "format": f"gmsh_msh_{mesh_format}_ascii" if mesh_format else "gmsh_msh_ascii",
        "nodes": _read_section_count(lines, "$Nodes"),
        "elements": _read_section_count(lines, "$Elements"),
        "physical_names": physical_names,
        "case_type": validation["case_type"],
        "openfoam_v1_ready": ready,
        "support_status": f"ready_{validation['case_type']}" if ready else "format_only_not_solver_ready",
        "warnings": warnings,
    }


def _read_mesh_format(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if line.strip() == "$MeshFormat" and index + 1 < len(lines):
            return lines[index + 1].split()[0]
    return ""


def _read_section_count(lines: list[str], section_name: str) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() == section_name and index + 1 < len(lines):
            try:
                return int(lines[index + 1].strip().split()[0])
            except (IndexError, ValueError):
                return None
    return None
