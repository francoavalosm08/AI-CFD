from __future__ import annotations


def build_cylinder_obstacle_geo(*, thickness: float = 0.01) -> str:
    return _external_obstacle_geo(
        obstacle_geometry=[
            "Point(10) = {0.00000000, 0.00000000, 0.00000000, 0.035};",
            "Point(11) = {0.50000000, 0.00000000, 0.00000000, 0.035};",
            "Point(12) = {0.00000000, 0.50000000, 0.00000000, 0.035};",
            "Point(13) = {-0.50000000, 0.00000000, 0.00000000, 0.035};",
            "Point(14) = {0.00000000, -0.50000000, 0.00000000, 0.035};",
            "Circle(11) = {11,10,12};",
            "Circle(12) = {12,10,13};",
            "Circle(13) = {13,10,14};",
            "Circle(14) = {14,10,11};",
            "Curve Loop(2) = {11,12,13,14};",
        ],
        obstacle_bbox="-0.501, -0.501, -0.001, 0.501, 0.501, 0.011",
        thickness=thickness,
    )


def build_box_obstacle_geo(*, thickness: float = 0.01) -> str:
    return _external_obstacle_geo(
        obstacle_geometry=[
            "Point(10) = {-0.45000000, -0.45000000, 0.00000000, 0.035};",
            "Point(11) = {0.45000000, -0.45000000, 0.00000000, 0.035};",
            "Point(12) = {0.45000000, 0.45000000, 0.00000000, 0.035};",
            "Point(13) = {-0.45000000, 0.45000000, 0.00000000, 0.035};",
            "Line(11) = {10,11};",
            "Line(12) = {11,12};",
            "Line(13) = {12,13};",
            "Line(14) = {13,10};",
            "Curve Loop(2) = {11,12,13,14};",
        ],
        obstacle_bbox="-0.451, -0.451, -0.001, 0.451, 0.451, 0.011",
        thickness=thickness,
    )


def _external_obstacle_geo(
    *,
    obstacle_geometry: list[str],
    obstacle_bbox: str,
    thickness: float,
) -> str:
    geo = [
        "Mesh.MshFileVersion = 2.2;",
        "Mesh.Algorithm = 6;",
        "Mesh.RecombineAll = 1;",
        "Mesh.CharacteristicLengthMin = 0.02;",
        "Mesh.CharacteristicLengthMax = 0.22;",
        "",
        'Point(1) = {-6.00000000, -3.00000000, 0.00000000, 0.22};',
        'Point(2) = {10.00000000, -3.00000000, 0.00000000, 0.22};',
        'Point(3) = {10.00000000, 3.00000000, 0.00000000, 0.22};',
        'Point(4) = {-6.00000000, 3.00000000, 0.00000000, 0.22};',
        "Line(1) = {1,2};",
        "Line(2) = {2,3};",
        "Line(3) = {3,4};",
        "Line(4) = {4,1};",
        "Curve Loop(1) = {1,2,3,4};",
        *obstacle_geometry,
        "Plane Surface(1) = {1,2};",
        "Extrude {0, 0, " + f"{thickness:.8f}" + "} { Surface{1}; Layers{1}; Recombine; }",
        "",
        'inlet[] = Surface In BoundingBox{-6.001, -3.001, -0.001, -5.999, 3.001, 0.011};',
        'outlet[] = Surface In BoundingBox{9.999, -3.001, -0.001, 10.001, 3.001, 0.011};',
        'farfield[] = Surface In BoundingBox{-6.001, -3.001, -0.001, 10.001, 3.001, 0.011};',
        "farfield[] -= inlet[];",
        "farfield[] -= outlet[];",
        f'obstacle[] = Surface In BoundingBox{{{obstacle_bbox}}};',
        'frontAndBack[] = Surface In BoundingBox{-6.001, -3.001, -0.001, 10.001, 3.001, 0.001};',
        'frontAndBack[] += Surface In BoundingBox{-6.001, -3.001, 0.009, 10.001, 3.001, 0.011};',
        'Physical Surface("inlet") = inlet[];',
        'Physical Surface("outlet") = outlet[];',
        'Physical Surface("farfield") = farfield[];',
        'Physical Surface("obstacle") = obstacle[];',
        'Physical Surface("frontAndBack") = frontAndBack[];',
        'Physical Volume("internal") = Volume{:};',
    ]
    return "\n".join(geo) + "\n"
