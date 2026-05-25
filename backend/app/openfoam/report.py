from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from app.openfoam.parsers import parse_check_mesh_summary


def write_run_report(
    *,
    run_dir: Path,
    output_path: Path,
    title: str,
    inputs: dict[str, str],
) -> Path:
    residual_rows = _read_residual_rows(run_dir / "residuals.csv")
    force_rows = _read_force_rows(run_dir / "forceCoeffs.csv")
    check_mesh_text = (run_dir / "checkMesh.log").read_text(errors="replace") if (run_dir / "checkMesh.log").exists() else ""
    check_mesh_summary = parse_check_mesh_summary(check_mesh_text)
    stored_check_mesh_summary = _read_json(run_dir / "checkMesh-summary.json")
    if stored_check_mesh_summary:
        check_mesh_summary = {**check_mesh_summary, **stored_check_mesh_summary}
    geometry_readiness = _read_json(run_dir / "geometry-readiness.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _html(
            title=title,
            inputs=inputs,
            residual_rows=residual_rows,
            force_rows=force_rows,
            check_mesh_text=check_mesh_text,
            check_mesh_summary=check_mesh_summary,
            geometry_readiness=geometry_readiness,
            run_dir=run_dir,
        ),
        encoding="utf-8",
    )
    return output_path


def _read_residual_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_force_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _html(
    *,
    title: str,
    inputs: dict[str, str],
    residual_rows: list[dict[str, str]],
    force_rows: list[dict[str, str]],
    check_mesh_text: str,
    check_mesh_summary: dict,
    geometry_readiness: dict,
    run_dir: Path,
) -> str:
    final_residuals: dict[str, str] = {}
    for row in residual_rows:
        final_residuals[row["field"]] = row["final"]
    image_cards = []
    for path in sorted(run_dir.glob("*.png")):
        src = html.escape(path.name, quote=True)
        image_cards.append(
            '<figure class="viz">'
            f'<img src="{src}" alt="{html.escape(path.name, quote=True)}">'
            f"<figcaption>{html.escape(path.name)}</figcaption>"
            "</figure>"
        )
    input_cards = "\n".join(
        f'<div class="card"><div class="muted">{html.escape(key)}</div><div class="metric">{html.escape(value)}</div></div>'
        for key, value in inputs.items()
    )
    residual_table = "\n".join(
        f"<tr><td>{html.escape(field)}</td><td>{html.escape(value)}</td></tr>"
        for field, value in sorted(final_residuals.items())
    )
    final_force_row = force_rows[-1] if force_rows else {}
    force_table = ""
    if final_force_row:
        force_table = "".join(
            f"<tr><td>{html.escape(name)}</td><td>{html.escape(final_force_row.get(name, ''))}</td></tr>"
            for name in ["Cl", "Cd", "Cm"]
        )
    run_quality_cards = _run_quality_cards(geometry_readiness, check_mesh_summary, final_force_row)
    readiness_recommendations = "".join(
        f"<li>{html.escape(str(item))}</li>"
        for item in geometry_readiness.get("recommendations", [])
    )
    check_lines = "\n".join(
        line
        for line in check_mesh_text.splitlines()
        if any(token in line for token in ["points:", "faces:", "cells:", "Max aspect ratio", "Mesh non-orthogonality", "Max skewness", "Mesh OK", "Failed"])
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:32px;background:#f8fafc;color:#172033}}
.wrap{{max-width:1080px;margin:auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
.card{{background:#fff;border:1px solid #dbe3ef;border-radius:8px;padding:16px;margin:14px 0}}
.metric{{font-size:24px;font-weight:700}} .muted{{color:#64748b}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #e2e8f0;text-align:left;padding:8px}}
pre{{background:#0f172a;color:#e2e8f0;border-radius:6px;padding:12px;overflow:auto}}
img{{max-width:100%;border:1px solid #dbe3ef;border-radius:6px;background:#fff}}
figure.viz{{margin:12px 0}} figcaption{{color:#64748b;margin-top:6px}}
a{{color:#075985}}
</style>
</head>
<body><div class="wrap">
<h1>{html.escape(title)}</h1>
<p class="muted">All values displayed here are parsed from generated OpenFOAM run files.</p>
<div class="grid">{input_cards}</div>
<div class="card"><h2>Run quality</h2><div class="grid">{run_quality_cards}</div><ul>{readiness_recommendations}</ul></div>
<div class="card"><h2>checkMesh summary</h2>
<p><b>Passed:</b> {html.escape(str(check_mesh_summary.get("passed")))}</p>
<p><b>Cells:</b> {html.escape(str(check_mesh_summary.get("cells")))}</p>
<pre>{html.escape(check_lines)}</pre></div>
<div class="card"><h2>Visual previews</h2>{''.join(image_cards) or '<p class="muted">No PNG previews were generated.</p>'}</div>
<div class="card"><h2>Final residuals</h2><table><tr><th>Field</th><th>Final residual</th></tr>{residual_table}</table></div>
<div class="card"><h2>Final force coefficients</h2><table><tr><th>Coefficient</th><th>Value</th></tr>{force_table}</table></div>
</div></body></html>
"""


def _run_quality_cards(geometry_readiness: dict, check_mesh_summary: dict, final_force_row: dict[str, str]) -> str:
    cards = {
        "Geometry readiness": geometry_readiness.get("status", "n/a"),
        "Repair mode": geometry_readiness.get("repair_mode", "n/a"),
        "MeshFix attempted": geometry_readiness.get("meshfix_attempted", "n/a"),
        "surfaceCheck": _pass_text(geometry_readiness.get("surface_check_passed")),
        "checkMesh": _pass_text(check_mesh_summary.get("passed", geometry_readiness.get("check_mesh_passed"))),
        "Cells": check_mesh_summary.get("cells", "n/a"),
        "Max non-orthogonality": check_mesh_summary.get("max_non_orthogonality", "n/a"),
        "Max skewness": check_mesh_summary.get("max_skewness", "n/a"),
        "Max aspect ratio": check_mesh_summary.get("max_aspect_ratio", "n/a"),
    }
    for coefficient in ["Cl", "Cd", "Cm"]:
        if coefficient in final_force_row:
            cards[coefficient] = final_force_row[coefficient]
    return "\n".join(
        f'<div class="card"><div class="muted">{html.escape(label)}</div><div class="metric">{html.escape(str(value))}</div></div>'
        for label, value in cards.items()
    )


def _pass_text(value) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "n/a"
