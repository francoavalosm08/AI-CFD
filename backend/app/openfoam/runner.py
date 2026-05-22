from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from pathlib import Path, PurePosixPath
from typing import Any

from app.openfoam.artifacts import write_residual_csv, zip_case
from app.openfoam.case_builder import build_openfoam_case
from app.openfoam.parsers import parse_check_mesh_summary, parse_residuals
from app.openfoam.report import write_run_report
from app.openfoam.runner_types import CommandResult
from app.openfoam.wsl import (
    make_wsl_command_executor,
    quote_bash,
    run_wsl_shell_command,
    windows_to_wsl_path,
)
from app.schemas import SimulationSpec


CommandExecutor = Callable[[str, Path, int], Awaitable[CommandResult]]


class LocalOpenFoamRunner:
    mesh_path_mode = "host"

    def __init__(
        self,
        *,
        spec: SimulationSpec,
        dry_run: bool = False,
        runtime: str = "wsl",
        wsl_distro: str = "Ubuntu",
        openfoam_bashrc: str = "/opt/openfoam*/etc/bashrc",
        timeout_seconds: int = 1200,
        command_executor: CommandExecutor | None = None,
    ) -> None:
        self.spec = spec
        self.dry_run = dry_run
        self.runtime = runtime
        self.wsl_distro = wsl_distro
        self.openfoam_bashrc = openfoam_bashrc
        self.timeout_seconds = timeout_seconds
        self._uses_default_executor = command_executor is None
        if command_executor is not None:
            self.command_executor = command_executor
        elif runtime == "wsl":
            self.command_executor = make_wsl_command_executor(
                distro=wsl_distro,
                bashrc=openfoam_bashrc,
            )
        else:
            self.command_executor = _run_shell_command

    async def run_external_aero(
        self,
        *,
        prompt: str,
        mesh_path: str | None,
        output_dir: str,
        emit: Callable[[str, str], Awaitable[None] | None],
    ) -> dict[str, Any]:
        if not mesh_path:
            raise RuntimeError("Local OpenFOAM mode requires an uploaded .msh mesh path")
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        case_dir = output / "case"
        await _emit(emit, "planning", "Building deterministic local OpenFOAM case")
        manifest = build_openfoam_case(
            spec=self.spec,
            mesh_path=Path(mesh_path),
            case_dir=case_dir,
        )
        commands = self._commands()
        command_manifest: dict[str, Any] = {
            "runtime": self.runtime,
            "dry_run": self.dry_run,
            "case_dir": str(case_dir),
            "case_dir_windows": str(case_dir),
            "commands": commands,
            "prompt_excerpt": prompt[:240],
        }
        if self.runtime == "wsl":
            command_manifest["wsl_distro"] = self.wsl_distro
            command_manifest["openfoam_bashrc"] = self.openfoam_bashrc
            command_manifest["case_dir_wsl"] = windows_to_wsl_path(case_dir)

        execution_case_dir = case_dir
        command_executor = self.command_executor
        staged_case_dir_wsl: str | None = None
        if self.runtime == "wsl" and self._uses_default_executor and not self.dry_run:
            staged_case_dir_wsl = f"/tmp/ai-cfd-workbench/{output.name}/case"
            command_manifest["execution_case_dir_wsl"] = staged_case_dir_wsl
            await _emit(emit, "preprocessing", "Staging OpenFOAM case into WSL-native storage")
            await self._stage_case_to_wsl(case_dir, staged_case_dir_wsl)
            command_executor = make_wsl_command_executor(
                distro=self.wsl_distro,
                bashrc=self.openfoam_bashrc,
                cwd_wsl=staged_case_dir_wsl,
            )

        (output / "openfoam-commands.json").write_text(
            json.dumps(command_manifest, indent=2),
            encoding="utf-8",
        )

        if self.dry_run:
            await _emit(emit, "running", "Dry run wrote OpenFOAM case and command manifest")
            (output / "openfoam-dry-run.log").write_text(
                "Dry run only. No OpenFOAM commands were executed.\n", encoding="utf-8"
            )
            archive = zip_case(case_dir, output / "openfoam-case.zip")
            return {
                "mode": "local_openfoam",
                "dry_run": True,
                "case_dir": str(case_dir),
                "case_archive": str(archive),
                "commands": commands,
                "manifest": manifest,
            }

        results: list[dict[str, Any]] = []
        await _emit(emit, "meshing", "Importing uploaded mesh with gmshToFoam")
        for command in commands:
            result = await command_executor(
                command["command"], execution_case_dir, self.timeout_seconds
            )
            results.append(_result_dict(result, command["name"], command["required"]))
            self._write_command_log(output, command["name"], result)
            if result.returncode != 0 and command["required"]:
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(f"{command['name']} failed: {detail}")
            if command["name"] == "import_mesh" and manifest.get("case_type") == "airfoil_2d":
                patch_result = await command_executor(
                    _front_and_back_empty_command(),
                    execution_case_dir,
                    self.timeout_seconds,
                )
                results.append(_result_dict(patch_result, "set_empty_patches", True))
                self._write_command_log(output, "set_empty_patches", patch_result)
                if patch_result.returncode != 0:
                    detail = (patch_result.stderr or patch_result.stdout).strip()
                    raise RuntimeError(f"set_empty_patches failed: {detail}")
            if command["name"] == "check_mesh":
                await _emit(emit, "running", "Running simpleFoam solver")

        solver_log = output / "solver.log"
        check_mesh_log = output / "checkMesh.log"
        check_mesh_summary = parse_check_mesh_summary(
            check_mesh_log.read_text(encoding="utf-8") if check_mesh_log.exists() else ""
        )
        if check_mesh_summary:
            (output / "checkMesh-summary.json").write_text(
                json.dumps(check_mesh_summary, indent=2),
                encoding="utf-8",
            )
        residuals = parse_residuals(solver_log.read_text(encoding="utf-8") if solver_log.exists() else "")
        if residuals:
            write_residual_csv(residuals, output / "residuals.csv")
        if staged_case_dir_wsl:
            await self._copy_wsl_case_back(staged_case_dir_wsl, case_dir)
        archive = zip_case(case_dir, output / "openfoam-case.zip")
        chord_length = manifest.get("chord_length_m") or self.spec.length_scale
        reynolds_number = manifest.get("reynolds_number")
        report = write_run_report(
            run_dir=output,
            output_path=output / "openfoam-report.html",
            title="OpenFOAM Solver Output",
            inputs={
                "Velocity": f"{self.spec.velocity:g} m/s",
                "Angle of attack": f"{self.spec.angle_of_attack:g} deg",
                "Chord": f"{chord_length:g} m",
                "Kinematic viscosity": f"{manifest.get('kinematic_viscosity_m2_s', 1.5e-5):g} m^2/s",
                "Reynolds number": f"{reynolds_number:g}" if reynolds_number is not None else "n/a",
            },
        )
        await _emit(emit, "visualizing", "Collected local OpenFOAM artifacts")
        return {
            "mode": "local_openfoam",
            "dry_run": False,
            "case_dir": str(case_dir),
            "case_archive": str(archive),
            "report": str(report),
            "commands": commands,
            "results": results,
            "manifest": manifest,
            "check_mesh_summary": check_mesh_summary,
        }

    def _commands(self) -> list[dict[str, Any]]:
        return [
            {"name": "import_mesh", "command": "gmshToFoam input.msh", "required": True},
            {
                "name": "check_mesh",
                "command": "checkMesh -allGeometry -allTopology",
                "required": True,
            },
            {"name": "solve", "command": "simpleFoam", "required": True},
            {"name": "export_vtk", "command": "foamToVTK", "required": False},
        ]

    def _write_command_log(self, output_dir: Path, name: str, result: CommandResult) -> None:
        filename = {
            "check_mesh": "checkMesh.log",
            "solve": "solver.log",
        }.get(name, f"{name}.log")
        text = result.stdout
        if result.stderr:
            text = f"{text}\n--- stderr ---\n{result.stderr}"
        (output_dir / filename).write_text(text, encoding="utf-8")

    async def _stage_case_to_wsl(self, case_dir: Path, staged_case_dir_wsl: str) -> None:
        staged_parent = str(PurePosixPath(staged_case_dir_wsl).parent)
        command = (
            f"rm -rf {quote_bash(staged_case_dir_wsl)} && "
            f"mkdir -p {quote_bash(staged_parent)} && "
            f"cp -a {quote_bash(windows_to_wsl_path(case_dir))} {quote_bash(staged_parent)}/case"
        )
        result = await run_wsl_shell_command(
            command,
            distro=self.wsl_distro,
            timeout_seconds=self.timeout_seconds,
            display_command="stage OpenFOAM case into WSL",
        )
        if result.returncode != 0:
            raise RuntimeError(f"WSL case staging failed: {(result.stderr or result.stdout).strip()}")

    async def _copy_wsl_case_back(self, staged_case_dir_wsl: str, case_dir: Path) -> None:
        case_dir.parent.mkdir(parents=True, exist_ok=True)
        case_dir.mkdir(parents=True, exist_ok=True)
        command = (
            f"cp -a {quote_bash(staged_case_dir_wsl)}/. "
            f"{quote_bash(windows_to_wsl_path(case_dir))}/"
        )
        result = await run_wsl_shell_command(
            command,
            distro=self.wsl_distro,
            timeout_seconds=self.timeout_seconds,
            display_command="copy OpenFOAM case back from WSL",
        )
        if result.returncode != 0:
            raise RuntimeError(f"WSL case copy-back failed: {(result.stderr or result.stdout).strip()}")


async def _run_shell_command(command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
    except TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        return CommandResult(
            command=command,
            returncode=124,
            stdout=stdout.decode(errors="replace"),
            stderr=(stderr.decode(errors="replace") + "\nCommand timed out.").strip(),
        )
    return CommandResult(
        command=command,
        returncode=process.returncode,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
    )


async def _emit(
    emit: Callable[[str, str], Awaitable[None] | None], status: str, message: str
) -> None:
    result = emit(status, message)
    if inspect.isawaitable(result):
        await result


def _result_dict(result: CommandResult, name: str, required: bool) -> dict[str, Any]:
    return {
        "name": name,
        "command": result.command,
        "required": required,
        "returncode": result.returncode,
        "stdout_excerpt": result.stdout[:500],
        "stderr_excerpt": result.stderr[:500],
    }


def _front_and_back_empty_command() -> str:
    script = (
        "from pathlib import Path; "
        "p=Path('constant/polyMesh/boundary'); "
        "text=p.read_text(); "
        "front='frontAndBack\\n    {\\n        type            patch;'; "
        "front_new='frontAndBack\\n    {\\n        type            empty;'; "
        "airfoil='airfoil\\n    {\\n        type            patch;'; "
        "airfoil_new='airfoil\\n    {\\n        type            wall;'; "
        "assert front in text, 'frontAndBack patch block with type patch was not found'; "
        "assert airfoil in text, 'airfoil patch block with type patch was not found'; "
        "text=text.replace(front,front_new,1).replace(airfoil,airfoil_new,1); "
        "p.write_text(text); "
        "print('airfoil set to wall; frontAndBack set to empty')"
    )
    escaped = script.replace("'", "'\"'\"'")
    return f"python3 -c '{escaped}'"
