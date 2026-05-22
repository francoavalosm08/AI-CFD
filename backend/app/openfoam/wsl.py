from __future__ import annotations

import asyncio
import shlex
import shutil
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.openfoam.runner_types import CommandResult


def windows_to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        return resolved.as_posix()
    parts = resolved.parts[1:]
    return "/mnt/" + drive + "/" + "/".join(parts)


def quote_bash(value: str) -> str:
    return shlex.quote(value)


def normalize_wsl_distros(output: str) -> list[str]:
    cleaned = output.replace("\x00", "")
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


def select_wsl_distro(available: list[str], requested: str) -> str | None:
    requested_lower = requested.lower()
    for distro in available:
        if distro.lower() == requested_lower:
            return distro
    if requested_lower == "ubuntu":
        for distro in available:
            if distro.lower().startswith("ubuntu"):
                return distro
    return None


def _source_target(value: str) -> str:
    if any(char in value for char in "*?[]"):
        return value
    return quote_bash(value)


def build_openfoam_source_command(bashrc: str) -> str:
    return f"set +u; source {_source_target(bashrc)} >/dev/null 2>&1 || true"


def build_wsl_bash_command(
    command: str, *, cwd: Path | None = None, bashrc: str, cwd_wsl: str | None = None
) -> str:
    if cwd_wsl is None:
        if cwd is None:
            raise ValueError("Either cwd or cwd_wsl is required")
        cwd_wsl = windows_to_wsl_path(cwd)
    case_dir = quote_bash(cwd_wsl)
    return f"{build_openfoam_source_command(bashrc)}; cd {case_dir} && {command}"


def make_wsl_command_executor(
    *,
    distro: str = "Ubuntu",
    bashrc: str = "/opt/openfoam*/etc/bashrc",
    cwd_wsl: str | None = None,
) -> Callable[[str, Path, int], Awaitable[CommandResult]]:
    async def execute(command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
        bash_command = build_wsl_bash_command(
            command,
            cwd=cwd,
            bashrc=bashrc,
            cwd_wsl=cwd_wsl,
        )
        return await run_wsl_shell_command(
            bash_command,
            distro=distro,
            timeout_seconds=timeout_seconds,
            display_command=command,
        )

    return execute


async def run_wsl_shell_command(
    command: str,
    *,
    distro: str,
    timeout_seconds: int,
    display_command: str | None = None,
) -> CommandResult:
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["wsl.exe", "-d", distro, "bash", "-lc", command],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=display_command or command,
            returncode=124,
            stdout=_normalize_completed_output(exc.stdout),
            stderr=(_normalize_completed_output(exc.stderr) + "\nCommand timed out.").strip(),
        )
    return CommandResult(
        command=display_command or command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


@dataclass
class OpenFoamPreflightResult:
    ok: bool
    checks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_wsl_preflight(
    *,
    distro: str = "Ubuntu",
    bashrc: str = "/opt/openfoam*/etc/bashrc",
    required_commands: tuple[str, ...] = ("gmshToFoam", "checkMesh", "simpleFoam"),
) -> OpenFoamPreflightResult:
    checks: list[str] = []
    errors: list[str] = []
    if not shutil.which("wsl.exe"):
        return OpenFoamPreflightResult(
            ok=False,
            errors=["wsl.exe was not found. Install WSL2 and Ubuntu before running local OpenFOAM."],
        )
    checks.append("wsl.exe found")

    distro_check = subprocess.run(
        ["wsl.exe", "-l", "-q"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    available_distros = normalize_wsl_distros(distro_check.stdout)
    selected_distro = select_wsl_distro(available_distros, distro)
    if distro_check.returncode != 0 or not selected_distro:
        available = ", ".join(available_distros) if available_distros else "none"
        errors.append(f"WSL distro '{distro}' was not found. Available distros: {available}")
        return OpenFoamPreflightResult(ok=False, checks=checks, errors=errors)
    checks.append(f"WSL distro '{selected_distro}' found")

    command_checks = " && ".join(f"command -v {command}" for command in required_commands)
    command = f"set +u; source {bashrc} >/dev/null 2>&1 || true; {command_checks}"
    result = subprocess.run(
        ["wsl.exe", "-d", selected_distro, "bash", "-lc", command],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        errors.append(
            "OpenFOAM environment is not ready. Could not source "
            f"{bashrc} and find commands: {', '.join(required_commands)}. "
            f"stderr: {result.stderr.strip()}"
        )
    else:
        checks.append("OpenFOAM commands found")
    return OpenFoamPreflightResult(ok=not errors, checks=checks, errors=errors)


def _normalize_completed_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
