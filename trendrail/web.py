"""Trendrail's local dashboard — the rules in a browser, no dependencies.

    python -m trendrail.web
    # then open http://127.0.0.1:8181

The dashboard is a thin skin over the same engine the CLI uses: ``scan`` asks
the rules what to do today, ``backtest`` replays them over a full history and
draws the equity curve. Nothing is computed differently — if the CLI and the
browser ever disagreed, one of them would be lying.

Design constraints, in order:

* **Local-first.** Binds to 127.0.0.1 by default. This is your tool on your
  machine; it never phones home and serves nobody but you.
* **Standard library only**, like the rest of Trendrail. ``http.server`` is plenty
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
}

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
    var s = JSON.parse(localStorage.getItem('trendrail-appearance')) || {};
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
  var KEY = 'trendrail-appearance';
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


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{_esc(title)}</title>"
        f"<script>{_APPEARANCE_BOOT_JS}</script>"
        f"<style>{_STYLE}</style></head>"
        f"<body><main>{body}"
        f"{_APPEARANCE_PANEL}"
        "<footer>Trendrail is an educational backtesting/paper-trading tool, not "
        "financial advice. Backtests use idealized fills; real markets gap, "
        "slip, and surprise.</footer>"
        f"</main><script>{_HOVER_JS}</script>"
        f"<script>{_APPEARANCE_JS}</script></body></html>"
    )


def _form(values: Dict[str, str]) -> str:
    def val(key: str) -> str:
        return _esc(values.get(key) or str(DEFAULTS.get(key, "")))

    return f"""
<div class="card"><form class="controls" method="get" action="/run">
  <label>Symbol (fetched live)
    <input name="symbol" value="{val('symbol')}" placeholder="AAPL"></label>
  <label>&hellip;or CSV path
    <input name="csv" class="wide" value="{val('csv')}"
           placeholder="examples/aapl_2015_2017.csv"></label>
  <label>Account
    <input name="account" value="{val('account')}"></label>
  <label>Risk / trade
    <input name="risk" value="{val('risk')}"></label>
  <label>Fast MA
    <input name="fast_ma" value="{val('fast_ma')}"></label>
  <label>Slow MA
    <input name="slow_ma" value="{val('slow_ma')}"></label>
  <button name="action" value="scan">Scan today</button>
  <button name="action" value="backtest" class="ghost">Backtest</button>
</form>
<p class="note">Scan asks the rules what to do <em>today</em>. Backtest replays
them over the whole history. Same engine as the CLI.</p></div>"""


def _watchlist_form(values: Dict[str, str]) -> str:
    def val(key: str) -> str:
        return _esc(values.get(key) or str(DEFAULTS.get(key, "")))

    return f"""
<div class="card"><form class="controls" method="get" action="/watchlist">
  <label>Watchlist &mdash; tickers or CSV paths, separated by spaces or commas
    <textarea name="symbols"
      placeholder="AAPL MSFT NVDA examples/aapl_2015_2017.csv">{val('symbols')}</textarea>
  </label>
  <label>Account
    <input name="account" value="{val('account')}"></label>
  <label>Risk / trade
    <input name="risk" value="{val('risk')}"></label>
  <button>Scan the watchlist</button>
</form>
<p class="note">One row per symbol: is the uptrend confirmed, is there an
entry today, and the exact stop and position size if there is.</p></div>"""


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
    return (
        f"<h2>Backtest &mdash; {_esc(label)} "
        f"<small>({len(bars)} bars, {_esc(bars[0].date)} &rarr; "
        f"{_esc(bars[-1].date)})</small></h2>"
        f'<div class="tiles">{tiles}</div>'
        f'<div class="card">{equity_curve_svg(dates, result.equity_curve)}</div>'
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
    return "".join(lines)


def _first(params: Dict[str, List[str]], key: str, default: str = "") -> str:
    vals = params.get(key)
    return vals[0].strip() if vals else default


def _load_bars(symbol: str, csv_path: str) -> Tuple[List[Bar], str]:
    if csv_path:
        return load_csv(csv_path), csv_path
    if symbol:
        from .fetch import fetch_csv  # lazy: offline use needs no network

        text = fetch_csv(symbol)
        return parse_csv_text(text), symbol.upper()
    raise ValueError("provide a symbol or a CSV path")


def _load_watchlist_item(item: str) -> Tuple[List[Bar], str]:
    """One watchlist entry: a CSV path if it looks/behaves like one, else a
    ticker fetched live."""
    if os.path.exists(item) or "/" in item or item.lower().endswith(".csv"):
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
            if isinstance(exc, (ValueError, OSError)) or \
                    exc.__class__.__name__ == "FetchError":
                rows.append(f'<tr><td>{_esc(item)}</td><td colspan="6" '
                            f'class="warn">{_esc(str(exc))}</td></tr>')
                continue
            raise

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

        if entry and stop:
            signals += 1
            per_share = bar.close - stop
            shares = (int(account * risk // per_share)
                      if per_share > 0 else 0)
            rows.append(
                f'<tr class="hit"><td>{_esc(label)}</td>'
                f"<td>{_esc(bar.date)}</td><td>{bar.close:,.2f}</td>"
                f'<td class="ok">YES</td>'
                f'<td class="ok">{_esc(signal.value.replace("enter_", "").upper())}</td>'
                f"<td>{stop:,.2f}</td><td>{shares} sh</td></tr>")
        else:
            note = ("no entry today" if uptrend
                    else "trend not confirmed — stay out")
            rows.append(
                f"<tr><td>{_esc(label)}</td>"
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
    title = "<h1>Trendrail <small>disciplined trend-following</small></h1>"
    if path == "/":
        return 200, _page("Trendrail", title + _form({}) + _watchlist_form({}))

    if path == "/watchlist":
        values = {k: _first(params, k) for k in ("symbols", "account", "risk")}
        header = title + _watchlist_form(values)
        try:
            account = float(values["account"] or DEFAULTS["account"])
            risk = float(values["risk"] or DEFAULTS["risk"])
        except ValueError:
            return 200, _page("Trendrail", header + '<div class="card warn">'
                              "Account and risk must be numbers.</div>")
        if not 0 < risk <= 0.1:
            return 200, _page("Trendrail", header + '<div class="card warn">'
                              "Risk per trade should be a small fraction, "
                              "e.g. 0.01-0.02.</div>")
        items = [s for s in re.split(r"[,\s]+", values["symbols"]) if s]
        if not items:
            return 200, _page("Trendrail", header + '<div class="card warn">'
                              "Add at least one ticker or CSV path.</div>")
        view = _watchlist_view(items, account, risk, StrategyConfig())
        return 200, _page("Trendrail", header + view)

    if path != "/run":
        return 404, _page("Not found", "<h1>404</h1><p>Nothing here.</p>")

    values = {k: _first(params, k) for k in
              ("symbol", "csv", "account", "risk", "fast_ma", "slow_ma",
               "breakout_lookback", "action")}
    header = ("<h1>Trendrail <small>disciplined trend-following</small></h1>"
              + _form(values))

    def fail(msg: str) -> Tuple[int, str]:
        return 200, _page(
            "Trendrail", header + f'<div class="card warn">{_esc(msg)}</div>')

    try:
        account = float(values["account"] or DEFAULTS["account"])
        risk = float(values["risk"] or DEFAULTS["risk"])
        cfg = StrategyConfig(
            fast_ma=int(values["fast_ma"] or DEFAULTS["fast_ma"]),
            slow_ma=int(values["slow_ma"] or DEFAULTS["slow_ma"]),
            breakout_lookback=int(values["breakout_lookback"]
                                  or DEFAULTS["breakout_lookback"]),
        )
    except ValueError:
        return fail("Account, risk, and MA settings must be numbers.")
    if not 0 < risk <= 0.1:
        return fail("Risk per trade should be a small fraction, e.g. 0.01-0.02.")

    try:
        bars, label = _load_bars(values["symbol"], values["csv"])
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
    return 200, _page("Trendrail", header + view)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        parsed = urlparse(self.path)
        status, body = route(parsed.path, parse_qs(parsed.query))
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
        prog="trendrail-web", description="Trendrail's local web dashboard.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind address (default 127.0.0.1 — local only)")
    parser.add_argument("--port", type=int, default=8181)
    args = parser.parse_args(argv)

    server = QuietServer((args.host, args.port), DashboardHandler)
    print(f"Trendrail dashboard: http://{args.host}:{args.port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
