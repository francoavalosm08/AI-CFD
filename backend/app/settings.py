from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    data_root: Path = Path(os.environ.get("AI_CFD_DATA_ROOT", "data"))
    database_path: Path | None = None
    cfd_runner_mode: str = os.environ.get(
        "CFD_RUNNER_MODE", os.environ.get("FOAM_AGENT_MODE", "fake")
    )
    foam_agent_url: str = os.environ.get("FOAM_AGENT_URL", "http://127.0.0.1:7860/mcp")
    foam_agent_mode: str = os.environ.get("FOAM_AGENT_MODE", "fake")
    foam_agent_run_timeout_seconds: int = int(
        os.environ.get("FOAM_AGENT_RUN_TIMEOUT_SECONDS", "900")
    )
    openfoam_runtime: str = os.environ.get("OPENFOAM_RUNTIME", "wsl")
    openfoam_wsl_distro: str = os.environ.get("OPENFOAM_WSL_DISTRO", "Ubuntu")
    openfoam_bashrc: str = os.environ.get("OPENFOAM_BASHRC", "/opt/openfoam*/etc/bashrc")
    openfoam_run_timeout_seconds: int = int(
        os.environ.get("OPENFOAM_RUN_TIMEOUT_SECONDS", "1200")
    )
    openfoam_dry_run: bool = os.environ.get("OPENFOAM_DRY_RUN", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    openfoam_full_case_archive: bool = os.environ.get("AI_CFD_FULL_CASE_ARCHIVE", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    app_data_root: Path | None = None
    agent_data_root: str = os.environ.get("FOAM_AGENT_SHARED_AGENT_ROOT", "/workspace/data")
    foam_agent_agent_runs_root: str = os.environ.get(
        "FOAM_AGENT_AGENT_RUNS_ROOT", "/home/openfoam/Foam-Agent/runs"
    )
    foam_agent_app_runs_root: Path | None = (
        Path(os.environ["FOAM_AGENT_APP_RUNS_ROOT"])
        if os.environ.get("FOAM_AGENT_APP_RUNS_ROOT")
        else None
    )
    gmsh_command: str = os.environ.get("GMSH_COMMAND", "gmsh")

    def resolved_database_path(self) -> Path:
        return self.database_path or self.data_root / "workbench.sqlite3"

    def resolved_app_data_root(self) -> Path:
        return self.app_data_root or self.data_root

    def resolved_foam_agent_app_runs_root(self) -> Path:
        return self.foam_agent_app_runs_root or self.data_root / "foamagent-runs"
