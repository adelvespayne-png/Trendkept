"""Indicators: simple moving averages and causal swing-point detection.

Everything here is *causal* — a value at index ``i`` is computed only from data
at or before ``i``. That matters: a backtest that peeks at future bars looks
brilliant and trades terribly. Swing points need ``window`` bars of
confirmation, so a pivot at bar ``i`` is only *known* at bar ``i + window``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from .data import Bar


def sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    """Simple moving average.

    Returns a list the same length as ``values``; entries are ``None`` until
    ``period`` values are available.
    """
    if period <= 0:
        raise ValueError("period must be positive")

    out: List[Optional[float]] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


@dataclass(frozen=True)
class Swing:
    """A confirmed pivot: ``kind`` is ``"high"`` or ``"low"``."""

    index: int
    price: float
    kind: str


def swing_points(bars: Sequence[Bar], window: int = 3) -> List[Swing]:
    """Find confirmed swing highs and lows.

    A swing high at ``i`` is a bar whose ``high`` is the strict maximum of the
    ``window`` bars on either side; a swing low is the symmetric minimum of
    ``low``. Bars within ``window`` of either end can never be confirmed.
    """
    if window < 1:
        raise ValueError("window must be >= 1")

    swings: List[Swing] = []
    n = len(bars)
    for i in range(window, n - window):
        hi = bars[i].high
        lo = bars[i].low
        is_high = all(
            bars[j].high < hi for j in range(i - window, i + window + 1) if j != i
        )
        is_low = all(
            bars[j].low > lo for j in range(i - window, i + window + 1) if j != i
        )
        if is_high:
            swings.append(Swing(i, hi, "high"))
        if is_low:
            swings.append(Swing(i, lo, "low"))
    return swings


def confirmed_swings_through(
    bars: Sequence[Bar], end: int, window: int = 3
) -> List[Swing]:
    """Swings that are *confirmed* by bar ``end`` (inclusive).

    A pivot at index ``i`` is only confirmed once ``window`` later bars exist,
    i.e. when ``end >= i + window``. This is the function the live/causal code
    paths use so they never act on a pivot the market hasn't yet revealed.
    """
    horizon = end - window
    return [s for s in swing_points(bars[: end + 1], window) if s.index <= horizon]


def last_swing(swings: Sequence[Swing], kind: str) -> Optional[Swing]:
    """Most recent swing of the given ``kind`` (``"high"`` or ``"low"``)."""
    for s in reversed(swings):
        if s.kind == kind:
            return s
    return None


def making_higher_highs_and_lows(swings: Sequence[Swing]) -> bool:
    """True when the last two swing highs *and* last two swing lows are rising.

    This is the structural half of an uptrend: higher highs and higher lows.
    Needs at least two confirmed highs and two confirmed lows to judge.
    """
    highs = [s.price for s in swings if s.kind == "high"]
    lows = [s.price for s in swings if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return False
    return highs[-1] > highs[-2] and lows[-1] > lows[-2]
