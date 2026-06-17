import unittest

from archie.alpaca import decide_management, ManagementAction
from archie.strategy import TrendFollowingStrategy, StrategyConfig
from archie.data import Bar


def uptrend_bars():
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


class TestDecideManagement(unittest.TestCase):
    def setUp(self):
        self.strat = TrendFollowingStrategy(StrategyConfig())

    def test_exit_on_trend_break(self):
        bars = uptrend_bars()
        crash = Bar("d9999", 200, 200, 50, 50)  # close far below the 50-day MA
        bars.append(crash)
        action = decide_management(self.strat, bars, current_stop=180.0, symbol="X")
        self.assertEqual(action.kind, "exit")

    def test_set_stop_when_none_exists(self):
        bars = uptrend_bars()
        action = decide_management(self.strat, bars, current_stop=None, symbol="X")
        self.assertEqual(action.kind, "set_stop")
        self.assertIsNotNone(action.new_stop)

    def test_raise_stop_when_swing_low_is_higher(self):
        bars = uptrend_bars()
        # A deliberately low current stop must be ratcheted up.
        action = decide_management(self.strat, bars, current_stop=1.0, symbol="X")
        self.assertEqual(action.kind, "raise_stop")
        self.assertGreater(action.new_stop, 1.0)

    def test_hold_when_stop_already_high(self):
        bars = uptrend_bars()
        # Stop just below current price (but below it) -> nothing higher to do.
        high_stop = bars[-1].close - 0.01
        action = decide_management(self.strat, bars, current_stop=high_stop,
                                   symbol="X")
        self.assertEqual(action.kind, "hold")

    def test_stop_only_ratchets_up(self):
        bars = uptrend_bars()
        # Across the whole series the decision never lowers a generous stop.
        action = decide_management(self.strat, bars, current_stop=1e9, symbol="X")
        self.assertIn(action.kind, ("hold", "exit"))


class TestActionDescribe(unittest.TestCase):
    def test_describe_variants(self):
        self.assertIn("EXIT", ManagementAction("exit", "x", symbol="A").describe())
        self.assertIn(
            "RAISE STOP",
            ManagementAction("raise_stop", "x", symbol="A",
                             current_stop=1.0, new_stop=2.0).describe(),
        )


class TestFindStopOrderParsing(unittest.TestCase):
    def test_finds_nested_leg_stop(self):
        # Reproduce the order-search logic against a canned OTO order shape.
        from archie.alpaca import AlpacaClient

        orders = [{
            "symbol": "AAPL", "side": "buy", "type": "limit", "status": "new",
            "legs": [{
                "id": "leg1", "symbol": "AAPL", "side": "sell",
                "type": "stop", "status": "held", "stop_price": "90.00",
            }],
        }]

        # Bind list_orders to return our canned data without a network call.
        client = AlpacaClient.__new__(AlpacaClient)
        client.list_orders = lambda status="open": orders  # type: ignore
        found = client.find_stop_order("aapl")
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "leg1")
        self.assertEqual(found["stop_price"], "90.00")

    def test_returns_none_when_absent(self):
        from archie.alpaca import AlpacaClient

        client = AlpacaClient.__new__(AlpacaClient)
        client.list_orders = lambda status="open": []  # type: ignore
        self.assertIsNone(client.find_stop_order("AAPL"))


if __name__ == "__main__":
    unittest.main()
