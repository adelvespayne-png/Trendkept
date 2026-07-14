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
    if strat.entry_signal(bars, i) in (Signal.ENTER_PULLBACK,
                                       Signal.ENTER_BREAKOUT):
        state, key = ("**uptrend confirmed — the ruleset's entry conditions "
                      "are met**"), ENTRY
    elif strat.is_uptrend(bars, i):
        state, key = "uptrend confirmed — no entry condition met today", UPTREND
    elif strat.exit_on_trend_break(bars, i):
        state, key = ("trend filter no longer met — close below the 50-day "
                      "average or a lower low"), BREAK
    else:
        state, key = "no confirmed uptrend", NONE
    return f"| {symbol} | {close:,.2f} | {state} |", key


def summarize(keys: List[str]) -> str:
    """One plain-English sentence describing the board, from state keys."""
    total = len(keys)
    up = keys.count(UPTREND) + keys.count(ENTRY)
    parts = [f"{up} of {total} in a confirmed uptrend"]
    if keys.count(ENTRY):
        parts[0] += (f" ({keys.count(ENTRY)} meeting the ruleset's entry "
                     "conditions)")
    if keys.count(BREAK):
        parts.append(f"{keys.count(BREAK)} where the trend filter is no "
                     "longer met")
    if keys.count(NONE):
        parts.append(f"{keys.count(NONE)} with no confirmed uptrend")
    if keys.count(ERROR):
        parts.append(f"{keys.count(ERROR)} unavailable (data error)")
    return "This week's board: " + "; ".join(parts) + "."


TABLE_HEADER = "| Ticker | Close | The rules say |\n|---|---|---|"

TABLE_FOOTNOTE = (
    "*As of the latest daily close. This is the mechanical output of "
    "a published ruleset applied to public data — not investment "
    "advice, and not a prediction.*")

STATES_LEGEND = """\
A quick reminder of what the states mean (they describe the data — what you
do with your own account is always your decision):

- **Uptrend confirmed** — price above the 50- and 200-day averages, averages
  aligned, structure making higher highs and lows. The ruleset only defines
  entries here, and only on a pullback or breakout that isn't over-extended.
- **No confirmed uptrend** — the ruleset's conditions aren't met, so it
  defines no action. In a mechanical system, "no action" is the most common
  state — that's a feature, not a gap.
- **Trend filter no longer met** — a close below the 50-day average or a
  lower low. This is the condition the ruleset treats as a trend break."""

FOOTER = """\
— [YOUR NAME]

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
        "Every Sunday, this email does one boring, useful thing: it runs a "
        "written trend-following ruleset over ~20 liquid tickers and "
        "reports what the rules say — uptrend confirmed, no entry, or "
        "trend broken. No predictions. No hot takes. The ruleset is public "
        "and the code that produces this table is open source.",
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
