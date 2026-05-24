from __future__ import annotations

from pathlib import Path


AIRFOIL_2D_REQUIRED_PHYSICAL_NAMES = {
    "airfoil",
    "farfield",
    "frontAndBack",
    "inlet",
    "internal",
    "outlet",
}
AIRFOIL_2D_HINT_NAMES = {"airfoil", "farfield", "frontAndBack"}
EXTERNAL_2D_OBSTACLE_REQUIRED_PHYSICAL_NAMES = {
    "farfield",
    "frontAndBack",
    "inlet",
    "internal",
    "obstacle",
    "outlet",
}


def read_msh_physical_names(mesh_path: Path) -> set[str]:
    text = mesh_path.read_text(errors="ignore")
    names: set[str] = set()
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "$PhysicalNames":
            in_section = True
            continue
        if stripped == "$EndPhysicalNames":
            break
        if in_section and '"' in stripped:
            names.add(stripped.split('"', 2)[1])
    return names


def validate_msh_physical_names(mesh_path: Path) -> dict:
    physical_names = read_msh_physical_names(mesh_path)
    warnings: list[str] = []
    if "obstacle" in physical_names:
        missing = sorted(EXTERNAL_2D_OBSTACLE_REQUIRED_PHYSICAL_NAMES - physical_names)
        if missing:
            warnings.append(
                "Missing required external_2d_obstacle physical names: " + ", ".join(missing)
            )
        return {
            "case_type": "external_2d_obstacle",
            "confidence": "high" if not missing else "low",
            "passed": not missing,
            "physical_names": sorted(physical_names),
            "required_physical_names": sorted(EXTERNAL_2D_OBSTACLE_REQUIRED_PHYSICAL_NAMES),
            "missing_required_physical_names": missing,
            "warnings": warnings,
        }

    is_airfoil_candidate = bool(physical_names & AIRFOIL_2D_HINT_NAMES)
    if is_airfoil_candidate:
        missing = sorted(AIRFOIL_2D_REQUIRED_PHYSICAL_NAMES - physical_names)
        if missing:
            warnings.append(
                "Missing required airfoil_2d physical names: " + ", ".join(missing)
            )
        return {
            "case_type": "airfoil_2d",
            "confidence": "high" if not missing else "low",
            "passed": not missing,
            "physical_names": sorted(physical_names),
            "required_physical_names": sorted(AIRFOIL_2D_REQUIRED_PHYSICAL_NAMES),
            "missing_required_physical_names": missing,
            "warnings": warnings,
        }

    warnings.append(
        "Mesh does not match a known V1 patch template; running as lower-confidence generic external mesh."
    )
    return {
        "case_type": "generic_external",
        "confidence": "low",
        "passed": True,
        "physical_names": sorted(physical_names),
        "required_physical_names": [],
        "missing_required_physical_names": [],
        "warnings": warnings,
    }
