"""Alpaca Markets connectivity — historical data and order placement.

Standard library only (``urllib`` + ``json``); no SDK to install. One client
talks to two Alpaca hosts:

* **Market data** (``data.alpaca.markets``) — split/dividend-adjusted daily bars
  that drop straight into the strategy and backtester.
* **Trading** (``paper-api`` / ``api`` ``.alpaca.markets``) — account, positions,
  and orders. Entries are submitted as an *OTO* (one-triggers-other) order so a
  protective stop-loss is attached the instant the position opens — rule #3,
  enforced by the broker.

Safety, by construction:

* Credentials come from the environment (``APCA_API_KEY_ID`` /
  ``APCA_API_SECRET_KEY``); they are never hard-coded or logged.
* ``paper=True`` by default — orders hit the paper endpoint unless you opt in.
* The high-level :func:`plan_trade` returns an *intent*; nothing is sent until
  you explicitly submit it. The CLI defaults to a dry run.

Get free API keys at https://alpaca.markets (a paper account is free). Then:

    export APCA_API_KEY_ID=...      # "Paper" keys from the dashboard
    export APCA_API_SECRET_KEY=...
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .data import Bar

DATA_HOST = "https://data.alpaca.markets"
PAPER_HOST = "https://paper-api.alpaca.markets"
LIVE_HOST = "https://api.alpaca.markets"


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
        return (
            f"{self.signal.upper()} {self.symbol}: buy {self.quantity} @ "
            f"~{self.entry_price:.2f}, stop {self.stop_price:.2f} "
            f"(risk {self.risk_per_share:.2f}/sh, total {self.dollar_risk:.2f} "
            f"= {self.dollar_risk / self.account_equity * 100:.2f}% of "
            f"{self.account_equity:,.2f})"
        )


class AlpacaClient:
    def __init__(
        self,
        key_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
        feed: str = "iex",
        timeout: float = 30.0,
    ) -> None:
        self.key_id = key_id or os.environ.get("APCA_API_KEY_ID")
        self.secret_key = secret_key or os.environ.get("APCA_API_SECRET_KEY")
        if not self.key_id or not self.secret_key:
            raise AlpacaError(
                "missing credentials: set APCA_API_KEY_ID and "
                "APCA_API_SECRET_KEY (use your Alpaca *paper* keys to start)"
            )
        self.paper = paper
        self.feed = feed
        self.timeout = timeout
        self.trading_host = PAPER_HOST if paper else LIVE_HOST

    # --- transport --------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, url: str, body: Optional[dict] = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, headers=self._headers(), method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:  # pragma: no cover - network path
            detail = exc.read().decode("utf-8", errors="replace")
            raise AlpacaError(f"HTTP {exc.code} {method} {url}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network path
            raise AlpacaError(f"network error {method} {url}: {exc.reason}") from exc
        return json.loads(raw) if raw.strip() else {}

    # --- market data ------------------------------------------------------

    @staticmethod
    def _bars_from_payload(payload: dict, intraday: bool = False) -> List[Bar]:
        """Convert an Alpaca bars payload into :class:`Bar` objects.

        Pure/static so it can be unit-tested without a network call. Intraday
        bars keep their time-of-day in the date string so multiple bars per
        day stay distinct (and ordered — the strategy only needs ordering).
        """
        out: List[Bar] = []
        for b in payload.get("bars") or []:
            if intraday:  # "2023-01-03T14:30:00Z" -> "2023-01-03 14:30"
                date = b["t"].replace("T", " ")[:16]
            else:
                date = b["t"].split("T")[0]  # RFC3339 -> YYYY-MM-DD
            o, h, l, c = float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"])
            hi, lo = max(h, o, c), min(l, o, c)  # guard feed rounding
            out.append(Bar(date, o, hi, lo, c, volume=float(b.get("v", 0)) or None))
        return out

    def daily_bars(
        self,
        symbol: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        adjustment: str = "all",
        max_bars: int = 5000,
        timeframe: str = "1Day",
    ) -> List[Bar]:
        """Adjusted bars for ``symbol``, oldest-first (daily by default).

        ``start``/``end`` are ``YYYY-MM-DD``; the default start scales with
        the bar size — ~5 years of daily bars, ~30 days of minute bars —
        enough history to warm up the averages without pulling a firehose.
        ``timeframe`` is Alpaca's notation: 1Min, 5Min, 30Min, 1Hour, 4Hour,
        1Day. ``adjustment`` ``"all"`` applies splits and dividends.
        """
        intraday = timeframe in ("1Min", "5Min", "15Min", "30Min",
                                 "1Hour", "4Hour")
        if start is None:
            days = {"1Min": 30, "5Min": 90, "30Min": 365,
                    "1Hour": 730, "4Hour": 730,
                    "1Week": 12 * 365, "1Month": 20 * 365}.get(
                        timeframe, 10 * 365)
            start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
                "%Y-%m-%d"
            )
        bars: List[Bar] = []
        page_token: Optional[str] = None
        while True:
            params = {
                "timeframe": timeframe,
                "start": start,
                "adjustment": adjustment,
                "feed": self.feed,
                "limit": 10000,
            }
            if end:
                params["end"] = end
            if page_token:
                params["page_token"] = page_token
            url = (
                f"{DATA_HOST}/v2/stocks/{urllib.parse.quote(symbol)}/bars?"
                + urllib.parse.urlencode(params)
            )
            payload = self._request("GET", url)
            bars.extend(self._bars_from_payload(payload, intraday=intraday))
            page_token = payload.get("next_page_token")
            if not page_token or len(bars) >= max_bars:
                break
        if not bars:
            raise AlpacaError(
                f"no bars returned for {symbol!r}; check the symbol and that your "
                f"plan permits the {self.feed!r} feed"
            )
        bars.sort(key=lambda x: x.date)
        return bars

    def crypto_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: Optional[str] = None,
        max_bars: int = 5000,
    ) -> List[Bar]:
        """Bars for a crypto pair like ``BTC/USD`` — Alpaca's crypto data
        endpoint (24/7 market; no feed or adjustment parameters). The
        payload keys bars by symbol, hence the reshaping before parsing."""
        intraday = timeframe in ("1Min", "5Min", "15Min", "30Min",
                                 "1Hour", "4Hour")
        if start is None:
            days = {"1Min": 30, "5Min": 90, "30Min": 365,
                    "1Hour": 730, "4Hour": 730,
                    "1Week": 12 * 365, "1Month": 20 * 365}.get(
                        timeframe, 10 * 365)
            start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
                "%Y-%m-%d"
            )
        bars: List[Bar] = []
        page_token: Optional[str] = None
        while True:
            params = {
                "symbols": symbol,
                "timeframe": timeframe,
                "start": start,
                "limit": 10000,
            }
            if page_token:
                params["page_token"] = page_token
            url = (f"{DATA_HOST}/v1beta3/crypto/us/bars?"
                   + urllib.parse.urlencode(params))
            payload = self._request("GET", url)
            per_symbol = (payload.get("bars") or {}).get(symbol) or []
            bars.extend(self._bars_from_payload({"bars": per_symbol},
                                                intraday=intraday))
            page_token = payload.get("next_page_token")
            if not page_token or len(bars) >= max_bars:
                break
        if not bars:
            raise AlpacaError(f"no crypto bars returned for {symbol!r}")
        bars.sort(key=lambda x: x.date)
        return bars

    # --- account & positions ---------------------------------------------

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
                "GET", f"{self.trading_host}/v2/positions/"
                f"{urllib.parse.quote(symbol)}"
            )
        except AlpacaError:
            return None  # 404 => no open position

    # --- orders -----------------------------------------------------------

    def submit_entry_with_stop(
        self,
        symbol: str,
        qty: int,
        stop_price: float,
        limit_price: Optional[float] = None,
        tif: str = "day",
    ) -> dict:
        """Buy ``qty`` shares with a protective stop attached (OTO order).

        ``limit_price`` makes the entry a limit order (recommended — avoids
        chasing a gap); omit for a market entry.
        """
        order: Dict[str, object] = {
            "symbol": symbol,
            "qty": str(qty),
            "side": "buy",
            "time_in_force": tif,
            "order_class": "oto",
            "stop_loss": {"stop_price": f"{stop_price:.2f}"},
        }
        if limit_price is not None:
            order["type"] = "limit"
            order["limit_price"] = f"{limit_price:.2f}"
        else:
            order["type"] = "market"
        return self._request("POST", f"{self.trading_host}/v2/orders", body=order)

    def submit_stop_sell(
        self, symbol: str, qty, stop_price: float, tif: str = "gtc"
    ) -> dict:
        """Place a standalone protective sell-stop (good-till-cancelled).

        Used when an open position has somehow lost its protective stop.
        """
        order = {
            "symbol": symbol,
            "qty": str(qty),
            "side": "sell",
            "type": "stop",
            "time_in_force": tif,
            "stop_price": f"{stop_price:.2f}",
        }
        return self._request("POST", f"{self.trading_host}/v2/orders", body=order)

    def list_orders(self, status: str = "open") -> List[dict]:
        url = f"{self.trading_host}/v2/orders?status={status}&limit=100"
        result = self._request("GET", url)
        return result if isinstance(result, list) else []

    def replace_order(self, order_id: str, stop_price: float) -> dict:
        """Raise a protective stop (trailing) by replacing the order."""
        return self._request(
            "PATCH",
            f"{self.trading_host}/v2/orders/{order_id}",
            body={"stop_price": f"{stop_price:.2f}"},
        )

    def cancel_order(self, order_id: str) -> dict:
        return self._request(
            "DELETE", f"{self.trading_host}/v2/orders/{order_id}"
        )

    def close_position(self, symbol: str) -> dict:
        """Liquidate the whole position in ``symbol`` at market."""
        return self._request(
            "DELETE",
            f"{self.trading_host}/v2/positions/{urllib.parse.quote(symbol)}",
        )

    def find_stop_order(self, symbol: str) -> Optional[dict]:
        """The open protective sell-stop for ``symbol``, if one exists.

        Searches top-level orders and the ``legs`` of bracket/OTO parents,
        because the stop appears nested until the entry fills.
        """
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


def plan_trade(
    client: AlpacaClient,
    strategy,
    symbol: str,
    bars: List[Bar],
    risk_pct: float,
) -> Optional[TradePlan]:
    """Turn the latest-bar signal into a sized, stop-protected intent.

    Returns ``None`` when the rules say "no entry today". Sizing uses live
    account equity so risk is a true percentage of the real account.
    """
    from .strategy import Signal

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
    dollar_risk = equity * risk_pct
    qty = int(dollar_risk // risk_per_share)
    # Never exceed cash on hand.
    qty = min(qty, int(equity // entry))
    if qty <= 0:
        return None

    return TradePlan(
        symbol=symbol.upper(),
        signal=signal.value,
        quantity=qty,
        entry_price=entry,
        stop_price=stop,
        risk_per_share=risk_per_share,
        dollar_risk=qty * risk_per_share,
        account_equity=equity,
    )


@dataclass
class ManagementAction:
    """What to do with an open position on the latest bar.

    ``kind`` is ``"exit"``, ``"raise_stop"``, ``"set_stop"`` (no protective stop
    was found — install one), or ``"hold"``.
    """

    kind: str
    reason: str
    symbol: str = ""
    new_stop: Optional[float] = None
    current_stop: Optional[float] = None

    def describe(self) -> str:
        if self.kind == "exit":
            return f"EXIT {self.symbol}: {self.reason}"
        if self.kind == "raise_stop":
            return (f"RAISE STOP {self.symbol}: "
                    f"{self.current_stop:.2f} -> {self.new_stop:.2f} "
                    f"({self.reason})")
        if self.kind == "set_stop":
            return f"SET STOP {self.symbol}: {self.new_stop:.2f} ({self.reason})"
        cur = f" (stop {self.current_stop:.2f})" if self.current_stop else ""
        return f"HOLD {self.symbol}: {self.reason}{cur}"


def decide_management(
    strategy,
    bars: List[Bar],
    current_stop: Optional[float],
    symbol: str = "",
) -> ManagementAction:
    """Decide how to manage an open long, using only the latest confirmed bar.

    Trend-break exit takes priority; otherwise the stop only ever ratchets up.
    Pure and side-effect-free so it can be tested without touching the broker.
    """
    i = len(bars) - 1

    if strategy.exit_on_trend_break(bars, i):
        return ManagementAction(
            "exit", "trend break: close below 50-day MA or a lower low",
            symbol=symbol, current_stop=current_stop,
        )

    candidate = strategy.initial_stop(bars, i)  # stop under latest swing low

    if current_stop is None:
        return ManagementAction(
            "set_stop", "no protective stop found; installing one",
            symbol=symbol, new_stop=candidate,
        )

    new_stop = strategy.trail_stop(bars, i, current_stop)
    # Stops are submitted to the broker rounded to the penny, so a raise of
    # less than a cent is a no-op — and Alpaca rejects a replace that leaves
    # the price unchanged (HTTP 422). Only act on a full-penny improvement.
    if new_stop - current_stop >= 0.01 - 1e-9:
        return ManagementAction(
            "raise_stop", "higher swing low formed",
            symbol=symbol, new_stop=new_stop, current_stop=current_stop,
        )

    return ManagementAction(
        "hold", "trend intact, stop unchanged",
        symbol=symbol, current_stop=current_stop,
    )
