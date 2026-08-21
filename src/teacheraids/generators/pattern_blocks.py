"""The standard six pattern blocks.

These are not six shapes that happen to be in a box together: they are six
shapes that tile against each other, and every relationship in the set comes
from their sharing one edge length.  Two green triangles make a blue rhombus;
three make the red trapezoid; six make the yellow hexagon.  Change the edge
and they all still tile.  Give any one of them an edge of its own and the set
is scrap, so `edge` is a single option and no shape may override it.

The one shape that does not share the edge is the trapezoid's long side, which
is two edges by construction -- it is half a hexagon.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, presets
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

# name -> (traditional colour, how many green triangles it is worth)
SHAPES: dict[str, tuple[str, float]] = {
    "hexagon": ("yellow", 6.0),
    "trapezoid": ("red", 3.0),
    "rhombus-60": ("blue", 2.0),
    "triangle": ("green", 1.0),
    "square": ("orange", 0.0),      # does not tile with the triangles
    "rhombus-30": ("tan", 0.0),     # nor does this one
}

OPTIONS = OptionSet([
    Option("shapes", "hexagon,trapezoid,rhombus-60,triangle,square,rhombus-30",
           "Which shapes to build, comma separated", kind="str",
           group="Content"),
    Option("quantity", 6, "How many of each shape to place on the plate",
           kind="int", minimum=1, maximum=40, group="Content"),

    Option("edge", presets.PATTERN_BLOCK_EDGE,
           "The edge every shape shares. One inch is what commercial sets "
           "use, so a printed set mixes with the one already in the cupboard",
           unit=" mm", minimum=10.0, maximum=80.0, group="Size"),
    Option("thickness", presets.PATTERN_BLOCK_THICKNESS,
           "Block thickness", unit=" mm", minimum=2.0, maximum=25.0,
           group="Size"),
    Option("kerf", 0.25,
           "Taken off every edge, so printed blocks tile without gaps opening "
           "up across a pattern", unit=" mm", minimum=0.0, maximum=1.0,
           group="Fit"),
    Option("corner_relief", 0.6,
           "Round every corner by this much. A printed sharp corner is the "
           "first thing to chip, and a rounded one still tiles",
           unit=" mm", minimum=0.0, maximum=3.0, group="Fit"),
    Option("stack_dimple", False,
           "Sink a shallow dimple in the top and a matching stud below, so a "
           "tower of blocks does not slide apart",
           kind="bool", group="Detail"),
    common.material_option(),
])


class PatternBlocksGenerator(Generator):
    key = "pattern-blocks"
    category = "math"
    title = "Pattern blocks"
    summary = (
        "The classic six-shape tiling set -- hexagon, trapezoid, two rhombi, "
        "triangle and square -- all built from one shared edge, so they tile "
        "against each other and against the set already in the cupboard."
    )
    tags = ("pattern blocks", "geometry", "math", "manipulative", "tiling",
            "tessellation", "classroom", "teaching aid", "parametric")
    ages = "4-11"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        wanted = _parse_shapes(opt["shapes"])
        edge = opt["edge"]
        kerf = opt["kerf"]

        common.check_features(report, opt["thickness"], 0.0, edge)
        if opt["thickness"] > edge * 0.6:
            report.warn(
                f"a {opt['thickness']:.0f} mm block on a {edge:.0f} mm edge is "
                "closer to a brick than a tile, and stands on its side when "
                "you want it flat."
            )

        parts = PartSet()
        for name in wanted:
            profile = _profile(name, edge, kerf, opt["corner_relief"])
            solid = geom.extrude(profile, opt["thickness"])
            if opt["stack_dimple"]:
                solid = self._dimple(solid, profile, opt)
            colour, worth = SHAPES[name]
            note = f"traditionally {colour}"
            if worth:
                note += (f"; {worth:g} green triangle"
                         + ("s" if worth != 1 else ""))
            parts.add(f"{name}_{colour}", solid, note=note,
                      copies=opt["quantity"])

        common.check_small_parts(report, parts)
        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": parts.total_copies,
                "shapes": ", ".join(wanted),
                "edge_mm": edge,
                "piece_mm": list(parts.parts[0].size),
                "kerf_mm": kerf,
                "fit_source": (
                    f"Built on a {edge:.1f} mm shared edge and a "
                    f"{opt['thickness']:.1f} mm thickness. Commercial sets use "
                    "a one-inch edge (25.4 mm) and a quarter-inch thickness, "
                    "which is what this defaults to, so a printed set mixes "
                    "with a bought one."
                ),
                "fit_confidence": "published",
                "supports": "none",
            },
            highlights=[
                f"All {len(wanted)} shapes on one {edge:.1f} mm edge, so they "
                "tile: two triangles make the blue rhombus, three make the "
                "trapezoid, six make the hexagon.",
                f"{opt['quantity']} of each, {parts.total_copies} blocks in "
                "total.",
                f"Every edge is pulled in {kerf:.2f} mm and every corner "
                f"rounded {opt['corner_relief']:.1f} mm, so a pattern laid out "
                "across a table does not creep.",
                "Matches a bought set at the default one-inch edge."
                if abs(edge - presets.PATTERN_BLOCK_EDGE) < 0.05 else
                f"A {edge:.0f} mm edge, which is not the commercial inch: this "
                "set tiles with itself but not with a bought one.",
            ],
            teaching_notes=[
                "Fractions without the notation: the trapezoid is half the "
                "hexagon, the blue rhombus a third, the triangle a sixth.",
                "Symmetry and tessellation: fill a shape outline every way it "
                "can be filled, then count the ways.",
                "Angles: six triangles round a point is 360 degrees, so one "
                "is 60. The square is the odd one out and that is worth "
                "noticing.",
            ],
            print_notes=[
                "Flat on the bed, no supports.",
                "One colour per shape, as the traditional set does: "
                + ", ".join(f"{n} {SHAPES[n][0]}" for n in wanted) + ".",
                "0.2 mm layers, 3 perimeters, 20% infill. They get poured out "
                "of a tub and swept back into it.",
                "Print one of each first and check they tile before "
                "committing to the whole set; that is what `kerf` is for.",
            ],
        )

    def _dimple(self, solid, profile, opt):
        """A shallow cone down into the top and a matching one proud below."""
        size = min(opt["edge"] * 0.18, opt["thickness"] * 0.8)
        depth = min(opt["thickness"] * 0.3, 1.2)
        x0, y0, x1, y1 = geom.shape_bounds(profile)
        # Not the bounding-box centre: on a trapezoid that is outside the
        # narrow end. The centroid of the profile's own area is inside every
        # convex shape in this set.
        at = _centroid(profile)
        top = geom.cone_z(size, size * 0.6, opt["thickness"] - depth,
                          opt["thickness"] + 0.01, at)
        stud = geom.cone_z(size * 0.94, size * 0.56, -depth + 0.01, 0.0, at)
        return geom.union([geom.difference(solid, top), stud])

    def slug(self, opt: dict[str, Any]) -> str:
        return f"pattern-blocks_{opt['edge']:g}mm_{opt['quantity']}each"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        return (f"Pattern blocks - {result.facts['pieces']} blocks on a "
                f"{opt['edge']:.1f} mm edge")


def _profile(name: str, edge: float, kerf: float, relief: float):
    """One shape's outline, already shrunk by the kerf and corner-relieved.

    The kerf is applied as a negative offset of the finished outline rather
    than by shortening each edge by hand: that keeps every interior angle
    exactly what it should be, which is what makes the shapes tile.
    """
    if name == "square":
        raw = geom.rect(edge, edge)
    elif name == "triangle":
        raw = geom.regular_polygon_by_edge(3, edge, rotation_deg=90.0)
    elif name == "hexagon":
        raw = geom.regular_polygon_by_edge(6, edge)
    elif name == "rhombus-60":
        raw = _rhombus(edge, 60.0)
    elif name == "rhombus-30":
        raw = _rhombus(edge, 30.0)
    elif name == "trapezoid":
        # Half a hexagon, cut across its long diagonal: three sides of `edge`
        # and one of `2 * edge`, with 60 and 120 degree corners.
        height = edge * math.sqrt(3.0) / 2.0
        raw = geom.polygon([
            (-edge, -height / 2.0), (edge, -height / 2.0),
            (edge / 2.0, height / 2.0), (-edge / 2.0, height / 2.0),
        ])
    else:  # pragma: no cover - guarded by _parse_shapes
        raise ValueError(name)

    shrunk = raw.offset(-kerf / 2.0, text_join(), 2.0, 24) if kerf > 0 else raw
    if shrunk.is_empty():
        raise ValueError(
            f"kerf {kerf:.2f} mm swallows the {name} at a {edge:.0f} mm edge")
    if relief <= 0:
        return shrunk
    # Round the corners by insetting and offsetting back, which leaves the
    # straight edges exactly where they were.
    return shrunk.offset(-relief, text_join(), 2.0, 24).offset(
        relief, text_join(), 2.0, 24)


def text_join():
    import manifold3d as m3
    return m3.JoinType.Round


def _rhombus(edge: float, acute_deg: float):
    angle = math.radians(acute_deg)
    dx = edge * math.cos(angle)
    dy = edge * math.sin(angle)
    return geom.polygon([
        (0.0, 0.0), (edge, 0.0), (edge + dx, dy), (dx, dy),
    ]).translate([-(edge + dx) / 2.0, -dy / 2.0])


def _centroid(profile) -> tuple[float, float]:
    contours = profile.to_polygons()
    if not contours:
        return (0.0, 0.0)
    points = [(float(x), float(y)) for x, y in contours[0]]
    area = geom.signed_area(points)
    if abs(area) < 1e-9:
        return (0.0, 0.0)
    cx = cy = 0.0
    for index, (x0, y0) in enumerate(points):
        x1, y1 = points[(index + 1) % len(points)]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return (cx / (6.0 * area), cy / (6.0 * area))


def _parse_shapes(raw: str) -> list[str]:
    wanted = [c.strip().lower() for c in str(raw).split(",") if c.strip()]
    unknown = [c for c in wanted if c not in SHAPES]
    if unknown:
        raise ValueError(
            "shapes: " + ", ".join(unknown) + " is not one of "
            + ", ".join(SHAPES)
        )
    if not wanted:
        raise ValueError("shapes is empty")
    return [name for name in SHAPES if name in wanted]


register(PatternBlocksGenerator())
