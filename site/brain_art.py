"""Render compact, deterministic hero art from the viewers' actual atlas meshes.

This build-time illustration uses only the standard library. It reads the
already embedded geometry; it never downloads an atlas or changes its anatomy.
Both source viewers use x = posterior, y = ventral, z = lateral. The camera
looks from an oblique lateral/dorsal direction, with the anterior end at left.
"""

from __future__ import annotations

import base64
import json
import math
from pathlib import Path
import struct


_SOURCES = {
    "human": "human/outputs/whole_brain/human_brain_3d.html",
    "mouse": "mouse/outputs/P56/motor_cortex_3d.html",
}
_WIDTH, _HEIGHT = 240, 168


def _decode(encoded: str, kind: str) -> tuple:
    raw = base64.b64decode(encoded)
    return struct.unpack(f"<{len(raw) // 4}{kind}", raw)


def _unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(value * value for value in vector))
    return tuple(value / length for value in vector)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _surface(species: str, repo: Path):
    """Return a tiny orthographic depth/lighting buffer of the visible shell."""
    source = (repo / _SOURCES[species]).read_text(encoding="utf-8")
    encoded = source.split("const REGIONS =", 1)[1].lstrip()
    regions, _ = json.JSONDecoder().raw_decode(encoded)
    mesh = regions["root"]
    positions = _decode(mesh["pos_b64"], "f")
    normals = _decode(mesh["norm_b64"], "f")
    indices = _decode(mesh["idx_b64"], "I")

    # A small anterior and dorsal offset reveals the surface relief while
    # retaining the recognizable lateral silhouette of either species.
    eye = _unit((-0.28, -0.34, 0.90))
    right = _unit((eye[2], 0.0, -eye[0]))
    down = (
        eye[1] * right[2],
        eye[2] * right[0] - eye[0] * right[2],
        -eye[1] * right[0],
    )
    lamp = _unit(tuple(-0.38 * right[i] - 0.57 * down[i] + 0.73 * eye[i] for i in range(3)))
    projected = []
    for offset in range(0, len(positions), 3):
        vertex = positions[offset : offset + 3]
        normal = normals[offset : offset + 3]
        projected.append((_dot(vertex, right), _dot(vertex, down), _dot(vertex, eye),
                          0.14 + 0.86 * max(0.0, _dot(normal, lamp))))
    min_x, max_x = min(v[0] for v in projected), max(v[0] for v in projected)
    min_y, max_y = min(v[1] for v in projected), max(v[1] for v in projected)
    scale = min((_WIDTH - 24) / (max_x - min_x), (_HEIGHT - 28) / (max_y - min_y))
    center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    vertices = [((x - center_x) * scale + _WIDTH / 2,
                 (y - center_y) * scale + _HEIGHT / 2,
                 z * scale, light) for x, y, z, light in projected]
    depth = [-math.inf] * (_WIDTH * _HEIGHT)
    lighting = [0.0] * len(depth)

    for offset in range(0, len(indices), 3):
        a, b, c = (vertices[indices[offset + i]] for i in range(3))
        denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denominator) < 1e-8:
            continue
        x0 = max(0, math.ceil(min(a[0], b[0], c[0])))
        x1 = min(_WIDTH - 1, math.floor(max(a[0], b[0], c[0])))
        y0 = max(0, math.ceil(min(a[1], b[1], c[1])))
        y1 = min(_HEIGHT - 1, math.floor(max(a[1], b[1], c[1])))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                wa = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
                wb = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
                wc = 1 - wa - wb
                if min(wa, wb, wc) < -1e-5:
                    continue
                z = wa * a[2] + wb * b[2] + wc * c[2]
                pixel = y * _WIDTH + x
                if z > depth[pixel]:
                    depth[pixel] = z
                    lighting[pixel] = wa * a[3] + wb * b[3] + wc * c[3]
    return depth, lighting


def _silhouette(depth):
    """Scanline fill keeps the mesh's concavities and disconnected sections."""
    segments = []
    for y in range(_HEIGHT):
        x = 0
        while x < _WIDTH:
            if depth[y * _WIDTH + x] == -math.inf:
                x += 1
                continue
            start = x
            while x < _WIDTH and depth[y * _WIDTH + x] != -math.inf:
                x += 1
            segments.append(f"M{start * 2.5:g} {y * 2.5:g}h{(x - start) * 2.5:g}v2.5h{(start - x) * 2.5:g}z")
    return "".join(segments)


def render_brain(species: str, repo: Path) -> str:
    """Return a self-contained SVG, using ``human`` or ``mouse`` atlas data.

    ``repo`` is the repository root supplied by the site builder. Invalid
    species and missing source viewers fail explicitly during the build.
    """
    if species not in _SOURCES:
        raise ValueError(f"Unknown species: {species!r}; expected 'human' or 'mouse'")
    depth, lighting = _surface(species, Path(repo))
    groups = [[] for _ in range(14)]
    # A deterministic, irregular sampling lattice avoids moire. Depth testing
    # prevents the far hemisphere showing through the foreground surface.
    for y in range(2, _HEIGHT - 2):
        for x in range(2, _WIDTH - 2):
            pixel = y * _WIDTH + x
            if depth[pixel] == -math.inf:
                continue
            seed = (x * 73856093 ^ y * 19349663) & 0xFFFFFFFF
            seed = ((seed ^ (seed >> 13)) * 1274126177) & 0xFFFFFFFF
            if seed % 100 >= 50:
                continue
            light = lighting[pixel]
            # A small ambient-occlusion term makes the actual cortical folds
            # legible at this illustration's deliberately modest resolution.
            occlusion = 0.0
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < _WIDTH and 0 <= ny < _HEIGHT:
                    neighbor = depth[ny * _WIDTH + nx]
                    if neighbor != -math.inf:
                        occlusion += max(0.0, min(1.0, (neighbor - depth[pixel] - 1.0) / 9.0))
            level = max(0, min(13, int((light * (1 - 0.11 * occlusion)) * 13)))
            jitter_x = (((seed >> 8) & 255) / 255 - 0.5) * 0.8
            jitter_y = (((seed >> 16) & 255) / 255 - 0.5) * 0.8
            groups[level].append(f"M{(x + jitter_x) * 2.5:.1f} {(y + jitter_y) * 2.5:.1f}h.01")

    label = "人類腦圖譜的立體表面示意" if species == "human" else "成年小鼠腦圖譜的立體表面示意"
    result = [f'<svg xmlns="http://www.w3.org/2000/svg" class="brain-art" viewBox="0 0 600 420" role="img" aria-label="{label}">',
              '<title>' + label + '</title>',
              '<desc>由既有 atlas 三角網格計算的斜側面投影；點的明暗表現表面形狀，並非神經元或活性訊號。</desc>',
              f'<path d="{_silhouette(depth)}" fill="#112c2b" fill-opacity=".72"/>',
              '<g fill="none" stroke-linecap="round">']
    dark = (41, 79, 75)
    bright = (199, 226, 196) if species == "human" else (137, 219, 205)
    for level, points in enumerate(groups):
        if not points:
            continue
        fraction = level / 13
        color = "#" + "".join(f"{round(a + (b - a) * fraction):02x}" for a, b in zip(dark, bright))
        width = 0.85 + 1.3 * fraction
        result.append(f'<path d="{"".join(points)}" stroke="{color}" stroke-width="{width:.2f}"/>')
    result.append('</g></svg>')
    return "".join(result)


def _map_contour(values: list[float], threshold: float) -> str:
    """Trace a scalar buffer with marching squares, retaining holes and islands.

    Shared grid-edge keys join neighboring segments exactly. Interpolating the
    crossings gives quieter contours than outlining the raster's square pixels.
    """
    points: dict[tuple[int, int, int], tuple[float, float]] = {}
    neighbors: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    # Corner order: top-left, top-right, bottom-right, bottom-left. Edge order:
    # top, right, bottom, left. Ambiguous saddles use the actual center value.
    cases = {
        1: ((3, 0),), 2: ((0, 1),), 3: ((3, 1),), 4: ((1, 2),),
        6: ((0, 2),), 7: ((3, 2),), 8: ((2, 3),), 9: ((2, 0),),
        11: ((2, 1),), 12: ((1, 3),), 13: ((1, 0),), 14: ((0, 3),),
    }
    for y in range(_HEIGHT - 1):
        for x in range(_WIDTH - 1):
            corners = (values[y * _WIDTH + x], values[y * _WIDTH + x + 1],
                       values[(y + 1) * _WIDTH + x + 1], values[(y + 1) * _WIDTH + x])
            case = sum(1 << i for i, value in enumerate(corners) if value >= threshold)
            if case in (0, 15):
                continue
            if case in (5, 10):
                center_inside = sum(corners) / 4 >= threshold
                pairs = ((0, 1), (2, 3)) if (case == 5) == center_inside else ((3, 0), (1, 2))
            else:
                pairs = cases[case]
            edges = ((0, x, y), (1, x + 1, y), (0, x, y + 1), (1, x, y))
            for a, b in pairs:
                for edge in (a, b):
                    key = edges[edge]
                    if key not in points:
                        axis, ex, ey = key
                        start = values[ey * _WIDTH + ex]
                        end = values[(ey + axis) * _WIDTH + ex + 1 - axis]
                        fraction = (threshold - start) / (end - start)
                        points[key] = (ex + (1 - axis) * fraction, ey + axis * fraction)
                neighbors.setdefault(edges[a], []).append(edges[b])
                neighbors.setdefault(edges[b], []).append(edges[a])

    remaining = set(neighbors)
    paths = []
    # Dict insertion order makes builds reproducible without sorting the graph.
    for start in neighbors:
        if start not in remaining:
            continue
        ring = []
        previous, current = None, start
        while current in remaining:
            remaining.remove(current)
            ring.append(points[current])
            following = neighbors[current]
            next_point = following[0] if following[0] != previous else following[-1]
            previous, current = current, next_point
        if len(ring) < 3 or current != start:
            continue
        # Split the closed ring before Douglas-Peucker simplification. The
        # maximum deviation is 0.14 source pixels (0.35 SVG units), so reducing
        # file size cannot straighten a long, gently curving anatomical edge.
        split = max(range(1, len(ring)), key=lambda i:
                    (ring[i][0] - ring[0][0]) ** 2 + (ring[i][1] - ring[0][1]) ** 2)

        def simplify(line):
            keep = {0, len(line) - 1}
            pending = [(0, len(line) - 1)]
            while pending:
                begin, end = pending.pop()
                a, b = line[begin], line[end]
                dx, dy = b[0] - a[0], b[1] - a[1]
                length_squared = dx * dx + dy * dy
                farthest, largest = None, 0.14 ** 2
                for i in range(begin + 1, end):
                    point = line[i]
                    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy)
                                        / length_squared)) if length_squared else 0.0
                    distance = (point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2
                    if distance > largest:
                        farthest, largest = i, distance
                if farthest is not None:
                    keep.add(farthest)
                    pending.extend(((begin, farthest), (farthest, end)))
            return [line[i] for i in sorted(keep)]

        simplified = simplify(ring[:split + 1])[:-1] + simplify(ring[split:] + ring[:1])[:-1]
        if len(simplified) < 3:
            simplified = ring
        paths.append("M" + "L".join(f"{x * 2.5:.1f} {y * 2.5:.1f}" for x, y in simplified) + "Z")
    return "".join(paths)


def render_map_brain(species: str, repo: Path) -> str:
    """Return a quiet, shaded atlas projection for the navigation map.

    The silhouette and relief come directly from the root mesh used by the
    viewer. Uniform projection scaling preserves its aspect ratio; the fill
    bands describe surface lighting, not anatomical region boundaries.
    """
    if species not in _SOURCES:
        raise ValueError(f"Unknown species: {species!r}; expected 'human' or 'mouse'")
    depth, lighting = _surface(species, Path(repo))
    visible = [value != -math.inf for value in depth]
    silhouette = _map_contour([float(value) for value in visible], 0.5)
    relief = [-1.0] * len(depth)
    for y in range(1, _HEIGHT - 1):
        for x in range(1, _WIDTH - 1):
            pixel = y * _WIDTH + x
            if not visible[pixel]:
                continue
            # A tiny local average suppresses triangle noise while leaving the
            # depth-derived sulci in place. Missing background is never mixed
            # into the surface, so the shell edge remains anatomically derived.
            light, weight = 0.0, 0.0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (y + dy) * _WIDTH + x + dx
                    if visible[neighbor]:
                        amount = (2 if dx == 0 else 1) * (2 if dy == 0 else 1)
                        light += lighting[neighbor] * amount
                        weight += amount
            occlusion = 0.0
            for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < _WIDTH and 0 <= ny < _HEIGHT:
                    neighbor = depth[ny * _WIDTH + nx]
                    if neighbor != -math.inf:
                        occlusion += max(0.0, min(1.0, (neighbor - depth[pixel] - 1.0) / 9.0))
            relief[pixel] = light / weight * (1 - 0.10 * occlusion)

    result = ['<svg xmlns="http://www.w3.org/2000/svg" class="map-brain-art" '
              'viewBox="0 0 600 420" aria-hidden="true" focusable="false">',
              f'<path d="{silhouette}" fill="#183735" fill-rule="evenodd"/>']
    dark, bright = (28, 61, 57), (117, 152, 140)
    for level in range(9):
        fraction = level / 8
        color = "#" + "".join(f"{round(a + (b - a) * fraction):02x}" for a, b in zip(dark, bright))
        contour = _map_contour(relief, 0.19 + fraction * 0.72)
        if contour:
            result.append(f'<path d="{contour}" fill="{color}" fill-rule="evenodd"/>')
    result.append(f'<path d="{silhouette}" fill="none" stroke="#a4bfb2" '
                  'stroke-width="1.1" stroke-opacity=".45"/>')
    result.append('</svg>')
    return "".join(result)
