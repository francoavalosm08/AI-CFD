from __future__ import annotations

from pathlib import Path

from app.foam_agent import FoamAgentMcpClient


def test_map_agent_path_maps_container_case_dir_to_host(tmp_path: Path) -> None:
    app_runs = tmp_path / "foamagent-runs"
    case_dir = app_runs / "case-1"
    case_dir.mkdir(parents=True)

    client = FoamAgentMcpClient(
        url="http://127.0.0.1:7860/mcp",
        app_runs_root=app_runs,
    )

    mapped = client._map_agent_path("/home/openfoam/Foam-Agent/runs/case-1")
    assert mapped == case_dir


def test_mirror_case_artifacts_copies_known_files_and_zip(tmp_path: Path) -> None:
    app_runs = tmp_path / "foamagent-runs"
    case_dir = app_runs / "case-1"
    case_dir.mkdir(parents=True)
    (case_dir / "pressure.png").write_bytes(b"png")
    (case_dir / "solver.log").write_text("done\n")
    (case_dir / "case.foam").write_text("foam\n")
    (case_dir / "field.vtk").write_text("vtk\n")

    output_dir = tmp_path / "runs" / "run-1"
    client = FoamAgentMcpClient(
        url="http://127.0.0.1:7860/mcp",
        app_runs_root=app_runs,
    )

    mirrored = client._mirror_case_artifacts(
        case_dir="/home/openfoam/Foam-Agent/runs/case-1",
        output_dir=output_dir,
        explicit_paths=[],
    )

    assert (output_dir / "pressure.png").exists()
    assert (output_dir / "solver.log").exists()
    assert (output_dir / "case.foam").exists()
    assert (output_dir / "field.vtk").exists()
    assert (output_dir / "openfoam-case.zip").exists()
    assert len(mirrored) >= 5


def test_mirror_case_artifacts_tolerates_missing_visualizations(tmp_path: Path) -> None:
    app_runs = tmp_path / "foamagent-runs"
    case_dir = app_runs / "case-2"
    case_dir.mkdir(parents=True)
    (case_dir / "solver.log").write_text("solver finished\n")

    output_dir = tmp_path / "runs" / "run-2"
    client = FoamAgentMcpClient(
        url="http://127.0.0.1:7860/mcp",
        app_runs_root=app_runs,
    )

    mirrored = client._mirror_case_artifacts(
        case_dir="/home/openfoam/Foam-Agent/runs/case-2",
        output_dir=output_dir,
        explicit_paths=["/home/openfoam/Foam-Agent/runs/case-2/missing.png"],
    )

    assert (output_dir / "solver.log").exists()
    assert (output_dir / "openfoam-case.zip").exists()
    assert mirrored
