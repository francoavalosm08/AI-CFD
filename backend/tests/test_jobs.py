from pathlib import Path

import pytest

from app.jobs import RunExecutor
from app.schemas import RunRecord, RunStatus, SimulationSpec, UploadRecord


class FakeFoamAgent:
    def __init__(self):
        self.calls = []

    async def run_external_aero(self, *, prompt, mesh_path, output_dir, emit):
        self.calls.append((prompt, mesh_path, output_dir))
        await emit("planning", "Fake Foam-Agent planning complete")
        await emit("running", "Fake OpenFOAM run complete")
        await emit("visualizing", "Fake PyVista image generated")
        Path(output_dir, "pressure.png").write_bytes(b"png")
        return {"summary": "fake complete"}


class FailingFoamAgent:
    async def run_external_aero(self, *, prompt, mesh_path, output_dir, emit):
        Path(output_dir, "mesh-validation.json").write_text('{"passed": false}\n')
        raise RuntimeError("Missing required airfoil_2d physical names: frontAndBack")


@pytest.mark.asyncio
async def test_run_executor_moves_run_to_completed_and_discovers_artifacts(tmp_path: Path):
    upload = UploadRecord(
        id="upload-1",
        original_name="wing.msh",
        stored_path=str(tmp_path / "uploads" / "wing.msh"),
        kind="gmsh_mesh",
    )
    Path(upload.stored_path).parent.mkdir()
    Path(upload.stored_path).write_text("$MeshFormat\n2.2 0 8\n")
    run = RunRecord(
        id="run-1",
        upload_id=upload.id,
        status=RunStatus.queued,
        spec=SimulationSpec(upload_id=upload.id, units="m", length_scale=1, velocity=20, angle_of_attack=3),
    )

    events = []
    executor = RunExecutor(
        foam_agent=FakeFoamAgent(),
        app_data_root=tmp_path,
        agent_data_root="/workspace/data",
        emit=lambda run_id, status, message: events.append((run_id, status, message)),
    )

    result = await executor.execute(run, upload)

    assert result.status == RunStatus.completed
    assert result.prompt_used is not None
    assert result.artifacts[0].display_name == "pressure.png"
    assert [event[1] for event in events] == ["preprocessing", "planning", "running", "visualizing", "completed"]


@pytest.mark.asyncio
async def test_run_executor_fails_stl_with_clear_mesh_conversion_error(tmp_path: Path):
    upload = UploadRecord(
        id="upload-1",
        original_name="body.stl",
        stored_path=str(tmp_path / "uploads" / "body.stl"),
        kind="surface_mesh",
    )
    Path(upload.stored_path).parent.mkdir()
    Path(upload.stored_path).write_text("solid empty\nendsolid empty\n")
    run = RunRecord(
        id="run-1",
        upload_id=upload.id,
        status=RunStatus.queued,
        spec=SimulationSpec(upload_id=upload.id, units="m", length_scale=1, velocity=20, angle_of_attack=3),
    )

    executor = RunExecutor(
        foam_agent=FakeFoamAgent(),
        app_data_root=tmp_path,
        agent_data_root="/workspace/data",
        emit=lambda *_: None,
        gmsh_command="definitely-not-installed",
    )

    result = await executor.execute(run, upload)

    assert result.status == RunStatus.failed
    assert "Could not convert body.stl to a Gmsh .msh file" in result.error


@pytest.mark.asyncio
async def test_run_executor_discovers_artifacts_written_before_failure(tmp_path: Path):
    upload = UploadRecord(
        id="upload-1",
        original_name="bad-airfoil.msh",
        stored_path=str(tmp_path / "uploads" / "bad-airfoil.msh"),
        kind="gmsh_mesh",
    )
    Path(upload.stored_path).parent.mkdir()
    Path(upload.stored_path).write_text("$MeshFormat\n2.2 0 8\n")
    run = RunRecord(
        id="run-1",
        upload_id=upload.id,
        status=RunStatus.queued,
        spec=SimulationSpec(upload_id=upload.id, units="m", length_scale=1, velocity=20),
    )
    executor = RunExecutor(
        foam_agent=FailingFoamAgent(),
        app_data_root=tmp_path,
        agent_data_root="/workspace/data",
        emit=lambda *_: None,
    )

    result = await executor.execute(run, upload)

    assert result.status == RunStatus.failed
    assert "frontAndBack" in (result.error or "")
    assert [artifact.display_name for artifact in result.artifacts] == ["mesh-validation.json"]
