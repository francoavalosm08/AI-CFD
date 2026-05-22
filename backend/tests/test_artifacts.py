from pathlib import Path

from app.artifacts import discover_artifacts


def test_discover_artifacts_classifies_images_logs_plots_and_downloads(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "pressure.png").write_bytes(b"png")
    (run_dir / "residuals.csv").write_text("step,Ux\n1,0.1\n")
    (run_dir / "solver.log").write_text("Solving for Ux\n")
    (run_dir / "case.zip").write_bytes(b"zip")
    (run_dir / "report.html").write_text("<html></html>")
    (run_dir / "internal.tmp").write_text("ignore")

    artifacts = discover_artifacts("run-1", run_dir)
    by_name = {artifact.display_name: artifact for artifact in artifacts}

    assert by_name["pressure.png"].type == "image"
    assert by_name["residuals.csv"].type == "plot_data"
    assert by_name["solver.log"].type == "log"
    assert by_name["case.zip"].type == "download"
    assert by_name["report.html"].type == "other"
    assert "internal.tmp" not in by_name
