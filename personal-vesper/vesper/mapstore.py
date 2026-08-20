"""The mainframe map, kept on your machine instead of in a browser tab.

The artifact version stores everything in localStorage: clear your history
and it is gone, and no assistant can read it. Here the map is a JSON file on
your disk that both the web page and the model can see — which is what makes
it possible to say "put the launch plan under Content" and have it happen.

Every write goes through `save()`, which writes to a temporary file and
renames it. A half-written map is worse than an old one.
"""

from __future__ import annotations

import json
import logging
import random
import re
import string
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("vesper.map")


def _uid() -> str:
    return "n" + "".join(random.choice(string.ascii_lowercase + string.digits)
                         for _ in range(8))


def _is_mine(nid: str) -> bool:
    """Was this node added by the user rather than shipped in the seed?

    Both `_uid()` here and `uid()` in the browser make ids as "n" plus a
    long random run. Every seed id is short and hand-written. That gap is
    what lets `refresh_from_seed` keep the user's work and drop the stale
    lines from an older seed, with no list to maintain.
    """
    return bool(re.fullmatch(r"n[a-z0-9]{6,}", nid or ""))


#: Where a refresh puts a node of the user's whose whole branch retired.
#: Under Personal, so it is somewhere they will actually look, and never at
#: the root — a stray leaf on the limb ring reads as a sixth area of their
#: life.
#:
#: The id is uid-shaped ON PURPOSE. It holds the user's nodes, so it has to
#: count as theirs and survive the NEXT refresh; a seed-shaped id would be
#: swept away as stale and quietly dump its children somewhere else. It is
#: also fixed rather than random, so a second refresh reuses the one that
#: exists instead of stacking up a new box each time.
RESCUE_ID = "nrescued0"
RESCUE_PARENT = "pr"


#: A limb that is yours but not the world's.
#:
#: This repo is public, so the seed below is public too — and the Health
#: branch names a real medical condition. Owner's call, August 2026: that
#: one stays off GitHub. It lives in this file instead, which `.gitignore`
#: excludes, and which ships in the download rather than in the repo.
#:
#: The mechanism matters as much as the decision. Health ids are
#: seed-shaped (`hl3d`), so `_is_mine` correctly says they are not the
#: user's own additions — and simply deleting them from SEED would make
#: the next refresh sweep them off the owner's laptop as stale. Loading
#: them here puts them back in `current_seed()`, so a refresh keeps them
#: on the machine that has the file and never invents them on one that
#: doesn't.
PRIVATE_SEED = Path(__file__).resolve().parent / "private_seed.json"


def current_seed() -> Dict[str, Any]:
    """The starting map: the public seed, plus any private limb on disk."""
    seed = json.loads(json.dumps(SEED))
    try:
        if PRIVATE_SEED.is_file():
            extra = json.loads(PRIVATE_SEED.read_text(encoding="utf-8"))
            nodes = extra.get("nodes")
            if isinstance(nodes, dict):
                for nid, node in nodes.items():
                    if isinstance(node, dict) and node.get("p"):
                        seed["nodes"][nid] = node
                for pair in extra.get("links", []):
                    if (len(pair) == 2
                            and all(x in seed["nodes"] for x in pair)):
                        seed["links"].append(list(pair))
    except (OSError, ValueError) as exc:
        # Never fatal. A broken private file must not stop Vesper starting.
        LOG.warning("could not read the private seed (%s); "
                    "carrying on without it", exc)
    return seed


#: The map a fresh install starts with. This is the one that counts —
#: the laptop serves it, so the browser copy in `web/map.html` (which is
#: only used when that file is opened straight from disk) has to match.
#: `selftest_seed.py` compares the two and fails if they drift.
SEED = {
    "nodes": {
        "root": {"id": "root", "t": "Vesper", "p": None, "done": False},
        "tk": {"id": "tk", "t": "Trendkept", "p": "root", "done": False},
        "tkw": {"id": "tkw", "t": "What it is", "p": "tk", "done": False},
        "tkwa": {"id": "tkwa", "t": "An open-source trend-following toolkit, plus Trendkept Pro",
                  "p": "tkw", "done": False},
        "tkwb": {"id": "tkwb", "t": "The promise: the rules are enforced before, during and after a trade",
                  "p": "tkw", "done": False},
        "tkwc": {"id": "tkwc", "t": "The wedge: journals score after the fact, brackets are one static rule",
                  "p": "tkw", "done": False},
        "tkwd": {"id": "tkwd", "t": "It never predicts. That anti-promise is the whole brand",
                  "p": "tkw", "done": False},
        "tkwe": {"id": "tkwe", "t": "Was Archie, then Trendrail, now Trendkept. Final, July 2026",
                  "p": "tkw", "done": False},
        "tkwf": {"id": "tkwf", "t": "The repo is public on purpose — building in public, eyes open",
                  "p": "tkw", "done": False},
        "prod": {"id": "prod", "t": "Product", "p": "tk", "done": False},
        "prod1": {"id": "prod1", "t": "Engine & rules",
                  "p": "prod", "done": False},
        "prod1a": {"id": "prod1a", "t": "Trend filter: above the 50 and 200, and higher highs",
                  "p": "prod1", "done": True},
        "prod1b": {"id": "prod1b", "t": "The stop goes in with the entry, never after",
                  "p": "prod1", "done": True},
        "prod1c": {"id": "prod1c", "t": "Size comes from the stop distance and the risk number",
                  "p": "prod1", "done": True},
        "prod1d": {"id": "prod1d", "t": "Full test suite green",
                  "p": "prod1", "done": True},
        "prod2": {"id": "prod2", "t": "Dashboard", "p": "prod", "done": False},
        "prod2a": {"id": "prod2a", "t": "python -m trendkept.web, runs on my own machine",
                  "p": "prod2", "done": True},
        "prod2b": {"id": "prod2b", "t": "Scan, backtest, watchlist",
                  "p": "prod2", "done": True},
        "prod2c": {"id": "prod2c", "t": "Trade journal in R-multiples",
                  "p": "prod2", "done": True},
        "prod2d": {"id": "prod2d", "t": "Hologram (Iron Man) theme across every page",
                  "p": "prod2", "done": True},
        "prod2e": {"id": "prod2e", "t": "Account and risk boxes remember my last number",
                  "p": "prod2", "done": True},
        "prod5": {"id": "prod5", "t": "Journal", "p": "prod", "done": False},
        "prod5a": {"id": "prod5a", "t": "Pairs broker fills into round trips, FIFO",
                  "p": "prod5", "done": True},
        "prod5b": {"id": "prod5b", "t": "Scores each one in R against the standing stop",
                  "p": "prod5", "done": True},
        "prod5c": {"id": "prod5c", "t": "Needs Alpaca keys, and they never leave the laptop",
                  "p": "prod5", "done": False},
        "prod5d": {"id": "prod5d", "t": "v2: a discipline score per rule, and my own notes",
                  "p": "prod5", "done": False},
        "prod3": {"id": "prod3", "t": "Assistant in the product",
                  "p": "prod", "done": False},
        "prod3a": {"id": "prod3a", "t": "Chat page and CLI",
                  "p": "prod3", "done": True},
        "prod3b": {"id": "prod3b", "t": "Voice replies and a spoken briefing",
                  "p": "prod3", "done": True},
        "prod3c": {"id": "prod3c", "t": "Why-didn't-it-enter diagnostics, gate by gate",
                  "p": "prod3", "done": True},
        "prod3d": {"id": "prod3d", "t": "Deterministic matching, not a cloud model. Nothing is sent",
                  "p": "prod3", "done": False},
        "prod4": {"id": "prod4", "t": "Next up", "p": "prod", "done": False},
        "prod4a": {"id": "prod4a", "t": "Journal v2 — discipline score per rule",
                  "p": "prod4", "done": False},
        "prod4b": {"id": "prod4b", "t": "Broker-agnostic CSV import",
                  "p": "prod4", "done": False},
        "prod4c": {"id": "prod4c", "t": "One-click Windows installer",
                  "p": "prod4", "done": False},
        "prod4d": {"id": "prod4d", "t": "Open in TradingView links on every symbol",
                  "p": "prod4", "done": False},
        "auto": {"id": "auto", "t": "The autopilot",
                  "p": "prod", "done": False},
        "autoa": {"id": "autoa", "t": "From day 7 the paper account flies itself",
                  "p": "auto", "done": False},
        "autob": {"id": "autob", "t": "A GitHub Action, every trading day at 21:30 UTC",
                  "p": "auto", "done": False},
        "autoc": {"id": "autoc", "t": "Manage the open positions, then at most one new entry",
                  "p": "auto", "done": False},
        "autod": {"id": "autod", "t": "Cash-limited, GTC stop attached, paper-only by construction",
                  "p": "auto", "done": False},
        "autoe": {"id": "autoe", "t": "Never more than 4 positions — the concentration rail",
                  "p": "auto", "done": False},
        "autof": {"id": "autof", "t": "It opens a GitHub issue when it acts; I spot-check",
                  "p": "auto", "done": False},
        "autog": {"id": "autog", "t": "My job became reviewer, not operator",
                  "p": "auto", "done": False},
        "autoh": {"id": "autoh", "t": "The story: I hit every human failure mode, then the rules flew",
                  "p": "auto", "done": False},
        "prod6": {"id": "prod6", "t": "The end state I want",
                  "p": "prod", "done": False},
        "prod6a": {"id": "prod6a", "t": "I chart it and alert it in TradingView",
                  "p": "prod6", "done": False},
        "prod6b": {"id": "prod6b", "t": "TradingView fires a webhook at a listener on my machine",
                  "p": "prod6", "done": False},
        "prod6c": {"id": "prod6c", "t": "Trendkept sizes it, attaches the stop, places it, journals it",
                  "p": "prod6", "done": False},
        "prod6d": {"id": "prod6d", "t": "\"TradingView thinks, Trendkept disciplines\"",
                  "p": "prod6", "done": False},
        "prod6e": {"id": "prod6e", "t": "Pro-tier scope, after month-3 monetisation",
                  "p": "prod6", "done": False},
        "biz": {"id": "biz", "t": "Business", "p": "tk", "done": False},
        "biz5": {"id": "biz5", "t": "What I am selling",
                  "p": "biz", "done": False},
        "biz5a": {"id": "biz5a", "t": "Sell the discipline, not the predictions",
                  "p": "biz5", "done": False},
        "biz5b": {"id": "biz5b", "t": "Free open core (MIT) — that IS the marketing engine",
                  "p": "biz5", "done": False},
        "biz5c": {"id": "biz5c", "t": "Pro at £12/mo or £99/yr",
                  "p": "biz5", "done": False},
        "biz5d": {"id": "biz5d", "t": "Lifetime £299, launch window only, capped at 200",
                  "p": "biz5", "done": False},
        "biz5e": {"id": "biz5e", "t": "\"The rules are free and open source; pay for the cockpit\"",
                  "p": "biz5", "done": False},
        "biz5f": {"id": "biz5f", "t": "The journal is the retention hook — 40 logged trades won't churn",
                  "p": "biz5", "done": False},
        "biz6": {"id": "biz6", "t": "Who buys it", "p": "biz", "done": False},
        "biz6a": {"id": "biz6a", "t": "Self-directed swing trader, 25-55, account £1k-£100k",
                  "p": "biz6", "done": False},
        "biz6b": {"id": "biz6b", "t": "Burned once by no stop, oversizing, or chasing",
                  "p": "biz6", "done": False},
        "biz6c": {"id": "biz6c", "t": "Actively looking for structure. That is the whole pitch",
                  "p": "biz6", "done": False},
        "biz6d": {"id": "biz6d", "t": "Secondary: the systematic-curious programmer on HN",
                  "p": "biz6", "done": False},
        "biz6e": {"id": "biz6e", "t": "NOT the customer: day traders, and signals groups wanting calls",
                  "p": "biz6", "done": False},
        "biz6f": {"id": "biz6f", "t": "Saying no to them keeps the product and the compliance clean",
                  "p": "biz6", "done": False},
        "biz1": {"id": "biz1", "t": "Validation", "p": "biz", "done": False},
        "biz1a": {"id": "biz1a", "t": "Day-30 gate — the log is the pitch",
                  "p": "biz1", "done": False},
        "biz1b": {"id": "biz1b", "t": "Three warm yeses at £12, in real conversations",
                  "p": "biz1", "done": False},
        "biz1c": {"id": "biz1c", "t": "Ten blank stares is a messaging finding, also worth having",
                  "p": "biz1", "done": False},
        "biz1d": {"id": "biz1d", "t": "Ask my own contacts for a REFERRAL, not traders for a sale",
                  "p": "biz1", "done": False},
        "biz1e": {"id": "biz1e", "t": "WhatsApp top 15 chats, one group chat, one story. Ten minutes",
                  "p": "biz1", "done": False},
        "biz1f": {"id": "biz1f", "t": "Who counts: trades own money, swing style, has rules they break",
                  "p": "biz1", "done": False},
        "biz1g": {"id": "biz1g", "t": "Not a professional quant — they would just build it themselves",
                  "p": "biz1", "done": False},
        "biz1h": {"id": "biz1h", "t": "Gates are trajectory checks, not a single tripwire",
                  "p": "biz1", "done": False},
        "biz1i": {"id": "biz1i", "t": "The investor's verdict matched our own gate exactly",
                  "p": "biz1", "done": False},
        "biz2": {"id": "biz2", "t": "Money", "p": "biz", "done": False},
        "biz2a": {"id": "biz2a", "t": "£10 of proof, then £100 to incorporate, then any monthly burn",
                  "p": "biz2", "done": False},
        "biz2b": {"id": "biz2b", "t": "Spent so far: £0 beyond the domain",
                  "p": "biz2", "done": True},
        "biz2c": {"id": "biz2c", "t": "~£9.66 per subscriber per month after real payment fees",
                  "p": "biz2", "done": False},
        "biz2d": {"id": "biz2d", "t": "Break-even at 35-40 recurring subscribers",
                  "p": "biz2", "done": False},
        "biz2e": {"id": "biz2e", "t": "Costs step with scale: ~£270/mo pre-revenue, ~£350-450 after",
                  "p": "biz2", "done": False},
        "biz2f": {"id": "biz2f", "t": "The model starts revenue at month 3, with ~9% real fees",
                  "p": "biz2", "done": False},
        "biz2g": {"id": "biz2g", "t": "Churn modelled at 10/7/5%, not a flattering single number",
                  "p": "biz2", "done": False},
        "biz2h": {"id": "biz2h", "t": "Churn is THE lever — 10%/mo means they stay 10 months",
                  "p": "biz2", "done": False},
        "biz2i": {"id": "biz2i", "t": "Change an assumption, rerun model.py, rebuild the manual",
                  "p": "biz2", "done": False},
        "biz7": {"id": "biz7", "t": "The three curves, honestly",
                  "p": "biz", "done": False},
        "biz7a": {"id": "biz7a", "t": "Base: ~£2.2k MRR at month 12, £1M net worth around month 50",
                  "p": "biz7", "done": False},
        "biz7b": {"id": "biz7b", "t": "Ambitious: £1M around month 27. Plan for it, don't count on it",
                  "p": "biz7", "done": False},
        "biz7c": {"id": "biz7c", "t": "Conservative is the MOST LIKELY one, and it never reaches £1M",
                  "p": "biz7", "done": False},
        "biz7d": {"id": "biz7d", "t": "Conservative: ~£600 MRR at month 12, ~£240k at year 5",
                  "p": "biz7", "done": False},
        "biz7e": {"id": "biz7e", "t": "That is a genuinely good side business, not a jackpot",
                  "p": "biz7", "done": False},
        "biz7f": {"id": "biz7f", "t": "The plan survives its own worst likely case. That's the test",
                  "p": "biz7", "done": False},
        "biz8": {"id": "biz8", "t": "Review gates — trajectory, not a tripwire",
                  "p": "biz", "done": False},
        "biz8a": {"id": "biz8a", "t": "Day 90: list vs curves (conservative ~340, base ~800)",
                  "p": "biz8", "done": False},
        "biz8b": {"id": "biz8b", "t": "Month 6: subscribers vs curves (conservative ~65, base ~230)",
                  "p": "biz8", "done": False},
        "biz8c": {"id": "biz8c", "t": "Month 12: MRR vs curves (conservative ~£600, base ~£2.2k)",
                  "p": "biz8", "done": False},
        "biz8d": {"id": "biz8d", "t": "Above £2k at month 12 → a winner. Let it run",
                  "p": "biz8", "done": False},
        "biz8e": {"id": "biz8e", "t": "On the conservative curve → continue, or demote to 2 h/week",
                  "p": "biz8", "done": False},
        "biz8f": {"id": "biz8f", "t": "Below it or shrinking → sell the codebase and the audience",
                  "p": "biz8", "done": False},
        "biz8g": {"id": "biz8g", "t": "Exiting a non-winner at a small profit is winning",
                  "p": "biz8", "done": False},
        "biz8h": {"id": "biz8h", "t": "Drifting without deciding is the only losing move",
                  "p": "biz8", "done": False},
        "biz9": {"id": "biz9", "t": "Roadmap, one marketable thing a month",
                  "p": "biz", "done": False},
        "biz9a": {"id": "biz9a", "t": "Month 2: journal + R-multiple discipline score",
                  "p": "biz9", "done": True},
        "biz9b": {"id": "biz9b", "t": "Month 3: payments and licence keys — Pro goes live",
                  "p": "biz9", "done": False},
        "biz9c": {"id": "biz9c", "t": "Month 4: daily \"what the rules say\" email",
                  "p": "biz9", "done": False},
        "biz9d": {"id": "biz9d", "t": "Month 5: hosted tier — analysis and journal ONLY, never keys",
                  "p": "biz9", "done": False},
        "biz9e": {"id": "biz9e", "t": "Month 6: a second broker, to widen the market",
                  "p": "biz9", "done": False},
        "biz9f": {"id": "biz9f", "t": "Months 7-9: discipline analytics — where I break my own rules",
                  "p": "biz9", "done": False},
        "biz9g": {"id": "biz9g", "t": "Months 10-12: subscriber forum, monthly rule-review call",
                  "p": "biz9", "done": False},
        "biz9h": {"id": "biz9h", "t": "Rule for all of it: stay boring. No AI predictions, no crypto",
                  "p": "biz9", "done": False},
        "bizr": {"id": "bizr", "t": "Risks, stated plainly",
                  "p": "biz", "done": False},
        "bizra": {"id": "bizra", "t": "No distribution — this is what kills most tool businesses",
                  "p": "bizr", "done": False},
        "bizrb": {"id": "bizrb", "t": "Data licensing — one cease-and-desist and there is no data",
                  "p": "bizr", "done": False},
        "bizrc": {"id": "bizrc", "t": "A bear market hurts acquisition and churn at the same time",
                  "p": "bizr", "done": False},
        "bizrd": {"id": "bizrd", "t": "Churn could run 10-15%, typical for trader B2C",
                  "p": "bizr", "done": False},
        "bizre": {"id": "bizre", "t": "Everything runs through one AI subscription. It's in the costs",
                  "p": "bizr", "done": False},
        "bizrf": {"id": "bizrf", "t": "Copycats can copy features, not the journal history",
                  "p": "bizr", "done": False},
        "bizrg": {"id": "bizrg", "t": "Burnout: ~10 h/week steady, but launch weeks are 25+",
                  "p": "bizr", "done": False},
        "biz3": {"id": "biz3", "t": "Legal", "p": "biz", "done": False},
        "biz3a": {"id": "biz3a", "t": "A UK limited company. Owner 100%, no investors",
                  "p": "biz3", "done": False},
        "biz3b": {"id": "biz3b", "t": "It executes the USER'S ruleset on the USER'S data",
                  "p": "biz3", "done": False},
        "biz3c": {"id": "biz3c", "t": "Never person-specific, never holds money, never promises returns",
                  "p": "biz3", "done": False},
        "biz3d": {"id": "biz3d", "t": "Same footing as TradingView or any backtesting library",
                  "p": "biz3", "done": False},
        "biz3e": {"id": "biz3e", "t": "The FCA bright line: descriptive, never imperative",
                  "p": "biz3", "done": False},
        "biz3f": {"id": "biz3f", "t": "\"Trend filter no longer met\" — never \"get out\"",
                  "p": "biz3", "done": False},
        "biz3g": {"id": "biz3g", "t": "No return promises, no gain screenshots, no per-person advice",
                  "p": "biz3", "done": False},
        "biz3h": {"id": "biz3h", "t": "A licensed data feed before anyone pays",
                  "p": "biz3", "done": False},
        "biz3i": {"id": "biz3i", "t": "US perimeter check before any US customer",
                  "p": "biz3", "done": False},
        "biz4": {"id": "biz4", "t": "Mine alone, never delegated",
                  "p": "biz", "done": False},
        "biz4a": {"id": "biz4a", "t": "Money and anything that spends it",
                  "p": "biz4", "done": False},
        "biz4b": {"id": "biz4b", "t": "Accounts, keys and secrets",
                  "p": "biz4", "done": False},
        "biz4c": {"id": "biz4c", "t": "Merges to main",
                  "p": "biz4", "done": False},
        "biz4d": {"id": "biz4d", "t": "Publishing anything under my name",
                  "p": "biz4", "done": False},
        "biz4e": {"id": "biz4e", "t": "Legal sign-off",
                  "p": "biz4", "done": False},
        "con": {"id": "con", "t": "Content", "p": "tk", "done": False},
        "con1": {"id": "con1", "t": "Website", "p": "con", "done": False},
        "con1a": {"id": "con1a", "t": "trendkept.com is live on a Cloudflare Worker",
                  "p": "con1", "done": True},
        "con1b": {"id": "con1b", "t": "Four free calculators, no signup",
                  "p": "con1", "done": True},
        "con1c": {"id": "con1c", "t": "OG image, sitemap, robots.txt, llm.txt",
                  "p": "con1", "done": True},
        "con1d": {"id": "con1d", "t": "The wedge is on the homepage and in the FAQ",
                  "p": "con1", "done": True},
        "con1e": {"id": "con1e", "t": "One primary call to action: the weekly email",
                  "p": "con1", "done": True},
        "con2": {"id": "con2", "t": "Newsletter", "p": "con", "done": False},
        "con2a": {"id": "con2a", "t": "The Trend Check, live on Buttondown",
                  "p": "con2", "done": True},
        "con2b": {"id": "con2b", "t": "The slug is `trendkept`, lowercase. This broke once",
                  "p": "con2", "done": False},
        "con2c": {"id": "con2c", "t": "news.trendkept.com verified, signup tested end to end",
                  "p": "con2", "done": True},
        "con2d": {"id": "con2d", "t": "Sunday auto-draft GitHub Action",
                  "p": "con2", "done": True},
        "con2e": {"id": "con2e", "t": "Subscriber number one is me",
                  "p": "con2", "done": False},
        "con5": {"id": "con5", "t": "How people find it",
                  "p": "con", "done": False},
        "con5a": {"id": "con5a", "t": "Open source is the top of the funnel: Show HN, r/algotrading",
                  "p": "con5", "done": False},
        "con5b": {"id": "con5b", "t": "Content that IS the philosophy, not ads for it",
                  "p": "con5", "done": False},
        "con5c": {"id": "con5c", "t": "\"You don't need better entries, you need smaller losses\"",
                  "p": "con5", "done": False},
        "con5d": {"id": "con5d", "t": "The newsletter is the mid-funnel: weekly check on 20 tickers",
                  "p": "con5", "done": False},
        "con5e": {"id": "con5e", "t": "SEO pages with buying intent the big players ignore",
                  "p": "con5", "done": False},
        "con5f": {"id": "con5f", "t": "Every backtest chart is content with the product inside it",
                  "p": "con5", "done": False},
        "con3": {"id": "con3", "t": "Drafts ready to post",
                  "p": "con", "done": False},
        "con3a": {"id": "con3a", "t": "Essay: moving stops",
                  "p": "con3", "done": False},
        "con3b": {"id": "con3b", "t": "Essay: lookahead bias",
                  "p": "con3", "done": False},
        "con3c": {"id": "con3c", "t": "Welcome email",
                  "p": "con3", "done": False},
        "con4": {"id": "con4", "t": "Rules for anything public",
                  "p": "con", "done": False},
        "con4a": {"id": "con4a", "t": "Every claim true of me on the day I post it",
                  "p": "con4", "done": False},
        "con4b": {"id": "con4b", "t": "No invented trading history. Not once, not softened",
                  "p": "con4", "done": False},
        "con4c": {"id": "con4c", "t": "The r/swingtrading post waits for four weeks of real log",
                  "p": "con4", "done": False},
        "con4d": {"id": "con4d", "t": "Broadcast copy describes. It never instructs",
                  "p": "con4", "done": False},
        "log": {"id": "log", "t": "Paper log — business/paper_log.csv",
                  "p": "tk", "done": False},
        "loga": {"id": "loga", "t": "26 rows across 22 trading days, to 12 August",
                  "p": "log", "done": True},
        "logb": {"id": "logb", "t": "Rules kept on 24 of 26",
                  "p": "log", "done": True},
        "logc": {"id": "logc", "t": "Three closed trades: NVDA -0.44R, SPY +0.02R, SPY -0.89R",
                  "p": "log", "done": False},
        "logd": {"id": "logd", "t": "Three execution faults found and fixed — none a rule change",
                  "p": "log", "done": False},
        "loge": {"id": "loge", "t": "The day-order stop expiry, the double-exit, the sub-penny raise",
                  "p": "log", "done": False},
        "logf": {"id": "logf", "t": "The watchlist is 20 liquid US names",
                  "p": "log", "done": False},
        "logg": {"id": "logg", "t": "One row per trading day, including the days I did nothing",
                  "p": "log", "done": True},
        "logh": {"id": "logh", "t": "I send photos, the session transcribes them into rows",
                  "p": "log", "done": False},
        "logi": {"id": "logi", "t": "Never backfill a day I haven't evidenced",
                  "p": "log", "done": False},
        "logj": {"id": "logj", "t": "Day 30 is what unlocks the results post",
                  "p": "log", "done": False},
        "logk": {"id": "logk", "t": "Rules kept is the number that matters, not profit",
                  "p": "log", "done": False},
        "rev": {"id": "rev", "t": "When the rules may change",
                  "p": "tk", "done": False},
        "reva": {"id": "reva", "t": "Written during a losing stretch, on purpose",
                  "p": "rev", "done": False},
        "revb": {"id": "revb", "t": "A threshold set while calm is worth something",
                  "p": "rev", "done": False},
        "revc": {"id": "revc", "t": "A threshold set while hurting is a feeling with a number on it",
                  "p": "rev", "done": False},
        "revd": {"id": "revd", "t": "The maths: ~37% win rate, +2.2R average win, -0.95R average loss",
                  "p": "rev", "done": False},
        "reve": {"id": "reve", "t": "That is an edge of about +0.2R, with 1.6R of spread per trade",
                  "p": "rev", "done": False},
        "revf": {"id": "revf", "t": "To tell +0.2R from zero takes ~250 trades — two to three years",
                  "p": "rev", "done": False},
        "revg": {"id": "revg", "t": "So the paper account can NEVER prove the strategy works",
                  "p": "rev", "done": False},
        "revh": {"id": "revh", "t": "What it can catch: execution faults, and drift from the backtest",
                  "p": "rev", "done": False},
        "revi": {"id": "revi", "t": "Execution faults get fixed immediately. Zero tolerance",
                  "p": "rev", "done": False},
        "revj": {"id": "revj", "t": "Drawdown -5%: note it. -10%: formal review. -20%: halt entries",
                  "p": "rev", "done": False},
        "revk": {"id": "revk", "t": "The divergence test runs at 30 closed trades, then every 30",
                  "p": "rev", "done": False},
        "revl": {"id": "revl", "t": "Forbidden: tightening a stop because a trade just lost",
                  "p": "rev", "done": False},
        "revm": {"id": "revm", "t": "Forbidden: skipping a signal because the last one lost",
                  "p": "rev", "done": False},
        "revn": {"id": "revn", "t": "Forbidden: fitting the rules to a few dozen trades",
                  "p": "rev", "done": False},
        "revo": {"id": "revo", "t": "A disciplined losing stretch proves more than a lucky winning one",
                  "p": "rev", "done": False},
        "dec": {"id": "dec", "t": "Decisions already settled",
                  "p": "tk", "done": False},
        "deca": {"id": "deca", "t": "No prediction feature. Nobody can honestly do it",
                  "p": "dec", "done": False},
        "decb": {"id": "decb", "t": "No per-trade auto-tuning — that is overfitting noise",
                  "p": "dec", "done": False},
        "decc": {"id": "decc", "t": "The honest version: backtest variants, out-of-sample split",
                  "p": "dec", "done": False},
        "decd": {"id": "decd", "t": "Journal insights wait until roughly 20 real trades exist",
                  "p": "dec", "done": False},
        "dece": {"id": "dece", "t": "Review monthly. Never after a single trade",
                  "p": "dec", "done": False},
        "decf": {"id": "decf", "t": "I can't fake ICT, SMC or Wyckoff, so I say so plainly",
                  "p": "dec", "done": False},
        "decg": {"id": "decg", "t": "Nearest honest offer: a breakout-of-structure entry",
                  "p": "dec", "done": False},
        "dech": {"id": "dech", "t": "Rejected: results threads on r/Daytrading, wrong audience",
                  "p": "dec", "done": False},
        "deci": {"id": "deci", "t": "Rejected: panic about the open core. Pro sells the easy version",
                  "p": "dec", "done": False},
        "mt": {"id": "mt", "t": "My trading", "p": "root", "done": False},
        "mta": {"id": "mta", "t": "My own money. Nothing here belongs to Trendkept",
                  "p": "mt", "done": False},
        "mt1": {"id": "mt1", "t": "My account", "p": "mt", "done": False},
        "mt1a": {"id": "mt1a", "t": "Broker, and what the account is actually worth",
                  "p": "mt1", "done": False},
        "mt1b": {"id": "mt1b", "t": "Risk per trade — the one number that decides everything",
                  "p": "mt1", "done": False},
        "mt1c": {"id": "mt1c", "t": "The most I will hold at once",
                  "p": "mt1", "done": False},
        "mt1d": {"id": "mt1d", "t": "Vesper remembers the last numbers I typed in",
                  "p": "mt1", "done": False},
        "mt4": {"id": "mt4", "t": "My rules", "p": "mt", "done": False},
        "mt4a": {"id": "mt4a", "t": "Price above the 50 and the 200, and the 50 above the 200",
                  "p": "mt4", "done": False},
        "mt4b": {"id": "mt4b", "t": "Higher highs and higher lows on the swing chart",
                  "p": "mt4", "done": False},
        "mt4c": {"id": "mt4c", "t": "The stop goes in at the same moment as the entry",
                  "p": "mt4", "done": False},
        "mt4d": {"id": "mt4d", "t": "Size falls out of the stop distance and my risk number",
                  "p": "mt4", "done": False},
        "mt4e": {"id": "mt4e", "t": "Most days the answer is do nothing. That is the discipline",
                  "p": "mt4", "done": False},
        "mt4f": {"id": "mt4f", "t": "I never move a stop away from price",
                  "p": "mt4", "done": False},
        "mt4g": {"id": "mt4g", "t": "I don't take a trade I can't say the reason for out loud",
                  "p": "mt4", "done": False},
        "mt4h": {"id": "mt4h", "t": "Never more than 4 positions open at once",
                  "p": "mt4", "done": False},
        "mt4i": {"id": "mt4i", "t": "Risk about 1% of the account on any one trade",
                  "p": "mt4", "done": False},
        "mt2": {"id": "mt2", "t": "Watchlist", "p": "mt", "done": False},
        "mt2a": {"id": "mt2a", "t": "Symbols I actually follow",
                  "p": "mt2", "done": False},
        "mt2b": {"id": "mt2b", "t": "Why each one is on here",
                  "p": "mt2", "done": False},
        "mt2c": {"id": "mt2c", "t": "What would take one off",
                  "p": "mt2", "done": False},
        "mt3": {"id": "mt3", "t": "Open positions", "p": "mt", "done": False},
        "mt3a": {"id": "mt3a", "t": "Entry, size, and where the stop sits",
                  "p": "mt3", "done": False},
        "mt3b": {"id": "mt3b", "t": "Total risk on right now, added up across everything",
                  "p": "mt3", "done": False},
        "mt5": {"id": "mt5", "t": "Closed trades", "p": "mt", "done": False},
        "mt5a": {"id": "mt5a", "t": "Every trade scored in R, win or lose",
                  "p": "mt5", "done": False},
        "mt5b": {"id": "mt5b", "t": "Did I follow my own rules — asked separately from did it pay",
                  "p": "mt5", "done": False},
        "mt5c": {"id": "mt5c", "t": "Review monthly, never after one trade",
                  "p": "mt5", "done": False},
        "mt5d": {"id": "mt5d", "t": "Patterns wait until there are enough trades to mean anything",
                  "p": "mt5", "done": False},
        "mt6": {"id": "mt6", "t": "Macro worth watching",
                  "p": "mt", "done": False},
        "mt6a": {"id": "mt6a", "t": "Rates decisions and inflation prints",
                  "p": "mt6", "done": False},
        "mt6b": {"id": "mt6b", "t": "Earnings dates for anything I am holding",
                  "p": "mt6", "done": False},
        "mt7": {"id": "mt7", "t": "Never", "p": "mt", "done": False},
        "mt7a": {"id": "mt7a", "t": "No predictions. Not mine, not anyone's",
                  "p": "mt7", "done": False},
        "mt7b": {"id": "mt7b", "t": "No tips, no \"should I buy\"",
                  "p": "mt7", "done": False},
        "mt7c": {"id": "mt7c", "t": "Vesper answers those with the descriptive read instead",
                  "p": "mt7", "done": False},
        "nw": {"id": "nw", "t": "News & weather", "p": "root", "done": False},
        "nw1": {"id": "nw1", "t": "Feeds I follow", "p": "nw", "done": False},
        "nw1a": {"id": "nw1a", "t": "Market open and close",
                  "p": "nw1", "done": False},
        "nw1b": {"id": "nw1b", "t": "Anything touching a symbol on my watchlist",
                  "p": "nw1", "done": False},
        "nw1c": {"id": "nw1c", "t": "UK news", "p": "nw1", "done": False},
        "nw2": {"id": "nw2", "t": "Watch words that interrupt me",
                  "p": "nw", "done": False},
        "nw2a": {"id": "nw2a", "t": "Only things I would thank it for interrupting",
                  "p": "nw2", "done": False},
        "nw2b": {"id": "nw2b", "t": "Everything else waits for the brief",
                  "p": "nw2", "done": False},
        "nw3": {"id": "nw3", "t": "Weather where I am",
                  "p": "nw", "done": False},
        "nw3a": {"id": "nw3a", "t": "Vesper has a weather tool. It looks it up rather than guessing",
                  "p": "nw3", "done": False},
        "nw3b": {"id": "nw3b", "t": "Worth knowing before an outdoor session, given the heat rule",
                  "p": "nw3", "done": False},
        "nw4": {"id": "nw4", "t": "Today's brief", "p": "nw", "done": False},
        "nw4a": {"id": "nw4a", "t": "Say \"brief me\" and Vesper reads it out",
                  "p": "nw4", "done": False},
        "nw4b": {"id": "nw4b", "t": "Paper log, the dials, and the read on any symbol I name",
                  "p": "nw4", "done": False},
        "nw4c": {"id": "nw4c", "t": "Replies are spoken on the laptop, locally",
                  "p": "nw4", "done": False},
        "nw4d": {"id": "nw4d", "t": "The microphone button is the one thing that leaves the machine",
                  "p": "nw4", "done": False},
        "nw5": {"id": "nw5", "t": "How alerts actually reach me",
                  "p": "nw", "done": False},
        "nw5a": {"id": "nw5a", "t": "A push notification to the phone, through ntfy",
                  "p": "nw5", "done": False},
        "nw5b": {"id": "nw5b", "t": "High priority, so it breaks through silent",
                  "p": "nw5", "done": False},
        "nw5c": {"id": "nw5c", "t": "Ambient events stay quiet. Real alerts do not",
                  "p": "nw5", "done": False},
        "pr": {"id": "pr", "t": "Personal", "p": "root", "done": False},
        "pr4": {"id": "pr4", "t": "The laptop", "p": "pr", "done": False},
        "pr4a": {"id": "pr4a", "t": "ThinkPad T480s, i5-8250U, 16GB, 256GB",
                  "p": "pr4", "done": False},
        "pr4b": {"id": "pr4b", "t": "Vesper lives in its own folder. Deleting the folder uninstalls it",
                  "p": "pr4", "done": False},
        "pr4c": {"id": "pr4c", "t": "Double-click \"Install Vesper.bat\" once, then \"Vesper.bat\" after",
                  "p": "pr4", "done": False},
        "pr4d": {"id": "pr4d", "t": "Settings live in a file called .env beside those two",
                  "p": "pr4", "done": False},
        "pr4e": {"id": "pr4e", "t": "The app and the browser page are one program, not two",
                  "p": "pr4", "done": False},
        "pr5": {"id": "pr5", "t": "Vesper itself", "p": "pr", "done": False},
        "pr5a": {"id": "pr5a", "t": "Local-first. Only the model call leaves the laptop",
                  "p": "pr5", "done": False},
        "pr5b": {"id": "pr5b", "t": "It calls me sir, in every single reply",
                  "p": "pr5", "done": False},
        "pr5c": {"id": "pr5c", "t": "Wake word is \"hey Jarvis\" until \"hey Vesper\" is trained",
                  "p": "pr5", "done": False},
        "pr5d": {"id": "pr5d", "t": "Voice is the Windows built-in one for now; Piper is better",
                  "p": "pr5", "done": False},
        "pr5e": {"id": "pr5e", "t": "ElevenLabs will not serve its API on the free tier",
                  "p": "pr5", "done": False},
        "pr6": {"id": "pr6", "t": "Still to do", "p": "pr", "done": False},
        "pr6a": {"id": "pr6a", "t": "Create the private repo: github.com/new, name vesper, Private",
                  "p": "pr6", "done": False},
        "pr6b": {"id": "pr6b", "t": "Train \"hey Vesper\" — about an hour in Colab",
                  "p": "pr6", "done": False},
        "pr6c": {"id": "pr6c", "t": "Install the VC++ redistributable so the wake word loads",
                  "p": "pr6", "done": False},
        "pr6d": {"id": "pr6d", "t": "Spotify control needs Premium before it can work",
                  "p": "pr6", "done": False},
        "pr1": {"id": "pr1", "t": "Ideas", "p": "pr", "done": False},
        "pr1a": {"id": "pr1a", "t": "Hand-gesture control, projector style",
                  "p": "pr1", "done": False},
        "pr1b": {"id": "pr1b", "t": "Have Vesper read me the Sunday newsletter draft",
                  "p": "pr1", "done": False},
        "pr1c": {"id": "pr1c", "t": "Say \"add X to ideas\" and it lands here",
                  "p": "pr1", "done": False},
        "pr2": {"id": "pr2", "t": "To do", "p": "pr", "done": False},
        "pr2a": {"id": "pr2a", "t": "Say \"add X to my to do\" and it lands here",
                  "p": "pr2", "done": False},
        "pr3": {"id": "pr3", "t": "Notes", "p": "pr", "done": False},
        "pr3a": {"id": "pr3a", "t": "Say \"note X\" and it lands here",
                  "p": "pr3", "done": False},
    },
    "links": [
        ["nw2", "nw4"],
        ["biz1a", "logd"],
        ["con3a", "prod1b"],
        ["biz3a", "con4d"],
        ["biz3d", "prod1"],
        ["con2d", "loga"],
        ["mt4", "prod1"],
        ["mt7", "dec"],
        ["pr5", "prod3"],
        ["rev", "dec"],
        ["auto", "log"],
        ["biz8", "biz7"],
        ["biz5", "prod5"],
        ["biz6", "mt"],
        ["con5", "con2"],
    ],
}


class MapStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data: Dict[str, Any] = self._load()

    # -- disk -------------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        if self.path.is_file():
            try:
                d = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(d, dict) and d.get("nodes", {}).get("root"):
                    d.setdefault("links", [])
                    return d
                LOG.warning("map file has the wrong shape; starting fresh")
            except (OSError, ValueError) as exc:
                LOG.error("could not read map (%s); starting fresh", exc)
        return current_seed()

    def save(self) -> None:
        with self._lock:
            payload = json.dumps(self.data, indent=1)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            LOG.error("could not write map: %s", exc)

    def replace(self, data: Dict[str, Any]) -> bool:
        """Take a whole map from the browser (a drag, a rename, an import)."""
        if not (isinstance(data, dict) and data.get("nodes", {}).get("root")):
            return False
        with self._lock:
            data.setdefault("links", [])
            self.data = data
        self.save()
        return True

    def refresh_from_seed(self) -> Tuple[int, int]:
        """Take the current starting map, keeping anything I added myself.

        The seed only ever applies to a fresh install, so an install made
        before the map was filled in keeps its thin old copy forever. This
        brings it up to date without being a reset.

        "Mine" is decided by the shape of the id, not by a list I would have
        to remember to update. Anything added through the app — here or in
        the browser — gets an id from a uid generator: an "n" and a long
        run of random characters. Seed ids are short and hand-written
        (`mt4a`, `biz3`, `nw5c`). So a uid-shaped id is mine and survives;
        anything else that the current seed no longer has was a line from
        an OLDER seed, and keeping it would leave the map showing both the
        old thin wording and the new one side by side.

        A carried node whose parent didn't survive is re-hung on the nearest
        ancestor that did, rather than dropped on the floor.

        Returns (added, kept-of-mine).
        """
        with self._lock:
            old = self.data
            new = current_seed()
            on, nn = old.get("nodes", {}), new["nodes"]
            mine = [nid for nid in on if nid not in nn and _is_mine(nid)]
            # Count before the merge; afterwards `nn` holds both sets and
            # the arithmetic quietly goes negative.
            added = len(set(nn) - set(on))

            def surviving_parent(nid: str) -> Optional[str]:
                """The nearest ancestor still on the map, or None.

                Walking up to "root" does NOT count as finding a home. Root
                always survives, so accepting it means every rescued leaf
                lands on the limb ring — the first version of this put
                "MSFT — watching the 50" up beside Trendkept and Health.
                Only a node the owner deliberately hung off root keeps it.
                """
                first = on.get(nid, {}).get("p")
                if first == "root":
                    return "root"
                seen, p = set(), first
                while p and p != "root" and p not in seen:
                    seen.add(p)
                    if p in nn or p in mine:
                        return p
                    p = on.get(p, {}).get("p")
                return None

            for nid in mine:
                nn[nid] = dict(on[nid])

            # Root is the limb ring. Hanging a rescued leaf there would put
            # "MSFT — watching the 50" up beside Trendkept and Health as if
            # it were a whole area of my life, which is how the map stops
            # meaning anything. Strays go to one findable place instead.
            rescue = None
            for nid in mine:
                p = surviving_parent(nid)
                if p is None:
                    if rescue is None:
                        rescue = RESCUE_ID
                        nn.setdefault(rescue, {
                            "id": rescue,
                            "t": "Rescued from the older map",
                            "p": RESCUE_PARENT if RESCUE_PARENT in nn else "root",
                            "done": False})
                    p = rescue
                nn[nid]["p"] = p

            keep = {tuple(sorted(map(str, l))) for l in new["links"]}
            for pair in old.get("links", []):
                if len(pair) == 2 and all(x in nn for x in pair) \
                        and tuple(sorted(map(str, pair))) not in keep:
                    new["links"].append(list(pair))
                    keep.add(tuple(sorted(map(str, pair))))

            self.data = new

        # A backup, because this rewrites a file the owner may care about.
        try:
            if self.path.is_file():
                self.path.with_suffix(".json.bak").write_text(
                    json.dumps(old, indent=1), encoding="utf-8")
        except OSError as exc:
            LOG.warning("could not write the map backup: %s", exc)
        self.save()
        return added, len(mine)

    # -- reading ----------------------------------------------------------

    def nodes(self) -> Dict[str, Any]:
        return self.data["nodes"]

    def node(self, nid: str) -> Optional[dict]:
        return self.data["nodes"].get(nid)

    def kids(self, nid: str) -> List[dict]:
        return [n for n in self.data["nodes"].values() if n.get("p") == nid]

    def find(self, name: str) -> Optional[dict]:
        """Match a spoken name to a node. Exact, then contained, then words.

        Deliberately forgiving — the model passes whatever the user called it,
        and "the paper log" should reach "Paper log".
        """
        if not name:
            return None
        want = name.strip().lower().lstrip("the ").strip()
        nodes = list(self.data["nodes"].values())
        for n in nodes:
            if n["t"].lower() == want:
                return n
        hits = [n for n in nodes if want in n["t"].lower()]
        if hits:
            return min(hits, key=lambda n: len(n["t"]))
        words = [w for w in want.split() if len(w) > 3]
        if words:
            scored = [(sum(w in n["t"].lower() for w in words), n) for n in nodes]
            best = max(scored, key=lambda s: s[0])
            if best[0]:
                return best[1]
        return None

    def path_of(self, nid: str) -> str:
        trail, seen = [], set()
        n = self.node(nid)
        while n and n["id"] not in seen:
            seen.add(n["id"])
            trail.append(n["t"])
            n = self.node(n["p"]) if n.get("p") else None
        return " › ".join(reversed(trail))

    def outline(self, max_depth: int = 3, limit: int = 220) -> str:
        """A plain-text outline for the model to read. Depth-capped so a big
        map doesn't fill the context window."""
        lines: List[str] = []

        def walk(nid: str, depth: int) -> None:
            if len(lines) >= limit or depth > max_depth:
                return
            for k in sorted(self.kids(nid), key=lambda x: x["t"].lower()):
                mark = " [done]" if k.get("done") else ""
                extra = ""
                kids = self.kids(k["id"])
                if depth == max_depth and kids:
                    extra = f" (+{len(kids)} more)"
                lines.append("  " * depth + "- " + k["t"] + mark + extra)
                walk(k["id"], depth + 1)

        walk("root", 0)
        return "\n".join(lines) if lines else "(the map is empty)"

    # -- writing ----------------------------------------------------------

    def add(self, text: str, parent: Optional[str] = None) -> Tuple[bool, str]:
        text = (text or "").strip()
        if not text:
            return False, "A point needs some text."
        with self._lock:
            pid = "root"
            if parent:
                p = self.find(parent)
                if not p:
                    return False, f"Nothing on the map is called {parent!r}."
                pid = p["id"]
            nid = _uid()
            self.data["nodes"][nid] = {"id": nid, "t": text, "p": pid,
                                       "done": False, "at": time.time()}
        self.save()
        return True, f"Added {text!r} under {self.node(pid)['t']!r}."

    def rename(self, name: str, to: str) -> Tuple[bool, str]:
        n = self.find(name)
        if not n:
            return False, f"Nothing on the map is called {name!r}."
        to = (to or "").strip()
        if not to:
            return False, "Needs a new name."
        old = n["t"]
        with self._lock:
            n["t"] = to
        self.save()
        return True, f"Renamed {old!r} to {to!r}."

    def set_done(self, name: str, done: bool = True) -> Tuple[bool, str]:
        n = self.find(name)
        if not n:
            return False, f"Nothing on the map is called {name!r}."
        with self._lock:
            n["done"] = bool(done)
        self.save()
        return True, f"{n['t']!r} marked {'done' if done else 'not done'}."

    def remove(self, name: str) -> Tuple[bool, str]:
        n = self.find(name)
        if not n:
            return False, f"Nothing on the map is called {name!r}."
        if n["id"] == "root":
            return False, "The core can't be deleted."
        doomed: List[str] = []

        def walk(x: str) -> None:
            doomed.append(x)
            for k in self.kids(x):
                walk(k["id"])

        with self._lock:
            walk(n["id"])
            for x in doomed:
                self.data["nodes"].pop(x, None)
            self.data["links"] = [l for l in self.data["links"]
                                  if l[0] not in doomed and l[1] not in doomed]
        self.save()
        under = len(doomed) - 1
        return True, (f"Deleted {n['t']!r}"
                      + (f" and the {under} points under it." if under else "."))

    def move(self, name: str, new_parent: str) -> Tuple[bool, str]:
        n, p = self.find(name), self.find(new_parent)
        if not n:
            return False, f"Nothing on the map is called {name!r}."
        if not p:
            return False, f"Nothing on the map is called {new_parent!r}."
        if n["id"] == "root":
            return False, "The core can't be moved."
        # Walk up from the destination: if we meet the node being moved, this
        # would detach a whole limb into a loop pointing at itself.
        c = p
        while c:
            if c["id"] == n["id"]:
                return False, f"Can't put {n['t']!r} inside itself."
            c = self.node(c["p"]) if c.get("p") else None
        with self._lock:
            n["p"] = p["id"]
        self.save()
        return True, f"Moved {n['t']!r} under {p['t']!r}."

    def link(self, a: str, b: str) -> Tuple[bool, str]:
        na, nb = self.find(a), self.find(b)
        if not na or not nb:
            return False, "I need two things that are both on the map."
        if na["id"] == nb["id"]:
            return False, "That's the same point twice."
        with self._lock:
            pair = [na["id"], nb["id"]]
            if pair not in self.data["links"] and pair[::-1] not in self.data["links"]:
                self.data["links"].append(pair)
        self.save()
        return True, f"Linked {na['t']!r} and {nb['t']!r}."

    def summary(self) -> str:
        total = len(self.data["nodes"]) - 1
        open_n = sum(1 for n in self.data["nodes"].values()
                     if n["id"] != "root" and not n.get("done"))
        limbs = [n["t"] for n in self.kids("root")]
        return (f"{total} points across {len(limbs)} limbs "
                f"({', '.join(limbs) if limbs else 'none'}); {open_n} open.")


def _main() -> int:
    """`python -m vesper.mapstore --refresh` — bring an old map up to date.

    An install made before the map was written out keeps the thin version it
    was born with, because the seed only ever applies to a brand-new file.
    This is how an existing install catches up.
    """
    import argparse

    from .config import CONFIG

    ap = argparse.ArgumentParser(description="Look after the map file.")
    ap.add_argument("--refresh", action="store_true",
                    help="take the current starting map, keeping what I added")
    ap.add_argument("--show", action="store_true", help="print the outline")
    args = ap.parse_args()

    store = MapStore(Path(CONFIG.map_path))
    if args.refresh:
        added, kept = store.refresh_from_seed()
        print(f"Map refreshed: {added} new points added, {kept} of your own "
              f"kept. The old one is beside it as {store.path.name}.bak")
    print(store.summary())
    if args.show:
        print()
        print(store.outline(max_depth=4, limit=400))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
