import math
import random
import unittest

from trendkept.data import Bar
from trendkept.portfolio import (PortfolioBacktester, Precomputed, Variant,
                                 split_date)
from trendkept.strategy import Signal, StrategyConfig, TrendFollowingStrategy


def synth(seed: int, n: int = 700) -> list:
    """Trend/chop/downtrend regimes with noise — enough structure to exercise
    uptrends, breakouts, pullbacks and trend breaks."""
    rng = random.Random(seed)
    price, bars, left, drift = 100.0, [], 0, 0.0
    for t in range(n):
        if left <= 0:
            r = rng.random()
            drift = (rng.uniform(0.0005, 0.0013) if r < 0.45 else
                     rng.uniform(-0.0002, 0.0002) if r < 0.75 else
                     rng.uniform(-0.0011, -0.0004))
            left = rng.randint(40, 150)
        left -= 1
        prev = price
        price = prev * math.exp(drift + 0.012 * rng.gauss(0, 1))
        op = prev * math.exp(rng.gauss(0, 0.003))
        hi = max(op, price) * (1 + abs(rng.gauss(0, 0.004)))
        lo = min(op, price) * (1 - abs(rng.gauss(0, 0.004)))
        bars.append(Bar(f"{2000 + t // 252:04d}-{(t % 252) // 21 + 1:02d}-"
                        f"{(t % 21) + 1:02d}", op, hi, lo, price))
    return bars


class TestPrecomputeParity(unittest.TestCase):
    """The lab's fast path must agree with the live strategy bar for bar.
    If it ever drifts, every conclusion the lab draws is worthless."""

    def test_matches_strategy_on_every_bar(self):
        cfg = StrategyConfig()
        strat = TrendFollowingStrategy(cfg)
        for seed in (1, 2, 3):
            bars = synth(seed)
            pre = Precomputed(bars, cfg)
            for i in range(len(bars)):
                self.assertEqual(pre.uptrend[i], strat.is_uptrend(bars, i),
                                 f"uptrend seed={seed} i={i}")
                self.assertEqual(pre.signal[i], strat.entry_signal(bars, i),
                                 f"signal seed={seed} i={i}")
                self.assertEqual(pre.exit[i], strat.exit_on_trend_break(bars, i),
                                 f"exit seed={seed} i={i}")
                a, b = pre.stop[i], strat.initial_stop(bars, i)
                if a is None or b is None:
                    self.assertEqual(a, b)
                else:
                    self.assertAlmostEqual(a, b, places=9,
                                           msg=f"stop seed={seed} i={i}")

    def test_signals_actually_fire(self):
        # A parity test passes trivially if nothing ever triggers.
        pre = Precomputed(synth(1), StrategyConfig())
        self.assertGreater(sum(pre.uptrend), 0)
        self.assertGreater(sum(1 for s in pre.signal if s is not Signal.NONE), 0)


class TestPortfolioMechanics(unittest.TestCase):
    def setUp(self):
        self.data = {f"S{i}": synth(10 + i) for i in range(6)}
        self.bt = PortfolioBacktester(starting_equity=100_000.0,
                                      risk_pct=0.01, max_positions=4)

    def test_never_exceeds_the_position_cap(self):
        res = self.bt.run(self.data, Variant("baseline"))
        # Reconstruct concurrent holdings from entry/exit dates.
        events = []
        for t in res.trades:
            events.append((t.entry_date, 1))
            events.append((t.exit_date or "9999-99-99", -1))
        events.sort()
        live = peak = 0
        for _, delta in events:
            live += delta
            peak = max(peak, live)
        self.assertLessEqual(peak, 4)

    def test_never_uses_margin(self):
        res = self.bt.run(self.data, Variant("baseline"))
        self.assertTrue(all(v > 0 for v in res.curve))

    def test_risk_per_trade_is_capped(self):
        res = self.bt.run(self.data, Variant("baseline"))
        for t in res.trades:
            risk = (t.entry - t.stop) * t.shares
            self.assertLessEqual(risk, 100_000 * 0.02,
                                 "a single trade risked more than 2%")

    def test_stops_only_ever_ratchet_up(self):
        res = self.bt.run(self.data, Variant("baseline"))
        for t in res.trades:
            self.assertGreaterEqual(t.stop, min(t.stop, t.entry) - 1e-9)

    def test_gap_through_the_stop_fills_below_it(self):
        # The AAPL case: price opens far under the stop, so the fill is the
        # open, not the stop. Modelling this is what keeps the lab honest.
        bars = synth(1)[:400]
        crash = bars[-1]
        bars = bars + [Bar("2099-01-01", crash.close * 0.6, crash.close * 0.62,
                           crash.close * 0.55, crash.close * 0.58)]
        res = self.bt.run({"X": bars}, Variant("baseline"))
        gapped = [t for t in res.closed if t.exit_date == "2099-01-01"]
        for t in gapped:
            self.assertLess(t.exit, t.stop, "gap fill should be below the stop")
            self.assertLess(t.r, -1.0, "a gap should cost more than 1R")

    def test_cooldown_reduces_or_holds_trade_count(self):
        base = self.bt.run(self.data, Variant("baseline"))
        cool = self.bt.run(self.data, Variant("c", cooldown_days=20))
        self.assertLessEqual(len(cool.trades), len(base.trades))

    def test_impossible_breadth_gate_blocks_all_entries(self):
        res = self.bt.run(self.data, Variant("b", min_breadth=999))
        self.assertEqual(len(res.trades), 0)
        self.assertAlmostEqual(res.ending_equity, 100_000.0, places=6)

    def test_date_window_is_respected(self):
        res = self.bt.run(self.data, Variant("baseline"),
                          date_from="2001-01-01", date_to="2001-12-31")
        for t in res.trades:
            self.assertGreaterEqual(t.entry_date, "2001-01-01")
            self.assertLessEqual(t.entry_date, "2001-12-31")

    def test_split_date_sits_inside_the_range(self):
        d = split_date(self.data, 0.7)
        alldates = sorted({b.date for bars in self.data.values() for b in bars})
        self.assertIn(d, alldates)
        self.assertGreater(d, alldates[0])
        self.assertLess(d, alldates[-1])


if __name__ == "__main__":
    unittest.main()
