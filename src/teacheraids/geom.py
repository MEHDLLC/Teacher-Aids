"""Solid- and profile-geometry helpers on top of manifold3d.

manifold3d is used rather than a mesh library with bolted-on booleans because
it guarantees the result of every operation is watertight and manifold.  That
matters here: the files this repo produces are handed straight to a slicer by
a teacher who has no way to repair them.

Most classroom aids are *flat things seen from above* -- a tile, a fraction
piece, a clock dial -- so the workhorse is a 2-D profile (`Shape`) that gets
extruded up in Z.  The 2-D layer is where letterforms, patterns and rounded
corners are composed; only the last step becomes a solid.

Coordinate convention used by every generator in this package:

    +X  width   (left to right across the face of the part)
    +Y  depth   (bottom to top of the face, or front to back for uprights)
    +Z  height  (up; Z=0 is the print bed)
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import manifold3d as m3
import numpy as np

Solid = m3.Manifold
Shape = m3.CrossSection
Point2 = tuple[float, float]

EPS = 1e-6

# Curved edges are sampled finely enough that a 40 mm dial has no visible
# facets, and coarsely enough that a 26-letter set stays a few megabytes.
SEGMENTS = 64


def segments_for(radius: float, minimum: int = 12, maximum: int = 128) -> int:
    """Facet count that keeps a curve's chord error under about 0.05 mm."""
    if radius <= EPS:
        return minimum
    # chord error = r * (1 - cos(pi/n)); solve for n at 0.05 mm.
    target = max(1.0 - 0.05 / radius, -1.0)
    count = math.ceil(math.pi / math.acos(min(target, 1.0 - 1e-12)))
    return int(min(max(count, minimum), maximum))


# ---------------------------------------------------------------------------
# 2-D profiles
# ---------------------------------------------------------------------------


def rect(width: float, height: float, center: bool = True) -> Shape:
    """Axis-aligned rectangle."""
    if width <= EPS or height <= EPS:
        return empty_shape()
    return Shape.square([width, height], center)


def rounded_rect(width: float, height: float, radius: float = 0.0,
                 center: bool = True) -> Shape:
    """Rectangle with round corners, built by insetting then offsetting back.

    Done with an offset rather than four arcs so a radius larger than half the
    short side degrades into a stadium instead of into a self-intersecting
    outline.
    """
    if width <= EPS or height <= EPS:
        return empty_shape()
    radius = max(min(radius, min(width, height) / 2.0 - EPS), 0.0)
    if radius <= EPS:
        return rect(width, height, center)
    core = Shape.square([width - 2 * radius, height - 2 * radius], True)
    shape = core.offset(radius, m3.JoinType.Round, 2.0, segments_for(radius))
    return shape if center else shape.translate([width / 2.0, height / 2.0])


def circle(radius: float, segments: int = 0) -> Shape:
    if radius <= EPS:
        return empty_shape()
    return Shape.circle(radius, segments or segments_for(radius))


def ring(outer: float, inner: float, segments: int = 0) -> Shape:
    if outer <= inner + EPS:
        return empty_shape()
    return circle(outer, segments) - circle(inner, segments)


def polygon(points: Iterable[Point2]) -> Shape:
    """A closed profile from an explicit point list, wound for you."""
    return Shape([ensure_ccw(points)])


def regular_polygon(sides: int, circumradius: float,
                    rotation_deg: float = 0.0) -> Shape:
    """A regular n-gon with a vertex at `rotation_deg` from +X."""
    if sides < 3 or circumradius <= EPS:
        return empty_shape()
    start = math.radians(rotation_deg)
    return polygon([
        (circumradius * math.cos(start + 2 * math.pi * i / sides),
         circumradius * math.sin(start + 2 * math.pi * i / sides))
        for i in range(sides)
    ])


def regular_polygon_by_edge(sides: int, edge: float,
                            rotation_deg: float = 0.0) -> Shape:
    """A regular n-gon specified the way a teaching set is: by edge length."""
    if sides < 3 or edge <= EPS:
        return empty_shape()
    return regular_polygon(sides, edge / (2.0 * math.sin(math.pi / sides)),
                           rotation_deg)


def capsule(a: Point2, b: Point2, radius: float) -> Shape:
    """A round-ended bar from `a` to `b`. The unit every stroked glyph is made of."""
    if radius <= EPS:
        return empty_shape()
    segments = segments_for(radius, minimum=10, maximum=32)
    head = circle(radius, segments).translate(list(a))
    if abs(a[0] - b[0]) < EPS and abs(a[1] - b[1]) < EPS:
        return head
    tail = circle(radius, segments).translate(list(b))
    return Shape.batch_hull([head, tail])


def sector(radius: float, start_deg: float, end_deg: float,
           inner: float = 0.0) -> Shape:
    """A pie slice (or an arc band, with `inner`), swept counter-clockwise."""
    span = end_deg - start_deg
    if radius <= EPS or span <= EPS:
        return empty_shape()
    if span >= 360.0 - EPS:
        return ring(radius, inner) if inner > EPS else circle(radius)
    steps = max(2, int(segments_for(radius) * span / 360.0) + 1)
    outer_arc = [
        (radius * math.cos(math.radians(start_deg + span * i / steps)),
         radius * math.sin(math.radians(start_deg + span * i / steps)))
        for i in range(steps + 1)
    ]
    if inner <= EPS:
        return polygon([(0.0, 0.0)] + outer_arc)
    inner_arc = [
        (inner * math.cos(math.radians(start_deg + span * i / steps)),
         inner * math.sin(math.radians(start_deg + span * i / steps)))
        for i in range(steps, -1, -1)
    ]
    return polygon(outer_arc + inner_arc)


def arc_points(cx: float, cy: float, rx: float, ry: float,
               start_deg: float, end_deg: float,
               steps: int | None = None) -> list[Point2]:
    """Points along an elliptical arc, inclusive of both ends.

    Letterforms need ellipses, not circles: a capital O is 74 mm wide and
    100 mm tall on this font's body, so its bowl is an ellipse and sampling
    it as a circle would make it round and short.
    """
    span = end_deg - start_deg
    if steps is None:
        steps = max(3, int(segments_for(max(rx, ry)) * abs(span) / 360.0))
    return [
        (cx + rx * math.cos(math.radians(start_deg + span * i / steps)),
         cy + ry * math.sin(math.radians(start_deg + span * i / steps)))
        for i in range(steps + 1)
    ]


def stroke(points: Sequence[Point2], width: float) -> Shape:
    """A round-capped, round-jointed stroke following a polyline.

    Built as a union of per-segment capsules rather than by offsetting the
    polyline, because Clipper's offset of an open path is not exposed and
    faking one with an out-and-back polygon encloses zero area, which the
    fill rule discards.  A union of capsules is slower to say and impossible
    to get subtly wrong.
    """
    radius = width / 2.0
    if radius <= EPS or len(points) == 0:
        return empty_shape()
    if len(points) == 1:
        return capsule(points[0], points[0], radius)
    pieces = [capsule(points[i], points[i + 1], radius)
              for i in range(len(points) - 1)]
    return shape_union(pieces)


def shape_union(*shapes: Shape | Iterable[Shape]) -> Shape:
    parts = list(_flatten(shapes, Shape))
    if not parts:
        return empty_shape()
    return Shape.batch_boolean(parts, m3.OpType.Add)


def shape_difference(base: Shape, *cutters: Shape | Iterable[Shape]) -> Shape:
    parts = list(_flatten(cutters, Shape))
    if not parts:
        return base
    return base - shape_union(parts)


def shape_intersection(*shapes: Shape | Iterable[Shape]) -> Shape:
    parts = list(_flatten(shapes, Shape))
    if not parts:
        return empty_shape()
    return Shape.batch_boolean(parts, m3.OpType.Intersect)


def empty_shape() -> Shape:
    return Shape()


def shape_bounds(shape: Shape) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1)."""
    return tuple(shape.bounds())


def shape_size(shape: Shape) -> tuple[float, float]:
    x0, y0, x1, y1 = shape_bounds(shape)
    return (x1 - x0, y1 - y0)


# ---------------------------------------------------------------------------
# 2-D -> 3-D
# ---------------------------------------------------------------------------


def extrude(shape: Shape, height: float, at_z: float = 0.0,
            taper: float = 0.0, step: float = 0.4) -> Solid:
    """Extrude a profile up Z, optionally drafting its walls inward.

    `taper` narrows the top face by that many millimetres per side.  A raised
    letter with vertical walls prints perfectly well -- it is standing on the
    solid top of a tile, not on air -- but a drafted one loses the elephant-
    foot flare at its base, releases from a silicone mould, and feels finished
    rather than printed under a fingertip.

    The draft is built as a short stack of slices, each an honest 2-D inset of
    the one below.  manifold's own `scale_top` cannot do this job: it scales
    the whole profile about one centre, so on a glyph with several contours --
    the bowl and the tail of a `g`, the dot and the stem of an `i` -- it drags
    the pieces toward each other instead of thinning each of them, and pinches
    out slivers of negative volume where they meet.  Insetting each slice
    separately is the only version that is right for a shape that is not one
    convex blob.
    """
    if height <= EPS or shape.is_empty():
        return empty()
    if taper <= EPS:
        return shape.extrude(height).translate([0.0, 0.0, at_z])

    # An inward offset moves a profile's outer edge in and its holes out, so a
    # big enough taper closes the gap between them: the counter of a capital A
    # meets the outside of its apex and the profile pinches to a point. That
    # extrudes into a solid touching itself along an edge -- which manifold
    # accepts and every mesh checker and slicer rejects. Rather than guess a
    # safe taper from the shape, build it, check it, and back off if it is
    # wrong. Backing off costs a little draft; shipping the pinch costs a part.
    for attempt in (taper, taper * 0.5, taper * 0.25):
        solid = _stepped(shape, height, attempt, step)
        if not solid.is_empty() and edge_manifold(solid):
            return solid.translate([0.0, 0.0, at_z])
    return shape.extrude(height).translate([0.0, 0.0, at_z])


def _stepped(shape: Shape, height: float, taper: float, step: float) -> Solid:
    """A drafted extrusion as a stack of insets, each rising from the base.

    Every slice starts at the bottom rather than on top of the one below: the
    result is the same stepped shape, but the slices overlap in volume instead
    of meeting on a shared plane, and a boolean across a shared plane is the
    other place degenerate edges come from.
    """
    slices = max(2, min(8, int(math.ceil(height / max(step, 0.05)))))
    layers: list[Solid] = []
    for index in range(slices):
        z1 = height * (index + 1) / slices
        inset = taper * index / (slices - 1) if slices > 1 else 0.0
        profile = (shape if inset <= EPS
                   else shape.offset(-inset, m3.JoinType.Round, 2.0, 16))
        if profile.is_empty():
            # The profile has narrowed to nothing: the remaining slices would
            # be empty too, so this is the top of the solid.
            break
        layers.append(profile.extrude(z1))
    return union(layers) if layers else empty()


def edge_manifold(solid: Solid, weld: float = 1e-4) -> bool:
    """Is every edge shared by exactly two triangles, once vertices are welded?

    manifold3d's own validity check is about its half-edge structure and will
    happily call a solid valid when two parts of it meet along a single edge.
    Written out to a mesh and read back -- which is what a slicer does -- that
    edge belongs to four triangles and the file is not manifold. This is the
    same test `verify` runs on the bytes on disk, done in memory so a
    generator can catch it before it writes anything.
    """
    if solid.is_empty():
        return False
    mesh = solid.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    tris = np.asarray(mesh.tri_verts, dtype=np.int64)
    if len(tris) == 0:
        return False
    keys = np.round(verts / weld).astype(np.int64)
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    faces = inverse.reshape(-1)[tris]
    keep = ((faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2])
            & (faces[:, 2] != faces[:, 0]))
    faces = faces[keep]
    if len(faces) == 0:
        return False
    directed = np.concatenate(
        [faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    low, high = directed.min(axis=1), directed.max(axis=1)
    edge_key = low * (int(faces.max()) + 2) + high
    _, counts = np.unique(edge_key, return_counts=True)
    return bool((counts == 2).all())


def box(size: Sequence[float], at: Sequence[float] = (0.0, 0.0, 0.0)) -> Solid:
    """Axis-aligned box whose minimum corner sits at `at`."""
    sx, sy, sz = size
    if min(sx, sy, sz) <= 0:
        return empty()
    return Solid.cube([sx, sy, sz]).translate(list(at))


def rounded_box(size: Sequence[float], radius: float,
                at: Sequence[float] = (0.0, 0.0, 0.0)) -> Solid:
    """A box with rounded vertical edges -- the body of almost every tile."""
    sx, sy, sz = size
    if min(sx, sy, sz) <= 0:
        return empty()
    profile = rounded_rect(sx, sy, radius, center=False)
    return extrude(profile, sz).translate(list(at))


def cylinder_z(radius: float, z0: float, z1: float,
               at_xy: Point2 = (0.0, 0.0), segments: int = 0) -> Solid:
    height = z1 - z0
    if height <= EPS or radius <= EPS:
        return empty()
    solid = Solid.cylinder(height, radius, radius,
                           circular_segments=segments or segments_for(radius))
    return solid.translate([at_xy[0], at_xy[1], z0])


def cylinder_y(radius: float, y0: float, y1: float,
               at_xz: Point2 = (0.0, 0.0), segments: int = 0) -> Solid:
    """Horizontal bore along +Y -- a lanyard hole through an upright plate."""
    length = y1 - y0
    if length <= EPS or radius <= EPS:
        return empty()
    solid = Solid.cylinder(length, radius, radius,
                           circular_segments=segments or segments_for(radius))
    return solid.rotate([-90, 0, 0]).translate([at_xz[0], y0, at_xz[1]])


def cylinder_x(radius: float, x0: float, x1: float,
               at_yz: Point2 = (0.0, 0.0), segments: int = 0) -> Solid:
    length = x1 - x0
    if length <= EPS or radius <= EPS:
        return empty()
    solid = Solid.cylinder(length, radius, radius,
                           circular_segments=segments or segments_for(radius))
    return solid.rotate([0, 90, 0]).translate([x0, at_yz[0], at_yz[1]])


def cone_z(bottom_radius: float, top_radius: float, z0: float, z1: float,
           at_xy: Point2 = (0.0, 0.0), segments: int = 0) -> Solid:
    height = z1 - z0
    if height <= EPS or max(bottom_radius, top_radius) <= EPS:
        return empty()
    solid = Solid.cylinder(
        height, bottom_radius, top_radius,
        circular_segments=segments or segments_for(max(bottom_radius,
                                                       top_radius)))
    return solid.translate([at_xy[0], at_xy[1], z0])


def sphere(radius: float, at: Sequence[float] = (0.0, 0.0, 0.0),
           segments: int = 0) -> Solid:
    if radius <= EPS:
        return empty()
    return Solid.sphere(radius, segments or segments_for(radius)).translate(
        list(at))


def prism_y(profile: Iterable[Point2], y0: float, y1: float) -> Solid:
    """Extrude a closed (x, z) profile along +Y from y0 to y1."""
    length = y1 - y0
    if length <= EPS:
        return empty()
    cross = Shape([ensure_ccw(profile)])
    return cross.extrude(length).rotate([90, 0, 0]).translate([0, y1, 0])


def prism_x(profile: Iterable[Point2], x0: float, x1: float) -> Solid:
    """Extrude a closed (y, z) profile along +X from x0 to x1."""
    length = x1 - x0
    if length <= EPS:
        return empty()
    # Extruding then rotating about Y maps the profile's first coordinate to Z
    # and its second to Y, so swap the pair.  Reversing the point order at the
    # same time keeps the polygon counter-clockwise: swapping alone mirrors it,
    # and a clockwise loop reads as a hole.
    swapped = [(b, a) for (a, b) in reversed(list(profile))]
    cross = Shape([ensure_ccw(swapped)])
    return cross.extrude(length).rotate([0, -90, 0]).translate([x1, 0, 0])


def prism_z(profile: Iterable[Point2], z0: float, z1: float) -> Solid:
    height = z1 - z0
    if height <= EPS:
        return empty()
    return Shape([ensure_ccw(profile)]).extrude(height).translate([0, 0, z0])


def union(*solids: Solid | Iterable[Solid]) -> Solid:
    parts = list(_flatten(solids, Solid))
    if not parts:
        return empty()
    return Solid.batch_boolean(parts, m3.OpType.Add)


def difference(base: Solid, *cutters: Solid | Iterable[Solid]) -> Solid:
    parts = list(_flatten(cutters, Solid))
    if not parts:
        return base
    return base - union(parts)


def intersection(*solids: Solid | Iterable[Solid]) -> Solid:
    parts = list(_flatten(solids, Solid))
    if not parts:
        return empty()
    return Solid.batch_boolean(parts, m3.OpType.Intersect)


def empty() -> Solid:
    return Solid()


def bounds(solid: Solid) -> tuple[float, float, float, float, float, float]:
    """(x0, y0, z0, x1, y1, z1)."""
    return tuple(solid.bounding_box())


def size_of(solid: Solid) -> tuple[float, float, float]:
    x0, y0, z0, x1, y1, z1 = bounds(solid)
    return (x1 - x0, y1 - y0, z1 - z0)


def centre_of(solid: Solid) -> tuple[float, float, float]:
    x0, y0, z0, x1, y1, z1 = bounds(solid)
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)


def is_one_piece(solid: Solid) -> bool:
    """Does this come off the bed in one piece?

    Asserted inside generators rather than only in tests: an option that drops
    a cross member is an easy thing to add and a silent way to ship a model
    that arrives as a handful of loose fragments.
    """
    return not solid.is_empty() and len(solid.decompose()) == 1


def touches(a: Solid, b: Solid) -> bool:
    """Do two solids share any volume?"""
    return not (a ^ b).is_empty()


# ---------------------------------------------------------------------------
# profile utilities
# ---------------------------------------------------------------------------


def signed_area(profile: Iterable[Point2]) -> float:
    """Twice the signed area of a closed polygon; positive means counter-clockwise."""
    points = list(profile)
    total = 0.0
    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def ensure_ccw(profile: Iterable[Point2]) -> list[Point2]:
    """Return the polygon wound counter-clockwise.

    A clockwise loop is a *hole* to manifold's cross-section code, so extruding
    one yields an empty solid rather than an error.  That failure is silent and
    looks exactly like a part that was never added, so every helper normalises
    the winding here instead of trusting its caller.
    """
    points = dedupe([(float(x), float(y)) for x, y in profile])
    if len(points) < 3:
        raise ValueError(f"a profile needs at least 3 points, got {len(points)}")
    area = signed_area(points)
    if abs(area) < EPS:
        raise ValueError("degenerate profile: the outline encloses no area")
    return points if area > 0 else points[::-1]


def chamfered_rect(x0: float, x1: float, y0: float, y1: float,
                   chamfer: float = 0.0) -> list[Point2]:
    """A rectangle with 45-degree corners, as a point list."""
    c = max(min(chamfer, (x1 - x0) / 2.0 - EPS, (y1 - y0) / 2.0 - EPS), 0.0)
    if c <= EPS:
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return dedupe([
        (x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c),
        (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c),
    ])


def dedupe(points: Sequence[Point2]) -> list[Point2]:
    """Drop repeated points, including the wrap-around from last back to first.

    A chamfer that shrinks to nothing leaves two coincident corners. Extruding
    that gives a zero-area sliver triangle: harmless to look at, but it fails
    every mesh validator and there is no reason to ship one.
    """
    out: list[Point2] = []
    for p in points:
        if not out or abs(p[0] - out[-1][0]) > EPS or abs(p[1] - out[-1][1]) > EPS:
            out.append((float(p[0]), float(p[1])))
    while (len(out) > 1 and abs(out[0][0] - out[-1][0]) < EPS
           and abs(out[0][1] - out[-1][1]) < EPS):
        out.pop()
    return out


def _flatten(items, kind):
    for item in items:
        if isinstance(item, kind):
            if not item.is_empty():
                yield item
        elif item is None:
            continue
        else:
            yield from _flatten(item, kind)
