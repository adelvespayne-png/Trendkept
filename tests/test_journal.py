import unittest

from trendkept.journal import (Fill, attach_stops, journal_stats,
                               normalize_fill, pair_fills)
from trendkept.web import _journal_view, route


def _week_one_fills():
    """The owner's real first week, as canned fills."""
    return [
        Fill("NVDA", "buy", 47, 211.29, "2026-07-14T18:26:05Z"),
        Fill("NVDA", "sell", 47, 202.11, "2026-07-17T13:31:44Z"),
        Fill("V", "buy", 45, 362.854667, "2026-07-17T13:34:08Z"),
    ]


def _week_one_stops():
    return [
        {"symbol": "NVDA", "stop_price": "190.19",
         "submitted_at": "2026-07-14T18:26:05Z"},
        {"symbol": "V", "stop_price": "342.80",
         "submitted_at": "2026-07-16T20:58:29Z"},
    ]


class TestPairing(unittest.TestCase):
    def test_pairs_week_one_into_one_trip_and_one_lot(self):
        trips, lots = pair_fills(_week_one_fills())
        self.assertEqual(len(trips), 1)
        self.assertEqual(len(lots), 1)
        t = trips[0]
        self.assertEqual(t.symbol, "NVDA")
        self.assertAlmostEqual(t.pnl, (202.11 - 211.29) * 47, places=2)
        self.assertEqual(lots[0].symbol, "V")

    def test_partial_fills_split_fifo(self):
        fills = [
            Fill("X", "buy", 10, 100, "2026-01-01"),
            Fill("X", "buy", 10, 110, "2026-01-02"),
            Fill("X", "sell", 15, 120, "2026-01-03"),
        ]
        trips, lots = pair_fills(fills)
        self.assertEqual([t.qty for t in trips], [10, 5])
        self.assertEqual([t.entry_price for t in trips], [100, 110])
        self.assertEqual(lots[0].qty, 5)

    def test_orphan_sell_is_ignored(self):
        trips, lots = pair_fills([Fill("X", "sell", 5, 100, "2026-01-01")])
        self.assertEqual((trips, lots), ([], []))


class TestStopsAndStats(unittest.TestCase):
    def test_r_multiple_uses_the_standing_stop(self):
        trips, lots = pair_fills(_week_one_fills())
        attach_stops(trips, lots, _week_one_stops())
        t = trips[0]
        self.assertEqual(t.planned_stop, 190.19)
        # -9.18 loss over 21.10 planned risk ~ -0.44R
        self.assertAlmostEqual(t.r_multiple, -0.435, places=2)
        # The V stop was submitted the evening before the fill: day slack.
        self.assertEqual(lots[0].planned_stop, 342.80)

    def test_stats_scoreboard(self):
        trips, lots = pair_fills(_week_one_fills())
        attach_stops(trips, lots, _week_one_stops())
        s = journal_stats(trips)
        self.assertEqual(s["trades"], 1)
        self.assertEqual(s["wins"], 0)
        self.assertEqual(s["scored"], 1)
        self.assertAlmostEqual(s["total_pnl"], -431.46, places=2)

    def test_normalize_fill_tolerates_junk(self):
        self.assertIsNone(normalize_fill({"side": "buy"}))
        f = normalize_fill({"symbol": "spy", "side": "BUY", "qty": "2",
                            "price": "700.5", "transaction_time": "t"})
        self.assertEqual((f.symbol, f.qty), ("SPY", 2.0))


class TestJournalPage(unittest.TestCase):
    def test_view_renders_trades_and_scoreboard(self):
        trips, lots = pair_fills(_week_one_fills())
        attach_stops(trips, lots, _week_one_stops())
        html = _journal_view(trips, lots, journal_stats(trips))
        self.assertIn("Scoreboard", html)
        self.assertIn("NVDA", html)
        self.assertIn("-0.44R", html)
        self.assertIn("Open positions", html)
        self.assertIn("342.80", html)

    def test_route_without_keys_explains_itself(self):
        import os
        saved = {k: os.environ.pop(k, None)
                 for k in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")}
        try:
            status, body = route("/journal", {})
            self.assertEqual(status, 200)
            self.assertIn("needs", body)
            self.assertIn("APCA_API_KEY_ID", body)
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
