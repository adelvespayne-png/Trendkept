"""Daily OHLC data: the :class:`Bar` type and a small CSV loader.

The CSV is expected to have a header row and, at minimum, the columns
``date,open,high,low,close``. A ``volume`` column is read when present but is
optional. Column order does not matter; matching is by header name.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Bar:
    """One day of price action."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"{self.date}: high {self.high} < low {self.low}")
        for name in ("open", "close"):
            price = getattr(self, name)
            if not (self.low <= price <= self.high):
                raise ValueError(
                    f"{self.date}: {name} {price} outside range "
                    f"[{self.low}, {self.high}]"
                )


_REQUIRED = ("date", "open", "high", "low", "close")


def load_csv(path: str) -> List[Bar]:
    """Load daily bars from a CSV file, sorted oldest-first by date.

    Raises ``ValueError`` if any required column is missing.
    """
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: file has no header row")
        headers = {name.strip().lower(): name for name in reader.fieldnames}
        missing = [col for col in _REQUIRED if col not in headers]
        if missing:
            raise ValueError(
                f"{path}: missing required column(s): {', '.join(missing)}"
            )

        bars: List[Bar] = []
        for row in reader:
            volume_raw = (row.get(headers["volume"]) if "volume" in headers
                          else None)
            bars.append(
                Bar(
                    date=row[headers["date"]].strip(),
                    open=float(row[headers["open"]]),
                    high=float(row[headers["high"]]),
                    low=float(row[headers["low"]]),
                    close=float(row[headers["close"]]),
                    volume=float(volume_raw) if volume_raw not in (None, "") else None,
                )
            )

    bars.sort(key=lambda b: b.date)
    return bars
