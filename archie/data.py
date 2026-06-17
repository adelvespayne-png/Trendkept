"""Daily OHLC data: the :class:`Bar` type and a robust CSV loader.

Real price files are messy. They come from Yahoo (``Date,Open,High,Low,Close,
Adj Close,Volume``), Stooq (``Date,Open,High,Low,Close,Volume``), broker
exports, or wide frames with ticker-prefixed headers (``AAPL.Open`` …). They
arrive newest-first or oldest-first, carry split/dividend distortions, and
occasionally have a close a hair outside the day's high/low from rounding.

This module copes with all of that so the strategy never trades on a data
artifact:

* Column names are matched by meaning, not exact spelling.
* When an adjusted-close column is present, the *whole* OHLC bar is scaled by
  the adjustment factor, so splits and dividends don't masquerade as price
  moves. A 2:1 split must not read as a 50% "lower low".
* Each bar is clamped so high/low actually bracket open/close.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class Bar:
    """One day of price action. Prices are post-adjustment when adjusted."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    def __post_init__(self) -> None:
        for name in ("open", "high", "low", "close"):
            v = getattr(self, name)
            if v <= 0:
                raise ValueError(f"{self.date}: {name} must be positive, got {v}")
        if self.high < self.low:
            raise ValueError(f"{self.date}: high {self.high} < low {self.low}")
        if not (self.low <= self.open <= self.high and
                self.low <= self.close <= self.high):
            raise ValueError(
                f"{self.date}: open/close outside [low, high]; "
                "load via load_csv/parse_csv_text which clamps feed artifacts"
            )


# Header aliases, matched case-insensitively. For wide frames the part after the
# last dot is also tried, so "AAPL.Open" resolves via "open".
_ALIASES: Dict[str, set] = {
    "date": {"date", "time", "datetime", "timestamp", "day"},
    "open": {"open", "o"},
    "high": {"high", "h"},
    "low": {"low", "l"},
    "close": {"close", "c", "price", "last"},
    "adj_close": {
        "adj close", "adj_close", "adjclose", "adjusted close",
        "adjusted_close", "adjusted", "adj. close",
    },
    "volume": {"volume", "vol", "v"},
}
_REQUIRED = ("date", "open", "high", "low", "close")


def _resolve_columns(fieldnames: Sequence[str]) -> Dict[str, str]:
    """Map canonical names to actual header strings. ``adj_close`` is matched
    before ``close`` so 'Adj Close' never gets mistaken for the raw close."""
    resolved: Dict[str, str] = {}
    order = ("date", "adj_close", "open", "high", "low", "close", "volume")
    for canonical in order:
        aliases = _ALIASES[canonical]
        for raw in fieldnames:
            if raw is None:
                continue
            key = raw.strip().lower()
            suffix = key.rsplit(".", 1)[-1].strip()
            if key in aliases or suffix in aliases:
                if raw not in resolved.values():
                    resolved[canonical] = raw
                    break
    missing = [c for c in _REQUIRED if c not in resolved]
    if missing:
        raise ValueError(
            "could not find column(s) for: " + ", ".join(missing)
            + f"; available headers: {list(fieldnames)}"
        )
    return resolved


def _num(row: dict, header: str) -> float:
    raw = row.get(header)
    if raw is None or raw.strip() == "":
        raise ValueError(f"empty value in column {header!r}")
    # Tolerate thousands separators that some exports include.
    return float(raw.replace(",", "").strip())


def _bars_from_reader(reader: csv.DictReader, adjust: bool) -> List[Bar]:
    if reader.fieldnames is None:
        raise ValueError("file has no header row")
    cols = _resolve_columns(reader.fieldnames)
    has_adj = adjust and "adj_close" in cols

    bars: List[Bar] = []
    for row in reader:
        date = row[cols["date"]].strip()
        if not date:
            continue  # skip blank trailing lines
        o = _num(row, cols["open"])
        h = _num(row, cols["high"])
        lo = _num(row, cols["low"])
        c = _num(row, cols["close"])

        if has_adj:
            adj = _num(row, cols["adj_close"])
            if c > 0:
                factor = adj / c
                o, h, lo, c = o * factor, h * factor, lo * factor, adj

        # Clamp away rounding artifacts so high/low bracket open/close.
        hi = max(h, o, c)
        low = min(lo, o, c)

        vol = None
        if "volume" in cols:
            raw_v = row.get(cols["volume"])
            if raw_v not in (None, ""):
                try:
                    vol = float(raw_v.replace(",", "").strip())
                except ValueError:
                    vol = None

        bars.append(Bar(date=date, open=o, high=hi, low=low, close=c, volume=vol))

    bars.sort(key=lambda b: b.date)
    return bars


def parse_csv_text(text: str, adjust: bool = True) -> List[Bar]:
    """Parse OHLC bars from CSV text. See module docstring for the rules."""
    return _bars_from_reader(csv.DictReader(io.StringIO(text)), adjust)


def load_csv(path: str, adjust: bool = True) -> List[Bar]:
    """Load daily bars from a CSV file, oldest-first.

    ``adjust`` (default True) scales OHLC by any adjusted-close column so splits
    and dividends don't appear as price moves. Raises ``ValueError`` if the
    required price columns can't be found.
    """
    with open(path, newline="") as handle:
        try:
            return _bars_from_reader(csv.DictReader(handle), adjust)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc
