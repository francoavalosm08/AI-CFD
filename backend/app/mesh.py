from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from app.openfoam.mesh_validation import read_msh_physical_names


AIRFOIL_2D_PHYSICAL_NAMES_COPY = (
    "airfoil, inlet, outlet, farfield, frontAndBack, and internal"
)


class MeshConversionError(RuntimeError):
    pass


def conversion_unavailable_message(source_name: str, gmsh_command: str) -> str:
    return (
        f"Could not convert {source_name} to a Gmsh .msh file because '{gmsh_command}' "
        "is not installed or not on PATH. STEP/STL conversion is best-effort in V1. "
        "For the production workflow, upload a pre-meshed Gmsh .msh file with physical "
        f"names: {AIRFOIL_2D_PHYSICAL_NAMES_COPY}."
    )


def cad_surface_conversion_unavailable_message(source_name: str, gmsh_command: str) -> str:
    return (
        f"Could not convert {source_name} to an STL surface because '{gmsh_command}' "
        "is not installed or not on PATH. Install Gmsh to use STEP/STP through the "
        "local snappyHexMesh path, or upload a watertight STL or pre-meshed Gmsh .msh file."
    )


def conversion_failure_message(source_name: str, detail: str) -> str:
    normalized = detail.lower()
    hints: list[str] = []

    if any(
        phrase in normalized
        for phrase in (
            "no elements in volume",
            "no tetrahedra",
            "no volume",
            "not a volume",
            "3d mesh cannot be generated",
            "invalid boundary mesh",
        )
    ):
        hints.append(
            "Gmsh did not create the required volume mesh; this usually means a "
            "missing volume mesh, open surface, non-watertight STL, or geometry "
            "that needs repair."
        )
    if "physical" in normalized:
        hints.append(
            f"The mesh must define Gmsh PhysicalNames: {AIRFOIL_2D_PHYSICAL_NAMES_COPY}."
        )
    hints.append(
        "Use a cleaner closed STL/STEP, or upload a pre-meshed Gmsh .msh file."
    )

    cleaned_detail = " ".join(detail.split())
    if cleaned_detail:
        cleaned_detail = cleaned_detail[:1200]
        return (
            f"Could not convert {source_name} to a Gmsh .msh file. STEP/STL conversion "
            f"is best-effort in V1. {' '.join(hints)} Gmsh output: {cleaned_detail}"
        )
    return (
        f"Could not convert {source_name} to a Gmsh .msh file. STEP/STL conversion "
        f"is best-effort in V1. {' '.join(hints)}"
    )


def cad_surface_conversion_failure_message(source_name: str, detail: str) -> str:
    cleaned_detail = " ".join(detail.split())[:1200]
    base = (
        f"Could not convert {source_name} to an STL surface for snappyHexMesh. "
        "This usually means the CAD needs geometry cleanup, face sewing, or export as a "
        "watertight STL. You can also upload a pre-meshed Gmsh .msh file."
    )
    if cleaned_detail:
        return f"{base} Gmsh output: {cleaned_detail}"
    return base


def validate_converted_mesh(output_path: Path, source_name: str) -> None:
    physical_names = read_msh_physical_names(output_path)
    if physical_names:
        return
    raise MeshConversionError(
        f"Converted {source_name} to .msh, but the result has no Gmsh PhysicalNames. "
        "V1 needs named patches before it can build a reliable OpenFOAM case. Define "
        f"physical names: {AIRFOIL_2D_PHYSICAL_NAMES_COPY}, or upload a pre-meshed "
        "Gmsh .msh file."
    )


def validate_converted_surface(output_path: Path, source_name: str) -> None:
    if output_path.exists() and output_path.stat().st_size > 0:
        return
    raise MeshConversionError(
        f"Converted {source_name} to STL, but the output surface was empty. "
        "Export a watertight STL or upload a pre-meshed Gmsh .msh file."
    )


async def convert_to_gmsh_mesh(
    source_path: Path, output_path: Path, *, gmsh_command: str = "gmsh"
) -> Path:
    gmsh = shutil.which(gmsh_command)
    if not gmsh:
        raise MeshConversionError(conversion_unavailable_message(source_path.name, gmsh_command))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        gmsh,
        str(source_path),
        "-3",
        "-format",
        "msh2",
        "-o",
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        detail = (stderr or stdout).decode(errors="replace").strip()
        raise MeshConversionError(conversion_failure_message(source_path.name, detail))
    validate_converted_mesh(output_path, source_path.name)
    return output_path


async def convert_cad_to_stl_surface(
    source_path: Path, output_path: Path, *, gmsh_command: str = "gmsh"
) -> Path:
    gmsh = shutil.which(gmsh_command)
    if not gmsh:
        raise MeshConversionError(
            cad_surface_conversion_unavailable_message(source_path.name, gmsh_command)
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        gmsh,
        str(source_path),
        "-2",
        "-format",
        "stl",
        "-o",
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        detail = (stderr or stdout).decode(errors="replace").strip()
        raise MeshConversionError(cad_surface_conversion_failure_message(source_path.name, detail))
    validate_converted_surface(output_path, source_path.name)
    return output_path
