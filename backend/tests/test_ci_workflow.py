from pathlib import Path


def test_github_actions_ci_runs_fast_release_gate() -> None:
    workflow = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"

    text = workflow.read_text(encoding="utf-8")

    assert "pull_request:" in text
    assert "push:" in text
    assert "runs-on: windows-latest" in text
    assert "actions/checkout@v5" in text
    assert "actions/setup-python@v6" in text
    assert "actions/setup-node@v6" in text
    assert "node-version: \"22\"" in text
    assert "npm --prefix frontend exec playwright install chromium" in text
    assert "npm --prefix frontend run build" in text
    assert ".\\scripts\\release-check.ps1" in text
    assert "smoke-naca-openfoam.ps1" not in text
