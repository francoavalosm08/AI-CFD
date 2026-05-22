from __future__ import annotations

import mimetypes
from pathlib import Path

from app.schemas import Artifact, ArtifactType


ARTIFACT_EXTENSIONS: dict[str, ArtifactType] = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".csv": "plot_data",
    ".json": "plot_data",
    ".log": "log",
    ".out": "log",
    ".err": "log",
    ".zip": "download",
    ".foam": "download",
    ".html": "other",
    ".vtk": "vtk",
    ".vtp": "vtk",
    ".vtu": "vtk",
}


def discover_artifacts(run_id: str, run_dir: Path) -> list[Artifact]:
    artifacts: list[Artifact] = []
    if not run_dir.exists():
        return artifacts

    for path in sorted(p for p in run_dir.rglob("*") if p.is_file()):
        artifact_type = ARTIFACT_EXTENSIONS.get(path.suffix.lower())
        if not artifact_type:
            continue
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        artifacts.append(
            Artifact(
                id=f"{run_id}-{len(artifacts) + 1}",
                run_id=run_id,
                type=artifact_type,
                path=str(path),
                display_name=path.name,
                mime_type=mime_type,
            )
        )
    return artifacts
