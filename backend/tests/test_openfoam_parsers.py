from app.openfoam.parsers import check_mesh_passed, parse_residuals


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
