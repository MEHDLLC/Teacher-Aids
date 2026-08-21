"""Ten frames and counters.

A ten frame is two rows of five, and the reason it works is that five is
visible without counting.  Everything here follows from that: the cells are
square so the counters sit centred, the middle wall is thicker than the rest
so the two fives read as two fives, and the counters are one clearance under
the cell so a five-year-old can drop them in rather than aim them.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("rows", 2, "Rows of cells", kind="int", minimum=1, maximum=10,
           group="Layout"),
    Option("columns", 5, "Cells per row", kind="int", minimum=2, maximum=12,
           group="Layout"),
    Option("split_after", 5,
           "Put the heavier dividing wall after this many columns, so the "
           "frame reads as groups. Zero makes every wall the same",
           kind="int", minimum=0, maximum=12, group="Layout"),
    Option("numbers", "none",
           "Engrave a number in every cell: counting up 1..n, or the same "
           "number in each row",
           kind="choice", choices=("none", "count", "per-row"),
           group="Layout"),

    Option("cell", 26.0, "Inside size of one square cell", unit=" mm",
           minimum=12.0, maximum=60.0, group="Size"),
    Option("wall", 3.0, "Thickness of the walls between cells", unit=" mm",
           minimum=1.2, maximum=10.0, group="Size"),
    Option("split_wall", 5.0,
           "Thickness of the heavier dividing wall", unit=" mm", minimum=1.2,
           maximum=16.0, group="Size"),
    Option("base", 2.4, "Thickness of the tray floor", unit=" mm",
           minimum=1.0, maximum=8.0, group="Size"),
    Option("rim", 3.0, "How far the walls stand above the floor", unit=" mm",
           minimum=1.0, maximum=15.0, group="Size"),

    Option("counters", True, "Also make the counters that go in it",
           kind="bool", group="Counters"),
    Option("counter_thickness", 4.0, "Counter thickness", unit=" mm",
           minimum=1.5, maximum=15.0, group="Counters"),
    Option("counter_clearance", 1.2,
           "Gap between a counter and its cell, per side. Small hands need "
           "this to be generous", unit=" mm", minimum=0.2, maximum=4.0,
           group="Counters"),
    Option("spare_counters", 2,
           "Extra counters beyond one per cell, because they get lost",
           kind="int", minimum=0, maximum=40, group="Counters"),

    *common.corner_options(4.0),
    common.material_option(),
])


class TenFrameGenerator(Generator):
    key = "ten-frame"
    category = "math"
    title = "Ten frame and counters"
    summary = (
        "The two-by-five frame that makes small numbers visible without "
        "counting, with a heavier wall down the middle and a set of counters "
        "sized to drop in rather than be aimed."
    )
    tags = ("ten frame", "subitising", "counting", "math", "manipulative",
            "numeracy", "early years", "classroom", "teaching aid")
    ages = "4-8"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        rows, columns = opt["rows"], opt["columns"]
        cell, wall = opt["cell"], opt["wall"]
        split_at = opt["split_after"] if 0 < opt["split_after"] < columns else 0
        split_wall = opt["split_wall"] if split_at else wall

        widths = [wall]
        for column in range(columns):
            widths.append(cell)
            widths.append(split_wall if column + 1 == split_at else wall)
        width = sum(widths)
        depth = rows * cell + (rows + 1) * wall
        height = opt["base"] + opt["rim"]

        common.check_features(report, opt["base"], 0.0, wall)
        counter_diameter = cell - 2.0 * opt["counter_clearance"]
        if counter_diameter < 8.0:
            raise ValueError(
                f"a {cell:.0f} mm cell with {opt['counter_clearance']:.1f} mm "
                f"clearance leaves a {counter_diameter:.1f} mm counter, which "
                "is too small to pick up. Grow the cell or cut the clearance."
            )

        parts = PartSet()
        parts.add("frame", self._frame(opt, widths, width, depth, height,
                                       split_at, report),
                  note=f"{rows} x {columns} cells, {cell:.0f} mm each")

        if opt["counters"]:
            counter = geom.extrude(
                geom.circle(counter_diameter / 2.0), opt["counter_thickness"])
            # Break the top edge so it is pleasant to pick up off a table.
            bevel = min(opt["counter_thickness"] * 0.25, 0.8)
            counter = geom.intersection(counter, geom.union([
                geom.cylinder_z(counter_diameter / 2.0, 0.0,
                                opt["counter_thickness"] - bevel),
                geom.cone_z(counter_diameter / 2.0,
                            counter_diameter / 2.0 - bevel,
                            opt["counter_thickness"] - bevel,
                            opt["counter_thickness"]),
            ]))
            parts.add("counter", counter,
                      note=f"{counter_diameter:.1f} mm across, drops into any "
                           "cell",
                      copies=rows * columns + opt["spare_counters"])

        common.check_small_parts(report, parts)
        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": parts.total_copies,
                "outside_mm": [round(width, 2), round(depth, 2), height],
                "piece_mm": [counter_diameter, counter_diameter,
                             opt["counter_thickness"]],
                "capacity": f"{rows * columns} counters",
                "supports": "none",
            },
            highlights=[
                f"{rows} x {columns} = {rows * columns} cells at "
                f"{cell:.0f} mm, in a {width:.0f} x {depth:.0f} mm frame.",
                f"A {split_wall:.0f} mm wall after the {_ordinal(split_at)} "
                f"cell against {wall:.0f} mm elsewhere, so the groups separate "
                "at a glance and nobody has to count past five."
                if split_at else
                f"A row is {columns} cells, which is the grouping -- no "
                "heavier wall is needed inside it.",
                f"{counter_diameter:.0f} mm counters with "
                f"{opt['counter_clearance']:.1f} mm of clearance a side: they "
                "drop in, they do not have to be aimed.",
                f"{opt['spare_counters']} spare counters, because they end up "
                "under the radiator." if opt["spare_counters"] else
                "Exactly one counter per cell.",
            ],
            teaching_notes=[
                "Subitising: fill some cells, cover it, ask how many. Five and "
                "ten get recognised long before they get counted.",
                "Number bonds to ten: fill some cells and ask how many empty. "
                "The frame answers the question itself.",
                "Adding past ten: two frames side by side is exactly how "
                "regrouping is meant to look.",
            ],
            print_notes=[
                "Both parts flat on the bed, no supports.",
                "Frame and counters in contrasting colours -- the whole point "
                "is that a filled cell looks different from an empty one.",
                "0.2 mm layers, 3 perimeters, 15% infill.",
                "Counters are quick and get lost. Print a plate of spares "
                "whenever the printer is otherwise idle.",
            ],
        )

    def _frame(self, opt, widths, width: float, depth: float, height: float,
               split_at: int, report: Report) -> geom.Solid:
        body = common.plate(width, depth, height, opt["corner"],
                            opt["corner_size"], centred=False)

        cutters = []
        wells: list[tuple[float, float]] = []
        x = widths[0]
        for column in range(opt["columns"]):
            y = opt["wall"]
            for row in range(opt["rows"]):
                cutters.append(geom.box(
                    [opt["cell"], opt["cell"], opt["rim"] + 0.01],
                    at=[x, y, opt["base"]]))
                wells.append((x + opt["cell"] / 2.0, y + opt["cell"] / 2.0))
                y += opt["cell"] + opt["wall"]
            x += opt["cell"] + widths[2 + column * 2]

        solid = geom.difference(body, cutters)
        solid = self._numbers(solid, opt, wells, report)
        if not geom.is_one_piece(solid):
            raise ValueError("the frame came apart; thicken `wall`")
        return solid

    def _numbers(self, solid, opt, wells, report: Report):
        if opt["numbers"] == "none":
            return solid
        rows, columns = opt["rows"], opt["columns"]
        shapes = []
        for index, (cx, cy) in enumerate(wells):
            # `wells` is filled column by column; a child counts along a row.
            column, row = divmod(index, rows)
            value = (column + 1 if opt["numbers"] == "per-row"
                     else row * columns + column + 1)
            shape, cap = text.fitted_line(
                str(value), opt["cell"] * 0.5, opt["cell"] * 0.45, 18.0,
                min_cap=3.0)
            if shape.is_empty():
                continue
            shapes.append(shape.translate([cx, cy - cap / 2.0]))
        if not shapes:
            return solid
        depth = min(opt["base"] * 0.4, 0.8)
        cutter = geom.extrude(geom.shape_union(shapes), depth + 0.01,
                              at_z=opt["base"] - depth)
        return geom.difference(solid, cutter)

    def slug(self, opt: dict[str, Any]) -> str:
        return (f"ten-frame_{opt['rows']}x{opt['columns']}"
                f"_{opt['cell']:g}mm")

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        return (f"{opt['rows']} x {opt['columns']} frame and "
                f"{result.parts.total_copies - 1} counters - "
                f"{opt['cell']:.0f} mm cells")


def _ordinal(value: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
            6: "sixth"}.get(value, f"{value}th")


register(TenFrameGenerator())
