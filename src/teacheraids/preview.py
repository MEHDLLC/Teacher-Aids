"""A small software renderer, so every run ships a picture of what it made.

Listings need images, and a generated model nobody looked at is a model
nobody checked.  This is a plain z-buffered triangle rasteriser with flat
shading: no GPU, no display, no extra dependency, and PNG written by hand
through zlib.

Two things here differ from a general model previewer, both because classroom
aids are *sets of flat things*: parts are laid out on a plate rather than
stacked at the origin, and one of the three views looks straight down, which
for a letter tile or a clock dial is the only view that shows what it is.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import Sequence

import numpy as np

from . import plate as plate_module
from .mesh_io import Part

BACKGROUND = (250, 250, 249)
SURFACE = (232, 122, 42)         # the printed part
ACCENT = (64, 132, 176)          # every other part, so a set reads as pieces
CONTEXT = (150, 158, 168)        # things the part holds, drawn cooler and duller

Layer = tuple[np.ndarray, np.ndarray, tuple[int, int, int]]

# A flat tile seen from three-quarters is a sliver; seen from above it is a
# letter.  Not straight down, though: at 90 degrees every top face returns the
# same shade and 1.5 mm of embossed letter disappears into the tile it sits on.
# Backing off to 72 keeps the plan view readable and lets the relief show.
DEFAULT_VIEWS: Sequence[tuple[str, float, float]] = (
    ("plan", 0.0, 72.0),
    ("three-quarter", 38.0, 30.0),
    ("front", 0.0, 6.0),
)


def render_views(path: Path, part: Part, size: int = 620,
                 views: Sequence[tuple[str, float, float]] = DEFAULT_VIEWS,
                 supersample: int = 2) -> Path:
    """Render several viewpoints of one part into a contact sheet."""
    return render_scene(path, [part], size=size, views=views,
                        supersample=supersample)


def render_scene(path: Path, parts: Sequence[Part],
                 context: Sequence[Part] = (), size: int = 620,
                 views: Sequence[tuple[str, float, float]] = DEFAULT_VIEWS,
                 supersample: int = 2, spread: bool = True) -> Path:
    """Render the printed parts, optionally with the things they sit in."""
    tiles = [
        scene_pixels(parts, context, size, azimuth, elevation, supersample,
                     spread)
        for _, azimuth, elevation in views
    ]
    _write_png(path, np.concatenate(tiles, axis=1))
    return path


def scene_pixels(parts: Sequence[Part], context: Sequence[Part] = (),
                 size: int = 620, azimuth: float = 38.0,
                 elevation: float = 30.0, supersample: int = 2,
                 spread: bool = True) -> np.ndarray:
    """One rendered view as a pixel array, for callers composing their own sheet."""
    layers = _layers(parts, spread) + _layers(context, spread, (CONTEXT,))
    pixels = _render(layers, size * supersample, azimuth, elevation)
    return _downsample(pixels, supersample) if supersample > 1 else pixels


def write_sheet(path: Path, rows: Sequence[Sequence[np.ndarray]]) -> Path:
    """Stack rendered views into one contact sheet."""
    _write_png(path, np.concatenate(
        [np.concatenate(row, axis=1) for row in rows], axis=0))
    return path


def _layers(parts: Sequence[Part], spread: bool,
            palette: Sequence[tuple[int, int, int]] = (SURFACE, ACCENT),
            ) -> list[Layer]:
    """Meshes, laid out on a plate and tinted so neighbours are separable."""
    meshes = []
    for part in parts:
        verts, tris = part.mesh()
        if len(tris):
            meshes.append((part, verts - verts.min(axis=0), tris))
    if not meshes:
        return []

    if spread and len(meshes) > 1:
        sizes = []
        for _, verts, _ in meshes:
            span = verts.max(axis=0)
            sizes.append((float(span[0]), float(span[1])))
        layout = plate_module.arrange(sizes, gap=4.0, single_plate=True)
        # Rows run down the image rather than up it, so a set previews in the
        # order it is named: A at the top left, Z at the bottom right.
        depth = layout.used[1]
        placed = []
        for i, (part, verts, tris) in enumerate(meshes):
            x, y = layout.offset(i)
            placed.append(
                (part, verts + np.array([x, depth - y - sizes[i][1], 0.0]), tris))
    else:
        placed = meshes

    return [
        (verts, tris, palette[index % len(palette)])
        for index, (_, verts, tris) in enumerate(placed)
    ]


def _render(layers: Sequence[Layer], size: int,
            azimuth: float, elevation: float) -> np.ndarray:
    if not layers:
        raise ValueError("nothing to render")
    camera = _basis(azimuth, elevation)

    everything = np.concatenate([verts for verts, _, _ in layers]) @ camera.T
    screen = everything[:, :2]
    lo, hi = screen.min(axis=0), screen.max(axis=0)
    extent = max((hi - lo).max(), 1e-6)
    scale = (size * 0.88) / extent
    offset = (size / 2.0) - ((lo + hi) / 2.0) * scale

    image = np.zeros((size, size, 3), dtype=np.float32)
    image[:] = np.array(BACKGROUND, dtype=np.float32) / 255.0
    zbuffer = np.full((size, size), -np.inf, dtype=np.float32)
    light = _normalise(camera[2] * 0.75 + camera[1] * 0.5 + camera[0] * 0.3)

    # Height tint. Flat shading alone cannot show relief on a flat part: the
    # top of a 1.6 mm embossed letter and the top of the tile it sits on are
    # both facing straight up, get the same lambert term, and come out the
    # same colour -- so the letter vanishes in exactly the view that was
    # supposed to show it. Lifting the tint with world height puts it back.
    world_z = np.concatenate([verts[:, 2] for verts, _, _ in layers])
    z_low, z_high = float(world_z.min()), float(world_z.max())
    z_span = max(z_high - z_low, 1e-6)

    for verts, tris, colour in layers:
        view = verts @ camera.T                  # x right, y up, z toward camera
        px = view[:, :2] * scale + offset
        px[:, 1] = size - px[:, 1]               # image rows run downward
        depth = view[:, 2]

        corners = np.stack([px[tris[:, i]] for i in range(3)], axis=1)
        z_corners = np.stack([depth[tris[:, i]] for i in range(3)], axis=1)

        world = np.stack([verts[tris[:, i]] for i in range(3)], axis=1)
        normals = np.cross(world[:, 1] - world[:, 0], world[:, 2] - world[:, 0])
        lengths = np.linalg.norm(normals, axis=1, keepdims=True)
        normals = np.divide(normals, lengths, out=np.zeros_like(normals),
                            where=lengths > 0)
        shade = 0.30 + 0.70 * np.clip(normals @ light, 0.0, 1.0)
        height = (world[:, :, 2].mean(axis=1) - z_low) / z_span
        shade = shade * (0.86 + 0.28 * height)
        base = np.array(colour, dtype=np.float32) / 255.0

        # Signed screen-space area picks out the front faces. Written out
        # rather than np.cross because a 2-D cross product is deprecated.
        edge1 = corners[:, 1] - corners[:, 0]
        edge2 = corners[:, 2] - corners[:, 0]
        facing = edge1[:, 0] * edge2[:, 1] - edge1[:, 1] * edge2[:, 0]
        for index in np.nonzero(facing < 0)[0]:  # image rows run downward
            _raster(image, zbuffer, corners[index], z_corners[index],
                    base * shade[index])
    return np.clip(image * 255.0, 0, 255).astype(np.uint8)


def _raster(image: np.ndarray, zbuffer: np.ndarray, tri: np.ndarray,
            z: np.ndarray, colour: np.ndarray) -> None:
    size = image.shape[0]
    x_min = max(int(math.floor(tri[:, 0].min())), 0)
    x_max = min(int(math.ceil(tri[:, 0].max())) + 1, size)
    y_min = max(int(math.floor(tri[:, 1].min())), 0)
    y_max = min(int(math.ceil(tri[:, 1].max())) + 1, size)
    if x_min >= x_max or y_min >= y_max:
        return

    (x0, y0), (x1, y1), (x2, y2) = tri
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-9:
        return

    ys, xs = np.mgrid[y_min:y_max, x_min:x_max]
    xs = xs + 0.5
    ys = ys + 0.5
    w0 = ((x1 - x0) * (ys - y0) - (xs - x0) * (y1 - y0)) / area
    w1 = ((xs - x0) * (y2 - y0) - (x2 - x0) * (ys - y0)) / area
    inside = (w0 >= 0) & (w1 >= 0) & (w0 + w1 <= 1)
    if not inside.any():
        return

    depth = z[0] + w1 * (z[1] - z[0]) + w0 * (z[2] - z[0])
    window = zbuffer[y_min:y_max, x_min:x_max]
    visible = inside & (depth > window)
    if not visible.any():
        return
    window[visible] = depth[visible]
    image[y_min:y_max, x_min:x_max][visible] = colour


def _basis(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """Rows are the camera's right, up and forward axes in model space."""
    az = math.radians(azimuth_deg)
    el = math.radians(min(elevation_deg, 89.0))
    forward = _normalise(np.array([
        math.sin(az) * math.cos(el),
        -math.cos(az) * math.cos(el),
        math.sin(el),
    ]))
    right = _normalise(np.cross(np.array([0.0, 0.0, 1.0]), forward))
    up = np.cross(forward, right)
    return np.stack([right, up, forward])


def _normalise(vector: np.ndarray) -> np.ndarray:
    length = np.linalg.norm(vector)
    return vector / length if length else vector


def _downsample(pixels: np.ndarray, factor: int) -> np.ndarray:
    height, width, channels = pixels.shape
    trimmed = pixels[: height // factor * factor, : width // factor * factor]
    return (
        trimmed.reshape(height // factor, factor, width // factor, factor, channels)
        .mean(axis=(1, 3))
        .astype(np.uint8)
    )


def _write_png(path: Path, pixels: np.ndarray) -> Path:
    height, width, _ = pixels.shape
    raw = b"".join(b"\x00" + pixels[row].tobytes() for row in range(height))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(_chunk(b"IHDR",
                            struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        handle.write(_chunk(b"IDAT", zlib.compress(raw, 9)))
        handle.write(_chunk(b"IEND", b""))
    return path


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )
