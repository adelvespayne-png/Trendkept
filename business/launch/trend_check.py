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

from trendkept.cli import STANDARD_TICKERS  # noqa: E402

DEFAULT_TICKERS = STANDARD_TICKERS  # one board: newsletter == autopilot

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

# The first month's lessons, written in advance so the Sunday draft needs
# no writing at all. From issue 5 the lesson comes from the week's real
# paper-log experience — drafted in a Claude session, reviewed by the owner.
LESSONS = {
    1: ("R-multiples", """\
The only score that matters in this system is the R-multiple: profit
measured in units of what you risked. Risk £10 on a trade (that's entry
minus stop, times shares) and make £30 — that's +3R. Get stopped — that's
−1R.

Here's the maths that surprises everyone: at +3R average winners, you can be
wrong 60% of the time and still grow the account. Win rate is a vanity
metric; R-expectancy is the business model. Next week: why the stop goes in
*with* the order, not after."""),
    2: ("the stop goes in with the order", """\
When this system buys, the protective stop is part of the same order — the
broker holds both from second one. There is never a moment where a position
exists and its exit doesn't.

Why so strict? Because "I'll put the stop in if it drops a bit" is not a
risk plan, it's a mood. The version of you that placed the trade is calm and
rational; the version watching it fall is neither. Sending them both to the
broker together means the calm one decides. Willpower is not a
risk-management system — order types are. Next week: position sizing."""),
    3: ("position sizing has no conviction knob", """\
Shares = (account × risk%) ÷ (entry − stop). That's the whole formula, and
notice what's missing: how much you *like* the trade.

Two worked examples at 1% of a £10,000 account (£100 of risk). Tight stop:
entry 50, stop 48 → £2 a share → 50 shares. Wide stop: entry 50, stop 42 →
£8 a share → 12 shares. The scarier trade automatically gets smaller. No
gut feel, no doubling down on favourites — the distance to the stop sets
the size, every time. Next week: why doing nothing is a position."""),
    4: ("doing nothing is a position", """\
Count the "nothing confirmed" rows across the last four boards and you'll
notice the system's loudest opinion is silence. Most tickers, most weeks,
meet no condition — so the rules define no action, and no action is taken.

That's not the system being lazy; it's the edge. Every forced trade in a
sideways chop is paid for in stops and fees. A ruleset that mostly says
"not today" is doing the hardest job in trading: keeping you out of the
trades you'd have talked yourself into."""),
}

FOOTER = """\
That's it for this week — same time next Sunday.

— Archie

The ruleset, the code, and the free dashboard live at
[trendkept.com](https://trendkept.com).

*Trendkept is analysis software and education, not investment advice. This
table is the mechanical output of a published ruleset on public data. Trading
involves risk of loss; past and backtested performance do not predict future
results. Unsubscribe below — no hard feelings.*"""


def next_issue_number(today=None) -> int:
    """Issue #1 sends Sunday 2026-07-19; one a week after that."""
    import datetime

    today = today or datetime.date.today()
    days = (today - datetime.date(2026, 7, 19)).days
    return max(1, days // 7 + 1 + (1 if days % 7 else 0)) if days > 0 \
        else 1


def build_draft(rows: List[str], keys: List[str], issue_no: str = "[N]") -> str:
    """The whole issue, paste-ready; brackets remain only when no
    pre-written lesson exists for this issue number."""
    table = "\n".join([TABLE_HEADER, *rows])
    try:
        title, body = LESSONS[int(issue_no)]
    except (KeyError, ValueError):
        title = ("[THIS WEEK'S LESSON — draft it from the week's paper log "
                 "in a Claude session]")
        body = ("[Two or three short paragraphs, written fresh from what "
                "the log actually showed this week.]")
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
        f"## One honest lesson: {title}",
        "",
        body,
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
    parser.add_argument("--issue", default="auto",
                        help="issue number for the subject line; 'auto' "
                             "computes it from the calendar")
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
        issue = str(next_issue_number()) if args.issue == "auto" \
            else args.issue
        print(build_draft(rows, keys, issue_no=issue))
    else:
        print(TABLE_HEADER)
        for row in rows:
            print(row)
        print("\n" + TABLE_FOOTNOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
