import unittest

from trendkept.web import interpret_description, _ruleset_page


class TestNamedStyleHonesty(unittest.TestCase):
    def _notes(self, text):
        return " ".join(interpret_description(text)[1]).lower()

    def test_ict_gets_an_honest_not_supported_note(self):
        n = self._notes("I trade ICT smart money and order blocks")
        self.assertIn("trend-follower", n)
        self.assertIn("can't faithfully reproduce", n)
        self.assertIn("breakout of structure", n)

    def test_tjr_and_wyckoff_recognised(self):
        self.assertIn("trend-follower", self._notes("I use TJR setups"))
        self.assertIn("wyckoff", self._notes("I trade Wyckoff accumulation"))

    def test_mean_reversion_is_declined_honestly(self):
        n = self._notes("I mean revert and buy oversold bounces")
        self.assertIn("confirmed uptrend", n)
        self.assertIn("won't fade", n)

    def test_breakout_and_pullback_leans(self):
        self.assertIn("breakout/momentum lean",
                      self._notes("I trade breakouts to new highs"))
        self.assertIn("pullback lean",
                      self._notes("I buy pullbacks within an uptrend"))

    def test_named_style_does_not_break_risk_or_tempo(self):
        # A discretionary mention must not corrupt the numeric dials.
        values, _ = interpret_description(
            "I trade ICT but I'm a cautious beginner risking 1%")
        self.assertEqual(values["risk"], "0.01")
        self.assertIn("fast_ma", values)

    def test_page_shows_clickable_style_examples(self):
        html = _ruleset_page()
        self.assertIn("see how it reads", html)
        self.assertIn("ICT / smart money", html)
        self.assertIn("/ruleset?describe=", html)


if __name__ == "__main__":
    unittest.main()
