"""The trend-following strategy, expressed as causal signals.

These are *the exact rules*, in code:

1. Trade only confirmed uptrends: close above both the 50- and 200-day SMA,
   and price making higher highs and higher lows.
2. Enter on a small pullback toward the 50-day average, or on a breakout above
   a recent high. Never chase: refuse entries already extended far above the
   50-day average.
3. The moment you enter, the stop sits just below the most recent swing low.
4. Exit when the trend breaks: a close below the 50-day average, or a lower low.

This module produces *signals*. Position sizing and trade management live in
:mod:`trendrail.backtest` so the rules stay readable and testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence

from .data import Bar
from . import indicators as ind


class Signal(Enum):
    NONE = "none"
    ENTER_PULLBACK = "enter_pullback"
    ENTER_BREAKOUT = "enter_breakout"
    EXIT_TREND_BREAK = "exit_trend_break"


@dataclass
class StrategyConfig:
    fast_ma: int = 50
    slow_ma: int = 200
    swing_window: int = 3
    # Breakout entry: close exceeds the highest high of the prior N bars.
    breakout_lookback: int = 20
    # Pullback entry: close is within this fraction of the 50-day average, then
    # closes up — a dip toward the trend, not a trend reversal.
    pullback_pct: float = 0.03
    # "Never chase": skip entries whose close is more than this fraction above
    # the 50-day average.
    max_extension_pct: float = 0.12
    # Stop buffer below the swing low, as a fraction of price.
    stop_buffer_pct: float = 0.005


class TrendFollowingStrategy:
    """Stateless signal generator. Each method is causal as of ``i``."""

    def __init__(self, config: Optional[StrategyConfig] = None) -> None:
        self.config = config or StrategyConfig()

    # --- trend filter -----------------------------------------------------

    def is_uptrend(self, bars: Sequence[Bar], i: int) -> bool:
        """True if bar ``i`` sits in a confirmed uptrend."""
        c = self.config
        if i < c.slow_ma:
            return False
        closes = [b.close for b in bars[: i + 1]]
        fast = ind.sma(closes, c.fast_ma)[i]
        slow = ind.sma(closes, c.slow_ma)[i]
        if fast is None or slow is None:
            return False

        close = bars[i].close
        above_mas = close > fast and close > slow
        # The faster average above the slower one means the recent trend leads
        # the long-term one — alignment, not just two separate threshold checks.
        stacked = fast > slow

        swings = ind.confirmed_swings_through(bars, i, c.swing_window)
        structure = ind.making_higher_highs_and_lows(swings)

        return above_mas and stacked and structure

    # --- entries ----------------------------------------------------------

    def _fast_ma(self, bars: Sequence[Bar], i: int) -> Optional[float]:
        closes = [b.close for b in bars[: i + 1]]
        return ind.sma(closes, self.config.fast_ma)[i]

    def _too_extended(self, bars: Sequence[Bar], i: int) -> bool:
        fast = self._fast_ma(bars, i)
        if fast is None or fast == 0:
            return True
        extension = (bars[i].close - fast) / fast
        return extension > self.config.max_extension_pct

    def _is_pullback_entry(self, bars: Sequence[Bar], i: int) -> bool:
        """A dip toward the 50-day average that closes back up."""
        if i < 1:
            return False
        fast = self._fast_ma(bars, i)
        if fast is None or fast == 0:
            return False
        # Today closed up (resuming the trend)...
        closed_up = bars[i].close > bars[i - 1].close
        # ...after pulling back near the 50-day average.
        near_ma = (bars[i].low - fast) / fast <= self.config.pullback_pct
        return closed_up and near_ma

    def _is_breakout_entry(self, bars: Sequence[Bar], i: int) -> bool:
        """Close pushes above the highest high of the prior lookback bars."""
        c = self.config
        if i < c.breakout_lookback:
            return False
        prior_high = max(b.high for b in bars[i - c.breakout_lookback:i])
        return bars[i].close > prior_high

    def entry_signal(self, bars: Sequence[Bar], i: int) -> Signal:
        """Entry signal for a flat account at bar ``i``."""
        if not self.is_uptrend(bars, i):
            return Signal.NONE
        if self._too_extended(bars, i):
            return Signal.NONE
        if self._is_pullback_entry(bars, i):
            return Signal.ENTER_PULLBACK
        if self._is_breakout_entry(bars, i):
            return Signal.ENTER_BREAKOUT
        return Signal.NONE

    # --- stops & exits ----------------------------------------------------

    def initial_stop(self, bars: Sequence[Bar], i: int) -> Optional[float]:
        """Stop just below the most recent confirmed swing low as of bar ``i``.

        Falls back to the lowest low of the swing window if no pivot is
        confirmed yet, so an entry always has a defined risk.
        """
        c = self.config
        swings = ind.confirmed_swings_through(bars, i, c.swing_window)
        low = ind.last_swing(swings, "low")
        if low is not None:
            ref = low.price
        else:
            start = max(0, i - c.swing_window)
            ref = min(b.low for b in bars[start:i + 1])
        return ref * (1.0 - c.stop_buffer_pct)

    def trail_stop(
        self, bars: Sequence[Bar], i: int, current_stop: float
    ) -> float:
        """Ratchet the stop up under the latest confirmed swing low.

        The stop only ever rises — we lock in gains, never give them back by
        loosening risk.
        """
        candidate = self.initial_stop(bars, i)
        if candidate is None:
            return current_stop
        return max(current_stop, candidate)

    def exit_on_trend_break(self, bars: Sequence[Bar], i: int) -> bool:
        """True when the trend has broken: close below the 50-day average,
        or a lower low (latest confirmed swing low below the prior one)."""
        c = self.config
        fast = self._fast_ma(bars, i)
        if fast is not None and bars[i].close < fast:
            return True

        swings = ind.confirmed_swings_through(bars, i, c.swing_window)
        lows = [s.price for s in swings if s.kind == "low"]
        if len(lows) >= 2 and lows[-1] < lows[-2]:
            return True
        return False
