from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    data_root: Path = Path(os.environ.get("AI_CFD_DATA_ROOT", "data"))
    database_path: Path | None = None
    foam_agent_url: str = os.environ.get("FOAM_AGENT_URL", "http://foamagent:7860/mcp")
    foam_agent_mode: str = os.environ.get("FOAM_AGENT_MODE", "mcp")
    app_data_root: Path | None = None
    agent_data_root: str = os.environ.get("FOAM_AGENT_SHARED_AGENT_ROOT", "/workspace/data")
    foam_agent_agent_runs_root: str = os.environ.get(
        "FOAM_AGENT_AGENT_RUNS_ROOT", "/home/openfoam/Foam-Agent/runs"
    )
    foam_agent_app_runs_root: Path | None = None
    gmsh_command: str = os.environ.get("GMSH_COMMAND", "gmsh")

    def resolved_database_path(self) -> Path:
        return self.database_path or self.data_root / "workbench.sqlite3"

    def resolved_app_data_root(self) -> Path:
        return self.app_data_root or self.data_root

    def resolved_foam_agent_app_runs_root(self) -> Path:
        return self.foam_agent_app_runs_root or self.data_root / "foamagent-runs"
