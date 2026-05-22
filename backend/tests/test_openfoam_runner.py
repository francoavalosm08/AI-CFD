import json
from pathlib import Path

import pytest

from app.openfoam.runner import CommandResult, LocalOpenFoamRunner
from app.schemas import SimulationSpec


class RecordingExecutor:
    def __init__(self, results: list[CommandResult] | None = None) -> None:
        self.commands: list[str] = []
        self.results = results or []

    async def __call__(self, command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
        self.commands.append(command)
        if self.results:
            return self.results.pop(0)
        return CommandResult(command=command, returncode=0, stdout="ok", stderr="")


def _spec() -> SimulationSpec:
    return SimulationSpec(
        upload_id="upload-1",
        units="m",
        length_scale=1,
        velocity=25,
        angle_of_attack=4,
    )


@pytest.mark.asyncio
async def test_runner_dry_run_writes_command_manifest_without_executing(tmp_path: Path) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    executor = RecordingExecutor()
    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=True, command_executor=executor)

    result = await runner.run_external_aero(
        prompt="local openfoam run",
        mesh_path=str(mesh),
        output_dir=str(tmp_path / "run"),
        emit=lambda _status, _message: None,
    )

    assert result["dry_run"] is True
    assert executor.commands == []
    assert (tmp_path / "run" / "openfoam-commands.json").exists()
    assert (tmp_path / "run" / "openfoam-dry-run.log").exists()
    assert (tmp_path / "run" / "openfoam-case.zip").exists()


@pytest.mark.asyncio
async def test_runner_dry_run_manifest_records_wsl_runtime_and_paths(tmp_path: Path) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=True, runtime="wsl")

    await runner.run_external_aero(
        prompt="local openfoam run",
        mesh_path=str(mesh),
        output_dir=str(tmp_path / "run"),
        emit=lambda _status, _message: None,
    )

    manifest = json.loads((tmp_path / "run" / "openfoam-commands.json").read_text())

    assert manifest["runtime"] == "wsl"
    assert manifest["case_dir_windows"].endswith("case")
    assert manifest["case_dir_wsl"].endswith("/case")


@pytest.mark.asyncio
async def test_runner_stops_when_required_command_fails(tmp_path: Path) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    executor = RecordingExecutor(
        [
            CommandResult(command="gmshToFoam input.msh", returncode=0, stdout="mesh imported", stderr=""),
            CommandResult(command="checkMesh -allGeometry -allTopology", returncode=1, stdout="", stderr="bad mesh"),
        ]
    )
    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=False, command_executor=executor)

    with pytest.raises(RuntimeError) as exc_info:
        await runner.run_external_aero(
            prompt="local openfoam run",
            mesh_path=str(mesh),
            output_dir=str(tmp_path / "run"),
            emit=lambda _status, _message: None,
        )

    assert "check_mesh failed" in str(exc_info.value)
    assert "bad mesh" in str(exc_info.value)
    assert (tmp_path / "run" / "checkMesh.log").exists()


@pytest.mark.asyncio
async def test_runner_allows_optional_export_failure(tmp_path: Path) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    executor = RecordingExecutor(
        [
            CommandResult(command="gmshToFoam input.msh", returncode=0, stdout="mesh imported", stderr=""),
            CommandResult(command="checkMesh -allGeometry -allTopology", returncode=0, stdout="Mesh OK", stderr=""),
            CommandResult(command="simpleFoam", returncode=0, stdout="Solving for Ux\nFinal residual = 1e-5", stderr=""),
            CommandResult(command="foamToVTK", returncode=1, stdout="", stderr="missing optional exporter"),
        ]
    )
    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=False, command_executor=executor)

    result = await runner.run_external_aero(
        prompt="local openfoam run",
        mesh_path=str(mesh),
        output_dir=str(tmp_path / "run"),
        emit=lambda _status, _message: None,
    )

    assert result["mode"] == "local_openfoam"
    assert result["commands"][-1]["required"] is False
    assert (tmp_path / "run" / "solver.log").exists()
