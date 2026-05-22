from app.openfoam.naca4412 import build_naca4412_geo, build_naca4412_stl


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
