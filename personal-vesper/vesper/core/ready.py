"""Speaking first, when there is something worth saying and you can hear it.

"Make the AI talk first when it knows I am ready." Two halves, and the
second is the one that decides whether this is a feature or an
irritation:

  * READY — you are at the machine and available. Cheap signals, no
    camera: the lid is open, something has been typed or clicked recently,
    the room is not silent.
  * WORTH IT — there is something you would rather hear than not. An
    assistant that greets you every time you sit down is a novelty for a
    day and a nuisance for a year.

The bar for speaking unprompted is deliberately high, and it is the same
bar the rest of the project uses for ambient events: say it only if the
user would thank you for the interruption. Three rules do most of the
work:

  * Never twice for the same thing.
  * Never within the quiet hours.
  * Never more than a few times a day, however much is happening.

Nothing here watches you. There is no camera and no keylogger; it reads
whether the session is idle, which is a number the operating system
already keeps.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

LOG = logging.getLogger("vesper.ready")


@dataclass
class Opening:
    """Something worth saying first, and the reason it qualifies."""

    key: str                 # what this is about; used to not repeat it
    text: str                # what to say
    why: str                 # for the log, and for explaining itself
    urgency: int = 1         # 1 ordinary, 2 worth interrupting for


def idle_seconds() -> Optional[float]:
    """How long since the user last touched this machine.

    Windows keeps this already (GetLastInputInfo), so on the ThinkPad it
    costs a syscall and no permissions. Elsewhere it returns None and the
    caller falls back to sound and the clock, which is why this is
    optional rather than required.
    """
    try:
        import ctypes

        class Info(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint),
                        ("dwTime", ctypes.c_uint)]

        info = Info()
        info.cbSize = ctypes.sizeof(Info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(millis / 1000.0, 0.0)
    except Exception:
        return None


class Readiness:
    """Decides when it is reasonable to speak without being asked."""

    def __init__(self, cfg, state=None) -> None:
        self.cfg = cfg
        self.state = state
        self.said: dict = {}          # key -> when it was last said
        self.spoken_today: List[float] = []
        self._was_away = True         # so the first arrival counts

    # -- the "are they there" half ----------------------------------------

    def present(self) -> bool:
        """Are they at the machine now?"""
        idle = idle_seconds()
        if idle is not None:
            return idle <= self.cfg.ready_idle_seconds
        # No idle clock (not Windows, or blocked). Fall back to whether the
        # room has any sound in it, which the world state already tracks.
        try:
            snap = self.state.snapshot() if self.state else None
            room = (snap.get("room") or {}) if snap else {}
            return bool(room.get("sound"))
        except Exception:
            return False

    def just_arrived(self) -> bool:
        """True once, on the transition from away to present.

        The transition is the moment worth speaking at. Being present is
        not: that is true for hours, and something that fires while it is
        true fires constantly.
        """
        here = self.present()
        arrived = here and self._was_away
        self._was_away = not here
        return arrived

    # -- the "is it worth it" half ----------------------------------------

    def quiet_hours(self, now: Optional[time.struct_time] = None) -> bool:
        now = now or time.localtime()
        start, end = self.cfg.quiet_from, self.cfg.quiet_until
        hour = now.tm_hour + now.tm_min / 60.0
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end      # a window over midnight

    def may_speak(self, key: str, urgency: int = 1) -> bool:
        """The three rules that keep this a feature rather than a nuisance."""
        if not self.cfg.proactive_enabled:
            return False
        now = time.time()

        # Never twice for the same thing.
        last = self.said.get(key)
        if last and now - last < self.cfg.ready_repeat_seconds:
            return False

        # Never in the quiet hours, unless it is genuinely urgent.
        if self.quiet_hours() and urgency < 2:
            return False

        # Never more than a few times a day, however much is happening.
        day = 24 * 3600
        self.spoken_today = [t for t in self.spoken_today if now - t < day]
        if len(self.spoken_today) >= self.cfg.ready_max_per_day and urgency < 2:
            return False
        return True

    def spoke(self, key: str) -> None:
        self.said[key] = time.time()
        self.spoken_today.append(time.time())

    # -- putting the two together -----------------------------------------

    def opening(self, sources: List[Callable[[], Optional[Opening]]]
                ) -> Optional[Opening]:
        """The one thing worth opening with, if anything is.

        Sources are asked in order and the FIRST that offers something
        wins. Not a digest of everything at once: a greeting that recites
        four items is a briefing nobody asked for, and the whole point is
        that this is the thing you would have wanted to know.
        """
        if not self.just_arrived():
            return None
        for source in sources:
            try:
                got = source()
            except Exception:
                LOG.debug("an opening source failed", exc_info=True)
                continue
            if got and self.may_speak(got.key, got.urgency):
                self.spoke(got.key)
                LOG.info("speaking first: %s", got.why)
                return got
        return None


# ── what is actually worth opening with ─────────────────────────────────
#
# Each of these returns an Opening or None. The bar is the same one the
# rest of the project uses for ambient events: say it only if the user
# would thank you for the interruption. Most of the time the honest answer
# is None, and a proactive assistant that usually says nothing is the only
# kind worth having.

def openings_for(vesper) -> List[Callable[[], Optional[Opening]]]:
    """The sources, in the order they get to speak."""

    def alert() -> Optional[Opening]:
        """Something fired while they were away and still matters."""
        pending = getattr(vesper, "pending_alert", None)
        if not pending:
            return None
        return Opening(key=f"alert:{pending[:40]}", text=pending,
                       why="an alert fired while they were away", urgency=2)

    def first_of_day() -> Optional[Opening]:
        """The first time today, and only if there is something in it."""
        now = time.localtime()
        if now.tm_hour >= 12:
            return None
        try:
            brain = getattr(vesper, "brain", None)
            mem = getattr(brain, "memory", None)
            if not mem:
                return None
            # Something they said they were doing today or tomorrow, told
            # to us yesterday or before. A greeting with nothing in it is
            # just noise with manners.
            hits = mem.recall("today tomorrow this morning plan meeting", 3)
            due = [h for h in hits if h.get("kind") == "episodic"]
            if not due:
                return None
            return Opening(
                key="first-of-day",
                text=f"Morning, sir. You mentioned {due[0]['text'].rstrip('.')}.",
                why="the first arrival of the day, with something pending")
        except Exception:
            return None

    def unfinished() -> Optional[Opening]:
        """A thread left open last time, worth picking back up."""
        try:
            brain = getattr(vesper, "brain", None)
            last = (getattr(brain, "history", None) or [])[-1:]
            if not last or last[0].get("role") != "assistant":
                return None
            text = str(last[0].get("content") or "")
            # Only if the last thing SHE said was a question -- that is a
            # thread genuinely left hanging, rather than a finished turn.
            if not text.rstrip().endswith("?"):
                return None
            return Opening(key="unfinished:" + text[:40],
                           text=f"Back to it, sir — {text}",
                           why="she asked something and never got an answer")
        except Exception:
            return None

    return [alert, first_of_day, unfinished]
