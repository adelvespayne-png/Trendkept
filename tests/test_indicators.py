import unittest

from trendkept.data import Bar
from trendkept import indicators as ind


def bar(i, o, h, l, c):
    return Bar(date=f"2023-01-{i:02d}", open=o, high=h, low=l, close=c)


class TestSMA(unittest.TestCase):
    def test_sma_warmup_is_none(self):
        out = ind.sma([1, 2, 3, 4], period=3)
        self.assertIsNone(out[0])
        self.assertIsNone(out[1])
        self.assertAlmostEqual(out[2], 2.0)
        self.assertAlmostEqual(out[3], 3.0)

    def test_sma_rejects_bad_period(self):
        with self.assertRaises(ValueError):
            ind.sma([1, 2, 3], period=0)


class TestSwings(unittest.TestCase):
    def test_detects_high_and_low_pivots(self):
        # A clear peak at index 3 and trough at index 7.
        highs = [10, 11, 12, 20, 12, 11, 10, 5, 10, 11, 12]
        bars = []
        for i, h in enumerate(highs):
            # build a low that troughs at index 7
            lo = h - 2 if i != 7 else 1
            bars.append(bar(i + 1, h - 1, h, lo, h - 1))
        swings = ind.swing_points(bars, window=2)
        highs_found = [s.index for s in swings if s.kind == "high"]
        lows_found = [s.index for s in swings if s.kind == "low"]
        self.assertIn(3, highs_found)
        self.assertIn(7, lows_found)

    def test_higher_highs_and_lows(self):
        from trendkept.indicators import Swing

        rising = [
            Swing(1, 5, "low"), Swing(2, 10, "high"),
            Swing(3, 7, "low"), Swing(4, 12, "high"),
        ]
        self.assertTrue(ind.making_higher_highs_and_lows(rising))

        falling = [
            Swing(1, 7, "low"), Swing(2, 12, "high"),
            Swing(3, 5, "low"), Swing(4, 10, "high"),
        ]
        self.assertFalse(ind.making_higher_highs_and_lows(falling))

    def test_confirmation_lag_is_causal(self):
        # A pivot at index i must not be visible until i + window bars exist.
        highs = [10, 11, 12, 20, 12, 11, 10]
        bars = [bar(i + 1, h - 1, h, h - 2, h - 1) for i, h in enumerate(highs)]
        # As of the peak bar itself (index 3), with window 2, not yet confirmed.
        early = ind.confirmed_swings_through(bars, end=3, window=2)
        self.assertEqual([s for s in early if s.index == 3], [])
        # Two bars later it is confirmed.
        later = ind.confirmed_swings_through(bars, end=5, window=2)
        self.assertTrue(any(s.index == 3 and s.kind == "high" for s in later))


if __name__ == "__main__":
    unittest.main()
