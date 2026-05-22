from __future__ import annotations

import csv
import html
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
    check_mesh_text = (run_dir / "checkMesh.log").read_text(errors="replace") if (run_dir / "checkMesh.log").exists() else ""
    check_mesh_summary = parse_check_mesh_summary(check_mesh_text)
    solver_tail = _tail(run_dir / "solver.log", 44)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _html(
            title=title,
            inputs=inputs,
            residual_rows=residual_rows,
            check_mesh_text=check_mesh_text,
            check_mesh_summary=check_mesh_summary,
            solver_tail=solver_tail,
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


def _tail(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(errors="replace").splitlines()[-lines:])


def _html(
    *,
    title: str,
    inputs: dict[str, str],
    residual_rows: list[dict[str, str]],
    check_mesh_text: str,
    check_mesh_summary: dict,
    solver_tail: str,
    run_dir: Path,
) -> str:
    final_residuals: dict[str, str] = {}
    for row in residual_rows:
        final_residuals[row["field"]] = row["final"]
    artifact_names = [
        "pressure.png",
        "velocity-magnitude.png",
        "residuals.png",
        "solver.log",
        "checkMesh.log",
        "residuals.csv",
        "checkMesh-summary.json",
        "openfoam-commands.json",
        "openfoam-case.zip",
    ]
    artifact_links = []
    for name in artifact_names:
        path = run_dir / name
        if path.exists():
            artifact_links.append(f'<li><a href="{path.resolve().as_uri()}">{html.escape(name)}</a></li>')
    image_cards = []
    for path in sorted(run_dir.glob("*.png")):
        image_cards.append(
            '<figure class="viz">'
            f'<img src="{path.resolve().as_uri()}" alt="{html.escape(path.name)}">'
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
<div class="card"><h2>checkMesh summary</h2>
<p><b>Passed:</b> {html.escape(str(check_mesh_summary.get("passed")))}</p>
<p><b>Cells:</b> {html.escape(str(check_mesh_summary.get("cells")))}</p>
<pre>{html.escape(check_lines)}</pre></div>
<div class="card"><h2>Visual previews</h2>{''.join(image_cards) or '<p class="muted">No PNG previews were generated.</p>'}</div>
<div class="card"><h2>Final residuals</h2><table><tr><th>Field</th><th>Final residual</th></tr>{residual_table}</table></div>
<div class="card"><h2>Generated artifacts</h2><ul>{''.join(artifact_links)}</ul></div>
<div class="card"><h2>Solver log tail</h2><pre>{html.escape(solver_tail)}</pre></div>
</div></body></html>
"""
