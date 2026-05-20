from __future__ import annotations

from pathlib import Path

from app.schemas import UploadKind


class UnsupportedUploadType(ValueError):
    pass


SUPPORTED_EXTENSIONS: dict[str, UploadKind] = {
    ".msh": "gmsh_mesh",
    ".stl": "surface_mesh",
    ".step": "cad",
    ".stp": "cad",
    ".zip": "openfoam_case",
}


def detect_upload_kind(filename: str) -> UploadKind:
    extension = Path(filename).suffix.lower()
    if extension in SUPPORTED_EXTENSIONS:
        return SUPPORTED_EXTENSIONS[extension]
    raise UnsupportedUploadType(
        "Unsupported file type. Upload a .msh, .stl, .step, .stp, or .zip file."
    )
