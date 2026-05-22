from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_settings_default_to_fake_runner_mode() -> None:
    settings = Settings()

    assert settings.cfd_runner_mode == "fake"
    assert settings.foam_agent_mode == "fake"


def test_settings_accept_local_openfoam_mode() -> None:
    settings = Settings(cfd_runner_mode="local_openfoam")

    assert settings.cfd_runner_mode == "local_openfoam"
    assert settings.openfoam_runtime == "wsl"
    assert settings.openfoam_run_timeout_seconds == 1200


def test_health_reports_runner_mode(tmp_path: Path) -> None:
    app = create_app(Settings(data_root=tmp_path, cfd_runner_mode="local_openfoam"))
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["runner_mode"] == "local_openfoam"
    assert response.json()["foam_agent_mode"] == "local_openfoam"
