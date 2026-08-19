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


SEED = {
    "nodes": {
        "root": {"id": "root", "t": "Vesper", "p": None, "done": False},
        "tk": {"id": "tk", "t": "Trendkept", "p": "root", "done": False},
        "me": {"id": "me", "t": "Personal", "p": "root", "done": False},
        "me1": {"id": "me1", "t": "Ideas", "p": "me", "done": False},
        "me2": {"id": "me2", "t": "To do", "p": "me", "done": False},
        "me3": {"id": "me3", "t": "Notes", "p": "me", "done": False},
    },
    "links": [],
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
