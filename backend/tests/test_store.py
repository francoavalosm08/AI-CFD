from pathlib import Path

from app.schemas import RunRecord, RunStatus, SimulationSpec, UploadRecord
from app.store import Repository


def test_repository_persists_uploads_and_runs(tmp_path: Path):
    repo = Repository(tmp_path / "workbench.sqlite3")
    upload = UploadRecord(
        id="upload-1",
        original_name="wing.msh",
        stored_path=str(tmp_path / "uploads" / "wing.msh"),
        kind="gmsh_mesh",
    )
    run = RunRecord(
        id="run-1",
        upload_id=upload.id,
        status=RunStatus.queued,
        spec=SimulationSpec(upload_id=upload.id, units="m", length_scale=1, velocity=25, angle_of_attack=4),
        prompt_used="prompt",
    )

    repo.save_upload(upload)
    repo.save_run(run)

    assert repo.get_upload(upload.id) == upload
    assert repo.get_run(run.id).prompt_used == "prompt"
    assert repo.list_runs()[0].id == "run-1"
