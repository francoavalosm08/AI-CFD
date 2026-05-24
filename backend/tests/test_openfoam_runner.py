import asyncio
import json
import threading
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


def _airfoil_mesh(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "$MeshFormat",
                "2.2 0 8",
                "$EndMeshFormat",
                "$PhysicalNames",
                "6",
                '2 1 "inlet"',
                '2 2 "outlet"',
                '2 3 "farfield"',
                '2 4 "airfoil"',
                '2 5 "frontAndBack"',
                '3 6 "internal"',
                "$EndPhysicalNames",
            ]
        )
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


@pytest.mark.asyncio
async def test_runner_does_not_block_event_loop_while_zipping_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mesh = tmp_path / "wing.msh"
    mesh.write_text("$MeshFormat\n2.2 0 8\n")
    executor = RecordingExecutor(
        [
            CommandResult(command="gmshToFoam input.msh", returncode=0, stdout="mesh imported", stderr=""),
            CommandResult(command="checkMesh -allGeometry -allTopology", returncode=0, stdout="Mesh OK", stderr=""),
            CommandResult(command="simpleFoam", returncode=0, stdout="Solving for Ux\nFinal residual = 1e-5", stderr=""),
            CommandResult(command="foamToVTK", returncode=0, stdout="vtk", stderr=""),
        ]
    )
    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=False, command_executor=executor)
    loop = asyncio.get_running_loop()
    zip_started = asyncio.Event()
    release_zip = threading.Event()

    def slow_zip_case(_case_dir: Path, archive_path: Path) -> Path:
        loop.call_soon_threadsafe(zip_started.set)
        release_zip.wait(timeout=1)
        archive_path.write_bytes(b"zip")
        return archive_path

    monkeypatch.setattr("app.openfoam.runner.zip_case", slow_zip_case)

    task = asyncio.create_task(
        runner.run_external_aero(
            prompt="local openfoam run",
            mesh_path=str(mesh),
            output_dir=str(tmp_path / "run"),
            emit=lambda _status, _message: None,
        )
    )

    await asyncio.wait_for(zip_started.wait(), timeout=0.5)
    assert not task.done()
    release_zip.set()
    result = await asyncio.wait_for(task, timeout=2)

    assert result["case_archive"].endswith("openfoam-case.zip")


@pytest.mark.asyncio
async def test_runner_sets_empty_patch_before_check_mesh_for_2d_airfoil(tmp_path: Path) -> None:
    mesh = tmp_path / "naca4412.msh"
    _airfoil_mesh(mesh)
    executor = RecordingExecutor(
        [
            CommandResult(command="gmshToFoam input.msh", returncode=0, stdout="mesh imported", stderr=""),
            CommandResult(command="python patch boundary", returncode=0, stdout="airfoil set wall; frontAndBack set empty", stderr=""),
            CommandResult(command="checkMesh -allGeometry -allTopology", returncode=0, stdout="cells: 45000\nMesh OK.", stderr=""),
            CommandResult(command="simpleFoam", returncode=0, stdout="Solving for Ux, Initial residual = 1e-4, Final residual = 1e-8, No Iterations 1", stderr=""),
            CommandResult(command="foamToVTK", returncode=0, stdout="vtk", stderr=""),
        ]
    )
    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=False, command_executor=executor)

    result = await runner.run_external_aero(
        prompt="local openfoam airfoil run",
        mesh_path=str(mesh),
        output_dir=str(tmp_path / "run"),
        emit=lambda _status, _message: None,
    )

    assert any("frontAndBack" in command and "airfoil" in command for command in executor.commands)
    assert result["check_mesh_summary"]["passed"] is True
    assert result["check_mesh_summary"]["cells"] == 45000
    assert result["visualizations"] == ["residuals.png"]
    assert (tmp_path / "run" / "residuals.png").exists()


@pytest.mark.asyncio
async def test_runner_fails_airfoil_mesh_validation_before_openfoam_commands(tmp_path: Path) -> None:
    mesh = tmp_path / "bad-airfoil.msh"
    mesh.write_text(
        "\n".join(
            [
                "$MeshFormat",
                "2.2 0 8",
                "$EndMeshFormat",
                "$PhysicalNames",
                "5",
                '2 1 "inlet"',
                '2 2 "outlet"',
                '2 3 "farfield"',
                '2 4 "airfoil"',
                '3 5 "internal"',
                "$EndPhysicalNames",
            ]
        )
    )
    executor = RecordingExecutor()
    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=False, command_executor=executor)

    with pytest.raises(RuntimeError) as exc_info:
        await runner.run_external_aero(
            prompt="local openfoam airfoil run",
            mesh_path=str(mesh),
            output_dir=str(tmp_path / "run"),
            emit=lambda _status, _message: None,
        )

    assert executor.commands == []
    assert "Missing required airfoil_2d physical names: frontAndBack" in str(exc_info.value)
    validation = json.loads((tmp_path / "run" / "mesh-validation.json").read_text())
    assert validation["passed"] is False


@pytest.mark.asyncio
async def test_runner_collects_force_coefficients_from_openfoam_postprocessing(tmp_path: Path) -> None:
    mesh = tmp_path / "naca4412.msh"
    _airfoil_mesh(mesh)
    output_dir = tmp_path / "run"
    case_dir = output_dir / "case"
    executor = RecordingExecutor(
        [
            CommandResult(command="gmshToFoam input.msh", returncode=0, stdout="mesh imported", stderr=""),
            CommandResult(command="python patch boundary", returncode=0, stdout="airfoil set wall; frontAndBack set empty", stderr=""),
            CommandResult(command="checkMesh -allGeometry -allTopology", returncode=0, stdout="cells: 45000\nMesh OK.", stderr=""),
            CommandResult(command="simpleFoam", returncode=0, stdout="Solving for Ux, Initial residual = 1e-4, Final residual = 1e-8, No Iterations 1", stderr=""),
            CommandResult(command="foamToVTK", returncode=0, stdout="vtk", stderr=""),
        ]
    )

    async def force_writing_executor(command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
        result = await executor(command, cwd, timeout_seconds)
        if command == "simpleFoam":
            force_dir = case_dir / "postProcessing" / "forceCoeffs1" / "0"
            force_dir.mkdir(parents=True)
            (force_dir / "forceCoeffs.dat").write_text(
                "# Time Cm Cd Cl Cl(f) Cl(r)\n0 0 0 0 0 0\n10 -0.01 0.03 0.4 0.2 0.2\n",
                encoding="utf-8",
            )
        return result

    runner = LocalOpenFoamRunner(spec=_spec(), dry_run=False, command_executor=force_writing_executor)

    result = await runner.run_external_aero(
        prompt="local openfoam airfoil run",
        mesh_path=str(mesh),
        output_dir=str(output_dir),
        emit=lambda _status, _message: None,
    )

    assert result["final_coefficients"] == {"time": 10.0, "Cm": -0.01, "Cd": 0.03, "Cl": 0.4}
    assert (output_dir / "forceCoeffs.dat").exists()
    assert (output_dir / "forceCoeffs.csv").exists()
    assert (output_dir / "force-coefficients.png").exists()
