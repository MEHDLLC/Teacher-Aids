"""Dice, in every shape and with whatever is wanted on the faces.

A classroom die is rarely a plain six.  It is letters for a word game, plus
and minus for a number game, blank faces for a teacher to write on, or ten
sides for place value.  So the faces are a list of strings and the solid is a
choice, and the two are independent: a twenty-sided die with operators on it
is a silly thing to want and is nevertheless one command away.

Face content is engraved rather than raised, because a raised pip on a die is
the first thing to wear off and the thing that makes it roll unfairly.
"""

from __future__ import annotations

from typing import Any

from .. import common, geom, polyhedra, text
from ..generator import BuildResult, Generator, register
from ..mesh_io import PartSet
from ..options import Option, OptionSet, Report

SHAPES = ("cube", "tetrahedron", "octahedron", "dodecahedron", "icosahedron")
FACE_COUNTS = {"cube": 6, "tetrahedron": 4, "octahedron": 8,
               "dodecahedron": 12, "icosahedron": 20}

PRESETS = {
    "pips": "",             # dots, not text; handled specially
    "numbers": "",          # 1..n
    "letters": "A,B,C,D,E,F",
    "vowels": "A,E,I,O,U,Y",
    "operators": "+,−,×,÷,+,−",
    "blank": ",,,,,",
    "yes-no": "YES,NO,YES,NO,MAYBE,ASK",
    "directions": "N,S,E,W,UP,DOWN",
}

OPTIONS = OptionSet([
    Option("shape", "cube", "Which solid the die is",
           kind="choice", choices=SHAPES, group="Content"),
    Option("faces", "pips",
           "What goes on the faces: a preset (pips, numbers, letters, vowels, "
           "operators, blank, yes-no, directions) or a comma separated list "
           "of your own", kind="str", group="Content"),
    Option("quantity", 2, "How many of this die to place on the plate",
           kind="int", minimum=1, maximum=40, group="Content"),

    Option("size", 18.0,
           "How big the die is across its widest point", unit=" mm",
           minimum=8.0, maximum=60.0, group="Size"),
    Option("corner", 1.6,
           "How much the corners and edges are taken off. A sharp-cornered "
           "printed die does not roll, it slides", unit=" mm", minimum=0.0,
           maximum=6.0, group="Size"),

    Option("engrave_depth", 0.9, "How deep the face markings are cut",
           unit=" mm", minimum=0.3, maximum=3.0, group="Detail"),
    Option("face_fill", 0.55,
           "How much of a face the marking takes up, at most", minimum=0.15,
           maximum=0.9, group="Detail"),
    Option("pip_underline", True,
           "Underline the 6 and the 9 on a numbered die, so they can be told "
           "apart", kind="bool", group="Detail"),
    common.material_option(),
])


class DiceGenerator(Generator):
    key = "dice"
    category = "games"
    title = "Classroom dice"
    summary = (
        "Dice in all five Platonic shapes with whatever you like on the "
        "faces -- pips, numbers, letters, arithmetic signs or blanks -- "
        "engraved rather than raised so they still roll fairly."
    )
    tags = ("dice", "game", "probability", "math", "classroom", "literacy",
            "teaching aid", "parametric", "3d printing")
    ages = "5-adult"
    options = OPTIONS

    def build(self, opt: dict[str, Any]) -> BuildResult:
        report = Report()
        shape = opt["shape"]
        count = FACE_COUNTS[shape]
        pips = str(opt["faces"]).strip().lower() == "pips"
        labels = _face_labels(opt["faces"], count, report)

        if pips and shape != "cube":
            raise ValueError(
                f"pips only make sense on a cube; a {shape} has {count} faces "
                "and nobody counts eleven dots. Use faces=numbers."
            )
        common.check_features(report, opt["size"], opt["engrave_depth"],
                              opt["size"] * 0.1)

        solid, body = self._die(opt, labels, pips, report)
        parts = PartSet()
        parts.add(f"die_{shape}_{count}", solid,
                  note=f"{count} faces: "
                       + ("pips 1-6" if pips
                          else ", ".join(l or "blank" for l in labels)),
                  copies=opt["quantity"])

        common.check_small_parts(report, parts)
        return BuildResult(
            parts=parts,
            effective_options=opt,
            report=report,
            facts={
                "pieces": opt["quantity"],
                "piece_mm": list(parts.parts[0].size),
                "faces": count,
                "supports": "none",
            },
            highlights=[
                f"A {count}-sided {shape}, {opt['size']:.0f} mm.",
                "Pips, the way a die is supposed to look." if pips else
                "Faces: " + ", ".join(l or "blank" for l in labels) + ".",
                f"Corners and edges taken off by {opt['corner']:.1f} mm, "
                "which is what makes a printed die roll instead of slide.",
                "Everything is engraved into the face, so nothing wears off "
                "and nothing makes one face heavier than another.",
            ],
            teaching_notes=[
                "Probability: roll it a hundred times and tally. The gap "
                "between what should happen and what did is the lesson.",
                "Two dice and the sums are not equally likely, which is the "
                "moment most children first meet a distribution.",
                "Blank faces and a marker turn one die into any die you need "
                "on the day.",
            ],
            print_notes=[
                "One face flat on the bed, no supports.",
                "0.15 mm layers: at this size, layer lines are most of what "
                "you see.",
                "4 perimeters and 25% infill or more. A hollow die lands "
                "lopsided and is not fair.",
                "Print several at once -- the plate laid out in the 3MF "
                f"already has {opt['quantity']}.",
                "Paint or crayon rubbed into the engraving and wiped off the "
                "surface makes the faces readable across a table.",
            ],
        )

    def _die(self, opt, labels, pips: bool, report: Report):
        shape = opt["shape"]
        if shape == "cube":
            body = geom.box([opt["size"]] * 3,
                            at=[-opt["size"] / 2.0] * 3)
            scale = opt["size"] / 2.0
            faces = [
                polyhedra.Face(f.normal * scale, f.normal, f.right, f.up,
                               scale, 4)
                for f in _axis_faces()
            ]
        else:
            # `size` is how big the die is across its widest point, not its
            # edge length. Edge-matched dice are wildly different objects --
            # an 18 mm-edge dodecahedron is nearly 50 mm across while an
            # 18 mm-edge tetrahedron is 13 -- and nobody buying dice means
            # that by "18 mm".
            reference = polyhedra.build(shape, 1.0)
            span = max(reference.vertices.max(axis=0)
                       - reference.vertices.min(axis=0))
            model = polyhedra.build(shape, opt["size"] / float(span))
            body = model.solid()
            faces = model.faces

        if opt["corner"] > 0:
            body = _round_edges(body, opt["corner"])

        cutters = []
        for index, face in enumerate(faces):
            if index >= len(labels) and not pips:
                break
            marking = (self._pips(index + 1, face, opt)
                       if pips else
                       self._label(labels[index], face, opt, index, report))
            if marking is None:
                continue
            cutters.append(marking)
        solid = geom.difference(body, cutters)
        if not geom.is_one_piece(solid):
            raise ValueError(
                "the die came apart: the engraving is deep enough to meet "
                "itself through the middle. Reduce engrave_depth or "
                "face_fill."
            )
        return solid, body

    def _label(self, label: str, face, opt, index: int, report: Report):
        if not label:
            return None
        room = face.inradius * 2.0 * opt["face_fill"]
        shape, cap = text.fitted_line(label, room, room * 0.9, min_cap=2.0)
        if shape.is_empty():
            report.note(f"{label!r} did not fit on a face and was left off.")
            return None
        if opt["pip_underline"] and label in ("6", "9"):
            width, _ = geom.shape_size(shape)
            shape = geom.shape_union([
                shape,
                geom.rect(width * 1.1, cap * 0.12).translate(
                    [0.0, -cap * 0.30]),
            ])
        # Centre the ink, then sink it into the face.
        bx0, by0, bx1, by1 = geom.shape_bounds(shape)
        shape = shape.translate([-(bx0 + bx1) / 2.0, -(by0 + by1) / 2.0])
        return _sink_into(shape, face, opt["engrave_depth"])

    def _pips(self, value: int, face, opt):
        """The dots for one face of a six, in the arrangement everyone knows."""
        spread = face.inradius * opt["face_fill"] * 0.9
        radius = min(face.inradius * 0.16, spread * 0.42)
        layouts = {
            1: [(0, 0)],
            2: [(-1, 1), (1, -1)],
            3: [(-1, 1), (0, 0), (1, -1)],
            4: [(-1, -1), (-1, 1), (1, -1), (1, 1)],
            5: [(-1, -1), (-1, 1), (0, 0), (1, -1), (1, 1)],
            6: [(-1, -1), (-1, 0), (-1, 1), (1, -1), (1, 0), (1, 1)],
        }
        dots = [
            geom.circle(radius).translate([x * spread, y * spread])
            for x, y in layouts[value]
        ]
        return _sink_into(geom.shape_union(dots), face,
                          opt["engrave_depth"])

    def slug(self, opt: dict[str, Any]) -> str:
        faces = str(opt["faces"]).replace(",", "-").replace(" ", "")[:18]
        safe = "".join(c if c.isalnum() or c == "-" else "x" for c in faces)
        return (f"dice_{opt['shape']}_{FACE_COUNTS[opt['shape']]}"
                f"_{safe}_{opt['size']:g}mm")

    def listing_title(self, opt: dict[str, Any], result: BuildResult) -> str:
        count = FACE_COUNTS[opt["shape"]]
        what = ("pips" if str(opt["faces"]).lower() == "pips"
                else str(opt["faces"]).lower())
        return (f"{count}-sided dice ({what}) - {opt['size']:.0f} mm, "
                f"{opt['quantity']} of them")


def _sink_into(shape, face, depth: float) -> geom.Solid:
    """A cutter that removes exactly `depth` of material from one face.

    The profile is extruded from `depth` below the face plane to 1 mm above
    it: the millimetre of overshoot guarantees the cut breaks the surface
    cleanly, and starting at -depth rather than at the face means the pocket
    really is `depth` deep. Extruding the whole depth+1 inward instead sinks
    the marking a millimetre deeper than asked, which on a small twenty-sided
    die is enough for the pockets on opposite faces to meet in the middle.
    """
    cutter = geom.extrude(shape, depth + 1.0, at_z=-depth)
    return polyhedra.place_on_face(cutter, face, sink=0.0)


def _axis_faces():
    """The six faces of an axis-aligned cube of half-size 1."""
    import numpy as np
    out = []
    axes = [
        (np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])),
        (np.array([0.0, 0.0, -1.0]), np.array([-1.0, 0.0, 0.0])),
        (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])),
        (np.array([-1.0, 0.0, 0.0]), np.array([0.0, -1.0, 0.0])),
        (np.array([0.0, 1.0, 0.0]), np.array([-1.0, 0.0, 0.0])),
        (np.array([0.0, -1.0, 0.0]), np.array([1.0, 0.0, 0.0])),
    ]
    for normal, right in axes:
        up = np.cross(normal, right)
        out.append(polyhedra.Face(normal * 0.0, normal, right, up, 1.0, 4))
    return out


def _round_edges(solid: geom.Solid, radius: float) -> geom.Solid:
    """Take the corners and edges off, by shrinking and re-inflating.

    Eroding a solid by r and dilating it back by r rounds every convex edge to
    radius r and leaves the flats where they were, which is exactly what a die
    wants. Manifold has no erode, so the erode is done as a Minkowski
    difference against a small sphere and the dilate as a hull of spheres
    placed at the eroded solid's vertices.
    """
    if radius <= 0:
        return solid
    ball = geom.sphere(radius, segments=16)
    try:
        core = solid.minkowski_difference(ball)
        if core.is_empty():
            return solid
        return core.minkowski_sum(ball)
    except Exception:                        # pragma: no cover - version guard
        return solid


def _face_labels(spec: str, count: int, report) -> list[str]:
    key = str(spec).strip().lower()
    if key == "pips":
        return [str(i) for i in range(1, count + 1)]
    if key == "numbers":
        return [str(i) for i in range(1, count + 1)]
    if key in PRESETS:
        labels = [part.strip() for part in PRESETS[key].split(",")]
    else:
        labels = [part.strip() for part in str(spec).split(",")]

    if len(labels) < count:
        # Repeat rather than refuse: a six-value list on a twenty-sided die is
        # a perfectly reasonable thing to ask for, and saying so is enough.
        report.note(
            f"{len(labels)} faces given for a {count}-sided die, so they "
            "repeat around it."
        )
        labels = [labels[i % len(labels)] for i in range(count)]
    elif len(labels) > count:
        report.warn(
            f"{len(labels)} faces given for a {count}-sided die; the extra "
            + ", ".join(labels[count:]) + " were dropped."
        )
        labels = labels[:count]

    for label in labels:
        missing = text.font.missing(label)
        if missing:
            raise ValueError(
                f"face {label!r} uses " + ", ".join(repr(c) for c in missing)
                + " which this font cannot draw."
            )
    return labels


register(DiceGenerator())
