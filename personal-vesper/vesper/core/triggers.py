"""Situational awareness — the rules that decide when to wake the model.

This is deliberately a small, dumb list of `(name, condition, why)` rules
rather than anything clever. Cheap sensors update the world state hundreds
of times a minute; a rule here fires maybe twice a day. Everything you want
Vesper to *notice* goes in this file.

A rule firing does not mean Vesper speaks. It means the brain gets woken
with the reason, and the brain decides whether it is worth saying anything
(it has a `stay_silent` tool for exactly that).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .world_state import Change, Snapshot

LOG = logging.getLogger("vesper.triggers")

Condition = Callable[[Snapshot, List[Change]], bool]


@dataclass
class Rule:
    name: str
    condition: Condition
    why: str
    # Rules are individually rate-limited: "someone is at the door" should be
    # able to fire often, "the stove has been on a while" should not.
    cooldown: float = 300.0
    last_fired: float = field(default=0.0, repr=False)

    def ready(self, now: float) -> bool:
        return now - self.last_fired >= self.cooldown


@dataclass
class Fired:
    rule: Rule
    why: str


def _changed(changes: List[Change], key: str) -> Optional[Change]:
    for c in changes:
        if c.key == key:
            return c
    return None


# --------------------------------------------------------------------------
# The rules themselves. Add to this list — that's the extension point.
# --------------------------------------------------------------------------

def _unknown_person_appeared(snap: Snapshot, changes: List[Change]) -> bool:
    change = _changed(changes, "people")
    if not change:
        return False
    before = set(change.old or [])
    after = set(change.new or [])
    return "unknown" in after - before


def _unknown_person_at_night(snap: Snapshot, changes: List[Change]) -> bool:
    return (_unknown_person_appeared(snap, changes)
            and snap.get("time_of_day") == "night")


def _someone_arrived(snap: Snapshot, changes: List[Change]) -> bool:
    change = _changed(changes, "people")
    if not change:
        return False
    return not (change.old or []) and bool(change.new or [])


def _everyone_left(snap: Snapshot, changes: List[Change]) -> bool:
    change = _changed(changes, "people")
    if not change:
        return False
    return bool(change.old or []) and not (change.new or [])


def _appliance_left_on_unattended(snap: Snapshot, changes: List[Change]) -> bool:
    """A hot appliance on, and nothing has moved for 20 minutes."""
    devices = snap.devices
    hot = [name for name, v in devices.items()
           if str(v).lower() in ("on", "heat", "true")
           and any(word in name.lower()
                   for word in ("stove", "oven", "hob", "cooker", "iron",
                                "heater", "grill"))]
    if not hot:
        return False
    idle = snap.seconds_since_motion()
    return idle is not None and idle > 20 * 60


def _door_open_and_nobody_home(snap: Snapshot, changes: List[Change]) -> bool:
    devices = snap.devices
    open_doors = [n for n, v in devices.items()
                  if "door" in n.lower() and str(v).lower() in ("open", "on", "true")]
    return bool(open_doors) and not snap.people


def _major_news_broke(snap: Snapshot, changes: List[Change]) -> bool:
    """A *newly arrived* headline matching one of the watch words.

    Two conditions, both necessary. Only headlines that weren't in the last
    poll count, or the same story re-fires every fifteen minutes for as long
    as it stays on the front page. And it has to match a watch word, because
    otherwise this is just "the news changed", which it always has.
    """
    change = _changed(changes, "headlines")
    if not change:
        return False
    before = {str(h).lower() for h in (change.old or [])}
    fresh = [str(h) for h in (change.new or []) if str(h).lower() not in before]
    if not fresh:
        return False
    words = [w.strip().lower() for w in (WATCH_WORDS or "").split(",") if w.strip()]
    if not words:
        return False
    return any(w in h.lower() for h in fresh for w in words)


# Set from config at startup by `configure_watch_words`. Module-level so the
# rule stays a plain function with the same signature as every other one.
WATCH_WORDS = ""


def configure_watch_words(words: str) -> None:
    global WATCH_WORDS
    WATCH_WORDS = words or ""


# Set from config at startup, like WATCH_WORDS.
LOAD_SIGMAS = 2.5


def configure_health(load_sigmas: float) -> None:
    global LOAD_SIGMAS
    LOAD_SIGMAS = load_sigmas


def _dev(snap: Snapshot, metric: str) -> Optional[dict]:
    return (snap.get("health") or {}).get(metric)


def _exertion_spike(snap: Snapshot, changes: List[Change]) -> bool:
    """Today's effort far outside your recent normal.

    This is the one worth catching early: the trigger for exertional trouble
    is the jump, not the absolute effort — an ordinary session for someone
    else can be a huge one for you this week.
    """
    if not _changed(changes, "health"):
        return False
    load = _dev(snap, "load")
    return bool(load and load.get("sigmas", 0) >= LOAD_SIGMAS)


def _strained_after_effort(snap: Snapshot, changes: List[Change]) -> bool:
    """Recovery markers unfavourable on two fronts at once.

    One metric drifting is noise. Resting heart rate up *and* HRV down is
    the pattern worth a look, and it is still only a prompt to check the
    symptoms — never a conclusion about what is happening.
    """
    if not _changed(changes, "health"):
        return False
    hr, hrv = _dev(snap, "resting_hr"), _dev(snap, "hrv")
    bad = [d for d in (hr, hrv) if d and d.get("unfavourable")
           and abs(d.get("sigmas", 0)) >= 1.5]
    return len(bad) >= 2


DEFAULT_RULES: List[Rule] = [
    Rule(
        name="exertion_spike",
        condition=_exertion_spike,
        why=("Today's exertion is far above this user's recent normal. Call "
             "read_body, tell them plainly how far outside their range it "
             "was, and ask the symptom questions — muscle pain beyond what "
             "the session justifies, urine colour, how much they have drunk. "
             "Log whatever they answer with log_symptom. Do not diagnose."),
        cooldown=6 * 3600,
    ),
    Rule(
        name="strained_after_effort",
        condition=_strained_after_effort,
        why=("Resting heart rate and HRV are both unfavourable against this "
             "user's own baseline. Call read_body, say what the numbers are "
             "doing in one sentence, and ask how they actually feel. This is "
             "a prompt to check, not a finding — say so."),
        cooldown=12 * 3600,
    ),
    Rule(
        name="major_news",
        condition=_major_news_broke,
        why=("A new headline matching the user's watch words has appeared. "
             "Look at the headlines in the world summary. Mention it ONLY if "
             "it is genuinely significant and they would want interrupting — "
             "a routine story, or anything they have likely already seen, is "
             "a stay_silent. One sentence if you do speak."),
        cooldown=1800.0,
    ),
    Rule(
        name="unknown_person_at_night",
        condition=_unknown_person_at_night,
        why=("An unidentified person appeared on camera and it is night. "
             "Decide whether this warrants alerting the user."),
        cooldown=120.0,
    ),
    Rule(
        name="unknown_person",
        condition=_unknown_person_appeared,
        why="An unidentified person appeared on camera.",
        cooldown=600.0,
    ),
    Rule(
        name="someone_arrived",
        condition=_someone_arrived,
        why=("Someone has just come into view after the room was empty. "
             "A short greeting may be appropriate; say nothing if not."),
        cooldown=900.0,
    ),
    Rule(
        name="everyone_left",
        condition=_everyone_left,
        why=("The room has just emptied. Consider whether anything should be "
             "turned off, but do not act without good reason."),
        cooldown=900.0,
    ),
    Rule(
        name="appliance_unattended",
        condition=_appliance_left_on_unattended,
        why=("A heat-producing appliance is on and there has been no motion "
             "for over twenty minutes. This is worth mentioning."),
        cooldown=900.0,
    ),
    Rule(
        name="door_open_nobody_home",
        condition=_door_open_and_nobody_home,
        why="A door is open and nobody is visible.",
        cooldown=600.0,
    ),
]


class TriggerEngine:
    def __init__(self, rules: Optional[List[Rule]] = None,
                 global_cooldown: float = 120.0) -> None:
        self.rules = list(rules if rules is not None else DEFAULT_RULES)
        self.global_cooldown = global_cooldown
        self._last_any = 0.0

    def add(self, rule: Rule) -> None:
        self.rules.append(rule)

    def evaluate(self, snap: Snapshot, changes: List[Change],
                 now: Optional[float] = None) -> Optional[Fired]:
        """First matching, off-cooldown rule wins.

        Order matters: put the specific rules above the general ones, so
        "unknown person at night" beats plain "unknown person".
        """
        now = time.time() if now is None else now
        if now - self._last_any < self.global_cooldown:
            return None

        for rule in self.rules:
            if not rule.ready(now):
                continue
            try:
                hit = rule.condition(snap, changes)
            except Exception:
                LOG.exception("trigger %s raised; skipping", rule.name)
                continue
            if hit:
                rule.last_fired = now
                self._last_any = now
                LOG.info("trigger fired: %s", rule.name)
                return Fired(rule=rule, why=rule.why)
        return None
