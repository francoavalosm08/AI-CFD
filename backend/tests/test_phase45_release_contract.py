from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_phase4_runtime_report_script_is_documented_and_reproducible() -> None:
    script = REPO_ROOT / "scripts" / "runtime-report.ps1"
    phase_summary = (REPO_ROOT / "docs" / "PHASES_SUMMARY.md").read_text(encoding="utf-8")
    runbook = (REPO_ROOT / "docs" / "LOCAL_OPENFOAM_NO_API_RUNBOOK.md").read_text(encoding="utf-8")

    text = script.read_text(encoding="utf-8")

    assert "runtime-report.json" in text
    assert "ConvertTo-Json" in text
    assert "wsl.exe" in text
    assert "gmsh" in text
    assert "simpleFoam" in text
    assert "snappyHexMesh" in text
    assert "surfaceCheck" in text
    assert "surfaceFeatures" in text
    assert "scripts\\runtime-report.ps1" in phase_summary
    assert "scripts\\runtime-report.ps1" in runbook


def test_phase5_local_v1_acceptance_script_runs_all_release_gates() -> None:
    script = REPO_ROOT / "scripts" / "release-v1-local.ps1"
    phase_summary = (REPO_ROOT / "docs" / "PHASES_SUMMARY.md").read_text(encoding="utf-8")
    roadmap = (REPO_ROOT / "docs" / "EXTERNAL_AERO_V1_ROADMAP.md").read_text(encoding="utf-8")

    text = script.read_text(encoding="utf-8")

    assert "release-check.ps1" in text
    assert "runtime-report.ps1" in text
    assert "dev-openfoam-wsl.ps1" in text
    assert "dev-openfoam-backend.ps1" in text
    assert "smoke-naca-openfoam.ps1" in text
    assert "smoke-bad-mesh-validation.ps1" in text
    assert "IncludeValidationMeshSuite" in text
    assert "smoke-validation-mesh-suite.ps1" in text
    assert "release-v1-local.ps1" in phase_summary
    assert "release-v1-local.ps1" in roadmap


def test_stl_snappy_helper_script_is_documented_for_manual_reliability_checks() -> None:
    script = REPO_ROOT / "scripts" / "generate-snappy-stl-case.ps1"
    roadmap = (REPO_ROOT / "docs" / "EXTERNAL_AERO_V1_ROADMAP.md").read_text(encoding="utf-8")
    runbook = (REPO_ROOT / "docs" / "LOCAL_OPENFOAM_NO_API_RUNBOOK.md").read_text(encoding="utf-8")

    text = script.read_text(encoding="utf-8")

    assert "build_snappy_stl_case" in text
    assert "snappyHexMesh" in text
    assert "surfaceCheck" in text
    assert "surfaceFeatures" in text
    assert "generate-snappy-stl-case.ps1" in roadmap
    assert "generate-snappy-stl-case.ps1" in runbook


def test_local_verify_cleans_up_child_server_processes_by_port() -> None:
    script = REPO_ROOT / "scripts" / "local-verify.ps1"

    text = script.read_text(encoding="utf-8")

    assert "function Stop-PortProcess" in text
    assert "Stop-PortProcess -Port $frontendPort" in text
    assert "Stop-PortProcess -Port $apiPort" in text
