"""Command line interface for Archie.

    python -m archie.cli backtest examples/sample_uptrend.csv --account 1000
    python -m archie.cli scan examples/sample_uptrend.csv --account 1000

``backtest`` simulates the full ruleset over a price history and reports the
stats that matter for a trend-follower. ``scan`` looks only at the most recent
bar and tells you what the rules say to do *today* — the paper-trading helper.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from .data import Bar, load_csv
from .strategy import Signal, StrategyConfig, TrendFollowingStrategy
from .backtest import Backtester


def _build_strategy(args: argparse.Namespace) -> TrendFollowingStrategy:
    return TrendFollowingStrategy(
        StrategyConfig(
            fast_ma=args.fast_ma,
            slow_ma=args.slow_ma,
            breakout_lookback=args.breakout_lookback,
        )
    )


def _cmd_backtest(args: argparse.Namespace) -> int:
    bars = load_csv(args.csv)
    if len(bars) < args.slow_ma + 1:
        print(
            f"Need at least {args.slow_ma + 1} bars to confirm a "
            f"{args.slow_ma}-day trend; got {len(bars)}.",
            file=sys.stderr,
        )
        return 1

    bt = Backtester(
        strategy=_build_strategy(args),
        starting_equity=args.account,
        risk_pct=args.risk,
    )
    result = bt.run(bars)

    print(f"Symbol/file      : {args.csv}")
    print(f"Bars             : {len(bars)} ({bars[0].date} -> {bars[-1].date})")
    print(f"Starting equity  : {result.starting_equity:,.2f}")
    print(f"Ending equity    : {result.ending_equity:,.2f}")
    print(f"Total return     : {result.total_return_pct:+.2f}%")
    print(f"Max drawdown     : {result.max_drawdown_pct:.2f}%")
    print(f"Closed trades    : {len(result.closed_trades)}")
    print(f"Win rate         : {result.win_rate:.1f}%")
    print(f"Expectancy       : {result.expectancy_r:+.2f}R per trade")
    pf = result.profit_factor
    print(f"Profit factor    : {'inf' if pf == float('inf') else f'{pf:.2f}'}")

    if args.verbose and result.trades:
        print("\nTrades:")
        print(
            f"  {'entry':<12}{'exit':<12}{'shares':>8}"
            f"{'entry$':>10}{'exit$':>10}{'R':>8}  reason/exit"
        )
        for t in result.trades:
            exit_date = t.exit_date or "(open)"
            exit_price = f"{t.exit_price:.2f}" if t.exit_price is not None else "-"
            print(
                f"  {t.entry_date:<12}{exit_date:<12}{t.shares:>8.4g}"
                f"{t.entry_price:>10.2f}{exit_price:>10}"
                f"{t.r_multiple:>8.2f}  {t.reason}/{t.exit_reason or '-'}"
            )
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    bars: List[Bar] = load_csv(args.csv)
    if len(bars) < args.slow_ma + 1:
        print(
            f"Need at least {args.slow_ma + 1} bars; got {len(bars)}.",
            file=sys.stderr,
        )
        return 1

    strat = _build_strategy(args)
    i = len(bars) - 1
    bar = bars[i]

    uptrend = strat.is_uptrend(bars, i)
    signal = strat.entry_signal(bars, i)
    stop = strat.initial_stop(bars, i)

    print(f"As of {bar.date}  close={bar.close:.2f}")
    print(f"Confirmed uptrend: {'YES' if uptrend else 'no'}")

    if signal in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT) and stop:
        risk_amount = args.account * args.risk
        per_share = bar.close - stop
        shares = int(risk_amount // per_share) if per_share > 0 else 0
        print(f"SIGNAL           : {signal.value.upper()}")
        print(f"Suggested entry  : {bar.close:.2f}")
        print(f"Initial stop     : {stop:.2f}  (risk {per_share:.2f}/share)")
        print(
            f"Position size    : {shares} shares "
            f"(risking {risk_amount:,.2f} = {args.risk * 100:.1f}% of "
            f"{args.account:,.2f})"
        )
        if shares == 0:
            print("  -> stop is too wide for this account at this risk %; skip.")
    else:
        print("SIGNAL           : no entry (wait for a pullback or breakout)")
        if not uptrend:
            print("  -> trend not confirmed; stay out.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archie",
        description="Disciplined trend-following: backtest and scan.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func in (("backtest", _cmd_backtest), ("scan", _cmd_scan)):
        p = sub.add_parser(name)
        p.add_argument("csv", help="CSV file with date,open,high,low,close")
        p.add_argument("--account", type=float, default=1000.0,
                       help="account size (default 1000)")
        p.add_argument("--risk", type=float, default=0.01,
                       help="fraction of account risked per trade (default 0.01)")
        p.add_argument("--fast-ma", type=int, default=50, dest="fast_ma")
        p.add_argument("--slow-ma", type=int, default=200, dest="slow_ma")
        p.add_argument("--breakout-lookback", type=int, default=20,
                       dest="breakout_lookback")
        if name == "backtest":
            p.add_argument("-v", "--verbose", action="store_true",
                           help="list every trade")
        p.set_defaults(func=func)
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
