"""A teaching clock with hands that turn.

The thing that makes a teaching clock teach is the minute ring: a child who
can read "3" on the hour ring still has to be told that the same mark means
fifteen minutes, and a clock that prints both numbers in two sizes says it
without anyone having to.

The hands turn on a post printed as part of the dial, held on by a cap that
presses over a barb.  Nothing here needs a screw, and the fit is one option
(`press_fit`) rather than something you discover after printing.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("diameter", 150.0, "Dial diameter", unit=" mm", minimum=60.0,
           maximum=300.0, group="Size"),
    Option("thickness", 4.0, "Dial thickness", unit=" mm", minimum=2.0,
           maximum=15.0, group="Size"),
    Option("hand_thickness", 3.0, "Hand thickness", unit=" mm", minimum=1.5,
           maximum=10.0, group="Size"),

    Option("minute_numbers", True,
           "Print the minute count (5, 10, 15...) outside the hour numbers, "
           "which is the whole difficulty of reading a clock",
           kind="bool", group="Dial"),
    Option("minute_ticks", True, "A tick for every minute", kind="bool",
           group="Dial"),
    Option("hour_ring", True,
           "A raised ring separating the hour numbers from the minute ones",
           kind="bool", group="Dial"),
    Option("relief", "raised", "Whether the dial markings stand off or sink in",
           kind="choice", choices=("raised", "recessed"), group="Dial"),
    Option("relief_depth", 1.2, "How far the markings stand off or sink in",
           unit=" mm", minimum=0.3, maximum=4.0, group="Dial"),
    Option("hour_cap", 0.0,
           "Height of the hour numerals. Zero sizes them from the dial",
           unit=" mm", minimum=0.0, maximum=60.0, group="Dial",
           default_note="12.5% of the diameter"),

    Option("hand_style", "arrow", "Shape of the hands",
           kind="choice", choices=("arrow", "plain"), group="Hands"),
    Option("hour_hand", 0.52, "Hour hand length, as a fraction of the radius",
           minimum=0.2, maximum=0.9, group="Hands"),
    Option("minute_hand", 0.84,
           "Minute hand length, as a fraction of the radius", minimum=0.3,
           maximum=1.0, group="Hands"),
    Option("hand_width", 0.09,
           "Hand width at the boss, as a fraction of the radius",
           minimum=0.03, maximum=0.25, group="Hands"),

    Option("post", 8.0, "Diameter of the post the hands turn on", unit=" mm",
           minimum=4.0, maximum=20.0, group="Fit"),
    Option("turn_clearance", 0.35,
           "Gap between the post and a hand's hole, so the hands turn freely",
           unit=" mm", minimum=0.1, maximum=1.0, group="Fit"),
    Option("press_fit", 0.12,
           "How much the cap is undersized on the post, so it stays put. "
           "Raise it if the cap falls off, lower it if it will not go on",
           unit=" mm", minimum=0.0, maximum=0.6, group="Fit"),
    Option("hang_hole", 9.0,
           "Diameter of the keyhole recessed into the back, for hanging the "
           "clock on a screw. Zero leaves it out", unit=" mm", minimum=0.0,
           maximum=20.0, group="Fit"),
    common.material_option(),
])


class ClockFaceGenerator(Generator):
    key = "clock-face"
    category = "math"
    title = "Teaching clock"
    summary = (
        "A geared-down-to-nothing teaching clock: hour numbers inside, minute "
        "numbers outside, sixty ticks between them, and two hands that turn "
        "on a printed post with no screw and no glue."
    )
    tags = ("clock", "telling time", "math", "manipulative", "numeracy",
            "classroom", "teaching aid", "parametric")
    ages = "5-9"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        radius = opt["diameter"] / 2.0
        hour_cap = opt["hour_cap"] or opt["diameter"] * 0.125

        common.check_features(report, opt["thickness"], opt["relief_depth"],
                              hour_cap * 0.18)
        if opt["minute_numbers"] and opt["diameter"] < 90.0:
            report.warn(
                f"a {opt['diameter']:.0f} mm dial has to fit two rings of "
                "numbers into very little space. Below about 90 mm the minute "
                "numbers stop being readable; consider minute_numbers=no."
            )

        parts = PartSet()
        parts.add("1_dial", self._dial(opt, radius, hour_cap, report),
                  note=f"{opt['diameter']:.0f} mm, with the post moulded in")
        parts.add("2_hand_hour",
                  self._hand(opt, radius * opt["hour_hand"], opt, short=True),
                  note="the short one")
        parts.add("3_hand_minute",
                  self._hand(opt, radius * opt["minute_hand"], opt, short=False),
                  note="the long one")
        parts.add("4_cap", self._cap(opt),
                  note="presses onto the post to hold the hands on")

        stack = opt["hand_thickness"] * 2.0
        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": 4,
                "outside_mm": [opt["diameter"], opt["diameter"],
                               opt["thickness"] + stack + 3.0],
                "piece_mm": list(parts.parts[0].size),
                "hour_cap_mm": round(hour_cap, 1),
                "post_mm": opt["post"],
                "supports": "none",
                "fit_source": (
                    f"The hands turn on a post {opt['post']:.1f} mm across "
                    f"with {opt['turn_clearance']:.2f} mm of clearance, and "
                    f"the cap is {opt['press_fit']:.2f} mm undersize so it "
                    "presses on. Both are options: printers differ by more "
                    "than this."
                ),
                "fit_confidence": "typical",
            },
            highlights=[
                f"A {opt['diameter']:.0f} mm dial with hour numbers inside "
                "and minute numbers outside, which is the bit that actually "
                "has to be learned." if opt["minute_numbers"] else
                f"A {opt['diameter']:.0f} mm dial with the twelve hours.",
                "Sixty ticks, with the five-minute marks longer, so a minute "
                "can be counted off rather than guessed."
                if opt["minute_ticks"] else
                "A clean dial with no ticks.",
                "Four parts, no hardware: the hands drop over a post printed "
                "into the dial and a cap presses on to hold them.",
                "The hands are different lengths and different shapes, so "
                "which is which is never in doubt.",
            ],
            teaching_notes=[
                "Set a time and read it; read a time and set it. Doing it "
                "backwards is what catches the child who has memorised "
                "positions.",
                "Turn the minute hand a full circle and watch the hour hand "
                "not move: the two hands being independent is a limitation "
                "worth naming out loud, and worth turning into the question "
                "'where should the hour hand really be at half past?'",
                "The minute numbers make 'quarter past' and 'fifteen minutes' "
                "the same mark, which is the confusion this dial exists to "
                "remove.",
            ],
            print_notes=[
                "All four parts flat on the bed, no supports.",
                "Dial in one colour, hands in another. A hand the same colour "
                "as the dial is invisible across a classroom.",
                "0.2 mm layers, 3 perimeters.",
                f"If the cap will not press on, sand the top of the post or "
                f"rerun with press_fit below {opt['press_fit']:.2f} mm. If the "
                "hands are stiff, raise turn_clearance.",
                "The hands are meant to be a friction fit against each other "
                "and the cap: too loose and they drift, too tight and a child "
                "cannot move them.",
            ],
        )

    # -- parts ------------------------------------------------------------

    def _dial(self, opt, radius: float, hour_cap: float,
              report: Report) -> geom.Solid:
        thickness = opt["thickness"]
        body = geom.extrude(geom.circle(radius), thickness)

        marks: list[Any] = []
        minute_cap = hour_cap * 0.45
        # Rings, from the rim inward. Each ring is placed by measuring the
        # labels that go on it, not by guessing: a two-digit minute number at
        # three o'clock reaches sideways by half its width, and a ring sized
        # from the cap height alone hangs "15" over the edge of the dial.
        cursor = radius - 2.0
        if opt["minute_numbers"]:
            labels = [_label(f"{(step * 5) % 60:02d}", minute_cap * 2.2,
                             minute_cap, min_cap=2.0) for step in range(12)]
            reach = max(_reach(shape) for shape, _ in labels)
            minute_radius = cursor - reach
            for step, (shape, cap) in enumerate(labels):
                if not shape.is_empty():
                    marks.append(_at_clock(shape, step, minute_radius, cap))
            cursor = minute_radius - reach - minute_cap * 0.25

        if opt["minute_ticks"]:
            long_tick = min(radius * 0.05, 5.0)
            for minute in range(60):
                is_hour = minute % 5 == 0
                length = long_tick if is_hour else long_tick * 0.55
                width = long_tick * (0.36 if is_hour else 0.20)
                angle = 90.0 - minute * 6.0
                marks.append(geom.capsule(
                    _polar(cursor, angle), _polar(cursor - length, angle),
                    width / 2.0))
            cursor -= long_tick

        if opt["hour_ring"]:
            band = min(radius * 0.012, 1.2)
            marks.append(geom.ring(cursor, cursor - band))
            cursor -= band * 2.0

        hour_labels = [_label(str(12 if step == 0 else step), hour_cap * 1.6,
                              hour_cap, min_cap=3.0) for step in range(12)]
        hour_reach = max(_reach(shape) for shape, _ in hour_labels)
        hour_radius = max(cursor - hour_reach, opt["post"])
        for step, (shape, cap) in enumerate(hour_labels):
            if not shape.is_empty():
                marks.append(_at_clock(shape, step, hour_radius, cap))

        if hour_radius - hour_reach < opt["post"] * 0.9:
            report.warn(
                "the hour numbers reach almost to the post. Grow the dial, "
                "shrink hour_cap, or turn off the minute numbers."
            )

        field = geom.shape_union(marks)
        solid = common.face_relief(body, field, opt["relief"],
                                   opt["relief_depth"], thickness,
                                   0.25 if opt["relief"] == "raised" else 0.0)

        # The post, and the barb the cap grips.
        post_top = thickness + opt["hand_thickness"] * 2.0 + 1.6
        post = geom.cylinder_z(opt["post"] / 2.0, thickness, post_top)
        barb = geom.cone_z(opt["post"] / 2.0 + 0.45, opt["post"] / 2.0,
                           post_top - 1.6, post_top)
        solid = geom.union([solid, post, barb])

        if opt["hang_hole"] > 0:
            solid = self._keyhole(solid, opt, radius, report)

        if not geom.is_one_piece(solid):
            raise ValueError(
                "the dial came out in pieces. Reduce relief_depth, or use "
                "relief=raised so the markings sit on the face instead of "
                "cutting into it."
            )
        return solid

    def _keyhole(self, solid, opt, radius: float, report: Report):
        """A keyhole slot in the *back*, so the face keeps all its numbers.

        A hole punched through the top of the dial lands on the twelve at any
        sensible size. Recessing a keyhole into the back hangs the clock on a
        screw and leaves the face alone.
        """
        head = opt["hang_hole"]
        depth = min(opt["thickness"] * 0.55, 2.5)
        floor = opt["thickness"] - depth
        if floor < 1.0:
            report.warn(
                f"a keyhole {depth:.1f} mm into a {opt['thickness']:.1f} mm "
                "dial would leave under a millimetre of face. It was left "
                "out; thicken the dial to hang it."
            )
            return solid
        centre_y = radius - head - 6.0
        pocket = geom.cylinder_z(head / 2.0, -0.01, depth, (0.0, centre_y))
        neck = geom.extrude(
            geom.capsule((0.0, centre_y), (0.0, centre_y + head * 0.9),
                         head * 0.28), depth + 0.01, at_z=-0.01)
        return geom.difference(solid, [pocket, neck])

    def _hand(self, opt, length: float, _o, short: bool) -> geom.Solid:
        radius = opt["diameter"] / 2.0
        boss = opt["post"] / 2.0 + max(opt["hand_thickness"], 2.2)
        width = radius * opt["hand_width"]
        tail = boss * 1.15

        if opt["hand_style"] == "arrow":
            head = length
            neck = length - width * 1.5
            outline = geom.polygon([
                (-tail, -width * 0.45), (neck, -width * 0.75),
                (head, 0.0), (neck, width * 0.75), (-tail, width * 0.45),
            ])
        else:
            outline = geom.capsule((-tail * 0.5, 0.0), (length, 0.0),
                                   width * 0.5)

        profile = geom.shape_union([outline, geom.circle(boss)])
        hole = geom.circle(opt["post"] / 2.0 + opt["turn_clearance"])
        solid = geom.extrude(profile - hole, opt["hand_thickness"])
        # The short hand gets a notch out of its tail so the two are told
        # apart by feel as well as by length.
        if short:
            solid = geom.difference(solid, geom.cylinder_z(
                width * 0.35, -1.0, opt["hand_thickness"] + 1.0,
                (-tail * 0.55, 0.0)))
        if not geom.is_one_piece(solid):
            raise ValueError("a hand came apart; widen hand_width")
        return solid

    def _cap(self, opt) -> geom.Solid:
        outer = opt["post"] / 2.0 + max(opt["hand_thickness"], 2.5)
        height = 3.2
        bore = opt["post"] / 2.0 - opt["press_fit"]
        body = geom.union([
            geom.cylinder_z(outer, 0.0, 1.6),
            geom.cone_z(outer, outer * 0.72, 1.6, height),
        ])
        return geom.difference(body, geom.cylinder_z(bore, -0.01, height - 1.0))

    def slug(self, opt: dict[str, Any]) -> str:
        return f"clock-face_{opt['diameter']:g}mm_{opt['hand_style']}"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        return (f"Teaching clock - {opt['diameter']:.0f} mm dial, "
                + ("hour and minute numbers" if opt["minute_numbers"]
                   else "hour numbers") + ", turning hands")


def _polar(radius: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return (radius * math.cos(angle), radius * math.sin(angle))


def _label(value: str, max_width: float, max_cap: float, min_cap: float):
    return text.fitted_line(value, max_width, max_cap, 18.0, min_cap=min_cap)


def _reach(shape) -> float:
    """Half the largest dimension of a label: how far it sticks out from its
    own centre in the worst direction, whichever way round the dial it sits."""
    if shape.is_empty():
        return 0.0
    width, height = geom.shape_size(shape)
    return max(width, height) / 2.0


def _at_clock(shape, step: int, radius: float, cap: float):
    """Put a centred label at the `step`-of-twelve position, upright."""
    x, y = _polar(radius, 90.0 - step * 30.0)
    return shape.translate([x, y - cap / 2.0])


register(ClockFaceGenerator())
