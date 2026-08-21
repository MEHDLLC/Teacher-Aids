"""Arranging a set of parts on a build plate.

A classroom set is not one object.  The alphabet is twenty-six tiles, a
fraction circle is fifteen wedges, a place-value set is four kinds of block in
quantity.  Laying those out along a single line -- which is what a naive 3MF
writer does -- produces a 3MF two metres wide that every slicer opens with
every object off the bed.

So parts are packed into rows that fit a real printer, in the order they were
made, because A-Z out of order is worse than A-Z on two plates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Roughly a Prusa MK4 / Bambu P1S, and comfortably inside an Ender 3.  Only
# used to decide where things sit; nothing is refused for being larger.
DEFAULT_PLATE = (220.0, 220.0)


@dataclass(frozen=True)
class Placement:
    """Where one part goes: its index, its plate, and its offset on it."""

    index: int
    plate: int
    x: float
    y: float


@dataclass(frozen=True)
class Layout:
    placements: list[Placement]
    plates: int
    used: tuple[float, float]        # footprint of the fullest plate
    plate_size: tuple[float, float]
    oversized: list[int]             # indices too big for the plate at all

    def offset(self, index: int) -> tuple[float, float]:
        return (self.placements[index].x, self.placements[index].y)


def arrange(sizes: Sequence[tuple[float, float]], gap: float = 5.0,
            plate_size: tuple[float, float] = DEFAULT_PLATE,
            single_plate: bool = False) -> Layout:
    """Row-pack `sizes` (each a width, depth pair) in the order given.

    `single_plate` keeps everything on one plate however tall the stack gets,
    which is what the preview wants: a picture of a set is more useful as one
    block than as three pages.
    """
    width_limit, depth_limit = plate_size
    placements: list[Placement] = []
    oversized: list[int] = []

    plate = 0
    cursor_x = 0.0
    cursor_y = 0.0
    row_depth = 0.0
    widest = 0.0
    deepest = 0.0

    for index, (width, depth) in enumerate(sizes):
        if width > width_limit or depth > depth_limit:
            oversized.append(index)
        # Wrap to a new row when this part would run off the right-hand edge.
        if placements and cursor_x + width > width_limit and cursor_x > 0:
            cursor_x = 0.0
            cursor_y += row_depth + gap
            row_depth = 0.0
            if not single_plate and cursor_y + depth > depth_limit:
                plate += 1
                cursor_y = 0.0
        placements.append(Placement(index, plate, cursor_x, cursor_y))
        cursor_x += width + gap
        row_depth = max(row_depth, depth)
        widest = max(widest, cursor_x - gap)
        deepest = max(deepest, cursor_y + row_depth)

    return Layout(
        placements=placements,
        plates=plate + 1,
        used=(widest, deepest),
        plate_size=plate_size,
        oversized=oversized,
    )
