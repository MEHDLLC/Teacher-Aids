"""Racks for markers, pens, brushes and glue sticks.

The bore diameter is the whole part.  Too tight and the marker will not go in;
too loose and a rack of them looks like a bin of them.  Every bore here comes
from a preset that says where its number came from and how sure it is, and
`clearance` is the single option that adjusts all of them at once.

Bores are tilted so the contents lean toward you and can be read and grabbed.
That tilt is also what stops the bore being a vertical hole a marker drops
straight through: the whole thing prints upright with no ceiling anywhere,
because every bore is open at the top and floored at the bottom.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, presets, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("bore", presets.DEFAULT_BORE, "What the rack is sized to hold",
           kind="choice", choices=presets.bore_keys(), group="Content"),
    Option("diameter", None,
           "Bore diameter, overriding the preset. Measure the barrel of the "
           "one on your desk and put that here", unit=" mm", minimum=4.0,
           maximum=45.0, group="Content", default_note="from the preset"),
    Option("columns", 6, "Bores across", kind="int", minimum=1, maximum=20,
           group="Layout"),
    Option("rows", 2, "Bores front to back", kind="int", minimum=1, maximum=8,
           group="Layout"),
    Option("stagger", True,
           "Offset alternate rows, so a back row is reachable between the "
           "fronts of the row in front", kind="bool", group="Layout"),

    Option("clearance", 1.2,
           "Added to the bore diameter, so a marker drops in rather than has "
           "to be pushed", unit=" mm", minimum=0.2, maximum=4.0, group="Fit"),
    Option("tilt", 12.0,
           "How far the bores lean back from vertical. Enough to see what is "
           "in them, not enough to make an overhang", unit=" deg",
           minimum=0.0, maximum=30.0, group="Fit"),
    Option("depth_fraction", 0.42,
           "How much of the marker's length sits in the rack", minimum=0.15,
           maximum=0.85, group="Fit"),

    Option("wall", 3.0, "Material between one bore and the next", unit=" mm",
           minimum=1.2, maximum=10.0, group="Size"),
    Option("floor", 3.0, "Thickness under the bottom of a bore", unit=" mm",
           minimum=1.2, maximum=10.0, group="Size"),
    Option("label", "", "Text embossed on the front face", kind="str",
           group="Detail"),
    Option("label_height", 10.0, "Height of the label lettering", unit=" mm",
           minimum=4.0, maximum=30.0, group="Detail"),
    *common.corner_options(4.0),
    common.material_option(),
])


class MarkerRackGenerator(Generator):
    key = "marker-rack"
    category = "organization"
    title = "Marker and pen rack"
    summary = (
        "A tilted rack for dry-erase markers, pens, brushes or glue sticks, "
        "with the bore sized from a named preset that says how confident that "
        "number is -- and one clearance option to adjust the lot."
    )
    tags = ("marker holder", "pen holder", "whiteboard", "classroom storage",
            "desk organizer", "teacher", "parametric", "3d printing")
    ages = "any"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        spec = presets.get_bore(opt["bore"])
        barrel = opt["diameter"] or spec.diameter
        bore = barrel + opt["clearance"]
        wall = opt["wall"]

        pitch = bore + wall
        tilt = math.radians(opt["tilt"])
        sink = spec.length * opt["depth_fraction"]
        height = sink * math.cos(tilt) + opt["floor"]
        # The bore leans back, so the block has to be deeper than the bores
        # by however far the top of the bore has travelled.
        lean = sink * math.sin(tilt)

        width = opt["columns"] * pitch + wall
        depth = opt["rows"] * pitch + wall + lean

        common.check_features(report, wall, 0.0, wall)
        if opt["tilt"] > 25.0:
            report.warn(
                f"a {opt['tilt']:.0f} degree tilt puts the underside of each "
                "bore past 45 degrees from vertical, which is where it starts "
                "needing support. Keep it under about 25."
            )
        if spec.confidence != "published" and opt["diameter"] is None:
            report.warn(
                f"the {spec.label} bore is a {spec.confidence} figure, not a "
                f"published one. Measure your barrel and pass "
                f"--diameter if the fit matters."
            )

        parts = PartSet()
        parts.add("rack", self._rack(opt, bore, pitch, width, depth, height,
                                     tilt, sink, lean, report),
                  note=f"{opt['columns'] * opt['rows']} bores at "
                       f"{bore:.1f} mm")

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": 1,
                "outside_mm": [round(width, 1), round(depth, 1),
                               round(height, 1)],
                "capacity": f"{opt['columns'] * opt['rows']} x {spec.label}",
                "bore_mm": round(bore, 2),
                "supports": "none",
                "fit_source": (
                    f"{spec.label}: barrel {spec.diameter:.1f} mm, length "
                    f"{spec.length:.0f} mm. {spec.source}"
                    if opt["diameter"] is None else
                    f"Bore set by hand to {opt['diameter']:.1f} mm, plus "
                    f"{opt['clearance']:.1f} mm clearance."
                ),
                "fit_confidence": (spec.confidence if opt["diameter"] is None
                                   else "measured"),
                "fit_notes": (
                    f"The bore is cut at {bore:.1f} mm: the "
                    f"{barrel:.1f} mm barrel plus {opt['clearance']:.1f} mm. "
                    "If it is tight, print one column as a test and raise "
                    "`clearance` before committing to the whole rack."
                ),
            },
            highlights=[
                f"{opt['columns'] * opt['rows']} bores at {bore:.1f} mm, for "
                f"{spec.label.lower()}.",
                f"Leaned back {opt['tilt']:.0f} degrees, so you can see which "
                "colour is which without picking them all up.",
                "Back rows offset by half a pitch, so a marker in the back is "
                "reachable between two in the front."
                if opt["stagger"] and opt["rows"] > 1 else
                "Bores in a straight grid.",
                f"{width:.0f} x {depth:.0f} x {height:.0f} mm on the desk.",
            ],
            teaching_notes=[
                "One at the board and one on each table: markers that have a "
                "place come back to it.",
                "Label it and the count is visible -- a gap is a marker "
                "somebody still has.",
            ],
            print_notes=[
                "Upright as supplied, bores facing up, no supports.",
                f"Every bore is open at the top and floored at the bottom, "
                f"and the {opt['tilt']:.0f} degree lean is well inside what "
                "prints unsupported, so nothing here bridges.",
                "0.2 mm layers, 3 perimeters, 15% infill.",
                "PETG if it lives by the board and gets knocked; PLA is fine "
                "on a desk.",
            ],
        )

    def _rack(self, opt, bore: float, pitch: float, width: float,
              depth: float, height: float, tilt: float, sink: float,
              lean: float, report: Report):
        wall = opt["wall"]
        body = common.plate(width, depth, height, opt["corner"],
                            opt["corner_size"], centred=False)

        cutters = []
        for row in range(opt["rows"]):
            offset = (pitch / 2.0 if opt["stagger"] and row % 2 else 0.0)
            # A staggered row is half a pitch over, so it needs the rack to be
            # wide enough for it; the last bore of an odd row would otherwise
            # hang off the end.
            columns = opt["columns"] - (1 if offset and opt["columns"] > 1
                                        else 0)
            for column in range(columns):
                x = wall + bore / 2.0 + offset + column * pitch
                y = wall + bore / 2.0 + row * pitch
                cutters.append(self._bore(bore, sink, tilt, x, y,
                                          opt["floor"]))
        solid = geom.difference(body, cutters)

        if opt["label"]:
            shape, cap = text.fitted_line(opt["label"], width * 0.8,
                                          opt["label_height"], min_cap=4.0)
            if not shape.is_empty():
                # Stood on the front face and left standing 1 mm proud of
                # it, with 0.4 mm buried so the two really are one solid.
                plaque = geom.extrude(shape, 1.4, taper=0.25)
                plaque = plaque.rotate([90, 0, 0]).translate(
                    [width / 2.0, 0.4, max(height * 0.45, cap * 0.7)])
                solid = geom.union([solid, plaque])

        if not geom.is_one_piece(solid):
            raise ValueError(
                "the rack came apart: the bores have met each other. Thicken "
                "`wall`, or cut `clearance`."
            )
        return solid

    def _bore(self, bore: float, sink: float, tilt: float, x: float, y: float,
              floor: float):
        """One leaning bore, open at the top, floored `floor` above the bed."""
        cylinder = geom.cylinder_z(bore / 2.0, 0.0, sink + 40.0)
        # Negative, so the top of the bore travels toward +Y -- backward, away
        # from the user. That is the direction the block was made deeper in:
        # lean them forward instead and the top of every bore comes straight
        # out through the front wall.
        leaned = cylinder.rotate([-math.degrees(tilt), 0, 0])
        return leaned.translate([x, y, floor])

    def slug(self, opt: dict[str, Any]) -> str:
        return (f"marker-rack_{opt['bore']}_{opt['columns']}x{opt['rows']}"
                f"_tilt{opt['tilt']:g}")

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        spec = presets.get_bore(opt["bore"])
        return (f"{spec.label} rack - {opt['columns'] * opt['rows']} bores, "
                f"{result.facts['outside_mm'][0]:.0f} x "
                f"{result.facts['outside_mm'][1]:.0f} mm")


register(MarkerRackGenerator())
