import math
import unittest

from trendkept.data import Bar
from trendkept.backtest import Backtester, Trade
from trendkept.strategy import TrendFollowingStrategy, StrategyConfig


class TestPositionSizing(unittest.TestCase):
    def test_risk_caps_loss_at_pct_of_equity(self):
        bt = Backtester(starting_equity=1000.0, risk_pct=0.02)
        # entry 100, stop 90 -> risk 10/share; 2% of 1000 = 20 -> 2 shares.
        shares = bt._size(equity=1000.0, entry=100.0, stop=90.0)
        self.assertEqual(shares, 2)
        # If stopped out, loss = 2 * 10 = 20 = 2% of equity.
        self.assertAlmostEqual(shares * (100.0 - 90.0), 20.0)

    def test_size_zero_when_stop_above_entry(self):
        bt = Backtester(starting_equity=1000.0, risk_pct=0.02)
        self.assertEqual(bt._size(1000.0, 100.0, 110.0), 0.0)

    def test_cannot_exceed_cash(self):
        bt = Backtester(starting_equity=100.0, risk_pct=0.02)
        # Tight stop would imply huge size, but cash caps it.
        shares = bt._size(equity=100.0, entry=50.0, stop=49.99)
        self.assertLessEqual(shares * 50.0, 100.0)

    def test_rejects_silly_risk_pct(self):
        with self.assertRaises(ValueError):
            Backtester(risk_pct=0.5)


class TestRMultiple(unittest.TestCase):
    def test_r_multiple(self):
        t = Trade(
            entry_date="d1", entry_price=100.0, shares=2,
            initial_stop=90.0, reason="enter_breakout",
        )
        t.exit_price = 120.0
        # risk/share = 10, profit/share = 20 -> 2R
        self.assertAlmostEqual(t.r_multiple, 2.0)
        self.assertAlmostEqual(t.pnl, 40.0)


class TestEndToEnd(unittest.TestCase):
    def _series(self):
        bars = []
        price = 100.0
        # base
        for i in range(210):
            price += 0.02
            bars.append(Bar(f"b{i:04d}", price - 0.1, price + 0.3, price - 0.3, price))
        # uptrend with pullbacks
        for cycle in range(5):
            for _ in range(20):
                price *= 1.004
                bars.append(Bar(f"u{len(bars):04d}", price * 0.999, price * 1.004,
                                price * 0.996, price))
            for _ in range(6):
                price *= 0.997
                bars.append(Bar(f"p{len(bars):04d}", price * 1.001, price * 1.003,
                                price * 0.997, price))
        # decline
        for _ in range(60):
            price *= 0.995
            bars.append(Bar(f"d{len(bars):04d}", price * 1.001, price * 1.004,
                            price * 0.995, price))
        return bars

    def test_runs_and_respects_risk(self):
        bars = self._series()
        bt = Backtester(starting_equity=1000.0, risk_pct=0.02)
        result = bt.run(bars)

        self.assertEqual(len(result.equity_curve), len(bars))
        # Equity should never go negative in a cash account.
        self.assertTrue(all(v > 0 for v in result.equity_curve))
        # Each closed losing trade should lose roughly <= 2% of the equity it
        # was sized against (allow slack for gaps through the stop).
        for t in result.closed_trades:
            if t.pnl < 0:
                self.assertLess(abs(t.pnl), 1000.0 * 0.05)

    def test_flat_series_makes_no_trades(self):
        flat = [Bar(f"f{i:04d}", 100, 100.1, 99.9, 100) for i in range(300)]
        bt = Backtester(starting_equity=1000.0, risk_pct=0.02)
        result = bt.run(flat)
        self.assertEqual(len(result.trades), 0)
        self.assertAlmostEqual(result.ending_equity, 1000.0)


if __name__ == "__main__":
    unittest.main()
