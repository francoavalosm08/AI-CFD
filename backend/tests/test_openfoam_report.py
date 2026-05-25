from pathlib import Path

from app.openfoam.report import write_run_report


def test_write_run_report_includes_generated_openfoam_outputs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "residuals.csv").write_text(
        "field,initial,final,iterations\nUx,1,1e-8,1\np,1,2e-8,2\n",
        encoding="utf-8",
    )
    (run_dir / "checkMesh.log").write_text("cells: 45000\nMesh OK.\n", encoding="utf-8")
    (run_dir / "solver.log").write_text("Time = 600s\nEnd\n", encoding="utf-8")
    (run_dir / "openfoam-case.zip").write_text("zip", encoding="utf-8")
    (run_dir / "openfoam-commands.json").write_text("{}", encoding="utf-8")
    (run_dir / "pressure.png").write_bytes(b"png")
    (run_dir / "forceCoeffs.csv").write_text(
        "time,Cl,Cd,Cm\n50,0.45,0.032,-0.014\n",
        encoding="utf-8",
    )
    (run_dir / "force-coefficients.png").write_bytes(b"png")

    report = write_run_report(
        run_dir=run_dir,
        output_path=tmp_path / "report.html",
        title="NACA 4412 OpenFOAM Solver Output",
        inputs={"Velocity": "25 m/s", "Angle of attack": "2 deg"},
    )

    html = report.read_text(encoding="utf-8")
    assert "NACA 4412 OpenFOAM Solver Output" in html
    assert "25 m/s" in html
    assert "2 deg" in html
    assert "Ux" in html
    assert "1e-8" in html
    assert "Mesh OK" in html
    assert "solver.log" in html
    assert "pressure.png" in html
    assert "forceCoeffs.csv" in html
    assert "force-coefficients.png" in html
    assert "0.45" in html
    assert "0.032" in html
    assert "-0.014" in html
    assert '<img src="pressure.png"' in html
    assert '<a href="pressure.png">' in html
    assert "file:///" not in html
