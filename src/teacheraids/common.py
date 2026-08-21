"""Pieces every generator here builds out of.

A teaching aid is nearly always a plate with something done to its face: a
letter raised off it, a groove sunk into it, a shape cut through it, a magnet
pocket in its back.  Writing that once means every tile in the repo rounds its
corners the same way, drafts its lettering the same way, and warns about the
same too-small features.
"""

from __future__ import annotations

from typing import Iterable

from . import geom, presets
from .geom import Shape, Solid
from .options import Option, Report

CORNER_STYLES = ("round", "chamfer", "square")
RELIEF_MODES = ("raised", "recessed", "cut", "flat")


def plate(width: float, depth: float, thickness: float,
          corner: str = "round", corner_size: float = 4.0,
          centred: bool = True) -> Solid:
    """The flat body almost everything here starts as.

    Corners are rounded by default because these are handled by children all
    day: a printed square corner on a 3 mm tile is sharp enough to score skin,
    and rounding it costs nothing.
    """
    if corner not in CORNER_STYLES:
        raise ValueError(
            f"unknown corner {corner!r}; use " + ", ".join(CORNER_STYLES))
    if corner == "round":
        profile = geom.rounded_rect(width, depth, corner_size, center=True)
    elif corner == "chamfer":
        profile = geom.polygon(
            geom.chamfered_rect(-width / 2, width / 2, -depth / 2, depth / 2,
                                corner_size))
    else:
        profile = geom.rect(width, depth, center=True)
    solid = geom.extrude(profile, thickness)
    return solid if centred else solid.translate([width / 2, depth / 2, 0])


def face_relief(body: Solid, shape: Shape, mode: str, depth: float,
                thickness: float, taper: float = 0.0) -> Solid:
    """Put a 2-D profile onto (or into, or through) the top face of a plate.

    One function for all four modes so that a `relief` option is a real
    variable rather than four near-copies of a generator, and so a theme can
    switch between them without any geometry changing hands.
    """
    if mode not in RELIEF_MODES:
        raise ValueError(
            f"unknown relief {mode!r}; use " + ", ".join(RELIEF_MODES))
    if mode == "flat" or shape.is_empty() or depth <= 0:
        return body
    if mode == "raised":
        return geom.union([body, geom.extrude(shape, depth, at_z=thickness,
                                              taper=taper)])
    if mode == "recessed":
        # Overshoot the top by a hair so the cut leaves no zero-thickness skin
        # where the two coplanar faces meet.
        cut = geom.extrude(shape, depth + 0.01, at_z=thickness - depth)
        return geom.difference(body, cut)
    return geom.difference(body, geom.extrude(shape, thickness + 2.0, at_z=-1.0))


def magnet_pocket(diameter: float, depth: float, at_xy=(0.0, 0.0),
                  clearance: float = 0.25) -> Solid:
    """A blind bore in the back of a tile, sized to press-fit a disc magnet.

    Cut from below, so it needs the tile's own thickness to be at least the
    magnet's depth plus a couple of layers of floor -- checked by the caller,
    which knows the thickness.
    """
    radius = diameter / 2.0 + clearance
    return geom.cylinder_z(radius, -0.01, depth, at_xy)


def hang_hole(diameter: float, thickness: float, at_xy=(0.0, 0.0)) -> Solid:
    """A through hole for a key ring, lanyard or shower curtain ring."""
    return geom.cylinder_z(diameter / 2.0, -1.0, thickness + 1.0, at_xy)


def check_features(report: Report, thickness: float, emboss_depth: float,
                   smallest_feature: float, label: str = "") -> None:
    """Warn, rather than refuse, when something is below what a nozzle resolves."""
    where = f"{label}: " if label else ""
    if smallest_feature < presets.MIN_FEATURE:
        report.warn(
            f"{where}the thinnest feature is {smallest_feature:.2f} mm, under "
            f"the {presets.MIN_FEATURE:.1f} mm two extrusions need. It will "
            "print, but as a single thin wall."
        )
    if 0 < emboss_depth < presets.MIN_EMBOSS_DEPTH:
        report.warn(
            f"{where}relief is {emboss_depth:.2f} mm, under two 0.2 mm layers. "
            "It will read as a texture rather than as a shape you can feel."
        )
    if thickness < 1.2:
        report.warn(
            f"{where}a {thickness:.1f} mm plate is thin enough to flex and "
            "snap in a classroom. 3 mm or more survives a school year."
        )


def check_small_parts(report: Report, parts: Iterable, ages: str = "") -> None:
    """Flag anything small enough to be a choking hazard.

    The threshold is the small-parts cylinder used for toy safety: anything
    that fits entirely inside a 31.7 mm diameter by 57.1 mm cylinder is a
    choking hazard for under-threes.  This repo cannot enforce that -- a
    counter is *meant* to be small -- but it can say so every time.
    """
    smallest = None
    for part in parts:
        width, depth, height = part.size
        longest = max(width, depth, height)
        if smallest is None or longest < smallest:
            smallest = longest
    if smallest is not None and smallest < 32.0:
        report.warn(
            f"the smallest piece is {smallest:.0f} mm across. Pieces under "
            "about 32 mm fit the small-parts cylinder and are a choking "
            "hazard: keep them away from children under three."
        )


# ---------------------------------------------------------------------------
# Option groups shared across generators
# ---------------------------------------------------------------------------


def material_option(group: str = "Print") -> Option:
    return Option(
        "material", "pla",
        "Filament, used only to estimate the weight in the listing",
        kind="choice", choices=("pla", "petg", "abs", "asa", "tpu"),
        group=group,
    )


def corner_options(default_radius: float = 4.0,
                   group: str = "Shape") -> list[Option]:
    return [
        Option("corner", "round", "How the outside corners are treated",
               kind="choice", choices=CORNER_STYLES, group=group),
        Option("corner_size", default_radius,
               "Corner radius, or chamfer size", unit=" mm", minimum=0.0,
               maximum=30.0, group=group),
    ]


def magnet_options(group: str = "Mounting") -> list[Option]:
    return [
        Option("magnet", "none",
               "Sink a pocket for a disc magnet in the back, by size",
               kind="choice",
               choices=("none",) + tuple(sorted(presets.MAGNET_SIZES)),
               group=group),
        Option("magnet_clearance", 0.25,
               "Extra radius in the magnet pocket, for a press fit",
               unit=" mm", minimum=0.0, maximum=1.0, group=group,
               listed=False),
    ]


def apply_magnet(body: Solid, spec: str, thickness: float, clearance: float,
                 report: Report, at_xy=(0.0, 0.0)) -> tuple[Solid, dict]:
    """Sink a magnet pocket, or say why it was not sunk."""
    if spec == "none":
        return body, {}
    diameter, depth = presets.MAGNET_SIZES[spec]
    floor = thickness - depth
    if floor < 0.6:
        report.warn(
            f"a {spec} magnet needs {depth:.0f} mm of the plate's "
            f"{thickness:.1f} mm, leaving {max(floor, 0):.1f} mm of floor. "
            "The pocket was left out; thicken the plate or use a thinner "
            "magnet."
        )
        return body, {}
    pocket = magnet_pocket(diameter, depth, at_xy, clearance)
    return geom.difference(body, pocket), {
        "magnet_mm": [diameter, depth],
        "magnet_floor_mm": round(floor, 2),
    }
