"""Bake trimesh geometry into the base64 vertex/index/normal blobs the
project's self-contained 3D viewers embed directly in their HTML (see the
`REGIONS` object in outputs/human/limbic/human_limbic_3d.html or the
`regions_js_parts` loop in build/demba_p15_3d.py).
"""

import base64


def f32_b64(arr):
    return base64.b64encode(arr.astype("<f4").tobytes()).decode("ascii")


def u32_b64(arr):
    return base64.b64encode(arr.astype("<u4").tobytes()).decode("ascii")


def mesh_to_region_js(acronym, mesh, color):
    """Return one `"ACR":{...}` fragment for a REGIONS JS object literal."""
    pos_b64 = f32_b64(mesh.vertices.reshape(-1))
    idx_b64 = u32_b64(mesh.faces.reshape(-1))
    norm_b64 = f32_b64(mesh.vertex_normals.reshape(-1))
    return f'"{acronym}":{{"color":"{color}","pos_b64":"{pos_b64}","idx_b64":"{idx_b64}","norm_b64":"{norm_b64}"}}'
