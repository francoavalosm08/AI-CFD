from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_download_mesh_corpus_script_records_provenance_and_classification() -> None:
    script = (REPO_ROOT / "scripts" / "download-mesh-corpus.ps1").read_text(encoding="utf-8")

    assert "people.sc.fsu.edu" in script
    assert "cylinder_2d.msh" in script
    assert "rectangle.msh" in script
    assert "step_2d.msh" in script
    assert "classify_msh_file" in script
    assert "sha256" in script


def test_generate_validation_meshes_script_creates_three_working_mesh_cases() -> None:
    script = (REPO_ROOT / "scripts" / "generate-validation-meshes.ps1").read_text(encoding="utf-8")

    assert "naca0012" in script
    assert "cylinder" in script
    assert "box" in script
    assert "build_naca4_geo" in script
    assert "build_cylinder_obstacle_geo" in script
    assert "build_box_obstacle_geo" in script
    assert "gmsh" in script


def test_local_openfoam_smoke_checks_force_outputs_for_any_enabled_case() -> None:
    script = (REPO_ROOT / "scripts" / "smoke-local-openfoam.ps1").read_text(encoding="utf-8")

    assert "forceEnabled" in script
    assert "forceCoeffs.dat" in script
    assert "force-coefficients.png" in script
    assert "final_coefficients" in script


def test_local_openfoam_smoke_can_write_structured_result_json() -> None:
    script = (REPO_ROOT / "scripts" / "smoke-local-openfoam.ps1").read_text(encoding="utf-8")

    assert "ResultPath" in script
    assert "run_id" in script
    assert "upload_id" in script
    assert "artifact_count" in script
    assert "event_count" in script
    assert "artifact_names" in script
    assert "ConvertTo-Json -Depth 20" in script


def test_validation_mesh_suite_runs_three_real_openfoam_smokes() -> None:
    script = (REPO_ROOT / "scripts" / "smoke-validation-mesh-suite.ps1").read_text(encoding="utf-8")
    runbook = (REPO_ROOT / "docs" / "LOCAL_OPENFOAM_NO_API_RUNBOOK.md").read_text(encoding="utf-8")

    assert "generate-validation-meshes.ps1" in script
    assert "dev-openfoam-backend.ps1" in script
    assert "smoke-local-openfoam.ps1" in script
    assert "cylinder.msh" in script
    assert "box.msh" in script
    assert "naca0012.msh" in script
    assert "NacaTimeoutSeconds" in script
    assert "smoke-validation-mesh-suite.ps1" in runbook


def test_validation_mesh_suite_writes_aggregate_report() -> None:
    script = (REPO_ROOT / "scripts" / "smoke-validation-mesh-suite.ps1").read_text(encoding="utf-8")
    corpus_doc = (REPO_ROOT / "docs" / "MESH_VALIDATION_CORPUS.md").read_text(encoding="utf-8")

    assert "ReportPath" in script
    assert "validation-suite-report.json" in script
    assert "-ResultPath" in script
    assert "artifact_count" in script
    assert "event_count" in script
    assert "case_type" in script
    assert "final_coefficients" in script
    assert "validation-suite-report.json" in corpus_doc
