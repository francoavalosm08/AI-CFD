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


def test_geometry_preflight_returns_stl_readiness_without_creating_run(tmp_path: Path):
    app = create_app(Settings(data_root=tmp_path, foam_agent_mode="fake"))
    client = TestClient(app)
    response = client.post(
        "/api/uploads",
        files={
            "file": (
                "body.stl",
                b"""solid tetra
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
  facet normal 0 -1 0
    outer loop
      vertex 0 0 0
      vertex 0 0 1
      vertex 1 0 0
    endloop
  endfacet
  facet normal 1 1 1
    outer loop
      vertex 1 0 0
      vertex 0 0 1
      vertex 0 1 0
    endloop
  endfacet
  facet normal -1 0 0
    outer loop
      vertex 0 0 0
      vertex 0 1 0
      vertex 0 0 1
    endloop
  endfacet
endsolid tetra
""",
                "application/octet-stream",
            )
        },
    )
    upload_id = response.json()["id"]

    preflight = client.post(f"/api/uploads/{upload_id}/geometry-preflight")

    assert preflight.status_code == 200
    body = preflight.json()
    assert body["upload_id"] == upload_id
    assert body["status"] in {"ready", "repaired_ready"}
    assert body["passed"] is True
    assert "geometry-diagnostics.json" in [artifact["display_name"] for artifact in body["artifacts"]]
    assert client.get("/api/runs").json() == []


def test_geometry_preflight_records_step_conversion_failure(tmp_path: Path):
    app = create_app(Settings(data_root=tmp_path, foam_agent_mode="fake", gmsh_command="missing-gmsh-for-test"))
    client = TestClient(app)
    response = client.post(
        "/api/uploads",
        files={"file": ("body.step", b"ISO-10303-21;\nEND-ISO-10303-21;\n", "application/octet-stream")},
    )
    upload_id = response.json()["id"]

    preflight = client.post(f"/api/uploads/{upload_id}/geometry-preflight")

    assert preflight.status_code == 200
    body = preflight.json()
    assert body["status"] == "failed_geometry"
    assert body["passed"] is False
    assert any("Gmsh" in item or "gmsh" in item for item in body["recommendations"])
    assert "step-conversion.log" in [artifact["display_name"] for artifact in body["artifacts"]]


def test_geometry_preflight_rejects_unknown_upload(tmp_path: Path):
    app = create_app(Settings(data_root=tmp_path, foam_agent_mode="fake"))
    client = TestClient(app)

    response = client.post("/api/uploads/missing/geometry-preflight")

    assert response.status_code == 404
