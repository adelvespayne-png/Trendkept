"""Red flags — the one path that never asks a model anything.

Everything else in Vesper is a model deciding what to say. This is not. If a
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

LOG = logging.getLogger("vesper.redflag")

EMERGENCY = "emergency"   # ambulance now
URGENT = "urgent"         # same-day assessment
CRISIS = "crisis"         # mental health, needs its own words
WATCH = "watch"           # note it, keep an eye

# Severity order, worst first. A report matching several lists takes the
# worst of them.
LEVELS = (EMERGENCY, CRISIS, URGENT, WATCH)

# Every word here is fixed. No hedging, no "you may wish to consider" —
# that is the phrasing people use to talk themselves out of going.
ADVICE = {
    EMERGENCY: ("Call 999 now. Do not drive yourself and do not wait to see "
                "if it settles. If you can, have someone with you until "
                "help arrives."),
    URGENT: ("That needs looking at today, not tomorrow. Go to A&E, or call "
             "111 if you are unsure which. Tell them what you have logged "
             "and any history you have."),
    CRISIS: ("Please talk to someone tonight. Samaritans are free on 116 123, "
             "any hour. If you are in immediate danger, call 999. I am not "
             "the right thing to carry this on your own with."),
    WATCH: ("Worth keeping an eye on. Stop training, keep drinking, and if it "
            "worsens or anything on the urgent list appears, get seen."),
}


def worst(levels) -> Optional[str]:
    """The most severe of several matches."""
    for lvl in LEVELS:
        if lvl in levels:
            return lvl
    return None


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


def classify(text: str, cfg) -> Optional[str]:
    """Match a report against every configured list, worst wins.

    The matching stays deliberately simple — a cleverer matcher is one that
    can be clever in the wrong direction, and the wrong direction here is a
    missed red flag.
    """
    t = " " + " ".join((text or "").lower().split()) + " "
    if not t.strip():
        return None
    lists = {
        EMERGENCY: cfg.redflag_emergency,
        CRISIS: cfg.redflag_crisis,
        URGENT: cfg.redflag_urgent,
        WATCH: cfg.redflag_watch,
    }
    hits = [lvl for lvl, spec in lists.items()
            if any(_matches(t, rule) for rule in _rules(spec))]
    return worst(hits)


def instruction(level: Optional[str]) -> str:
    """The fixed words for a level. No model involved at any point."""
    if level in ADVICE:
        return ADVICE[level]
    return ("Nothing on your lists matched that. Log it anyway if it worries "
            "you, and trust your own judgement over mine — I only know the "
            "words you have given me.")


#: Levels serious enough to leave the free gateway for. A sore leg is not
#: worth routing elsewhere; something that could put you in hospital is.
PRIVATE_LEVELS = (EMERGENCY, CRISIS, URGENT)


def check(text: str, cfg) -> Dict[str, Optional[str]]:
    """One call: classify, and return the fixed instruction with it."""
    level = classify(text, cfg)
    return {"level": level, "instruction": instruction(level),
            "private": level in PRIVATE_LEVELS,
            "deterministic": True}
