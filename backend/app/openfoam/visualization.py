from __future__ import annotations

import csv
import math
import struct
import zlib
from pathlib import Path


WIDTH = 900
HEIGHT = 520
MARGIN = 58


def write_visualization_previews(run_dir: Path) -> list[Path]:
    previews: list[Path] = []
    residuals = _read_residual_series(run_dir / "residuals.csv")
    if residuals:
        path = run_dir / "residuals.png"
        _write_line_plot(path, residuals, "Final residuals")
        previews.append(path)

    vtk = _find_latest_case_vtk(run_dir / "case" / "VTK")
    if vtk:
        data = _read_ascii_vtk(vtk)
        if data.points and data.velocity_magnitude:
            path = run_dir / "velocity-magnitude.png"
            _write_point_plot(path, data.points, data.velocity_magnitude, "Velocity magnitude")
            previews.append(path)
        if data.points and data.pressure:
            path = run_dir / "pressure.png"
            _write_point_plot(path, data.points, data.pressure, "Pressure")
            previews.append(path)
    return previews


def _read_residual_series(path: Path) -> dict[str, list[float]]:
    if not path.exists():
        return {}
    series: dict[str, list[float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            field = row.get("field")
            final = row.get("final")
            if not field or final is None:
                continue
            try:
                value = float(final)
            except ValueError:
                continue
            if value > 0:
                series.setdefault(field, []).append(value)
    return series


def _write_line_plot(path: Path, series: dict[str, list[float]], title: str) -> None:
    image = _canvas()
    _draw_axes(image)
    values = [value for field_values in series.values() for value in field_values]
    min_log = math.floor(math.log10(min(values)))
    max_log = math.ceil(math.log10(max(values)))
    colors = [(36, 99, 235), (220, 38, 38), (22, 163, 74), (147, 51, 234), (217, 119, 6)]
    for index, (field, field_values) in enumerate(sorted(series.items())):
        if len(field_values) == 1:
            points = [(_plot_x(0, 1), _plot_y(math.log10(field_values[0]), min_log, max_log))]
        else:
            points = [
                (_plot_x(i, len(field_values) - 1), _plot_y(math.log10(value), min_log, max_log))
                for i, value in enumerate(field_values)
            ]
        _draw_polyline(image, points, colors[index % len(colors)])
        _draw_text(image, 690, 70 + index * 18, field, colors[index % len(colors)])
    _draw_text(image, MARGIN, 26, title, (15, 23, 42))
    _draw_text(image, MARGIN, HEIGHT - 18, "solver step", (71, 85, 105))
    _draw_text(image, 12, MARGIN, "log10(final)", (71, 85, 105))
    _write_png(path, image)


def _find_latest_case_vtk(vtk_dir: Path) -> Path | None:
    if not vtk_dir.exists():
        return None
    candidates = sorted(
        (path for path in vtk_dir.glob("case_*.vtk") if path.is_file()),
        key=lambda path: _vtk_time_index(path),
    )
    return candidates[-1] if candidates else None


def _vtk_time_index(path: Path) -> int:
    try:
        return int(path.stem.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return -1


class _VtkData:
    def __init__(self) -> None:
        self.points: list[tuple[float, float]] = []
        self.velocity_magnitude: list[float] = []
        self.pressure: list[float] = []


def _read_ascii_vtk(path: Path) -> _VtkData:
    data = _VtkData()
    header = path.read_bytes()[:256].replace(b"\r\n", b"\n")
    if b"\nASCII\n" not in header:
        return data
    tokens = path.read_text(errors="replace").split()
    cursor = 0
    data_target = ""
    data_count = 0
    while cursor < len(tokens):
        token = tokens[cursor]
        if token == "POINTS" and cursor + 2 < len(tokens):
            count = int(tokens[cursor + 1])
            cursor += 3
            points: list[tuple[float, float]] = []
            for _ in range(count):
                if cursor + 2 >= len(tokens):
                    break
                points.append((float(tokens[cursor]), float(tokens[cursor + 1])))
                cursor += 3
            data.points = points
            continue
        if token in {"POINT_DATA", "CELL_DATA"} and cursor + 1 < len(tokens):
            data_target = token
            data_count = int(tokens[cursor + 1])
            cursor += 2
            continue
        if token == "FIELD" and data_target == "POINT_DATA" and cursor + 2 < len(tokens):
            array_count = int(tokens[cursor + 2])
            cursor += 3
            for _ in range(array_count):
                if cursor + 3 >= len(tokens):
                    return data
                name = tokens[cursor]
                components = int(tokens[cursor + 1])
                tuples = int(tokens[cursor + 2])
                cursor += 4
                value_count = components * tuples
                values = [float(value) for value in tokens[cursor : cursor + value_count]]
                cursor += value_count
                if tuples != data_count or tuples != len(data.points):
                    continue
                if name == "p" and components == 1:
                    data.pressure = values
                elif name == "U" and components == 3:
                    data.velocity_magnitude = [
                        math.sqrt(values[index] ** 2 + values[index + 1] ** 2 + values[index + 2] ** 2)
                        for index in range(0, len(values), 3)
                    ]
            continue
        if token == "VECTORS" and cursor + 3 < len(tokens) and tokens[cursor + 1] == "U":
            cursor += 3
            values = []
            for _ in range(len(data.points)):
                if cursor + 2 >= len(tokens):
                    break
                u, v, w = float(tokens[cursor]), float(tokens[cursor + 1]), float(tokens[cursor + 2])
                values.append(math.sqrt(u * u + v * v + w * w))
                cursor += 3
            data.velocity_magnitude = values
            continue
        if token == "SCALARS" and cursor + 2 < len(tokens) and tokens[cursor + 1] == "p":
            cursor += 4
            if cursor < len(tokens) and tokens[cursor] == "LOOKUP_TABLE":
                cursor += 2
            pressure = []
            for _ in range(len(data.points)):
                if cursor >= len(tokens):
                    break
                pressure.append(float(tokens[cursor]))
                cursor += 1
            data.pressure = pressure
            continue
        cursor += 1
    return data


def _write_point_plot(path: Path, points: list[tuple[float, float]], values: list[float], title: str) -> None:
    image = _canvas()
    if not points or not values:
        _write_png(path, image)
        return
    min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
    min_y, max_y = min(y for _, y in points), max(y for _, y in points)
    min_value, max_value = min(values), max(values)
    for (x, y), value in zip(points, values):
        px = _scale(x, min_x, max_x, MARGIN, WIDTH - MARGIN)
        py = _scale(y, min_y, max_y, HEIGHT - MARGIN, MARGIN)
        _draw_disc(image, int(px), int(py), 2, _color_ramp(value, min_value, max_value))
    _draw_axes(image)
    _draw_text(image, MARGIN, 26, title, (15, 23, 42))
    _draw_text(image, WIDTH - 210, HEIGHT - 18, f"min {min_value:.4g}  max {max_value:.4g}", (71, 85, 105))
    _write_png(path, image)


def _canvas() -> list[bytearray]:
    return [bytearray([248, 250, 252] * WIDTH) for _ in range(HEIGHT)]


def _draw_axes(image: list[bytearray]) -> None:
    _draw_line(image, MARGIN, HEIGHT - MARGIN, WIDTH - MARGIN, HEIGHT - MARGIN, (100, 116, 139))
    _draw_line(image, MARGIN, MARGIN, MARGIN, HEIGHT - MARGIN, (100, 116, 139))


def _plot_x(index: int, max_index: int) -> int:
    return int(MARGIN + index / max(max_index, 1) * (WIDTH - 2 * MARGIN))


def _plot_y(value: float, min_value: float, max_value: float) -> int:
    return int(_scale(value, min_value, max_value, HEIGHT - MARGIN, MARGIN))


def _scale(value: float, min_value: float, max_value: float, out_min: float, out_max: float) -> float:
    if max_value == min_value:
        return (out_min + out_max) / 2
    return out_min + (value - min_value) / (max_value - min_value) * (out_max - out_min)


def _draw_polyline(image: list[bytearray], points: list[tuple[int, int]], color: tuple[int, int, int]) -> None:
    for start, end in zip(points[:-1], points[1:]):
        _draw_line(image, start[0], start[1], end[0], end[1], color)
    for x, y in points:
        _draw_disc(image, x, y, 3, color)


def _draw_line(image: list[bytearray], x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _set_pixel(image, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _draw_disc(image: list[bytearray], cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                _set_pixel(image, x, y, color)


def _draw_text(image: list[bytearray], x: int, y: int, text: str, color: tuple[int, int, int]) -> None:
    for offset, character in enumerate(text[:48]):
        _draw_character(image, x + offset * 6, y, character, color)


def _draw_character(image: list[bytearray], x: int, y: int, character: str, color: tuple[int, int, int]) -> None:
    bitmap = _FONT.get(character.upper(), _FONT.get(" ", []))
    for row, bits in enumerate(bitmap):
        for col, bit in enumerate(bits):
            if bit == "1":
                _set_pixel(image, x + col, y + row, color)


def _set_pixel(image: list[bytearray], x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        offset = x * 3
        image[y][offset : offset + 3] = bytes(color)


def _color_ramp(value: float, min_value: float, max_value: float) -> tuple[int, int, int]:
    t = 0.5 if max_value == min_value else (value - min_value) / (max_value - min_value)
    t = min(1.0, max(0.0, t))
    if t < 0.5:
        local = t * 2
        return (int(37 + local * 217), int(99 + local * 105), int(235 - local * 235))
    local = (t - 0.5) * 2
    return (254, int(204 - local * 166), int(local * 38))


def _write_png(path: Path, image: list[bytearray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(b"\x00" + bytes(row) for row in image)
    payload = zlib.compress(raw, 9)
    with path.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        _write_chunk(handle, b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
        _write_chunk(handle, b"IDAT", payload)
        _write_chunk(handle, b"IEND", b"")


def _write_chunk(handle, chunk_type: bytes, payload: bytes) -> None:
    handle.write(struct.pack(">I", len(payload)))
    handle.write(chunk_type)
    handle.write(payload)
    handle.write(struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF))


_FONT = {
    " ": ["000", "000", "000", "000", "000"],
    ".": ["0", "0", "0", "0", "1"],
    "-": ["000", "000", "111", "000", "000"],
    "_": ["000", "000", "000", "000", "111"],
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "A": ["010", "101", "111", "101", "101"],
    "B": ["110", "101", "110", "101", "110"],
    "C": ["111", "100", "100", "100", "111"],
    "D": ["110", "101", "101", "101", "110"],
    "E": ["111", "100", "110", "100", "111"],
    "F": ["111", "100", "110", "100", "100"],
    "G": ["111", "100", "101", "101", "111"],
    "H": ["101", "101", "111", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "J": ["111", "001", "001", "101", "111"],
    "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"],
    "M": ["101", "111", "111", "101", "101"],
    "N": ["101", "111", "111", "111", "101"],
    "O": ["111", "101", "101", "101", "111"],
    "P": ["111", "101", "111", "100", "100"],
    "Q": ["111", "101", "101", "111", "001"],
    "R": ["111", "101", "111", "110", "101"],
    "S": ["111", "100", "111", "001", "111"],
    "T": ["111", "010", "010", "010", "010"],
    "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"],
    "W": ["101", "101", "111", "111", "101"],
    "X": ["101", "101", "010", "101", "101"],
    "Y": ["101", "101", "010", "010", "010"],
    "Z": ["111", "001", "010", "100", "111"],
}
