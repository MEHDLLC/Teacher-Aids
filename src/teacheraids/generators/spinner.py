"""Probability spinners.

The teaching value is in the *unequal* spinner.  A six-sector spinner where
every sector is a sixth is a die that takes longer; a spinner where red is
half and blue is a sixth is a question a die cannot ask.  So the sectors are
given as weights, and the listing states the probability each one came out at,
worked out from the geometry rather than from what was intended.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("labels", "1,2,3,4,5,6",
           "What is written in each sector, comma separated", kind="str",
           group="Content"),
    Option("weights", "",
           "Relative sector sizes, comma separated. Empty makes them equal; "
           "3,1,1,1 makes the first one half the spinner", kind="str",
           group="Content"),
    Option("divider_relief", "raised",
           "Whether the sector lines stand off or sink in",
           kind="choice", choices=("raised", "recessed"), group="Content"),

    Option("diameter", 120.0, "Dial diameter", unit=" mm", minimum=50.0,
           maximum=250.0, group="Size"),
    Option("thickness", 4.0, "Dial thickness", unit=" mm", minimum=2.0,
           maximum=12.0, group="Size"),
    Option("pointer_thickness", 3.0, "Pointer thickness", unit=" mm",
           minimum=1.5, maximum=8.0, group="Size"),
    Option("relief_depth", 1.2, "How far the markings stand off or sink in",
           unit=" mm", minimum=0.3, maximum=4.0, group="Size"),
    Option("divider_width", 1.6, "Width of the lines between sectors",
           unit=" mm", minimum=0.6, maximum=5.0, group="Size"),

    Option("post", 8.0, "Diameter of the post the pointer turns on",
           unit=" mm", minimum=4.0, maximum=20.0, group="Fit"),
    Option("turn_clearance", 0.4,
           "Gap between post and pointer, so it spins freely", unit=" mm",
           minimum=0.15, maximum=1.2, group="Fit"),
    Option("press_fit", 0.12, "How much the cap is undersized on the post",
           unit=" mm", minimum=0.0, maximum=0.6, group="Fit"),
    Option("rim", 2.0,
           "A raised rim around the dial, so the pointer cannot be knocked "
           "off the edge. Zero leaves it flat", unit=" mm", minimum=0.0,
           maximum=8.0, group="Fit"),
    common.material_option(),
])


class SpinnerGenerator(Generator):
    key = "spinner"
    category = "games"
    title = "Probability spinner"
    summary = (
        "A spinner with sectors you size yourself, so red really can be half "
        "the circle -- with the probability each sector actually came out at "
        "printed in the listing."
    )
    tags = ("spinner", "probability", "chance", "math", "game", "classroom",
            "teaching aid", "parametric")
    ages = "6-14"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        labels = [part.strip() for part in str(opt["labels"]).split(",")]
        labels = [l for l in labels if l != ""] or ["1", "2"]
        if len(labels) < 2:
            raise ValueError("a spinner needs at least two sectors")
        if len(labels) > 16:
            raise ValueError(
                f"{len(labels)} sectors on a {opt['diameter']:.0f} mm dial is "
                "narrower than the pointer. Sixteen is the limit."
            )
        for label in labels:
            missing = text.font.missing(label)
            if missing:
                raise ValueError(
                    f"sector {label!r} uses "
                    + ", ".join(repr(c) for c in missing)
                    + " which this font cannot draw."
                )

        weights = _parse_weights(opt["weights"], len(labels))
        total = sum(weights)
        spans = [360.0 * w / total for w in weights]
        chances = [w / total for w in weights]

        narrowest = min(spans)
        if narrowest < 12.0:
            report.warn(
                f"the narrowest sector is {narrowest:.0f} degrees, which is "
                "about as wide as the pointer. A spin landing on it will be "
                "arguable."
            )
        common.check_features(report, opt["thickness"], opt["relief_depth"],
                              opt["divider_width"])

        radius = opt["diameter"] / 2.0
        parts = PartSet()
        parts.add("1_dial", self._dial(opt, radius, labels, spans, report),
                  note=", ".join(
                      f"{l} {c * 100:.0f}%" for l, c in zip(labels, chances)))
        parts.add("2_pointer", self._pointer(opt, radius),
                  note="spins on the post")
        parts.add("3_cap", self._cap(opt), note="presses on to hold it")

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": 3,
                "outside_mm": [opt["diameter"], opt["diameter"],
                               opt["thickness"] + opt["pointer_thickness"]
                               + 3.2],
                "piece_mm": list(parts.parts[0].size),
                "sectors": len(labels),
                "probabilities": {l: round(c, 4)
                                  for l, c in zip(labels, chances)},
                "supports": "none",
            },
            highlights=[
                f"{len(labels)} sectors on a {opt['diameter']:.0f} mm dial: "
                + ", ".join(f"{l} at {c * 100:.0f}%"
                            for l, c in zip(labels, chances)) + ".",
                "Equal sectors, so every outcome is as likely as every other."
                if len(set(weights)) == 1 else
                "Deliberately unequal, which is the interesting case: a "
                "spinner can ask questions a die cannot.",
                "Three parts, no hardware: the pointer drops over a post "
                "printed into the dial and a cap presses on.",
                f"A {opt['rim']:.0f} mm rim keeps the pointer on the dial."
                if opt["rim"] > 0 else "Flat, with no rim.",
            ],
            teaching_notes=[
                "Predict, then spin fifty times and tally. Comparing the "
                "tally with the prediction is the entire lesson.",
                "With unequal sectors, ask which is more likely before "
                "counting -- and then ask how much more.",
                "Two spinners and the combined outcomes are a sample space "
                "worth drawing out on a grid.",
            ],
            print_notes=[
                "All three parts flat on the bed, no supports.",
                "Dial and pointer in contrasting colours.",
                "0.2 mm layers, 3 perimeters.",
                "The pointer wants to be a little loose. If it stops dead "
                f"instead of spinning, raise turn_clearance above "
                f"{opt['turn_clearance']:.2f} mm, or rub a pencil on the post.",
                "A drop of oil, candle wax or graphite on the post makes it "
                "spin for much longer, which children care about a great deal.",
            ],
        )

    def _dial(self, opt, radius: float, labels, spans, report: Report):
        thickness = opt["thickness"]
        face = radius - opt["rim"] - 1.0
        body = geom.extrude(geom.circle(radius), thickness)

        marks = []
        cursor = 90.0                    # start at twelve o'clock
        half = opt["divider_width"] / 2.0
        for label, span in zip(labels, spans):
            marks.append(geom.capsule(
                (0.0, 0.0),
                (face * math.cos(math.radians(cursor)),
                 face * math.sin(math.radians(cursor))), half))
            mid = math.radians(cursor - span / 2.0)
            # Room for the label is the chord across the sector at the radius
            # the label sits on, which is what actually limits it.
            label_radius = face * 0.62
            room = min(2.0 * label_radius * math.sin(math.radians(span / 2.0))
                       * 0.85, face * 0.5)
            shape, cap = text.fitted_line(label, room, face * 0.24,
                                          min_cap=3.0)
            if shape.is_empty():
                report.note(f"{label!r} did not fit its sector.")
            else:
                bx0, by0, bx1, by1 = geom.shape_bounds(shape)
                shape = shape.translate([-(bx0 + bx1) / 2.0,
                                         -(by0 + by1) / 2.0])
                marks.append(shape.translate([
                    label_radius * math.cos(mid),
                    label_radius * math.sin(mid)]))
            cursor -= span

        if opt["rim"] > 0:
            marks.append(geom.ring(radius, radius - opt["rim"]))

        field = geom.shape_union(marks)
        solid = common.face_relief(body, field, opt["divider_relief"],
                                   opt["relief_depth"], thickness,
                                   0.25 if opt["divider_relief"] == "raised"
                                   else 0.0)

        post_top = thickness + opt["pointer_thickness"] + 1.6
        solid = geom.union([
            solid,
            geom.cylinder_z(opt["post"] / 2.0, thickness, post_top),
            geom.cone_z(opt["post"] / 2.0 + 0.45, opt["post"] / 2.0,
                        post_top - 1.6, post_top),
        ])
        if not geom.is_one_piece(solid):
            raise ValueError("the dial came apart; reduce relief_depth")
        return solid

    def _pointer(self, opt, radius: float):
        length = (radius - opt["rim"] - 3.0) * 0.94
        boss = opt["post"] / 2.0 + max(opt["pointer_thickness"], 2.5)
        width = max(radius * 0.10, boss * 0.9)
        # A long head and a short counterweighted tail, so it balances on the
        # post instead of drooping and dragging on the dial.
        outline = geom.polygon([
            (-length * 0.30, -width * 0.42),
            (length - width, -width * 0.62),
            (length, 0.0),
            (length - width, width * 0.62),
            (-length * 0.30, width * 0.42),
        ])
        profile = geom.shape_union([outline, geom.circle(boss)])
        profile = profile - geom.circle(opt["post"] / 2.0
                                        + opt["turn_clearance"])
        solid = geom.extrude(profile, opt["pointer_thickness"])
        if not geom.is_one_piece(solid):
            raise ValueError("the pointer came apart; widen it")
        return solid

    def _cap(self, opt):
        outer = opt["post"] / 2.0 + max(opt["pointer_thickness"], 2.5)
        height = 3.2
        bore = opt["post"] / 2.0 - opt["press_fit"]
        body = geom.union([
            geom.cylinder_z(outer, 0.0, 1.6),
            geom.cone_z(outer, outer * 0.72, 1.6, height),
        ])
        return geom.difference(body, geom.cylinder_z(bore, -0.01, height - 1.0))

    def slug(self, opt: dict[str, Any]) -> str:
        count = len([l for l in str(opt["labels"]).split(",") if l.strip()])
        kind = "even" if not str(opt["weights"]).strip() else "weighted"
        return f"spinner_{count}-way_{kind}_{opt['diameter']:g}mm"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        return (f"Probability spinner - {result.facts['sectors']} sectors, "
                f"{opt['diameter']:.0f} mm"
                + ("" if not str(opt["weights"]).strip() else ", weighted"))


def _parse_weights(raw: str, count: int) -> list[float]:
    text_value = str(raw).strip()
    if not text_value:
        return [1.0] * count
    values = []
    for chunk in text_value.replace(" ", "").split(","):
        if not chunk:
            continue
        try:
            value = float(chunk)
        except ValueError:
            raise ValueError(
                f"weights: {chunk!r} is not a number. Write them like 3,1,1,1."
            ) from None
        if value <= 0:
            raise ValueError(f"weights: {value} is not a sector size")
        values.append(value)
    if len(values) != count:
        raise ValueError(
            f"weights has {len(values)} numbers but there are {count} labels. "
            "Give one weight per label, or leave weights empty for equal ones."
        )
    return values


register(SpinnerGenerator())
