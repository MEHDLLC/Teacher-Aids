"""Desk name plates.

The awkward requirement is that "Al" and "Konstantina" have to come off the
same generator at the same plate size, or a class set does not line up on the
desks.  So the plate size is fixed and the lettering is fitted to it, rather
than the other way round -- and the fitted cap height is reported, because a
set where one name is half the size of the others is worth knowing about
before thirty of them are printed.
"""

from __future__ import annotations

import math
from typing import Any

from .. import common, geom, patterns, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

OPTIONS = OptionSet([
    Option("names", "",
           "One name, or several separated by semicolons to make a class set "
           "in a single run", kind="str", group="Content"),
    Option("second_line", "",
           "A smaller line under the name -- a room, a table, a subject",
           kind="str", group="Content"),
    Option("max_plates", 36, "Stop after this many plates", kind="int",
           minimum=1, maximum=120, group="Content"),
    Option("style", "wedge",
           "wedge stands on the desk by itself; flat lies down or tapes to a "
           "desk; stand is a flat plate and a separate slotted base",
           kind="choice", choices=("wedge", "flat", "stand"), group="Content"),
    Option("both_sides", False,
           "Put the name on the back as well, so it reads from behind",
           kind="bool", group="Content"),

    Option("width", 180.0, "Plate width", unit=" mm", minimum=50.0,
           maximum=300.0, group="Size"),
    Option("face_height", 45.0, "Height of the lettered face", unit=" mm",
           minimum=18.0, maximum=120.0, group="Size"),
    Option("thickness", 3.5, "Plate thickness", unit=" mm", minimum=1.5,
           maximum=12.0, group="Size"),
    Option("lean", 22.0,
           "How far a wedge leans back from vertical", unit=" deg",
           minimum=0.0, maximum=45.0, group="Size"),
    Option("cap_height", 0.0,
           "Cap the lettering at this height. Zero fits it to the plate",
           unit=" mm", minimum=0.0, maximum=90.0, group="Size",
           default_note="60% of the face"),

    Option("relief", "raised", "Whether the name stands off or sinks in",
           kind="choice", choices=("raised", "recessed"), group="Detail"),
    Option("relief_depth", 1.4, "How far the name stands off or sinks in",
           unit=" mm", minimum=0.3, maximum=5.0, group="Detail"),
    Option("pattern", "none", "A border pattern engraved around the name",
           kind="choice", choices=("none",) + patterns.PATTERNS,
           group="Detail"),
    *common.corner_options(4.0),
    common.material_option(),
])


class NamePlateGenerator(Generator):
    key = "name-plate"
    category = "classroom"
    title = "Desk name plate"
    summary = (
        "Name plates for desks, as a self-standing wedge, a flat plate or a "
        "plate with a slotted base -- with the lettering fitted to a fixed "
        "plate so a whole class set is the same size."
    )
    tags = ("name plate", "desk", "classroom", "back to school", "teacher",
            "personalised", "parametric", "3d printing")
    ages = "any"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        names = [n.strip() for n in str(opt["names"]).split(";") if n.strip()]
        if not names:
            raise ValueError(
                "names is empty. Give one name, or several separated by "
                "semicolons: --names 'Amara;Ben;Chidi'"
            )
        if len(names) > opt["max_plates"]:
            report.warn(
                f"{len(names)} names is more than max_plates "
                f"({opt['max_plates']}), so this run stops at "
                f"{names[opt['max_plates'] - 1]!r} and leaves out "
                + ", ".join(names[opt["max_plates"]:]) + "."
            )
            names = names[: opt["max_plates"]]

        for name in names:
            missing = text.font.missing(name)
            if missing:
                raise ValueError(
                    f"{name!r} uses " + ", ".join(repr(c) for c in missing)
                    + " which this font cannot draw. It draws "
                    + " ".join(sorted(text.font.GLYPHS)) + "."
                )

        max_cap = opt["cap_height"] or opt["face_height"] * 0.60
        if opt["second_line"]:
            max_cap = min(max_cap, opt["face_height"] * 0.45)
        room = opt["width"] - 2.0 * max(opt["corner_size"], 6.0)

        caps = {n: text.fit_cap_height(n, room, max_cap, min_cap=5.0)
                for n in names}
        smallest, largest = min(caps.values()), max(caps.values())
        if largest - smallest > largest * 0.25:
            longest = max(caps, key=lambda n: len(n))
            report.warn(
                f"{longest!r} had to be set at {caps[longest]:.0f} mm against "
                f"{largest:.0f} mm for the shortest name, so this set is not "
                "one size. Widen the plate to even them up."
            )

        common.check_features(report, opt["thickness"], opt["relief_depth"],
                              smallest * 0.18)

        parts = PartSet()
        for name in names:
            parts.add(_safe(name), self._plate(name, opt, caps[name], report),
                      note=f"{name}, {caps[name]:.0f} mm lettering")
        if opt["style"] == "stand":
            parts.add("base", self._base(opt),
                      note="one per plate; slide the plate into the slot",
                      copies=len(names))

        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": parts.total_copies,
                "piece_mm": list(parts.parts[0].size),
                "outside_mm": [opt["width"], opt["face_height"],
                               opt["thickness"]],
                "cap_height_mm": round(largest, 1),
                "characters": ", ".join(names),
                "supports": "none",
            },
            highlights=[
                f"{len(names)} plate" + ("s" if len(names) != 1 else "")
                + f", all {opt['width']:.0f} mm wide, so they line up along a "
                  "row of desks.",
                {"wedge": f"A wedge leaning back {opt['lean']:.0f} degrees: it "
                          "stands on the desk by itself, prints in one piece "
                          "and has nothing to lose.",
                 "flat": "A flat plate, to tape to the desk or slot into a "
                         "name-card holder.",
                 "stand": "A flat plate and a slotted base, so the plates "
                          "stack flat in a drawer over the holidays."
                 }[opt["style"]],
                f"Lettering fitted to the plate: {smallest:.0f} to "
                f"{largest:.0f} mm depending on the name."
                if smallest != largest else
                f"{largest:.0f} mm lettering throughout.",
                "The name is on the back as well, so it reads from behind the "
                "desk too." if opt["both_sides"] else
                "Lettered on the front.",
            ],
            teaching_notes=[
                "A class set on the first day tells you who everybody is, and "
                "tells them the classroom was set up for them.",
                "Print the second line as the table or group name and "
                "regrouping is a matter of reprinting one line.",
            ],
            print_notes=[
                {"wedge": "Flat on the bed, sloped face up, no supports. The "
                          "wedge is drawn so its face leans back rather than "
                          "forward, which is what keeps it support-free.",
                 "flat": "Flat on the bed, no supports.",
                 "stand": "Both parts flat on the bed, no supports.",
                 }[opt["style"]],
                "Two colours by adding a filament change at "
                f"{opt['thickness']:.1f} mm gives a coloured name on a "
                "different plate for the cost of one swap."
                if opt["relief"] == "raised" else
                "Brush acrylic into the sunken letters and wipe the surface "
                "before it dries.",
                "0.2 mm layers, 3 perimeters, 15% infill.",
                "A class set is a long print. Lay them out on one plate and "
                "run it overnight; the 3MF supplied already is.",
            ],
        )

    def _face(self, name: str, opt, cap: float, report: Report):
        """The lettering for one plate, centred on a face-sized rectangle."""
        width, height = opt["width"], opt["face_height"]
        lines = [(name, cap)]
        if opt["second_line"]:
            shape, small = text.fitted_line(
                opt["second_line"], width * 0.7, cap * 0.5, min_cap=3.5)
            lines.append((opt["second_line"], small))

        drawn = []
        if opt["second_line"]:
            drawn.append(text.line_shape(name, cap).translate(
                [0.0, -cap * 0.35]))
            drawn.append(text.line_shape(opt["second_line"], lines[1][1])
                         .translate([0.0, -cap * 0.35 - lines[1][1] * 1.15]))
        else:
            drawn.append(text.line_shape(name, cap).translate([0.0, -cap / 2.0]))
        block = geom.shape_union(drawn)

        if opt["pattern"] != "none":
            inset = max(opt["corner_size"], 5.0)
            border = (geom.rect(width - 2 * inset, height - 2 * inset)
                      - geom.rect(width - 2 * inset - 12.0,
                                  height - 2 * inset - 12.0))
            profiles = patterns.tile(
                opt["pattern"], (-width / 2 + inset, -height / 2 + inset,
                                 width / 2 - inset, height / 2 - inset),
                patterns.default_cell(opt["pattern"]) * 0.5,
                patterns.default_rib(opt["pattern"]) * 0.5)
            field = geom.shape_intersection(
                geom.shape_union([geom.polygon(p) for p in profiles]), border)
            block = geom.shape_union([block, field - block.offset(
                2.0, text.geom_join(), 2.0, 12)])
        return block

    def _plate(self, name: str, opt, cap: float, report: Report):
        width, height = opt["width"], opt["face_height"]
        thickness = opt["thickness"]
        block = self._face(name, opt, cap, report)

        if opt["style"] in ("flat", "stand"):
            body = common.plate(width, height, thickness, opt["corner"],
                                opt["corner_size"])
            solid = common.face_relief(body, block, opt["relief"],
                                       opt["relief_depth"], thickness,
                                       0.3 if opt["relief"] == "raised" else 0)
            if opt["both_sides"]:
                mirrored = block.mirror([1.0, 0.0])
                if opt["relief"] == "raised":
                    solid = geom.union([solid, geom.extrude(
                        mirrored, opt["relief_depth"]).mirror(
                            [0.0, 0.0, 1.0])])
                else:
                    solid = geom.difference(solid, geom.extrude(
                        mirrored, opt["relief_depth"] + 0.01, at_z=-0.01))
            return solid

        # A wedge: a right triangle in section, face leaning back.
        lean = math.radians(opt["lean"])
        rise = height * math.cos(lean)
        run = height * math.sin(lean)
        foot = run + thickness / math.cos(lean) + 8.0
        section = [
            (0.0, 0.0), (foot, 0.0), (run + thickness / math.cos(lean), rise),
            (run, rise),
        ]
        body = geom.prism_x(section, -width / 2.0, width / 2.0)
        # The lettering is built flat and then leaned onto the sloped face.
        #
        # Rotating about X by (90 - lean), not by lean: the block's own +Y has
        # to end up pointing up the slope and its +Z out along the face's
        # normal, and those two are 90 degrees apart from the pair a rotation
        # by `lean` would give. Its centre then goes to the centre of the
        # sloped face, which is half way along the slope at (run/2, rise/2).
        #
        # The slab is cut to length rather than trimmed against the body
        # afterwards. Subtracting the wedge from an over-long slab and
        # unioning the remainder looks equivalent and is not: where a letter's
        # edge runs almost tangent to the sloped face the subtraction leaves
        # zero-volume slivers, and those come back as extra "pieces" that fail
        # the one-piece check for no reason a printer would ever notice.
        inward = min(1.0, thickness * 0.4)
        if opt["relief"] == "raised":
            slab = geom.extrude(block, opt["relief_depth"] + inward,
                                at_z=-inward)
        else:
            slab = geom.extrude(block, opt["relief_depth"] + 1.0,
                                at_z=-opt["relief_depth"])
        slab = slab.rotate([90.0 - opt["lean"], 0, 0]).translate(
            [0.0, run / 2.0, rise / 2.0])
        if opt["relief"] == "raised":
            solid = geom.union([body, slab])
        else:
            solid = geom.difference(body, slab)
        if not geom.is_one_piece(solid):
            raise ValueError(
                f"the wedge for {name!r} came apart. Reduce relief_depth or "
                "thicken the plate."
            )
        return solid

    def _base(self, opt):
        """A slotted foot for the flat-plate style."""
        thickness = opt["thickness"]
        length = min(opt["width"] * 0.55, 110.0)
        depth = max(opt["face_height"] * 0.55, 26.0)
        tall = 14.0
        slot_lean = 12.0
        body = common.plate(length, depth, tall, "chamfer", 3.0)
        slot = geom.box([length + 2, thickness + 0.4, tall + 2],
                        at=[-length / 2 - 1, -(thickness + 0.4) / 2, 3.0])
        slot = slot.rotate([slot_lean, 0, 0])
        return geom.difference(body, slot)

    def slug(self, opt: dict[str, Any]) -> str:
        names = [n.strip() for n in str(opt["names"]).split(";") if n.strip()]
        tag = _safe(names[0]) if len(names) == 1 else f"{len(names)}-names"
        return f"name-plate_{opt['style']}_{tag}_{opt['width']:g}mm"

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        names = [n.strip() for n in str(opt["names"]).split(";") if n.strip()]
        if len(names) == 1:
            return (f"Desk name plate - {names[0]}, {opt['width']:.0f} mm "
                    f"{opt['style']}")
        return (f"Desk name plates - {len(names)} names, "
                f"{opt['width']:.0f} mm {opt['style']}")


def _safe(name: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in name).strip("-")
    return out or "plate"


register(NamePlateGenerator())
