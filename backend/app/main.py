from __future__ import annotations

import asyncio
import shutil
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.files import UnsupportedUploadType, detect_upload_kind
from app.foam_agent import FakeFoamAgentRunner, FoamAgentMcpClient
from app.jobs import RunExecutor
from app.openfoam.runner import LocalOpenFoamRunner
from app.schemas import ArtifactListResponse, RunCreateRequest, RunRecord, RunStatus, UploadRecord
from app.settings import Settings
from app.store import Repository


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    data_root = settings.data_root
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / "uploads").mkdir(exist_ok=True)
    (data_root / "runs").mkdir(exist_ok=True)
    settings.resolved_foam_agent_app_runs_root().mkdir(parents=True, exist_ok=True)
    repo = Repository(settings.resolved_database_path())
    events: dict[str, list[tuple[str, str]]] = defaultdict(list)

    app = FastAPI(title="AI CFD Workbench", version="0.1.0")
    app.state.settings = settings
    app.state.repo = repo
    app.state.events = events

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def emit(run_id: str, status: str, message: str) -> None:
        events[run_id].append((status, message))

    def make_runner(run: RunRecord) -> RunExecutor:
        if settings.cfd_runner_mode == "fake":
            runner = FakeFoamAgentRunner()
        elif settings.cfd_runner_mode == "local_openfoam":
            runner = LocalOpenFoamRunner(
                spec=run.spec,
                dry_run=settings.openfoam_dry_run,
                runtime=settings.openfoam_runtime,
                wsl_distro=settings.openfoam_wsl_distro,
                openfoam_bashrc=settings.openfoam_bashrc,
                timeout_seconds=settings.openfoam_run_timeout_seconds,
            )
        else:
            runner = FoamAgentMcpClient(
                url=settings.foam_agent_url,
                timeout_seconds=settings.foam_agent_run_timeout_seconds,
                run_timeout_seconds=settings.foam_agent_run_timeout_seconds,
                agent_runs_root=settings.foam_agent_agent_runs_root,
                app_runs_root=settings.resolved_foam_agent_app_runs_root(),
            )
        return RunExecutor(
            foam_agent=runner,
            app_data_root=settings.resolved_app_data_root(),
            agent_data_root=settings.agent_data_root,
            emit=emit,
            gmsh_command=settings.gmsh_command,
            save_run=repo.save_run,
        )

    async def execute_run(run_id: str) -> None:
        run = repo.get_run(run_id)
        if not run or run.status == RunStatus.cancelled:
            return
        upload = repo.get_upload(run.upload_id)
        if not upload:
            run.status = RunStatus.failed
            run.error = f"Upload not found: {run.upload_id}"
            repo.save_run(run)
            return
        updated = await make_runner(run).execute(run, upload)
        repo.save_run(updated)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "foam_agent_mode": settings.cfd_runner_mode,
            "runner_mode": settings.cfd_runner_mode,
        }

    @app.post("/api/uploads", response_model=UploadRecord)
    async def upload_file(file: UploadFile = File(...)) -> UploadRecord:
        try:
            kind = detect_upload_kind(file.filename or "")
        except UnsupportedUploadType as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        upload_id = str(uuid.uuid4())
        safe_name = Path(file.filename or "upload").name
        stored_path = data_root / "uploads" / f"{upload_id}-{safe_name}"
        with stored_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)
        record = UploadRecord(
            id=upload_id,
            original_name=safe_name,
            stored_path=str(stored_path),
            kind=kind,
        )
        repo.save_upload(record)
        return record

    @app.post("/api/runs", response_model=RunRecord)
    async def create_run(request: RunCreateRequest, background_tasks: BackgroundTasks) -> RunRecord:
        upload = repo.get_upload(request.spec.upload_id)
        if not upload:
            raise HTTPException(status_code=404, detail="Upload not found")
        run = RunRecord(
            id=str(uuid.uuid4()),
            upload_id=upload.id,
            status=RunStatus.queued,
            spec=request.spec,
        )
        repo.save_run(run)
        emit(run.id, RunStatus.queued.value, "Run queued")
        background_tasks.add_task(execute_run, run.id)
        return run

    @app.get("/api/runs", response_model=list[RunRecord])
    async def list_runs() -> list[RunRecord]:
        return repo.list_runs()

    @app.get("/api/runs/{run_id}", response_model=RunRecord)
    async def get_run(run_id: str) -> RunRecord:
        run = repo.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/api/runs/{run_id}/artifacts", response_model=ArtifactListResponse)
    async def get_artifacts(run_id: str) -> ArtifactListResponse:
        run = repo.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return ArtifactListResponse(artifacts=run.artifacts)

    @app.get("/api/runs/{run_id}/events")
    async def stream_events(run_id: str) -> StreamingResponse:
        async def event_stream():
            cursor = 0
            while True:
                run = repo.get_run(run_id)
                items = events[run_id]
                while cursor < len(items):
                    status, message = items[cursor]
                    cursor += 1
                    yield f"event: status\ndata: {status}|{message}\n\n"
                if run and run.status in {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}:
                    break
                await asyncio.sleep(0.5)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/runs/{run_id}/cancel", response_model=RunRecord)
    async def cancel_run(run_id: str) -> RunRecord:
        run = repo.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.status not in {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}:
            run.status = RunStatus.cancelled
            repo.save_run(run)
            emit(run.id, RunStatus.cancelled.value, "Run cancellation requested")
        return run

    @app.get("/api/artifacts/{artifact_id}")
    async def download_artifact(artifact_id: str) -> FileResponse:
        for run in repo.list_runs():
            for artifact in run.artifacts:
                if artifact.id == artifact_id:
                    path = Path(artifact.path)
                    if not path.exists():
                        raise HTTPException(status_code=404, detail="Artifact file not found")
                    return FileResponse(path, media_type=artifact.mime_type, filename=artifact.display_name)
        raise HTTPException(status_code=404, detail="Artifact not found")

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
