from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from app.artifacts import discover_artifacts
from app.mesh import MeshConversionError, convert_to_gmsh_mesh
from app.prompt import build_foam_agent_prompt
from app.schemas import RunRecord, RunStatus, UploadRecord


EventEmitter = Callable[[str, str, str], None]
RunPersister = Callable[[RunRecord], None]


class FoamAgentRunner:
    async def run_external_aero(
        self,
        *,
        prompt: str,
        mesh_path: str | None,
        output_dir: str,
        emit: Callable[[str, str], Awaitable[None]],
    ) -> dict:
        raise NotImplementedError


class RunExecutor:
    def __init__(
        self,
        *,
        foam_agent: FoamAgentRunner,
        app_data_root: Path,
        agent_data_root: str,
        emit: EventEmitter,
        gmsh_command: str = "gmsh",
        save_run: RunPersister | None = None,
    ) -> None:
        self.foam_agent = foam_agent
        self.app_data_root = app_data_root
        self.agent_data_root = PurePosixPath(agent_data_root)
        self.emit_event = emit
        self.gmsh_command = gmsh_command
        self.save_run = save_run

    async def execute(self, run: RunRecord, upload: UploadRecord) -> RunRecord:
        run_dir = self.app_data_root / "runs" / run.id
        run_dir.mkdir(parents=True, exist_ok=True)
        run.started_at = datetime.now(timezone.utc)

        async def emit(status: str, message: str) -> None:
            self._set_status_from_event(run, status, message)

        try:
            self._set_status(run, RunStatus.preprocessing, "Preparing uploaded geometry")
            mesh_path = await self._prepare_mesh(upload, run_dir)
            use_host_mesh_path = getattr(self.foam_agent, "mesh_path_mode", "") == "host"
            agent_mesh_path = (
                str(mesh_path) if use_host_mesh_path and mesh_path else self._to_agent_path(mesh_path) if mesh_path else None
            )
            run.prompt_used = build_foam_agent_prompt(
                run.spec, agent_visible_mesh_path=agent_mesh_path
            )

            if hasattr(self.foam_agent, "preflight"):
                await self.foam_agent.preflight(emit)

            result = await self.foam_agent.run_external_aero(
                prompt=run.prompt_used,
                mesh_path=agent_mesh_path,
                output_dir=str(run_dir),
                emit=emit,
            )
            run.summary = result
            run.artifacts = discover_artifacts(run.id, run_dir)
            run.completed_at = datetime.now(timezone.utc)
            self._set_status(run, RunStatus.completed, "Run completed")
        except MeshConversionError as exc:
            run.error = str(exc)
            run.artifacts = discover_artifacts(run.id, run_dir)
            run.completed_at = datetime.now(timezone.utc)
            self._set_status(run, RunStatus.failed, run.error)
        except Exception as exc:
            run.error = f"Simulation run failed: {exc}"
            run.artifacts = discover_artifacts(run.id, run_dir)
            run.completed_at = datetime.now(timezone.utc)
            self._set_status(run, RunStatus.failed, run.error)
        return run

    async def _prepare_mesh(self, upload: UploadRecord, run_dir: Path) -> Path | None:
        source = Path(upload.stored_path)
        if upload.kind == "gmsh_mesh":
            return source
        if upload.kind == "surface_mesh" and getattr(self.foam_agent, "accepts_surface_mesh", False):
            return source
        if upload.kind in {"surface_mesh", "cad"}:
            return await convert_to_gmsh_mesh(
                source,
                run_dir / "input.msh",
                gmsh_command=self.gmsh_command,
            )
        if upload.kind == "openfoam_case":
            return None
        raise MeshConversionError(f"Unsupported upload kind: {upload.kind}")

    def _to_agent_path(self, path: Path) -> str:
        resolved = path.resolve()
        relative = resolved.relative_to(self.app_data_root.resolve())
        return str(self.agent_data_root.joinpath(*relative.parts))

    def _set_status(self, run: RunRecord, status: RunStatus, message: str) -> None:
        run.status = status
        run.updated_at = datetime.now(timezone.utc)
        self.emit_event(run.id, status.value, message)
        if self.save_run is not None:
            self.save_run(run)

    def _set_status_from_event(self, run: RunRecord, status: str, message: str) -> None:
        try:
            run_status = RunStatus(status)
        except ValueError:
            self.emit_event(run.id, status, message)
            return
        self._set_status(run, run_status, message)
