#!/usr/bin/env python3
"""Trendrail — a disciplined trend-following trading bot, in a single file.

Pure Python standard library: no pip install, no dependencies. Drop this one
file anywhere and run it with Python 3.9+.

THE RULES (this bot enforces exactly these):
  1. Trade only confirmed uptrends: close above the 50- and 200-day moving
     averages (and the 50 above the 200), making higher highs and higher lows.
  2. Enter on a small pullback toward the 50-day average, or a breakout above a
     recent high. Never chase a move already extended far above the 50-day MA.
  3. The moment you enter, the stop sits just below the most recent swing low.
  4. Size so a stop-out costs only 1-2% of the account.
  5. Trail the stop up under each new higher swing low (it only ever rises).
  6. Exit when the trend breaks: a close below the 50-day MA, or a lower low.
The edge: cut losers fast and small, let winners run big.

USAGE
  # Backtest / scan a CSV (date,open,high,low,close[,volume])
  python3 trendrail_bot.py backtest mydata.csv --account 1000 --risk 0.02 -v
  python3 trendrail_bot.py scan     mydata.csv

  # Live data, free, no API key (Stooq -> Yahoo)
  python3 trendrail_bot.py backtest --symbol AAPL --account 1000 -v
  python3 trendrail_bot.py fetch    AAPL --out aapl.csv

  # Alpaca paper trading (free keys from alpaca.markets):
  export APCA_API_KEY_ID=...        # Windows PowerShell: $env:APCA_API_KEY_ID="..."
  export APCA_API_SECRET_KEY=...
  python3 trendrail_bot.py account
  python3 trendrail_bot.py trade  AAPL --risk 0.01 --confirm   # paper, with attached stop
  python3 trendrail_bot.py manage --confirm                    # run daily: trail / exit

Educational tool, not financial advice. Backtests use idealized fills. Paper
trade until you can follow the rules without flinching before risking real money.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Sequence

__version__ = "0.1.0"


# =============================================================================
# DATA  — the Bar type and a robust CSV loader
# =============================================================================

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
    return float(raw.replace(",", "").strip())  # tolerate thousands separators


def _bars_from_reader(reader: csv.DictReader, adjust: bool) -> List[Bar]:
    if reader.fieldnames is None:
        raise ValueError("file has no header row")
    cols = _resolve_columns(reader.fieldnames)
    has_adj = adjust and "adj_close" in cols

    bars: List[Bar] = []
    for row in reader:
        date = row[cols["date"]].strip()
        if not date:
            continue
        o = _num(row, cols["open"])
        h = _num(row, cols["high"])
        lo = _num(row, cols["low"])
        c = _num(row, cols["close"])

        if has_adj:
            adj = _num(row, cols["adj_close"])
            if c > 0:
                factor = adj / c  # scale whole bar so splits aren't false moves
                o, h, lo, c = o * factor, h * factor, lo * factor, adj

        hi = max(h, o, c)   # clamp away rounding artifacts
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
    """Parse OHLC bars from CSV text."""
    return _bars_from_reader(csv.DictReader(io.StringIO(text)), adjust)


def load_csv(path: str, adjust: bool = True) -> List[Bar]:
    """Load daily bars from a CSV file, oldest-first. ``adjust`` scales OHLC by
    any adjusted-close column so splits/dividends don't appear as price moves."""
    with open(path, newline="") as handle:
        try:
            return _bars_from_reader(csv.DictReader(handle), adjust)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from exc


# =============================================================================
# INDICATORS  — moving averages and causal swing-point detection
# =============================================================================
# Everything is *causal*: a value at index i uses only data at or before i.
# Swing pivots need ``window`` later bars to confirm, so a pivot at bar i is
# only known at bar i + window. A backtest that peeks ahead trades terribly.

def sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    """Simple moving average; entries are None until ``period`` values exist."""
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
    """A confirmed pivot: ``kind`` is 'high' or 'low'."""

    index: int
    price: float
    kind: str


def swing_points(bars: Sequence[Bar], window: int = 3) -> List[Swing]:
    """Confirmed swing highs/lows: a strict extreme of the ``window`` bars on
    either side. Bars within ``window`` of either end can't be confirmed."""
    if window < 1:
        raise ValueError("window must be >= 1")
    swings: List[Swing] = []
    n = len(bars)
    for i in range(window, n - window):
        hi, lo = bars[i].high, bars[i].low
        if all(bars[j].high < hi for j in range(i - window, i + window + 1) if j != i):
            swings.append(Swing(i, hi, "high"))
        if all(bars[j].low > lo for j in range(i - window, i + window + 1) if j != i):
            swings.append(Swing(i, lo, "low"))
    return swings


def confirmed_swings_through(bars: Sequence[Bar], end: int,
                             window: int = 3) -> List[Swing]:
    """Swings confirmed by bar ``end`` (only those at index <= end - window)."""
    horizon = end - window
    return [s for s in swing_points(bars[: end + 1], window) if s.index <= horizon]


def last_swing(swings: Sequence[Swing], kind: str) -> Optional[Swing]:
    for s in reversed(swings):
        if s.kind == kind:
            return s
    return None


def making_higher_highs_and_lows(swings: Sequence[Swing]) -> bool:
    """True when the last two swing highs AND last two swing lows are rising."""
    highs = [s.price for s in swings if s.kind == "high"]
    lows = [s.price for s in swings if s.kind == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return False
    return highs[-1] > highs[-2] and lows[-1] > lows[-2]


# =============================================================================
# STRATEGY  — the rules expressed as causal signals
# =============================================================================

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
    breakout_lookback: int = 20      # breakout: close above prior-N highest high
    pullback_pct: float = 0.03       # pullback: dip within 3% of the 50-day MA
    max_extension_pct: float = 0.12  # "never chase": skip if >12% above the 50MA
    stop_buffer_pct: float = 0.005   # stop sits this far below the swing low


class TrendFollowingStrategy:
    """Stateless signal generator. Each method is causal as of bar ``i``."""

    def __init__(self, config: Optional[StrategyConfig] = None) -> None:
        self.config = config or StrategyConfig()

    def is_uptrend(self, bars: Sequence[Bar], i: int) -> bool:
        c = self.config
        if i < c.slow_ma:
            return False
        closes = [b.close for b in bars[: i + 1]]
        fast = sma(closes, c.fast_ma)[i]
        slow = sma(closes, c.slow_ma)[i]
        if fast is None or slow is None:
            return False
        close = bars[i].close
        above_mas = close > fast and close > slow
        stacked = fast > slow  # recent trend leads the long-term one
        swings = confirmed_swings_through(bars, i, c.swing_window)
        structure = making_higher_highs_and_lows(swings)
        return above_mas and stacked and structure

    def _fast_ma(self, bars: Sequence[Bar], i: int) -> Optional[float]:
        return sma([b.close for b in bars[: i + 1]], self.config.fast_ma)[i]

    def _too_extended(self, bars: Sequence[Bar], i: int) -> bool:
        fast = self._fast_ma(bars, i)
        if fast is None or fast == 0:
            return True
        return (bars[i].close - fast) / fast > self.config.max_extension_pct

    def _is_pullback_entry(self, bars: Sequence[Bar], i: int) -> bool:
        if i < 1:
            return False
        fast = self._fast_ma(bars, i)
        if fast is None or fast == 0:
            return False
        closed_up = bars[i].close > bars[i - 1].close          # resuming up...
        near_ma = (bars[i].low - fast) / fast <= self.config.pullback_pct  # ...after a dip
        return closed_up and near_ma

    def _is_breakout_entry(self, bars: Sequence[Bar], i: int) -> bool:
        c = self.config
        if i < c.breakout_lookback:
            return False
        prior_high = max(b.high for b in bars[i - c.breakout_lookback:i])
        return bars[i].close > prior_high

    def entry_signal(self, bars: Sequence[Bar], i: int) -> Signal:
        if not self.is_uptrend(bars, i):
            return Signal.NONE
        if self._too_extended(bars, i):
            return Signal.NONE
        if self._is_pullback_entry(bars, i):
            return Signal.ENTER_PULLBACK
        if self._is_breakout_entry(bars, i):
            return Signal.ENTER_BREAKOUT
        return Signal.NONE

    def initial_stop(self, bars: Sequence[Bar], i: int) -> Optional[float]:
        """Stop just below the most recent confirmed swing low as of bar ``i``."""
        c = self.config
        swings = confirmed_swings_through(bars, i, c.swing_window)
        low = last_swing(swings, "low")
        if low is not None:
            ref = low.price
        else:
            start = max(0, i - c.swing_window)
            ref = min(b.low for b in bars[start:i + 1])
        return ref * (1.0 - c.stop_buffer_pct)

    def trail_stop(self, bars: Sequence[Bar], i: int, current_stop: float) -> float:
        """Ratchet the stop up under the latest swing low; it only ever rises."""
        candidate = self.initial_stop(bars, i)
        if candidate is None:
            return current_stop
        return max(current_stop, candidate)

    def exit_on_trend_break(self, bars: Sequence[Bar], i: int) -> bool:
        """Close below the 50-day MA, or a lower low."""
        c = self.config
        fast = self._fast_ma(bars, i)
        if fast is not None and bars[i].close < fast:
            return True
        swings = confirmed_swings_through(bars, i, c.swing_window)
        lows = [s.price for s in swings if s.kind == "low"]
        return len(lows) >= 2 and lows[-1] < lows[-2]


# =============================================================================
# BACKTEST  — bar-by-bar simulator with risk sizing and trailing stops
# =============================================================================

@dataclass
class Trade:
    entry_date: str
    entry_price: float
    shares: float
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
        """Profit in units of initial risk — the score for a let-winners-run system."""
        risk = self.risk_per_share * self.shares
        return self.pnl / risk if risk > 0 else 0.0


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
        return sum(1 for t in closed if t.pnl > 0) / len(closed) * 100.0

    @property
    def expectancy_r(self) -> float:
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
    def __init__(self, strategy: Optional[TrendFollowingStrategy] = None,
                 starting_equity: float = 1000.0, risk_pct: float = 0.01,
                 allow_fractional: bool = False) -> None:
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
        max_affordable = equity / entry  # cash account, no leverage
        if shares > max_affordable:
            shares = (max_affordable if self.allow_fractional
                      else math.floor(max_affordable))
        return max(shares, 0.0)

    def run(self, bars: List[Bar]) -> BacktestResult:
        equity = cash = self.starting_equity
        trades: List[Trade] = []
        open_trade: Optional[Trade] = None
        curve: List[float] = []
        strat = self.strategy

        for i, bar in enumerate(bars):
            if open_trade is not None:
                # 1) Stop check vs the low; a gap-down fills at the worse of stop/open.
                if bar.low <= open_trade.highest_stop:
                    fill = min(open_trade.highest_stop, bar.open)
                    cash += fill * open_trade.shares
                    open_trade.exit_date = bar.date
                    open_trade.exit_price = fill
                    open_trade.exit_reason = "stop"
                    open_trade = None
                elif strat.exit_on_trend_break(bars, i):  # 2) trend-break exit on close
                    cash += bar.close * open_trade.shares
                    open_trade.exit_date = bar.date
                    open_trade.exit_price = bar.close
                    open_trade.exit_reason = "trend_break"
                    open_trade = None
                else:                                      # 3) otherwise trail the stop up
                    open_trade.highest_stop = strat.trail_stop(
                        bars, i, open_trade.highest_stop)

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
                                entry_date=bar.date, entry_price=entry,
                                shares=shares, initial_stop=stop,
                                reason=signal.value, highest_stop=stop)
                            trades.append(open_trade)

            holding = open_trade.shares * bar.close if open_trade else 0.0
            equity = cash + holding
            curve.append(equity)

        if open_trade is not None and bars:
            equity = cash + open_trade.shares * bars[-1].close

        return BacktestResult(self.starting_equity, equity, trades, curve)


# =============================================================================
# FETCH  — free daily history, no API key (Stooq primary, Yahoo fallback)
# =============================================================================

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


class FetchError(RuntimeError):
    """Raised when a provider returns no usable data."""


def _http_get(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"network error for {url}: {exc.reason}") from exc


def _stooq_symbol(symbol: str) -> str:
    """Stooq wants an exchange suffix; default bare tickers to US equities.
    Index symbols (^spx) and explicit suffixes (vod.uk) are left alone."""
    s = symbol.strip().lower()
    if "." in s or s.startswith("^"):
        return s
    return f"{s}.us"


def stooq_csv(symbol: str, timeout: float = 30.0) -> str:
    url = f"https://stooq.com/q/d/l/?s={_stooq_symbol(symbol)}&i=d"
    text = _http_get(url, timeout)
    head = text.strip().lower()
    if not head or head.startswith("n/d") or "date" not in head.splitlines()[0]:
        raise FetchError(f"Stooq returned no data for {symbol!r} (got: {text[:60]!r})")
    return text


def yahoo_to_csv(payload: str, symbol: str = "") -> str:
    """Convert a Yahoo v8 chart JSON payload to OHLC CSV text."""
    data = json.loads(payload)
    chart = data.get("chart") or {}
    if chart.get("error"):
        raise FetchError(f"Yahoo error for {symbol!r}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise FetchError(f"Yahoo returned no result for {symbol!r}")
    result = results[0]

    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adj_block = result.get("indicators", {}).get("adjclose") or [{}]
    adjclose = adj_block[0].get("adjclose") if adj_block else None
    opens, highs = quote.get("open") or [], quote.get("high") or []
    lows, closes = quote.get("low") or [], quote.get("close") or []
    volumes = quote.get("volume") or []
    if not timestamps:
        raise FetchError(f"Yahoo returned no timestamps for {symbol!r}")

    lines = ["Date,Open,High,Low,Close,Adj Close,Volume"]
    for i, ts in enumerate(timestamps):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if None in (o, h, l, c):  # null on holidays/halts
            continue
        adj = adjclose[i] if adjclose and adjclose[i] is not None else c
        vol = volumes[i] if i < len(volumes) and volumes[i] is not None else ""
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        lines.append(f"{date},{o},{h},{l},{c},{adj},{vol}")
    if len(lines) == 1:
        raise FetchError(f"Yahoo returned no usable bars for {symbol!r}")
    return "\n".join(lines) + "\n"


def yahoo_csv(symbol: str, range_: str = "5y", interval: str = "1d",
              timeout: float = 30.0) -> str:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={range_}&interval={interval}&events=div%2Csplit")
    return yahoo_to_csv(_http_get(url, timeout), symbol)


def fetch_csv(symbol: str, provider: str = "auto", *, range_: str = "5y",
              timeout: float = 30.0) -> str:
    """Raw CSV text for ``symbol``. provider: auto | stooq | yahoo."""
    provider = provider.lower()
    if provider == "stooq":
        return stooq_csv(symbol, timeout)
    if provider == "yahoo":
        return yahoo_csv(symbol, range_=range_, timeout=timeout)
    if provider == "auto":
        errors = []
        for name, fn in (("stooq", lambda: stooq_csv(symbol, timeout)),
                         ("yahoo", lambda: yahoo_csv(symbol, range_=range_,
                                                     timeout=timeout))):
            try:
                return fn()
            except FetchError as exc:
                errors.append(f"{name}: {exc}")
        raise FetchError(f"all providers failed for {symbol!r}: " + " | ".join(errors))
    raise ValueError(f"unknown provider {provider!r}; use auto, stooq, or yahoo")


# =============================================================================
# ALPACA  — historical data + paper/live order placement (stdlib only)
# =============================================================================
# Credentials come from APCA_API_KEY_ID / APCA_API_SECRET_KEY (env only).
# paper=True by default; nothing is sent until you confirm. Free keys at
# https://alpaca.markets.

_DATA_HOST = "https://data.alpaca.markets"
_PAPER_HOST = "https://paper-api.alpaca.markets"
_LIVE_HOST = "https://api.alpaca.markets"


class AlpacaError(RuntimeError):
    """Any failure talking to Alpaca (auth, HTTP, or empty data)."""


@dataclass
class TradePlan:
    """A sized, stop-protected entry intent — not yet submitted."""

    symbol: str
    signal: str
    quantity: int
    entry_price: float
    stop_price: float
    risk_per_share: float
    dollar_risk: float
    account_equity: float

    def describe(self) -> str:
        return (f"{self.signal.upper()} {self.symbol}: buy {self.quantity} @ "
                f"~{self.entry_price:.2f}, stop {self.stop_price:.2f} "
                f"(risk {self.risk_per_share:.2f}/sh, total {self.dollar_risk:.2f} "
                f"= {self.dollar_risk / self.account_equity * 100:.2f}% of "
                f"{self.account_equity:,.2f})")


class AlpacaClient:
    def __init__(self, key_id: Optional[str] = None, secret_key: Optional[str] = None,
                 paper: bool = True, feed: str = "iex", timeout: float = 30.0) -> None:
        self.key_id = key_id or os.environ.get("APCA_API_KEY_ID")
        self.secret_key = secret_key or os.environ.get("APCA_API_SECRET_KEY")
        if not self.key_id or not self.secret_key:
            raise AlpacaError(
                "missing credentials: set APCA_API_KEY_ID and "
                "APCA_API_SECRET_KEY (use your Alpaca *paper* keys to start)")
        self.paper = paper
        self.feed = feed
        self.timeout = timeout
        self.trading_host = _PAPER_HOST if paper else _LIVE_HOST

    def _headers(self) -> Dict[str, str]:
        return {"APCA-API-KEY-ID": self.key_id,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Content-Type": "application/json", "Accept": "application/json"}

    def _request(self, method: str, url: str, body: Optional[dict] = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(),
                                     method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AlpacaError(f"HTTP {exc.code} {method} {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise AlpacaError(f"network error {method} {url}: {exc.reason}") from exc
        return json.loads(raw) if raw.strip() else {}

    @staticmethod
    def _bars_from_payload(payload: dict) -> List[Bar]:
        out: List[Bar] = []
        for b in payload.get("bars") or []:
            date = b["t"].split("T")[0]  # RFC3339 -> YYYY-MM-DD
            o, h, l, c = float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"])
            hi, lo = max(h, o, c), min(l, o, c)
            out.append(Bar(date, o, hi, lo, c, volume=float(b.get("v", 0)) or None))
        return out

    def daily_bars(self, symbol: str, start: Optional[str] = None,
                   end: Optional[str] = None, adjustment: str = "all",
                   max_bars: int = 5000) -> List[Bar]:
        """Adjusted daily bars, oldest-first; default ~5 years through today."""
        if start is None:
            start = (datetime.now(timezone.utc)
                     - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
        bars: List[Bar] = []
        page_token: Optional[str] = None
        while True:
            params = {"timeframe": "1Day", "start": start, "adjustment": adjustment,
                      "feed": self.feed, "limit": 10000}
            if end:
                params["end"] = end
            if page_token:
                params["page_token"] = page_token
            url = (f"{_DATA_HOST}/v2/stocks/{urllib.parse.quote(symbol)}/bars?"
                   + urllib.parse.urlencode(params))
            payload = self._request("GET", url)
            bars.extend(self._bars_from_payload(payload))
            page_token = payload.get("next_page_token")
            if not page_token or len(bars) >= max_bars:
                break
        if not bars:
            raise AlpacaError(
                f"no bars returned for {symbol!r}; check the symbol and that your "
                f"plan permits the {self.feed!r} feed")
        bars.sort(key=lambda x: x.date)
        return bars

    def account(self) -> dict:
        return self._request("GET", f"{self.trading_host}/v2/account")

    def equity(self) -> float:
        return float(self.account()["equity"])

    def positions(self) -> List[dict]:
        result = self._request("GET", f"{self.trading_host}/v2/positions")
        return result if isinstance(result, list) else []

    def get_position(self, symbol: str) -> Optional[dict]:
        try:
            return self._request(
                "GET", f"{self.trading_host}/v2/positions/{urllib.parse.quote(symbol)}")
        except AlpacaError:
            return None  # 404 => no open position

    def submit_entry_with_stop(self, symbol: str, qty: int, stop_price: float,
                               limit_price: Optional[float] = None,
                               tif: str = "day") -> dict:
        """Buy with a protective stop attached (OTO order)."""
        order: Dict[str, object] = {
            "symbol": symbol, "qty": str(qty), "side": "buy", "time_in_force": tif,
            "order_class": "oto", "stop_loss": {"stop_price": f"{stop_price:.2f}"}}
        if limit_price is not None:
            order["type"] = "limit"
            order["limit_price"] = f"{limit_price:.2f}"
        else:
            order["type"] = "market"
        return self._request("POST", f"{self.trading_host}/v2/orders", body=order)

    def submit_stop_sell(self, symbol: str, qty, stop_price: float,
                         tif: str = "gtc") -> dict:
        """Standalone protective sell-stop (good-till-cancelled)."""
        order = {"symbol": symbol, "qty": str(qty), "side": "sell", "type": "stop",
                 "time_in_force": tif, "stop_price": f"{stop_price:.2f}"}
        return self._request("POST", f"{self.trading_host}/v2/orders", body=order)

    def list_orders(self, status: str = "open") -> List[dict]:
        result = self._request(
            "GET", f"{self.trading_host}/v2/orders?status={status}&limit=100")
        return result if isinstance(result, list) else []

    def replace_order(self, order_id: str, stop_price: float) -> dict:
        """Raise a protective stop (trailing) by replacing the order."""
        return self._request("PATCH", f"{self.trading_host}/v2/orders/{order_id}",
                             body={"stop_price": f"{stop_price:.2f}"})

    def cancel_order(self, order_id: str) -> dict:
        return self._request("DELETE", f"{self.trading_host}/v2/orders/{order_id}")

    def close_position(self, symbol: str) -> dict:
        """Liquidate the whole position at market."""
        return self._request(
            "DELETE", f"{self.trading_host}/v2/positions/{urllib.parse.quote(symbol)}")

    def find_stop_order(self, symbol: str) -> Optional[dict]:
        """The open protective sell-stop, digging through OTO/bracket legs."""
        symbol = symbol.upper()
        for order in self.list_orders(status="open"):
            for candidate in [order, *(order.get("legs") or [])]:
                if (candidate.get("symbol", "").upper() == symbol
                        and candidate.get("side") == "sell"
                        and "stop" in (candidate.get("type") or "")
                        and candidate.get("status") in (
                            "new", "held", "accepted", "pending_new")):
                    return candidate
        return None


def plan_trade(client: AlpacaClient, strategy: TrendFollowingStrategy, symbol: str,
               bars: List[Bar], risk_pct: float) -> Optional[TradePlan]:
    """Turn the latest-bar signal into a sized, stop-protected intent (or None)."""
    i = len(bars) - 1
    signal = strategy.entry_signal(bars, i)
    if signal not in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT):
        return None
    stop = strategy.initial_stop(bars, i)
    entry = bars[i].close
    if stop is None or stop >= entry:
        return None
    equity = client.equity()
    risk_per_share = entry - stop
    qty = int((equity * risk_pct) // risk_per_share)
    qty = min(qty, int(equity // entry))  # never exceed cash
    if qty <= 0:
        return None
    return TradePlan(symbol.upper(), signal.value, qty, entry, stop, risk_per_share,
                     qty * risk_per_share, equity)


@dataclass
class ManagementAction:
    """What to do with an open position: exit | raise_stop | set_stop | hold."""

    kind: str
    reason: str
    symbol: str = ""
    new_stop: Optional[float] = None
    current_stop: Optional[float] = None

    def describe(self) -> str:
        if self.kind == "exit":
            return f"EXIT {self.symbol}: {self.reason}"
        if self.kind == "raise_stop":
            return (f"RAISE STOP {self.symbol}: {self.current_stop:.2f} -> "
                    f"{self.new_stop:.2f} ({self.reason})")
        if self.kind == "set_stop":
            return f"SET STOP {self.symbol}: {self.new_stop:.2f} ({self.reason})"
        cur = f" (stop {self.current_stop:.2f})" if self.current_stop else ""
        return f"HOLD {self.symbol}: {self.reason}{cur}"


def decide_management(strategy: TrendFollowingStrategy, bars: List[Bar],
                      current_stop: Optional[float], symbol: str = "") -> ManagementAction:
    """Manage an open long on the latest bar. Trend-break exit wins; else the
    stop only ratchets up. Pure and side-effect-free."""
    i = len(bars) - 1
    if strategy.exit_on_trend_break(bars, i):
        return ManagementAction("exit", "trend break: close below 50-day MA or a lower low",
                                symbol=symbol, current_stop=current_stop)
    candidate = strategy.initial_stop(bars, i)
    if current_stop is None:
        return ManagementAction("set_stop", "no protective stop found; installing one",
                                symbol=symbol, new_stop=candidate)
    new_stop = strategy.trail_stop(bars, i, current_stop)
    if new_stop > current_stop + 1e-6:
        return ManagementAction("raise_stop", "higher swing low formed", symbol=symbol,
                                new_stop=new_stop, current_stop=current_stop)
    return ManagementAction("hold", "trend intact, stop unchanged", symbol=symbol,
                            current_stop=current_stop)


# =============================================================================
# CLI
# =============================================================================

def _build_strategy(args: argparse.Namespace) -> TrendFollowingStrategy:
    return TrendFollowingStrategy(StrategyConfig(
        fast_ma=args.fast_ma, slow_ma=args.slow_ma,
        breakout_lookback=args.breakout_lookback))


def _load_bars(args: argparse.Namespace):
    if getattr(args, "symbol", None):
        if args.provider == "alpaca":
            client = AlpacaClient(paper=not getattr(args, "live", False),
                                  feed=getattr(args, "feed", "iex"))
            return client.daily_bars(args.symbol), f"{args.symbol.upper()} (alpaca {client.feed})"
        text = fetch_csv(args.symbol, provider=args.provider, range_=args.range)
        return parse_csv_text(text), f"{args.symbol.upper()} ({args.provider})"
    if args.csv:
        return load_csv(args.csv), args.csv
    raise SystemExit("error: provide a CSV path or --symbol TICKER")


def _load_bars_or_exit(args: argparse.Namespace):
    try:
        return _load_bars(args)
    except FileNotFoundError as exc:
        raise SystemExit(f"error: file not found: {exc.filename}")
    except (ValueError, OSError, FetchError, AlpacaError) as exc:
        raise SystemExit(f"error: {exc}")


def _cmd_backtest(args: argparse.Namespace) -> int:
    bars, label = _load_bars_or_exit(args)
    if len(bars) < args.slow_ma + 1:
        print(f"Need at least {args.slow_ma + 1} bars to confirm a {args.slow_ma}-day "
              f"trend; got {len(bars)}.", file=sys.stderr)
        return 1
    result = Backtester(_build_strategy(args), args.account, args.risk).run(bars)

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
        print(f"  {'entry':<12}{'exit':<12}{'shares':>8}{'entry$':>10}"
              f"{'exit$':>10}{'R':>8}  reason/exit")
        for t in result.trades:
            exit_date = t.exit_date or "(open)"
            exit_price = f"{t.exit_price:.2f}" if t.exit_price is not None else "-"
            print(f"  {t.entry_date:<12}{exit_date:<12}{t.shares:>8.4g}"
                  f"{t.entry_price:>10.2f}{exit_price:>10}{t.r_multiple:>8.2f}  "
                  f"{t.reason}/{t.exit_reason or '-'}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    bars, label = _load_bars_or_exit(args)
    if len(bars) < args.slow_ma + 1:
        print(f"Need at least {args.slow_ma + 1} bars; got {len(bars)}.", file=sys.stderr)
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
        print(f"Position size    : {shares} shares (risking {risk_amount:,.2f} = "
              f"{args.risk * 100:.1f}% of {args.account:,.2f})")
        if shares == 0:
            print("  -> stop is too wide for this account at this risk %; skip.")
    else:
        print("SIGNAL           : no entry (wait for a pullback or breakout)")
        if not uptrend:
            print("  -> trend not confirmed; stay out.")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
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
    print(f"  equity        : {float(acct.get('equity', 0)):,.2f} {acct.get('currency', '')}")
    print(f"  cash          : {float(acct.get('cash', 0)):,.2f}")
    print(f"  buying power   : {float(acct.get('buying_power', 0)):,.2f}")
    print(f"  open positions : {len(positions)}")
    for p in positions:
        print(f"    {p.get('symbol'):<6} {p.get('qty')} @ "
              f"{float(p.get('avg_entry_price', 0)):.2f}  "
              f"P/L {float(p.get('unrealized_pl', 0)):+.2f}")
    return 0


def _cmd_trade(args: argparse.Namespace) -> int:
    try:
        client = AlpacaClient(paper=not args.live, feed=args.feed)
        bars = client.daily_bars(args.symbol)
    except AlpacaError as exc:
        print(f"Alpaca error: {exc}", file=sys.stderr)
        return 1
    if len(bars) < args.slow_ma + 1:
        print(f"Need at least {args.slow_ma + 1} bars; got {len(bars)}.", file=sys.stderr)
        return 1
    strat = _build_strategy(args)
    i = len(bars) - 1
    mode = "LIVE" if args.live else "paper"
    print(f"{args.symbol.upper()} (alpaca {mode})  as of {bars[i].date}  "
          f"close={bars[i].close:.2f}")
    print(f"Confirmed uptrend: {'YES' if strat.is_uptrend(bars, i) else 'no'}")

    if client.get_position(args.symbol):
        print("Already holding a position in this symbol; use `manage`. No order placed.")
        return 0
    try:
        plan = plan_trade(client, strat, args.symbol, bars, args.risk)
    except AlpacaError as exc:
        print(f"Alpaca error: {exc}", file=sys.stderr)
        return 1
    if plan is None:
        print("SIGNAL: no entry today (wait for a pullback or breakout). Nothing to do.")
        return 0

    print("SIGNAL: " + plan.describe())
    if not args.confirm:
        print(f"\nDRY RUN — no order sent. Re-run with --confirm to submit to {mode}.")
        return 0
    if args.live and not args.i_understand_live:
        print("\nRefusing to place a LIVE order without --i-understand-live. "
              "This risks real money.", file=sys.stderr)
        return 1
    limit = plan.entry_price * (1 + args.limit_slippage)
    order = client.submit_entry_with_stop(plan.symbol, plan.quantity, plan.stop_price,
                                          limit_price=limit)
    print(f"\nOrder submitted to {mode}: id={order.get('id')} status={order.get('status')} "
          f"(buy {plan.quantity} {plan.symbol}, stop {plan.stop_price:.2f})")
    return 0


def _manage_one(client: AlpacaClient, strat: TrendFollowingStrategy,
                position: dict, args: argparse.Namespace) -> None:
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
    if action.kind == "exit":
        if stop_order:
            client.cancel_order(stop_order["id"])
        client.close_position(symbol)
        print("    -> position closed at market; stop order cancelled.")
    elif action.kind == "raise_stop" and stop_order:
        client.replace_order(stop_order["id"], action.new_stop)
        print(f"    -> stop raised to {action.new_stop:.2f}.")
    elif action.kind in ("set_stop", "raise_stop"):
        client.submit_stop_sell(symbol, qty, action.new_stop)
        print(f"    -> protective stop placed at {action.new_stop:.2f}.")


def _cmd_manage(args: argparse.Namespace) -> int:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trendrail_bot", description="Disciplined trend-following trading bot.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_source(p):
        p.add_argument("csv", nargs="?", default=None,
                       help="CSV with date,open,high,low,close (or use --symbol)")
        p.add_argument("--symbol", help="ticker to fetch live instead of a CSV")
        p.add_argument("--provider", default="auto",
                       choices=["auto", "stooq", "yahoo", "alpaca"],
                       help="data provider for --symbol (default auto)")
        p.add_argument("--range", default="5y", dest="range",
                       help="history range for Yahoo fetches (default 5y)")
        p.add_argument("--feed", default="iex",
                       help="Alpaca data feed: iex (free) or sip (default iex)")
        p.add_argument("--live", action="store_true",
                       help="use the LIVE Alpaca account for --provider alpaca")

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
    fp.add_argument("--provider", default="auto", choices=["auto", "stooq", "yahoo"])
    fp.add_argument("--range", default="5y", dest="range")
    fp.add_argument("--out", help="write CSV here (default: stdout)")
    fp.set_defaults(func=_cmd_fetch)

    ap = sub.add_parser("account", help="show Alpaca account & positions")
    ap.add_argument("--live", action="store_true", help="use the LIVE account")
    ap.set_defaults(func=_cmd_account)

    tp = sub.add_parser("trade",
                        help="scan a symbol on Alpaca and place a stop-protected entry")
    tp.add_argument("symbol", help="ticker to trade, e.g. AAPL")
    tp.add_argument("--risk", type=float, default=0.01,
                    help="fraction of account risked per trade (default 0.01)")
    tp.add_argument("--feed", default="iex", help="Alpaca data feed (default iex)")
    tp.add_argument("--fast-ma", type=int, default=50, dest="fast_ma")
    tp.add_argument("--slow-ma", type=int, default=200, dest="slow_ma")
    tp.add_argument("--breakout-lookback", type=int, default=20, dest="breakout_lookback")
    tp.add_argument("--limit-slippage", type=float, default=0.005, dest="limit_slippage",
                    help="limit price headroom above close (default 0.5%%)")
    tp.add_argument("--confirm", action="store_true",
                    help="actually submit the order (otherwise dry run)")
    tp.add_argument("--live", action="store_true", help="trade the LIVE account")
    tp.add_argument("--i-understand-live", action="store_true", dest="i_understand_live",
                    help="required acknowledgement to place LIVE orders")
    tp.set_defaults(func=_cmd_trade)

    mp = sub.add_parser("manage",
                        help="trail stops and exit broken trends on open positions")
    mp.add_argument("symbol", nargs="?", default=None,
                    help="manage just this symbol (default: all positions)")
    mp.add_argument("--feed", default="iex", help="Alpaca data feed (default iex)")
    mp.add_argument("--fast-ma", type=int, default=50, dest="fast_ma")
    mp.add_argument("--slow-ma", type=int, default=200, dest="slow_ma")
    mp.add_argument("--breakout-lookback", type=int, default=20, dest="breakout_lookback")
    mp.add_argument("--confirm", action="store_true",
                    help="actually amend/cancel/close orders (otherwise dry run)")
    mp.add_argument("--live", action="store_true", help="manage the LIVE account")
    mp.add_argument("--i-understand-live", action="store_true", dest="i_understand_live",
                    help="required acknowledgement to act on LIVE positions")
    mp.set_defaults(func=_cmd_manage)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
