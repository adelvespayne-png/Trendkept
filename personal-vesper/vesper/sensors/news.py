"""Ambient awareness of the outside world — RSS headlines, polled.

    python -m vesper.sensors.news       # fetch once and print what came back

Like the camera, this **never calls the LLM**. It pulls headlines on an
interval and writes them into the world state, which means two things:

  * every answer Vesper gives already has the day's news in context, without
    you asking and without a search costing anything, and
  * a trigger rule can notice something major broke and wake the brain, which
    then decides whether it's worth interrupting you (usually it isn't).

RSS because it needs no key, no account and no scraping — it's the format
news organisations publish *for* this. Parsed with the standard library.
"""

from __future__ import annotations

import html
import logging
import re
import sys
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional

from ..config import CONFIG, Config, setup_logging
from ..core.world_state import WorldState

LOG = logging.getLogger("vesper.news")

UA = "vesper-assistant/1.0 (personal use)"


def _clean(text: str) -> str:
    """Strip tags and entities — some feeds put HTML in the title."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def fetch_feed(url: str, timeout: float = 10.0, limit: int = 10) -> List[str]:
    """Headlines from one RSS or Atom feed. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except Exception as exc:
        LOG.warning("could not fetch %s: %s", url, exc)
        return []
    return parse_feed(raw, limit=limit)


def parse_feed(raw: bytes, limit: int = 10) -> List[str]:
    """RSS `<item><title>` or Atom `<entry><title>`, in feed order."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        LOG.warning("feed was not valid XML: %s", exc)
        return []

    titles: List[str] = []
    # RSS 2.0
    for item in root.iter("item"):
        node = item.find("title")
        if node is not None and node.text:
            titles.append(_clean(node.text))
    # Atom — namespaced, so match on the tag's local name
    if not titles:
        for entry in root.iter():
            if entry.tag.rsplit("}", 1)[-1] != "entry":
                continue
            for child in entry:
                if child.tag.rsplit("}", 1)[-1] == "title" and child.text:
                    titles.append(_clean(child.text))
                    break
    return [t for t in titles if t][:limit]


class NewsFeed:
    """Polls the configured feeds on a background thread."""

    def __init__(self, state: WorldState, cfg: Config = CONFIG) -> None:
        self.state = state
        self.cfg = cfg
        self.available = bool(cfg.news_enabled and cfg.news_feeds)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def feeds(self) -> List[str]:
        return [u.strip() for u in self.cfg.news_feeds.split(",") if u.strip()]

    def poll_once(self) -> List[str]:
        """Fetch every feed, interleaved so one source can't crowd out another."""
        per_feed = [fetch_feed(u, limit=self.cfg.news_per_feed)
                    for u in self.feeds()]
        merged: List[str] = []
        for i in range(max((len(f) for f in per_feed), default=0)):
            for feed in per_feed:
                if i < len(feed):
                    merged.append(feed[i])
        # Same story from two outlets is one story as far as we're concerned.
        seen, out = set(), []
        for title in merged:
            key = title.lower()
            if key not in seen:
                seen.add(key)
                out.append(title)
        return out[:self.cfg.news_keep]

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        if not self.available:
            LOG.debug("news disabled or no feeds configured")
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="news",
                                        daemon=True)
        self._thread.start()
        LOG.info("following %d feed(s) every %.0f min", len(self.feeds()),
                 self.cfg.news_interval / 60)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            headlines = self.poll_once()
            if headlines:
                self.state.update(headlines=headlines,
                                  headlines_at=time.time())
            self._stop.wait(self.cfg.news_interval)


def main(argv=None) -> int:
    setup_logging(CONFIG.log_level)
    state = WorldState()
    feed = NewsFeed(state, CONFIG)
    if not feed.available:
        print("News is off. Set NEWS_ENABLED=true (and NEWS_FEEDS) in .env.")
        return 1
    print(f"Fetching {len(feed.feeds())} feed(s)…\n")
    headlines = feed.poll_once()
    if not headlines:
        print("Nothing came back — check the URLs and your connection.")
        return 1
    for h in headlines:
        print(" •", h)
    print(f"\n{len(headlines)} headlines. These go into the world state, so "
          "Vesper has them without searching.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
