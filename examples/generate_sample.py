"""Generate a deterministic synthetic daily series for demos and tests.

The series walks through the regimes the strategy is built to handle: a long
base, a sustained uptrend with pullbacks (where the strategy should make
money), then a trend break and decline (where it should be flat). No random
seed dependence on the platform — we use a tiny built-in LCG so the CSV is
byte-identical everywhere.

    python examples/generate_sample.py > examples/sample_uptrend.csv
"""

from __future__ import annotations

import sys
from datetime import date, timedelta


class LCG:
    """Minimal deterministic pseudo-random generator (no stdlib dependence)."""

    def __init__(self, seed: int = 12345) -> None:
        self.state = seed

    def next(self) -> float:
        self.state = (1103515245 * self.state + 12345) & 0x7FFFFFFF
        return self.state / 0x7FFFFFFF  # in [0, 1)

    def noise(self, scale: float) -> float:
        return (self.next() - 0.5) * 2.0 * scale


def build_series():
    rng = LCG()
    price = 100.0
    rows = []
    day = 0

    def emit(drift: float, vol: float, n: int) -> None:
        nonlocal price, day
        for _ in range(n):
            day_change = drift + rng.noise(vol)
            open_p = price
            close_p = max(1.0, price * (1.0 + day_change))
            hi = max(open_p, close_p) * (1.0 + abs(rng.noise(vol)) * 0.5)
            lo = min(open_p, close_p) * (1.0 - abs(rng.noise(vol)) * 0.5)
            rows.append((day, open_p, hi, lo, close_p))
            price = close_p
            day += 1

    # Regime 1: long sideways base so the 200-day MA is well established.
    emit(drift=0.0005, vol=0.012, n=210)
    # Regime 2: strong uptrend with periodic pullbacks.
    for _ in range(6):
        emit(drift=0.004, vol=0.012, n=25)   # impulse up
        emit(drift=-0.003, vol=0.012, n=8)   # pullback
    # Regime 3: trend break and decline.
    emit(drift=-0.004, vol=0.015, n=80)
    return rows


def main() -> int:
    rows = build_series()
    out = sys.stdout
    out.write("date,open,high,low,close\n")
    start = date(2022, 1, 3)  # a Monday; we step one calendar day per bar
    for day, o, h, l, c in rows:
        d = (start + timedelta(days=day)).isoformat()
        out.write(f"{d},{o:.2f},{h:.2f},{l:.2f},{c:.2f}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
