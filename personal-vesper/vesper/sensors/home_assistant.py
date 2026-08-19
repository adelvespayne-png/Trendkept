"""Smart home — optional Home Assistant REST client.

    python -m vesper.sensors.home_assistant     # prints your entities

Entirely optional and off by default. With HA_ENABLED unset the class still
constructs, reports `available = False`, and every method returns a polite
failure — so the rest of Vesper neither knows nor cares whether you own a
single smart plug.

It does two jobs:
  * polls entity states into the world state (so triggers can reason about
    "the hob is on and nobody has moved"), and
  * turns things on and off when Claude calls `set_device`.

Only entities whose domain is in `WATCHED_DOMAINS` are polled. A full HA
install exposes hundreds of entities — sun angles, battery percentages,
update sensors — and pushing all of that into the LLM's context every turn
is both expensive and useless.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

from ..config import CONFIG, Config, setup_logging
from ..core.world_state import WorldState

LOG = logging.getLogger("vesper.home")

# The domains worth telling the model about.
WATCHED_DOMAINS = ("light", "switch", "binary_sensor", "lock", "climate",
                   "fan", "cover", "media_player")

# Domains we are willing to switch. Notably absent: `lock`. Unlocking a door
# on a voice command that might have been the television is not a trade I am
# willing to make on your behalf — add it here yourself if you disagree.
CONTROLLABLE = ("light", "switch", "fan", "input_boolean")


class HomeAssistant:
    def __init__(self, cfg: Config = CONFIG,
                 state: Optional[WorldState] = None) -> None:
        self.cfg = cfg
        self.state = state
        self.available = False
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        if not cfg.ha_enabled:
            LOG.debug("home assistant disabled by config")
            return
        if not (cfg.ha_url and cfg.ha_token):
            LOG.warning("HA_ENABLED is true but HA_URL/HA_TOKEN are unset; "
                        "home control is off. See README step 9.")
            return
        self.base = cfg.ha_url.rstrip("/")
        if self._ping():
            self.available = True

    # -- transport --------------------------------------------------------

    def _request(self, path: str, payload: Optional[dict] = None,
                 timeout: float = 10.0):
        url = f"{self.base}/api/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url, data=data, method="POST" if data else "GET",
            headers={
                "Authorization": f"Bearer {self.cfg.ha_token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
        return json.loads(body) if body else None

    def _ping(self) -> bool:
        try:
            self._request("", timeout=5.0)
            LOG.info("home assistant reachable at %s", self.base)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                LOG.error("home assistant rejected the token (HTTP %s); "
                          "check HA_TOKEN", exc.code)
            else:
                LOG.error("home assistant returned HTTP %s", exc.code)
        except Exception as exc:
            LOG.error("could not reach home assistant at %s: %s", self.base, exc)
        return False

    # -- reading ----------------------------------------------------------

    def entities(self) -> Dict[str, str]:
        """`{entity_id: state}` for the watched domains only."""
        if not self.available:
            return {}
        try:
            raw = self._request("states") or []
        except Exception as exc:
            LOG.warning("could not read states: %s", exc)
            return {}
        out: Dict[str, str] = {}
        for item in raw:
            eid = item.get("entity_id", "")
            if eid.split(".", 1)[0] in WATCHED_DOMAINS:
                out[eid] = item.get("state", "unknown")
        return out

    def friendly_names(self) -> Dict[str, str]:
        """`{entity_id: friendly name}` — handy when debugging by hand."""
        if not self.available:
            return {}
        try:
            raw = self._request("states") or []
        except Exception:
            return {}
        return {i["entity_id"]: i.get("attributes", {}).get("friendly_name", "")
                for i in raw if i.get("entity_id", "").split(".", 1)[0]
                in WATCHED_DOMAINS}

    # -- writing ----------------------------------------------------------

    def set_state(self, entity_id: str, state: str) -> Tuple[bool, str]:
        """Turn an entity on or off. Returns (ok, detail)."""
        if not self.available:
            return False, "Home Assistant is not configured."
        domain = entity_id.split(".", 1)[0]
        if domain not in CONTROLLABLE:
            return False, (f"I don't switch {domain} entities — only "
                           f"{', '.join(CONTROLLABLE)}.")
        service = "turn_on" if state == "on" else "turn_off"
        try:
            self._request(f"services/{domain}/{service}",
                          {"entity_id": entity_id})
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except Exception as exc:
            return False, str(exc)
        LOG.info("%s -> %s", entity_id, state)
        return True, "ok"

    # -- polling ----------------------------------------------------------

    def start(self) -> bool:
        """Poll entity states into the world state on a background thread."""
        if not (self.available and self.state):
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="home",
                                        daemon=True)
        self._thread.start()
        LOG.info("polling every %.0fs", self.cfg.ha_poll_interval)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            devices = self.entities()
            if devices:
                # One update for the whole dict: the world state diffs it as a
                # unit, so a single light changing is one change, not two
                # hundred no-ops.
                self.state.update(devices=devices)
            self._stop.wait(self.cfg.ha_poll_interval)


def main(argv=None) -> int:
    setup_logging(CONFIG.log_level)
    home = HomeAssistant()
    if not home.available:
        print("Home Assistant is not configured (or not reachable).")
        print("Set HA_ENABLED=true, HA_URL and HA_TOKEN in .env — README step 9.")
        return 1
    names = home.friendly_names()
    entities = home.entities()
    print(f"{len(entities)} watched entities:\n")
    for eid, state in sorted(entities.items()):
        label = names.get(eid) or ""
        controllable = "*" if eid.split(".", 1)[0] in CONTROLLABLE else " "
        print(f" {controllable} {eid:<44} {state:<12} {label}")
    print("\n(* = Vesper is allowed to switch it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
