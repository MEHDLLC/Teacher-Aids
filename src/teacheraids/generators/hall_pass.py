"""Hall passes.

Big, obvious and hard to lose, which is the entire specification: a pass that
fits in a pocket ends up in a pocket.  The handle is what makes it visible
from across a corridor, and it is also what makes it printable -- a long
paddle lying flat on the bed with no overhangs anywhere.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, patterns, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("text", "HALL PASS", "The main line", kind="str", group="Content"),
    Option("second_line", "", "A smaller line under it -- a room, a teacher",
           kind="str", group="Content"),
    Option("passes", "",
           "Several passes in one run, separated by semicolons, each becoming "
           "the second line. Empty makes one", kind="str", group="Content"),
    Option("max_passes", 20, "Stop after this many", kind="int", minimum=1,
           maximum=60, group="Content"),

    Option("width", 80.0, "Width of the paddle head", unit=" mm",
           minimum=40.0, maximum=180.0, group="Size"),
    Option("head", 110.0, "Height of the paddle head", unit=" mm",
           minimum=40.0, maximum=220.0, group="Size"),
    Option("handle", 70.0, "Length of the handle. Zero leaves it off",
           unit=" mm", minimum=0.0, maximum=180.0, group="Size"),
    Option("handle_width", 28.0, "Width of the handle", unit=" mm",
           minimum=14.0, maximum=70.0, group="Size"),
    Option("thickness", 5.0, "Thickness", unit=" mm", minimum=2.0,
           maximum=15.0, group="Size"),

    Option("relief", "raised", "Whether the text stands off or sinks in",
           kind="choice", choices=("raised", "recessed", "cut"),
           group="Detail"),
    Option("relief_depth", 1.6, "How far the text stands off or sinks in",
           unit=" mm", minimum=0.3, maximum=5.0, group="Detail"),
    Option("bridge", 3.0,
           "Width of the tabs that hold the middle of an A or an O in place "
           "when the text is cut through", unit=" mm", minimum=0.8,
           maximum=10.0, group="Detail"),
    Option("both_sides", True, "Put the text on the back as well", kind="bool",
           group="Detail"),
    Option("lanyard", 8.0,
           "Hole through the handle for a lanyard or a hook. Zero leaves it "
           "out", unit=" mm", minimum=0.0, maximum=20.0, group="Detail"),
    Option("grip", True,
           "Finger grooves down the handle, so a running child keeps hold of "
           "it", kind="bool", group="Detail"),
    Option("pattern", "none", "A border pattern engraved around the text",
           kind="choice", choices=("none",) + patterns.PATTERNS,
           group="Detail"),
    *common.corner_options(10.0),
    common.material_option(),
])


class HallPassGenerator(Generator):
    key = "hall-pass"
    category = "classroom"
    title = "Hall pass"
    summary = (
        "A paddle hall pass: big enough to be seen from the end of a "
        "corridor, thick enough to survive being dropped, and lettered on "
        "both sides so it reads whichever way up it is carried."
    )
    tags = ("hall pass", "bathroom pass", "classroom management", "school",
            "teacher", "parametric", "3d printing")
    ages = "any"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        variants = [p.strip() for p in str(opt["passes"]).split(";") if p.strip()]
        if not variants:
            variants = [opt["second_line"].strip()]
        if len(variants) > opt["max_passes"]:
            report.warn(
                f"{len(variants)} passes is more than max_passes "
                f"({opt['max_passes']}); this run leaves out "
                + ", ".join(variants[opt["max_passes"]:]) + "."
            )
            variants = variants[: opt["max_passes"]]

        common.check_features(report, opt["thickness"], opt["relief_depth"],
                              opt["handle_width"])
        if opt["relief"] == "cut" and opt["both_sides"]:
            report.note(
                "cut-through text reads from both sides on its own, so "
                "both_sides adds nothing."
            )

        parts = PartSet()
        for second in variants:
            name = _safe(second or opt["text"])
            parts.add(name, self._one(opt, second, report),
                      note=(f"{opt['text']} / {second}" if second
                            else opt["text"]))

        total = opt["head"] + opt["handle"]
        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": len(parts),
                "piece_mm": list(parts.parts[0].size),
                "outside_mm": [opt["width"], total, opt["thickness"]],
                "supports": "none",
            },
            highlights=[
                f"{opt['width']:.0f} x {total:.0f} mm and "
                f"{opt['thickness']:.0f} mm thick -- visible from the end of a "
                "corridor and awkward to put in a pocket, which is the point.",
                f"A {opt['handle']:.0f} mm handle"
                + (" with finger grooves" if opt["grip"] else "")
                + (f" and an {opt['lanyard']:.0f} mm lanyard hole."
                   if opt["lanyard"] > 0 else ".")
                if opt["handle"] > 0 else "No handle: a plain paddle.",
                "Lettered on both faces, so it reads whichever way it is "
                "picked up." if opt["both_sides"] else "Lettered on one face.",
                f"{len(parts)} passes in the set: "
                + ", ".join(v for v in variants if v) + "."
                if len(parts) > 1 else "",
            ],
            teaching_notes=[
                "One pass per destination and the question 'where are you "
                "going' answers itself from the doorway.",
                "Hang them by the door on hooks: a missing pass is a child "
                "who is out.",
            ],
            print_notes=[
                "Flat on the bed, no supports.",
                "Two colours by adding a filament change at "
                f"{opt['thickness']:.1f} mm."
                if opt["relief"] == "raised" and not opt["both_sides"] else
                "Text on both faces means the underside letters print against "
                "the bed: they come out crisp, but expect them to be shiny "
                "rather than matte."
                if opt["both_sides"] else
                "0.2 mm layers.",
                "4 perimeters, 20% infill. This gets dropped down stairwells.",
                "PETG. A PLA pass snaps at the handle within a term.",
            ],
        )

    def _one(self, opt, second: str, report: Report) -> geom.Solid:
        width, head = opt["width"], opt["head"]
        thickness = opt["thickness"]
        handle, handle_w = opt["handle"], opt["handle_width"]

        outline = geom.rounded_rect(width, head, opt["corner_size"])
        if handle > 0:
            # Overlap the head by a corner radius so the two blend into one
            # outline rather than meeting at a step that snaps.
            shaft = geom.rounded_rect(
                handle_w, handle + opt["corner_size"] * 2.0,
                min(handle_w / 2.5, 8.0)
            ).translate([0.0, -head / 2.0 - handle / 2.0
                         + opt["corner_size"]])
            outline = geom.shape_union([outline, shaft])
        body = geom.extrude(outline, thickness)

        block = self._face(opt, second)
        # Cut-through text needs the counters tabbed, or the middle of every
        # A, P and O drops out of the paddle on the first print.
        ink = (text.stencil_cut(block, opt["bridge"])
               if opt["relief"] == "cut" else block)
        solid = common.face_relief(body, ink, opt["relief"],
                                   opt["relief_depth"], thickness,
                                   0.3 if opt["relief"] == "raised" else 0.0)
        if opt["both_sides"] and opt["relief"] != "cut":
            mirrored = block.mirror([1.0, 0.0])
            if opt["relief"] == "raised":
                solid = geom.union([
                    solid,
                    geom.extrude(mirrored, opt["relief_depth"]).mirror(
                        [0.0, 0.0, 1.0])])
            else:
                solid = geom.difference(solid, geom.extrude(
                    mirrored, opt["relief_depth"] + 0.01, at_z=-0.01))

        if handle > 0 and opt["lanyard"] > 0:
            centre = -head / 2.0 - handle + opt["lanyard"] * 0.9
            solid = geom.difference(solid, common.hang_hole(
                opt["lanyard"], thickness, (0.0, centre)))

        if handle > 0 and opt["grip"]:
            grooves = []
            span = handle * 0.55
            count = max(2, int(span / 12.0))
            for index in range(count):
                y = -head / 2.0 - handle * 0.30 - index * (span / count)
                grooves.append(geom.cylinder_x(
                    2.0, -width, width, (y, thickness)))
                grooves.append(geom.cylinder_x(2.0, -width, width, (y, 0.0)))
            solid = geom.difference(solid, grooves)

        if not geom.is_one_piece(solid):
            raise ValueError(
                "the pass came apart. Cut text has probably reached the edge: "
                "shorten the text or widen the paddle."
            )
        return solid

    def _face(self, opt, second: str):
        width, head = opt["width"], opt["head"]
        room = width * 0.82
        lines = []
        if second:
            main, main_cap = text.fitted_line(opt["text"], room, head * 0.24,
                                              min_cap=5.0)
            sub, sub_cap = text.fitted_line(second, room, head * 0.16,
                                            min_cap=4.0)
            lines.append(main.translate([0.0, head * 0.06]))
            lines.append(sub.translate([0.0, head * 0.06 - sub_cap * 1.7]))
        else:
            words = opt["text"].split()
            if len(words) > 1 and max(len(w) for w in words) * 1.4 < len(
                    opt["text"]):
                # Two short words stack better than one long line on a paddle
                # that is taller than it is wide.
                block = text.block_shape(words, head * 0.22, 18.0, leading=1.4)
                bx0, by0, bx1, by1 = geom.shape_bounds(block)
                span = max(bx1 - bx0, 1e-6)
                if span > room:
                    block = block.scale([room / span, room / span])
                lines.append(block)
            else:
                main, main_cap = text.fitted_line(opt["text"], room,
                                                  head * 0.26, min_cap=5.0)
                lines.append(main.translate([0.0, -main_cap / 2.0]))

        block = geom.shape_union(lines)
        if opt["pattern"] != "none" and not block.is_empty():
            inset = opt["corner_size"] + 2.0
            profiles = patterns.tile(
                opt["pattern"],
                (-width / 2 + inset, -head / 2 + inset,
                 width / 2 - inset, head / 2 - inset),
                patterns.default_cell(opt["pattern"]) * 0.5,
                patterns.default_rib(opt["pattern"]) * 0.6)
            if profiles:
                field = geom.shape_union([geom.polygon(p) for p in profiles])
                block = geom.shape_union([
                    block,
                    field - block.offset(2.5, text.geom_join(), 2.0, 12)])
        return block

    def slug(self, opt: dict[str, Any]) -> str:
        variants = [p.strip() for p in str(opt["passes"]).split(";") if p.strip()]
        tag = (f"{len(variants)}-passes" if len(variants) > 1
               else _safe(opt["text"]))
        return f"hall-pass_{tag}_{opt['width']:g}x{opt['head']:g}"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        if result.facts["pieces"] > 1:
            return (f"Hall passes - {result.facts['pieces']} in the set, "
                    f"{opt['width']:.0f} mm paddles")
        return (f"{opt['text']} - {opt['width']:.0f} x "
                f"{opt['head'] + opt['handle']:.0f} mm paddle")


def _safe(raw: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in raw).strip("-")
    return out or "pass"


register(HallPassGenerator())
