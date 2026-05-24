from __future__ import annotations

import math


def _parse_naca4(code: str) -> tuple[float, float, float]:
    normalized = code.strip()
    if len(normalized) != 4 or not normalized.isdigit():
        raise ValueError("NACA 4-digit airfoil code must contain exactly 4 digits")
    return int(normalized[0]) / 100, int(normalized[1]) / 10, int(normalized[2:]) / 100


def naca4_points(
    code: str = "4412",
    *,
    count: int = 241,
    chord: float = 1.0,
) -> list[tuple[float, float, float]]:
    m, p, t = _parse_naca4(code)
    half = (count + 1) // 2
    xs = [(1 - math.cos(math.pi * i / (half - 1))) / 2 for i in range(half)]
    upper: list[tuple[float, float, float]] = []
    lower: list[tuple[float, float, float]] = []
    for x in xs:
        yt = 5 * t * (
            0.2969 * math.sqrt(max(x, 0))
            - 0.1260 * x
            - 0.3516 * x * x
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
        if m == 0 or p == 0:
            yc = 0.0
            dyc = 0.0
        elif x < p:
            yc = m / (p * p) * (2 * p * x - x * x)
            dyc = 2 * m / (p * p) * (p - x)
        else:
            yc = m / ((1 - p) ** 2) * ((1 - 2 * p) + 2 * p * x - x * x)
            dyc = 2 * m / ((1 - p) ** 2) * (p - x)
        theta = math.atan(dyc)
        upper.append(((x - yt * math.sin(theta)) * chord, (yc + yt * math.cos(theta)) * chord, 0.0))
        lower.append(((x + yt * math.sin(theta)) * chord, (yc - yt * math.cos(theta)) * chord, 0.0))
    return list(reversed(upper)) + lower[1:]


def naca4412_points(count: int = 241, chord: float = 1.0) -> list[tuple[float, float, float]]:
    return naca4_points("4412", count=count, chord=chord)


def build_naca4_geo(
    *,
    code: str = "4412",
    chord: float = 1.0,
    thickness: float = 0.01,
) -> str:
    points = naca4_points(code, chord=chord)
    geo: list[str] = [
        'SetFactory("OpenCASCADE");',
        "Mesh.MshFileVersion = 2.2;",
        "Mesh.Algorithm = 8;",
        "Mesh.RecombineAll = 1;",
        "Mesh.CharacteristicLengthMin = 0.002;",
        "Mesh.CharacteristicLengthMax = 0.085;",
        "",
        'Point(1) = {-6.00000000, -4.00000000, 0.00000000, 0.085};',
        'Point(2) = {10.00000000, -4.00000000, 0.00000000, 0.085};',
        'Point(3) = {10.00000000, 4.00000000, 0.00000000, 0.085};',
        'Point(4) = {-6.00000000, 4.00000000, 0.00000000, 0.085};',
        "Line(1) = {1,2};",
        "Line(2) = {2,3};",
        "Line(3) = {3,4};",
        "Line(4) = {4,1};",
        "Curve Loop(1) = {1,2,3,4};",
    ]
    start = 100
    for index, (x, y, z) in enumerate(points, start):
        geo.append(f"Point({index}) = {{{x:.8f}, {y:.8f}, {z:.8f}, 0.002}};")
    ids = list(range(start, start + len(points)))
    upper_end = start + (len(points) + 1) // 2 - 1
    geo.append("Spline(1000) = {" + ",".join(map(str, range(start, upper_end + 1))) + "};")
    geo.append("Spline(1001) = {" + ",".join(map(str, range(upper_end, start + len(points)))) + f",{start}" + "};")
    geo.extend(
        [
            "Curve Loop(2) = {1000,1001};",
            "Plane Surface(1) = {1,2};",
            "Transfinite Curve {1000,1001} = 241 Using Progression 1;",
            "Extrude {0, 0, " + f"{thickness:.8f}" + "} { Surface{1}; Layers{1}; Recombine; }",
            "",
            'inlet[] = Surface In BoundingBox{-6.001, -4.001, -0.001, -5.999, 4.001, 0.011};',
            'outlet[] = Surface In BoundingBox{9.999, -4.001, -0.001, 10.001, 4.001, 0.011};',
            'farfield[] = Surface In BoundingBox{-6.001, -4.001, -0.001, 10.001, 4.001, 0.011};',
            "farfield[] -= inlet[];",
            "farfield[] -= outlet[];",
            'airfoil[] = Surface In BoundingBox{-0.01, -0.25, -0.001, 1.01, 0.25, 0.011};',
            'frontAndBack[] = Surface In BoundingBox{-6.001, -4.001, -0.001, 10.001, 4.001, 0.001};',
            'frontAndBack[] += Surface In BoundingBox{-6.001, -4.001, 0.009, 10.001, 4.001, 0.011};',
            'Physical Surface("inlet") = inlet[];',
            'Physical Surface("outlet") = outlet[];',
            'Physical Surface("farfield") = farfield[];',
            'Physical Surface("airfoil") = airfoil[];',
            'Physical Surface("frontAndBack") = frontAndBack[];',
            'Physical Volume("internal") = Volume{:};',
        ]
    )
    return "\n".join(geo) + "\n"


def build_naca4412_geo(*, chord: float = 1.0, thickness: float = 0.01) -> str:
    return build_naca4_geo(code="4412", chord=chord, thickness=thickness)


def build_naca4_stl(
    *,
    code: str = "4412",
    chord: float = 1.0,
    thickness: float = 0.01,
) -> str:
    normalized = code.strip()
    points = naca4_points(normalized, chord=chord)
    name = f"naca{normalized}"
    lines = [f"solid {name}"]
    loop = points + [points[0]]
    for (x1, y1, _), (x2, y2, _) in zip(loop[:-1], loop[1:]):
        for tri in [
            ((x1, y1, 0.0), (x2, y2, 0.0), (x2, y2, thickness)),
            ((x1, y1, 0.0), (x2, y2, thickness), (x1, y1, thickness)),
        ]:
            lines.extend(["  facet normal 0 0 0", "    outer loop"])
            for x, y, z in tri:
                lines.append(f"      vertex {x:.8f} {y:.8f} {z:.8f}")
            lines.extend(["    endloop", "  endfacet"])
    lines.append(f"endsolid {name}")
    return "\n".join(lines) + "\n"


def build_naca4412_stl(*, chord: float = 1.0, thickness: float = 0.01) -> str:
    return build_naca4_stl(code="4412", chord=chord, thickness=thickness)
