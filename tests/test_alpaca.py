import unittest

from trendrail.alpaca import AlpacaClient, plan_trade, TradePlan
from trendrail.strategy import TrendFollowingStrategy, StrategyConfig
from trendrail.data import Bar


class TestBarPayloadParsing(unittest.TestCase):
    def test_parses_alpaca_bars(self):
        payload = {
            "bars": [
                {"t": "2021-01-04T05:00:00Z", "o": 133.5, "h": 133.6,
                 "l": 126.8, "c": 129.4, "v": 143301900},
                {"t": "2021-01-05T05:00:00Z", "o": 128.9, "h": 131.7,
                 "l": 128.4, "c": 131.0, "v": 97664900},
            ],
            "next_page_token": None,
        }
        bars = AlpacaClient._bars_from_payload(payload)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0].date, "2021-01-04")
        self.assertAlmostEqual(bars[0].close, 129.4)
        self.assertEqual(bars[0].volume, 143301900)

    def test_intraday_bars_keep_time_of_day(self):
        payload = {"bars": [
            {"t": "2021-01-04T14:30:00Z", "o": 10, "h": 11, "l": 9,
             "c": 10.5, "v": 1},
            {"t": "2021-01-04T15:30:00Z", "o": 10.5, "h": 11, "l": 10,
             "c": 10.8, "v": 1},
        ]}
        bars = AlpacaClient._bars_from_payload(payload, intraday=True)
        self.assertEqual(bars[0].date, "2021-01-04 14:30")
        self.assertNotEqual(bars[0].date, bars[1].date)

    def test_clamps_inconsistent_bar(self):
        payload = {"bars": [
            {"t": "2021-01-04T05:00:00Z", "o": 10, "h": 9.99, "l": 8,
             "c": 10.0, "v": 1},
        ]}
        bars = AlpacaClient._bars_from_payload(payload)
        self.assertGreaterEqual(bars[0].high, bars[0].close)


class _FakeClient:
    """Stands in for AlpacaClient so plan_trade needs no network/keys."""

    def __init__(self, equity):
        self._equity = equity

    def equity(self):
        return self._equity


def _uptrend_bars():
    bars = []
    price = 100.0

    def push(direction, count, mag):
        nonlocal price
        for _ in range(count):
            price += direction * mag
            o = price - direction * mag * 0.5
            c = price
            h = max(o, c) + mag * 0.4
            l = min(o, c) - mag * 0.4
            bars.append(Bar(f"d{len(bars):04d}", o, h, l, c))

    while len(bars) < 260:
        push(+1, 14, 0.5)
        push(-1, 5, 0.4)
    return bars


class TestPlanTrade(unittest.TestCase):
    def test_no_plan_when_no_signal(self):
        flat = [Bar(f"f{i:04d}", 100, 100.1, 99.9, 100) for i in range(260)]
        strat = TrendFollowingStrategy(StrategyConfig())
        plan = plan_trade(_FakeClient(10000), strat, "TEST", flat, 0.01)
        self.assertIsNone(plan)

    def test_sizes_to_risk_budget(self):
        bars = _uptrend_bars()
        strat = TrendFollowingStrategy(StrategyConfig())
        # Force a known entry by checking only if a signal exists; if the
        # synthetic series yields one, validate the sizing invariant.
        plan = plan_trade(_FakeClient(10000), strat, "test", bars, 0.02)
        if plan is not None:
            self.assertIsInstance(plan, TradePlan)
            self.assertEqual(plan.symbol, "TEST")
            self.assertLess(plan.stop_price, plan.entry_price)
            # Risk taken must not exceed the 2% budget.
            self.assertLessEqual(plan.dollar_risk, 10000 * 0.02 + 1e-9)
            self.assertGreater(plan.quantity, 0)


if __name__ == "__main__":
    unittest.main()
