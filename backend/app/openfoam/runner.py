from __future__ import annotations

import asyncio
import inspect
import json
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path, PurePosixPath
from typing import Any

from app.openfoam.artifacts import write_force_coefficients_csv, write_residual_csv, zip_case
from app.openfoam.case_builder import build_openfoam_case
from app.openfoam.mesh_validation import validate_msh_physical_names
from app.openfoam.parsers import (
    final_force_coefficients,
    parse_check_mesh_summary,
    parse_force_coefficients,
    parse_residuals,
)
from app.openfoam.report import write_run_report
from app.openfoam.runner_types import CommandResult
from app.openfoam.snappy import build_snappy_stl_case, snappy_openfoam_commands
from app.openfoam.visualization import write_visualization_previews
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
    accepts_surface_mesh = True

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
        source_path = Path(mesh_path)
        if source_path.suffix.lower() == ".stl":
            await _emit(emit, "preprocessing", "Preparing STL surface for snappyHexMesh")
            mesh_validation = {
                "case_type": "external_3d_stl_snappy",
                "confidence": "medium",
                "passed": True,
                "physical_names": [],
                "required_physical_names": [],
                "missing_required_physical_names": [],
                "warnings": [
                    "STL accepted for snappyHexMesh meshing; reliability depends on a closed/watertight surface and checkMesh results."
                ],
            }
            (output / "mesh-validation.json").write_text(
                json.dumps(mesh_validation, indent=2),
                encoding="utf-8",
            )
            await _emit(emit, "planning", "Building deterministic snappyHexMesh case")
            manifest = build_snappy_stl_case(
                spec=self.spec,
                stl_path=source_path,
                case_dir=case_dir,
            )
            commands = snappy_openfoam_commands()
        else:
            await _emit(emit, "preprocessing", "Validating Gmsh physical names")
            mesh_validation = validate_msh_physical_names(source_path)
            (output / "mesh-validation.json").write_text(
                json.dumps(mesh_validation, indent=2),
                encoding="utf-8",
            )
            if not mesh_validation["passed"]:
                raise RuntimeError("; ".join(mesh_validation["warnings"]))

            await _emit(emit, "planning", "Building deterministic local OpenFOAM case")
            manifest = build_openfoam_case(
                spec=self.spec,
                mesh_path=source_path,
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
            "mesh_validation": mesh_validation,
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
            archive = await asyncio.to_thread(zip_case, case_dir, output / "openfoam-case.zip")
            return {
                "mode": "local_openfoam",
                "dry_run": True,
                "case_dir": str(case_dir),
                "case_archive": str(archive),
                "commands": commands,
                "manifest": manifest,
                "mesh_validation": mesh_validation,
            }

        results: list[dict[str, Any]] = []
        meshing_message = (
            "Meshing STL surface with snappyHexMesh"
            if manifest.get("case_type") == "external_3d_stl_snappy"
            else "Importing uploaded mesh with gmshToFoam"
        )
        await _emit(emit, "meshing", meshing_message)
        for command in commands:
            result = await command_executor(
                command["command"], execution_case_dir, self.timeout_seconds
            )
            results.append(_result_dict(result, command["name"], command["required"]))
            self._write_command_log(output, command["name"], result)
            if result.returncode != 0 and command["required"]:
                detail = (result.stderr or result.stdout).strip()
                raise RuntimeError(f"{command['name']} failed: {detail}")
            if command["name"] == "import_mesh" and manifest.get("case_type") in {"airfoil_2d", "external_2d_obstacle"}:
                patch_result = await command_executor(
                    _front_and_back_empty_command(
                        "airfoil" if manifest.get("case_type") == "airfoil_2d" else "obstacle"
                    ),
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
        force_rows = _collect_force_coefficients(case_dir, output)
        final_coefficients = final_force_coefficients(force_rows)
        visualizations = write_visualization_previews(output)
        archive = await asyncio.to_thread(zip_case, case_dir, output / "openfoam-case.zip")
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
            "visualizations": [path.name for path in visualizations],
            "commands": commands,
            "results": results,
            "manifest": manifest,
            "mesh_validation": mesh_validation,
            "force_coefficients": manifest.get("force_coefficients", {"enabled": False}),
            "final_coefficients": final_coefficients,
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
            {"name": "export_vtk", "command": "foamToVTK -ascii", "required": False},
        ]

    def _write_command_log(self, output_dir: Path, name: str, result: CommandResult) -> None:
        filename = {
            "surface_check": "surfaceCheck.log",
            "block_mesh": "blockMesh.log",
            "surface_features": "surfaceFeatures.log",
            "snappy_hex_mesh": "snappyHexMesh.log",
            "check_mesh": "checkMesh.log",
            "check_mesh_strict": "checkMesh-strict.log",
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


def _front_and_back_empty_command(wall_patch: str) -> str:
    script = (
        "from pathlib import Path; "
        "p=Path('constant/polyMesh/boundary'); "
        "text=p.read_text(); "
        "front='frontAndBack\\n    {\\n        type            patch;'; "
        "front_new='frontAndBack\\n    {\\n        type            empty;'; "
        f"wall='{wall_patch}\\n    {{\\n        type            patch;'; "
        f"wall_new='{wall_patch}\\n    {{\\n        type            wall;'; "
        "assert front in text, 'frontAndBack patch block with type patch was not found'; "
        f"assert wall in text, '{wall_patch} patch block with type patch was not found'; "
        "text=text.replace(front,front_new,1).replace(wall,wall_new,1); "
        "p.write_text(text); "
        f"print('{wall_patch} set to wall; frontAndBack set to empty')"
    )
    escaped = script.replace("'", "'\"'\"'")
    return f"python3 -c '{escaped}'"


def _collect_force_coefficients(case_dir: Path, output_dir: Path) -> list[dict]:
    source = _latest_force_coefficients_file(case_dir)
    if source is None:
        return []
    copied = output_dir / "forceCoeffs.dat"
    shutil.copy2(source, copied)
    rows = parse_force_coefficients(copied.read_text(errors="replace"))
    if rows:
        write_force_coefficients_csv(rows, output_dir / "forceCoeffs.csv")
    return rows


def _latest_force_coefficients_file(case_dir: Path) -> Path | None:
    candidates = [path for path in case_dir.rglob("forceCoeffs.dat") if path.is_file()]
    if not candidates:
        return None
    return sorted(candidates, key=_force_coefficients_sort_key)[-1]


def _force_coefficients_sort_key(path: Path) -> tuple[float, str]:
    try:
        time_value = float(path.parent.name)
    except ValueError:
        time_value = -1.0
    return (time_value, path.as_posix())
