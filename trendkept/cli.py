"""Command line interface for Trendkept.

    # From a CSV you already have
    python -m trendkept.cli backtest examples/sample_uptrend.csv --account 1000
    python -m trendkept.cli scan  examples/aapl_2015_2017.csv --account 1000

    # Straight from a ticker (fetches live data; needs network)
    python -m trendkept.cli backtest --symbol AAPL --account 1000 --risk 0.02 -v
    python -m trendkept.cli scan     --symbol MSFT --account 1000
    python -m trendkept.cli fetch    AAPL --out data/aapl.csv

``backtest`` simulates the full ruleset over a price history and reports the
stats that matter for a trend-follower. ``scan`` looks only at the most recent
bar and tells you what the rules say to do *today* — the paper-trading helper.
``fetch`` downloads daily history to a CSV.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from .data import Bar, load_csv, parse_csv_text
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


def _load_bars(args: argparse.Namespace) -> tuple[List[Bar], str]:
    """Resolve the data source: a CSV path or a live ``--symbol`` fetch.

    Returns the bars and a human label for reporting.
    """
    if getattr(args, "symbol", None):
        if args.provider == "alpaca":
            from .alpaca import AlpacaClient  # lazy: only needs keys when used

            client = AlpacaClient(paper=not getattr(args, "live", False),
                                  feed=getattr(args, "feed", "iex"))
            bars = client.daily_bars(args.symbol)
            return bars, f"{args.symbol.upper()} (alpaca {client.feed})"

        from .fetch import fetch_csv  # imported lazily so offline use needs no net

        text = fetch_csv(args.symbol, provider=args.provider, range_=args.range)
        return parse_csv_text(text), f"{args.symbol.upper()} ({args.provider})"
    if args.csv:
        return load_csv(args.csv), args.csv
    raise SystemExit("error: provide a CSV path or --symbol TICKER")


def _load_bars_or_exit(args: argparse.Namespace) -> tuple[List[Bar], str]:
    """Load bars, turning any data/network error into a clean message."""
    try:
        return _load_bars(args)
    except FileNotFoundError as exc:
        raise SystemExit(f"error: file not found: {exc.filename}")
    except (ValueError, OSError) as exc:
        raise SystemExit(f"error: {exc}")
    except Exception as exc:  # AlpacaError / FetchError live in lazy imports
        if exc.__class__.__name__ in ("AlpacaError", "FetchError"):
            raise SystemExit(f"error: {exc}")
        raise


def _cmd_backtest(args: argparse.Namespace) -> int:
    bars, label = _load_bars_or_exit(args)
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

    print(f"Source           : {label}")
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
    bars, label = _load_bars_or_exit(args)
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

    print(f"{label}  as of {bar.date}  close={bar.close:.2f}")
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


def _cmd_fetch(args: argparse.Namespace) -> int:
    from .fetch import fetch_csv, FetchError

    try:
        text = fetch_csv(args.symbol, provider=args.provider, range_=args.range)
    except FetchError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    bars = parse_csv_text(text)
    if args.out:
        with open(args.out, "w", newline="") as handle:
            handle.write(text)
        print(f"Saved {len(bars)} bars for {args.symbol.upper()} "
              f"({bars[0].date} -> {bars[-1].date}) to {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def _cmd_account(args: argparse.Namespace) -> int:
    from .alpaca import AlpacaClient, AlpacaError

    try:
        client = AlpacaClient(paper=not args.live, feed="iex")
        acct = client.account()
        positions = client.positions()
    except AlpacaError as exc:
        print(f"Alpaca error: {exc}", file=sys.stderr)
        return 1

    mode = "LIVE" if args.live else "paper"
    print(f"Alpaca account ({mode})")
    print(f"  status        : {acct.get('status')}")
    print(f"  equity        : {float(acct.get('equity', 0)):,.2f} "
          f"{acct.get('currency', '')}")
    print(f"  cash          : {float(acct.get('cash', 0)):,.2f}")
    print(f"  buying power   : {float(acct.get('buying_power', 0)):,.2f}")
    print(f"  open positions : {len(positions)}")
    for p in positions:
        print(f"    {p.get('symbol'):<6} {p.get('qty')} @ "
              f"{float(p.get('avg_entry_price', 0)):.2f}  "
              f"P/L {float(p.get('unrealized_pl', 0)):+.2f}")
    return 0


def _cmd_trade(args: argparse.Namespace) -> int:
    from .alpaca import AlpacaClient, AlpacaError, plan_trade

    try:
        client = AlpacaClient(paper=not args.live, feed=args.feed)
        bars = client.daily_bars(args.symbol)
    except AlpacaError as exc:
        print(f"Alpaca error: {exc}", file=sys.stderr)
        return 1

    if len(bars) < args.slow_ma + 1:
        print(f"Need at least {args.slow_ma + 1} bars; got {len(bars)}.",
              file=sys.stderr)
        return 1

    strat = _build_strategy(args)
    i = len(bars) - 1
    mode = "LIVE" if args.live else "paper"
    print(f"{args.symbol.upper()} (alpaca {mode})  as of {bars[i].date}  "
          f"close={bars[i].close:.2f}")
    print(f"Confirmed uptrend: {'YES' if strat.is_uptrend(bars, i) else 'no'}")

    if client.get_position(args.symbol):
        print("Already holding a position in this symbol; managing existing "
              "trades is out of scope for this command. No order placed.")
        return 0

    try:
        plan = plan_trade(client, strat, args.symbol, bars, args.risk)
    except AlpacaError as exc:
        print(f"Alpaca error: {exc}", file=sys.stderr)
        return 1

    if plan is None:
        print("SIGNAL: no entry today (wait for a pullback or breakout). "
              "Nothing to do.")
        return 0

    print("SIGNAL: " + plan.describe())

    if not args.confirm:
        print("\nDRY RUN — no order sent. Re-run with --confirm to submit "
              f"this order to your {mode} account.")
        return 0

    if args.live and not args.i_understand_live:
        print("\nRefusing to place a LIVE order without --i-understand-live. "
              "This risks real money.", file=sys.stderr)
        return 1

    limit = plan.entry_price * (1 + args.limit_slippage)
    order = client.submit_entry_with_stop(
        plan.symbol, plan.quantity, plan.stop_price, limit_price=limit
    )
    print(f"\nOrder submitted to {mode}: id={order.get('id')} "
          f"status={order.get('status')} "
          f"(buy {plan.quantity} {plan.symbol}, stop {plan.stop_price:.2f})")
    return 0


def _manage_one(client, strat, position: dict, args) -> None:
    from .alpaca import AlpacaError, decide_management

    symbol = position.get("symbol", "")
    qty = position.get("qty", "?")
    try:
        bars = client.daily_bars(symbol)
    except AlpacaError as exc:
        print(f"  {symbol}: could not load bars: {exc}")
        return

    stop_order = client.find_stop_order(symbol)
    current_stop = (float(stop_order["stop_price"])
                    if stop_order and stop_order.get("stop_price") else None)

    action = decide_management(strat, bars, current_stop, symbol=symbol)
    print(f"  {symbol} ({qty} sh, last {bars[-1].close:.2f}): {action.describe()}")

    if not args.confirm or action.kind == "hold":
        return

    try:
        if action.kind == "exit":
            if stop_order:
                client.cancel_order(stop_order["id"])
            client.close_position(symbol)
            print(f"    -> position closed at market; stop order cancelled.")
        elif action.kind == "raise_stop" and stop_order:
            client.replace_order(stop_order["id"], action.new_stop)
            print(f"    -> stop raised to {action.new_stop:.2f}.")
        elif action.kind in ("set_stop", "raise_stop"):
            # No existing stop order to amend: place a fresh protective
            # sell-stop.
            client.submit_stop_sell(symbol, qty, action.new_stop)
            print(f"    -> protective stop placed at {action.new_stop:.2f}.")
    except AlpacaError as exc:
        # One symbol failing must not crash the whole management pass; the
        # existing stop order stays in force either way.
        print(f"    -> broker refused the change ({exc}); the current stop "
              "is still in place. Re-run manage tomorrow or raise it by "
              "hand in the Alpaca dashboard.")


def _cmd_manage(args: argparse.Namespace) -> int:
    from .alpaca import AlpacaClient, AlpacaError

    try:
        client = AlpacaClient(paper=not args.live, feed=args.feed)
        if args.symbol:
            pos = client.get_position(args.symbol)
            positions = [pos] if pos else []
        else:
            positions = client.positions()
    except AlpacaError as exc:
        print(f"Alpaca error: {exc}", file=sys.stderr)
        return 1

    mode = "LIVE" if args.live else "paper"
    if not positions:
        print(f"No open positions on the {mode} account. Nothing to manage.")
        return 0

    if args.live and args.confirm and not args.i_understand_live:
        print("Refusing to manage LIVE positions without --i-understand-live.",
              file=sys.stderr)
        return 1

    strat = _build_strategy(args)
    print(f"Managing {len(positions)} position(s) on {mode}"
          + ("" if args.confirm else "  [DRY RUN — re-run with --confirm to act]"))
    for pos in positions:
        _manage_one(client, strat, pos, args)
    return 0


def _cmd_journal(args: argparse.Namespace) -> int:
    from .alpaca import AlpacaClient, AlpacaError
    from .journal import (attach_stops, journal_stats, normalize_fill,
                          pair_fills)

    try:
        client = AlpacaClient(paper=not args.live)
        fills = [f for f in map(normalize_fill, client.fills()) if f]
        stops = client.stop_order_history()
    except AlpacaError as exc:
        print(f"Alpaca error: {exc}", file=sys.stderr)
        return 1

    trips, open_lots = pair_fills(fills)
    attach_stops(trips, open_lots, stops)

    mode = "LIVE" if args.live else "paper"
    if not trips and not open_lots:
        print(f"No fills on the {mode} account yet. The journal starts "
              "with your first trade.")
        return 0

    if trips:
        print(f"Completed trades ({mode}):")
        print("  entry date  symbol   qty     entry      exit       P/L"
              "        R")
        for t in trips:
            r = f"{t.r_multiple:+.2f}R" if t.r_multiple is not None else "  —  "
            print(f"  {t.entry_at[:10]}  {t.symbol:<6} {t.qty:>5.0f} "
                  f"{t.entry_price:>9.2f} {t.exit_price:>9.2f} "
                  f"{t.pnl:>+9.2f}  {r:>7}")
    if open_lots:
        print("Open positions:")
        for lot in open_lots:
            stop = (f"stop {lot.planned_stop:.2f}"
                    if lot.planned_stop is not None else "stop unknown")
            print(f"  {lot.entry_at[:10]}  {lot.symbol:<6} {lot.qty:>5.0f} "
                  f"@ {lot.entry_price:.2f}  ({stop})")

    s = journal_stats(trips)
    if s["trades"]:
        win = f"{s['win_rate'] * 100:.0f}%" if s["win_rate"] is not None else "—"
        avg = f"{s['avg_r']:+.2f}R" if s["avg_r"] is not None else "—"
        print(f"\nScoreboard: {s['trades']} trades, {win} winners, "
              f"total {s['total_pnl']:+.2f}, average {avg} "
              f"({s['scored']}/{s['trades']} scored against a known stop).")
        print("Expectancy in R is the number that matters — win rate is "
              "a vanity metric.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trendkept",
        description="Disciplined trend-following: fetch, backtest, and scan.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_source(p: argparse.ArgumentParser) -> None:
        p.add_argument("csv", nargs="?", default=None,
                       help="CSV file with date,open,high,low,close (or use --symbol)")
        p.add_argument("--symbol", help="ticker to fetch live instead of a CSV")
        p.add_argument("--provider", default="auto",
                       choices=["auto", "stooq", "yahoo", "alpaca"],
                       help="data provider for --symbol (default auto)")
        p.add_argument("--range", default="5y", dest="range",
                       help="history range for Yahoo fetches (default 5y)")
        p.add_argument("--feed", default="iex",
                       help="Alpaca data feed: iex (free) or sip (default iex)")

    for name, func in (("backtest", _cmd_backtest), ("scan", _cmd_scan)):
        p = sub.add_parser(name)
        add_source(p)
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

    fp = sub.add_parser("fetch")
    fp.add_argument("symbol", help="ticker to download, e.g. AAPL")
    fp.add_argument("--provider", default="auto",
                    choices=["auto", "stooq", "yahoo"])
    fp.add_argument("--range", default="5y", dest="range")
    fp.add_argument("--out", help="write CSV here (default: stdout)")
    fp.set_defaults(func=_cmd_fetch)

    # Alpaca account summary.
    ap = sub.add_parser("account", help="show Alpaca account & positions")
    ap.add_argument("--live", action="store_true",
                    help="use the LIVE account instead of paper")
    ap.set_defaults(func=_cmd_account)

    # Alpaca order placement (paper + dry-run by default).
    tp = sub.add_parser("trade",
                        help="scan a symbol on Alpaca and place a stop-protected "
                             "entry order")
    tp.add_argument("symbol", help="ticker to trade, e.g. AAPL")
    tp.add_argument("--risk", type=float, default=0.01,
                    help="fraction of account risked per trade (default 0.01)")
    tp.add_argument("--feed", default="iex", help="Alpaca data feed (default iex)")
    tp.add_argument("--fast-ma", type=int, default=50, dest="fast_ma")
    tp.add_argument("--slow-ma", type=int, default=200, dest="slow_ma")
    tp.add_argument("--breakout-lookback", type=int, default=20,
                    dest="breakout_lookback")
    tp.add_argument("--limit-slippage", type=float, default=0.005,
                    dest="limit_slippage",
                    help="limit price headroom above close (default 0.5%%)")
    tp.add_argument("--confirm", action="store_true",
                    help="actually submit the order (otherwise dry run)")
    tp.add_argument("--live", action="store_true",
                    help="trade the LIVE account instead of paper")
    tp.add_argument("--i-understand-live", action="store_true",
                    dest="i_understand_live",
                    help="required acknowledgement to place LIVE orders")
    tp.set_defaults(func=_cmd_trade)

    # Manage open Alpaca positions: trail stops up, exit on trend break.
    mp = sub.add_parser("manage",
                        help="trail stops and exit broken trends on open "
                             "Alpaca positions")
    mp.add_argument("symbol", nargs="?", default=None,
                    help="manage just this symbol (default: all positions)")
    mp.add_argument("--feed", default="iex", help="Alpaca data feed (default iex)")
    mp.add_argument("--fast-ma", type=int, default=50, dest="fast_ma")
    mp.add_argument("--slow-ma", type=int, default=200, dest="slow_ma")
    mp.add_argument("--breakout-lookback", type=int, default=20,
                    dest="breakout_lookback")
    mp.add_argument("--confirm", action="store_true",
                    help="actually amend/cancel/close orders (otherwise dry run)")
    mp.add_argument("--live", action="store_true",
                    help="manage the LIVE account instead of paper")
    mp.add_argument("--i-understand-live", action="store_true",
                    dest="i_understand_live",
                    help="required acknowledgement to act on LIVE positions")
    mp.set_defaults(func=_cmd_manage)

    jp = sub.add_parser("journal",
                        help="score completed paper trades in R-multiples "
                             "from the broker's fill history")
    jp.add_argument("--live", action="store_true",
                    help="read the LIVE account instead of paper")
    jp.set_defaults(func=_cmd_journal)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
