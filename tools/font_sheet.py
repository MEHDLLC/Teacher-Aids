#!/usr/bin/env python3
"""Render every glyph in the font onto one sheet.

The font is data. A glyph with a transposed coordinate still builds, still
exports and still passes every topological check -- it just looks wrong, and
looking wrong is invisible in a diff. This makes it visible.

    python tools/font_sheet.py --out proofs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from teacheraids import font, geom, preview, text          # noqa: E402
from teacheraids.mesh_io import Part                       # noqa: E402


def sheet(out: Path, weight: float, cap: float = 24.0,
          tile: float = 34.0) -> Path:
    parts = []
    for char in sorted(font.GLYPHS, key=_order):
        if char == " ":
            continue
        glyph = text.glyph_shape(char, cap, weight)
        x0, _, x1, _ = geom.shape_bounds(glyph)
        body = geom.extrude(geom.rounded_rect(tile, tile, 5.0), 3.0)
        ink = geom.extrude(glyph.translate([-(x0 + x1) / 2.0, -cap * 0.42]),
                           1.8, at_z=3.0, taper=0.35)
        parts.append(Part(char, geom.union([body, ink])))

    out.parent.mkdir(parents=True, exist_ok=True)
    return preview.render_scene(out, parts, size=900,
                                views=[("plan", 0.0, 72.0)], supersample=2)


def _order(char: str) -> tuple[int, str]:
    for rank, group in enumerate((font.UPPERCASE, font.LOWERCASE, font.DIGITS,
                                  font.OPERATORS, font.PUNCTUATION)):
        if char in group:
            return (rank, f"{group.index(char):03d}")
    return (9, char)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="proofs", metavar="DIR")
    parser.add_argument("--weights", default="0.14,0.18,0.24,0.30",
                        metavar="LIST",
                        help="stroke weights to render, as fractions of the "
                             "cap height")
    args = parser.parse_args()

    root = Path(args.out)
    for raw in args.weights.split(","):
        weight = float(raw)
        path = sheet(root / f"font-weight-{weight:g}.png", weight * 100.0)
        print(f"wrote {path}")
    print(f"{len(font.GLYPHS)} glyphs rendered at "
          f"{len(args.weights.split(','))} weights")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
