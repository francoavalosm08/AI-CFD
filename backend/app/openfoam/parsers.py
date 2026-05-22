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


def parse_check_mesh_summary(output: str) -> dict:
    failed_match = re.search(r"Failed\s+(?P<count>\d+)\s+mesh checks", output)
    return {
        "passed": check_mesh_passed(output),
        "points": _first_int(output, r"^\s*points:\s+(\d+)"),
        "faces": _first_int(output, r"^\s*faces:\s+(\d+)"),
        "cells": _first_int(output, r"^\s*cells:\s+(\d+)"),
        "max_aspect_ratio": _first_float(output, r"Max aspect ratio\s*=\s*([-+0-9.eE]+)"),
        "max_non_orthogonality": _first_float(output, r"Mesh non-orthogonality Max:\s*([-+0-9.eE]+)"),
        "average_non_orthogonality": _first_float(
            output, r"Mesh non-orthogonality Max:\s*[-+0-9.eE]+\s+average:\s*([-+0-9.eE]+)"
        ),
        "max_skewness": _first_float(output, r"Max skewness\s*=\s*([-+0-9.eE]+)"),
        "failed_checks": int(failed_match.group("count")) if failed_match else 0,
    }


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


def parse_force_coefficients(text: str) -> list[dict]:
    header: list[str] = []
    rows: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            candidate = stripped.lstrip("#").split()
            if "Time" in candidate and {"Cm", "Cd", "Cl"}.issubset(candidate):
                header = candidate
            continue
        if not header:
            continue
        values = stripped.split()
        if len(values) < len(header):
            continue
        parsed = _force_row(header, values)
        if parsed:
            rows.append(parsed)
    return rows


def final_force_coefficients(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    final = rows[-1]
    return {
        "time": final["time"],
        "Cm": final["Cm"],
        "Cd": final["Cd"],
        "Cl": final["Cl"],
    }


def _force_row(header: list[str], values: list[str]) -> dict | None:
    by_name = dict(zip(header, values, strict=False))
    try:
        return {
            "time": float(by_name["Time"]),
            "Cm": float(by_name["Cm"]),
            "Cd": float(by_name["Cd"]),
            "Cl": float(by_name["Cl"]),
        }
    except (KeyError, ValueError):
        return None


def _first_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text, re.MULTILINE)
    return int(match.group(1)) if match else None


def _first_float(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.MULTILINE)
    return float(match.group(1)) if match else None
