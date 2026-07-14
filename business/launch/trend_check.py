"""Generate the ticker table — or a full paste-ready draft — for a
"Trend Check" newsletter issue.

    python business/launch/trend_check.py AAPL MSFT NVDA GOOGL AMZN
    python business/launch/trend_check.py --default   # the standard 20
    python business/launch/trend_check.py --default --draft   # whole issue

Fetches daily history for each ticker and prints a markdown table of the
engine's verdict — paste it straight into the newsletter. Needs a network
connection. Uses your Alpaca data feed when APCA_API_KEY_ID /
APCA_API_SECRET_KEY are set (the free providers often refuse requests
from cloud servers, e.g. GitHub Actions); otherwise falls back to the
free providers.

Every state is descriptive, never imperative (LEGAL.md §2): the email
reports what a published ruleset shows on public data; it never tells
anyone to act.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", ".."))

from trendkept.fetch import FetchError               # noqa: E402
from trendkept.strategy import (                     # noqa: E402
    Signal, StrategyConfig, TrendFollowingStrategy)
from trendkept.web import _fetch_symbol              # noqa: E402

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "JPM", "V", "UNH", "XOM", "COST", "PG", "HD", "NFLX", "AMD",
    "SPY", "QQQ", "IWM",
]

# State keys returned alongside each table row, for the summary line.
ENTRY, UPTREND, BREAK, NONE, ERROR = (
    "entry", "uptrend", "break", "none", "error")


def verdict(symbol: str, strat: TrendFollowingStrategy) -> Tuple[str, str]:
    """One table row plus a state key for the weekly summary."""
    try:
        bars, _ = _fetch_symbol(symbol)
    except (FetchError, ValueError, OSError) as exc:
        return f"| {symbol} | – | data unavailable ({exc}) |", ERROR
    if len(bars) < strat.config.slow_ma + 1:
        return f"| {symbol} | – | not enough history |", ERROR

    # Descriptive states only — the newsletter reports what the ruleset's
    # conditions show on public data; it never tells anyone to act
    # (LEGAL.md §2: descriptive, never imperative, in broadcast copy).
    i = len(bars) - 1
    close = bars[i].close
    # Short states keep the table calm and readable; the legend below the
    # table carries the precise definitions once, instead of every row
    # repeating them. Wording stays descriptive, never imperative
    # (LEGAL.md §2).
    if strat.entry_signal(bars, i) in (Signal.ENTER_PULLBACK,
                                       Signal.ENTER_BREAKOUT):
        state, key = "**in an uptrend — entry conditions met**", ENTRY
    elif strat.is_uptrend(bars, i):
        state, key = "in an uptrend — no entry today", UPTREND
    elif strat.exit_on_trend_break(bars, i):
        state, key = "trend broken", BREAK
    else:
        state, key = "nothing confirmed", NONE
    return f"| {symbol} | {close:,.2f} | {state} |", key


def summarize(keys: List[str]) -> str:
    """One friendly plain-English sentence describing the board."""
    total = len(keys)
    up = keys.count(UPTREND) + keys.count(ENTRY)
    first = f"{up} of the {total} are in a confirmed uptrend"
    if keys.count(ENTRY):
        first += f" ({keys.count(ENTRY)} meeting the entry conditions)"
    parts = [first]
    if keys.count(BREAK):
        parts.append(f"{keys.count(BREAK)} have broken their trend")
    if keys.count(NONE):
        parts.append(f"{keys.count(NONE)} show nothing confirmed either way")
    if keys.count(ERROR):
        parts.append(f"{keys.count(ERROR)} couldn't be checked (data error)")
    if len(parts) > 1:
        body = ", ".join(parts[:-1]) + " and " + parts[-1]
    else:
        body = parts[0]
    return "The short version: " + body + "."


TABLE_HEADER = "| Ticker | Close | The rules say |\n|---|---|---|"

TABLE_FOOTNOTE = (
    "*As of the latest daily close. This is the mechanical output of "
    "a published ruleset applied to public data — not investment "
    "advice, and not a prediction.*")

STATES_LEGEND = """\
What the states mean, in plain English (they describe the data — what you do
with your own account is always your decision):

- **In an uptrend** — price above its 50- and 200-day averages, the averages
  aligned, and the chart making higher highs and lows. The ruleset only
  defines entries here, and only on a pullback or breakout that isn't
  over-extended.
- **Nothing confirmed** — the conditions aren't met, so the ruleset defines
  no action. Most weeks, most tickers sit here. That's not the system being
  lazy — it's the discipline doing its job.
- **Trend broken** — a close below the 50-day average, or a lower low. This
  is the condition the ruleset treats as the end of an uptrend."""

FOOTER = """\
That's it for this week — same time next Sunday.

— [YOUR NAME]

The ruleset, the code, and the free dashboard live at
[trendkept.com](https://trendkept.com).

*Trendkept is analysis software and education, not investment advice. This
table is the mechanical output of a published ruleset on public data. Trading
involves risk of loss; past and backtested performance do not predict future
results. Unsubscribe below — no hard feelings.*"""


def build_draft(rows: List[str], keys: List[str], issue_no: str = "[N]") -> str:
    """The whole issue, paste-ready except the bracketed spots."""
    table = "\n".join([TABLE_HEADER, *rows])
    return "\n".join([
        f"Subject: **The Trend Check #{issue_no} — what the rules say "
        "this week**",
        "",
        "---",
        "",
        "Hi — thanks for reading The Trend Check.",
        "",
        "Every Sunday this email does one small, honest job: a written "
        "trend-following ruleset runs over 20 well-known tickers, and I "
        "report what it says — in an uptrend, nothing confirmed, or trend "
        "broken. No predictions, no hot takes. The ruleset is public and "
        "the code behind this table is open source.",
        "",
        summarize(keys),
        "",
        "## This week's board",
        "",
        table,
        "",
        TABLE_FOOTNOTE,
        "",
        STATES_LEGEND,
        "",
        "## One honest lesson: [THIS WEEK'S LESSON — skeletons in "
        "business/launch/trend_check_001.md]",
        "",
        "[Two or three short paragraphs. Week 1: R-multiples. Week 2: the "
        "stop goes in with the order. Week 3: position sizing has no "
        "conviction knob. Week 4: doing nothing is a position.]",
        "",
        FOOTER,
    ])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="tickers to check")
    parser.add_argument("--default", action="store_true",
                        help="use the standard 20-ticker list")
    parser.add_argument("--draft", action="store_true",
                        help="print the whole paste-ready issue, not just "
                             "the table")
    parser.add_argument("--issue", default="[N]",
                        help="issue number for the subject line")
    args = parser.parse_args(argv)

    tickers = DEFAULT_TICKERS if args.default or not args.tickers \
        else [t.upper() for t in args.tickers]
    strat = TrendFollowingStrategy(StrategyConfig())

    rows, keys = [], []
    for symbol in tickers:
        row, key = verdict(symbol, strat)
        rows.append(row)
        keys.append(key)

    if args.draft:
        print(build_draft(rows, keys, issue_no=args.issue))
    else:
        print(TABLE_HEADER)
        for row in rows:
            print(row)
        print("\n" + TABLE_FOOTNOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
