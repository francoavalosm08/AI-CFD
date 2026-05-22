from __future__ import annotations

import re


RESIDUAL_RE = re.compile(
    r"Solving for (?P<field>[^,]+), Initial residual = (?P<initial>[-+0-9.eE]+), "
    r"Final residual = (?P<final>[-+0-9.eE]+), No Iterations (?P<iterations>\d+)"
)


def check_mesh_passed(output: str) -> bool:
    lowered = output.lower()
    if "failed" in lowered or " ***error" in lowered:
        return False
    return "mesh ok" in lowered


def parse_residuals(log_text: str) -> list[dict]:
    rows: list[dict] = []
    for match in RESIDUAL_RE.finditer(log_text):
        rows.append(
            {
                "field": match.group("field").strip(),
                "initial": float(match.group("initial")),
                "final": float(match.group("final")),
                "iterations": int(match.group("iterations")),
            }
        )
    return rows
