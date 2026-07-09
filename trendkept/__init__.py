"""Trendkept — a disciplined trend-following toolkit.

Trendkept encodes one strategy and nothing else: ride confirmed uptrends, cut
losers fast and small, let winners run. The whole package is pure standard
library so it runs anywhere Python 3.9+ does, with no pip install.

Modules:
    indicators  Simple moving averages and causal swing-point detection.
    data        OHLC bar type and a CSV loader.
    strategy    The trend-following rules expressed as signals.
    backtest    A bar-by-bar simulator with position sizing and trailing stops.
    cli         Command line entry points: ``backtest`` and ``scan``.
"""

from .strategy import StrategyConfig, TrendFollowingStrategy
from .backtest import Backtester, BacktestResult
from .data import Bar, load_csv

__all__ = [
    "StrategyConfig",
    "TrendFollowingStrategy",
    "Backtester",
    "BacktestResult",
    "Bar",
    "load_csv",
]

__version__ = "0.1.0"
