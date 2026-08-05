"""Portfolio backtester and strategy lab.

Why this exists: :mod:`trendkept.backtest` simulates **one symbol with its own
account**. The thing we actually run is a *portfolio* — one pot of cash across
20 tickers, at most four positions at once, every trade risking ~1% of current
equity, no margin. Testing a variant on a single symbol therefore tells us
very little about the system we own.

This module models the live autopilot's actual shape, then lets us compare
rule variants against it on real data, with an out-of-sample split.

**Speed.** ``confirmed_swings_through`` recomputes every pivot on every call,
which is O(n^2) per symbol and far too slow across 20 tickers and a decade of
bars. :class:`Precomputed` derives the same per-bar signals once. A pivot at
index ``i`` depends only on bars ``i-window .. i+window``, so pivots found over
the whole series, filtered to ``index <= i - window``, are *identical* to those
confirmed as of bar ``i``. ``tests/test_portfolio.py`` asserts bar-for-bar
parity with :class:`~trendkept.strategy.TrendFollowingStrategy`; if the fast
path ever drifts, the suite fails rather than the lab quietly lying.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from . import indicators as ind
from .data import Bar
from .strategy import Signal, StrategyConfig


class Precomputed:
    """Per-bar strategy outputs for one symbol, computed once."""

    def __init__(self, bars: Sequence[Bar], cfg: StrategyConfig) -> None:
        self.bars = bars
        self.cfg = cfg
        n = len(bars)
        closes = [b.close for b in bars]
        fast = ind.sma(closes, cfg.fast_ma)
        slow = ind.sma(closes, cfg.slow_ma)
        self.fast = fast

        swings = ind.swing_points(bars, cfg.swing_window)

        self.uptrend: List[bool] = [False] * n
        self.signal: List[Signal] = [Signal.NONE] * n
        self.stop: List[Optional[float]] = [None] * n
        self.exit: List[bool] = [False] * n

        # Walk forward, advancing a pointer into `swings` as pivots become
        # confirmed. Mirrors confirmed_swings_through(bars, i, window).
        ptr = 0
        highs: List[float] = []
        lows: List[float] = []
        for i in range(n):
            horizon = i - cfg.swing_window
            while ptr < len(swings) and swings[ptr].index <= horizon:
                s = swings[ptr]
                (highs if s.kind == "high" else lows).append(s.price)
                ptr += 1

            b = bars[i]
            f, sl = fast[i], slow[i]

            structure = (len(highs) >= 2 and len(lows) >= 2
                         and highs[-1] > highs[-2] and lows[-1] > lows[-2])
            up = (i >= cfg.slow_ma and f is not None and sl is not None
                  and b.close > f and b.close > sl and f > sl and structure)
            self.uptrend[i] = up

            # Stop: just under the last confirmed swing low, else the window low.
            if lows:
                ref = lows[-1]
            else:
                start = max(0, i - cfg.swing_window)
                ref = min(x.low for x in bars[start:i + 1])
            self.stop[i] = ref * (1.0 - cfg.stop_buffer_pct)

            # Exit: close below the fast MA, or a lower confirmed low.
            self.exit[i] = bool(
                (f is not None and b.close < f)
                or (len(lows) >= 2 and lows[-1] < lows[-2])
            )

            if not up or f is None or f == 0:
                continue
            if (b.close - f) / f > cfg.max_extension_pct:   # never chase
                continue
            if i >= 1 and b.close > bars[i - 1].close and \
                    (b.low - f) / f <= cfg.pullback_pct:
                self.signal[i] = Signal.ENTER_PULLBACK
            elif i >= cfg.breakout_lookback and b.close > max(
                    x.high for x in bars[i - cfg.breakout_lookback:i]):
                self.signal[i] = Signal.ENTER_BREAKOUT


@dataclass
class Variant:
    """A rule variant to test against the baseline."""

    name: str
    # H1 — do not re-enter a symbol for N trading days after it closes.
    cooldown_days: int = 0
    # H2 — require this fraction of the universe to be in a confirmed uptrend
    # before opening anything new. A *fraction*, not a count, so the threshold
    # means the same thing whatever size universe a variant trades. Exits are
    # never gated: a breadth collapse must not trap us in a broken trend.
    min_breadth_pct: float = 0.0
    # H3 — stop distance override, as a fraction below the close.
    stop_pct: Optional[float] = None
    # H4 — trade a different universe. None means "whatever the caller passed".
    universe: Optional[List[str]] = None


@dataclass
class PortfolioTrade:
    symbol: str
    entry_date: str
    entry: float
    shares: int
    # `stop` ratchets up as the trade runs; `initial_stop` never moves.
    # R must be measured against the risk taken *at entry* — dividing by the
    # trailed stop shrinks the denominator on winners (and can flip its sign),
    # which silently corrupts every expectancy figure downstream.
    stop: float
    initial_stop: float = 0.0
    exit_date: Optional[str] = None
    exit: Optional[float] = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.initial_stop:
            self.initial_stop = self.stop

    @property
    def pnl(self) -> float:
        return 0.0 if self.exit is None else (self.exit - self.entry) * self.shares

    @property
    def risk(self) -> float:
        return (self.entry - self.initial_stop) * self.shares

    @property
    def r(self) -> float:
        return 0.0 if self.risk <= 0 else self.pnl / self.risk


@dataclass
class LabResult:
    variant: str
    start: str
    end: str
    starting_equity: float
    ending_equity: float
    trades: List[PortfolioTrade] = field(default_factory=list)
    curve: List[float] = field(default_factory=list)

    @property
    def closed(self) -> List[PortfolioTrade]:
        return [t for t in self.trades if t.exit is not None]

    @property
    def return_pct(self) -> float:
        return (self.ending_equity / self.starting_equity - 1.0) * 100.0

    @property
    def win_rate(self) -> float:
        c = self.closed
        return 0.0 if not c else sum(1 for t in c if t.pnl > 0) / len(c) * 100.0

    @property
    def expectancy_r(self) -> float:
        c = self.closed
        return 0.0 if not c else sum(t.r for t in c) / len(c)

    @property
    def max_dd_pct(self) -> float:
        peak, worst = -math.inf, 0.0
        for v in self.curve:
            peak = max(peak, v)
            if peak > 0:
                worst = min(worst, (v - peak) / peak)
        return worst * 100.0

    @property
    def profit_factor(self) -> float:
        w = sum(t.pnl for t in self.closed if t.pnl > 0)
        l = -sum(t.pnl for t in self.closed if t.pnl < 0)
        return (float("inf") if w > 0 else 0.0) if l == 0 else w / l


class PortfolioBacktester:
    """Simulates the live autopilot: one pot of cash, a position cap, risk
    sizing, stops attached at entry and trailed daily."""

    def __init__(self, cfg: Optional[StrategyConfig] = None,
                 starting_equity: float = 100_000.0, risk_pct: float = 0.01,
                 max_positions: int = 4) -> None:
        self.cfg = cfg or StrategyConfig()
        self.starting_equity = starting_equity
        self.risk_pct = risk_pct
        self.max_positions = max_positions

    def run(self, data: Dict[str, Sequence[Bar]], variant: Variant,
            order: Optional[Sequence[str]] = None,
            date_from: Optional[str] = None,
            date_to: Optional[str] = None) -> LabResult:
        symbols = list(variant.universe or order or sorted(data))
        pre = {s: Precomputed(data[s], self.cfg) for s in symbols if data.get(s)}
        symbols = [s for s in symbols if s in pre]

        # Master timeline + per-symbol lookup from date to that symbol's index.
        at: Dict[str, Dict[str, int]] = {
            s: {b.date: i for i, b in enumerate(data[s])} for s in symbols
        }
        dates = sorted({d for s in symbols for d in at[s]})
        if date_from:
            dates = [d for d in dates if d >= date_from]
        if date_to:
            dates = [d for d in dates if d <= date_to]

        cash = self.starting_equity
        open_pos: Dict[str, PortfolioTrade] = {}
        trades: List[PortfolioTrade] = []
        curve: List[float] = []
        cooldown_until: Dict[str, int] = {}

        for day, date in enumerate(dates):
            # --- 1. manage open positions (stops first, then trend break) ---
            for sym in list(open_pos):
                i = at[sym].get(date)
                if i is None:
                    continue
                bar = data[sym][i]
                t = open_pos[sym]
                if bar.low <= t.stop:
                    # A gap opens below the stop: you fill where the market is.
                    fill = min(t.stop, bar.open)
                    cash += fill * t.shares
                    t.exit, t.exit_date, t.reason = fill, date, "stop"
                    del open_pos[sym]
                    cooldown_until[sym] = day + variant.cooldown_days
                elif pre[sym].exit[i]:
                    cash += bar.close * t.shares
                    t.exit, t.exit_date, t.reason = bar.close, date, "trend_break"
                    del open_pos[sym]
                    cooldown_until[sym] = day + variant.cooldown_days
                else:
                    if variant.stop_pct is not None:
                        cand = bar.close * (1.0 - variant.stop_pct)
                    else:
                        cand = pre[sym].stop[i] or t.stop
                    t.stop = max(t.stop, cand)  # ratchet only

            # --- 2. breadth gate (H2) ---
            live_syms = [s for s in symbols if date in at[s]]
            if variant.min_breadth_pct > 0 and live_syms:
                breadth = sum(1 for s in live_syms if pre[s].uptrend[at[s][date]])
                may_enter = breadth / len(live_syms) >= variant.min_breadth_pct
            else:
                may_enter = True

            # --- 3. new entries, in the live scan order ---
            if may_enter:
                for sym in symbols:
                    if len(open_pos) >= self.max_positions:
                        break
                    if sym in open_pos or day < cooldown_until.get(sym, -1):
                        continue
                    i = at[sym].get(date)
                    if i is None:
                        continue
                    if pre[sym].signal[i] is Signal.NONE:
                        continue
                    bar = data[sym][i]
                    entry = bar.close
                    stop = (entry * (1.0 - variant.stop_pct)
                            if variant.stop_pct is not None else pre[sym].stop[i])
                    if stop is None or stop >= entry:
                        continue
                    equity = cash + sum(
                        p.shares * data[s][at[s][date]].close
                        for s, p in open_pos.items() if date in at[s])
                    shares = math.floor((equity * self.risk_pct) / (entry - stop))
                    shares = min(shares, math.floor(cash / entry))  # no margin
                    if shares <= 0:
                        continue
                    cash -= entry * shares
                    t = PortfolioTrade(sym, date, entry, shares, stop,
                                       initial_stop=stop)
                    open_pos[sym] = t
                    trades.append(t)

            held = sum(p.shares * data[s][at[s][date]].close
                       for s, p in open_pos.items() if date in at[s])
            curve.append(cash + held)

        return LabResult(
            variant=variant.name,
            start=dates[0] if dates else "",
            end=dates[-1] if dates else "",
            starting_equity=self.starting_equity,
            ending_equity=curve[-1] if curve else self.starting_equity,
            trades=trades, curve=curve,
        )


# --- universes -------------------------------------------------------------
#
# The live board is 20 US equities — but 13 of them are US mega-cap tech or
# indices dominated by it, so it behaves like roughly one bet. When tech falls
# the whole board falls together, which is exactly what "0 of 20 in an
# uptrend" has meant these past weeks.
#
# Trend-following's historical edge leans heavily on *diversification across
# uncorrelated markets* — something is usually trending somewhere. The
# extended universe below adds bonds, gold and commodities, energy, currencies,
# international equities and the US sectors, all as liquid ETFs. H4 tests
# whether that actually helps, rather than assuming it.

DIVERSIFIERS: List[str] = [
    # bonds / rates
    "TLT", "IEF", "SHY", "LQD", "HYG", "TIP",
    # metals & commodities
    "GLD", "SLV", "GDX", "DBC", "USO", "UNG",
    # international equity
    "EFA", "EEM", "VGK", "EWJ", "FXI", "EWZ",
    # US sectors
    "XLE", "XLF", "XLV", "XLU", "XLP", "XLI", "XLK", "XLB", "XLY", "XLRE",
    # real assets & currency
    "VNQ", "UUP",
]

CORE_20: List[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "JPM", "V", "UNH", "XOM", "COST", "PG", "HD", "NFLX", "AMD",
    "SPY", "QQQ", "IWM",
]

EXTENDED: List[str] = CORE_20 + DIVERSIFIERS

# The hypotheses, each traceable to something we observed live (see
# business/REVIEW_PROTOCOL.md).
VARIANTS: List[Variant] = [
    Variant("baseline"),
    Variant("H1 cooldown 5d", cooldown_days=5),
    Variant("H1 cooldown 10d", cooldown_days=10),
    Variant("H2 breadth >=15%", min_breadth_pct=0.15),
    Variant("H2 breadth >=25%", min_breadth_pct=0.25),
    Variant("H2 breadth >=40%", min_breadth_pct=0.40),
    Variant("H1+H2 (5d, 25%)", cooldown_days=5, min_breadth_pct=0.25),
    Variant("H3 stop 8%", stop_pct=0.08),
    Variant("H3 stop 12%", stop_pct=0.12),
    Variant("H4 diversified", universe=EXTENDED),
    Variant("H4 diversifiers only", universe=DIVERSIFIERS),
    Variant("H4 + cooldown 5d", universe=EXTENDED, cooldown_days=5),
    Variant("H4 + breadth 25%", universe=EXTENDED, min_breadth_pct=0.25),
]


def split_date(data: Dict[str, Sequence[Bar]], fraction: float = 0.7) -> str:
    """Date splitting the timeline: tune before it, validate after."""
    dates = sorted({b.date for bars in data.values() for b in bars})
    if not dates:
        return ""
    return dates[int(len(dates) * fraction)]
