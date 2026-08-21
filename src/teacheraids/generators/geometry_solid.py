"""Geometric solids: the shapes a child has to hold to believe.

Two things this set does that a picture in a textbook cannot.  It can be
printed as an open frame, so the edges and vertices are countable rather than
asserted -- and the frame is the version that teaches, because a solid cube
hides eight of its twelve edges at any one time.  And every piece carries its
own face, edge and vertex counts engraved on the base, so a shape that has
been argued over can settle the argument itself.

Curved solids -- the cylinder, cone and sphere -- have no edges to frame, and
they say so rather than quietly printing something else.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, polyhedra, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

# name -> (faces, edges, vertices, what to call it, can it be framed)
SOLIDS: dict[str, tuple[int, int, int, str, bool]] = {
    "cube": (6, 12, 8, "Cube", True),
    "cuboid": (6, 12, 8, "Cuboid", True),
    "tetrahedron": (4, 6, 4, "Tetrahedron", True),
    "octahedron": (8, 12, 6, "Octahedron", True),
    "dodecahedron": (12, 30, 20, "Dodecahedron", True),
    "icosahedron": (20, 30, 12, "Icosahedron", True),
    "triangular-prism": (5, 9, 6, "Triangular prism", True),
    "pentagonal-prism": (7, 15, 10, "Pentagonal prism", True),
    "hexagonal-prism": (8, 18, 12, "Hexagonal prism", True),
    "square-pyramid": (5, 8, 5, "Square pyramid", True),
    "triangular-pyramid": (4, 6, 4, "Triangular pyramid", True),
    "cylinder": (3, 2, 0, "Cylinder", False),
    "cone": (2, 1, 1, "Cone", False),
    "sphere": (1, 0, 0, "Sphere", False),
}

DEFAULT_SET = ("cube,cuboid,triangular-prism,hexagonal-prism,square-pyramid,"
               "cylinder,cone,sphere")

OPTIONS = OptionSet([
    Option("solids", DEFAULT_SET, "Which solids to build, comma separated",
           kind="str", group="Content"),
    Option("style", "solid",
           "solid blocks, or open frames showing every edge and vertex",
           kind="choice", choices=("solid", "frame"), group="Content"),
    Option("label", True,
           "Engrave the name and the face, edge and vertex counts on the base",
           kind="bool", group="Content"),

    Option("size", 50.0,
           "Nominal size: the edge of the cube, and the width every other "
           "solid is scaled to match", unit=" mm", minimum=15.0, maximum=200.0,
           group="Size"),
    Option("height_ratio", 1.0,
           "How tall the solids are, relative to their width. The cuboid "
           "ignores this and is deliberately not a cube", minimum=0.4,
           maximum=2.5, group="Size"),

    Option("rib", 4.0, "Bar thickness when style is frame", unit=" mm",
           minimum=1.5, maximum=15.0, group="Frame"),
    Option("label_depth", 0.7, "How deep the engraving on the base is",
           unit=" mm", minimum=0.2, maximum=2.0, group="Detail"),
    Option("sphere_flat", 0.18,
           "Fraction of the sphere's diameter flattened off the bottom, so it "
           "sits still and prints without a support tower", minimum=0.0,
           maximum=0.45, group="Detail"),
    common.material_option(),
])


class GeometrySolidGenerator(Generator):
    key = "geometry-solid"
    category = "math"
    title = "Geometric solids"
    summary = (
        "A set of 3-D shapes to hold, sort and count -- as solid blocks or as "
        "open frames where every edge and vertex can actually be counted -- "
        "each with its face, edge and vertex numbers engraved on the base."
    )
    tags = ("geometry", "solids", "3d shapes", "math", "manipulative",
            "platonic solids", "classroom", "teaching aid", "parametric")
    ages = "5-14"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        wanted = _parse_solids(opt["solids"])
        size = opt["size"]

        framed = opt["style"] == "frame"
        if framed:
            curved = [n for n in wanted if not SOLIDS[n][4]]
            if curved:
                report.warn(
                    "a " + ", ".join(curved) + " has no edges to frame, so "
                    "it was built solid. Everything else in this set is a "
                    "frame."
                )
        common.check_features(report, size, opt["label_depth"],
                              opt["rib"] if framed else size)

        parts = PartSet()
        for name in wanted:
            solid = self._one(name, opt, report)
            faces, edges, vertices, label, _ = SOLIDS[name]
            if opt["label"]:
                solid = self._engrave(solid, name, opt, report)
            note = (f"{faces} faces, {edges} edges, {vertices} vertices"
                    if vertices else _CURVED_NOTE[name])
            parts.add(f"{name}", solid, note=note)

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": len(parts),
                "shapes": ", ".join(wanted),
                "piece_mm": list(parts.parts[0].size),
                "outside_mm": [size, size, size * opt["height_ratio"]],
                "supports": ("none" if not any(n in wanted for n in ("sphere",))
                             or opt["sphere_flat"] > 0 else "sphere only"),
            },
            highlights=[
                f"{len(parts)} solids on a {size:.0f} mm nominal size, so "
                "they compare directly against each other.",
                "Printed as open frames: every edge is a bar and every vertex "
                "a ball, so a child counting them is counting the thing "
                "itself rather than a picture of it."
                if framed else
                "Solid blocks, for sorting, tracing round and building with.",
                "Face, edge and vertex counts engraved on the base of each, "
                "so the answer is on the shape."
                if opt["label"] else
                "Unlabelled, so the counting is the exercise.",
                "The sphere has a flat off its bottom, which is what lets it "
                "sit on a desk and print without a support tower under it."
                if "sphere" in wanted and opt["sphere_flat"] > 0 else
                "Every solid stands on a flat face.",
            ],
            teaching_notes=[
                "Sort by number of faces, then by whether the faces are all "
                "the same. That second sort is what picks out the five "
                "Platonic solids.",
                "Euler's formula: faces plus vertices minus edges is two for "
                "every one of these. Check it on the engraved numbers.",
                "Roll them: which will roll, which will slide, which will do "
                "neither. That is a lesson about curved surfaces that does "
                "not need the words.",
                "Dip a face in paint and print it: a cube stamps a square, a "
                "cylinder stamps a circle and a cone stamps a dot.",
            ],
            print_notes=self._print_notes(opt, wanted, framed),
        )

    # -- shapes -----------------------------------------------------------

    def _one(self, name: str, opt, report: Report) -> geom.Solid:
        solid = self._shape(name, opt, report)
        if opt["style"] == "frame" and SOLIDS[name][4]:
            self._check_openness(name, solid, opt, report)
        return solid

    def _check_openness(self, name: str, frame, opt, report: Report) -> None:
        """Say so when a rib is thick enough that the frame is barely open.

        A tetrahedron's faces are small for its circumradius and its dihedral
        angle is sharp, so a rib that leaves an icosahedron looking like a
        wire model leaves a tetrahedron looking like a tetrahedron with
        dimples in it.
        """
        plain = dict(opt)
        plain["style"] = "solid"
        solid = self._shape(name, plain, Report())
        if solid.is_empty() or frame.is_empty():
            return
        openness = 1.0 - frame.volume() / solid.volume()
        if openness < 0.35:
            report.warn(
                f"the {name} frame is only {openness * 100:.0f}% open at a "
                f"{opt['rib']:.1f} mm rib: its faces are small for its size, "
                "so it reads as a dimpled solid rather than a wire model. "
                "Thin the rib, or grow the size."
            )

    def _shape(self, name: str, opt, report: Report) -> geom.Solid:
        size = opt["size"]
        height = size * opt["height_ratio"]
        rib = opt["rib"]
        framed = opt["style"] == "frame" and SOLIDS[name][4]

        if name in polyhedra.PLATONIC:
            # Scale by the edge so a tetrahedron and a cube with the same
            # `size` have the same edge, which is the comparison that matters.
            reference = polyhedra.build(name, 1.0)
            a, b = reference.edges[0]
            unit_edge = float(
                ((reference.vertices[a] - reference.vertices[b]) ** 2).sum() ** 0.5)
            shape = polyhedra.build(name, size / unit_edge)
            return shape.frame(rib) if framed else shape.solid()

        if name in ("cuboid", "cube"):
            width = size
            depth = size * (0.6 if name == "cuboid" else 1.0)
            tall = height * (1.5 if name == "cuboid" else 1.0)
            return (_box_frame(width, depth, tall, rib) if framed
                    else geom.box([width, depth, tall]))

        if name.endswith("-prism"):
            sides = {"triangular": 3, "pentagonal": 5, "hexagonal": 6}[
                name.split("-")[0]]
            profile = geom.regular_polygon_by_edge(sides, size,
                                                   rotation_deg=90.0)
            if not framed:
                return geom.extrude(profile, height)
            return _prism_frame(profile, height, rib)

        if name == "square-pyramid":
            return (_pyramid_frame(geom.rect(size, size), height, rib) if framed
                    else _pyramid(geom.rect(size, size), height))

        if name == "triangular-pyramid":
            profile = geom.regular_polygon_by_edge(3, size, rotation_deg=90.0)
            return (_pyramid_frame(profile, height, rib) if framed
                    else _pyramid(profile, height))

        if name == "cylinder":
            return geom.cylinder_z(size / 2.0, 0.0, height)

        if name == "cone":
            return geom.cone_z(size / 2.0, 0.0, 0.0, height)

        if name == "sphere":
            ball = geom.sphere(size / 2.0, (0.0, 0.0, size / 2.0))
            cut = opt["sphere_flat"] * size
            if cut <= 0:
                report.warn(
                    "a sphere with no flat needs a support tower under it and "
                    "rolls off the desk. Set sphere_flat above zero."
                )
                return ball
            return geom.difference(
                ball, geom.box([size * 2, size * 2, cut],
                               at=[-size, -size, 0.0])).translate([0, 0, 0])

        raise ValueError(f"no builder for {name!r}")   # pragma: no cover

    def _engrave(self, solid: geom.Solid, name: str, opt,
                 report: Report) -> geom.Solid:
        """Sink the name and the counts into the underside."""
        faces, edges, vertices, label, _ = SOLIDS[name]
        x0, y0, z0, x1, y1, z1 = geom.bounds(solid)
        room = min(x1 - x0, y1 - y0) * 0.80
        if room < 12.0:
            report.note(f"{name} is too small to engrave legibly; left plain.")
            return solid

        lines = [label.upper()]
        if vertices:
            lines.append(f"F{faces} E{edges} V{vertices}")
        cap = min(room / max(len(max(lines, key=len)), 1) * 1.5, room * 0.28)
        block = text.block_shape(lines, cap, 18.0, leading=1.5)
        if block.is_empty():
            return solid
        bx0, by0, bx1, by1 = geom.shape_bounds(block)
        span = max(bx1 - bx0, 1e-6)
        if span > room:
            block = block.scale([room / span, room / span])
        # Mirrored, because it is read from underneath: engrave it the right
        # way round on the model and it comes out backwards on the part.
        block = block.mirror([1.0, 0.0]).translate(
            [(x0 + x1) / 2.0, (y0 + y1) / 2.0])
        cutter = geom.extrude(block, opt["label_depth"] + 0.01, at_z=z0 - 0.01)
        engraved = geom.difference(solid, cutter)
        if not geom.is_one_piece(engraved):
            report.note(
                f"{name}: the engraving would have cut it into pieces, so it "
                "was left plain."
            )
            return solid
        return engraved

    def _print_notes(self, opt, wanted, framed: bool) -> list[str]:
        notes = ["Every solid stands on a flat face. No supports."]
        if framed:
            notes.append(
                f"The frames are diamond-section bars: nothing overhangs past "
                f"45 degrees, so a {opt['rib']:.0f} mm bar prints in mid-air "
                "across the top of the shape without help."
            )
        if "sphere" in wanted:
            notes.append(
                f"The sphere's flat is {opt['sphere_flat'] * 100:.0f}% of its "
                "diameter. That is what it is standing on; do not slice it off."
                if opt["sphere_flat"] > 0 else
                "The sphere is a full sphere and will need supports."
            )
        if "cone" in wanted:
            notes.append(
                "The cone's side is well inside 45 degrees from vertical at "
                "the default proportions. Push `height_ratio` below about 0.5 "
                "and it becomes an overhang."
            )
        notes += [
            "0.2 mm layers. 3 perimeters and 10% infill for the solid style; "
            "frames are nearly all perimeter, so infill does nothing.",
            "The engraving on the base is mirrored in the model so it reads "
            "correctly on the printed part.",
        ]
        return notes

    def slug(self, opt: dict[str, Any]) -> str:
        return f"geometry-solid_{opt['style']}_{opt['size']:g}mm"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        noun = "frames" if opt["style"] == "frame" else "solids"
        return (f"Geometric {noun} - {result.facts['pieces']} shapes at "
                f"{opt['size']:.0f} mm")


_CURVED_NOTE = {
    "cylinder": "2 flat faces and 1 curved surface, no vertices",
    "cone": "1 flat face, 1 curved surface and 1 apex",
    "sphere": "1 curved surface, no faces, edges or vertices",
}


def _pyramid(profile, height: float) -> geom.Solid:
    """A pyramid: an extrusion whose top scales to a single point."""
    return profile.extrude(height, 0, 0.0, (0.0, 0.0))


def _box_frame(width: float, depth: float, height: float,
               rib: float) -> geom.Solid:
    verts = [(x, y, z)
             for z in (0.0, height) for y in (0.0, depth) for x in (0.0, width)]
    return _bars(verts, rib)


def _prism_frame(profile, height: float, rib: float) -> geom.Solid:
    ring = [(float(x), float(y)) for x, y in profile.to_polygons()[0]]
    verts = ([(x, y, 0.0) for x, y in ring]
             + [(x, y, height) for x, y in ring])
    return _bars(verts, rib)


def _pyramid_frame(profile, height: float, rib: float) -> geom.Solid:
    ring = [(float(x), float(y)) for x, y in profile.to_polygons()[0]]
    count = len(ring)
    centre = (sum(p[0] for p in ring) / count, sum(p[1] for p in ring) / count)
    verts = [(x, y, 0.0) for x, y in ring] + [(centre[0], centre[1], height)]
    return _bars(verts, rib)


def _bars(verts, rib: float) -> geom.Solid:
    """A frame for any convex shape, from its corner points alone."""
    import numpy as np
    return polyhedra.from_points(np.array(verts, dtype=float)).frame(rib)


def _parse_solids(raw: str) -> list[str]:
    wanted = [c.strip().lower() for c in str(raw).split(",") if c.strip()]
    unknown = [c for c in wanted if c not in SOLIDS]
    if unknown:
        raise ValueError(
            "solids: " + ", ".join(unknown) + " is not one of "
            + ", ".join(SOLIDS)
        )
    if not wanted:
        raise ValueError("solids is empty")
    return [name for name in SOLIDS if name in wanted]


register(GeometrySolidGenerator())
