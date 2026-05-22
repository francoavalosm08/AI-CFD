from pathlib import Path

from app.openfoam.artifacts import write_residual_csv, zip_case


def test_write_residual_csv_creates_plot_data(tmp_path: Path) -> None:
    output = tmp_path / "residuals.csv"

    write_residual_csv(
        [{"field": "Ux", "initial": 0.1, "final": 1e-5, "iterations": 2}],
        output,
    )

    assert output.read_text().splitlines() == [
        "field,initial,final,iterations",
        "Ux,0.1,1e-05,2",
    ]


def test_zip_case_creates_archive(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "system").mkdir()
    (case_dir / "system" / "controlDict").write_text("application simpleFoam;\n")

    archive = zip_case(case_dir, tmp_path / "openfoam-case.zip")

    assert archive.exists()
    assert archive.suffix == ".zip"
