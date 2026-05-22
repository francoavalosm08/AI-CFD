from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
