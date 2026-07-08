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
        self.assertIn("My Trading Diagram", body)
        self.assertIn("how do you trade?", body)
        self.assertIn("rs-preset", body)          # the style presets
        self.assertIn("trendrail-ruleset", body)  # localStorage key

    def test_describe_box_present(self):
        _, body = route("/ruleset", {})
        self.assertIn('name="describe"', body)
        self.assertIn("Describe how you trade", body)

    def test_description_fills_the_diagram(self):
        status, body = route("/ruleset", {"describe": [
            "I'm a cautious beginner with a £5,000 account, I know I "
            "have a habit of chasing"]})
        self.assertEqual(status, 200)
        self.assertIn("Here's how I read that", body)
        self.assertIn('value="0.005"', body)   # cautious -> 0.5% risk
        self.assertIn('value="5000"', body)    # the account size
        self.assertIn('value="0.08"', body)    # chase-prone -> tight limit
        self.assertIn("data-skip-restore", body)

    def test_interpret_description_directly(self):
        from trendrail.web import interpret_description
        # Explicit risk % beats mood words; tempo words map to averages.
        values, notes = interpret_description(
            "long term investor, risk 2%, patient")
        self.assertEqual(values["fast_ma"], "100")
        self.assertEqual(values["slow_ma"], "250")
        self.assertEqual(values["risk"], "0.02")
        self.assertTrue(any("Risk per trade: 2%" in n for n in notes))
        # Risk is capped at 2% no matter what is asked for.
        values, _ = interpret_description("aggressive, risk 10%")
        self.assertEqual(values["risk"], "0.02")
        # Day-trading words pick the fast tempo and warn about it.
        values, notes = interpret_description("I want to day trade quickly")
        self.assertEqual(values["fast_ma"], "20")
        self.assertTrue(any("chopped" in n for n in notes))
        # Nothing recognised -> classic defaults, honestly labelled.
        values, notes = interpret_description("hello there")
        self.assertEqual(values["fast_ma"], "50")
        self.assertTrue(any("classic" in n.lower() for n in notes))

    def test_nav_bar_on_every_page(self):
        for path, params in (("/", {}), ("/ruleset", {}),
                             ("/run", {"csv": [UPTREND_CSV],
                                       "action": ["scan"]})):
            _, body = route(path, params)
            self.assertIn('nav class="top"', body)
            self.assertIn("My Trading Diagram", body)
            self.assertIn('href="/"', body)       # home link everywhere

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

    def test_chart_timeframe_selector_and_line_mode(self):
        # Default window shows candles and the timeframe links.
        status, body = route("/chart", {"csv": [AAPL_CSV]})
        self.assertEqual(status, 200)
        self.assertIn("Timeframe:", body)
        self.assertIn('rect class="candle-up"', body)
        # "everything" on a 2-year file switches to the close-price line.
        status, body = route("/chart", {"csv": [AAPL_CSV],
                                        "window": ["all"]})
        self.assertEqual(status, 200)
        self.assertIn('polyline class="price-line"', body)
        self.assertNotIn('rect class="candle-up"', body)

    def test_index_has_chart_section(self):
        status, body = route("/", {})
        self.assertEqual(status, 200)
        self.assertIn('action="/chart"', body)
        self.assertIn("View chart", body)

    def test_bar_size_selector_present(self):
        _, body = route("/", {})
        self.assertIn('name="interval"', body)
        for key in ("1min", "5min", "30min", "1hour", "4hour", "1day",
                    "1week", "1month"):
            self.assertIn(f'value="{key}"', body)

    def test_weekly_monthly_resample(self):
        from trendrail.data import load_csv
        from trendrail.web import resample_bars
        daily = load_csv(AAPL_CSV)
        weekly = resample_bars(daily, "1week")
        monthly = resample_bars(daily, "1month")
        # ~5 daily bars per weekly bar, ~21 per monthly bar.
        self.assertLess(len(weekly), len(daily) / 4)
        self.assertLess(len(monthly), len(weekly) / 3)
        # Aggregation is honest: month high is the max of its days.
        self.assertAlmostEqual(
            monthly[0].high,
            max(b.high for b in daily if b.date[:7] == monthly[0].date[:7]))
        self.assertEqual(monthly[-1].close, daily[-1].close)

    def test_scan_on_weekly_bars_from_csv(self):
        # Weekly bars shrink history below a 200-bar slow average, so use a
        # weekly-scale ruleset — exactly what a user would do.
        status, body = route("/run", {
            "csv": [AAPL_CSV], "action": ["scan"], "interval": ["1week"],
            "fast_ma": ["10"], "slow_ma": ["40"],
        })
        self.assertEqual(status, 200)
        self.assertIn("1 week bars", body)
        self.assertIn("SIGNAL", body)

    def test_scan_shows_annotated_chart_and_explanations(self):
        status, body = route("/run", {
            "csv": [AAPL_CSV], "action": ["scan"],
        })
        self.assertEqual(status, 200)
        self.assertIn("on the chart", body)
        self.assertIn("<svg", body)
        # Either recent events are explained, or the quiet state is named.
        self.assertTrue("Recent signals, explained" in body
                        or "quiet is the most common" in body)

    def test_rules_panel_shows_the_active_numbers(self):
        # Default diagram: the written rules with default numbers.
        _, body = route("/run", {"csv": [AAPL_CSV], "action": ["scan"],
                                 "risk": ["0.02"]})
        self.assertIn("The rules in force", body)
        self.assertIn("50-bar", body)
        self.assertIn("200-bar", body)
        self.assertIn("12%", body)             # never-chase limit
        self.assertIn("2% of the account", body)
        # A custom diagram: the panel reflects it, not the defaults.
        _, body = route("/run", {"csv": [AAPL_CSV], "action": ["scan"],
                                 "fast_ma": ["20"], "slow_ma": ["100"],
                                 "max_extension_pct": ["0.08"]})
        self.assertIn("20-bar", body)
        self.assertIn("100-bar", body)
        self.assertIn("8%", body)

    def test_rules_panel_on_backtest_and_chart(self):
        _, body = route("/run", {"csv": [UPTREND_CSV],
                                 "action": ["backtest"]})
        self.assertIn("The rules in force", body)
        _, body = route("/chart", {"csv": [AAPL_CSV]})
        self.assertIn("The rules in force", body)

    def test_chart_one_month_window(self):
        status, body = route("/chart", {"csv": [AAPL_CSV],
                                        "window": ["1mo"]})
        self.assertEqual(status, 200)
        self.assertIn("<strong>1 month</strong>", body)

    def test_backtest_draws_trades_on_price_chart(self):
        status, body = route("/run", {
            "csv": [UPTREND_CSV], "account": ["1000"], "risk": ["0.02"],
            "action": ["backtest"],
        })
        self.assertEqual(status, 200)
        self.assertIn("The trades, on the chart", body)
        self.assertIn("marker-entry", body)
        self.assertIn("Equity curve", body)

    def test_intraday_without_alpaca_keys_fails_cleanly(self):
        import os
        from unittest import mock
        from trendrail.web import _fetch_symbol
        from trendrail.fetch import FetchError
        with mock.patch.dict(os.environ, {"APCA_API_KEY_ID": "",
                                          "APCA_API_SECRET_KEY": ""}):
            with self.assertRaises(FetchError) as ctx:
                _fetch_symbol("XYZTEST", "4hour")
        self.assertIn("Alpaca keys", str(ctx.exception))

    def test_watchlist_survives_any_row_exception(self):
        # A provider blowing up with an unexpected error type must produce
        # an error row, never a dead page.
        import trendrail.web as web
        original = web._load_watchlist_item
        web._load_watchlist_item = lambda item: (_ for _ in ()).throw(
            RuntimeError("provider exploded"))
        try:
            status, body = route("/watchlist", {"symbols": ["AAPL"]})
        finally:
            web._load_watchlist_item = original
        self.assertEqual(status, 200)
        self.assertIn("provider exploded", body)

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
