"""Fetch real daily price history — standard library only, no API key.

Two free providers, tried in order by ``provider="auto"``:

* **Stooq** (``stooq.com``) — returns a clean adjusted-OHLC CSV. Primary.
* **Yahoo Finance** chart API — returns JSON we normalize to the same CSV
  shape (including an ``Adj Close`` column). Fallback.

Both are best-effort public endpoints. They can rate-limit or change; that is
exactly why the rest of Trendrail works fine on a plain CSV you saved yourself.
Network calls live *only* here, isolated from the strategy and backtester.

Note: this sandbox restricts outbound network, so these functions are exercised
against canned provider payloads in the test suite. On your own machine they hit
the live endpoints.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import List

from .data import Bar, parse_csv_text

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class FetchError(RuntimeError):
    """Raised when a provider returns no usable data."""


def _http_get(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        raise FetchError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network path
        raise FetchError(f"network error for {url}: {exc.reason}") from exc


def _stooq_symbol(symbol: str) -> str:
    """Stooq wants an exchange suffix; default bare tickers to US equities.

    Index symbols (``^spx``) and anything already carrying a market suffix
    (``vod.uk``) are left untouched.
    """
    s = symbol.strip().lower()
    if "." in s or s.startswith("^"):
        return s
    return f"{s}.us"


def stooq_csv(symbol: str, timeout: float = 30.0) -> str:
    """Raw daily CSV text from Stooq (``Date,Open,High,Low,Close,Volume``)."""
    url = f"https://stooq.com/q/d/l/?s={_stooq_symbol(symbol)}&i=d"
    text = _http_get(url, timeout)
    head = text.strip().lower()
    if not head or head.startswith("n/d") or "date" not in head.splitlines()[0]:
        raise FetchError(f"Stooq returned no data for {symbol!r} (got: {text[:60]!r})")
    return text


def yahoo_to_csv(payload: str, symbol: str = "", intraday: bool = False) -> str:
    """Convert a Yahoo v8 chart JSON payload to OHLC CSV text.

    Split out from the HTTP call so it can be unit-tested with a canned
    payload. Intraday bars keep time-of-day in the date column so several
    bars per day stay distinct and ordered.
    """
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

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    if not timestamps:
        raise FetchError(f"Yahoo returned no timestamps for {symbol!r}")

    lines = ["Date,Open,High,Low,Close,Adj Close,Volume"]
    for i, ts in enumerate(timestamps):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        # Yahoo emits null for holidays/halts; skip incomplete bars.
        if None in (o, h, l, c):
            continue
        adj = adjclose[i] if adjclose and adjclose[i] is not None else c
        vol = volumes[i] if i < len(volumes) and volumes[i] is not None else ""
        fmt = "%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(fmt)
        lines.append(f"{date},{o},{h},{l},{c},{adj},{vol}")

    if len(lines) == 1:
        raise FetchError(f"Yahoo returned no usable bars for {symbol!r}")
    return "\n".join(lines) + "\n"


# Yahoo's history depth per intraday interval (their hard limits, roughly).
_YAHOO_INTRADAY_RANGE = {"1m": "5d", "5m": "1mo", "30m": "1mo", "60m": "6mo"}


def yahoo_csv(symbol: str, range_: str = "5y", interval: str = "1d",
              timeout: float = 30.0) -> str:
    """Raw CSV text from Yahoo's chart API (daily or intraday bars)."""
    intraday = interval != "1d"
    if intraday:
        range_ = _YAHOO_INTRADAY_RANGE.get(interval, "1mo")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range={range_}&interval={interval}&events=div%2Csplit"
    )
    return yahoo_to_csv(_http_get(url, timeout), symbol, intraday=intraday)


def fetch_csv(symbol: str, provider: str = "auto", *, range_: str = "5y",
              timeout: float = 30.0, interval: str = "1d") -> str:
    """Return raw CSV text for ``symbol`` from the chosen provider.

    ``provider`` is ``"auto"`` (Stooq then Yahoo), ``"stooq"``, or ``"yahoo"``.
    ``interval`` supports Yahoo's intraday bar sizes (``1m``/``5m``/``30m``/
    ``60m``); Stooq is daily-only, so intraday requests go straight to Yahoo.
    """
    provider = provider.lower()
    if interval != "1d" and provider in ("auto", "yahoo"):
        return yahoo_csv(symbol, range_=range_, interval=interval,
                         timeout=timeout)
    if interval != "1d":
        raise ValueError("intraday bars are only available from yahoo/auto "
                         "(or Alpaca via the dashboard)")
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
            except FetchError as exc:  # pragma: no cover - network path
                errors.append(f"{name}: {exc}")
        raise FetchError(f"all providers failed for {symbol!r}: " + " | ".join(errors))
    raise ValueError(f"unknown provider {provider!r}; use auto, stooq, or yahoo")


def fetch_bars(symbol: str, provider: str = "auto", *, range_: str = "5y",
               timeout: float = 30.0, adjust: bool = True) -> List[Bar]:
    """Fetch ``symbol`` and parse it into adjustment-aware :class:`Bar` objects."""
    return parse_csv_text(fetch_csv(symbol, provider, range_=range_,
                                    timeout=timeout), adjust=adjust)
