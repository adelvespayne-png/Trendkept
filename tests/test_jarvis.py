"""Tests for Jarvis — the plain-English assistant.

The brain is pure (fetching is injected), so everything here runs offline
against the example CSVs. The tests pin down the promises that matter:
symbols get spotted sensibly, predictions get refused, advice gets refused,
and every scan answer stays descriptive.
"""

import contextlib
import csv
import io
import os
import tempfile
import unittest

from trendkept.cli import main as cli_main
from trendkept.data import load_csv
from trendkept.jarvis import ask, extract_symbols
from trendkept.paper_log import HEADER
from trendkept.web import route

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")
UPTREND_CSV = os.path.join(EXAMPLES, "sample_uptrend.csv")


def fake_fetch(item):
    return load_csv(UPTREND_CSV), item.upper()


class TestSymbolSpotting(unittest.TestCase):
    def test_plain_ticker(self):
        self.assertEqual(extract_symbols("how is AAPL looking?"), ["AAPL"])

    def test_household_names(self):
        self.assertEqual(extract_symbols("check apple and bitcoin"),
                         ["AAPL", "BTC/USD"])

    def test_structured_notations(self):
        self.assertEqual(extract_symbols("scan ES=F, EURUSD and ^FTSE"),
                         ["ES=F", "EURUSD", "^FTSE"])

    def test_csv_paths_pass_through(self):
        self.assertEqual(extract_symbols(f"check {UPTREND_CSV}"),
                         [UPTREND_CSV])

    def test_english_words_are_not_tickers(self):
        self.assertEqual(extract_symbols("should i buy it now"), [])
        self.assertEqual(extract_symbols("what are my rules?"), [])

    def test_uppercase_beats_the_stopword_list(self):
        # "IT" is small talk in lowercase but a real ticker in caps.
        self.assertEqual(extract_symbols("check IT today"), ["IT"])


class TestAsk(unittest.TestCase):
    def test_greeting_states_the_honest_scope(self):
        answer = ask("hello jarvis")
        self.assertEqual(answer.kind, "help")
        self.assertIn("never do", answer.text)
        self.assertIn("predict", answer.text)

    def test_identity_is_honest(self):
        answer = ask("who are you?")
        self.assertIn("not a cloud AI", answer.text)
        self.assertIn("deterministic", answer.text)

    def test_prediction_is_refused_but_the_present_is_reported(self):
        answer = ask("will AAPL go up next week?", fetch=fake_fetch)
        self.assertEqual(answer.kind, "refusal")
        self.assertIn("don't predict", answer.text)
        # ...and it still gives the honest read of today.
        self.assertIn("Confirmed uptrend", answer.text)

    def test_buy_advice_is_refused(self):
        answer = ask("should I buy AAPL?", fetch=fake_fetch)
        self.assertEqual(answer.kind, "refusal")
        self.assertIn("buy or sell", answer.text)

    def test_scan_reads_a_symbol_descriptively(self):
        answer = ask("check AAPL", fetch=fake_fetch)
        self.assertEqual(answer.kind, "scan")
        self.assertIn("Confirmed uptrend", answer.text)
        # Descriptive, never imperative: these words must not appear as
        # instructions anywhere in a scan answer.
        self.assertNotIn("you should buy", answer.text.lower())
        self.assertNotIn("get out now", answer.text.lower())

    def test_scan_without_data_access_fails_honestly(self):
        answer = ask("check AAPL", fetch=None)
        self.assertEqual(answer.kind, "error")

    def test_bad_symbol_fails_in_its_own_line(self):
        def broken(item):
            raise ValueError("no data found for symbol")
        answer = ask("check FOO", fetch=broken)
        self.assertIn("couldn't load", answer.text)

    def test_rules_are_recited_with_the_actual_numbers(self):
        answer = ask("what are my rules?")
        self.assertIn("50", answer.text)
        self.assertIn("200", answer.text)
        self.assertIn("stop", answer.text.lower())
        self.assertIn("1%", answer.text.replace(" ", ""))

    def test_paper_log_summary(self):
        rows = [
            HEADER,
            ["2026-07-20", "1", "none", "", "", "", "", "", "", "Y", "quiet"],
            ["2026-07-21", "2", "autopilot enter AAPL", "AAPL", "", "", "",
             "", "", "Y", "entry"],
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                         newline="") as fh:
            csv.writer(fh).writerows(rows)
            path = fh.name
        try:
            answer = ask("how's the paper log?", paper_log_path=path)
        finally:
            os.unlink(path)
        self.assertIn("2 trading days", answer.text)
        self.assertIn("2 of 2", answer.text)

    def test_journal_points_at_the_journal(self):
        answer = ask("how am I doing?")
        self.assertIn("R-multiples", answer.text)
        self.assertIn(("/journal", "Open the journal"), answer.links)

    def test_why_gives_full_diagnostics_with_a_verdict(self):
        answer = ask("why didn't it enter TEST?", fetch=fake_fetch)
        self.assertIn("Diagnostics", answer.text)
        self.assertIn("Verdict", answer.text)
        # Every gate is marked pass or fail, with the actual numbers.
        self.assertTrue("✓" in answer.text or "✗" in answer.text)
        self.assertIn("average", answer.text)

    def test_briefing_reports_status_and_reads_named_symbols(self):
        answer = ask("morning briefing on TEST", fetch=fake_fetch)
        self.assertIn("Status report", answer.text)
        self.assertIn("Dials", answer.text)
        self.assertIn("Confirmed uptrend", answer.text)

    def test_plain_greeting_is_not_a_briefing(self):
        self.assertEqual(ask("good morning jarvis").kind, "help")

    def test_unknown_question_admits_it(self):
        answer = ask("make me a sandwich")
        self.assertEqual(answer.kind, "error")
        self.assertIn("didn't recognise", answer.text)


class TestJarvisRoute(unittest.TestCase):
    def test_page_serves_greeting_and_form(self):
        status, body = route("/jarvis", {})
        self.assertEqual(status, 200)
        self.assertIn('action="/jarvis"', body)
        self.assertIn("At your service", body)

    def test_rules_question_through_the_web(self):
        status, body = route("/jarvis", {"q": ["what are my rules"]})
        self.assertEqual(status, 200)
        self.assertIn("Trend filter", body)

    def test_scan_through_the_web_on_a_csv(self):
        status, body = route("/jarvis", {"q": [f"check {UPTREND_CSV}"]})
        self.assertEqual(status, 200)
        self.assertIn("Confirmed uptrend", body)

    def test_garbled_dials_never_block_the_chat(self):
        status, body = route("/jarvis", {"q": ["what are my rules"],
                                         "fast_ma": ["banana"]})
        self.assertEqual(status, 200)
        self.assertIn("Trend filter", body)

    def test_hologram_theme_is_offered(self):
        status, body = route("/jarvis", {})
        self.assertIn('value="hologram"', body)

    def test_voice_controls_present(self):
        status, body = route("/jarvis", {})
        self.assertIn('id="jarvis-voice"', body)
        self.assertIn('id="jarvis-mic"', body)

    def test_nav_links_to_jarvis(self):
        status, body = route("/", {})
        self.assertIn('href="/jarvis"', body)


class TestJarvisCli(unittest.TestCase):
    def test_one_shot_question(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli_main(["jarvis", "what", "are", "my", "rules?"])
        self.assertEqual(code, 0)
        self.assertIn("Trend filter", out.getvalue())


if __name__ == "__main__":
    unittest.main()
