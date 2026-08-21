"""Bookmarks.

Thin, so it does not splay the book, and that thinness is the whole design
problem: at 1.2 mm a bookmark is three or four layers, and a cut-out motif
with a 1 mm web between it and the edge will tear the first time a child pulls
it out by the corner.  So the motif is held clear of the edge by a margin the
generator enforces, and anything under two extrusions gets warned about.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, patterns, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

MOTIFS = ("none", "star", "circle", "heart", "diamond", "triangle", "hexagon")

OPTIONS = OptionSet([
    Option("text", "READ", "Text along the bookmark", kind="str",
           group="Content"),
    Option("texts", "",
           "Several bookmarks in one run, separated by semicolons. Overrides "
           "`text`", kind="str", group="Content"),
    Option("max_marks", 24, "Stop after this many bookmarks", kind="int",
           minimum=1, maximum=80, group="Content"),
    Option("motif", "star", "A shape cut through the top",
           kind="choice", choices=MOTIFS, group="Content"),

    Option("length", 150.0, "Length", unit=" mm", minimum=60.0, maximum=260.0,
           group="Size"),
    Option("width", 32.0, "Width", unit=" mm", minimum=15.0, maximum=70.0,
           group="Size"),
    Option("thickness", 1.6, "Thickness", unit=" mm", minimum=0.8,
           maximum=5.0, group="Size"),
    Option("margin", 4.0, "Clear border kept around everything", unit=" mm",
           minimum=2.0, maximum=15.0, group="Size"),

    Option("relief", "raised", "Whether the text stands off or sinks in",
           kind="choice", choices=("raised", "recessed", "cut"),
           group="Detail"),
    Option("relief_depth", 0.8, "How far the text stands off or sinks in",
           unit=" mm", minimum=0.2, maximum=3.0, group="Detail"),
    Option("bridge", 2.4,
           "Width of the tabs that hold the middle of an A or an O in place "
           "when the text is cut through", unit=" mm", minimum=0.8,
           maximum=8.0, group="Detail"),
    Option("along", True,
           "Run the text along the length. Off sets it across, which suits a "
           "short word", kind="bool", group="Detail"),
    Option("tassel_hole", 4.0,
           "Hole at the top for a ribbon or tassel. Zero leaves it out",
           unit=" mm", minimum=0.0, maximum=12.0, group="Detail"),
    Option("pattern", "none", "A texture engraved down the face",
           kind="choice", choices=("none",) + patterns.PATTERNS,
           group="Detail"),
    *common.corner_options(6.0),
    common.material_option(),
])


class BookmarkGenerator(Generator):
    key = "bookmark"
    category = "classroom"
    title = "Bookmark"
    summary = (
        "Thin printed bookmarks with a name or a word down the length, a "
        "shape cut through the top and a hole for a ribbon -- a class set in "
        "one run."
    )
    tags = ("bookmark", "reading", "classroom", "library", "reward",
            "personalised", "parametric", "3d printing")
    ages = "any"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        phrases = [t.strip() for t in str(opt["texts"]).split(";") if t.strip()]
        if not phrases:
            phrases = [str(opt["text"]).strip()]
        if not any(phrases):
            raise ValueError("text is empty; give a word, a name or a phrase")
        if len(phrases) > opt["max_marks"]:
            report.warn(
                f"{len(phrases)} bookmarks is more than max_marks "
                f"({opt['max_marks']}); this run leaves out "
                + ", ".join(phrases[opt["max_marks"]:]) + "."
            )
            phrases = phrases[: opt["max_marks"]]

        common.check_features(report, opt["thickness"], opt["relief_depth"],
                              opt["thickness"])
        if opt["relief"] == "raised" and opt["relief_depth"] > opt["thickness"]:
            report.warn(
                f"{opt['relief_depth']:.1f} mm of raised text on a "
                f"{opt['thickness']:.1f} mm bookmark is taller than the "
                "bookmark is thick, which will hold the book open."
            )

        parts = PartSet()
        for phrase in phrases:
            parts.add(_safe(phrase), self._one(phrase, opt, report),
                      note=phrase)

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": len(parts),
                "piece_mm": list(parts.parts[0].size),
                "outside_mm": [opt["width"], opt["length"], opt["thickness"]],
                "supports": "none",
            },
            highlights=[
                f"{len(parts)} bookmark" + ("s" if len(parts) != 1 else "")
                + f", {opt['length']:.0f} x {opt['width']:.0f} mm and "
                  f"{opt['thickness']:.1f} mm thin.",
                f"A {opt['motif']} cut through the top."
                if opt["motif"] != "none" else "A plain top.",
                f"A {opt['tassel_hole']:.0f} mm hole for a ribbon or a tassel."
                if opt["tassel_hole"] > 0 else "No ribbon hole.",
                "Text runs down the length, which is what fits a long name."
                if opt["along"] else
                "Text runs across, which suits a short word at a large size.",
            ],
            teaching_notes=[
                "A class set with each child's name is a five-minute job per "
                "plate and lands better than a sticker.",
                "Reading-challenge rewards: print the milestone on it and the "
                "bookmark is the certificate.",
            ],
            print_notes=[
                "Flat on the bed, no supports.",
                f"At {opt['thickness']:.1f} mm this is "
                f"{max(int(opt['thickness'] / 0.2), 1)} layers at 0.2 mm. Use "
                "0.15 mm layers and it comes out smoother without taking much "
                "longer.",
                "4 perimeters, 100% infill -- at this thickness it is all "
                "perimeter anyway, and gaps make it snap.",
                "PETG flexes rather than snapping. PLA bookmarks break at the "
                "tassel hole eventually.",
            ],
        )

    def _one(self, phrase: str, opt, report: Report) -> geom.Solid:
        width, length = opt["width"], opt["length"]
        thickness, margin = opt["thickness"], opt["margin"]
        body = common.plate(width, length, thickness, opt["corner"],
                            opt["corner_size"])

        top = length / 2.0 - margin
        cursor = top
        cutters = []

        if opt["tassel_hole"] > 0:
            centre = cursor - opt["tassel_hole"] / 2.0
            cutters.append(common.hang_hole(opt["tassel_hole"], thickness,
                                            (0.0, centre)))
            cursor = centre - opt["tassel_hole"] / 2.0 - margin

        if opt["motif"] != "none":
            span = min(width - 2.0 * margin, (length * 0.22))
            motif = _motif(opt["motif"], span)
            centre = cursor - span / 2.0
            cutters.append(geom.extrude(motif.translate([0.0, centre]),
                                        thickness + 2.0, at_z=-1.0))
            cursor = centre - span / 2.0 - margin

        solid = geom.difference(body, cutters)

        # Whatever is left below the motif is the text's.
        low = -length / 2.0 + margin
        field_height = cursor - low
        field_width = width - 2.0 * margin
        if opt["along"]:
            shape, cap = text.fitted_line(phrase, field_height,
                                          field_width * 0.8, min_cap=4.0)
            shape = shape.rotate(90.0)
        else:
            shape, cap = text.fitted_line(phrase, field_width,
                                          min(field_height * 0.7, width * 0.6),
                                          min_cap=4.0)
        # Centre the ink in the space that is left, measured rather than
        # assumed: a rotation is about the origin, so a line set on a baseline
        # at y=0 comes back sitting entirely to one side of it, and shifting
        # by half a cap height instead of by the real bounds walks the letters
        # off the edge of the bookmark.
        if not shape.is_empty():
            bx0, by0, bx1, by1 = geom.shape_bounds(shape)
            shape = shape.translate([-(bx0 + bx1) / 2.0,
                                     (cursor + low) / 2.0 - (by0 + by1) / 2.0])

        if shape.is_empty():
            report.warn(f"{phrase!r} did not fit and was left off its bookmark.")
        else:
            ink = (text.stencil_cut(shape, opt["bridge"])
                   if opt["relief"] == "cut" else shape)
            solid = common.face_relief(
                solid, ink, opt["relief"], opt["relief_depth"], thickness,
                0.2 if opt["relief"] == "raised" else 0.0)

        if opt["pattern"] != "none":
            profiles = patterns.tile(
                opt["pattern"], (-field_width / 2.0, low, field_width / 2.0,
                                 cursor),
                patterns.default_cell(opt["pattern"]) * 0.4,
                patterns.default_rib(opt["pattern"]) * 0.5)
            if profiles:
                field = geom.shape_union([geom.polygon(p) for p in profiles])
                field = field - shape.offset(1.5, text.geom_join(), 2.0, 12)
                depth = min(opt["relief_depth"] * 0.5, thickness * 0.3)
                solid = geom.difference(solid, geom.extrude(
                    field, depth + 0.01, at_z=thickness - depth))

        if not geom.is_one_piece(solid):
            raise ValueError(
                f"the bookmark for {phrase!r} came apart. The motif or the "
                "cut text has reached the edge; raise `margin`."
            )
        return solid

    def slug(self, opt: dict[str, Any]) -> str:
        phrases = [t.strip() for t in str(opt["texts"]).split(";") if t.strip()]
        tag = (_safe(phrases[0]) if len(phrases) == 1
               else f"{len(phrases)}-marks" if phrases
               else _safe(str(opt["text"])))
        return f"bookmark_{tag}_{opt['motif']}_{opt['length']:g}mm"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        count = result.facts["pieces"]
        if count == 1:
            return (f"Bookmark - {opt['length']:.0f} mm, "
                    + (f"{opt['motif']} cut-out" if opt["motif"] != "none"
                       else "plain"))
        return f"Bookmarks - {count} in the set, {opt['length']:.0f} mm"


def _motif(name: str, span: float):
    """A shape to cut through the top, sized to fit inside `span`."""
    radius = span / 2.0
    if name == "circle":
        return geom.circle(radius)
    if name == "hexagon":
        return geom.regular_polygon(6, radius, rotation_deg=90.0)
    if name == "triangle":
        return geom.regular_polygon(3, radius, rotation_deg=90.0)
    if name == "diamond":
        return geom.polygon([(0, -radius), (radius, 0), (0, radius),
                             (-radius, 0)])
    if name == "star":
        inner = radius * 0.42
        points = []
        for index in range(10):
            reach = radius if index % 2 == 0 else inner
            angle = math.pi / 2.0 + index * math.pi / 5.0
            points.append((reach * math.cos(angle), reach * math.sin(angle)))
        return geom.polygon(points)
    if name == "heart":
        # Two round lobes and a triangular point. The triangle's top corners
        # sit *inside* the lobes rather than on them: a corner that lands on
        # a circle's edge is a tangent contact, and a union across one of
        # those produces an edge shared by more than two triangles, which no
        # slicer and no mesh checker will accept.
        lobe = radius * 0.5
        left = geom.circle(lobe).translate([-lobe * 0.9, lobe * 0.55])
        right = geom.circle(lobe).translate([lobe * 0.9, lobe * 0.55])
        tip = geom.polygon([
            (-lobe * 1.75, lobe * 0.62), (0.0, -radius),
            (lobe * 1.75, lobe * 0.62),
        ])
        return geom.shape_union([left, right, tip])
    raise ValueError(f"unknown motif {name!r}")   # pragma: no cover


def _safe(raw: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in raw).strip("-")
    return out or "bookmark"


register(BookmarkGenerator())
