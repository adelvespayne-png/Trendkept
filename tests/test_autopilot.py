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
