"""What Vesper actually remembers about you, between conversations.

The session history in `brain.py` holds the last twenty turns and then
forgets. That is the difference between a chatbot and an assistant: tell a
chatbot on Monday that you train on Tuesdays and Thursdays, and by Friday
it has never heard of you.

Three kinds of memory, which is the split the literature settles on and
which turns out to matter in practice because they are RETRIEVED
differently:

  * SEMANTIC — facts that stay true. "Risk per trade is 1%." "Trains
    Tuesdays and Thursdays." Retrieved by subject.
  * EPISODIC — things that happened, with a date. "Bought V at 362.85 on
    17 July." Retrieved by recency and by subject.
  * STANDING — instructions that change how Vesper behaves. "Never tell me
    the price without the trend." Retrieved ALWAYS, because an instruction
    you have to be reminded of is not an instruction.

Deliberately NOT a vector database. This runs on a ThinkPad with 16GB
beside a speech model, and an embedding model would be a second process,
a second dependency and a second thing to break — for a store that will
hold a few thousand short lines. Scored retrieval over the actual words
is what fits the machine, and at this size it is also more predictable:
you can read the file and know exactly what it will find.

Every write goes through `save()`, which writes a temporary file and
renames it. A half-written memory is worse than an old one.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("vesper.memory")

KINDS = ("semantic", "episodic", "standing")

#: Words too common to tell two memories apart. Kept small on purpose —
#: over-filtering loses the words that actually carry the subject.
_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that",
    "this", "these", "those", "is", "are", "was", "were", "be", "been",
    "being", "am", "do", "does", "did", "have", "has", "had", "i", "me",
    "my", "you", "your", "it", "its", "of", "in", "on", "at", "to", "for",
    "with", "from", "by", "about", "as", "so", "not", "no", "yes", "what",
    "when", "where", "who", "how", "why", "can", "could", "would", "should",
    "will", "shall", "may", "might", "must", "just", "very", "really",
    "sir", "please", "thanks", "thank",
}

_WORD = re.compile(r"[a-z0-9][a-z0-9'’\-\.]*")


def _terms(text: str) -> List[str]:
    """The words worth matching on, lowercased and de-duplicated in order."""
    out, seen = [], set()
    for w in _WORD.findall((text or "").lower()):
        w = w.strip(".'’-")
        if len(w) < 2 or w in _STOP or w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out


def _looks_like_a_fact(text: str) -> bool:
    """Cheap guard against storing conversational noise as knowledge."""
    t = (text or "").strip()
    if len(t) < 8 or len(t) > 400:
        return False
    # A question is something the user wanted answered, not something known.
    return not t.endswith("?")


class Memory:
    """A small, readable, on-disk store of what Vesper knows about you."""

    def __init__(self, path: Path, limit: int = 2000) -> None:
        self.path = Path(path)
        self.limit = limit
        self._lock = threading.RLock()
        self.items: List[Dict[str, Any]] = self._load()

    # -- disk -------------------------------------------------------------

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            LOG.error("could not read memory (%s); starting empty", exc)
            return []
        if not isinstance(raw, list):
            return []
        out = []
        for it in raw:
            if isinstance(it, dict) and it.get("text"):
                it.setdefault("kind", "semantic")
                it.setdefault("at", time.time())
                it.setdefault("uses", 0)
                out.append(it)
        return out

    def save(self) -> None:
        with self._lock:
            payload = json.dumps(self.items, indent=1, ensure_ascii=False)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            LOG.error("could not write memory: %s", exc)

    # -- writing ----------------------------------------------------------

    def remember(self, text: str, kind: str = "semantic",
                 source: str = "said") -> Optional[dict]:
        """Store one thing. Returns the item, or None if it was rejected.

        Near-duplicates REPLACE rather than accumulate. Without that, a
        fact mentioned weekly becomes fifty near-identical lines that
        crowd everything else out of retrieval — the store slowly fills
        with its own echo.
        """
        text = " ".join((text or "").split())
        if not _looks_like_a_fact(text):
            return None
        if kind not in KINDS:
            kind = "semantic"

        with self._lock:
            twin = self._closest(text, kind)
            if twin is not None:
                twin["text"] = text          # the newer wording wins
                twin["at"] = time.time()
                twin["uses"] = twin.get("uses", 0) + 1
                self.save()
                return twin

            item = {"text": text, "kind": kind, "source": source,
                    "at": time.time(), "uses": 0}
            self.items.append(item)
            self._prune()
        self.save()
        return item

    def _closest(self, text: str, kind: str) -> Optional[dict]:
        """An existing memory saying substantially the same thing."""
        want = set(_terms(text))
        if not want:
            return None
        for it in self.items:
            if it.get("kind") != kind:
                continue
            have = set(_terms(it.get("text", "")))
            if not have:
                continue
            overlap = len(want & have) / max(len(want | have), 1)
            if overlap >= 0.7:
                return it
        return None

    def forget(self, needle: str) -> int:
        """Drop everything matching. Returns how many went."""
        want = set(_terms(needle))
        if not want:
            return 0
        with self._lock:
            before = len(self.items)
            self.items = [
                it for it in self.items
                if not want <= set(_terms(it.get("text", "")))]
            gone = before - len(self.items)
        if gone:
            self.save()
        return gone

    def _prune(self) -> None:
        """Keep the store bounded, dropping the least useful first.

        Standing instructions are never pruned. They are the smallest
        group and the most expensive to lose — forgetting how you want to
        be spoken to is worse than forgetting a fact you can be told again.
        """
        if len(self.items) <= self.limit:
            return
        keep_always = [i for i in self.items if i.get("kind") == "standing"]
        rest = [i for i in self.items if i.get("kind") != "standing"]
        rest.sort(key=lambda i: (i.get("uses", 0), i.get("at", 0)),
                  reverse=True)
        self.items = keep_always + rest[:max(self.limit - len(keep_always), 0)]

    # -- reading ----------------------------------------------------------

    def recall(self, query: str, limit: int = 8) -> List[dict]:
        """The memories worth putting in front of the model for this turn.

        Standing instructions always come first and always come back;
        everything else is scored on shared words, then nudged by recency
        and by how often it has proved useful before.
        """
        with self._lock:
            standing = [i for i in self.items if i.get("kind") == "standing"]
            others = [i for i in self.items if i.get("kind") != "standing"]

        want = set(_terms(query))
        now = time.time()
        scored = []
        for it in others:
            have = set(_terms(it.get("text", "")))
            if not (want and have):
                continue
            shared = len(want & have)
            if not shared:
                continue
            # Proportion of the QUESTION covered, not of the memory: a long
            # memory should not be penalised for containing extra detail.
            score = shared / len(want)
            age_days = max((now - it.get("at", now)) / 86400.0, 0.0)
            score *= 1.0 / (1.0 + age_days / 45.0)     # gentle decay
            score *= 1.0 + min(it.get("uses", 0), 10) * 0.03
            if it.get("kind") == "episodic":
                score *= 0.9        # a fact outranks an anecdote, narrowly
            scored.append((score, it))

        scored.sort(key=lambda p: p[0], reverse=True)
        picked = [it for _s, it in scored[:max(limit - len(standing), 0)]]

        with self._lock:
            for it in picked:
                it["uses"] = it.get("uses", 0) + 1
        return standing + picked

    def block(self, query: str, limit: int = 8) -> str:
        """`recall`, rendered for a prompt. Empty string when nothing fits."""
        hits = self.recall(query, limit=limit)
        if not hits:
            return ""
        lines = ["What you already know about the user (from earlier "
                 "conversations — treat as true unless they correct you):"]
        for it in hits:
            when = time.strftime("%d %b", time.localtime(it.get("at", 0)))
            if it.get("kind") == "standing":
                lines.append(f"- STANDING INSTRUCTION: {it['text']}")
            elif it.get("kind") == "episodic":
                lines.append(f"- ({when}) {it['text']}")
            else:
                lines.append(f"- {it['text']}")
        return "\n".join(lines)

    def summary(self) -> str:
        with self._lock:
            n = len(self.items)
            by = {k: sum(1 for i in self.items if i.get("kind") == k)
                  for k in KINDS}
        return (f"{n} memories — {by['semantic']} facts, "
                f"{by['episodic']} events, {by['standing']} standing "
                f"instructions.")


# ── noticing things worth keeping ───────────────────────────────────────
#
# Memory only feels like intelligence if it is INVISIBLE. An assistant you
# have to say "remember this" to is a notebook with extra steps; the whole
# effect comes from it having quietly kept the thing you mentioned once,
# three weeks ago, in passing.
#
# Two ways to notice, and both earn their place:
#
#   * these patterns, which are free, instant, and run on every turn;
#   * a model pass (`extract_with`), which catches what patterns cannot,
#     and costs a call — so it runs occasionally, not per turn.

_STANDING = re.compile(
    r"\b(?:always|never|from now on|in future|stop|don'?t ever|"
    r"remember to|make sure (?:you|to)|i want you to|i'?d like you to|"
    r"call me|refer to me)\b", re.I)

_FACT = re.compile(
    r"\b(?:i(?:'|’)?m|i am|i was|my |mine |i have|i'?ve|i own|i use|"
    r"i live|i work|i trade|i train|i prefer|i like|i hate|i can'?t|"
    r"i don'?t|i never|i usually|i always|call me)\b", re.I)

_EVENT = re.compile(
    r"\b(?:yesterday|today|this morning|last night|last week|"
    r"just (?:did|had|been|got|bought|sold|finished)|"
    r"i (?:did|had|went|bought|sold|finished|started|saw|met))\b", re.I)


def notice(text: str) -> List[tuple]:
    """Things in one utterance worth keeping. Returns [(kind, text)].

    Conservative on purpose. A memory store that fills with noise is worse
    than an empty one: every wrong line crowds a right one out of
    retrieval, and the user has no idea why the answers got worse.
    """
    said = " ".join((text or "").split())
    if not _looks_like_a_fact(said):
        return []

    out = []
    # One utterance can carry two different things ("call me sir, and I
    # trade Visa") so each sentence is judged on its own.
    for part in re.split(r"(?<=[.!?])\s+|,\s+(?=and |but )", said):
        part = part.strip()
        if not _looks_like_a_fact(part):
            continue
        if _STANDING.search(part):
            out.append(("standing", part))
        elif _EVENT.search(part):
            out.append(("episodic", part))
        elif _FACT.search(part):
            out.append(("semantic", part))
    # If nothing matched sentence-by-sentence, judge the whole thing --
    # people write without punctuation more often than not.
    if not out:
        if _STANDING.search(said):
            out.append(("standing", said))
        elif _EVENT.search(said):
            out.append(("episodic", said))
        elif _FACT.search(said):
            out.append(("semantic", said))
    return out[:3]


EXTRACT_PROMPT = """From this exchange, list what is worth remembering \
about the user for months to come.

Rules:
- Only what is DURABLE. Not the answer you gave, not the weather today.
- One short third-person sentence each, readable on its own in a year.
- Mark each: FACT (stays true), EVENT (happened, dated), or \
STANDING (an instruction about how to behave).
- If there is nothing worth keeping, reply exactly: NOTHING
- At most three.

Format, one per line:
FACT: they risk 1% of the account per trade

The exchange:
USER: {user}
YOU: {reply}"""


def parse_extraction(raw: str) -> List[tuple]:
    """Read what the model listed. Ignores anything malformed."""
    out = []
    for line in (raw or "").splitlines():
        line = line.strip().lstrip("-•* ").strip()
        if not line or line.upper().startswith("NOTHING"):
            continue
        head, _, body = line.partition(":")
        kind = {"FACT": "semantic", "EVENT": "episodic",
                "STANDING": "standing"}.get(head.strip().upper())
        body = body.strip()
        if kind and _looks_like_a_fact(body):
            out.append((kind, body))
    return out[:3]
