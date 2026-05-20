from __future__ import annotations

import asyncio
import shutil
from pathlib import Path


class MeshConversionError(RuntimeError):
    pass


async def convert_to_gmsh_mesh(
    source_path: Path, output_path: Path, *, gmsh_command: str = "gmsh"
) -> Path:
    gmsh = shutil.which(gmsh_command)
    if not gmsh:
        raise MeshConversionError(
            f"Could not convert {source_path.name} to a Gmsh .msh file because '{gmsh_command}' "
            "is not installed or not on PATH. Upload a cleaner STL/STEP with Gmsh available, or "
            "upload a pre-meshed .msh file."
        )

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
    if process.returncode != 0 or not output_path.exists():
        detail = (stderr or stdout).decode(errors="replace").strip()
        raise MeshConversionError(
            f"Could not convert {source_path.name} to a Gmsh .msh file. {detail}"
        )
    return output_path
