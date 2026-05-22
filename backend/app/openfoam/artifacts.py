from __future__ import annotations

import csv
import shutil
from pathlib import Path


def write_residual_csv(rows: list[dict], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "initial", "final", "iterations"])
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def zip_case(case_dir: Path, archive_path: Path) -> Path:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    base_name = archive_path.with_suffix("")
    created = shutil.make_archive(str(base_name), "zip", case_dir)
    return Path(created)
