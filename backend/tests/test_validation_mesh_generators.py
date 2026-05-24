from app.openfoam.naca4412 import build_naca4_geo
from app.openfoam.validation_meshes import build_box_obstacle_geo, build_cylinder_obstacle_geo


def test_cylinder_obstacle_geo_uses_external_2d_contract() -> None:
    geo = build_cylinder_obstacle_geo()

    assert 'Physical Surface("inlet")' in geo
    assert 'Physical Surface("outlet")' in geo
    assert 'Physical Surface("farfield")' in geo
    assert 'Physical Surface("obstacle")' in geo
    assert 'Physical Surface("frontAndBack")' in geo
    assert 'Physical Volume("internal")' in geo
    assert "Mesh.MshFileVersion = 2.2;" in geo
    assert "Circle(" in geo


def test_box_obstacle_geo_uses_external_2d_contract() -> None:
    geo = build_box_obstacle_geo()

    assert 'Physical Surface("inlet")' in geo
    assert 'Physical Surface("outlet")' in geo
    assert 'Physical Surface("farfield")' in geo
    assert 'Physical Surface("obstacle")' in geo
    assert 'Physical Surface("frontAndBack")' in geo
    assert 'Physical Volume("internal")' in geo
    assert "Line(" in geo


def test_naca0012_geo_remains_available_for_generated_validation_suite() -> None:
    geo = build_naca4_geo(code="0012")

    assert 'Physical Surface("airfoil")' in geo
    assert 'Physical Surface("frontAndBack")' in geo
