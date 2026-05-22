from pathlib import Path

import pytest

from app.jobs import RunExecutor
from app.openfoam.runner import LocalOpenFoamRunner
from app.schemas import RunRecord, RunStatus, SimulationSpec, UploadRecord


@pytest.mark.asyncio
async def test_run_executor_completes_local_openfoam_dry_run(tmp_path: Path) -> None:
    upload_path = tmp_path / "uploads" / "wing.msh"
    upload_path.parent.mkdir()
    upload_path.write_text("$MeshFormat\n2.2 0 8\n")
    upload = UploadRecord(
        id="upload-1",
        original_name="wing.msh",
        stored_path=str(upload_path),
        kind="gmsh_mesh",
    )
    run = RunRecord(
        id="run-1",
        upload_id=upload.id,
        status=RunStatus.queued,
        spec=SimulationSpec(upload_id=upload.id, units="m", length_scale=1, velocity=20),
    )
    events: list[str] = []
    executor = RunExecutor(
        foam_agent=LocalOpenFoamRunner(spec=run.spec, dry_run=True),
        app_data_root=tmp_path,
        agent_data_root="/workspace/data",
        emit=lambda _run_id, status, _message: events.append(status),
    )

    result = await executor.execute(run, upload)

    assert result.status == RunStatus.completed
    assert result.summary["mode"] == "local_openfoam"
    assert result.summary["dry_run"] is True
    assert any(artifact.display_name == "openfoam-commands.json" for artifact in result.artifacts)
    assert "running" in events
