"""The font and the text engine.

The font is data, and data is where the silent mistakes live: a glyph that
draws as a blob, a dot that welds itself to its stem at a heavy weight, a
counter that survives bridging and drops out of a stencil on the bed.
"""

import unittest

import _support  # noqa: F401
from teacheraids import font, geom, text

WEIGHTS = (0.12, 0.18, 0.24, 0.30)
EVERY = font.UPPERCASE + font.LOWERCASE + font.DIGITS + font.OPERATORS


class TestFontData(unittest.TestCase):
    def test_every_glyph_draws_something_the_right_size(self):
        for char in font.GLYPHS:
            if char == " ":
                continue
            shape = text.glyph_shape(char, 30.0, 18.0)
            self.assertFalse(shape.is_empty(), f"{char!r} drew nothing")
            width, height = geom.shape_size(shape)
            # Nothing may be wider than the body or taller than ascender to
            # descender, and nothing may be a dot when it should be a letter.
            self.assertLess(width, 40.0, f"{char!r} is {width:.1f} wide")
            self.assertLess(height, 45.0, f"{char!r} is {height:.1f} tall")
            self.assertGreater(width, 1.0, f"{char!r} is {width:.1f} wide")

    def test_capitals_reach_the_cap_height(self):
        for char in font.UPPERCASE + font.DIGITS:
            shape = text.glyph_shape(char, 40.0, 18.0)
            _, _, _, top = geom.shape_bounds(shape)
            # The top of the ink is the cap plus half the pen.
            self.assertAlmostEqual(top, 40.0 + 40.0 * 0.09, delta=1.2,
                                   msg=f"{char!r} tops out at {top:.1f}")

    def test_i_and_j_keep_their_dots_separate(self):
        # At classroom weights the pen is a fifth of the cap height; a dot
        # placed by eye welds to the stem and the letter reads as an l.
        for weight in WEIGHTS:
            for char in "ij":
                shape = text.glyph_shape(char, 30.0, weight * 100.0)
                self.assertEqual(
                    len(shape.decompose()), 2,
                    f"{char!r} at weight {weight} is one blob, not a stem "
                    "and a dot")

    def test_letters_with_counters_keep_them_open(self):
        for char in "ABDOPQRabdegopq0468":
            for weight in WEIGHTS:
                shape = text.glyph_shape(char, 30.0, weight * 100.0)
                self.assertGreater(
                    len(text.counters(shape)), 0,
                    f"{char!r} at weight {weight} closed its counter")

    def test_unknown_character_names_itself(self):
        with self.assertRaises(KeyError) as caught:
            font.glyph("é")
        self.assertIn("no glyph", str(caught.exception))


class TestMetrics(unittest.TestCase):
    def test_width_scales_linearly_with_cap_height(self):
        small = text.measure("HELLO", 10.0).width
        large = text.measure("HELLO", 30.0).width
        self.assertAlmostEqual(large / small, 3.0, places=6)

    def test_fit_cap_height_actually_fits(self):
        for word in ("Al", "Ben", "Konstantina", "Mr Okafor"):
            cap = text.fit_cap_height(word, 120.0, 40.0)
            self.assertLessEqual(text.measure(word, cap).width, 120.001)

    def test_a_short_name_is_not_stretched_past_the_cap(self):
        self.assertAlmostEqual(text.fit_cap_height("Al", 500.0, 30.0), 30.0)

    def test_alignment(self):
        for align, expect in (("centre", 0.0), ("left", 1.0), ("right", -1.0)):
            shape = text.line_shape("HELLO", 20.0, align=align)
            x0, _, x1, _ = geom.shape_bounds(shape)
            middle = (x0 + x1) / 2.0
            self.assertEqual(expect == 0.0, abs(middle) < 1.0)


class TestCharsets(unittest.TestCase):
    def test_named_sets(self):
        self.assertEqual(text.expand_charset("uppercase"), font.UPPERCASE)
        self.assertEqual(text.expand_charset("digits"), font.DIGITS)
        self.assertEqual(len(text.expand_charset("both-cases")), 52)
        self.assertEqual(text.expand_charset("vowels"), "AEIOU")

    def test_ranges(self):
        self.assertEqual(text.expand_charset("A-F"), "ABCDEF")
        self.assertEqual(text.expand_charset("3-7"), "34567")

    def test_a_backwards_range_is_an_error(self):
        with self.assertRaises(text.TextError):
            text.expand_charset("F-A")

    def test_literal_characters_are_deduplicated(self):
        self.assertEqual(text.expand_charset("AABBC"), "ABC")

    def test_unknown_characters_are_named(self):
        with self.assertRaises(text.TextError) as caught:
            text.expand_charset("ABç")
        self.assertIn("no glyph", str(caught.exception))


class TestStencils(unittest.TestCase):
    def test_bridges_close_every_counter(self):
        # This is the whole point of a stencil: an unbridged O prints as a
        # ring and a loose disc.
        for char in EVERY:
            shape = text.glyph_shape(char, 40.0, 22.0)
            cut = text.stencil_cut(shape, 3.0)
            self.assertEqual(
                text.counters(cut), [],
                f"{char!r} still has a counter that would fall out")

    def test_bridges_are_not_added_where_they_are_not_needed(self):
        shape = text.glyph_shape("L", 40.0, 22.0)
        self.assertTrue(text.bridges(shape, 3.0).is_empty())

    def test_no_bridge_means_no_bridge(self):
        shape = text.glyph_shape("O", 40.0, 22.0)
        self.assertEqual(len(text.counters(text.stencil_cut(shape, 0.0))), 1)

    def test_outline_hollows_the_letter(self):
        solid = text.glyph_shape("A", 40.0, 22.0)
        hollow = text.outline(solid, 2.5)
        self.assertLess(hollow.area(), solid.area())
        self.assertGreater(hollow.area(), 0.0)


class TestStartPoint(unittest.TestCase):
    def test_start_point_lands_on_the_letter(self):
        for char in "ABCLOSg":
            spot = text.start_point(char, 40.0, 20.0)
            self.assertIsNotNone(spot)
            shape = text.glyph_shape(char, 40.0, 20.0)
            x0, y0, x1, y1 = geom.shape_bounds(shape)
            self.assertTrue(x0 - 0.01 <= spot[0] <= x1 + 0.01)
            self.assertTrue(y0 - 0.01 <= spot[1] <= y1 + 0.01)


if __name__ == "__main__":
    unittest.main()
