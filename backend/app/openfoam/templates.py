from __future__ import annotations


def foam_header(class_name: str, object_name: str) -> str:
    return f"""FoamFile
{{
    version     2.0;
    format      ascii;
    class       {class_name};
    object      {object_name};
}}
"""


def vector(value: tuple[float, float, float]) -> str:
    return f"({value[0]:.6f} {value[1]:.6f} {value[2]:.6f})"
