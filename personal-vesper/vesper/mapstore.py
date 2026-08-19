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
import string
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("vesper.map")


def _uid() -> str:
    return "n" + "".join(random.choice(string.ascii_lowercase + string.digits)
                         for _ in range(8))


#: The map a fresh install starts with. This is the one that counts —
#: the laptop serves it, so the browser copy in `web/map.html` (which is
#: only used when that file is opened straight from disk) has to match.
#: `selftest_seed.py` compares the two and fails if they drift.
SEED = {
    "nodes": {
        "root": {"id": "root", "t": "Vesper", "p": None, "done": False},
        "tk": {"id": "tk", "t": "Trendkept", "p": "root", "done": False},
        "prod": {"id": "prod", "t": "Product", "p": "tk", "done": False},
        "prod1": {"id": "prod1", "t": "Engine & rules",
                 "p": "prod", "done": False},
        "prod1a": {"id": "prod1a", "t": "Trend filter: 50/200, higher highs",
                 "p": "prod1", "done": False},
        "prod1b": {"id": "prod1b", "t": "Stop goes in with the entry",
                 "p": "prod1", "done": False},
        "prod1c": {"id": "prod1c", "t": "Full test suite green",
                 "p": "prod1", "done": True},
        "prod2": {"id": "prod2", "t": "Dashboard", "p": "prod", "done": False},
        "prod2a": {"id": "prod2a", "t": "Scan, backtest, watchlist",
                 "p": "prod2", "done": True},
        "prod2b": {"id": "prod2b", "t": "Trade journal in R-multiples",
                 "p": "prod2", "done": True},
        "prod2c": {"id": "prod2c", "t": "Hologram theme",
                 "p": "prod2", "done": True},
        "prod3": {"id": "prod3", "t": "Assistant", "p": "prod", "done": False},
        "prod3a": {"id": "prod3a", "t": "Chat page + CLI",
                 "p": "prod3", "done": True},
        "prod3b": {"id": "prod3b", "t": "Voice & briefings",
                 "p": "prod3", "done": True},
        "prod3c": {"id": "prod3c", "t": "Why-didn't-it-enter diagnostics",
                 "p": "prod3", "done": True},
        "prod4": {"id": "prod4", "t": "Next up", "p": "prod", "done": False},
        "prod4a": {"id": "prod4a", "t": "Journal v2 — discipline score",
                 "p": "prod4", "done": False},
        "prod4b": {"id": "prod4b", "t": "One-click Windows installer",
                 "p": "prod4", "done": False},
        "prod4c": {"id": "prod4c", "t": "Open in TradingView links",
                 "p": "prod4", "done": False},
        "biz": {"id": "biz", "t": "Business", "p": "tk", "done": False},
        "biz1": {"id": "biz1", "t": "Validation", "p": "biz", "done": False},
        "biz1a": {"id": "biz1a", "t": "Day-30 gate — the log is the pitch",
                 "p": "biz1", "done": False},
        "biz1b": {"id": "biz1b", "t": "Three warm yeses, £12 question",
                 "p": "biz1", "done": False},
        "biz2": {"id": "biz2", "t": "Money", "p": "biz", "done": False},
        "biz2a": {"id": "biz2a", "t": "£10 proof → £100 incorporate → monthly",
                 "p": "biz2", "done": False},
        "biz2b": {"id": "biz2b", "t": "Spent so far: £0",
                 "p": "biz2", "done": True},
        "biz2c": {"id": "biz2c", "t": "Revenue starts month 3 in the model",
                 "p": "biz2", "done": False},
        "biz3": {"id": "biz3", "t": "Legal", "p": "biz", "done": False},
        "biz3a": {"id": "biz3a", "t": "FCA bright line — descriptive only",
                 "p": "biz3", "done": False},
        "biz3b": {"id": "biz3b", "t": "Licensed feed before the paid tier",
                 "p": "biz3", "done": False},
        "biz3c": {"id": "biz3c", "t": "US perimeter check",
                 "p": "biz3", "done": False},
        "con": {"id": "con", "t": "Content", "p": "tk", "done": False},
        "con1": {"id": "con1", "t": "Website", "p": "con", "done": False},
        "con1a": {"id": "con1a", "t": "trendkept.com live",
                 "p": "con1", "done": True},
        "con1b": {"id": "con1b", "t": "Four free calculators",
                 "p": "con1", "done": True},
        "con1c": {"id": "con1c", "t": "OG image, sitemap, llm.txt",
                 "p": "con1", "done": True},
        "con2": {"id": "con2", "t": "Newsletter", "p": "con", "done": False},
        "con2a": {"id": "con2a", "t": "The Trend Check — live",
                 "p": "con2", "done": True},
        "con2b": {"id": "con2b", "t": "Sunday auto-draft action",
                 "p": "con2", "done": True},
        "con3": {"id": "con3", "t": "Drafts ready", "p": "con", "done": False},
        "con3a": {"id": "con3a", "t": "Essay: moving stops",
                 "p": "con3", "done": False},
        "con3b": {"id": "con3b", "t": "Essay: lookahead bias",
                 "p": "con3", "done": False},
        "con3c": {"id": "con3c", "t": "Welcome email",
                 "p": "con3", "done": False},
        "log": {"id": "log", "t": "Paper log", "p": "tk", "done": False},
        "log1": {"id": "log1", "t": "26 days recorded to 12 Aug",
                 "p": "log", "done": True},
        "log2": {"id": "log2", "t": "Rules kept on 24 of 26",
                 "p": "log", "done": True},
        "log3": {"id": "log3", "t": "Send photos — Vesper transcribes",
                 "p": "log", "done": False},
        "log4": {"id": "log4", "t": "Never backfill an unevidenced day",
                 "p": "log", "done": False},
        "log5": {"id": "log5", "t": "Day 30 unlocks the results post",
                 "p": "log", "done": False},
        "hl": {"id": "hl", "t": "Health", "p": "root", "done": False},
        "hl1": {"id": "hl1", "t": "The episode", "p": "hl", "done": False},
        "hl1a": {"id": "hl1a", "t": "Get the discharge summary + peak CK",
                 "p": "hl1", "done": False},
        "hl1b": {"id": "hl1b", "t": "Did my kidneys recover fully?",
                 "p": "hl1", "done": False},
        "hl1c": {"id": "hl1c", "t": "What triggered it — or was there no clear trigger?",
                 "p": "hl1", "done": False},
        "hl1d": {"id": "hl1d", "t": "Referral to look for an underlying cause?",
                 "p": "hl1", "done": False},
        "hl1e": {"id": "hl1e", "t": "What CK retest schedule do you want?",
                 "p": "hl1", "done": False},
        "hl2": {"id": "hl2", "t": "Red flags — A&E same day",
                 "p": "hl", "done": False},
        "hl2a": {"id": "hl2a", "t": "Dark urine, or passing much less",
                 "p": "hl2", "done": False},
        "hl2b": {"id": "hl2b", "t": "Muscle pain beyond what the session justifies",
                 "p": "hl2", "done": False},
        "hl2c": {"id": "hl2c", "t": "Swelling, weakness, nausea",
                 "p": "hl2", "done": False},
        "hl2d": {"id": "hl2d", "t": "Say: I have had rhabdomyolysis before",
                 "p": "hl2", "done": False},
        "hl3": {"id": "hl3", "t": "Prevention", "p": "hl", "done": False},
        "hl3a": {"id": "hl3a", "t": "Build up gradually — the trigger is the jump",
                 "p": "hl3", "done": False},
        "hl3b": {"id": "hl3b", "t": "Never train through illness or fever",
                 "p": "hl3", "done": False},
        "hl3c": {"id": "hl3c", "t": "Hydrate before, during, after",
                 "p": "hl3", "done": False},
        "hl3d": {"id": "hl3d", "t": "No hard sessions in heat",
                 "p": "hl3", "done": False},
        "hl3e": {"id": "hl3e", "t": "Check supplements and meds with the GP",
                 "p": "hl3", "done": False},
        "hl4": {"id": "hl4", "t": "Set up", "p": "hl", "done": False},
        "hl4a": {"id": "hl4a", "t": "Medical ID on the phone",
                 "p": "hl4", "done": False},
        "hl4b": {"id": "hl4b", "t": "Tell whoever I train with",
                 "p": "hl4", "done": False},
        "hl4c": {"id": "hl4c", "t": "Choose a wearable",
                 "p": "hl4", "done": False},
        "hl4d": {"id": "hl4d", "t": "Alerts to phone when something is off",
                 "p": "hl4", "done": False},
        "hl3f": {"id": "hl3f", "t": "Not training until cleared",
                 "p": "hl3", "done": False},
        "mk": {"id": "mk", "t": "Markets", "p": "root", "done": False},
        "mk1": {"id": "mk1", "t": "Watchlist", "p": "mk", "done": False},
        "mk1a": {"id": "mk1a", "t": "Symbols I actually follow",
                 "p": "mk1", "done": False},
        "mk1b": {"id": "mk1b", "t": "Why each one is on here",
                 "p": "mk1", "done": False},
        "mk2": {"id": "mk2", "t": "Positions & risk",
                 "p": "mk", "done": False},
        "mk2a": {"id": "mk2a", "t": "Account size and risk per trade",
                 "p": "mk2", "done": False},
        "mk2b": {"id": "mk2b", "t": "Open positions and where the stops are",
                 "p": "mk2", "done": False},
        "mk3": {"id": "mk3", "t": "What my rules say",
                 "p": "mk", "done": False},
        "mk3a": {"id": "mk3a", "t": "Trend filter: 50/200, higher highs",
                 "p": "mk3", "done": False},
        "mk3b": {"id": "mk3b", "t": "Stop goes in with the entry",
                 "p": "mk3", "done": False},
        "mk3c": {"id": "mk3c", "t": "Most days the answer is do nothing",
                 "p": "mk3", "done": False},
        "mk4": {"id": "mk4", "t": "Macro worth watching",
                 "p": "mk", "done": False},
        "mk4a": {"id": "mk4a", "t": "Rates, inflation prints, earnings season",
                 "p": "mk4", "done": False},
        "mk5": {"id": "mk5", "t": "Never: predictions, tips, should-I-buy",
                 "p": "mk", "done": False},
        "nw": {"id": "nw", "t": "News & weather", "p": "root", "done": False},
        "nw1": {"id": "nw1", "t": "Feeds I follow", "p": "nw", "done": False},
        "nw2": {"id": "nw2", "t": "Watch words that interrupt me",
                 "p": "nw", "done": False},
        "nw3": {"id": "nw3", "t": "Weather where I am",
                 "p": "nw", "done": False},
        "nw4": {"id": "nw4", "t": "Today's brief", "p": "nw", "done": False},
        "me": {"id": "me", "t": "Personal", "p": "root", "done": False},
        "me1": {"id": "me1", "t": "Ideas", "p": "me", "done": False},
        "me2": {"id": "me2", "t": "To do", "p": "me", "done": False},
        "me3": {"id": "me3", "t": "Notes", "p": "me", "done": False},
    },
    "links": [
        ["hl4c", "hl4d"],
        ["mk3a", "prod1a"],
        ["nw2", "nw4"],
        ["biz1a", "log5"],
        ["con3a", "prod1b"],
        ["biz3a", "prod3a"],
        ["biz3b", "prod1"],
        ["con2b", "log1"],
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
        return json.loads(json.dumps(SEED))

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
