"""Generate the ticker table for a "Trend Check" newsletter issue.

    python business/launch/trend_check.py AAPL MSFT NVDA GOOGL AMZN
    python business/launch/trend_check.py --default   # the standard 20

Fetches daily history for each ticker and prints a markdown table of the
engine's verdict — paste it straight into the newsletter. Needs a network
connection. Uses your Alpaca data feed when APCA_API_KEY_ID /
APCA_API_SECRET_KEY are set (the free providers often refuse requests
from cloud servers, e.g. GitHub Actions); otherwise falls back to the
free providers.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

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


def verdict(symbol: str, strat: TrendFollowingStrategy) -> str:
    try:
        bars, _ = _fetch_symbol(symbol)
    except (FetchError, ValueError, OSError) as exc:
        return f"| {symbol} | – | data unavailable ({exc}) |"
    if len(bars) < strat.config.slow_ma + 1:
        return f"| {symbol} | – | not enough history |"

    # Descriptive states only — the newsletter reports what the ruleset's
    # conditions show on public data; it never tells anyone to act
    # (LEGAL.md §2: descriptive, never imperative, in broadcast copy).
    i = len(bars) - 1
    close = bars[i].close
    if strat.entry_signal(bars, i) in (Signal.ENTER_PULLBACK,
                                       Signal.ENTER_BREAKOUT):
        state = "**uptrend confirmed — the ruleset's entry conditions are met**"
    elif strat.is_uptrend(bars, i):
        state = "uptrend confirmed — no entry condition met today"
    elif strat.exit_on_trend_break(bars, i):
        state = ("trend filter no longer met — close below the 50-day "
                 "average or a lower low")
    else:
        state = "no confirmed uptrend"
    return f"| {symbol} | {close:,.2f} | {state} |"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="tickers to check")
    parser.add_argument("--default", action="store_true",
                        help="use the standard 20-ticker list")
    args = parser.parse_args(argv)

    tickers = DEFAULT_TICKERS if args.default or not args.tickers \
        else [t.upper() for t in args.tickers]
    strat = TrendFollowingStrategy(StrategyConfig())

    print("| Ticker | Close | The rules say |")
    print("|---|---|---|")
    for symbol in tickers:
        print(verdict(symbol, strat))
    print("\n*As of the latest daily close. This is the mechanical output of "
          "a published ruleset applied to public data — not investment "
          "advice, and not a prediction.*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
