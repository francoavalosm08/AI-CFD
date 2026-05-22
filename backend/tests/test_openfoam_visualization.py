from pathlib import Path

from app.openfoam.visualization import _focused_point_window, write_visualization_previews


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def test_write_visualization_previews_creates_residual_png_from_csv(tmp_path: Path) -> None:
    (tmp_path / "residuals.csv").write_text(
        "field,initial,final,iterations\n"
        "Ux,1,0.1,2\n"
        "Uy,0.5,0.05,2\n"
        "Ux,0.1,0.01,2\n"
        "Uy,0.05,0.005,2\n",
        encoding="utf-8",
    )

    previews = write_visualization_previews(tmp_path)

    residual = tmp_path / "residuals.png"
    assert residual in previews
    assert _png_size(residual) == (900, 520)


def test_write_visualization_previews_creates_vtk_png_from_ascii_vtk_points(tmp_path: Path) -> None:
    vtk_dir = tmp_path / "case" / "VTK"
    vtk_dir.mkdir(parents=True)
    (vtk_dir / "case_100.vtk").write_text(
        "# vtk DataFile Version 2.0\n"
        "OpenFOAM output\n"
        "ASCII\n"
        "DATASET POLYDATA\n"
        "POINTS 4 float\n"
        "0 0 0\n1 0 0\n1 1 0\n0 1 0\n"
        "POINT_DATA 4\n"
        "VECTORS U float\n"
        "1 0 0\n2 0 0\n3 0 0\n4 0 0\n"
        "SCALARS p float 1\n"
        "LOOKUP_TABLE default\n"
        "0\n1\n2\n3\n",
        encoding="utf-8",
    )

    previews = write_visualization_previews(tmp_path)

    velocity = tmp_path / "velocity-magnitude.png"
    pressure = tmp_path / "pressure.png"
    assert velocity in previews
    assert pressure in previews
    assert _png_size(velocity) == (900, 520)
    assert _png_size(pressure) == (900, 520)


def test_write_visualization_previews_skips_binary_vtk_without_hanging(tmp_path: Path) -> None:
    vtk_dir = tmp_path / "case" / "VTK"
    vtk_dir.mkdir(parents=True)
    (vtk_dir / "case_100.vtk").write_bytes(
        b"# vtk DataFile Version 2.0\ncase\nBINARY\nDATASET UNSTRUCTURED_GRID\n" + b"\x00" * 128
    )

    previews = write_visualization_previews(tmp_path)

    assert previews == []


def test_write_visualization_previews_reads_openfoam_field_attribute_vtk(tmp_path: Path) -> None:
    vtk_dir = tmp_path / "case" / "VTK"
    vtk_dir.mkdir(parents=True)
    (vtk_dir / "case_100.vtk").write_text(
        "# vtk DataFile Version 2.0\n"
        "case\n"
        "ASCII\n"
        "DATASET UNSTRUCTURED_GRID\n"
        "POINTS 3 float\n"
        "0 0 0\n1 0 0\n0 1 0\n"
        "POINT_DATA 3\n"
        "FIELD attributes 2\n"
        "p 1 3 float\n"
        "0 2 4\n"
        "U 3 3 float\n"
        "1 0 0 0 2 0 0 0 3\n",
        encoding="utf-8",
    )

    previews = write_visualization_previews(tmp_path)

    assert tmp_path / "velocity-magnitude.png" in previews
    assert tmp_path / "pressure.png" in previews


def test_focused_point_window_crops_wide_external_domain_toward_center() -> None:
    points = [(-6, -4), (10, -4), (10, 4), (-6, 4), (0, 0), (1, 0.1)]

    bounds = _focused_point_window(points)

    min_x, max_x, min_y, max_y = bounds
    assert round(max_x - min_x, 2) == 6.08
    assert round(max_y - min_y, 2) == 3.04
    assert min_x < 0 < max_x
    assert min_y < 0 < max_y
