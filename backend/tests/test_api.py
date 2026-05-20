from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def test_upload_endpoint_accepts_supported_file(tmp_path: Path):
    app = create_app(Settings(data_root=tmp_path, foam_agent_mode="fake"))
    client = TestClient(app)

    response = client.post(
        "/api/uploads",
        files={"file": ("wing.msh", b"$MeshFormat\n2.2 0 8\n", "application/octet-stream")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["original_name"] == "wing.msh"
    assert body["kind"] == "gmsh_mesh"
    assert Path(body["stored_path"]).exists()


def test_upload_endpoint_rejects_unsupported_file(tmp_path: Path):
    app = create_app(Settings(data_root=tmp_path, foam_agent_mode="fake"))
    client = TestClient(app)

    response = client.post(
        "/api/uploads",
        files={"file": ("notes.txt", b"not cfd", "text/plain")},
    )

    assert response.status_code == 400
    assert ".msh, .stl, .step, .stp, or .zip" in response.json()["detail"]


def test_create_run_endpoint_starts_background_run_and_exposes_artifacts(tmp_path: Path):
    app = create_app(Settings(data_root=tmp_path, foam_agent_mode="fake"))
    client = TestClient(app)
    upload_response = client.post(
        "/api/uploads",
        files={"file": ("wing.msh", b"$MeshFormat\n2.2 0 8\n", "application/octet-stream")},
    )
    upload_id = upload_response.json()["id"]

    response = client.post(
        "/api/runs",
        json={
            "spec": {
                "upload_id": upload_id,
                "units": "m",
                "length_scale": 1,
                "velocity": 25,
                "angle_of_attack": 4,
            }
        },
    )

    assert response.status_code == 200
    run = response.json()
    assert run["status"] in {"queued", "completed"}

    run_detail = client.get(f"/api/runs/{run['id']}").json()
    assert run_detail["spec"]["velocity"] == 25

    artifacts = client.get(f"/api/runs/{run['id']}/artifacts").json()["artifacts"]
    assert any(artifact["type"] == "image" for artifact in artifacts)
