from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.openfoam.artifacts import write_residual_csv, zip_case
from app.openfoam.case_builder import build_openfoam_case
from app.openfoam.parsers import parse_residuals
from app.openfoam.runner_types import CommandResult
from app.openfoam.wsl import make_wsl_command_executor, windows_to_wsl_path
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
            result = await self.command_executor(
                command["command"], case_dir, self.timeout_seconds
            )
            results.append(_result_dict(result, command["name"], command["required"]))
            self._write_command_log(output, command["name"], result)
            if result.returncode != 0 and command["required"]:
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(f"{command['name']} failed: {detail}")
            if command["name"] == "check_mesh":
                await _emit(emit, "running", "Running simpleFoam solver")

        solver_log = output / "solver.log"
        residuals = parse_residuals(solver_log.read_text(encoding="utf-8") if solver_log.exists() else "")
        if residuals:
            write_residual_csv(residuals, output / "residuals.csv")
        archive = zip_case(case_dir, output / "openfoam-case.zip")
        await _emit(emit, "visualizing", "Collected local OpenFOAM artifacts")
        return {
            "mode": "local_openfoam",
            "dry_run": False,
            "case_dir": str(case_dir),
            "case_archive": str(archive),
            "commands": commands,
            "results": results,
            "manifest": manifest,
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
