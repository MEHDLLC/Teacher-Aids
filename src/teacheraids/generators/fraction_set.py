"""Fraction circles and fraction bars.

The point of a fraction manipulative is that the pieces are *comparable*: two
quarters have to sit exactly on top of one half, and three thirds have to
close the circle with no gap you can see.  That is a geometry problem with one
awkward corner -- a printed piece is fatter than its model by roughly one
extrusion width, so a set built at nominal size jams.  `kerf` takes that back
off every cut edge, and it is the option that decides whether the set works.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("style", "circle", "Round pieces that make a pie, or straight bars",
           kind="choice", choices=("circle", "bar"), group="Content"),
    Option("denominators", "1,2,3,4,6,8",
           "Which families to make, as a comma separated list. 4 makes four "
           "quarters", kind="str", group="Content"),
    Option("max_pieces", 60,
           "Stop before the set gets larger than this many pieces. "
           "1,2,3,4,5,6,8,10,12 is already 51", kind="int", minimum=2,
           maximum=250, group="Content"),
    Option("label", True, "Emboss 1/2, 1/3 and so on on each piece",
           kind="bool", group="Content"),

    Option("size", 120.0,
           "Diameter of the whole circle, or length of the whole bar",
           unit=" mm", minimum=30.0, maximum=300.0, group="Size"),
    Option("bar_width", 26.0, "Width of a bar, when style is bar", unit=" mm",
           minimum=8.0, maximum=80.0, group="Size"),
    Option("thickness", 6.0, "Piece thickness", unit=" mm", minimum=2.0,
           maximum=25.0, group="Size"),
    Option("hub", 0.0,
           "Diameter of a hole left at the centre of a circle set, so the "
           "pieces can pivot on a pin. Zero leaves the centre solid",
           unit=" mm", minimum=0.0, maximum=40.0, group="Size"),

    Option("kerf", 0.35,
           "Taken off every cut edge, so printed pieces still assemble. A "
           "printed part is about one extrusion wider than its model, and a "
           "twelfth with no kerf will not fit twelve to a circle",
           unit=" mm", minimum=0.0, maximum=1.5, group="Fit"),
    Option("label_depth", 0.8, "How deep the fraction is engraved", unit=" mm",
           minimum=0.2, maximum=3.0, group="Fit"),
    Option("label_relief", "recessed", "Whether the fraction sinks in or stands off",
           kind="choice", choices=("recessed", "raised"), group="Fit"),
    common.material_option(),
])


class FractionSetGenerator(Generator):
    key = "fraction-set"
    category = "math"
    title = "Fraction circles and bars"
    summary = (
        "Matched sets of fraction pieces -- halves, thirds, quarters and "
        "beyond -- as pie wedges or as bars, each engraved with the fraction "
        "it is, and undersized by one kerf so the printed pieces actually "
        "assemble."
    )
    tags = ("fractions", "math", "manipulative", "montessori", "numeracy",
            "classroom", "teaching aid", "parametric")
    ages = "6-12"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        denominators = _parse_denominators(opt["denominators"])

        kept: list[int] = []
        total = 0
        for denominator in denominators:
            if total + denominator > opt["max_pieces"]:
                report.warn(
                    f"stopping at 1/{kept[-1] if kept else '?'}: adding "
                    f"{denominator} more pieces would pass max_pieces "
                    f"({opt['max_pieces']}). Left out: "
                    + ", ".join(f"1/{d}" for d in denominators[len(kept):])
                    + "."
                )
                break
            kept.append(denominator)
            total += denominator
        if not kept:
            raise ValueError(
                f"max_pieces is {opt['max_pieces']}, which is not enough for "
                f"even 1/{denominators[0]}."
            )

        parts = PartSet()
        for denominator in kept:
            solid, note = (self._wedge(denominator, opt, report)
                           if opt["style"] == "circle"
                           else self._bar(denominator, opt, report))
            parts.add(f"{_ordinal_name(denominator)}", solid,
                      note=note, copies=denominator)

        common.check_small_parts(report, parts)
        facts = {
            "pieces": total,
            "families": ", ".join(f"1/{d}" for d in kept),
            "piece_mm": list(parts.parts[-1].size),
            "kerf_mm": opt["kerf"],
            "supports": "none",
        }
        if opt["style"] == "circle":
            facts["outside_mm"] = [opt["size"], opt["size"], opt["thickness"]]
        else:
            facts["outside_mm"] = [opt["size"], opt["bar_width"],
                                   opt["thickness"]]

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts=facts,
            highlights=[
                f"{total} pieces in {len(kept)} families: "
                + ", ".join(f"{d} x 1/{d}" for d in kept) + ".",
                ("A " + f"{opt['size']:.0f} mm circle" if opt["style"] == "circle"
                 else f"A {opt['size']:.0f} mm bar")
                + f", {opt['thickness']:.0f} mm thick, split every way at once.",
                f"Every cut edge is pulled back {opt['kerf']:.2f} mm, so the "
                "pieces still go together after the printer has added its own "
                "width to them.",
                "Each piece carries its own fraction, so a piece that has "
                "wandered into the wrong tub can be put back."
                if opt["label"] else
                "Unlabelled, so the pieces are compared rather than read.",
            ],
            teaching_notes=[
                "Build the whole from one family, then from two: two quarters "
                "and one half close the same circle.",
                "Equivalence by stacking: lay 2/6 on top of 1/3 and look "
                "through the edges.",
                "Ordering: line up 1/2, 1/3, 1/4, 1/6 and see the pieces get "
                "smaller as the number gets bigger, which is the thing that "
                "does not go in from a worksheet.",
            ],
            print_notes=[
                "Flat on the bed, no supports.",
                "Print each family in its own colour. Colour is how a child "
                "finds all the thirds, and it costs nothing but a filament "
                "swap between plates.",
                "0.2 mm layers, 3 perimeters, 20% infill.",
                f"If the pieces are tight, raise `kerf` above "
                f"{opt['kerf']:.2f} mm and reprint one family to check before "
                "committing to the set.",
            ],
        )

    def _wedge(self, denominator: int, opt, report: Report):
        radius = opt["size"] / 2.0
        kerf = opt["kerf"]
        span = 360.0 / denominator

        if denominator == 1:
            profile = geom.circle(radius - kerf)
        else:
            # Pull the two straight edges in by half a kerf each, by rotating
            # the slice inward, and the arc in by a whole kerf. The angular
            # inset is the arc-length kerf divided by the radius, so a small
            # wedge is not eaten alive by it.
            inset_deg = math.degrees(kerf / 2.0 / max(radius, 1e-6))
            if span - 2.0 * inset_deg <= 1.0:
                raise ValueError(
                    f"1/{denominator} of a {opt['size']:.0f} mm circle is too "
                    f"narrow to take a {kerf:.2f} mm kerf. Make the circle "
                    "bigger or the kerf smaller."
                )
            profile = geom.sector(radius - kerf, -span / 2.0 + inset_deg,
                                  span / 2.0 - inset_deg)
        if opt["hub"] > 0:
            profile = profile - geom.circle(opt["hub"] / 2.0 + kerf)

        solid = geom.extrude(profile, opt["thickness"])
        # The whole circle has the middle to itself; a wedge has to fit its
        # label inside the chord at the radius the label sits on.
        if denominator == 1:
            at, room = (0.0, 0.0), radius * 0.7
        else:
            at = (radius * 0.55, 0.0)
            room = min(radius * 0.5,
                       2.0 * radius * 0.55
                       * math.sin(math.radians(span / 2.0)) * 0.9)
        solid = self._label(solid, opt, f"1/{denominator}", at=at, room=room,
                            report=report)
        return solid, (f"one {_ordinal_word(denominator)} of the circle"
                       if denominator > 1 else "the whole circle")

    def _bar(self, denominator: int, opt, report: Report):
        kerf = opt["kerf"]
        length = opt["size"] / denominator - kerf
        width = opt["bar_width"] - kerf
        if length <= 2.0:
            raise ValueError(
                f"1/{denominator} of a {opt['size']:.0f} mm bar is "
                f"{length:.1f} mm long once the kerf is off it. Make the bar "
                "longer or drop the larger denominators."
            )
        solid = common.plate(length, width, opt["thickness"], "round",
                             min(1.5, length / 4.0, width / 4.0))
        solid = self._label(solid, opt, f"1/{denominator}", at=(0.0, 0.0),
                            room=min(length * 0.8, width * 0.8), report=report)
        return solid, (f"one {_ordinal_word(denominator)} of the bar"
                       if denominator > 1 else "the whole bar")

    def _label(self, solid, opt, label: str, at, room: float,
               report: Report):
        if not opt["label"] or room <= 3.0:
            return solid
        shape, cap = text.fitted_line(label, room, opt["thickness"] * 1.6,
                                      18.0, min_cap=2.5)
        if shape.is_empty() or cap < 3.0:
            report.note(
                f"{label} was left off its piece: there is no room for a "
                "readable one at this size."
            )
            return solid
        shape = shape.translate([at[0], at[1] - cap / 2.0])
        return common.face_relief(solid, shape, opt["label_relief"],
                                  opt["label_depth"], opt["thickness"],
                                  0.2 if opt["label_relief"] == "raised" else 0.0)

    def slug(self, opt: dict[str, Any]) -> str:
        digits = str(opt["denominators"]).replace(",", "-").replace(" ", "")
        return f"fraction-{opt['style']}_{digits}_{opt['size']:g}mm"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        noun = "circles" if opt["style"] == "circle" else "bars"
        return (f"Fraction {noun} - {result.facts['pieces']} pieces, "
                f"{result.facts['families']}, {opt['size']:.0f} mm")


def _parse_denominators(raw: str) -> list[int]:
    values: list[int] = []
    for chunk in str(raw).replace(" ", "").split(","):
        if not chunk:
            continue
        try:
            value = int(chunk)
        except ValueError:
            raise ValueError(
                f"denominators: {chunk!r} is not a whole number. Write them "
                "like 1,2,3,4,6,8."
            ) from None
        if value < 1:
            raise ValueError(f"denominators: {value} is not a denominator")
        if value > 24:
            raise ValueError(
                f"denominators: 1/{value} of a hand-sized circle is a sliver "
                "no child can pick up. 24 is the limit."
            )
        if value not in values:
            values.append(value)
    if not values:
        raise ValueError("denominators is empty; try 1,2,3,4,6,8")
    return sorted(values)


_ORDINALS = {
    1: "whole", 2: "half", 3: "third", 4: "quarter", 5: "fifth", 6: "sixth",
    7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh",
    12: "twelfth", 16: "sixteenth", 20: "twentieth", 24: "twenty-fourth",
}


def _ordinal_word(denominator: int) -> str:
    return _ORDINALS.get(denominator, f"1/{denominator}")


def _ordinal_name(denominator: int) -> str:
    return f"{denominator:02d}_one-{_ORDINALS.get(denominator, str(denominator))}"


register(FractionSetGenerator())
