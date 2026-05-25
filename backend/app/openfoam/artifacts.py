from __future__ import annotations

import csv
import shutil
import zipfile
from pathlib import Path


def write_residual_csv(rows: list[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "initial", "final", "iterations"])
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def write_force_coefficients_csv(rows: list[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "Cl", "Cd", "Cm"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "time": row["time"],
                    "Cl": row["Cl"],
                    "Cd": row["Cd"],
                    "Cm": row["Cm"],
                }
            )
    return output_path


def zip_case(case_dir: Path, archive_path: Path) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    base_name = archive_path.with_suffix("")
    created = shutil.make_archive(str(base_name), "zip", case_dir)
    return Path(created)


def write_minimal_case_archive(*, run_dir: Path, case_dir: Path, archive_path: Path) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _minimal_run_files(run_dir):
            archive.write(path, path.relative_to(run_dir).as_posix())
        for path in _minimal_case_files(case_dir):
            archive.write(path, Path("case", path.relative_to(case_dir)).as_posix())
    return archive_path


def _minimal_run_files(run_dir: Path) -> list[Path]:
    allowed_suffixes = {".json", ".log", ".csv", ".dat", ".png", ".html", ".foam"}
    return sorted(
        path
        for path in run_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in allowed_suffixes
        and path.name not in {"openfoam-case.zip", "openfoam-case-minimal.zip"}
    )


def _minimal_case_files(case_dir: Path) -> list[Path]:
    if not case_dir.exists():
        return []
    allowed_roots = {"0", "constant", "system", "postProcessing"}
    files: list[Path] = []
    for path in sorted(p for p in case_dir.rglob("*") if p.is_file()):
        try:
            root = path.relative_to(case_dir).parts[0]
        except IndexError:
            continue
        if root in allowed_roots:
            files.append(path)
    return files
