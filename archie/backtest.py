"""Bar-by-bar backtester with risk-based position sizing and trailing stops.

The simulator is deliberately conservative about *when* it acts so results are
honest:

* Signals are computed on a bar's close (causal — no peeking ahead).
* Entries fill at that close. Real fills slip; treat backtest equity as an
  optimistic ceiling, not a promise.
* Each subsequent bar, the stop is checked against the bar's *low* before any
  exit signal. If the low pierces the stop, the trade exits at the stop price
  (a gap-down below the stop fills at the open — modelled here as the worse of
  stop and open).

Risk is the heart of it: every position is sized so that being stopped out
costs no more than ``risk_pct`` of current equity. That is the rule that makes
"wrong 60% of the time, still profitable" possible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from .data import Bar
from .strategy import Signal, StrategyConfig, TrendFollowingStrategy


@dataclass
class Trade:
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    reason: str
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    highest_stop: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.exit_price is None

    @property
    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def risk_per_share(self) -> float:
        return self.entry_price - self.initial_stop

    @property
    def r_multiple(self) -> float:
        """Profit measured in units of initial risk (the only score that
        matters for a cut-losers-let-winners-run system)."""
        risk = self.risk_per_share * self.shares
        if risk <= 0:
            return 0.0
        return self.pnl / risk


@dataclass
class BacktestResult:
    starting_equity: float
    ending_equity: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    @property
    def closed_trades(self) -> List[Trade]:
        return [t for t in self.trades if not t.is_open]

    @property
    def total_return_pct(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return (self.ending_equity / self.starting_equity - 1.0) * 100.0

    @property
    def win_rate(self) -> float:
        closed = self.closed_trades
        if not closed:
            return 0.0
        wins = sum(1 for t in closed if t.pnl > 0)
        return wins / len(closed) * 100.0

    @property
    def expectancy_r(self) -> float:
        """Average R per closed trade — expected reward per unit risked."""
        closed = self.closed_trades
        if not closed:
            return 0.0
        return sum(t.r_multiple for t in closed) / len(closed)

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl for t in self.closed_trades if t.pnl > 0)
        gross_loss = -sum(t.pnl for t in self.closed_trades if t.pnl < 0)
        if gross_loss == 0:
            return float("inf") if gross_win > 0 else 0.0
        return gross_win / gross_loss

    @property
    def max_drawdown_pct(self) -> float:
        peak = -math.inf
        worst = 0.0
        for v in self.equity_curve:
            peak = max(peak, v)
            if peak > 0:
                worst = min(worst, (v - peak) / peak)
        return worst * 100.0


class Backtester:
    def __init__(
        self,
        strategy: Optional[TrendFollowingStrategy] = None,
        starting_equity: float = 1000.0,
        risk_pct: float = 0.01,
        allow_fractional: bool = False,
    ) -> None:
        if not 0 < risk_pct <= 0.1:
            raise ValueError("risk_pct should be a small fraction, e.g. 0.01-0.02")
        self.strategy = strategy or TrendFollowingStrategy(StrategyConfig())
        self.starting_equity = starting_equity
        self.risk_pct = risk_pct
        self.allow_fractional = allow_fractional

    def _size(self, equity: float, entry: float, stop: float) -> float:
        risk_amount = equity * self.risk_pct
        per_share = entry - stop
        if per_share <= 0:
            return 0.0
        raw = risk_amount / per_share
        shares = raw if self.allow_fractional else math.floor(raw)
        # Never commit more cash than we have (cash account, no leverage).
        max_affordable = equity / entry
        if shares > max_affordable:
            shares = max_affordable if self.allow_fractional else math.floor(
                max_affordable
            )
        return max(shares, 0.0)

    def run(self, bars: List[Bar]) -> BacktestResult:
        equity = self.starting_equity
        cash = self.starting_equity
        trades: List[Trade] = []
        open_trade: Optional[Trade] = None
        curve: List[float] = []
        strat = self.strategy

        for i, bar in enumerate(bars):
            if open_trade is not None:
                # 1) Stop check against the low. A gap-down opens below the
                #    stop, so fill at the worse of stop and open.
                if bar.low <= open_trade.highest_stop:
                    fill = min(open_trade.highest_stop, bar.open)
                    cash += fill * open_trade.shares
                    open_trade.exit_date = bar.date
                    open_trade.exit_price = fill
                    open_trade.exit_reason = "stop"
                    open_trade = None
                else:
                    # 2) Trend-break exit on the close.
                    if strat.exit_on_trend_break(bars, i):
                        cash += bar.close * open_trade.shares
                        open_trade.exit_date = bar.date
                        open_trade.exit_price = bar.close
                        open_trade.exit_reason = "trend_break"
                        open_trade = None
                    else:
                        # 3) Otherwise ratchet the trailing stop up.
                        open_trade.highest_stop = strat.trail_stop(
                            bars, i, open_trade.highest_stop
                        )

            if open_trade is None:
                signal = strat.entry_signal(bars, i)
                if signal in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT):
                    entry = bar.close
                    stop = strat.initial_stop(bars, i)
                    if stop is not None and stop < entry:
                        shares = self._size(cash, entry, stop)
                        if shares > 0:
                            cash -= entry * shares
                            open_trade = Trade(
                                entry_date=bar.date,
                                entry_price=entry,
                                shares=shares,
                                initial_stop=stop,
                                reason=signal.value,
                                highest_stop=stop,
                            )
                            trades.append(open_trade)

            holding = open_trade.shares * bar.close if open_trade else 0.0
            equity = cash + holding
            curve.append(equity)

        # Mark any still-open position to the final close for reporting.
        if open_trade is not None and bars:
            equity = cash + open_trade.shares * bars[-1].close

        return BacktestResult(
            starting_equity=self.starting_equity,
            ending_equity=equity,
            trades=trades,
            equity_curve=curve,
        )
