"""Desk caddies and supply trays.

The compartment sizes are the whole design.  A caddy with six identical square
holes is what you get when nobody asked what goes in it; a classroom caddy
needs a long deep slot for the scissors, a wide shallow one for the glue
sticks and a fistful of small ones for pencils, and those wants are
irreconcilable in one grid.  So the columns are given as a list of widths and
the rows as a list of depths, and the grid falls out of them.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, patterns, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("columns", "1,1,1",
           "Relative widths of the compartments across the caddy. 2,1,1 makes "
           "the left one twice the width of the others", kind="str",
           group="Layout"),
    Option("rows", "1",
           "Relative depths of the compartments front to back", kind="str",
           group="Layout"),
    Option("handle", "none",
           "A handle across the caddy: a bar to carry it by, or a divider "
           "wall standing above the rim",
           kind="choice", choices=("none", "bar", "spine"), group="Layout"),

    Option("width", 150.0, "Outside width", unit=" mm", minimum=40.0,
           maximum=300.0, group="Size"),
    Option("depth", 90.0, "Outside depth", unit=" mm", minimum=40.0,
           maximum=300.0, group="Size"),
    Option("height", 90.0, "Outside height, not counting a handle", unit=" mm",
           minimum=20.0, maximum=250.0, group="Size"),
    Option("wall", 2.4, "Wall and divider thickness", unit=" mm", minimum=1.2,
           maximum=8.0, group="Size"),
    Option("floor", 2.4, "Floor thickness", unit=" mm", minimum=1.2,
           maximum=10.0, group="Size"),

    Option("pattern", "none",
           "Cut a pattern through the outside walls -- lighter, faster, and "
           "you can see what is in it",
           kind="choice", choices=("none",) + patterns.PATTERNS,
           group="Pattern"),
    Option("pattern_cell", None, "How big one repeat of the pattern is",
           unit=" mm", minimum=3.0, maximum=60.0, group="Pattern",
           default_note="per pattern"),
    Option("pattern_rib", None, "Web left between pattern cells", unit=" mm",
           minimum=1.0, maximum=20.0, group="Pattern", default_note="per pattern"),
    Option("pattern_margin", 8.0,
           "Solid band left at the top and bottom of a patterned wall",
           unit=" mm", minimum=2.0, maximum=40.0, group="Pattern"),

    Option("label", "", "Text embossed on the front. Empty leaves it plain",
           kind="str", group="Detail"),
    Option("label_height", 12.0, "Height of the label lettering", unit=" mm",
           minimum=4.0, maximum=40.0, group="Detail"),
    Option("drain", False,
           "Slots in the floor, so water and pencil shavings fall out instead "
           "of collecting", kind="bool", group="Detail"),
    *common.corner_options(6.0),
    common.material_option(),
])


class SupplyCaddyGenerator(Generator):
    key = "supply-caddy"
    category = "organization"
    title = "Desk caddy and supply tray"
    summary = (
        "A compartment tray sized by what goes in it rather than by a grid: "
        "give the columns and rows as relative widths and the dividers land "
        "where the scissors, glue sticks and pencils actually need them."
    )
    tags = ("desk organizer", "caddy", "supply tray", "classroom storage",
            "pencil holder", "teacher", "parametric", "3d printing")
    ages = "any"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        opt = dict(opt)
        if opt["pattern_cell"] is None:
            opt["pattern_cell"] = patterns.default_cell(opt["pattern"])
        if opt["pattern_rib"] is None:
            opt["pattern_rib"] = patterns.default_rib(opt["pattern"])

        columns = _parse_weights(opt["columns"], "columns")
        rows = _parse_weights(opt["rows"], "rows")
        wall, floor = opt["wall"], opt["floor"]
        width, depth, height = opt["width"], opt["depth"], opt["height"]

        inner_w = width - 2.0 * wall - (len(columns) - 1) * wall
        inner_d = depth - 2.0 * wall - (len(rows) - 1) * wall
        if inner_w <= 5.0 or inner_d <= 5.0:
            raise ValueError(
                f"{len(columns)} columns and {len(rows)} rows of "
                f"{wall:.1f} mm wall leave no room inside a "
                f"{width:.0f} x {depth:.0f} mm caddy."
            )
        cell_widths = [inner_w * w / sum(columns) for w in columns]
        cell_depths = [inner_d * r / sum(rows) for r in rows]

        common.check_features(report, wall, 0.0, wall)
        smallest = min(min(cell_widths), min(cell_depths))
        if smallest < 12.0:
            report.warn(
                f"the narrowest compartment is {smallest:.0f} mm. Nothing a "
                "classroom keeps in a caddy is that thin except a pencil, and "
                "a pencil in a slot that size cannot be got out again."
            )

        parts = PartSet()
        solid = self._body(opt, cell_widths, cell_depths, report)
        parts.add("caddy", solid,
                  note=f"{len(columns)} x {len(rows)} compartments")

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": 1,
                "outside_mm": [width, depth,
                               height + (25.0 if opt["handle"] != "none" else 0.0)],
                "capacity": (f"{len(columns) * len(rows)} compartments, "
                             + " x ".join(
                                 f"{w:.0f}" for w in cell_widths)
                             + f" mm wide by {cell_depths[0]:.0f} mm deep"),
                "supports": "none",
            },
            highlights=[
                f"{len(columns) * len(rows)} compartments in a "
                f"{width:.0f} x {depth:.0f} x {height:.0f} mm tray.",
                "Compartment widths are "
                + ":".join(f"{w:g}" for w in columns)
                + ", so they come out "
                + ", ".join(f"{w:.0f} mm" for w in cell_widths) + ".",
                {"bar": "A bar across the top to carry it by, from table to "
                        "table and back to the cupboard.",
                 "spine": "A divider wall standing proud of the rim, which is "
                          "both the handle and the thing that stops a caddy "
                          "of pencils becoming one pile of pencils.",
                 "none": "Open topped, so it stacks and slides under a shelf."
                 }[opt["handle"]],
                patterns.describe(opt["pattern"], opt["pattern_cell"],
                                  opt["pattern_rib"])
                + " cut through the outside walls, which takes weight and "
                "print time out and lets you see what is in it."
                if opt["pattern"] != "none" else
                "Solid walls: quicker to wipe out, and nothing falls through.",
            ],
            teaching_notes=[
                "One per table group, filled the same way, so 'get your "
                "caddy' is a single instruction.",
                "Label the front and the compartments have to go back where "
                "they came from, which is most of tidying up.",
            ],
            print_notes=[
                "Upright as supplied, open side up, no supports.",
                "Vase mode is not what this is: it needs the floor and the "
                "dividers. 3 perimeters, 15% infill.",
                "0.2 mm layers. A caddy is big, so this is a long print; "
                "0.3 mm layers with a 0.6 mm nozzle roughly halves it.",
                "The pattern's cut-outs are chamfered at the top so nothing "
                "bridges more than 12 mm."
                if opt["pattern"] != "none" else
                "PETG survives being knocked off a desk better than PLA.",
            ],
        )

    def _body(self, opt, cell_widths, cell_depths, report: Report):
        width, depth, height = opt["width"], opt["depth"], opt["height"]
        wall, floor = opt["wall"], opt["floor"]

        outer = common.plate(width, depth, height, opt["corner"],
                             opt["corner_size"], centred=False)

        pockets = []
        y = wall
        for cell_depth in cell_depths:
            x = wall
            for cell_width in cell_widths:
                pockets.append(geom.box(
                    [cell_width, cell_depth, height - floor + 0.01],
                    at=[x, y, floor]))
                x += cell_width + wall
            y += cell_depth + wall
        solid = geom.difference(outer, pockets)

        if opt["pattern"] != "none":
            solid = geom.difference(solid, self._wall_pattern(opt))

        if opt["drain"]:
            slots = []
            y = wall
            for cell_depth in cell_depths:
                x = wall
                for cell_width in cell_widths:
                    slot_w = min(cell_width * 0.5, 12.0)
                    slot_d = min(cell_depth * 0.5, 12.0)
                    slots.append(geom.box(
                        [slot_w, slot_d, floor + 2.0],
                        at=[x + (cell_width - slot_w) / 2.0,
                            y + (cell_depth - slot_d) / 2.0, -1.0]))
                    x += cell_width + wall
                y += cell_depth + wall
            solid = geom.difference(solid, slots)

        if opt["handle"] != "none":
            solid = geom.union([solid, self._handle(opt, cell_widths,
                                                    cell_depths)])

        if opt["label"]:
            solid = self._label(solid, opt, report)

        if not geom.is_one_piece(solid):
            raise ValueError(
                "the caddy came apart. The pattern has probably eaten a whole "
                "wall: raise pattern_rib or pattern_margin."
            )
        return solid

    def _wall_pattern(self, opt):
        """Cut-outs through the four outside walls, and only those.

        A tunnel cut straight through the body would come out of the far wall
        having also gone through every divider in between, and two of those
        crossing can isolate a corner. Clipping every cutter to the perimeter
        band keeps the pattern where it was asked for and leaves the dividers
        doing their job.
        """
        width, depth, height = opt["width"], opt["depth"], opt["height"]
        wall, margin = opt["wall"], opt["pattern_margin"]
        low = opt["floor"] + margin
        high = height - margin
        if high - low < 8.0:
            return geom.empty()

        band = geom.extrude(
            geom.rounded_rect(width, depth, opt["corner_size"], center=False)
            - geom.rect(width - 2.0 * wall, depth - 2.0 * wall,
                        center=False).translate([wall, wall]),
            height + 2.0, at_z=-1.0)

        cutters = []
        for span, axis in ((width, "x"), (depth, "y")):
            rect = (margin, low, span - margin, high)
            profiles = patterns.tile(opt["pattern"], rect, opt["pattern_cell"],
                                     opt["pattern_rib"])
            if not profiles:
                continue
            for profile in profiles:
                if axis == "x":
                    cutters.append(geom.prism_y(profile, -1.0, depth + 1.0))
                else:
                    cutters.append(geom.prism_x(profile, -1.0, width + 1.0))
        if not cutters:
            return geom.empty()
        return geom.intersection(geom.union(cutters), band)

    def _handle(self, opt, cell_widths, cell_depths):
        width, depth, height = opt["width"], opt["depth"], opt["height"]
        wall = opt["wall"]
        rise = min(max(height * 0.28, 18.0), 45.0)

        if opt["handle"] == "spine":
            # Extend the middle divider up past the rim and cut a grip in it.
            if len(cell_widths) < 2:
                spine_x = width / 2.0 - wall / 2.0
            else:
                spine_x = wall + sum(cell_widths[: len(cell_widths) // 2]) \
                    + wall * (len(cell_widths) // 2 - 1)
            blade = geom.box([wall, depth, rise], at=[spine_x, 0.0, height])
            top = geom.cylinder_x(wall / 2.0, spine_x, spine_x + wall,
                                  (depth / 2.0, height + rise))
            grip = geom.cylinder_x(min(depth * 0.22, 16.0),
                                   spine_x - 1.0, spine_x + wall + 1.0,
                                   (depth / 2.0, height + rise * 0.45))
            return geom.difference(geom.union([blade, top]), grip)

        # A bar: two posts and a rail across the middle, with the rail's
        # corners taken off at 45 degrees so it prints without support.
        # Narrow in depth, or it is not a handle -- it is a lid.
        post = min(wall * 2.5, 8.0)
        rail = min(wall * 2.5, 8.0)
        grip = min(max(depth * 0.28, 14.0), depth - 2.0 * wall)
        y0 = (depth - grip) / 2.0
        posts = [
            geom.box([post, grip, rise], at=[0.0, y0, height]),
            geom.box([post, grip, rise], at=[width - post, y0, height]),
        ]
        bar_profile = geom.chamfered_rect(0.0, width, height + rise - rail,
                                          height + rise, rail * 0.5)
        bar = geom.prism_y(bar_profile, y0, y0 + grip)
        return geom.union(posts + [bar])

    def _label(self, solid, opt, report: Report):
        shape, cap = text.fitted_line(
            opt["label"], opt["width"] * 0.8, opt["label_height"],
            min_cap=4.0)
        if shape.is_empty():
            return solid
        band = opt["height"] * 0.5
        if band - cap / 2.0 < opt["floor"]:
            report.warn("the label does not fit on the front; it was left off.")
            return solid
        # Built in XY, stood up on the front wall, and left standing 1 mm
        # proud of it: buried flush it would be a label nobody can read.
        plaque = geom.extrude(shape, 1.4, taper=0.25)
        plaque = plaque.rotate([90, 0, 0]).translate(
            [opt["width"] / 2.0, 0.4, band - cap / 2.0])
        return geom.union([solid, plaque])

    def slug(self, opt: dict[str, Any]) -> str:
        grid = f"{len(_parse_weights(opt['columns'], 'columns'))}x" \
               f"{len(_parse_weights(opt['rows'], 'rows'))}"
        return (f"supply-caddy_{grid}_{opt['width']:g}x{opt['depth']:g}"
                f"_{opt['handle']}")

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        columns = _parse_weights(opt["columns"], "columns")
        rows = _parse_weights(opt["rows"], "rows")
        return (f"Desk caddy - {len(columns) * len(rows)} compartments, "
                f"{opt['width']:.0f} x {opt['depth']:.0f} x "
                f"{opt['height']:.0f} mm")


def _parse_weights(raw: str, field: str) -> list[float]:
    values = []
    for chunk in str(raw).replace(" ", "").split(","):
        if not chunk:
            continue
        try:
            value = float(chunk)
        except ValueError:
            raise ValueError(
                f"{field}: {chunk!r} is not a number. Write them like 2,1,1 "
                "for a wide compartment and two narrow ones."
            ) from None
        if value <= 0:
            raise ValueError(f"{field}: {value} is not a width")
        values.append(value)
    if not values:
        raise ValueError(f"{field} is empty; try 1,1,1")
    if len(values) > 12:
        raise ValueError(f"{field}: {len(values)} compartments is too many")
    return values


register(SupplyCaddyGenerator())
