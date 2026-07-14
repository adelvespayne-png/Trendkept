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
        self.assertIn("4 of 20 in a confirmed uptrend", line)
        self.assertIn("1 meeting the ruleset's entry conditions", line)
        self.assertIn("12 where the trend filter is no longer met", line)
        self.assertIn("3 with no confirmed uptrend", line)
        self.assertIn("1 unavailable (data error)", line)

    def test_quiet_board_stays_short(self):
        line = trend_check.summarize([trend_check.NONE] * 20)
        self.assertIn("0 of 20 in a confirmed uptrend", line)
        self.assertIn("20 with no confirmed uptrend", line)
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
        self.assertIn("One honest lesson", draft)
        self.assertIn("not investment advice", draft)
        # Compliance: broadcast copy must describe, never instruct.
        for banned in ("buy now", "sell now", "get out", "you should buy"):
            self.assertNotIn(banned, draft.lower())


if __name__ == "__main__":
    unittest.main()
