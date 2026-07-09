"""Trendkept's local dashboard — the rules in a browser, no dependencies.

    python -m trendkept.web
    # then open http://127.0.0.1:8181

The dashboard is a thin skin over the same engine the CLI uses: ``scan`` asks
the rules what to do today, ``backtest`` replays them over a full history and
draws the equity curve. Nothing is computed differently — if the CLI and the
browser ever disagreed, one of them would be lying.

Design constraints, in order:

* **Local-first.** Binds to 127.0.0.1 by default. This is your tool on your
  machine; it never phones home and serves nobody but you.
* **Standard library only**, like the rest of Trendkept. ``http.server`` is plenty
  for one user on localhost.
* **Honest rendering.** The equity curve is the backtester's actual curve —
  idealized fills and all — with the same caveat the CLI prints.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .backtest import Backtester, BacktestResult
from .data import Bar, load_csv, parse_csv_text
from .strategy import Signal, StrategyConfig, TrendFollowingStrategy

_esc = html.escape

DEFAULTS = {
    "account": 1000.0,
    "risk": 0.01,
    "fast_ma": 50,
    "slow_ma": 200,
    "breakout_lookback": 20,
    "pullback_pct": 0.03,
    "max_extension_pct": 0.12,
    "stop_buffer_pct": 0.005,
    "swing_window": 3,
}

# Every strategy knob a personal ruleset can set, in one place. The ruleset
# page edits them, localStorage remembers them per person (local-first, like
# the appearance settings), and the scan/watchlist forms carry them through
# as (mostly hidden) inputs.
RULESET_KEYS = ("fast_ma", "slow_ma", "breakout_lookback", "pullback_pct",
                "max_extension_pct", "stop_buffer_pct", "swing_window")

# Bar sizes: ui key -> (label, Alpaca timeframe, Yahoo interval or None).
# The rules count BARS, not days — 50 bars of 1-hour data is ~50 trading
# hours. Intraday history is limited by the providers (1-min ≈ days, not
# years); 4-hour bars need the Alpaca feed (Yahoo doesn't serve them).
INTERVALS = {
    "1min": ("1 minute", "1Min", "1m"),
    "5min": ("5 minutes", "5Min", "5m"),
    "30min": ("30 minutes", "30Min", "30m"),
    "1hour": ("1 hour", "1Hour", "60m"),
    "4hour": ("4 hours", "4Hour", None),
    "1day": ("1 day", "1Day", "1d"),
    # Weekly/monthly bars are aggregated from daily data ("resample"), so
    # they work with every source — Alpaca, the free providers, and CSVs.
    "1week": ("1 week", "1Week", "resample"),
    "1month": ("1 month", "1Month", "resample"),
}


def resample_bars(bars: List[Bar], interval: str) -> List[Bar]:
    """Aggregate daily bars into weekly or monthly ones (TradingView-style):
    open = first open, high = max, low = min, close = last close. The bar is
    labelled with its first day, and a partial current period is included —
    it's the truth so far, same as any live chart."""
    if interval not in ("1week", "1month"):
        return bars

    def bucket(date: str) -> str:
        from datetime import datetime as _dt

        day = _dt.strptime(date[:10], "%Y-%m-%d")
        if interval == "1month":
            return day.strftime("%Y-%m")
        iso = day.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"

    out: List[Bar] = []
    current = None
    for b in bars:
        key = bucket(b.date)
        if current and current[0] == key:
            current[1].append(b)
        else:
            if current:
                out.append(_merge_bars(current[1]))
            current = (key, [b])
    if current:
        out.append(_merge_bars(current[1]))
    return out


def _merge_bars(group: List[Bar]) -> Bar:
    vol = sum(b.volume or 0 for b in group) or None
    return Bar(
        date=group[0].date,
        open=group[0].open,
        high=max(b.high for b in group),
        low=min(b.low for b in group),
        close=group[-1].close,
        volume=vol,
    )


def _build_cfg(values: Dict[str, str]) -> StrategyConfig:
    """Strategy settings from request params, defaulting each blank knob.

    Raises ValueError on non-numeric input (callers turn that into a clean
    message) and clamps into sane bounds so a typo can't produce a config
    that silently never trades or chases anything.
    """
    def num(key: str, cast, lo, hi):
        raw = values.get(key) or ""
        value = cast(raw) if raw else DEFAULTS[key]
        return min(max(value, lo), hi)

    fast = num("fast_ma", int, 5, 400)
    slow = num("slow_ma", int, 10, 500)
    if fast >= slow:
        raise ValueError("the fast average must be shorter than the slow one")
    return StrategyConfig(
        fast_ma=fast,
        slow_ma=slow,
        breakout_lookback=num("breakout_lookback", int, 5, 200),
        pullback_pct=num("pullback_pct", float, 0.005, 0.2),
        max_extension_pct=num("max_extension_pct", float, 0.02, 0.5),
        stop_buffer_pct=num("stop_buffer_pct", float, 0.0, 0.05),
        swing_window=num("swing_window", int, 2, 10),
    )

# Palette: validated light/dark tokens (single accent-coloured series; status
# greens/reds reserved for P/L deltas only, never decoration).
#
# Everything personal about the look flows through CSS custom properties, and
# the properties are switched by data-* attributes on <html>. The Appearance
# panel (bottom of every page) writes the choices to localStorage, so each
# individual's browser keeps their own look — local-first, like the tool.
_DARK_VARS = """
    --surface: #1a1a19; --page: #0d0d0d;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
    --series: var(--accent-d); --up: #0ca30c; --down: #d03b3b;
"""

_STYLE = """
:root {
  /* customization knobs (Appearance panel) */
  --accent-l: #2a78d6; --accent-d: #3987e5;      /* blue (default) */
  --fs: 15px; --pad-card: 16px; --pad-cell: 6px 8px; --radius: 10px;
}
:root[data-accent="aqua"]    { --accent-l: #1baf7a; --accent-d: #199e70; }
:root[data-accent="violet"]  { --accent-l: #4a3aa7; --accent-d: #9085e9; }
:root[data-accent="orange"]  { --accent-l: #eb6834; --accent-d: #d95926; }
:root[data-accent="magenta"] { --accent-l: #e87ba4; --accent-d: #d55181; }
:root[data-font="small"]   { --fs: 13px; }
:root[data-font="large"]   { --fs: 17px; }
:root[data-density="compact"] { --pad-card: 9px; --pad-cell: 3px 6px; }
:root[data-corners="square"]  { --radius: 2px; }

:root {
  --surface: #fcfcfb; --page: #f9f9f7;
  --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --ring: rgba(11,11,11,0.10);
  --series: var(--accent-l); --up: #006300; --down: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {DARK_VARS}
}
:root[data-theme="dark"] {DARK_VARS}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--ink);
  font: var(--fs)/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 880px; margin: 0 auto; padding: 24px 16px 64px; }
h1 { font-size: 22px; margin: 8px 0 2px; }
h1 small { color: var(--muted); font-weight: 400; font-size: 13px; }
h2 { font-size: 16px; margin: 24px 0 8px; }
.card {
  background: var(--surface); border: 1px solid var(--ring);
  border-radius: var(--radius); padding: var(--pad-card); margin: 12px 0;
}
form.controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; }
form.controls label { display: flex; flex-direction: column; gap: 4px;
  font-size: 12px; color: var(--ink-2); }
form.controls input {
  background: var(--page); color: var(--ink); border: 1px solid var(--axis);
  border-radius: 6px; padding: 7px 9px; font: inherit; width: 130px;
}
form.controls input.wide { width: 220px; }
form.controls button {
  background: var(--series); color: #fff; border: 0; border-radius: 6px;
  padding: 9px 16px; font: inherit; font-weight: 600; cursor: pointer;
}
form.controls button.ghost {
  background: transparent; color: var(--series);
  border: 1px solid var(--series);
}
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; }
.tile { background: var(--surface); border: 1px solid var(--ring);
  border-radius: var(--radius); padding: 12px 14px; }
.tile .k { font-size: 12px; color: var(--muted); }
.tile .v { font-size: 20px; font-weight: 650; margin-top: 2px; }
.tile .v.up { color: var(--up); } .tile .v.down { color: var(--down); }
table.trades { border-collapse: collapse; width: 100%; font-size: 13px; }
table.trades th, table.trades td {
  text-align: right; padding: var(--pad-cell);
  border-bottom: 1px solid var(--grid);
  font-variant-numeric: tabular-nums;
}
table.trades th { color: var(--muted); font-weight: 500; }
table.trades td:first-child, table.trades th:first-child,
table.trades td:last-child, table.trades th:last-child { text-align: left; }
table.trades tr.hit td { font-weight: 650; }
table.trades td.ok { color: var(--up); }
form.controls textarea {
  background: var(--page); color: var(--ink); border: 1px solid var(--axis);
  border-radius: 6px; padding: 7px 9px; font: inherit; width: 340px;
  height: 56px; resize: vertical;
}
form.controls select {
  background: var(--page); color: var(--ink); border: 1px solid var(--axis);
  border-radius: 6px; padding: 7px 9px; font: inherit;
}
svg .candle-up { fill: var(--up); }
svg .candle-down { fill: var(--down); }
svg .wick { stroke: var(--muted); stroke-width: 1; }
svg .ma-fast { stroke: var(--series); stroke-width: 2; fill: none; }
svg .ma-slow { stroke: var(--muted); stroke-width: 2; fill: none; }
svg .stop-line { stroke: var(--down); stroke-width: 1.5;
  stroke-dasharray: 6 4; }
svg .price-line { stroke: var(--ink); stroke-width: 1.5; fill: none;
  opacity: 0.85; }
svg .marker-entry { fill: var(--up); }
svg .marker-exit { fill: var(--down); }
svg .marker-blocked { fill: #eda100; }
:root[data-theme="dark"] svg .marker-blocked { fill: #c98500; }
details.rules-panel { margin: 14px 0; }
details.rules-panel summary { cursor: pointer; font-weight: 650;
  font-size: 14px; color: var(--ink-2); }
ol.rules-list { padding-left: 4px; margin: 4px 0; list-style: none; }
ol.rules-list li { margin: 8px 0; font-size: 13.5px; color: var(--ink-2); }
ol.rules-list li b { color: var(--ink); }
nav.top { display: flex; gap: 10px; align-items: center; margin: 0 0 14px; }
nav.top a.home { font-weight: 750; font-size: 19px; color: var(--ink);
  text-decoration: none; margin-right: auto; }
nav.top a.home small { color: var(--muted); font-weight: 400;
  font-size: 12px; }
nav.top a.btn { background: var(--series); color: #fff; text-decoration:
  none; font-weight: 600; font-size: 13px; padding: 8px 14px;
  border-radius: var(--radius); }
nav.top a.btn.ghost { background: transparent; color: var(--series);
  border: 1px solid var(--series); }
svg text.lbl { font-size: 11px; font-family: inherit; }
.windows a { margin-right: 10px; font-size: 13px; }
.windows strong { margin-right: 10px; font-size: 13px; }
.note { color: var(--ink-2); font-size: 13px; }
.warn { color: var(--down); }
.signal { font-size: 18px; font-weight: 650; }
figure.eq { margin: 0; position: relative; }
figure.eq svg text { fill: var(--muted); font-size: 11px;
  font-family: inherit; font-variant-numeric: tabular-nums; }
#eq-tip { position: absolute; pointer-events: none; display: none;
  background: var(--surface); border: 1px solid var(--ring); border-radius: 6px;
  padding: 4px 8px; font-size: 12px; color: var(--ink);
  box-shadow: 0 2px 8px rgba(0,0,0,.15); white-space: nowrap; }
a { color: var(--series); }
footer { margin-top: 32px; font-size: 12px; color: var(--muted); }
details.appearance { margin-top: 28px; }
details.appearance summary { cursor: pointer; color: var(--muted);
  font-size: 13px; user-select: none; }
details.appearance summary:hover { color: var(--ink-2); }
.appearance-grid { display: flex; flex-wrap: wrap; gap: 12px;
  align-items: end; background: var(--surface); border: 1px solid var(--ring);
  border-radius: var(--radius); padding: var(--pad-card); margin-top: 8px; }
.appearance-grid label { display: flex; flex-direction: column; gap: 4px;
  font-size: 12px; color: var(--ink-2); }
.appearance-grid select {
  background: var(--page); color: var(--ink); border: 1px solid var(--axis);
  border-radius: var(--radius); padding: 6px 8px; font: inherit;
}
.appearance-grid button { background: transparent; color: var(--muted);
  border: 1px solid var(--axis); border-radius: var(--radius);
  padding: 6px 12px; font: inherit; font-size: 13px; cursor: pointer; }
.swatch { display: inline-block; width: 10px; height: 10px;
  border-radius: 50%; background: var(--series); margin-right: 5px; }
""".replace("{DARK_VARS}", "{" + _DARK_VARS + "}")

# Applied in <head>, before first paint, so a saved dark theme never flashes
# light. Kept tiny and defensive: a broken localStorage value must never break
# the page.
_APPEARANCE_BOOT_JS = """
(function () {
  try {
    var s = JSON.parse(localStorage.getItem('trendkept-appearance')) || {};
    ['theme', 'accent', 'font', 'density', 'corners'].forEach(function (k) {
      var v = s[k];
      if (v && v !== 'auto' && v !== 'default') {
        document.documentElement.setAttribute('data-' + k, v);
      }
    });
  } catch (e) { /* corrupted setting: fall back to defaults */ }
})();
"""

_APPEARANCE_PANEL = """
<details class="appearance"><summary><span class="swatch"></span>Appearance
&mdash; make it yours</summary>
<div class="appearance-grid">
  <label>Theme
    <select data-ap="theme">
      <option value="auto">Match my system</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select></label>
  <label>Accent &amp; chart colour
    <select data-ap="accent">
      <option value="default">Blue</option>
      <option value="aqua">Aqua</option>
      <option value="violet">Violet</option>
      <option value="orange">Orange</option>
      <option value="magenta">Magenta</option>
    </select></label>
  <label>Text size
    <select data-ap="font">
      <option value="default">Default</option>
      <option value="small">Small</option>
      <option value="large">Large</option>
    </select></label>
  <label>Density
    <select data-ap="density">
      <option value="default">Comfortable</option>
      <option value="compact">Compact</option>
    </select></label>
  <label>Corners
    <select data-ap="corners">
      <option value="default">Rounded</option>
      <option value="square">Square</option>
    </select></label>
  <button type="button" id="ap-reset">Reset</button>
</div>
<p class="note">Saved in this browser only &mdash; your look, your machine.
Nothing leaves your computer.</p>
</details>
"""

_APPEARANCE_JS = """
(function () {
  var KEY = 'trendkept-appearance';
  var root = document.documentElement;
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || {}; }
    catch (e) { return {}; }
  }
  function save(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {}
  }
  function apply(s) {
    ['theme', 'accent', 'font', 'density', 'corners'].forEach(function (k) {
      var v = s[k];
      if (v && v !== 'auto' && v !== 'default') {
        root.setAttribute('data-' + k, v);
      } else {
        root.removeAttribute('data-' + k);
      }
    });
  }
  var selects = document.querySelectorAll('[data-ap]');
  var settings = load();
  selects.forEach(function (sel) {
    var k = sel.getAttribute('data-ap');
    if (settings[k]) sel.value = settings[k];
    sel.addEventListener('change', function () {
      settings[k] = sel.value;
      save(settings);
      apply(settings);
    });
  });
  var reset = document.getElementById('ap-reset');
  if (reset) reset.addEventListener('click', function () {
    settings = {};
    try { localStorage.removeItem(KEY); } catch (e) {}
    apply(settings);
    selects.forEach(function (sel) { sel.selectedIndex = 0; });
  });
})();
"""

_HOVER_JS = """
(function () {
  var fig = document.getElementById('eq-fig');
  if (!fig) return;
  var svg = fig.querySelector('svg');
  var data = JSON.parse(fig.getAttribute('data-points'));
  var plot = JSON.parse(fig.getAttribute('data-plot'));
  var tip = document.getElementById('eq-tip');
  var hair = document.getElementById('eq-hair');
  var dot = document.getElementById('eq-dot');
  svg.addEventListener('mousemove', function (ev) {
    var box = svg.getBoundingClientRect();
    var sx = (ev.clientX - box.left) / box.width * plot.w;
    var frac = (sx - plot.x0) / (plot.x1 - plot.x0);
    var i = Math.round(frac * (data.length - 1));
    i = Math.max(0, Math.min(data.length - 1, i));
    var p = data[i];
    hair.setAttribute('x1', p[2]); hair.setAttribute('x2', p[2]);
    hair.style.display = 'block';
    dot.setAttribute('cx', p[2]); dot.setAttribute('cy', p[3]);
    dot.style.display = 'block';
    tip.style.display = 'block';
    tip.textContent = p[0] + '  ' + Number(p[1]).toLocaleString(
      undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    var left = p[2] / plot.w * box.width + 10;
    if (left > box.width - 150) left -= 170;
    tip.style.left = left + 'px';
    tip.style.top = (p[3] / plot.h * box.height - 30) + 'px';
  });
  svg.addEventListener('mouseleave', function () {
    tip.style.display = 'none';
    hair.style.display = 'none';
    dot.style.display = 'none';
  });
})();
"""


_NAV = """
<nav class="top">
  <a class="home" href="/">Trendkept <small>disciplined
  trend-following</small></a>
  <a class="btn ghost" href="/">Home</a>
  <a class="btn" href="/ruleset">My Trading Diagram</a>
</nav>"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{_esc(title)}</title>"
        f"<script>{_APPEARANCE_BOOT_JS}</script>"
        f"<style>{_STYLE}</style></head>"
        f"<body><main>{_NAV}{body}"
        f"{_APPEARANCE_PANEL}"
        "<footer>Trendkept is an educational backtesting/paper-trading tool, not "
        "financial advice. Backtests use idealized fills; real markets gap, "
        "slip, and surprise.</footer>"
        f"</main><script>{_HOVER_JS}</script>"
        f"<script>{_APPEARANCE_JS}</script>"
        f"<script>{_RULESET_JS}</script></body></html>"
    )


def _interval_select(current: str) -> str:
    options = "".join(
        f'<option value="{k}"{" selected" if k == current else ""}>'
        f"{label}</option>"
        for k, (label, _, _) in INTERVALS.items())
    return f'<select name="interval">{options}</select>'


def _form(values: Dict[str, str]) -> str:
    def val(key: str) -> str:
        return _esc(values.get(key) or str(DEFAULTS.get(key, "")))

    interval = values.get("interval") or "1day"
    return f"""
<div class="card"><form class="controls" method="get" action="/run">
  <label>Symbol (fetched live)
    <input name="symbol" value="{val('symbol')}" placeholder="AAPL, BTC/USD, EURUSD, ES=F, SPX"></label>
  <label>&hellip;or CSV path
    <input name="csv" class="wide" value="{val('csv')}"
           placeholder="(optional) your own CSV file"></label>
  <label>Account
    <input name="account" value="{val('account')}"></label>
  <label>Risk / trade
    <input name="risk" value="{val('risk')}"></label>
  <label>Fast MA
    <input name="fast_ma" value="{val('fast_ma')}"></label>
  <label>Slow MA
    <input name="slow_ma" value="{val('slow_ma')}"></label>
  <label>Bar size
    {_interval_select(interval)}</label>
  <input type="hidden" name="breakout_lookback" value="{val('breakout_lookback')}">
  <input type="hidden" name="pullback_pct" value="{val('pullback_pct')}">
  <input type="hidden" name="max_extension_pct" value="{val('max_extension_pct')}">
  <input type="hidden" name="stop_buffer_pct" value="{val('stop_buffer_pct')}">
  <input type="hidden" name="swing_window" value="{val('swing_window')}">
  <button name="action" value="scan">Scan today</button>
  <button name="action" value="backtest" class="ghost">Backtest</button>
</form>
<p class="note">Scan asks the rules what to do on the latest bar. Backtest
replays them over the whole history &mdash; trades are drawn on the price
chart. Both run <a href="/ruleset">your Trading Diagram</a>. The averages
count <em>bars</em>: on 1-hour bars, 50 means 50 trading hours. Intraday
history is limited (1-minute &asymp; the last week).<br>
<strong>Symbols:</strong> stocks <code>AAPL</code> &middot; crypto
<code>BTC/USD</code> (24/7) &middot; forex <code>EURUSD</code> &middot;
futures <code>ES=F</code> / <code>GC=F</code> (continuous front month)
&middot; indices <code>SPX</code>, <code>^FTSE</code>. Stocks &amp; crypto
use your Alpaca feed; the rest use the free feed.</p></div>"""


def _watchlist_form(values: Dict[str, str]) -> str:
    def val(key: str) -> str:
        return _esc(values.get(key) or str(DEFAULTS.get(key, "")))

    return f"""
<div class="card"><form class="controls" method="get" action="/watchlist">
  <label>Watchlist &mdash; tickers or CSV paths, separated by spaces or commas
    <textarea name="symbols"
      placeholder="AAPL MSFT BTC/USD EURUSD ES=F SPX">{val('symbols')}</textarea>
  </label>
  <label>Account
    <input name="account" value="{val('account')}"></label>
  <label>Risk / trade
    <input name="risk" value="{val('risk')}"></label>
  <input type="hidden" name="fast_ma" value="{val('fast_ma')}">
  <input type="hidden" name="slow_ma" value="{val('slow_ma')}">
  <input type="hidden" name="breakout_lookback" value="{val('breakout_lookback')}">
  <input type="hidden" name="pullback_pct" value="{val('pullback_pct')}">
  <input type="hidden" name="max_extension_pct" value="{val('max_extension_pct')}">
  <input type="hidden" name="stop_buffer_pct" value="{val('stop_buffer_pct')}">
  <input type="hidden" name="swing_window" value="{val('swing_window')}">
  <button>Scan the watchlist</button>
</form>
<p class="note">One row per symbol: is the uptrend confirmed, is there an
entry today, and the exact stop and position size if there is. Runs
<a href="/ruleset">your Trading Diagram</a> (daily bars &mdash; the
watchlist is the once-a-day discipline habit).</p></div>"""


def _chart_form(values: Dict[str, str]) -> str:
    def val(key: str) -> str:
        return _esc(values.get(key) or str(DEFAULTS.get(key, "")))

    hidden = "".join(
        f'<input type="hidden" name="{k}" value="{val(k)}">'
        for k in RULESET_KEYS)
    interval = values.get("interval") or "1day"
    return f"""
<div class="card"><form class="controls" method="get" action="/chart">
  <label>Chart a symbol
    <input name="symbol" value="{val('symbol')}" placeholder="NVDA, BTC/USD, GC=F, ^FTSE"></label>
  <label>&hellip;or CSV path
    <input name="csv" class="wide" value="{val('csv')}"
           placeholder="(optional) your own CSV file"></label>
  <label>Bar size
    {_interval_select(interval)}</label>
  <label>Timeframe
    <select name="window">
      <option value="1mo">1 month</option>
      <option value="6m" selected>6 months</option>
      <option value="1y">1 year</option>
      <option value="2y">2 years</option>
      <option value="all">Everything</option>
    </select></label>
  {hidden}
  <button>View chart</button>
</form>
<p class="note">Candles with your averages and the current stop drawn on
&mdash; watch a trade working (or breaking) at a glance. Uses
<a href="/ruleset">your Trading Diagram</a>. On intraday bar sizes the
timeframe shows everything the provider serves.</p></div>"""


def interpret_description(text: str) -> Tuple[Dict[str, str], List[str]]:
    """Turn a plain-English trading description into Diagram settings.

    Deliberately simple keyword matching — deterministic, inspectable, and
    honest about what it did (the readback list). It is NOT mind-reading and
    never invents: anything it doesn't recognise stays at the classic
    defaults, and the person reviews every number before saving.
    """
    t = " " + text.lower() + " "
    values: Dict[str, str] = {
        "account": "100000", "risk": "0.01", "fast_ma": "50",
        "slow_ma": "200", "breakout_lookback": "20", "pullback_pct": "0.03",
        "max_extension_pct": "0.12", "stop_buffer_pct": "0.005",
        "swing_window": "3",
    }
    notes: List[str] = []

    fast_words = ("day trad", "scalp", "quick", "fast", "short term",
                  "short-term", "few days", "daily profits", "rapid")
    slow_words = ("long term", "long-term", "invest", "patient", "months",
                  "position trad", "slow", "big trends", "years")
    if any(w in t for w in fast_words):
        values.update(fast_ma="20", slow_ma="100", breakout_lookback="10",
                      swing_window="2", pullback_pct="0.02")
        notes.append("Faster tempo: 20/100 averages, 10-bar breakout — more "
                     "signals, more noise. (Heads-up: honest backtests of "
                     "very fast trend-following usually show it getting "
                     "chopped up — test it before you trust it.)")
    elif any(w in t for w in slow_words):
        values.update(fast_ma="100", slow_ma="250", breakout_lookback="40",
                      swing_window="4", pullback_pct="0.04",
                      max_extension_pct="0.15")
        notes.append("Long-term tempo: 100/250 averages, 40-bar breakout — "
                     "rare entries, big trends, weekly-checking pace.")
    else:
        notes.append("Tempo: the classic written rules (50/200 averages, "
                     "20-bar breakout).")

    cautious_words = ("cautious", "careful", "beginner", "nervous", "new to",
                      "safe", "scared", "small risk")
    aggressive_words = ("aggressive", "confident", "high risk", "risky",
                        "big swings")
    m = re.search(r"risk\D{0,12}?(\d+(?:\.\d+)?)\s*%", t) or \
        re.search(r"(\d+(?:\.\d+)?)\s*%\s*risk", t)
    if m:
        pct = min(max(float(m.group(1)), 0.25), 2.0)
        values["risk"] = str(pct / 100)
        notes.append(f"Risk per trade: {pct:g}% (capped at 2% — that cap "
                     "has no off switch).")
    elif any(w in t for w in cautious_words):
        values["risk"] = "0.005"
        values["max_extension_pct"] = "0.08"
        notes.append("Cautious: 0.5% risk per trade and a stricter "
                     "no-chasing limit.")
    elif any(w in t for w in aggressive_words):
        values["risk"] = "0.02"
        notes.append("Higher risk appetite: 2% per trade — the maximum the "
                     "written rules allow, and it stays capped there.")
    else:
        notes.append("Risk per trade: the standard 1%.")

    m = re.search(r"[£$€]?\s*([\d,]+(?:\.\d+)?)\s*(k)?\s*"
                  r"(?:account|pot|capital|to trade|savings)", t)
    if m:
        amount = float(m.group(1).replace(",", ""))
        if m.group(2):
            amount *= 1000
        if amount >= 100:
            values["account"] = f"{amount:g}"
            notes.append(f"Account size: {amount:,.0f}.")

    if any(w in t for w in ("chas", "fomo", "jump in late", "buy the top")):
        values["max_extension_pct"] = "0.08"
        notes.append("Chase-prone: tightened the never-chase limit to 8% "
                     "above the fast average.")

    return values, notes


def _ruleset_page(values: Optional[Dict[str, str]] = None,
                  readback: Optional[List[str]] = None,
                  described: str = "") -> str:
    v = {
        "ruleset_name": "", "account": "100000", "risk": "0.01",
        "fast_ma": "50", "slow_ma": "200", "breakout_lookback": "20",
        "pullback_pct": "0.03", "max_extension_pct": "0.12",
        "stop_buffer_pct": "0.005", "swing_window": "3",
    }
    if values:
        v.update({k: val for k, val in values.items() if val})

    readback_html = ""
    if readback:
        items = "".join(f"<li>{_esc(n)}</li>" for n in readback)
        readback_html = (
            '<div class="card" style="border-left:3px solid var(--series)">'
            "<strong>Here's how I read that</strong> (keyword matching, not "
            "mind-reading — check the numbers below, then backtest):"
            f"<ul>{items}</ul></div>")

    skip = ' data-skip-restore="1"' if readback else ""
    return f"""
<h2>My Trading Diagram &mdash; how do you trade?</h2>
<p class="note">Describe it in your own words below, or set the dials
directly. Every scan, chart, backtest, and watchlist run then uses
<em>your</em> rules — saved in this browser only. The one thing you can't
switch off is the discipline: every Diagram is trend-following with a stop
and risk-based sizing.</p>

<div class="card"><form class="controls" method="get" action="/ruleset">
  <label style="flex-basis:100%">Describe how you trade, in your own words
    <textarea name="describe" style="width:100%;height:64px"
      placeholder="e.g. I'm a cautious beginner with a £5,000 account — I want to hold winners for weeks and I know I have a habit of chasing.">{_esc(described)}</textarea>
  </label>
  <button>Fill in my Diagram from this</button>
</form></div>
{readback_html}
<div class="card"><form class="controls" id="ruleset-form" method="get"
     action="/run"{skip}>
  <label style="flex-basis:100%">Name your Diagram
    <input name="ruleset_name" class="wide" value="{_esc(v['ruleset_name'])}"
           placeholder="My rules"></label>

  <label style="flex-basis:100%">Trading tempo
    <select id="rs-preset">
      <option value="">&mdash; pick a starting style &mdash;</option>
      <option value="classic">Classic trend (50/200 averages, 20-day
        breakout) &mdash; the written rules</option>
      <option value="faster">Faster swing (20/100 averages, 10-day breakout)
        &mdash; more signals, more noise</option>
      <option value="longterm">Long-term (100/250 averages, 40-day breakout)
        &mdash; fewer, bigger trends</option>
    </select></label>

  <label>Account
    <input name="account" value="{_esc(v['account'])}"></label>
  <label>Risk per trade (fraction)
    <input name="risk" value="{_esc(v['risk'])}"></label>
  <label>Fast average (days)
    <input name="fast_ma" value="{_esc(v['fast_ma'])}"></label>
  <label>Slow average (days)
    <input name="slow_ma" value="{_esc(v['slow_ma'])}"></label>
  <label>Breakout window (days)
    <input name="breakout_lookback" value="{_esc(v['breakout_lookback'])}"></label>

  <details style="flex-basis:100%"><summary class="note">Fine-tuning
  (sensible defaults &mdash; open only if you know why)</summary>
  <div class="controls" style="display:flex;flex-wrap:wrap;gap:12px;
       margin-top:8px">
  <label>Pullback tolerance (fraction of the fast average)
    <input name="pullback_pct" value="{_esc(v['pullback_pct'])}"></label>
  <label>"Never chase" limit (fraction above fast average)
    <input name="max_extension_pct" value="{_esc(v['max_extension_pct'])}"></label>
  <label>Stop buffer below swing low (fraction)
    <input name="stop_buffer_pct" value="{_esc(v['stop_buffer_pct'])}"></label>
  <label>Swing confirmation (bars)
    <input name="swing_window" value="{_esc(v['swing_window'])}"></label>
  </div></details>

  <input type="hidden" name="csv" value="examples/aapl_2015_2017.csv">
  <input type="hidden" name="action" value="backtest">
  <button type="button" id="rs-save">Save my Diagram</button>
  <button class="ghost" type="submit">Save &amp; backtest it (AAPL sample)</button>
  <span class="note" id="rs-status"></span>
</form>
<p class="note"><strong>The discipline part:</strong> changing a rule after
you've started trading it is how systems die. Set it, backtest it, write it
down &mdash; then judge yourself by whether you followed it, not by whether
you liked today's answer.</p></div>
"""

_RULESET_JS = """
(function () {
  var KEY = 'trendkept-ruleset';
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || null; }
    catch (e) { return null; }
  }
  var saved = load();

  // On the home page: quietly fill every form with the saved ruleset.
  if (location.pathname === '/' && saved) {
    document.querySelectorAll('form.controls').forEach(function (form) {
      Object.keys(saved).forEach(function (k) {
        var el = form.querySelector('[name="' + k + '"]');
        if (el) el.value = saved[k];
      });
    });
    var note = document.getElementById('ruleset-note');
    if (note && saved.ruleset_name) {
      note.textContent = 'Using your Trading Diagram: ' + saved.ruleset_name;
    }
  }

  // On the ruleset page: presets, restore, save.
  var form = document.getElementById('ruleset-form');
  if (!form) return;
  var PRESETS = {
    classic:  { fast_ma: 50,  slow_ma: 200, breakout_lookback: 20 },
    faster:   { fast_ma: 20,  slow_ma: 100, breakout_lookback: 10 },
    longterm: { fast_ma: 100, slow_ma: 250, breakout_lookback: 40 }
  };
  // When the page was just filled from a plain-English description, the
  // server's values win — don't clobber them with the previously saved
  // Diagram.
  if (saved && !form.hasAttribute('data-skip-restore')) {
    Object.keys(saved).forEach(function (k) {
      var el = form.querySelector('[name="' + k + '"]');
      if (el) el.value = saved[k];
    });
  }
  var preset = document.getElementById('rs-preset');
  preset.addEventListener('change', function () {
    var p = PRESETS[preset.value];
    if (!p) return;
    Object.keys(p).forEach(function (k) {
      form.querySelector('[name="' + k + '"]').value = p[k];
    });
  });
  function saveNow() {
    var out = {};
    form.querySelectorAll('input[name]').forEach(function (el) {
      if (el.type !== 'hidden' || el.name === 'ruleset_name') {
        out[el.name] = el.value;
      }
    });
    delete out.csv; delete out.action;
    try { localStorage.setItem(KEY, JSON.stringify(out)); } catch (e) {}
    var status = document.getElementById('rs-status');
    if (status) status.textContent =
      'Saved. Scans and the watchlist now use these rules.';
  }
  document.getElementById('rs-save').addEventListener('click', saveNow);
  form.addEventListener('submit', saveNow);  // save-and-backtest path
})();
"""


def equity_curve_svg(
    dates: List[str], curve: List[float], width: int = 800, height: int = 240
) -> str:
    """The backtest equity curve as a self-contained inline SVG.

    A single series, so no legend — the caption names it. Coordinates are also
    embedded as JSON on the wrapping <figure> so the hover crosshair can find
    the nearest bar without recomputing scales in JS.
    """
    if len(curve) < 2:
        return "<p class=\"note\">Not enough data for an equity curve.</p>"

    pad_l, pad_r, pad_t, pad_b = 64, 12, 10, 24
    x0, x1 = pad_l, width - pad_r
    y0, y1 = height - pad_b, pad_t
    lo, hi = min(curve), max(curve)
    if hi == lo:
        hi = lo + 1.0

    def x(i: int) -> float:
        return x0 + (x1 - x0) * i / (len(curve) - 1)

    def y(v: float) -> float:
        return y0 + (y1 - y0) * (v - lo) / (hi - lo)

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(curve))
    points_json = json.dumps(
        [[d, round(v, 2), round(x(i), 1), round(y(v), 1)]
         for i, (d, v) in enumerate(zip(dates, curve))]
    )
    plot_json = json.dumps(
        {"x0": x0, "x1": x1, "w": width, "h": height}
    )

    grid_rows = []
    for k in range(5):
        gv = lo + (hi - lo) * k / 4
        gy = y(gv)
        grid_rows.append(
            f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" '
            'stroke="var(--grid)" stroke-width="1"/>'
            f'<text x="{x0 - 8}" y="{gy + 4:.1f}" text-anchor="end">'
            f"{gv:,.0f}</text>"
        )

    return f"""
<figure class="eq" id="eq-fig" data-points='{_esc(points_json)}'
        data-plot='{_esc(plot_json)}'>
<svg viewBox="0 0 {width} {height}" width="100%" role="img"
     aria-label="Equity curve, {_esc(dates[0])} to {_esc(dates[-1])}">
  {''.join(grid_rows)}
  <line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}"
        stroke="var(--axis)" stroke-width="1"/>
  <polyline points="{pts}" fill="none" stroke="var(--series)"
            stroke-width="2" stroke-linejoin="round"/>
  <line id="eq-hair" x1="0" y1="{y1}" x2="0" y2="{y0}" stroke="var(--axis)"
        stroke-width="1" style="display:none"/>
  <circle id="eq-dot" r="4" fill="var(--series)" stroke="var(--surface)"
          stroke-width="2" style="display:none"/>
  <text x="{x0}" y="{height - 6}">{_esc(dates[0])}</text>
  <text x="{x1}" y="{height - 6}" text-anchor="end">{_esc(dates[-1])}</text>
</svg>
<div id="eq-tip"></div>
<figcaption class="note">Equity curve (idealized fills — an optimistic
ceiling, not a promise).</figcaption>
</figure>"""


# Chart timeframe choices: label -> bars shown (~21 trading days/month for
# daily bars; the window always counts bars, TradingView-style).
CHART_WINDOWS = {"1mo": 21, "6m": 130, "1y": 260, "2y": 520, "all": 10**9}


def _signal_annotations(bars: List[Bar], cfg: StrategyConfig,
                        window: int) -> Tuple[list, List[str]]:
    """Walk the recent bars and annotate the teaching moments:

    * bars where the ruleset's entry conditions were fully met (a fresh
      signal, assuming you were flat), and
    * bars where price did something tempting — a breakout-shaped close or a
      big up-move — but a rule said no, with the rule named.

    Returns (chart markers, human explanations, newest last).
    """
    strat = TrendFollowingStrategy(cfg)
    start = max(cfg.slow_ma, len(bars) - window)
    markers = []
    explained: List[str] = []
    for i in range(start, len(bars)):
        b = bars[i]
        sig = strat.entry_signal(bars, i)
        if sig in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT):
            kind = sig.value.replace("enter_", "")
            markers.append((b.date, "ok",
                            f"{b.date}: entry conditions met ({kind})"))
            explained.append(
                f"{b.date} — the rules ALLOWED an entry ({kind}): confirmed "
                "uptrend, not over-extended, and the pattern completed.")
            continue

        # Tempting but blocked: a breakout-shaped bar or a strong up day.
        breakout_shaped = strat._is_breakout_entry(bars, i)
        pullback_shaped = strat._is_pullback_entry(bars, i)
        if not (breakout_shaped or pullback_shaped):
            continue
        shape = "breakout" if breakout_shaped else "pullback"
        if not strat.is_uptrend(bars, i):
            reason = ("the trend wasn't confirmed — price/averages/structure "
                      "not aligned. Momentum without a confirmed trend is "
                      "how people buy tops")
        elif strat._too_extended(bars, i):
            reason = (f"price was too far above the {cfg.fast_ma}-bar "
                      "average — that's chasing, and chasing buys other "
                      "people's exits")
        else:
            continue
        markers.append((b.date, "blocked",
                        f"{b.date}: {shape} blocked — {reason.split('—')[0]}"))
        explained.append(f"{b.date} — a {shape} LOOKED tempting, but the "
                         f"rules said no: {reason}.")
    return markers, explained


def candle_chart_svg(bars: List[Bar], cfg: StrategyConfig,
                     width: int = 820, height: int = 340,
                     window: int = 130, trades=None,
                     signals=None) -> str:
    """Daily candles with the ruleset drawn on top: both moving averages and
    the current stop level. Hovering any candle shows its OHLC (native
    tooltips — this is a reading chart, not a drawing tool).

    Long windows (over ~a year) switch from candles to a close-price line —
    hundreds of overlapping candle bodies read as mud, and at that zoom the
    question is the trend, not any single day.
    """
    from .indicators import sma

    if len(bars) < 2:
        return "<p class=\"note\">Not enough data to chart.</p>"

    closes = [b.close for b in bars]
    fast_all = sma(closes, cfg.fast_ma)
    slow_all = sma(closes, cfg.slow_ma)

    view = bars[-window:]
    start = len(bars) - len(view)
    fast = fast_all[start:]
    slow = slow_all[start:]

    strat = TrendFollowingStrategy(cfg)
    stop = strat.initial_stop(bars, len(bars) - 1)

    pad_l, pad_r, pad_t, pad_b = 64, 56, 12, 24
    x0, x1 = pad_l, width - pad_r
    y0, y1 = height - pad_b, pad_t
    lo = min(b.low for b in view)
    hi = max(b.high for b in view)
    for series in (fast, slow):
        vals = [v for v in series if v is not None]
        if vals:
            lo, hi = min(lo, min(vals)), max(hi, max(vals))
    if stop is not None:
        lo = min(lo, stop)
    if hi == lo:
        hi = lo + 1.0
    pad = (hi - lo) * 0.04  # headroom so trade markers never clip
    lo, hi = lo - pad, hi + pad

    def y(v: float) -> float:
        return y0 + (y1 - y0) * (v - lo) / (hi - lo)

    n = len(view)
    step = (x1 - x0) / n
    body_w = max(step * 0.6, 1.5)

    def x(i: int) -> float:
        return x0 + (i + 0.5) * step

    grid = []
    for k in range(5):
        gv = lo + (hi - lo) * k / 4
        gy = y(gv)
        grid.append(
            f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" '
            'stroke="var(--grid)" stroke-width="1"/>'
            f'<text class="lbl" x="{x0 - 8}" y="{gy + 4:.1f}" '
            f'text-anchor="end" fill="var(--muted)">{gv:,.0f}</text>')

    if n > 260:
        # Line mode for long windows: the close as a single readable path.
        pts = " ".join(f"{x(i):.1f},{y(b.close):.1f}"
                       for i, b in enumerate(view))
        candles = [f'<polyline class="price-line" points="{pts}"/>']
    else:
        candles = []
        for i, b in enumerate(view):
            cx = x(i)
            top, bot = max(b.open, b.close), min(b.open, b.close)
            cls = "candle-up" if b.close >= b.open else "candle-down"
            body_h = max(y(bot) - y(top), 1.0)
            candles.append(
                f'<g><title>{_esc(b.date)}  O {b.open:,.2f}  H {b.high:,.2f}  '
                f'L {b.low:,.2f}  C {b.close:,.2f}</title>'
                f'<line class="wick" x1="{cx:.1f}" y1="{y(b.high):.1f}" '
                f'x2="{cx:.1f}" y2="{y(b.low):.1f}"/>'
                f'<rect class="{cls}" x="{cx - body_w / 2:.1f}" '
                f'y="{y(top):.1f}" width="{body_w:.1f}" '
                f'height="{body_h:.1f}"/></g>')

    def ma_line(series, css: str, label: str) -> str:
        pts = [f"{x(i):.1f},{y(v):.1f}"
               for i, v in enumerate(series) if v is not None]
        if len(pts) < 2:
            return ""
        last = [v for v in series if v is not None][-1]
        color = "var(--series)" if css == "ma-fast" else "var(--muted)"
        return (f'<polyline class="{css}" points="{" ".join(pts)}"/>'
                f'<text class="lbl" x="{x1 + 4}" y="{y(last) + 4:.1f}" '
                f'fill="{color}">{label}</text>')

    stop_layer = ""
    if stop is not None and lo <= stop <= hi:
        stop_layer = (
            f'<line class="stop-line" x1="{x0}" y1="{y(stop):.1f}" '
            f'x2="{x1}" y2="{y(stop):.1f}"/>'
            f'<text class="lbl" x="{x1 + 4}" y="{y(stop) + 4:.1f}" '
            f'fill="var(--down)">stop {stop:,.2f}</text>')

    # Trade markers (backtest view): entry triangles under the bar, exit
    # triangles above it — the trades drawn where they happened.
    markers = []
    if signals:
        idx = {b.date: i for i, b in enumerate(view)}
        for date, kind, text in signals:
            i = idx.get(date)
            if i is None:
                continue
            if kind == "ok":
                my = y(view[i].low) + 6
                markers.append(
                    f'<path class="marker-entry" d="M {x(i):.1f} {my:.1f} '
                    f'l -5 9 l 10 0 z"><title>{_esc(text)}</title></path>')
            else:
                my = y(view[i].high) - 10
                markers.append(
                    f'<rect class="marker-blocked" x="{x(i) - 4:.1f}" '
                    f'y="{my:.1f}" width="8" height="8" '
                    f'transform="rotate(45 {x(i):.1f} {my + 4:.1f})">'
                    f"<title>{_esc(text)}</title></rect>")
    if trades:
        idx = {b.date: i for i, b in enumerate(view)}
        for t in trades:
            i = idx.get(t.entry_date)
            if i is not None:
                my = y(view[i].low) + 6
                markers.append(
                    f'<path class="marker-entry" d="M {x(i):.1f} {my:.1f} '
                    'l -5 9 l 10 0 z">'
                    f"<title>entry {_esc(t.entry_date)} @ "
                    f"{t.entry_price:,.2f}</title></path>")
            if t.exit_date:
                j = idx.get(t.exit_date)
                if j is not None:
                    my = y(view[j].high) - 6
                    markers.append(
                        f'<path class="marker-exit" d="M {x(j):.1f} {my:.1f} '
                        'l -5 -9 l 10 0 z">'
                        f"<title>exit {_esc(t.exit_date)} @ "
                        f"{(t.exit_price or 0):,.2f} ({_esc(t.exit_reason or '')})"
                        "</title></path>")

    return f"""
<svg viewBox="0 0 {width} {height}" width="100%" role="img"
     aria-label="Daily candles with moving averages and stop level">
  {''.join(grid)}
  <line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}"
        stroke="var(--axis)" stroke-width="1"/>
  {''.join(candles)}
  {ma_line(fast, 'ma-fast', f'{cfg.fast_ma}d')}
  {ma_line(slow, 'ma-slow', f'{cfg.slow_ma}d')}
  {stop_layer}
  {''.join(markers)}
  <text class="lbl" x="{x0}" y="{height - 6}"
        fill="var(--muted)">{_esc(view[0].date)}</text>
  <text class="lbl" x="{x1}" y="{height - 6}" text-anchor="end"
        fill="var(--muted)">{_esc(view[-1].date)}</text>
</svg>"""


def _chart_view(bars: List[Bar], label: str, cfg: StrategyConfig,
                values: Dict[str, str], window_key: str) -> str:
    from urllib.parse import urlencode

    strat = TrendFollowingStrategy(cfg)
    i = len(bars) - 1
    bar = bars[i]
    uptrend = strat.is_uptrend(bars, i)
    signal = strat.entry_signal(bars, i)
    entry_today = signal in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT)

    state = ("uptrend confirmed — entry conditions met today" if entry_today
             else "uptrend confirmed — no entry today" if uptrend
             else "no confirmed uptrend")

    current_iv = values.get("interval") or "1day"
    iv_links = []
    short = {"1min": "1m", "5min": "5m", "30min": "30m", "1hour": "1h",
             "4hour": "4h", "1day": "1D", "1week": "1W", "1month": "1M"}
    for key, text in short.items():
        if key == current_iv:
            iv_links.append(f"<strong>{text}</strong>")
        else:
            q = {k: v for k, v in values.items() if v}
            q["interval"] = key
            iv_links.append(
                f'<a href="/chart?{_esc(urlencode(q))}">{text}</a>')

    links = []
    labels = {"1mo": "1 month", "6m": "6 months", "1y": "1 year",
              "2y": "2 years", "all": "everything"}
    for key, text in labels.items():
        if key == window_key:
            links.append(f"<strong>{text}</strong>")
        else:
            q = {k: v for k, v in values.items() if v}
            q["window"] = key
            links.append(f'<a href="/chart?{_esc(urlencode(q))}">{text}</a>')
    selector = ('<p class="windows">Bar size: ' + "".join(iv_links)
                + "</p>"
                '<p class="windows">Timeframe: ' + "".join(links) + "</p>")

    window = CHART_WINDOWS.get(window_key, 130)
    return (
        f"<h2>Chart &mdash; {_esc(label)} <small>as of {_esc(bar.date)}, "
        f"close {bar.close:,.2f} &middot; {_esc(state)}</small></h2>"
        f'<div class="card">{selector}{candle_chart_svg(bars, cfg, window=window)}'
        '<p class="note">Reading it: daily bars (hover a candle for its '
        "numbers; long timeframes draw the closing price as a line). The "
        "coloured line is your fast average, the grey one your slow average "
        "— the trend is only confirmed with price above both and fast above "
        "slow. The dashed line is where the ruleset would put the stop "
        "right now; it only ever moves up. Reload for the latest daily bar "
        "— daily by design, no tick noise.</p></div>"
        f"{_rules_panel(cfg, open_=False)}"
        '<p class="note"><a href="/">&larr; back to scan &amp; watchlist</a></p>'
    )


def _chart_href(item: str, cfg: StrategyConfig) -> str:
    from urllib.parse import urlencode

    q = {("csv" if _is_csv_item(item) else "symbol"): item,
         "fast_ma": cfg.fast_ma, "slow_ma": cfg.slow_ma,
         "breakout_lookback": cfg.breakout_lookback,
         "pullback_pct": cfg.pullback_pct,
         "max_extension_pct": cfg.max_extension_pct,
         "stop_buffer_pct": cfg.stop_buffer_pct,
         "swing_window": cfg.swing_window}
    return "/chart?" + urlencode(q)


def _rules_panel(cfg: StrategyConfig, risk: Optional[float] = None,
                 open_: bool = True) -> str:
    """The five rules, written out with THIS run's actual numbers plugged
    in — so what the engine just did is never implicit. Shown with every
    scan, backtest, and chart."""
    risk_txt = (f"{risk * 100:g}% of the account"
                if risk is not None else "your chosen % of the account")
    rules = [
        (f"<b>1. Trade only a confirmed uptrend.</b> The close must be above "
         f"both the {cfg.fast_ma}-bar and {cfg.slow_ma}-bar averages, the "
         f"{cfg.fast_ma}-bar must be above the {cfg.slow_ma}-bar, and the "
         f"chart must be making higher highs and higher lows (a swing point "
         f"only counts once {cfg.swing_window} bars confirm it). Fail any of "
         "these: no trade."),
        (f"<b>2. Enter without chasing.</b> Only two entries exist: a "
         f"pullback that comes within {cfg.pullback_pct * 100:g}% of the "
         f"{cfg.fast_ma}-bar average and closes back up, or a breakout above "
         f"the highest high of the last {cfg.breakout_lookback} bars. And "
         f"never when the close is more than "
         f"{cfg.max_extension_pct * 100:g}% above the {cfg.fast_ma}-bar "
         "average — that's chasing."),
        (f"<b>3. The stop goes in with the entry.</b> "
         f"{cfg.stop_buffer_pct * 100:g}% below the most recent confirmed "
         "swing low — decided before the trade, held by the broker."),
        (f"<b>4. Size by risk, not conviction.</b> Shares = ({risk_txt}) "
         "&divide; (entry &minus; stop). A stopped-out trade always costs "
         "the same small fraction."),
        (f"<b>5. Trail the stop; exit on the break.</b> The stop rises under "
         f"each new higher swing low (never falls). Exit entirely on a close "
         f"below the {cfg.fast_ma}-bar average or a lower low."),
    ]
    items = "".join(f"<li>{r}</li>" for r in rules)
    return (f'<details class="rules-panel"{" open" if open_ else ""}>'
            "<summary>The rules in force &mdash; exactly what this run "
            "applied</summary>"
            f'<div class="card"><ol class="rules-list">{items}</ol>'
            '<p class="note">These numbers are your <a href="/ruleset">'
            "Trading Diagram</a>. \"Bar\" means one bar at the size you "
            "picked &mdash; days, hours, or minutes.</p></div></details>")


def _tile(label: str, value: str, cls: str = "") -> str:
    return (f'<div class="tile"><div class="k">{_esc(label)}</div>'
            f'<div class="v {cls}">{_esc(value)}</div></div>')


def _backtest_view(bars: List[Bar], label: str, account: float, risk: float,
                   cfg: StrategyConfig) -> str:
    bt = Backtester(
        strategy=TrendFollowingStrategy(cfg),
        starting_equity=account,
        risk_pct=risk,
    )
    result = bt.run(bars)
    ret = result.total_return_pct
    pf = result.profit_factor
    tiles = "".join([
        _tile("Ending equity", f"{result.ending_equity:,.2f}"),
        _tile("Total return", f"{ret:+.2f}%", "up" if ret >= 0 else "down"),
        _tile("Max drawdown", f"{result.max_drawdown_pct:.2f}%",
              "down" if result.max_drawdown_pct < 0 else ""),
        _tile("Closed trades", str(len(result.closed_trades))),
        _tile("Win rate", f"{result.win_rate:.1f}%"),
        _tile("Expectancy", f"{result.expectancy_r:+.2f}R"),
        _tile("Profit factor", "inf" if pf == float("inf") else f"{pf:.2f}"),
    ])

    rows = []
    for t in result.trades:
        exit_date = _esc(t.exit_date) if t.exit_date else "(open)"
        exit_price = f"{t.exit_price:.2f}" if t.exit_price is not None else "&ndash;"
        rows.append(
            "<tr>"
            f"<td>{_esc(t.entry_date)}</td><td>{exit_date}</td>"
            f"<td>{t.shares:g}</td><td>{t.entry_price:.2f}</td>"
            f"<td>{exit_price}</td><td>{t.r_multiple:+.2f}</td>"
            f"<td>{_esc(t.reason)} / {_esc(t.exit_reason or '-')}</td></tr>"
        )
    trades_table = (
        '<h2>Trades</h2><div class="card"><table class="trades">'
        "<tr><th>Entry</th><th>Exit</th><th>Shares</th><th>Entry $</th>"
        "<th>Exit $</th><th>R</th><th>Reason / exit</th></tr>"
        + "".join(rows) + "</table></div>"
        if result.trades else
        '<p class="note">No trades: the rules never found a confirmed, '
        "unextended entry in this history. Staying out <em>is</em> the "
        "system working.</p>"
    )

    dates = [b.date for b in bars]
    price_chart = (
        '<h2>The trades, on the chart</h2><div class="card">'
        + candle_chart_svg(bars, cfg, window=10**9, trades=result.trades)
        + '<p class="note">&#9650; entry &middot; &#9660; exit (hover a '
        "marker for the numbers). Long histories draw the closing price as "
        "a line.</p></div>"
    )
    return (
        f"<h2>Backtest &mdash; {_esc(label)} "
        f"<small>({len(bars)} bars, {_esc(bars[0].date)} &rarr; "
        f"{_esc(bars[-1].date)})</small></h2>"
        f'<div class="tiles">{tiles}</div>'
        f"{_rules_panel(cfg, risk, open_=False)}"
        f"{price_chart}"
        f'<div class="card"><h2 style="margin-top:0">Equity curve</h2>'
        f"{equity_curve_svg(dates, result.equity_curve)}</div>"
        f"{trades_table}"
    )


def _scan_view(bars: List[Bar], label: str, account: float, risk: float,
               cfg: StrategyConfig) -> str:
    strat = TrendFollowingStrategy(cfg)
    i = len(bars) - 1
    bar = bars[i]
    uptrend = strat.is_uptrend(bars, i)
    signal = strat.entry_signal(bars, i)
    stop = strat.initial_stop(bars, i)

    lines = [
        f"<h2>Scan &mdash; {_esc(label)} <small>as of {_esc(bar.date)}, "
        f"close {bar.close:,.2f}</small></h2>",
        '<div class="card">',
        f"<p>Confirmed uptrend: <strong>{'YES' if uptrend else 'no'}</strong></p>",
    ]
    if signal in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT) and stop:
        per_share = bar.close - stop
        risk_amount = account * risk
        shares = int(risk_amount // per_share) if per_share > 0 else 0
        lines.append(
            f'<p class="signal">SIGNAL: {_esc(signal.value.upper())}</p>'
            f"<p>Suggested entry {bar.close:,.2f} &middot; initial stop "
            f"{stop:,.2f} (risk {per_share:,.2f}/share)<br>"
            f"Position size <strong>{shares} shares</strong> "
            f"(risking {risk_amount:,.2f} = {risk * 100:.1f}% of "
            f"{account:,.2f})</p>"
        )
        if shares == 0:
            lines.append('<p class="warn">Stop is too wide for this account '
                         "at this risk % — skip the trade.</p>")
    else:
        lines.append('<p class="signal">SIGNAL: no entry</p>')
        lines.append(
            '<p class="note">'
            + ("Trend not confirmed — stay out. No exceptions."
               if not uptrend else
               "Uptrend confirmed, but no pullback or breakout entry today "
               "(or price is too extended to chase). Wait.")
            + "</p>"
        )
    lines.append("</div>")
    lines.append(_rules_panel(cfg, risk))

    # The chart, with the recent teaching moments drawn on: where the rules
    # allowed an entry, and where a tempting move was blocked — and why.
    signals, explained = _signal_annotations(bars, cfg, window=130)
    lines.append(
        '<h2>The last months, on the chart</h2><div class="card">'
        + candle_chart_svg(bars, cfg, window=130, signals=signals)
        + '<p class="note">&#9650; the rules allowed an entry &middot; '
        "&#9670; a tempting move the rules blocked (hover any marker for "
        "the why).</p></div>")

    if explained:
        recent = "".join(f"<li>{_esc(e)}</li>" for e in explained[-6:][::-1])
        lines.append(
            '<h2>Recent signals, explained</h2><div class="card">'
            f"<ul>{recent}</ul>"
            '<p class="note">This is the discipline, visible: entries are '
            "rare on purpose, and every blocked marker is a mistake the "
            "rules stopped you making.</p></div>")
    else:
        lines.append(
            '<p class="note">No entry signals and no near-misses in the '
            "recent window — nothing qualified. In a mechanical system, "
            "quiet is the most common (and cheapest) state.</p>")
    return "".join(lines)


def _first(params: Dict[str, List[str]], key: str, default: str = "") -> str:
    vals = params.get(key)
    return vals[0].strip() if vals else default


# Fetched symbols are cached briefly so a watchlist reload doesn't re-hit
# the providers 20 times. Daily bars barely change intraday; ten minutes is
# conservative freshness, and it's the difference between "instant page"
# and "rate-limited by the free endpoints".
_BARS_CACHE: Dict[str, Tuple[float, List[Bar], str]] = {}
_BARS_CACHE_TTL = 600.0


# Symbol classification: one box accepts stocks, crypto, forex, futures,
# and indices, in the notations people actually type.
_INDEX_ALIASES = {
    "SPX": "^GSPC", "SP500": "^GSPC", "S&P500": "^GSPC", "NDX": "^NDX",
    "NASDAQ": "^IXIC", "DJI": "^DJI", "DOW": "^DJI", "FTSE": "^FTSE",
    "FTSE100": "^FTSE", "DAX": "^GDAXI", "NIKKEI": "^N225", "VIX": "^VIX",
    "RUSSELL": "^RUT", "RUT": "^RUT",
}
_CRYPTO_BASES = {"BTC", "ETH", "SOL", "DOGE", "ADA", "XRP", "LTC", "AVAX",
                 "DOT", "LINK", "BCH", "UNI", "AAVE", "SHIB", "MATIC"}
_FIAT = {"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"}


class SymbolInfo:
    """Where a typed symbol lives: its asset class and per-provider names."""

    def __init__(self, kind: str, display: str, yahoo: str,
                 alpaca: Optional[str] = None,
                 alpaca_kind: Optional[str] = None):
        self.kind = kind                # stock/crypto/forex/futures/index
        self.display = display
        self.yahoo = yahoo
        self.alpaca = alpaca            # symbol in Alpaca notation, if served
        self.alpaca_kind = alpaca_kind  # "stock" | "crypto" | None


def classify_symbol(raw: str) -> SymbolInfo:
    s = raw.strip().upper()

    if s.startswith("^") or s in _INDEX_ALIASES:
        return SymbolInfo("index", s, _INDEX_ALIASES.get(s, s))

    if s.endswith("=F") or (s.startswith("/") and 2 <= len(s) <= 5):
        base = s.lstrip("/")
        yahoo = base if base.endswith("=F") else f"{base}=F"
        return SymbolInfo("futures", yahoo, yahoo)

    if s.endswith("=X"):
        return SymbolInfo("forex", s[:-2], s)

    for sep in ("/", "-"):
        if sep in s:
            base, _, quote = s.partition(sep)
            if base in _CRYPTO_BASES:
                quote = quote or "USD"
                return SymbolInfo("crypto", f"{base}/{quote}",
                                  f"{base}-{quote}", f"{base}/{quote}",
                                  "crypto")
            if base in _FIAT and quote in _FIAT:
                return SymbolInfo("forex", f"{base}{quote}",
                                  f"{base}{quote}=X")
    if s in _CRYPTO_BASES:
        return SymbolInfo("crypto", f"{s}/USD", f"{s}-USD", f"{s}/USD",
                          "crypto")
    if len(s) == 6 and s[:3] in _FIAT and s[3:] in _FIAT:
        return SymbolInfo("forex", s, f"{s}=X")

    return SymbolInfo("stock", s, s, s, "stock")


def _fetch_symbol(symbol: str, interval: str = "1day") -> Tuple[List[Bar], str]:
    """Bars for any symbol at the chosen bar size. Alpaca serves stocks and
    crypto when keys are configured (the user's own entitlement); futures,
    forex, and indices ride the free Yahoo feed. Stooq stays in the fallback
    chain for plain stocks only."""
    import time

    label_txt, alpaca_tf, yahoo_iv = INTERVALS.get(interval, INTERVALS["1day"])
    info = classify_symbol(symbol)
    key = f"{info.display}:{interval}"
    hit = _BARS_CACHE.get(key)
    now = time.time()
    if hit and now - hit[0] < _BARS_CACHE_TTL:
        return hit[1], hit[2]

    bars: Optional[List[Bar]] = None
    label = info.display
    if info.kind != "stock":
        label += f" ({info.kind})"
    if interval != "1day":
        label += f" ({label_txt} bars)"

    if info.alpaca_kind and os.environ.get("APCA_API_KEY_ID") and \
            os.environ.get("APCA_API_SECRET_KEY"):
        try:
            from .alpaca import AlpacaClient

            client = AlpacaClient(paper=True, feed="iex")
            if info.alpaca_kind == "crypto":
                bars = client.crypto_bars(info.alpaca, timeframe=alpaca_tf)
            else:
                bars = client.daily_bars(info.alpaca, timeframe=alpaca_tf)
        except Exception:
            bars = None  # fall through to the free providers

    if bars is None:
        if yahoo_iv is None:
            from .fetch import FetchError

            if info.alpaca_kind:
                raise FetchError(
                    f"{label_txt} bars need your Alpaca keys set — the "
                    "free providers don't serve that bar size")
            raise FetchError(
                f"{label_txt} bars aren't available for {info.kind} "
                "symbols — try 1 hour or 1 day")
        from .fetch import fetch_csv  # lazy: offline use needs no network

        # Fail fast: a browser won't wait minutes for a page. Weekly and
        # monthly bars come from daily data, aggregated locally. Stooq only
        # understands plain stocks; everything else goes straight to Yahoo.
        fetch_iv = "1d" if yahoo_iv == "resample" else yahoo_iv
        provider = "auto" if info.kind == "stock" else "yahoo"
        bars = parse_csv_text(fetch_csv(info.yahoo, provider=provider,
                                        timeout=8.0, interval=fetch_iv,
                                        range_="10y"))
        bars = resample_bars(bars, interval)

    _BARS_CACHE[key] = (now, bars, label)
    return bars, label


def _load_bars(symbol: str, csv_path: str,
               interval: str = "1day") -> Tuple[List[Bar], str]:
    # A typed symbol always wins: it means "live data, through today".
    # The CSV path is the offline/bring-your-own-data option.
    if symbol:
        return _fetch_symbol(symbol, interval)
    if csv_path:
        if interval not in ("1day", "1week", "1month"):
            raise ValueError(
                "CSV files hold daily bars — minute/hour bar sizes need a "
                "live symbol (clear the CSV box and type a ticker)")
        bars = load_csv(csv_path)
        label = csv_path
        if interval in ("1week", "1month"):
            bars = resample_bars(bars, interval)
            label += f" ({INTERVALS[interval][0]} bars)"
        return bars, label
    raise ValueError("provide a symbol or a CSV path")


def _is_csv_item(item: str) -> bool:
    """A file if it ends .csv or actually exists — NOT merely because it
    contains a slash (BTC/USD is a crypto pair, not a path)."""
    return item.lower().endswith(".csv") or os.path.exists(item)


def _load_watchlist_item(item: str) -> Tuple[List[Bar], str]:
    """One watchlist entry: a CSV path if it looks/behaves like one, else a
    symbol fetched live (stocks, crypto, forex, futures, indices)."""
    if _is_csv_item(item):
        return load_csv(item), item
    return _load_bars(item, "")


def _watchlist_view(items: List[str], account: float, risk: float,
                    cfg: StrategyConfig) -> str:
    strat = TrendFollowingStrategy(cfg)
    rows = []
    signals = 0
    for item in items:
        try:
            bars, label = _load_watchlist_item(item)
        except FileNotFoundError as exc:
            rows.append(f'<tr><td>{_esc(item)}</td><td colspan="6" '
                        f'class="warn">file not found: '
                        f"{_esc(str(exc.filename))}</td></tr>")
            continue
        except Exception as exc:
            # One bad symbol (rate-limited provider, typo, network blip)
            # must never take down the whole board — report it in its row
            # and keep scanning the rest.
            rows.append(f'<tr><td>{_esc(item)}</td><td colspan="6" '
                        f'class="warn">{_esc(str(exc) or exc.__class__.__name__)}'
                        "</td></tr>")
            continue

        if len(bars) < cfg.slow_ma + 1:
            rows.append(f"<tr><td>{_esc(label)}</td><td colspan=\"6\" "
                        f"class=\"warn\">only {len(bars)} bars — need "
                        f"{cfg.slow_ma + 1} to confirm the trend</td></tr>")
            continue

        i = len(bars) - 1
        bar = bars[i]
        uptrend = strat.is_uptrend(bars, i)
        signal = strat.entry_signal(bars, i)
        stop = strat.initial_stop(bars, i)
        entry = signal in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT)

        chart = _esc(_chart_href(item, cfg))
        name_cell = f'<td><a href="{chart}">{_esc(label)}</a></td>'
        if entry and stop:
            signals += 1
            per_share = bar.close - stop
            shares = (int(account * risk // per_share)
                      if per_share > 0 else 0)
            rows.append(
                f'<tr class="hit">{name_cell}'
                f"<td>{_esc(bar.date)}</td><td>{bar.close:,.2f}</td>"
                f'<td class="ok">YES</td>'
                f'<td class="ok">{_esc(signal.value.replace("enter_", "").upper())}</td>'
                f"<td>{stop:,.2f}</td><td>{shares} sh</td></tr>")
        else:
            note = ("no entry today" if uptrend
                    else "trend not confirmed — stay out")
            rows.append(
                f"<tr>{name_cell}"
                f"<td>{_esc(bar.date)}</td><td>{bar.close:,.2f}</td>"
                f"<td>{'YES' if uptrend else 'no'}</td>"
                f"<td>&ndash;</td><td>&ndash;</td>"
                f"<td>{note}</td></tr>")

    summary = (f"{signals} entry signal{'s' if signals != 1 else ''} today"
               if signals else
               "No entries today across the list — staying out is the "
               "system working.")
    return (
        f"<h2>Watchlist <small>({len(items)} symbols)</small></h2>"
        f'<p class="note">{summary}</p>'
        '<div class="card"><table class="trades">'
        "<tr><th>Symbol</th><th>As of</th><th>Close</th><th>Uptrend</th>"
        "<th>Signal</th><th>Stop</th><th>Size / note</th></tr>"
        + "".join(rows) + "</table></div>"
        f'<p class="note">Sizing risks {risk * 100:.1f}% of '
        f"{account:,.2f} per trade. Stops go in with the order — rule #3.</p>"
    )


def route(path: str, params: Dict[str, List[str]]) -> Tuple[int, str]:
    """Pure request router: (path, query params) -> (status, html page).

    Kept free of any HTTP machinery so tests exercise exactly what the
    browser sees.
    """
    title = ""  # branding lives in the nav bar (_NAV) on every page
    if path == "/":
        note = ('<p class="note" id="ruleset-note">Rules run with the '
                'defaults until you fill in <a href="/ruleset">My Trading '
                "Diagram</a> &mdash; tell Trendkept how <em>you</em> trade "
                "and every scan, chart, and backtest uses your rules.</p>")
        return 200, _page("Trendkept",
                          title + note + _form({}) + _watchlist_form({})
                          + _chart_form({}))

    if path == "/ruleset":
        described = _first(params, "describe")
        if described.strip():
            values, notes = interpret_description(described)
            body = _ruleset_page(values, notes, described)
        else:
            body = _ruleset_page()
        return 200, _page("Trendkept", title + body)

    if path == "/chart":
        values = {k: _first(params, k) for k in
                  ("symbol", "csv", "window", "interval") + RULESET_KEYS}
        chart_interval = values.get("interval") or "1day"
        if chart_interval not in INTERVALS:
            chart_interval = "1day"
        window_key = values.get("window") or "6m"
        if window_key not in CHART_WINDOWS:
            window_key = "6m"

        def chart_fail(msg: str) -> Tuple[int, str]:
            return 200, _page("Trendkept", title + '<div class="card warn">'
                              f"{_esc(msg)}</div>"
                              '<p class="note"><a href="/">&larr; back</a></p>')

        try:
            cfg = _build_cfg(values)
        except ValueError as exc:
            return chart_fail(str(exc) if "average" in str(exc)
                              else "Rule settings must be numbers.")
        try:
            bars, label = _load_bars(values["symbol"], values["csv"],
                                     chart_interval)
        except FileNotFoundError as exc:
            return chart_fail(f"File not found: {exc.filename}")
        except (ValueError, OSError) as exc:
            return chart_fail(str(exc))
        except Exception as exc:
            if exc.__class__.__name__ == "FetchError":
                return chart_fail(str(exc))
            raise
        if len(bars) < cfg.slow_ma + 1:
            return chart_fail(
                f"Need at least {cfg.slow_ma + 1} bars to draw the "
                f"{cfg.slow_ma}-bar average; got {len(bars)}. Intraday "
                "history is limited — try a larger bar size or shorter "
                "averages in My Trading Diagram.")
        if chart_interval != "1day":
            window_key = "all"  # intraday: show everything the feed serves
        return 200, _page("Trendkept",
                          title + _chart_view(bars, label, cfg, values,
                                              window_key))

    if path == "/watchlist":
        values = {k: _first(params, k) for k in
                  ("symbols", "account", "risk") + RULESET_KEYS}
        header = title + _watchlist_form(values)
        try:
            account = float(values["account"] or DEFAULTS["account"])
            risk = float(values["risk"] or DEFAULTS["risk"])
            cfg = _build_cfg(values)
        except ValueError as exc:
            msg = (str(exc) if "average" in str(exc)
                   else "Account, risk, and rule settings must be numbers.")
            return 200, _page("Trendkept", header + '<div class="card warn">'
                              f"{_esc(msg)}</div>")
        if not 0 < risk <= 0.1:
            return 200, _page("Trendkept", header + '<div class="card warn">'
                              "Risk per trade should be a small fraction, "
                              "e.g. 0.01-0.02.</div>")
        items = [s for s in re.split(r"[,\s]+", values["symbols"]) if s]
        if not items:
            return 200, _page("Trendkept", header + '<div class="card warn">'
                              "Add at least one ticker or CSV path.</div>")
        view = _watchlist_view(items, account, risk, cfg)
        return 200, _page("Trendkept", header + view)

    if path != "/run":
        return 404, _page("Not found", "<h1>404</h1><p>Nothing here.</p>")

    values = {k: _first(params, k) for k in
              ("symbol", "csv", "account", "risk", "action", "interval")
              + RULESET_KEYS}
    interval = values.get("interval") or "1day"
    if interval not in INTERVALS:
        interval = "1day"
    header = _form(values)

    def fail(msg: str) -> Tuple[int, str]:
        return 200, _page(
            "Trendkept", header + f'<div class="card warn">{_esc(msg)}</div>')

    try:
        account = float(values["account"] or DEFAULTS["account"])
        risk = float(values["risk"] or DEFAULTS["risk"])
        cfg = _build_cfg(values)
    except ValueError as exc:
        if "average" in str(exc):
            return fail(str(exc))
        return fail("Account, risk, and rule settings must be numbers.")
    if not 0 < risk <= 0.1:
        return fail("Risk per trade should be a small fraction, e.g. 0.01-0.02.")

    try:
        bars, label = _load_bars(values["symbol"], values["csv"], interval)
    except FileNotFoundError as exc:
        return fail(f"File not found: {exc.filename}")
    except (ValueError, OSError) as exc:
        return fail(str(exc))
    except Exception as exc:  # FetchError lives in a lazy import
        if exc.__class__.__name__ == "FetchError":
            return fail(str(exc))
        raise

    if len(bars) < cfg.slow_ma + 1:
        return fail(f"Need at least {cfg.slow_ma + 1} bars to confirm a "
                    f"{cfg.slow_ma}-day trend; got {len(bars)}.")

    if values["action"] == "backtest":
        view = _backtest_view(bars, label, account, risk, cfg)
    else:
        view = _scan_view(bars, label, account, risk, cfg)
    return 200, _page("Trendkept", header + view)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        parsed = urlparse(self.path)
        try:
            status, body = route(parsed.path, parse_qs(parsed.query))
        except Exception as exc:  # always answer; a silent close helps nobody
            status = 500
            body = _page("Trendkept", (
                "<h1>Something went wrong</h1>"
                f'<div class="card warn">{_esc(exc.__class__.__name__)}: '
                f"{_esc(str(exc))}</div>"
                '<p class="note">This is a bug worth reporting — copy the '
                "message above. <a href=\"/\">Back to the dashboard</a>.</p>"))
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        pass  # keep the terminal quiet; this is a local tool


class QuietServer(ThreadingHTTPServer):
    """Browsers abandon connections constantly (tab closed, page refreshed
    mid-load). That's routine, not an error — don't print a scary traceback
    at the person running their own local tool."""

    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        import sys

        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                            BrokenPipeError)):
            return
        super().handle_error(request, client_address)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trendkept-web", description="Trendkept's local web dashboard.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address (default 127.0.0.1 — local only)")
    parser.add_argument("--port", type=int, default=8181)
    args = parser.parse_args(argv)

    server = QuietServer((args.host, args.port), DashboardHandler)
    print(f"Trendkept dashboard: http://{args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
