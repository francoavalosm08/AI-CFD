import pytest

from app.openfoam.naca4412 import (
    build_naca4_geo,
    build_naca4_stl,
    build_naca4412_geo,
    build_naca4412_stl,
    naca4_points,
)


def test_naca4412_geo_contains_required_airfoil_patch_names() -> None:
    geo = build_naca4412_geo()

    assert 'Physical Surface("inlet")' in geo
    assert 'Physical Surface("outlet")' in geo
    assert 'Physical Surface("farfield")' in geo
    assert 'Physical Surface("airfoil")' in geo
    assert 'Physical Surface("frontAndBack")' in geo
    assert 'Physical Volume("internal")' in geo
    assert "Transfinite Curve" in geo
    assert "Layers{1}" in geo


def test_naca4412_stl_is_generated_locally() -> None:
    stl = build_naca4412_stl()

    assert stl.startswith("solid naca4412")
    assert "facet normal" in stl
    assert "endsolid naca4412" in stl


def test_naca0012_geo_uses_same_openfoam_airfoil_patch_contract() -> None:
    geo = build_naca4_geo(code="0012")

    assert 'Physical Surface("inlet")' in geo
    assert 'Physical Surface("outlet")' in geo
    assert 'Physical Surface("farfield")' in geo
    assert 'Physical Surface("airfoil")' in geo
    assert 'Physical Surface("frontAndBack")' in geo
    assert 'Physical Volume("internal")' in geo
    assert "Mesh.MshFileVersion = 2.2;" in geo


def test_naca0012_points_are_symmetric_without_division_by_zero() -> None:
    points = naca4_points("0012", count=241)
    ys = [point[1] for point in points]

    assert len(points) == 241
    assert max(ys) > 0
    assert min(ys) < 0
    assert abs(max(ys) + min(ys)) < 0.002


def test_naca4_stl_names_generated_airfoil() -> None:
    stl = build_naca4_stl(code="0012")

    assert stl.startswith("solid naca0012")
    assert "endsolid naca0012" in stl


def test_naca4_rejects_invalid_airfoil_code() -> None:
    with pytest.raises(ValueError, match="NACA 4-digit"):
        naca4_points("12A4")
