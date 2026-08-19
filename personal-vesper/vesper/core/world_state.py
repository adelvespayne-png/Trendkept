"""The shared world-state — what Vesper currently believes about the room.

Cheap sensors write here continuously; the expensive model reads it only
when something needs reasoning. That split is the whole architecture: the
camera loop never calls the LLM, it just updates state and lets the trigger
rules decide whether anything is worth waking up for.

Thread-safe because the writers are ordinary threads (audio callbacks, the
camera loop) while the readers live in the asyncio loop.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

LOG = logging.getLogger("vesper.state")


@dataclass
class Change:
    """One field that moved, with both sides, so triggers can compare."""

    key: str
    old: Any
    new: Any

    def __repr__(self) -> str:  # pragma: no cover - debugging affordance
        return f"<{self.key}: {self.old!r} -> {self.new!r}>"


@dataclass
class Snapshot:
    """An immutable read of the world, safe to hand to a trigger or the LLM."""

    data: Dict[str, Any]
    at: float = field(default_factory=time.time)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def people(self) -> List[str]:
        return list(self.data.get("people", []))

    @property
    def objects(self) -> List[str]:
        return list(self.data.get("objects", []))

    @property
    def devices(self) -> Dict[str, Any]:
        return dict(self.data.get("devices", {}))

    @property
    def headlines(self) -> List[str]:
        return list(self.data.get("headlines", []))

    def seconds_since_motion(self) -> Optional[float]:
        last = self.data.get("last_motion_at")
        return None if last is None else self.at - last

    def describe(self, news: int = 6) -> str:
        """Plain-English world summary — this is what the LLM actually sees.

        `news` caps how many headlines are included. They ride along on every
        turn, so this is a direct trade of tokens for awareness; six is enough
        to know what today is about without paying for the whole front page.
        """
        bits: List[str] = []

        people = self.people
        if people:
            known = [p for p in people if p != "unknown"]
            unknown = len(people) - len(known)
            if known:
                bits.append("People visible: " + ", ".join(known) + ".")
            if unknown:
                bits.append(f"{unknown} unidentified "
                            f"{'person' if unknown == 1 else 'people'} visible.")
        elif self.data.get("vision_active"):
            bits.append("Nobody visible.")

        objects = [o for o in self.objects if o not in ("person",)]
        if objects:
            bits.append("Also in view: " + ", ".join(sorted(set(objects))) + ".")

        since = self.seconds_since_motion()
        if since is not None:
            bits.append(f"Last motion {int(since)}s ago.")

        devices = self.devices
        if devices:
            on = [name for name, v in devices.items()
                  if str(v).lower() in ("on", "true", "open", "heat", "playing")]
            bits.append("Devices on: " + (", ".join(sorted(on)) if on else "none")
                        + f" (of {len(devices)} known).")

        if self.data.get("time_of_day"):
            bits.append(f"It is {self.data['time_of_day']}.")

        summary = " ".join(bits) if bits else "No sensor data yet."

        heads = self.headlines[:news] if news else []
        if heads:
            age = self.data.get("headlines_at")
            when = ""
            if age:
                mins = int((self.at - age) / 60)
                when = f" (fetched {mins} min ago)" if mins else " (just now)"
            summary += ("\n\nHeadlines today" + when + ":\n"
                        + "\n".join("- " + h for h in heads))
        return summary


class WorldState:
    """A thread-safe dict with change detection and a JSON snapshot on disk."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {
            "people": [],
            "objects": [],
            "last_motion_at": None,
            "devices": {},
            "vision_active": False,
            "conversation": [],
            "time_of_day": None,
        }
        self._path = path
        self._listeners: List[Callable[[List[Change], Snapshot], None]] = []
        self._last_seen: Dict[str, Any] = dict(self._data)

    # -- reading ----------------------------------------------------------

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(json.loads(json.dumps(self._data, default=str)))

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    # -- writing ----------------------------------------------------------

    def update(self, **fields: Any) -> List[Change]:
        """Set fields; return only the ones that actually changed.

        Sensors call this on every tick, so the no-op case has to be cheap
        and silent — otherwise the triggers fire on every frame.
        """
        changes: List[Change] = []
        with self._lock:
            for key, new in fields.items():
                old = self._data.get(key)
                if _same(old, new):
                    continue
                self._data[key] = new
                changes.append(Change(key, old, new))
            snap = Snapshot(json.loads(json.dumps(self._data, default=str)))

        if changes:
            LOG.debug("state changed: %s", ", ".join(c.key for c in changes))
            self._notify(changes, snap)
            self._persist(snap)
        return changes

    def touch_motion(self) -> None:
        self.update(last_motion_at=time.time())

    def set_device(self, entity: str, value: Any) -> List[Change]:
        with self._lock:
            devices = dict(self._data.get("devices", {}))
            devices[entity] = value
        return self.update(devices=devices)

    def append_conversation(self, role: str, text: str, keep: int = 40) -> None:
        with self._lock:
            convo = list(self._data.get("conversation", []))
            convo.append({"role": role, "text": text, "at": time.time()})
            self._data["conversation"] = convo[-keep:]

    # -- diffing ----------------------------------------------------------

    def diff(self) -> List[Change]:
        """Changes since the last call to diff().

        Triggers use this rather than the live listener when they want to
        reason about a batch of movement rather than each individual write.
        """
        with self._lock:
            out: List[Change] = []
            for key, new in self._data.items():
                old = self._last_seen.get(key)
                if not _same(old, new):
                    out.append(Change(key, old, new))
            self._last_seen = json.loads(json.dumps(self._data, default=str))
        return out

    # -- listeners --------------------------------------------------------

    def subscribe(self, fn: Callable[[List[Change], Snapshot], None]) -> None:
        self._listeners.append(fn)

    def _notify(self, changes: List[Change], snap: Snapshot) -> None:
        for fn in list(self._listeners):
            try:
                fn(changes, snap)
            except Exception:
                # A broken listener must never take down a sensor thread.
                LOG.exception("state listener failed")

    def _persist(self, snap: Snapshot) -> None:
        if not self._path:
            return
        try:
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(snap.data, indent=1, default=str),
                           encoding="utf-8")
            tmp.replace(self._path)
        except OSError as exc:
            LOG.warning("could not write state file: %s", exc)


def _same(a: Any, b: Any) -> bool:
    """Equality that treats lists of labels as unordered sets.

    YOLO returns detections in confidence order, which reshuffles constantly
    even when the room is still. Without this, every frame looks like news.
    """
    if isinstance(a, list) and isinstance(b, list):
        try:
            return sorted(map(str, a)) == sorted(map(str, b))
        except TypeError:
            pass
    return a == b
