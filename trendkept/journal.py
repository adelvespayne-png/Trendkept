"""The trade journal: turn broker fill history into scored round trips.

The journal is the discipline mirror. It pairs buy and sell fills into
completed round-trip trades (FIFO, long-only — matching the strategy),
finds the protective stop that was standing during each trade so the
result can be scored in R-multiples (profit measured in units of planned
risk), and summarises the numbers that actually matter: expectancy, not
win rate.

Everything here is pure data-in, data-out — no network — so the CLI and
the dashboard share it and the tests can feed it canned fills.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class Fill:
    symbol: str
    side: str        # "buy" | "sell"
    qty: float
    price: float
    at: str          # ISO timestamp, sortable as text


@dataclass
class RoundTrip:
    symbol: str
    qty: float
    entry_at: str
    entry_price: float
    exit_at: str
    exit_price: float
    planned_stop: Optional[float] = None

    @property
    def pnl(self) -> float:
        return (self.exit_price - self.entry_price) * self.qty

    @property
    def risk_per_share(self) -> Optional[float]:
        if self.planned_stop is None:
            return None
        risk = self.entry_price - self.planned_stop
        return risk if risk > 0 else None

    @property
    def r_multiple(self) -> Optional[float]:
        rps = self.risk_per_share
        if rps is None:
            return None
        return (self.exit_price - self.entry_price) / rps


@dataclass
class OpenLot:
    symbol: str
    qty: float
    entry_at: str
    entry_price: float
    planned_stop: Optional[float] = None


def normalize_fill(activity: dict) -> Optional[Fill]:
    """One Alpaca FILL activity -> a Fill, or None if malformed."""
    try:
        side = str(activity["side"]).lower()
        if side not in ("buy", "sell"):
            return None
        return Fill(
            symbol=str(activity["symbol"]).upper(),
            side=side,
            qty=float(activity["qty"]),
            price=float(activity["price"]),
            at=str(activity.get("transaction_time") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def pair_fills(fills: Sequence[Fill]) -> Tuple[List[RoundTrip], List[OpenLot]]:
    """FIFO-pair buys and sells per symbol into round trips + open lots.

    Partial fills are handled by quantity: a sell consumes the oldest open
    buy quantity first, splitting lots where needed.
    """
    trips: List[RoundTrip] = []
    lots: Dict[str, List[OpenLot]] = {}
    for f in sorted(fills, key=lambda f: f.at):
        book = lots.setdefault(f.symbol, [])
        if f.side == "buy":
            book.append(OpenLot(f.symbol, f.qty, f.at, f.price))
            continue
        remaining = f.qty
        while remaining > 1e-9 and book:
            lot = book[0]
            take = min(lot.qty, remaining)
            trips.append(RoundTrip(
                symbol=f.symbol, qty=take,
                entry_at=lot.entry_at, entry_price=lot.entry_price,
                exit_at=f.at, exit_price=f.price,
            ))
            lot.qty -= take
            remaining -= take
            if lot.qty <= 1e-9:
                book.pop(0)
        # A sell with no matching buy (short, transfer) is ignored: the
        # journal scores this strategy's long round trips only.
    open_lots = [lot for book in lots.values() for lot in book]
    return trips, open_lots


def attach_stops(trips: Sequence[RoundTrip], lots: Sequence[OpenLot],
                 stop_orders: Sequence[dict]) -> None:
    """Give each trade its planned stop, from the broker's order history.

    ``stop_orders``: dicts with symbol, stop_price, submitted_at. The
    planned stop is the earliest stop order submitted in the trade's
    window (a day's slack before entry covers stops submitted with the
    entry order, pre-fill).
    """
    def candidates(symbol: str, start: str, end: Optional[str]):
        # Compare by calendar day, with a day's slack before the entry
        # fill: the stop goes in with the entry order, which may be
        # submitted the evening before the fill prints.
        import datetime

        try:
            first = datetime.date.fromisoformat(start[:10])
            first_day = (first - datetime.timedelta(days=1)).isoformat()
        except ValueError:
            first_day = start[:10]
        last_day = (end or "9999-12-31")[:10]
        for o in stop_orders:
            try:
                if str(o["symbol"]).upper() != symbol:
                    continue
                day = str(o.get("submitted_at") or "")[:10]
                if not first_day <= day <= last_day:
                    continue
                yield day, float(o["stop_price"])
            except (KeyError, TypeError, ValueError):
                continue

    for t in trips:
        found = sorted(candidates(t.symbol, t.entry_at, t.exit_at))
        if found:
            t.planned_stop = found[0][1]
    for lot in lots:
        found = sorted(candidates(lot.symbol, lot.entry_at, None))
        if found:
            lot.planned_stop = found[0][1]


def journal_stats(trips: Sequence[RoundTrip]) -> dict:
    """The scoreboard: expectancy in R, not win rate vanity."""
    n = len(trips)
    wins = [t for t in trips if t.pnl > 0]
    rs = [t.r_multiple for t in trips if t.r_multiple is not None]
    stats = {
        "trades": n,
        "wins": len(wins),
        "win_rate": (len(wins) / n) if n else None,
        "total_pnl": sum(t.pnl for t in trips),
        "scored": len(rs),          # trades with a known planned stop
        "avg_r": (sum(rs) / len(rs)) if rs else None,
        "best_r": max(rs) if rs else None,
        "worst_r": min(rs) if rs else None,
        "stop_coverage": (len(rs) / n) if n else None,
    }
    return stats
