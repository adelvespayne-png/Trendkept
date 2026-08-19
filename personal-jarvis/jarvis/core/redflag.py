"""Red flags — the one path that never asks a model anything.

Everything else in Jarvis is a model deciding what to say. This is not. If a
logged symptom matches a rule here, the instruction that comes out is fixed
text from a table, produced by an `if`.

That is deliberate. Models are wrong sometimes, and the cost of being wrong
on the other paths is a poor answer. Here it would be someone not going to
hospital. So this runs as plain code, works with no API key, no network and
no provider, and the model is only allowed to read the result aloud — never
to reword it, weigh it up, or decide it doesn't apply.

The symptom list is configuration, not code: what counts as a red flag is a
matter for you and your doctor, and it lives in your own `.env`.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

LOG = logging.getLogger("jarvis.redflag")

URGENT = "urgent"
WATCH = "watch"

# Wording is fixed. `urgent` says where to go and when, with no hedging,
# because "you may wish to consider" is how people talk themselves out of it.
ADVICE = {
    URGENT: ("That is on your red-flag list. Go to A&E today — not tomorrow. "
             "Tell them what you have logged and that you have had "
             "rhabdomyolysis before."),
    WATCH: ("That is on your watch list. Keep drinking, stop training, and "
            "if it worsens or you notice anything on the red-flag list, "
            "go to A&E."),
}


class SymptomLog:
    """Append-only, on your machine. Nothing here is ever sent anywhere."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def add(self, text: str, level: str) -> dict:
        entry = {"at": time.time(),
                 "when": time.strftime("%Y-%m-%d %H:%M"),
                 "text": text, "level": level}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError as exc:
            LOG.error("could not write the symptom log: %s", exc)
        return entry

    def recent(self, hours: float = 72) -> List[dict]:
        if not self.path.is_file():
            return []
        cutoff = time.time() - hours * 3600
        out = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("at", 0) >= cutoff:
                    out.append(rec)
        except OSError:
            return []
        return out


def _matches(text: str, rule: str) -> bool:
    """One rule against the text.

    A rule is groups joined by `+`, alternatives within a group by `|`:

        urine|pee|wee + dark|brown|cola|tea

    means "some word for urine AND some word for the wrong colour". Plain
    substring matching is not enough here — nobody says "dark urine", they
    say "my urine is dark brown" or "weeing brown". Word order must not
    decide whether a red flag is caught.
    """
    for group in rule.split("+"):
        alts = [a.strip() for a in group.split("|") if a.strip()]
        if not alts:
            continue
        if not any(a in text for a in alts):
            return False
    return True


def _rules(spec: str) -> List[str]:
    return [r.strip().lower() for r in (spec or "").split(",") if r.strip()]


def classify(text: str, urgent_terms: str, watch_terms: str) -> Optional[str]:
    """Match a reported symptom against the two configured lists.

    Urgent is checked first: anything hitting both lists is urgent. The
    matching stays deliberately simple — a cleverer matcher is one that can
    be clever in the wrong direction, and the wrong direction here is a
    missed red flag.
    """
    t = " " + " ".join((text or "").lower().split()) + " "
    if not t.strip():
        return None
    for rule in _rules(urgent_terms):
        if _matches(t, rule):
            return URGENT
    for rule in _rules(watch_terms):
        if _matches(t, rule):
            return WATCH
    return None


def instruction(level: Optional[str]) -> str:
    """The fixed words for a level. No model involved at any point."""
    if level in ADVICE:
        return ADVICE[level]
    return ("Nothing on your lists matched that. Log it anyway if it worries "
            "you, and trust your own judgement over mine.")


def check(text: str, cfg) -> Dict[str, Optional[str]]:
    """One call: classify, and return the fixed instruction with it."""
    level = classify(text, cfg.redflag_urgent, cfg.redflag_watch)
    return {"level": level, "instruction": instruction(level),
            "deterministic": True}
