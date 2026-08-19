"""The clock — keeps the world state's sense of time current.

Small but load-bearing. `time_of_day` used to be written only by the vision
loop, so on a machine with the camera off it was set once at startup and then
never again: leave Vesper running from breakfast and at midnight it still
believed it was morning, and every rule keyed on "night" was dead.

This ticks once a minute, costs nothing, and is what makes time-of-day rules
work on a long-running daemon.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from ..config import CONFIG, Config
from ..core.world_state import WorldState

LOG = logging.getLogger("vesper.clock")


def time_of_day(now: Optional[time.struct_time] = None) -> str:
    hour = (now or time.localtime()).tm_hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


class Clock:
    def __init__(self, state: WorldState, cfg: Config = CONFIG,
                 interval: float = 60.0) -> None:
        self.state = state
        self.cfg = cfg
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def tick(self) -> None:
        now = time.localtime()
        # Only `time_of_day` and the date are written. Writing the clock
        # minute-by-minute would mark the state changed sixty times an hour
        # and wake the triggers for nothing.
        self.state.update(
            time_of_day=time_of_day(now),
            date=time.strftime("%Y-%m-%d", now),
            weekday=time.strftime("%A", now),
        )

    def start(self) -> bool:
        self.tick()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="clock",
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._stop.wait(self.interval)
            if not self._stop.is_set():
                self.tick()
