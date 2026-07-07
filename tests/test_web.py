"""Tests for the web dashboard's router — the exact HTML a browser gets."""

import os
import unittest

from trendrail.web import equity_curve_svg, route

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples")
UPTREND_CSV = os.path.join(EXAMPLES, "sample_uptrend.csv")
AAPL_CSV = os.path.join(EXAMPLES, "aapl_2015_2017.csv")


class TestRoutes(unittest.TestCase):
    def test_index_serves_the_form(self):
        status, body = route("/", {})
        self.assertEqual(status, 200)
        self.assertIn('action="/run"', body)
        self.assertIn("Backtest", body)
        self.assertIn("Scan today", body)

    def test_unknown_path_is_404(self):
        status, body = route("/nope", {})
        self.assertEqual(status, 404)

    def test_backtest_on_example_csv(self):
        status, body = route("/run", {
            "csv": [UPTREND_CSV], "account": ["1000"], "risk": ["0.02"],
            "action": ["backtest"],
        })
        self.assertEqual(status, 200)
        self.assertIn("Ending equity", body)
        self.assertIn("Expectancy", body)
        self.assertIn("<svg", body)          # the equity curve rendered
        self.assertIn("Trades", body)

    def test_scan_on_example_csv(self):
        status, body = route("/run", {
            "csv": [AAPL_CSV], "account": ["1000"], "action": ["scan"],
        })
        self.assertEqual(status, 200)
        self.assertIn("SIGNAL", body)
        self.assertIn("Confirmed uptrend", body)

    def test_missing_file_is_a_clean_error_not_a_traceback(self):
        status, body = route("/run", {
            "csv": ["does/not/exist.csv"], "action": ["scan"],
        })
        self.assertEqual(status, 200)
        self.assertIn("File not found", body)

    def test_no_source_given(self):
        status, body = route("/run", {"action": ["scan"]})
        self.assertEqual(status, 200)
        self.assertIn("provide a symbol or a CSV path", body)

    def test_bad_numbers_rejected(self):
        status, body = route("/run", {
            "csv": [UPTREND_CSV], "account": ["lots"], "action": ["scan"],
        })
        self.assertEqual(status, 200)
        self.assertIn("must be numbers", body)

    def test_silly_risk_rejected(self):
        status, body = route("/run", {
            "csv": [UPTREND_CSV], "risk": ["0.5"], "action": ["scan"],
        })
        self.assertEqual(status, 200)
        self.assertIn("small fraction", body)

    def test_too_few_bars_explained(self):
        status, body = route("/run", {
            "csv": [UPTREND_CSV], "slow_ma": ["100000"], "action": ["scan"],
        })
        self.assertEqual(status, 200)
        self.assertIn("Need at least", body)

    def test_user_input_is_escaped(self):
        evil = "<script>alert(1)</script>"
        status, body = route("/run", {"csv": [evil], "action": ["scan"]})
        self.assertEqual(status, 200)
        self.assertNotIn(evil, body)
        self.assertIn("&lt;script&gt;", body)


class TestWatchlist(unittest.TestCase):
    def test_index_includes_watchlist_form(self):
        status, body = route("/", {})
        self.assertEqual(status, 200)
        self.assertIn('action="/watchlist"', body)

    def test_watchlist_scans_multiple_csvs(self):
        status, body = route("/watchlist", {
            "symbols": [f"{UPTREND_CSV}, {AAPL_CSV}"],
            "account": ["1000"], "risk": ["0.02"],
        })
        self.assertEqual(status, 200)
        self.assertIn("Watchlist", body)
        self.assertIn("sample_uptrend.csv", body)
        self.assertIn("aapl_2015_2017.csv", body)
        self.assertIn("Uptrend", body)

    def test_watchlist_bad_item_fails_row_not_page(self):
        status, body = route("/watchlist", {
            "symbols": [f"{UPTREND_CSV} missing/nope.csv"],
        })
        self.assertEqual(status, 200)
        self.assertIn("file not found", body)          # the broken row
        self.assertIn("sample_uptrend.csv", body)      # the good row survives

    def test_watchlist_empty_prompts(self):
        status, body = route("/watchlist", {"symbols": ["   "]})
        self.assertEqual(status, 200)
        self.assertIn("Add at least one", body)

    def test_watchlist_escapes_input(self):
        evil = "<script>alert(1)</script>"
        status, body = route("/watchlist", {"symbols": [evil]})
        self.assertEqual(status, 200)
        self.assertNotIn(evil, body)


class TestAppearance(unittest.TestCase):
    """The customization layer: every page carries the panel, the boot
    script, and the CSS hooks the panel's settings switch on."""

    def test_every_page_has_the_appearance_panel(self):
        for path, params in (
            ("/", {}),
            ("/run", {"csv": [UPTREND_CSV], "action": ["scan"]}),
            ("/watchlist", {"symbols": [UPTREND_CSV]}),
        ):
            status, body = route(path, params)
            self.assertEqual(status, 200)
            self.assertIn('class="appearance"', body)
            self.assertIn("trendrail-appearance", body)   # localStorage key

    def test_theme_override_hooks_exist(self):
        _, body = route("/", {})
        # Explicit choice must beat the OS preference in both directions.
        self.assertIn(':root[data-theme="dark"]', body)
        self.assertIn(':not([data-theme="light"])', body)
        # The dark-vars template must expand into a *braced* CSS block —
        # an unsubstituted or brace-less expansion is malformed CSS that
        # silently kills dark mode (regression).
        self.assertNotIn("{DARK_VARS}", body)
        self.assertRegex(body, r':root\[data-theme="dark"\]\s*\{\s*\n?\s*--surface')

    def test_accent_font_density_corner_hooks_exist(self):
        _, body = route("/", {})
        for hook in ('[data-accent="aqua"]', '[data-accent="violet"]',
                     '[data-accent="orange"]', '[data-accent="magenta"]',
                     '[data-font="large"]', '[data-density="compact"]',
                     '[data-corners="square"]'):
            self.assertIn(hook, body)

    def test_all_panel_options_have_css_or_default(self):
        # Every <option value="X"> in the panel is either a default/auto (no
        # attribute set) or has a matching :root[data-*="X"] rule.
        import re as _re
        _, body = route("/", {})
        panel = body[body.index('class="appearance"'):]
        panel = panel[:panel.index("</details>")]
        for select in _re.findall(r'<select data-ap="(\w+)">(.*?)</select>',
                                  panel, _re.S):
            key, options_html = select
            for value in _re.findall(r'option value="([\w-]+)"', options_html):
                if value in ("auto", "default"):
                    continue
                self.assertIn(f'[data-{key}="{value}"]', body,
                              f"panel offers {key}={value} but no CSS hook")


class TestRuleset(unittest.TestCase):
    def test_ruleset_page_serves(self):
        status, body = route("/ruleset", {})
        self.assertEqual(status, 200)
        self.assertIn("How do you trade?", body)
        self.assertIn("rs-preset", body)          # the style presets
        self.assertIn("trendrail-ruleset", body)  # localStorage key

    def test_index_links_to_ruleset(self):
        _, body = route("/", {})
        self.assertIn('href="/ruleset"', body)

    def test_run_honours_custom_knobs(self):
        # An absurdly tight "never chase" limit must be accepted and applied.
        status, body = route("/run", {
            "csv": [AAPL_CSV], "action": ["scan"],
            "max_extension_pct": ["0.02"], "fast_ma": ["20"],
            "slow_ma": ["100"], "breakout_lookback": ["10"],
        })
        self.assertEqual(status, 200)
        self.assertIn("SIGNAL", body)

    def test_fast_must_be_below_slow(self):
        status, body = route("/run", {
            "csv": [AAPL_CSV], "action": ["scan"],
            "fast_ma": ["200"], "slow_ma": ["50"],
        })
        self.assertEqual(status, 200)
        self.assertIn("fast average must be shorter", body)

    def test_watchlist_honours_ruleset_knobs(self):
        # A huge slow MA -> every row reports not enough history.
        # (sample_uptrend.csv has 488 bars, under the 501 needed.)
        status, body = route("/watchlist", {
            "symbols": [UPTREND_CSV], "slow_ma": ["500"],
        })
        self.assertEqual(status, 200)
        self.assertIn("need 501", body)

    def test_build_cfg_clamps_nonsense(self):
        from trendrail.web import _build_cfg
        cfg = _build_cfg({"pullback_pct": "9", "swing_window": "999",
                          "fast_ma": "1", "slow_ma": "50000"})
        self.assertLessEqual(cfg.pullback_pct, 0.2)
        self.assertLessEqual(cfg.swing_window, 10)
        self.assertGreaterEqual(cfg.fast_ma, 5)
        self.assertLessEqual(cfg.slow_ma, 500)


class TestChart(unittest.TestCase):
    def test_chart_page_renders_candles_mas_and_stop(self):
        status, body = route("/chart", {"csv": [AAPL_CSV]})
        self.assertEqual(status, 200)
        self.assertIn("candle-", body)     # candle bodies
        self.assertIn("50d", body)         # fast MA label
        self.assertIn("200d", body)        # slow MA label
        self.assertIn("stop", body)        # the stop line
        self.assertIn("Chart", body)

    def test_chart_missing_source(self):
        status, body = route("/chart", {})
        self.assertEqual(status, 200)
        self.assertIn("provide a symbol or a CSV path", body)

    def test_chart_too_few_bars(self):
        status, body = route("/chart", {"csv": [UPTREND_CSV],
                                        "slow_ma": ["500"]})
        self.assertEqual(status, 200)
        self.assertIn("Need at least", body)

    def test_watchlist_rows_link_to_chart(self):
        status, body = route("/watchlist", {"symbols": [AAPL_CSV]})
        self.assertEqual(status, 200)
        self.assertIn('href="/chart?', body)

    def test_candle_svg_direct(self):
        from trendrail.data import load_csv
        from trendrail.strategy import StrategyConfig
        from trendrail.web import candle_chart_svg
        bars = load_csv(AAPL_CSV)
        svg = candle_chart_svg(bars, StrategyConfig())
        self.assertIn("<svg", svg)
        self.assertIn("candle-up", svg)
        self.assertIn("candle-down", svg)


class TestEquityCurveSvg(unittest.TestCase):
    def test_renders_polyline_and_labels(self):
        dates = ["2023-01-0%d" % d for d in range(1, 6)]
        curve = [1000.0, 1010.0, 1005.0, 1030.0, 1050.0]
        svg = equity_curve_svg(dates, curve)
        self.assertIn("<polyline", svg)
        self.assertIn("2023-01-01", svg)
        self.assertIn("2023-01-05", svg)
        self.assertIn("data-points", svg)

    def test_flat_curve_does_not_divide_by_zero(self):
        svg = equity_curve_svg(["a", "b"], [1000.0, 1000.0])
        self.assertIn("<polyline", svg)

    def test_single_point_degrades_gracefully(self):
        svg = equity_curve_svg(["a"], [1000.0])
        self.assertIn("Not enough data", svg)


if __name__ == "__main__":
    unittest.main()
