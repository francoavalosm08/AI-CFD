from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


UploadKind = Literal["gmsh_mesh", "surface_mesh", "cad", "openfoam_case"]
ArtifactType = Literal["image", "log", "plot_data", "download", "vtk", "other"]


class RunStatus(StrEnum):
    queued = "queued"
    preprocessing = "preprocessing"
    planning = "planning"
    meshing = "meshing"
    running = "running"
    reviewing = "reviewing"
    visualizing = "visualizing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class SimulationSpec(BaseModel):
    upload_id: str
    units: Literal["m", "cm", "mm", "in", "ft"]
    length_scale: float = Field(gt=0)
    velocity: float = Field(gt=0)
    mach: float | None = Field(default=None, ge=0)
    angle_of_attack: float = Field(default=0)
    fluid_preset: str = "air_15c"
    turbulence_preset: str = "steady_rans_sst"
    mesh_quality: Literal["coarse", "balanced", "fine"] = "balanced"
    requested_outputs: list[str] = Field(
        default_factory=lambda: ["residuals", "pressure", "velocity", "forces"]
    )
    max_runtime_minutes: int = Field(default=60, ge=1, le=24 * 60)

    @field_validator("requested_outputs")
    @classmethod
    def requested_outputs_must_not_be_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one requested output is required")
        return value


class UploadRecord(BaseModel):
    id: str
    original_name: str
    stored_path: str
    kind: UploadKind
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Artifact(BaseModel):
    id: str
    run_id: str
    type: ArtifactType
    path: str
    display_name: str
    mime_type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunRecord(BaseModel):
    id: str
    upload_id: str
    status: RunStatus
    spec: SimulationSpec
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    prompt_used: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Artifact] = Field(default_factory=list)


class RunCreateRequest(BaseModel):
    spec: SimulationSpec


class ArtifactListResponse(BaseModel):
    artifacts: list[Artifact]
