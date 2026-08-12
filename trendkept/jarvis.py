"""Jarvis — Trendkept's plain-English assistant.

Ask it things the way you'd ask a person ("how's AAPL looking?", "what are
my rules?", "will bitcoin go up?") and it answers from the same engine the
dashboard and CLI use. It is named after the butler, and it behaves like
one: it fetches, reads, and reports — it never freelances.

What Jarvis is, honestly:

* **Deterministic keyword matching**, like the Trading Diagram interpreter —
  not a cloud AI, not mind-reading. Every answer is computed locally from
  your data and your ruleset. Nothing you type leaves your machine.
* **A reporter, not an adviser.** It describes what the written rules read
  on today's bar — "trend filter met", "no entry today" — and never tells
  anyone to buy or sell anything.
* **Allergic to prediction.** Ask it where a price is going and it will
  tell you the truth: nobody knows, and Trendkept doesn't guess. That
  refusal is the product working, not a missing feature.

The module is pure: ``ask()`` takes the question plus injected callables
for anything that touches the outside world (fetching bars, reading the
paper log), so tests can drive it entirely offline.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from .data import Bar
from .strategy import Signal, StrategyConfig, TrendFollowingStrategy

# fetch(item) -> (bars, label). Injected so the brain stays offline-pure;
# the dashboard and CLI pass their own loaders (live symbols + CSV paths).
Fetcher = Callable[[str], Tuple[List[Bar], str]]


@dataclass
class Answer:
    """One reply: plain text (the CLI prints it verbatim; the web page
    escapes it), plus a kind so callers can style refusals differently."""

    text: str
    kind: str = "info"  # info | scan | refusal | help | error
    # Optional dashboard follow-ups: (href, label) pairs.
    links: List[Tuple[str, str]] = field(default_factory=list)


# --- symbol spotting --------------------------------------------------------

# Company/asset names people say instead of tickers. Small and boring on
# purpose — anything not listed is simply treated as a ticker attempt, and
# a wrong ticker fails loudly at fetch time rather than being guessed at.
_NAMES = {
    "apple": "AAPL", "microsoft": "MSFT", "tesla": "TSLA", "nvidia": "NVDA",
    "amazon": "AMZN", "google": "GOOGL", "alphabet": "GOOGL", "meta": "META",
    "facebook": "META", "netflix": "NFLX", "amd": "AMD", "intel": "INTC",
    "bitcoin": "BTC/USD", "ethereum": "ETH/USD", "solana": "SOL/USD",
    "gold": "GC=F", "silver": "SI=F", "oil": "CL=F", "crude": "CL=F",
    "sp500": "SPX", "s&p": "SPX", "s&p500": "SPX", "spx": "SPX",
    "nasdaq": "NDX", "dow": "DJI", "ftse": "FTSE", "dax": "DAX",
    "nikkei": "NIKKEI", "vix": "VIX", "russell": "RUSSELL",
}

# English words that would otherwise look like 1-5 letter tickers. If a
# real ticker collides with one of these (there is an actual ticker "A"),
# typing it in UPPERCASE always wins.
_STOPWORDS = {
    "a", "about", "again", "an", "and", "any", "are", "as", "at", "am",
    "back", "bad", "be", "been", "big", "bit", "but",
    "buy", "can", "chart", "cheers", "check", "close", "could", "day",
    "days", "do", "does", "doing", "done", "down", "end", "entry", "even",
    "ever", "exit", "feel", "for", "from", "get",
    "give", "go", "going", "gone", "good", "great", "has", "have", "hello",
    "here", "hey", "hi", "hold", "how", "i", "if", "in", "into", "is",
    "it", "its", "jarvis", "just", "keep", "last", "like", "long", "look",
    "looks", "lot", "make", "market", "mate", "moon", "more", "most",
    "much",
    "me", "morning", "my", "need", "new", "next", "no", "not", "now", "of",
    "off", "on", "one", "or", "our", "out", "over", "paper", "phase",
    "ok", "okay", "only", "please", "price", "read", "right", "risk",
    "rules", "run", "scan",
    "sell", "set", "share", "shares", "short", "should", "show", "since",
    "so", "some", "soon", "still", "stock", "stocks", "stop", "sure",
    "take", "tell", "test", "than", "thank", "thanks",
    "that", "the", "them", "then", "there", "think", "this", "till", "time",
    "to", "today", "trade", "trades", "trend", "up", "us", "very", "was",
    "we", "week", "well", "what", "when", "where", "which", "who", "why",
    "will", "with", "would", "wrong", "yes", "yet", "you", "your",
}

_SYMBOLISH = re.compile(r"^[A-Za-z^][A-Za-z0-9.^=/-]{0,11}$")


def extract_symbols(question: str) -> List[str]:
    """Pull the tradeable things out of a question, in order, de-duplicated.

    Recognises tickers (AAPL), pairs (BTC/USD, EURUSD), futures (ES=F),
    indices (^FTSE, SPX), CSV paths, and a short list of household names
    ("apple", "bitcoin"). Everything ambiguous errs toward "not a symbol" —
    except when typed in UPPERCASE, which always reads as a ticker.
    """
    found: List[str] = []
    for raw in re.split(r"[\s,;?!()]+", question):
        token = raw.strip(".").strip("'\"")
        if not token:
            continue
        if token.lower().endswith(".csv"):
            found.append(raw.strip("'\""))
            continue
        lower = token.lower()
        if lower in _NAMES:
            found.append(_NAMES[lower])
            continue
        if not _SYMBOLISH.match(token):
            continue
        # Structured notations are unambiguous whatever the case.
        if any(ch in token for ch in "^=/") or "-" in token:
            found.append(token.upper())
            continue
        if lower in _STOPWORDS and not token.isupper():
            continue
        if token.isupper() or (token.isalpha() and len(token) <= 5):
            found.append(token.upper())
    seen = set()
    return [s for s in found if not (s in seen or seen.add(s))]


# --- the scan read, spoken --------------------------------------------------

def _read_symbol(item: str, cfg: StrategyConfig, account: float, risk: float,
                 fetch: Fetcher) -> str:
    """One symbol's descriptive read: what the written rules see on the
    latest bar. Descriptive on purpose — it reports the ruleset's state,
    it does not tell anyone to do anything."""
    try:
        bars, label = fetch(item)
    except Exception as exc:
        # Provider errors can run to several URLs; a chat bubble needs the
        # gist, not the transcript.
        msg = str(exc) or exc.__class__.__name__
        if len(msg) > 160:
            msg = msg[:157] + "..."
        return f"{item}: couldn't load it — {msg}"

    if len(bars) < cfg.slow_ma + 1:
        return (f"{label}: only {len(bars)} bars of history — the "
                f"{cfg.slow_ma}-bar average needs {cfg.slow_ma + 1} to "
                "confirm a trend, so the rules can't read this one yet.")

    strat = TrendFollowingStrategy(cfg)
    i = len(bars) - 1
    bar = bars[i]
    uptrend = strat.is_uptrend(bars, i)
    signal = strat.entry_signal(bars, i)
    stop = strat.initial_stop(bars, i)

    head = f"{label} — as of {bar.date}, close {bar.close:,.2f}."
    if signal in (Signal.ENTER_PULLBACK, Signal.ENTER_BREAKOUT) and stop:
        flavour = ("a pullback that resumed the trend"
                   if signal is Signal.ENTER_PULLBACK
                   else "a breakout above recent highs")
        per_share = bar.close - stop
        shares = int(account * risk // per_share) if per_share > 0 else 0
        sizing = (f"sized by the ruleset that's {shares} shares, risking "
                  f"{account * risk:,.2f} ({risk * 100:.1f}% of "
                  f"{account:,.2f})")
        if shares == 0:
            sizing = (f"at {risk * 100:.1f}% of {account:,.2f} the stop is "
                      "too wide to size a single share — the ruleset would "
                      "sit this one out")
        return (f"{head} Confirmed uptrend: YES. Today's bar qualifies as "
                f"an entry under the written rules — {flavour} — with the "
                f"initial stop at {stop:,.2f} ({per_share:,.2f}/share of "
                f"risk); {sizing}. That's the ruleset's reading, not an "
                "instruction.")
    if uptrend:
        return (f"{head} Confirmed uptrend: YES, but no entry today — no "
                "qualifying pullback or breakout (or price is too extended "
                "to chase). Under the rules, a day like this is a waiting "
                "day.")
    return (f"{head} Confirmed uptrend: no — the trend filter isn't met, "
            "so the rules read this as stay-out. Most days, on most "
            "symbols, this is the answer; that's the discipline.")


# --- intents ----------------------------------------------------------------

_PREDICT_WORDS = ("will ", "predict", "forecast", "price target", "gonna",
                  "going to go", "going up", "going down", "where is it going",
                  "headed", "next week", "next month", "moon", "crash",
                  "how high", "how low", "future")
_ADVICE_WORDS = ("should i buy", "should i sell", "should i get in",
                 "should i get out", "worth buying", "worth selling",
                 "do i buy", "do i sell", "tell me to buy", "good buy",
                 "good investment")
_RULES_WORDS = ("what are the rules", "what are my rules", "my rules",
                "the rules", "my ruleset", "ruleset", "my diagram",
                "trading diagram", "when do we exit", "when do i exit",
                "exit rule", "stop rule", "what's the stop", "whats the stop",
                "entry rule", "how do you decide", "how does it decide",
                "explain the")
_JOURNAL_WORDS = ("journal", "how am i doing", "my trades", "win rate",
                  "expectancy", "r-multiple", "r multiple", "performance")
_LOG_WORDS = ("paper log", "paper trading", "paper-trading", "day 30",
              "validation", "how many days", "the log")
_HELP_WORDS = ("help", "what can you do", "what do you do", "commands",
               "how do i use")
_IDENTITY_WORDS = ("who are you", "what are you", "are you an ai",
                   "are you chatgpt", "are you real")
_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|yo|good (morning|afternoon|evening)|morning)"
    r"[\s,!.]*(jarvis)?[\s!.]*$", re.IGNORECASE)

_SCAN_HINTS = ("check", "scan", "how is", "how's", "hows ", "look at",
               "status", "what about", "read on", "looking", "update on",
               "brief", "uptrend", "watchlist", "run ")


def _rules_text(cfg: StrategyConfig, account: float, risk: float) -> str:
    return (
        "Your ruleset, as currently dialled in:\n"
        f"1. Trend filter — only trade a confirmed uptrend: close above "
        f"both the {cfg.fast_ma}- and {cfg.slow_ma}-bar averages, the "
        f"faster one above the slower, and price making higher highs and "
        f"higher lows.\n"
        f"2. Entries — a pullback to within {cfg.pullback_pct * 100:g}% of "
        f"the {cfg.fast_ma}-bar average that closes back up, or a breakout "
        f"above the prior {cfg.breakout_lookback}-bar high. Never chase: "
        f"no entries more than {cfg.max_extension_pct * 100:g}% above the "
        f"{cfg.fast_ma}-bar average.\n"
        f"3. Stops — in with the order, just below the latest confirmed "
        f"swing low (buffer {cfg.stop_buffer_pct * 100:g}%), and they only "
        f"ever move up.\n"
        f"4. Sizing — risk {risk * 100:g}% of {account:,.2f} per trade, "
        f"never more.\n"
        f"5. Exit — when the trend breaks: a close below the "
        f"{cfg.fast_ma}-bar average, or a lower low.\n"
        "Change any of this on the My Trading Diagram page — scans, charts "
        "and backtests all follow it."
    )


def _paper_log_summary(path: str) -> str:
    try:
        with open(path, newline="") as fh:
            rows = list(csv.reader(fh))
    except OSError:
        return ("I can't see the paper log from here (business/"
                "paper_log.csv). It lives in the repository — the "
                "day-30 review reads it there.")
    body = [r for r in rows[1:] if len(r) >= 10 and r[0].strip()]
    if not body:
        return "The paper log exists but has no rows yet."
    days = len(body)
    followed = sum(1 for r in body if r[9].strip().upper().startswith("Y"))
    traded = sum(1 for r in body
                 if r[2].strip().lower() not in ("", "none", "no trade")
                 and "none" not in r[2].lower())
    last = body[-1][0]
    return (f"The paper log has {days} trading day"
            f"{'s' if days != 1 else ''} recorded, up to {last}. "
            f"Rules followed on {followed} of {days} days; "
            f"{traded} day{'s' if traded != 1 else ''} involved an action "
            "(entry, exit, or a stop moved). The whole point of the log is "
            "that it's evidence, not memory — every row is a day that "
            "actually happened.")


_CAPABILITIES = (
    "Things you can ask me:\n"
    "- \"How's AAPL looking?\" / \"Check bitcoin and gold\" — I run your "
    "ruleset over the latest data and report what the rules read: trend "
    "confirmed or not, entry or not, where the stop would sit, and the "
    "position size your risk setting implies.\n"
    "- \"What are my rules?\" — I read your Trading Diagram back to you "
    "in plain English, with your actual numbers.\n"
    "- \"How's the paper log?\" — a summary of the paper-trading "
    "evidence file.\n"
    "- \"How am I doing?\" — I'll point you at the trade journal, which "
    "scores your completed trades in R-multiples.\n"
    "What I will never do: predict prices, or tell you to buy or sell "
    "anything. I report what your written rules say — the discipline is "
    "the product."
)


def ask(question: str, *, cfg: Optional[StrategyConfig] = None,
        account: float = 1000.0, risk: float = 0.01,
        fetch: Optional[Fetcher] = None,
        paper_log_path: str = "business/paper_log.csv") -> Answer:
    """Answer one plain-English question. Pure routing + the engine."""
    cfg = cfg or StrategyConfig()
    q = " ".join(question.split()).lower()

    if not q or _GREETING_RE.match(question):
        return Answer(
            "At your service. I'm Jarvis — Trendkept's assistant. I can "
            "read any symbol against your ruleset, recite your rules, and "
            "summarise the paper log. What I never do is predict or "
            "advise — I report what the written rules say.\n\n"
            + _CAPABILITIES, kind="help",
            links=[("/ruleset", "My Trading Diagram")])

    if any(w in q for w in _IDENTITY_WORDS):
        return Answer(
            "Honestly? I'm not a cloud AI. I'm a small, deterministic "
            "assistant built into Trendkept — keyword matching in front of "
            "the same engine the dashboard uses. Everything I say is "
            "computed on your machine from your data and your ruleset; "
            "nothing you type here leaves it. The Iron Man films promised "
            "more charisma, but their Jarvis also made up fewer numbers "
            "than the chatbots do.", kind="info")

    if any(w in q for w in _HELP_WORDS):
        return Answer(_CAPABILITIES, kind="help",
                      links=[("/ruleset", "My Trading Diagram")])

    symbols = extract_symbols(question)

    if any(w in q for w in _ADVICE_WORDS):
        text = (
            "That's the one question I'm built to refuse. Trendkept never "
            "tells anyone to buy or sell — not because of small print, but "
            "because \"should I\" hands the decision to someone who isn't "
            "carrying your risk. What I can do is report what your written "
            "rules read on today's bar, and then the decision stays where "
            "it belongs: with you and your ruleset.")
        if symbols and fetch:
            reads = [_read_symbol(s, cfg, account, risk, fetch)
                     for s in symbols[:5]]
            text += "\n\nHere is that reading:\n" + "\n\n".join(reads)
        return Answer(text, kind="refusal")

    if any(w in q for w in _PREDICT_WORDS):
        text = (
            "I don't predict — nobody honestly can, and Trendkept's whole "
            "premise is to stop pretending otherwise. Trend-following "
            "doesn't forecast where price goes next; it defines in advance "
            "what a healthy trend looks like, what an entry is, where the "
            "stop sits, and what breaks the trend — then follows whichever "
            "way it actually resolves.")
        if symbols and fetch:
            reads = [_read_symbol(s, cfg, account, risk, fetch)
                     for s in symbols[:5]]
            text += ("\n\nWhat I can give you is the present, read "
                     "honestly:\n" + "\n\n".join(reads))
        elif symbols:
            text += ("\n\nAsk me to *check* "
                     + ", ".join(symbols[:5])
                     + " and I'll report what the rules read today.")
        return Answer(text, kind="refusal")

    if any(w in q for w in _LOG_WORDS):
        return Answer(_paper_log_summary(paper_log_path), kind="info")

    if any(w in q for w in _JOURNAL_WORDS):
        return Answer(
            "The trade journal scores your completed paper trades in "
            "R-multiples — each exit measured against the stop you actually "
            "had in place, which is the only honest yardstick. I don't "
            "reach into the broker from this chat; open the Journal page "
            "(it needs your Alpaca paper keys set) or run "
            "\"python -m trendkept.cli journal\".",
            kind="info", links=[("/journal", "Open the journal")])

    # Rules questions beat the scan intent so "explain the exit rule"
    # doesn't get read as a ticker hunt.
    if any(w in q for w in _RULES_WORDS) and not symbols:
        return Answer(_rules_text(cfg, account, risk), kind="info",
                      links=[("/ruleset", "My Trading Diagram")])

    if symbols and (any(w in q for w in _SCAN_HINTS) or len(q.split()) <= 4):
        if fetch is None:
            return Answer(
                "I can't reach any data from here to read "
                + ", ".join(symbols[:5]) + ".", kind="error")
        reads = [_read_symbol(s, cfg, account, risk, fetch)
                 for s in symbols[:8]]
        tail = ("\n\nNo entries anywhere is a normal day — in a mechanical "
                "system, quiet is the most common (and cheapest) state."
                if not any("qualifies as an entry" in r for r in reads)
                else "\n\nEvery reading above is descriptive — the "
                     "ruleset's state, not an instruction.")
        return Answer("\n\n".join(reads) + tail, kind="scan")

    if any(w in q for w in _RULES_WORDS):
        return Answer(_rules_text(cfg, account, risk), kind="info",
                      links=[("/ruleset", "My Trading Diagram")])

    return Answer(
        "I didn't recognise that one — I'm keyword matching, not "
        "mind-reading, and I'd rather admit it than guess. Try a ticker "
        "(\"check NVDA\"), \"what are my rules?\", \"how's the paper "
        "log?\", or \"help\" for the full list.", kind="error")


# --- interactive CLI loop ---------------------------------------------------

def repl(ask_fn: Callable[[str], Answer],
         input_fn: Callable[[str], str] = input,
         print_fn: Callable[[str], None] = print) -> None:
    """A tiny terminal chat: EOF, 'exit' or 'quit' ends it."""
    print_fn("Jarvis at your service. Ask away ('exit' to leave).")
    while True:
        try:
            line = input_fn("you> ")
        except (EOFError, KeyboardInterrupt):
            print_fn("")
            break
        if line.strip().lower() in ("exit", "quit", "bye", "q"):
            print_fn("jarvis> Very good. I'll be here.")
            break
        if not line.strip():
            continue
        print_fn("jarvis> " + ask_fn(line).text + "\n")
