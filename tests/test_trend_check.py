import importlib.util
import os
import unittest

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "business", "launch", "trend_check.py")
_spec = importlib.util.spec_from_file_location("trend_check", _PATH)
trend_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_spec and trend_check)


class TestSummarize(unittest.TestCase):
    def test_counts_every_state(self):
        keys = ([trend_check.ENTRY] * 1 + [trend_check.UPTREND] * 3
                + [trend_check.BREAK] * 12 + [trend_check.NONE] * 3
                + [trend_check.ERROR] * 1)
        line = trend_check.summarize(keys)
        self.assertIn("4 of the 20 are in a confirmed uptrend", line)
        self.assertIn("1 meeting the entry conditions", line)
        self.assertIn("12 have broken their trend", line)
        self.assertIn("3 show nothing confirmed either way", line)
        self.assertIn("1 couldn't be checked (data error)", line)

    def test_quiet_board_stays_short(self):
        line = trend_check.summarize([trend_check.NONE] * 20)
        self.assertIn("0 of the 20 are in a confirmed uptrend", line)
        self.assertIn("20 show nothing confirmed either way", line)
        self.assertNotIn("data error", line)
        self.assertNotIn("entry conditions", line)


class TestBuildDraft(unittest.TestCase):
    def test_draft_contains_all_sections_and_stays_descriptive(self):
        rows = ["| NVDA | 211.22 | **uptrend confirmed — the ruleset's "
                "entry conditions are met** |"]
        draft = trend_check.build_draft(rows, [trend_check.ENTRY],
                                        issue_no="1")
        self.assertIn("Subject: **The Trend Check #1", draft)
        self.assertIn("This week's board", draft)
        self.assertIn("| NVDA | 211.22 |", draft)
        self.assertIn("One honest lesson: R-multiples", draft)
        self.assertIn("R-expectancy", draft)  # week-1 lesson filled in
        self.assertNotIn("[THIS WEEK", draft)  # no brackets left
        self.assertIn("not investment advice", draft)
        # Compliance: broadcast copy must describe, never instruct.
        for banned in ("buy now", "sell now", "get out", "you should buy"):
            self.assertNotIn(banned, draft.lower())

    def test_unwritten_lesson_leaves_a_bracket(self):
        draft = trend_check.build_draft([], [], issue_no="9")
        self.assertIn("[THIS WEEK'S LESSON", draft)

    def test_issue_number_from_calendar(self):
        import datetime

        d = datetime.date
        self.assertEqual(trend_check.next_issue_number(d(2026, 7, 14)), 1)
        self.assertEqual(trend_check.next_issue_number(d(2026, 7, 19)), 1)
        self.assertEqual(trend_check.next_issue_number(d(2026, 7, 26)), 2)
        self.assertEqual(trend_check.next_issue_number(d(2026, 8, 2)), 3)


if __name__ == "__main__":
    unittest.main()
