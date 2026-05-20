import pytest

from app.files import UnsupportedUploadType, detect_upload_kind


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("wing.msh", "gmsh_mesh"),
        ("body.MSH", "gmsh_mesh"),
        ("fairing.stl", "surface_mesh"),
        ("airframe.step", "cad"),
        ("airframe.stp", "cad"),
        ("openfoam_case.zip", "openfoam_case"),
    ],
)
def test_detect_upload_kind_accepts_supported_formats(filename, expected):
    assert detect_upload_kind(filename) == expected


def test_detect_upload_kind_rejects_unknown_extension():
    with pytest.raises(UnsupportedUploadType) as exc:
        detect_upload_kind("notes.txt")

    assert ".msh, .stl, .step, .stp, or .zip" in str(exc.value)
