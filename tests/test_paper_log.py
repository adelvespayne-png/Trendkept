import csv
import os
import tempfile
import unittest

from trendkept.paper_log import (HEADER, ROBOT_MARK, append_pass, build_row,
                                 summarise)

ENTER_PASS = """Autopilot pass (paper) — 1 open position(s)
  V (45 sh, last 366.75): RAISE STOP V: 342.80 -> 346.81 (higher swing low formed)
    -> stop raised to 346.81.
  ENTER_BREAKOUT AAPL: LONG buy 44 @ ~340.00, stop-loss 317.77
  -> submitted: accepted (buy 44 AAPL, stop 317.77)
  Safety check: 2 open position(s), every one protected by a standing stop-loss.
"""

QUIET_PASS = """Autopilot pass (paper) — 1 open position(s)
  V (45 sh, last 355.62): HOLD V: trend intact, stop unchanged (stop 342.80)
  no new entries — the rules say sit tight.
  Safety check: 1 open position(s), every one protected by a standing stop-loss.
"""

EXIT_PASS = """Autopilot pass (paper) — 2 open position(s)
  SPY (104 sh, last 742.15): EXIT SPY: trend break: close below 50-day MA
    -> position closed at market; stop order cancelled.
  V (45 sh, last 361.05): HOLD V: trend intact, stop unchanged (stop 342.80)
"""

NAKED_PASS = QUIET_PASS + "  UNPROTECTED POSITION(S): V — no standing stop\n"


class TestSummarise(unittest.TestCase):
    def test_reads_entries_and_stop_raises(self):
        f = summarise(ENTER_PASS)
        self.assertEqual(f["entered"], ["AAPL"])
        self.assertEqual(f["raised"], ["V"])
        self.assertIn("enter AAPL", f["action"])
        self.assertIn("raise stop V", f["action"])

    def test_reads_exits(self):
        f = summarise(EXIT_PASS)
        self.assertEqual(f["exited"], ["SPY"])
        self.assertEqual(f["held"], ["V"])

    def test_quiet_pass_is_none(self):
        f = summarise(QUIET_PASS)
        self.assertEqual(f["action"], "autopilot none")
        self.assertEqual(f["symbol"], "V")  # what it held


class TestRowBuilding(unittest.TestCase):
    def _rows(self):
        return [HEADER,
                ["2026-07-27", "11", "x", "", "", "", "", "", "", "Y", "n"]]

    def test_day_number_continues_the_sequence(self):
        row = build_row("2026-07-28", ENTER_PASS, self._rows())
        self.assertEqual(row[1], "12")

    def test_row_has_the_right_shape_and_is_marked(self):
        row = build_row("2026-07-28", ENTER_PASS, self._rows())
        self.assertEqual(len(row), len(HEADER))
        self.assertIn(ROBOT_MARK, row[10])
        self.assertEqual(row[9], "Y")

    def test_unprotected_position_flags_the_row(self):
        row = build_row("2026-07-28", NAKED_PASS, self._rows())
        self.assertEqual(row[9], "N")

    def test_never_invents_prices(self):
        # Fills happen at the next open, so price columns must stay blank
        # rather than carrying the *planned* number as if it were real.
        row = build_row("2026-07-28", ENTER_PASS, self._rows())
        self.assertEqual(row[5], "")   # Entry
        self.assertEqual(row[6], "")   # Stop
        self.assertEqual(row[7], "")   # Shares


class TestAppend(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(self.path, "w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(HEADER)
            w.writerow(["2026-07-27", "11", "hand-written", "", "", "", "",
                        "", "", "Y", "transcribed by a human"])

    def tearDown(self):
        os.unlink(self.path)

    def _read(self):
        with open(self.path, newline="") as fh:
            return list(csv.reader(fh))

    def test_appends_and_keeps_the_file_valid_csv(self):
        append_pass(self.path, "2026-07-28", ENTER_PASS)
        rows = self._read()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(len(r) == len(HEADER) for r in rows))
        self.assertEqual(rows[-1][0], "2026-07-28")

    def test_is_idempotent_for_the_same_day(self):
        append_pass(self.path, "2026-07-28", ENTER_PASS)
        second = append_pass(self.path, "2026-07-28", ENTER_PASS)
        self.assertIsNone(second)
        self.assertEqual(len(self._read()), 3)

    def test_never_touches_hand_written_history(self):
        before = self._read()[1]
        append_pass(self.path, "2026-07-28", ENTER_PASS)
        self.assertEqual(self._read()[1], before)

    def test_empty_pass_writes_nothing(self):
        self.assertIsNone(append_pass(self.path, "2026-07-28", "   "))
        self.assertEqual(len(self._read()), 2)

    def test_commas_in_the_note_stay_quoted(self):
        append_pass(self.path, "2026-07-28", ENTER_PASS)
        with open(self.path) as fh:
            raw = fh.read()
        self.assertIn('"', raw)
        self.assertTrue(all(len(r) == len(HEADER) for r in self._read()))


if __name__ == "__main__":
    unittest.main()
