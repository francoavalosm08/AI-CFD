from pathlib import Path

from app.openfoam.wsl import (
    build_wsl_bash_command,
    normalize_wsl_distros,
    quote_bash,
    select_wsl_distro,
    windows_to_wsl_path,
)


def test_windows_path_maps_to_wsl_path() -> None:
    path = Path("C:/Users/franc/OneDrive/Desktop/AI CFD/data/runs")

    assert (
        windows_to_wsl_path(path)
        == "/mnt/c/Users/franc/OneDrive/Desktop/AI CFD/data/runs"
    )


def test_relative_path_maps_to_wsl_path_after_resolution(tmp_path: Path) -> None:
    relative = tmp_path / "case folder"
    relative.mkdir()

    mapped = windows_to_wsl_path(relative)

    assert mapped.startswith("/mnt/")
    assert mapped.endswith("/case folder")


def test_quote_bash_handles_spaces_and_quotes() -> None:
    assert quote_bash("/mnt/c/AI CFD/case's run") == "'/mnt/c/AI CFD/case'\"'\"'s run'"


def test_build_wsl_bash_command_sources_openfoam_and_enters_case_dir(tmp_path: Path) -> None:
    case_dir = tmp_path / "case folder"

    command = build_wsl_bash_command(
        "simpleFoam",
        cwd=case_dir,
        bashrc="/opt/openfoam10/etc/bashrc",
    )

    assert command.startswith("source /opt/openfoam10/etc/bashrc")
    assert f"cd {quote_bash(windows_to_wsl_path(case_dir))}" in command
    assert command.endswith("&& simpleFoam")


def test_normalize_wsl_distros_removes_null_padding() -> None:
    raw = "U\x00b\x00u\x00n\x00t\x00u\x00-\x002\x002\x00.\x000\x004\x00\n\x00docker-desktop"

    assert normalize_wsl_distros(raw) == ["Ubuntu-22.04", "docker-desktop"]


def test_select_wsl_distro_allows_ubuntu_version_alias() -> None:
    assert select_wsl_distro(["Ubuntu-22.04", "docker-desktop"], "Ubuntu") == "Ubuntu-22.04"
    assert select_wsl_distro(["Ubuntu-22.04"], "Ubuntu-22.04") == "Ubuntu-22.04"
    assert select_wsl_distro(["Debian"], "Ubuntu") is None
