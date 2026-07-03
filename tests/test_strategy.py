import unittest

from trendrail.data import Bar
from trendrail.strategy import Signal, StrategyConfig, TrendFollowingStrategy


def make_uptrend(n=260, start=100.0, step=0.5):
    """A rising series that zig-zags, long enough to confirm a 200-day MA.

    A real uptrend makes higher highs *and* higher lows, so we alternate short
    impulse-up legs with shallow pullbacks. A strictly straight line has no
    swing pivots and the strategy would — correctly — refuse to call it a
    trend, so the fixture must actually breathe. ``n`` is treated as a target;
    the series is built in cycles until it reaches at least that length.
    """
    bars = []
    price = start

    def push(direction, count, mag):
        nonlocal price
        for _ in range(count):
            price += direction * mag
            o = price - direction * mag * 0.5
            c = price
            h = max(o, c) + mag * 0.4
            l = min(o, c) - mag * 0.4
            bars.append(Bar(date=f"d{len(bars):04d}", open=o, high=h, low=l, close=c))

    while len(bars) < n:
        push(+1, 14, step)        # impulse up
        push(-1, 5, step * 0.8)   # shallow pullback (stays a higher low)
    return bars


class TestTrendFilter(unittest.TestCase):
    def setUp(self):
        self.strat = TrendFollowingStrategy(StrategyConfig())

    def test_no_uptrend_before_warmup(self):
        bars = make_uptrend(n=120)
        self.assertFalse(self.strat.is_uptrend(bars, len(bars) - 1))

    def test_uptrend_detected_in_rising_series(self):
        bars = make_uptrend(n=300)
        # Inject pullbacks so swing structure (HH/HL) is actually present.
        self.assertTrue(self.strat.is_uptrend(bars, len(bars) - 1))

    def test_downtrend_not_flagged(self):
        bars = make_uptrend(n=300)
        falling = list(reversed(bars))
        # Re-date so they stay ordered.
        falling = [
            Bar(date=f"d{i:04d}", open=b.open, high=b.high, low=b.low, close=b.close)
            for i, b in enumerate(falling)
        ]
        self.assertFalse(self.strat.is_uptrend(falling, len(falling) - 1))


class TestStopAndExit(unittest.TestCase):
    def setUp(self):
        self.strat = TrendFollowingStrategy(StrategyConfig())

    def test_initial_stop_below_entry(self):
        bars = make_uptrend(n=300)
        i = len(bars) - 1
        stop = self.strat.initial_stop(bars, i)
        self.assertIsNotNone(stop)
        self.assertLess(stop, bars[i].close)

    def test_trail_stop_never_lowers(self):
        bars = make_uptrend(n=300)
        i = len(bars) - 1
        high_stop = bars[i].close  # artificially high existing stop
        trailed = self.strat.trail_stop(bars, i, high_stop)
        self.assertGreaterEqual(trailed, high_stop)

    def test_exit_on_close_below_fast_ma(self):
        bars = make_uptrend(n=300)
        # Append a bar that crashes well below the 50-day average.
        crash = Bar(date="d9999", open=200, high=200, low=50, close=50)
        bars.append(crash)
        self.assertTrue(self.strat.exit_on_trend_break(bars, len(bars) - 1))


class TestEntries(unittest.TestCase):
    def test_no_entry_without_uptrend(self):
        strat = TrendFollowingStrategy(StrategyConfig())
        bars = make_uptrend(n=120)
        self.assertEqual(strat.entry_signal(bars, len(bars) - 1), Signal.NONE)


if __name__ == "__main__":
    unittest.main()
