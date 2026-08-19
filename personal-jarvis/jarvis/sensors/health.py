"""Exertion and recovery — a wearable's numbers, compared against your own.

    python -m jarvis.sensors.health            # fetch once and show the read
    python -m jarvis.sensors.health --history  # the baseline it has built

Like every other sensor here, this **never calls the LLM**. It fetches, keeps
a rolling history, and writes deviations into the world state.

The deviations are the point. A resting heart rate of 62 means nothing; 62
when yours is normally 53 means something. So nothing raw goes into the world
state — only "9 above your 14-day median", which is the only form in which
any of it is useful.

Backends:
  file    a JSON or CSV file you drop in — works with any device that can
          export, and is the one that cannot break
  oura    Oura's v2 API (a personal access token)
  none    off

Nothing here interprets. It reports numbers against your own baseline and
lets the rules in `core/triggers.py` decide whether to say anything.
"""

from __future__ import annotations

import csv
import json
import logging
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from ..config import CONFIG, Config, setup_logging
from ..core.world_state import WorldState

LOG = logging.getLogger("jarvis.health")

# What we track. Each is a daily number; the baseline is per-metric.
METRICS = ("resting_hr", "hrv", "sleep_hours", "temp_delta", "load")

# Which direction is the concerning one, so a deviation can be described
# without the model having to work it out.
WORSE_WHEN_HIGH = {"resting_hr", "temp_delta", "load"}


class Baseline:
    """Your own normal, kept on disk, so today can be compared to it."""

    def __init__(self, path: Path, days: int = 14) -> None:
        self.path = Path(path)
        self.days = days
        self.history: List[dict] = self._load()

    def _load(self) -> List[dict]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError) as exc:
            LOG.warning("could not read health history (%s); starting fresh", exc)
            return []

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.history[-120:], indent=1),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            LOG.error("could not write health history: %s", exc)

    def add(self, reading: dict) -> None:
        """One reading per day; a repeat for the same day replaces it."""
        day = reading.get("day") or time.strftime("%Y-%m-%d")
        reading["day"] = day
        self.history = [r for r in self.history if r.get("day") != day]
        self.history.append(reading)
        self.history.sort(key=lambda r: r.get("day", ""))
        self.save()

    def median(self, metric: str) -> Optional[float]:
        vals = self._recent(metric)
        return statistics.median(vals) if len(vals) >= 3 else None

    def spread(self, metric: str) -> Optional[float]:
        """Median absolute deviation — robust to the one wild day."""
        vals = self._recent(metric)
        if len(vals) < 4:
            return None
        med = statistics.median(vals)
        mad = statistics.median([abs(v - med) for v in vals])
        return mad or None

    def _recent(self, metric: str) -> List[float]:
        # Yesterday backwards: today is what we're comparing, not part of
        # the baseline, or a bad day quietly raises its own normal.
        rows = self.history[:-1][-self.days:] if len(self.history) > 1 else []
        return [float(r[metric]) for r in rows
                if isinstance(r.get(metric), (int, float))]

    def deviation(self, metric: str, value: float) -> Optional[dict]:
        med = self.median(metric)
        if med is None:
            return None
        spread = self.spread(metric)
        delta = value - med
        out = {"value": round(value, 2), "median": round(med, 2),
               "delta": round(delta, 2)}
        if spread:
            out["sigmas"] = round(delta / spread, 2)
        out["direction"] = "above" if delta > 0 else "below"
        worse = ((metric in WORSE_WHEN_HIGH and delta > 0)
                 or (metric not in WORSE_WHEN_HIGH and delta < 0))
        out["unfavourable"] = bool(worse)
        return out


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------

def _from_file(cfg: Config) -> Optional[dict]:
    """Whatever your device exports, dropped in as JSON or CSV.

    The path that cannot break: no API, no token, no vendor. If a CSV, the
    last row wins and the column names are the metric names.
    """
    path = Path(cfg.health_file)
    if not path.is_file():
        LOG.warning("no health file at %s", path)
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".csv":
            rows = list(csv.DictReader(text.splitlines()))
            raw = rows[-1] if rows else {}
        else:
            data = json.loads(text)
            raw = data[-1] if isinstance(data, list) and data else data
    except (OSError, ValueError, IndexError) as exc:
        LOG.error("could not read %s: %s", path, exc)
        return None

    out: Dict[str, float] = {}
    for m in METRICS:
        v = raw.get(m)
        if v not in (None, ""):
            try:
                out[m] = float(v)
            except (TypeError, ValueError):
                pass
    if raw.get("day"):
        out["day"] = raw["day"]
    return out or None


def _from_oura(cfg: Config) -> Optional[dict]:
    """Oura v2. UNVERIFIED — written from their documentation, not from a
    call I have watched succeed. If the shapes have moved, the file backend
    still works and this is the only thing that needs correcting."""
    if not cfg.oura_token:
        LOG.warning("OURA_TOKEN is unset")
        return None
    today = time.strftime("%Y-%m-%d")
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() - 3 * 86400))

    def get(endpoint: str):
        url = (f"https://api.ouraring.com/v2/usercollection/{endpoint}"
               f"?start_date={start}&end_date={today}")
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + cfg.oura_token})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()).get("data", [])

    out: Dict[str, float] = {}
    try:
        sleep = get("daily_sleep")
        readiness = get("daily_readiness")
        activity = get("daily_activity")
    except Exception as exc:
        LOG.error("Oura fetch failed: %s", exc)
        return None

    if sleep:
        last = sleep[-1]
        contrib = last.get("contributors", {}) or {}
        if last.get("day"):
            out["day"] = last["day"]
        total = last.get("total_sleep_duration") or contrib.get("total_sleep")
        if isinstance(total, (int, float)) and total > 100:
            out["sleep_hours"] = round(total / 3600, 2)
    if readiness:
        last = readiness[-1]
        contrib = last.get("contributors", {}) or {}
        for src, dest in (("hrv_balance", "hrv"),
                          ("resting_heart_rate", "resting_hr")):
            v = contrib.get(src)
            if isinstance(v, (int, float)):
                out[dest] = float(v)
        t = last.get("temperature_deviation")
        if isinstance(t, (int, float)):
            out["temp_delta"] = float(t)
    if activity:
        last = activity[-1]
        for key in ("active_calories", "steps"):
            v = last.get(key)
            if isinstance(v, (int, float)):
                out["load"] = float(v)
                break
    return out or None


BACKENDS = {"file": _from_file, "oura": _from_oura}


# --------------------------------------------------------------------------


class HealthFeed:
    def __init__(self, state: WorldState, cfg: Config = CONFIG) -> None:
        self.state = state
        self.cfg = cfg
        self.backend = (cfg.health_backend or "none").lower()
        self.available = self.backend in BACKENDS
        self.baseline = Baseline(Path(cfg.health_history), cfg.health_baseline_days)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def poll_once(self) -> Optional[dict]:
        if not self.available:
            return None
        reading = BACKENDS[self.backend](self.cfg)
        if not reading:
            return None
        self.baseline.add(dict(reading))
        return self.read(reading)

    def read(self, reading: dict) -> dict:
        """Turn today's raw numbers into deviations from your own normal."""
        out: Dict[str, dict] = {}
        for m in METRICS:
            if isinstance(reading.get(m), (int, float)):
                dev = self.baseline.deviation(m, float(reading[m]))
                if dev:
                    out[m] = dev
        return out

    def push(self, deviations: dict) -> None:
        """Into the world state — deviations only, never the raw numbers."""
        self.state.update(health=deviations, health_at=time.time())

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        if not self.available:
            LOG.debug("health backend is %r; nothing to do", self.backend)
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="health",
                                        daemon=True)
        self._thread.start()
        LOG.info("health: %s backend, every %.0f min",
                 self.backend, self.cfg.health_interval / 60)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            devs = self.poll_once()
            if devs:
                self.push(devs)
            self._stop.wait(self.cfg.health_interval)


def describe(deviations: dict) -> str:
    """Plain English, comparative, no interpretation."""
    if not deviations:
        return ""
    names = {"resting_hr": "resting heart rate", "hrv": "HRV",
             "sleep_hours": "sleep", "temp_delta": "skin temperature",
             "load": "exertion"}
    bits = []
    for m, d in deviations.items():
        unit = "h" if m == "sleep_hours" else ""
        bits.append(f"{names.get(m, m)} {d['value']}{unit}, "
                    f"{abs(d['delta'])}{unit} {d['direction']} your "
                    f"{len(names) and ''}usual")
    return "Body: " + "; ".join(bits) + "."


def main(argv=None) -> int:
    setup_logging(CONFIG.log_level)
    feed = HealthFeed(WorldState(), CONFIG)

    if argv and "--history" in argv or "--history" in sys.argv:
        h = feed.baseline.history
        print(f"\n{len(h)} day(s) of history in {CONFIG.health_history}\n")
        for row in h[-14:]:
            print("  " + json.dumps(row))
        print("\nBaselines (median of the last "
              f"{CONFIG.health_baseline_days} days, today excluded):")
        for m in METRICS:
            med = feed.baseline.median(m)
            print(f"  {m:<12} {med if med is not None else '— not enough days yet'}")
        return 0

    if not feed.available:
        print("Health is off. Set HEALTH_BACKEND=file (and HEALTH_FILE), "
              "or =oura with an OURA_TOKEN.")
        return 1
    devs = feed.poll_once()
    if not devs:
        print(f"Nothing came back from the {feed.backend} backend.")
        print("With `file`, check the path and that the names match:",
              ", ".join(METRICS))
        return 1
    print("\nToday against your own baseline:\n")
    for m, d in devs.items():
        flag = "  <-- unfavourable" if d.get("unfavourable") else ""
        sig = f", {d['sigmas']} sigma" if "sigmas" in d else ""
        print(f"  {m:<12} {d['value']:>7}   median {d['median']:>7}   "
              f"{d['delta']:+}{sig}{flag}")
    print("\n" + describe(devs))
    print("\nThese numbers stay on this machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
