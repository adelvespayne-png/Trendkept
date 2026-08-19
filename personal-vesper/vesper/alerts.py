"""Getting hold of you when you are not at the laptop.

    python -m vesper.alerts "test"     # send one and see if your phone buzzes

Speaking aloud only works if you are in the room. This pushes to your phone
as well, so a red flag reaches you in the garden, at work, or asleep.

Deliberately dumb and deliberately local-first: an HTTP POST to a topic
nobody needs an account for. The default is ntfy.sh — free, open, no signup,
an app on both phone stores. Point it at your own server if you would rather.

Two things this module refuses to be clever about:

  * It never decides *whether* something is worth sending. That decision was
    already made by `core/redflag.py` in plain code. This just delivers.
  * It never fails loudly into the assistant. A phone that did not buzz must
    not stop Vesper saying the same thing out loud.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import urllib.request
from typing import Optional

from .config import CONFIG, Config, setup_logging

LOG = logging.getLogger("vesper.alerts")

#: ntfy priorities: 5 shouts through a silenced phone, 3 is a normal
#: notification. Anything urgent should be able to wake you.
PRIORITY = {"emergency": 5, "crisis": 5, "urgent": 5, "watch": 3, "info": 3}

TAGS = {"emergency": "rotating_light", "crisis": "heart",
        "urgent": "warning", "watch": "eyes", "info": "bell"}


def _header_safe(text: str) -> str:
    """HTTP headers are latin-1 only.

    An em dash in the title made urllib raise before the request left the
    machine — so every alert failed, silently, while the code looked fine.
    The body is UTF-8 and keeps its punctuation; only headers get flattened.
    """
    swaps = {"\u2014": "-", "\u2013": "-", "\u2019": "'", "\u2018": "'",
             "\u201c": '"', "\u201d": '"', "\u2026": "..."}
    for bad, good in swaps.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


class Alerts:
    def __init__(self, cfg: Config = CONFIG) -> None:
        self.cfg = cfg
        self.backend = (cfg.alert_backend or "none").lower()
        self.available = bool(self.backend != "none" and self._target())

    def _target(self) -> str:
        if self.backend == "ntfy":
            topic = (self.cfg.ntfy_topic or "").strip()
            if not topic:
                return ""
            if topic.startswith("http"):
                return topic
            return self.cfg.ntfy_server.rstrip("/") + "/" + topic
        if self.backend == "webhook":
            return (self.cfg.alert_webhook or "").strip()
        return ""

    def send(self, text: str, level: str = "info",
             title: Optional[str] = None) -> bool:
        """Fire and forget. Returns whether it was even attempted."""
        if not self.available:
            return False
        url = self._target()
        threading.Thread(target=self._post, args=(url, text, level, title),
                         daemon=True, name="alert").start()
        return True

    def _post(self, url: str, text: str, level: str, title: Optional[str]) -> None:
        try:
            if self.backend == "ntfy":
                req = urllib.request.Request(
                    url, data=text.encode("utf-8"), method="POST",
                    headers={
                        "Title": _header_safe(title or f"Vesper - {level}")[:120],
                        "Priority": str(PRIORITY.get(level, 3)),
                        "Tags": TAGS.get(level, "bell"),
                    })
            else:
                body = json.dumps({"level": level, "title": title or "Vesper",
                                   "text": text}).encode("utf-8")
                req = urllib.request.Request(
                    url, data=body, method="POST",
                    headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read()
            LOG.info("alert sent (%s)", level)
        except Exception as exc:
            # Never raises into the assistant: the same words are being said
            # aloud anyway, and a failed push must not take that down too.
            LOG.error("could not send the alert: %s", exc)


def main(argv=None) -> int:
    setup_logging(CONFIG.log_level)
    text = " ".join(argv or sys.argv[1:]) or "Test from Vesper."
    a = Alerts(CONFIG)
    if not a.available:
        print("Alerts are off.\n")
        print("Set ALERT_BACKEND=ntfy and NTFY_TOPIC to something long and")
        print("unguessable — anyone who knows the topic can read your alerts.")
        print("Then install the ntfy app and subscribe to the same topic.")
        return 1
    print(f"backend: {a.backend}\ntarget:  {a._target()}\n")
    a.send(text, "urgent", "Vesper - test")
    import time
    time.sleep(3)
    print("Sent. If your phone did not buzz, check the topic matches exactly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
