"""Letter, number and word stencils.

A stencil is the one thing in this repo where the geometry can be *correct*
and the object still useless: cut an O clean through and the middle falls out
on the first print.  Every enclosed counter therefore gets a bridge, and the
bridge width is an option because it trades legibility against how likely a
child is to snap it.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("charset", "uppercase",
           "Characters to make stencils for, when mode is cards. A named set, "
           "a range like A-M, or the literal characters",
           kind="str", group="Content"),
    Option("text", "", "A word or phrase, when mode is strip", kind="str",
           group="Content"),
    Option("mode", "cards",
           "cards makes one stencil per character; strip puts the whole of "
           "`text` on a single stencil",
           kind="choice", choices=("cards", "strip"), group="Content"),
    Option("max_cards", 30, "Stop after this many cards", kind="int",
           minimum=1, maximum=120, group="Content"),

    Option("cap_height", 45.0, "Height of the cut-out letter", unit=" mm",
           minimum=8.0, maximum=250.0, group="Size"),
    Option("weight", 0.22,
           "Stroke thickness as a fraction of the letter height. A stencil "
           "wants a heavier stroke than a tile: thin cut-outs are what tear",
           minimum=0.10, maximum=0.40, group="Size"),
    Option("border", 10.0, "Frame of plate left around the cut-outs",
           unit=" mm", minimum=3.0, maximum=60.0, group="Size"),
    Option("thickness", 2.0, "Plate thickness", unit=" mm", minimum=0.8,
           maximum=8.0, group="Size"),
    Option("tracking", 0.20,
           "Gap between letters on a strip, as a fraction of letter height",
           minimum=0.0, maximum=1.0, group="Size"),

    Option("bridge", 3.5,
           "Width of the tabs holding the middle of an O in place. Wider is "
           "stronger and less like the letter", unit=" mm", minimum=0.8,
           maximum=12.0, group="Cutting"),

    *common.corner_options(6.0),
    Option("hole", 5.0,
           "Hole through the frame for hanging the set on a ring. Zero leaves "
           "it out", unit=" mm", minimum=0.0, maximum=20.0, group="Mounting"),
    common.material_option(),
])


class StencilGenerator(Generator):
    key = "stencil"
    category = "alphabet"
    title = "Letter and word stencils"
    summary = (
        "Stencil cards for tracing, painting and chalking letters, numbers "
        "and words, with the bridges that stop the middle of an O falling out "
        "built into the model."
    )
    tags = ("stencil", "alphabet", "letters", "handwriting", "art",
            "classroom", "teaching aid", "parametric")
    ages = "4-10"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        cap = opt["cap_height"]
        weight = opt["weight"] * 100.0
        stroke_mm = cap * opt["weight"]

        common.check_features(report, opt["thickness"], 0.0, stroke_mm,
                              "cut-out")
        if opt["bridge"] > stroke_mm * 0.8:
            report.warn(
                f"a {opt['bridge']:.1f} mm bridge across a {stroke_mm:.1f} mm "
                "stroke closes most of the letter. Narrow the bridge or raise "
                "the weight."
            )

        parts = PartSet()
        if opt["mode"] == "strip":
            phrase = opt["text"].strip()
            if not phrase:
                raise ValueError(
                    "mode is strip, so `text` has to say what to cut. "
                    "Use mode=cards to stencil a whole character set instead."
                )
            parts.add(_safe_name("strip_" + phrase),
                      self._strip(phrase, opt, cap, weight, report),
                      note=f"the whole of {phrase!r} on one plate")
            characters = phrase
        else:
            characters = text.expand_charset(opt["charset"])
            if len(characters) > opt["max_cards"]:
                dropped = characters[opt["max_cards"]:]
                characters = characters[: opt["max_cards"]]
                report.warn(
                    f"charset {opt['charset']!r} is more than max_cards "
                    f"({opt['max_cards']}), so this set leaves out "
                    + " ".join(dropped) + ". Raise max_cards to build the rest."
                )
            for char in characters:
                parts.add(_safe_name("stencil_" + char),
                          self._card(char, opt, cap, weight, report),
                          note=f"the letter {char}")

        first = parts.parts[0]
        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "characters": " ".join(characters),
                "pieces": len(parts),
                "piece_mm": list(first.size),
                "cap_height_mm": cap,
                "stroke_mm": round(stroke_mm, 2),
                "bridge_mm": opt["bridge"],
                "supports": "none",
            },
            highlights=[
                f"{len(parts)} stencil"
                + ("s" if len(parts) != 1 else "")
                + f", {cap:.0f} mm letters cut through a "
                  f"{opt['thickness']:.1f} mm plate.",
                f"{opt['bridge']:.1f} mm bridges hold the middle of every O, "
                "A, B, D, P, Q, R, 0, 4, 6, 8 and 9 -- worked out from the "
                "letter itself, not hand-placed, so they land in the same "
                "place at any size.",
                "Flat, so it lies down on paper and does not rock.",
            ],
            teaching_notes=[
                "Trace inside the cut-out with a pencil, then lift and write "
                "it freehand next to it.",
                "Sponge or stipple paint through it -- dab, do not brush, or "
                "paint runs under the edge.",
                "Chalk through it on a playground, or press it into damp sand.",
            ],
            print_notes=[
                "Flat on the bed, no supports.",
                "The bridges are part of the letter. Cutting them off after "
                "printing loses the middle of the O.",
                "0.2 mm layers, 4 perimeters. A stencil is nearly all "
                "perimeter, so infill barely matters.",
                "Print in a colour that contrasts with the paper, so the "
                "child can see where the cut-out is.",
            ],
        )

    def _card(self, char: str, opt, cap: float, weight: float,
              report: Report):
        glyph = text.line_shape(char, cap, weight, align="centre")
        return self._plate_around(glyph, opt, report)

    def _strip(self, phrase: str, opt, cap: float, weight: float,
               report: Report):
        glyph = text.line_shape(phrase, cap, weight,
                               tracking=opt["tracking"] * 100.0,
                               align="centre")
        return self._plate_around(glyph, opt, report)

    def _plate_around(self, glyph, opt, report: Report):
        x0, y0, x1, y1 = geom.shape_bounds(glyph)
        glyph = glyph.translate([-(x0 + x1) / 2.0, -(y0 + y1) / 2.0])
        width = (x1 - x0) + 2.0 * opt["border"]
        depth = (y1 - y0) + 2.0 * opt["border"]

        body = common.plate(width, depth, opt["thickness"], opt["corner"],
                            min(opt["corner_size"], opt["border"] * 0.8))
        cut = text.stencil_cut(glyph, opt["bridge"])
        plate_solid = common.face_relief(body, cut, "cut", opt["thickness"],
                                         opt["thickness"])

        if opt["hole"] > 0:
            inset = opt["hole"] / 2.0 + min(opt["border"] * 0.4, 4.0)
            if inset + opt["hole"] / 2.0 <= opt["border"]:
                plate_solid = geom.difference(plate_solid, common.hang_hole(
                    opt["hole"], opt["thickness"],
                    (-width / 2.0 + inset, depth / 2.0 - inset)))
            else:
                report.warn(
                    f"a {opt['hole']:.0f} mm hanging hole does not fit in a "
                    f"{opt['border']:.0f} mm border, so it was left out."
                )

        if not geom.is_one_piece(plate_solid):
            raise ValueError(
                "this stencil came out in "
                f"{len(plate_solid.decompose())} pieces. Widen `bridge`, or "
                "raise `weight` so the strokes are thicker than the tabs."
            )
        return plate_solid

    def slug(self, opt: dict[str, Any]) -> str:
        if opt["mode"] == "strip":
            return f"stencil_strip_{_safe_name(opt['text'])[:24]}"
        safe = "".join(c if c.isalnum() or c == "-" else "x"
                       for c in str(opt["charset"]).lower())
        return f"stencil_{safe[:16]}_{opt['cap_height']:g}mm"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        if opt["mode"] == "strip":
            return f"{opt['text']!r} stencil - {opt['cap_height']:.0f} mm letters"
        return (f"Letter stencils - {result.facts['pieces']} cards, "
                f"{opt['cap_height']:.0f} mm letters")


def _safe_name(raw: str) -> str:
    out = []
    for char in raw:
        if char.isalnum():
            out.append(char if char.isascii() else "u")
        elif char in " -_":
            out.append("-")
    name = "".join(out).strip("-") or "stencil"
    # A and a would collide on a case-insensitive disk, so say which.
    if len(raw) == 1 and raw.isalpha():
        name = f"{raw.upper()}-{'upper' if raw.isupper() else 'lower'}"
    return name


register(StencilGenerator())
