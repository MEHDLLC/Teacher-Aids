"""Book ends.

A printed book end has one job it usually fails at: staying put.  Plastic is
light, and a shelf of paperbacks pushes harder than an empty L-bracket weighs.
So the foot goes *under* the books -- their own weight holds it down, which is
how the steel ones work -- and there is a cavity to fill with coins, sand or
scrap filament for the cases where that is not enough.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, patterns, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("height", 150.0, "Height of the upright face", unit=" mm",
           minimum=60.0, maximum=300.0, group="Size"),
    Option("width", 120.0, "Width across the shelf", unit=" mm", minimum=50.0,
           maximum=250.0, group="Size"),
    Option("foot", 110.0,
           "How far the foot reaches under the books. This is what stops it "
           "sliding, so longer is better up to about the depth of a paperback",
           unit=" mm", minimum=30.0, maximum=250.0, group="Size"),
    Option("thickness", 4.0, "Thickness of the upright and the foot",
           unit=" mm", minimum=2.0, maximum=12.0, group="Size"),
    Option("pair", True,
           "Make a matching mirrored pair, since a shelf needs two",
           kind="bool", group="Size"),

    Option("ballast", True,
           "A sealed-except-for-a-slot cavity in the upright, to fill with "
           "coins or sand", kind="bool", group="Weight"),
    Option("ballast_slot", 14.0,
           "Width of the opening you pour the ballast in through", unit=" mm",
           minimum=6.0, maximum=40.0, group="Weight"),

    Option("pattern", "none", "Cut a pattern through the upright face",
           kind="choice", choices=("none",) + patterns.PATTERNS,
           group="Pattern"),
    Option("pattern_cell", None, "How big one repeat of the pattern is",
           unit=" mm", minimum=4.0, maximum=60.0, group="Pattern",
           default_note="per pattern"),
    Option("pattern_rib", None, "Web left between pattern cells", unit=" mm",
           minimum=1.5, maximum=20.0, group="Pattern", default_note="per pattern"),

    Option("label", "", "Text embossed across the upright", kind="str",
           group="Detail"),
    Option("label_height", 18.0, "Height of the label lettering", unit=" mm",
           minimum=6.0, maximum=60.0, group="Detail"),
    Option("gusset", True,
           "A triangular brace between the upright and the foot, so a heavy "
           "shelf does not fold it over", kind="bool", group="Detail"),
    Option("grip", True,
           "A recess under the foot for a strip of non-slip matting or a few "
           "dabs of hot glue", kind="bool", group="Detail"),
    common.material_option(),
])


class BookEndGenerator(Generator):
    key = "book-end"
    category = "organization"
    title = "Book end"
    summary = (
        "An L-bracket book end whose foot goes under the books, so their own "
        "weight holds it down, with a fillable cavity for the shelves where "
        "that is not enough."
    )
    tags = ("book end", "bookend", "classroom library", "shelf",
            "organization", "teacher", "parametric", "3d printing")
    ages = "any"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        opt = dict(opt)
        if opt["pattern_cell"] is None:
            opt["pattern_cell"] = patterns.default_cell(opt["pattern"])
        if opt["pattern_rib"] is None:
            opt["pattern_rib"] = patterns.default_rib(opt["pattern"])

        thickness = opt["thickness"]
        common.check_features(report, thickness, 0.0, thickness)
        if opt["ballast"] and thickness < 3.0:
            report.warn(
                f"a {thickness:.1f} mm upright has no room for a ballast "
                "cavity inside it, so the cavity was skipped. Thicken to "
                "4 mm or more."
            )
        wants_ballast = opt["ballast"] and thickness >= 3.0
        if opt["pattern"] != "none" and wants_ballast:
            report.note(
                "the pattern is cut only above the ballast cavity, so the "
                "cavity stays a cavity."
            )

        parts = PartSet()
        left = self._one(opt, wants_ballast, report)
        parts.add("book-end", left,
                  note="foot points right; mirror it for the other end"
                       if opt["pair"] else "",
                  copies=1)
        if opt["pair"]:
            parts.add("book-end-mirrored", left.mirror([1.0, 0.0, 0.0]),
                      note="the other end of the shelf")

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": len(parts),
                "outside_mm": [opt["width"], opt["foot"], opt["height"]],
                "piece_mm": list(parts.parts[0].size),
                "supports": "none",
            },
            highlights=[
                f"{opt['height']:.0f} mm tall with a {opt['foot']:.0f} mm foot "
                "that slides under the books, so their weight is what holds it.",
                "A cavity in the upright takes about "
                f"{self._cavity_ml(opt):.0f} ml of coins, sand or old "
                "filament -- roughly "
                f"{self._cavity_ml(opt) * 1.5:.0f} g of dry sand."
                if wants_ballast else
                "No ballast cavity; it relies on the foot alone.",
                "A pair, mirrored, because a shelf needs two."
                if opt["pair"] else "A single end.",
                patterns.describe(opt["pattern"], opt["pattern_cell"],
                                  opt["pattern_rib"]) + " through the upright."
                if opt["pattern"] != "none" else
                "A solid face, which is also a surface to label.",
            ],
            teaching_notes=[
                "Label them by section and a classroom library stays sorted "
                "for longer than a week.",
                "Print in the colour that matches the book bands, and putting "
                "a book back becomes a matching exercise.",
            ],
            print_notes=[
                "Flat on the bed, foot down, no supports. The upright is one "
                "flat wall standing on the foot: nothing overhangs.",
                "The gusset's hypotenuse is the only sloped face and it rises "
                "at 45 degrees or steeper." if opt["gusset"] else
                "Without the gusset this is two flat plates meeting at a "
                "right angle; a heavy shelf will eventually bend it.",
                "0.3 mm layers, 4 perimeters, 20% infill. This is a "
                "structural part, not a decorative one.",
                "PETG if the shelf is heavy. PLA creeps under a sustained "
                "sideways load and will slowly lean.",
                f"Fill through the {opt['ballast_slot']:.0f} mm slot at the "
                "top, then tape or glue it shut." if wants_ballast else
                "Add a strip of non-slip matting under the foot.",
            ],
        )

    def _cavity_ml(self, opt) -> float:
        inner = self._cavity_box(opt)
        return inner[0] * inner[1] * inner[2] / 1000.0 if inner else 0.0

    def _cavity_box(self, opt):
        """Inside dimensions of the ballast cavity: width, depth, height.

        Only the lower 55% of the upright, for two reasons. Ballast carried
        low is what makes a thing hard to tip, which is the entire purpose;
        and it leaves the top of the face free for a pattern and a label
        instead of forcing a choice between weight and either of them.
        """
        skin = 1.6
        width = opt["width"] - 2.0 * skin
        height = (opt["height"] - opt["thickness"] - 2.0 * skin) * 0.55
        depth = opt["thickness"] - 2.0 * 1.0
        if min(width, height, depth) <= 1.0:
            return None
        return (width, depth, height)

    def _one(self, opt, wants_ballast: bool, report: Report) -> geom.Solid:
        width, height = opt["width"], opt["height"]
        foot, thickness = opt["foot"], opt["thickness"]

        # Upright stands at y = 0..thickness; the foot runs back from it.
        upright = geom.box([width, thickness, height])
        base = geom.box([width, foot, thickness])
        solid = geom.union([upright, base])

        if opt["gusset"]:
            reach = min(foot * 0.55, height * 0.55)
            rib = min(thickness * 1.2, 6.0)
            triangle = geom.polygon([
                (thickness, thickness), (thickness + reach, thickness),
                (thickness, thickness + reach),
            ])
            # Built in the (y, z) plane and extruded across a little of the
            # width at each side, so the middle of the shelf stays clear.
            for x in (0.0, width - rib):
                solid = geom.union([
                    solid,
                    geom.prism_x([(y, z) for y, z in triangle.to_polygons()[0]],
                                 x, x + rib)])

        cavity_top = 0.0
        if wants_ballast:
            box = self._cavity_box(opt)
            skin = 1.6
            cavity = geom.box([box[0], box[1], box[2]],
                              at=[skin, (thickness - box[1]) / 2.0,
                                  thickness + skin])
            cavity_top = thickness + skin + box[2]
            # A channel from the top of the cavity up through the top edge, so
            # the ballast can be poured in from above and the opening is not a
            # hole in the face for it to trickle back out of.
            slot = geom.box(
                [opt["ballast_slot"], box[1], height - cavity_top + 2.0],
                at=[(width - opt["ballast_slot"]) / 2.0,
                    (thickness - box[1]) / 2.0, cavity_top - 1.0])
            solid = geom.difference(solid, [cavity, slot])

        if opt["pattern"] != "none":
            low = max(cavity_top + 4.0, thickness + 6.0)
            high = height - 6.0
            if high - low >= 10.0:
                profiles = patterns.tile(
                    opt["pattern"], (6.0, low, width - 6.0, high),
                    opt["pattern_cell"], opt["pattern_rib"])
                # Keep the pattern off the fill channel: a cut-out that opens
                # into it turns the channel into a hole the sand comes out of.
                if wants_ballast:
                    keep_out = (width - opt["ballast_slot"]) / 2.0 - 3.0
                    keep_in = (width + opt["ballast_slot"]) / 2.0 + 3.0
                    profiles = [
                        p for p in profiles
                        if max(x for x, _ in p) < keep_out
                        or min(x for x, _ in p) > keep_in
                    ]
                if profiles:
                    solid = geom.difference(solid, [
                        geom.prism_y(p, -1.0, thickness + 1.0)
                        for p in profiles])
            else:
                report.warn(
                    "there is no clear band of upright left to put a pattern "
                    "in once the ballast cavity has taken its share. It was "
                    "left off."
                )

        if opt["grip"]:
            inset = 8.0
            pad = geom.box([width - 2 * inset, foot - thickness - 2 * inset,
                            0.8],
                           at=[inset, thickness + inset, -0.01])
            solid = geom.difference(solid, pad)

        if opt["label"]:
            shape, cap = text.fitted_line(opt["label"], width * 0.82,
                                          opt["label_height"], min_cap=5.0)
            if not shape.is_empty():
                plaque = geom.extrude(shape, 1.4, taper=0.3)
                plaque = plaque.rotate([90, 0, 0]).translate(
                    [width / 2.0, 0.4, height * 0.55 - cap / 2.0])
                solid = geom.union([solid, plaque])

        if not geom.is_one_piece(solid):
            raise ValueError(
                "the book end came apart; the pattern has cut right through "
                "the upright. Raise pattern_rib."
            )
        return solid

    def slug(self, opt: dict[str, Any]) -> str:
        return (f"book-end_{opt['width']:g}x{opt['height']:g}"
                f"_{opt['pattern']}")

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        what = "Book ends, a pair" if opt["pair"] else "Book end"
        return (f"{what} - {opt['height']:.0f} mm tall, "
                f"{opt['foot']:.0f} mm foot"
                + (", fillable" if opt["ballast"] else ""))


register(BookEndGenerator())
