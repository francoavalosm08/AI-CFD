from app.openfoam.parsers import (
    check_mesh_passed,
    final_force_coefficients,
    parse_check_mesh_summary,
    parse_force_coefficients,
    parse_residuals,
)


def test_check_mesh_passed_detects_success() -> None:
    assert check_mesh_passed("Mesh OK.\nEnd\n") is True
    assert check_mesh_passed("Failed 3 mesh checks.\n") is False


def test_parse_residuals_extracts_solver_rows() -> None:
    log = """
Time = 1
Solving for Ux, Initial residual = 0.1, Final residual = 1e-05, No Iterations 2
Solving for p, Initial residual = 0.2, Final residual = 2e-05, No Iterations 3
"""

    rows = parse_residuals(log)

    assert rows == [
        {"field": "Ux", "initial": 0.1, "final": 1e-05, "iterations": 2},
        {"field": "p", "initial": 0.2, "final": 2e-05, "iterations": 3},
    ]


def test_parse_check_mesh_summary_extracts_counts_and_status() -> None:
    output = """
Mesh stats
    points:           12000
    faces:            60000
    cells:            45000
Checking geometry...
    Max aspect ratio = 45.5 OK.
    Mesh non-orthogonality Max: 62.1 average: 8.2
    Max skewness = 1.3 OK.
Mesh OK.
"""

    summary = parse_check_mesh_summary(output)

    assert summary == {
        "passed": True,
        "points": 12000,
        "faces": 60000,
        "cells": 45000,
        "max_aspect_ratio": 45.5,
        "max_non_orthogonality": 62.1,
        "average_non_orthogonality": 8.2,
        "max_skewness": 1.3,
        "failed_checks": 0,
    }


def test_parse_force_coefficients_extracts_openfoam_rows_and_final_values() -> None:
    text = """
# Time         Cm             Cd             Cl             Cl(f)          Cl(r)
0             0              0              0              0              0
50            -0.0123        0.0345         0.4567         0.22           0.23
"""

    rows = parse_force_coefficients(text)

    assert rows == [
        {"time": 0.0, "Cm": 0.0, "Cd": 0.0, "Cl": 0.0},
        {"time": 50.0, "Cm": -0.0123, "Cd": 0.0345, "Cl": 0.4567},
    ]
    assert final_force_coefficients(rows) == {"time": 50.0, "Cm": -0.0123, "Cd": 0.0345, "Cl": 0.4567}
