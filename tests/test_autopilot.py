import unittest

from trendkept.cli import (STANDARD_TICKERS, _AUTOPILOT_MAX_POSITIONS,
                           build_parser)


class TestAutopilotSafety(unittest.TestCase):
    def test_paper_only_no_live_flag_exists(self):
        # The autopilot must not even be able to express "live".
        args = build_parser().parse_args(["autopilot"])
        self.assertFalse(hasattr(args, "live"))
        self.assertFalse(args.confirm)  # dry run unless told otherwise
        self.assertEqual(args.risk, 0.01)

    def test_position_cap_is_small(self):
        self.assertLessEqual(_AUTOPILOT_MAX_POSITIONS, 5)

    def test_standard_board_is_the_newsletter_board(self):
        import importlib.util
        import os

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "business", "launch", "trend_check.py")
        spec = importlib.util.spec_from_file_location("tc", path)
        tc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tc)
        self.assertEqual(tc.DEFAULT_TICKERS, STANDARD_TICKERS)
        self.assertEqual(len(STANDARD_TICKERS), 20)


if __name__ == "__main__":
    unittest.main()


class TestExitDeduplication(unittest.TestCase):
    def test_second_pass_skips_when_exit_already_pending(self):
        # Reproduces the 07-20 double-exit: the 21:17 pass queued the SPY
        # market sell; the 22:30 pass must notice and not stack another.
        import argparse

        from trendkept.cli import _manage_one
        from trendkept.strategy import StrategyConfig, TrendFollowingStrategy
        from trendkept.data import Bar

        bars = []
        price = 100.0
        for i in range(260):
            price += 0.5
            bars.append(Bar(f"d{i:04d}", price - 0.2, price + 0.3,
                            price - 0.4, price))
        bars.append(Bar("crash", price, price, 10, 10))  # trend break

        class FakeClient:
            closed = False

            def daily_bars(self, symbol):
                return bars

            def find_stop_order(self, symbol):
                return None

            def list_orders(self, status="open"):
                return [{"symbol": "SPY", "side": "sell", "type": "market",
                         "qty": "104", "status": "accepted"}]

            def close_position(self, symbol):
                FakeClient.closed = True

        args = argparse.Namespace(confirm=True)
        strat = TrendFollowingStrategy(StrategyConfig())
        _manage_one(FakeClient(), strat,
                    {"symbol": "SPY", "qty": "104"}, args)
        self.assertFalse(FakeClient.closed)


class TestScanSummaryIsAuditable(unittest.TestCase):
    """A silent loop can't prove it swept the board. These assert the
    tally line reports the real counts, so a short scan is visible."""

    def _run_pass(self, failing=()):
        import argparse
        import contextlib
        import io
        from unittest import mock

        from trendkept import alpaca as alpaca_mod
        from trendkept.cli import _cmd_autopilot
        from trendkept.data import Bar

        bars = []
        price = 100.0
        for i in range(260):
            price += 0.5
            bars.append(Bar(f"d{i:04d}", price - 0.2, price + 0.3,
                            price - 0.4, price))

        class FakeClient:
            def __init__(self, paper=True):
                pass

            def positions(self):
                return []

            def daily_bars(self, symbol):
                if symbol in failing:
                    raise alpaca_mod.AlpacaError(f"no data for {symbol}")
                return bars

            def cash(self):
                return 1_000_000.0

            def find_stop_order(self, symbol):
                return {"id": "x"}

        buf = io.StringIO()
        with mock.patch.object(alpaca_mod, "AlpacaClient", FakeClient), \
             mock.patch.object(alpaca_mod, "plan_trade",
                               lambda *a, **k: None), \
             contextlib.redirect_stdout(buf):
            _cmd_autopilot(argparse.Namespace(confirm=False, risk=0.01))
        return buf.getvalue()

    def test_clean_pass_reports_the_full_sweep(self):
        out = self._run_pass()
        self.assertIn("Scan: 20 of 20 tickers checked", out)
        self.assertIn("0 met entry conditions", out)
        self.assertIn("0 data error(s)", out)

    def test_data_errors_are_named_not_hidden(self):
        out = self._run_pass(failing={"NFLX", "IWM"})
        self.assertIn("Scan: 18 of 20 tickers checked", out)
        self.assertIn("2 data error(s)", out)
        self.assertIn("NFLX", out)
        self.assertIn("IWM", out)
