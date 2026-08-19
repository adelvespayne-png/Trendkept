"""Dispatch Claude's tool calls to real functions.

Every handler returns a string (what Claude sees next) and must not raise —
a failed tool comes back as an error result so the model can adapt, which is
far better behaviour than an exception killing the turn.
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from ..config import CONFIG, Config
from ..core.world_state import WorldState

LOG = logging.getLogger("vesper.tools")


class ToolExecutor:
    def __init__(self, state: WorldState, cfg: Config = CONFIG,
                 home=None, reminders_path: Optional[Path] = None,
                 mapstore=None, health=None, alerts=None) -> None:
        self.state = state
        self.cfg = cfg
        self.home = home            # sensors.home_assistant.HomeAssistant | None
        self.map = mapstore         # mapstore.MapStore | None
        self.health = health        # sensors.health.HealthFeed | None
        self.alerts = alerts        # alerts.Alerts | None
        self.reminders_path = reminders_path or (
            Path(cfg.state_path).parent / "reminders.jsonl")
        self._handlers: Dict[str, Callable[[dict], str]] = {
            "answer": self._answer,
            "stay_silent": self._stay_silent,
            "get_weather": self._get_weather,
            "create_reminder": self._create_reminder,
            "list_reminders": self._list_reminders,
            "recall_world": self._recall_world,
            "set_device": self._set_device,
            "fetch_page": self._fetch_page,
            "search_web": self._search_web,
            "log_symptom": self._log_symptom,
            "read_body": self._read_body,
            "map_read": self._map_read,
            "map_add": self._map_add,
            "map_update": self._map_update,
        }
        # Set when a turn changed the map, so the page knows to redraw.
        self.map_dirty = False
        # Filled in by the brain for terminal tools.
        self.spoken: Optional[str] = None
        self.silent_reason: Optional[str] = None

    def reset_turn(self) -> None:
        self.spoken = None
        self.silent_reason = None
        self.map_dirty = False

    def run(self, name: str, args: dict) -> Tuple[str, bool]:
        """Returns (result_text, is_error)."""
        handler = self._handlers.get(name)
        if handler is None:
            LOG.warning("unknown tool %r", name)
            return f"No such tool: {name}", True
        try:
            return handler(args or {}), False
        except Exception as exc:
            LOG.exception("tool %s failed", name)
            return f"{type(exc).__name__}: {exc}", True

    # -- terminal ---------------------------------------------------------

    def _answer(self, args: dict) -> str:
        self.spoken = (args.get("text") or "").strip()
        return "Spoken to the user."

    def _stay_silent(self, args: dict) -> str:
        self.silent_reason = (args.get("reason") or "").strip() or "(no reason given)"
        LOG.info("staying silent: %s", self.silent_reason)
        return "Said nothing."

    # -- the body ----------------------------------------------------------

    def _log_symptom(self, args: dict) -> str:
        """Record it, then classify it in local code.

        The `instruction` in the result is fixed text chosen by an if
        statement in `core/redflag.py`. The model's only job is to read it
        out unchanged — which is why it is handed over as a quoted string
        rather than as facts to summarise.
        """
        from ..core.redflag import SymptomLog, check

        text = (args.get("text") or "").strip()
        if not text:
            return "Nothing to record."
        verdict = check(text, self.cfg)
        SymptomLog(self.cfg.symptom_log).add(text, verdict["level"] or "none")
        if verdict["level"]:
            LOG.warning("symptom logged as %s: %s", verdict["level"], text)
            # Push straight from here, not from the model's reply. The phone
            # buzzing must not depend on a model choosing to mention it.
            self._alert(verdict["level"], verdict["instruction"], text)
        return json.dumps({
            "logged": True,
            "level": verdict["level"],
            "say_this_verbatim": verdict["instruction"],
            "note": ("This instruction was decided by local code, not by a "
                     "model. Read it out exactly as written."),
        })

    def _alert(self, level: str, instruction: str, said: str) -> None:
        from .. import alerts as alerts_mod

        if self.alerts is None or not self.alerts.available:
            return
        order = ["watch", "urgent", "crisis", "emergency"]
        floor = (self.cfg.alert_min_level or "urgent").lower()
        try:
            if order.index(level) < order.index(floor):
                return
        except ValueError:
            pass
        self.alerts.send(f"You said: {said}\n\n{instruction}",
                         level=level, title=f"Vesper - {level}")

    def _read_body(self, args: dict) -> str:
        from ..core.redflag import SymptomLog

        out = {"baseline_days": self.cfg.health_baseline_days}
        if self.health is not None:
            snap = self.state.snapshot()
            out["today_vs_your_normal"] = snap.get("health") or {}
            out["backend"] = self.health.backend
        else:
            out["today_vs_your_normal"] = {}
            out["backend"] = "off"
        recent = SymptomLog(self.cfg.symptom_log).recent(72)
        out["symptoms_last_3_days"] = [
            {"when": r.get("when"), "text": r.get("text"), "level": r.get("level")}
            for r in recent]
        if not out["today_vs_your_normal"]:
            out["note"] = ("No wearable data. Say so rather than guessing at "
                           "how they are.")
        return json.dumps(out)

    # -- searching ---------------------------------------------------------

    def _search_web(self, args: dict) -> str:
        """Search, through whichever backend is configured.

        Lives here rather than on Anthropic's servers, which is the point:
        a tool on this machine follows Vesper onto any provider.
        """
        query = (args.get("query") or "").strip()
        if not query:
            return "Search needs something to look for."
        backend = self.cfg.search_backend()
        n = self.cfg.search_results
        if not backend:
            return "Web search is switched off (SEARCH_PROVIDER=none)."
        try:
            if backend == "brave":
                hits = self._brave(query, n)
            elif backend == "tavily":
                hits = self._tavily(query, n)
            else:
                hits = self._duckduckgo(query, n)
        except Exception as exc:
            LOG.warning("%s search failed: %s", backend, exc)
            return (f"The {backend} search failed ({type(exc).__name__}). "
                    "You can still give me a URL to read directly.")
        if not hits:
            return f"No results for {query!r}."
        return json.dumps({"source": backend, "results": hits})

    def _brave(self, query: str, n: int):
        url = ("https://api.search.brave.com/res/v1/web/search?"
               + urllib.parse.urlencode({"q": query, "count": n}))
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "X-Subscription-Token": self.cfg.brave_api_key})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        return [{"title": x.get("title"), "url": x.get("url"),
                 "snippet": x.get("description")}
                for x in (data.get("web", {}).get("results") or [])[:n]]

    def _tavily(self, query: str, n: int):
        body = json.dumps({"api_key": self.cfg.tavily_api_key, "query": query,
                           "max_results": n}).encode()
        req = urllib.request.Request(
            "https://api.tavily.com/search", data=body, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
        return [{"title": x.get("title"), "url": x.get("url"),
                 "snippet": (x.get("content") or "")[:400]}
                for x in (data.get("results") or [])[:n]]

    def _duckduckgo(self, query: str, n: int):
        """No key, no account — and correspondingly fragile. It scrapes a
        results page, so a layout change breaks it. Keyed backends are
        better; this is here so search works out of the box."""
        import re

        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
            {"q": query})
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0 Safari/537.36")})
        with urllib.request.urlopen(req, timeout=20) as r:
            page = r.read().decode("utf-8", "replace")

        def strip(s):
            return html_mod.unescape(re.sub(r"(?s)<[^>]+>", "", s)).strip()

        out = []
        for m in re.finditer(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                page, re.S):
            href, title = m.group(1), strip(m.group(2))
            # DuckDuckGo wraps targets in a redirect; unwrap to the real URL.
            if "uddg=" in href:
                href = urllib.parse.unquote(
                    urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    .get("uddg", [href])[0])
            out.append({"title": title, "url": href, "snippet": ""})
            if len(out) >= n:
                break
        snips = [strip(s) for s in re.findall(
            r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>', page, re.S)]
        for i, s in enumerate(snips[:len(out)]):
            out[i]["snippet"] = s[:400]
        return out

    # -- the open web ------------------------------------------------------

    def _fetch_page(self, args: dict) -> str:
        """Fetch a page and hand back its text, stripped and capped."""
        import re

        url = (args.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return "That isn't a URL I can fetch."
        req = urllib.request.Request(url, headers={
            "User-Agent": "vesper-assistant/1.0 (personal use)",
            "Accept": "text/html,application/xhtml+xml,text/plain",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            ctype = resp.headers.get("Content-Type", "")
            raw = resp.read(2_000_000)
        if not any(k in ctype for k in ("text", "html", "json", "xml")):
            return f"That page is {ctype or 'not text'}, so there is nothing to read."
        text = raw.decode(resp.headers.get_content_charset() or "utf-8", "replace")
        # Scripts and styles first, or their contents survive the tag strip.
        text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html_mod.unescape(text)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        if len(text) > 12000:
            text = text[:12000] + "\n…(truncated)"
        return text or "That page had no readable text."

    # -- the map ----------------------------------------------------------

    def _map_read(self, args: dict) -> str:
        if self.map is None:
            return "The project map isn't available in this session."
        return self.map.summary() + "\n\n" + self.map.outline()

    def _map_add(self, args: dict) -> str:
        if self.map is None:
            return "The project map isn't available in this session."
        ok, msg = self.map.add(args.get("text", ""), args.get("parent") or None)
        if ok:
            self.map_dirty = True
        return msg

    def _map_update(self, args: dict) -> str:
        if self.map is None:
            return "The project map isn't available in this session."
        name = args.get("name", "")
        action = (args.get("action") or "").lower()
        value = args.get("value") or ""
        if action == "done":
            ok, msg = self.map.set_done(name, True)
        elif action == "reopen":
            ok, msg = self.map.set_done(name, False)
        elif action == "rename":
            ok, msg = self.map.rename(name, value)
        elif action == "move":
            ok, msg = self.map.move(name, value)
        elif action == "delete":
            ok, msg = self.map.remove(name)
        elif action == "link":
            ok, msg = self.map.link(name, value)
        else:
            return f"I don't know how to {action!r} something."
        if ok:
            self.map_dirty = True
        return msg

    # -- world ------------------------------------------------------------

    def _recall_world(self, args: dict) -> str:
        snap = self.state.snapshot()
        return json.dumps({
            "summary": snap.describe(),
            "people": snap.people,
            "objects": snap.objects,
            "devices": snap.devices,
            "seconds_since_motion": snap.seconds_since_motion(),
        }, default=str)

    # -- reminders --------------------------------------------------------

    def _create_reminder(self, args: dict) -> str:
        text = (args.get("text") or "").strip()
        if not text:
            return "A reminder needs some text."
        record = {"text": text, "when": (args.get("when") or "").strip(),
                  "created_at": time.time(), "done": False}
        self.reminders_path.parent.mkdir(parents=True, exist_ok=True)
        with self.reminders_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        LOG.info("reminder saved: %s", text)
        return f"Saved: {text}" + (f" ({record['when']})" if record["when"] else "")

    def _list_reminders(self, args: dict) -> str:
        if not self.reminders_path.is_file():
            return "There are no reminders saved."
        out = []
        with self.reminders_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not rec.get("done"):
                    out.append(rec.get("text", "") +
                               (f" ({rec['when']})" if rec.get("when") else ""))
        return json.dumps(out) if out else "There are no reminders saved."

    # -- weather ----------------------------------------------------------

    def _get_weather(self, args: dict) -> str:
        """Open-Meteo: no API key, no account. Geocode, then forecast."""
        location = (args.get("location") or "").strip()
        if not location:
            return "Which place?"

        geo_url = ("https://geocoding-api.open-meteo.com/v1/search?"
                   + urllib.parse.urlencode({"name": location, "count": 1}))
        with urllib.request.urlopen(geo_url, timeout=10) as resp:
            geo = json.loads(resp.read())
        results = geo.get("results") or []
        if not results:
            return f"I couldn't find a place called {location}."
        place = results[0]

        url = ("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,precipitation,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto", "forecast_days": 1,
        }))
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())

        cur = data.get("current", {})
        daily = data.get("daily", {})
        return json.dumps({
            "place": place.get("name"),
            "country": place.get("country"),
            "temperature_c": cur.get("temperature_2m"),
            "feels_like_c": cur.get("apparent_temperature"),
            "precipitation_mm": cur.get("precipitation"),
            "conditions": _WEATHER_CODES.get(cur.get("weather_code"), "unknown"),
            "today_high_c": (daily.get("temperature_2m_max") or [None])[0],
            "today_low_c": (daily.get("temperature_2m_min") or [None])[0],
            "rain_chance_pct": (daily.get("precipitation_probability_max") or [None])[0],
        })

    # -- home -------------------------------------------------------------

    def _set_device(self, args: dict) -> str:
        if self.home is None or not getattr(self.home, "available", False):
            return ("Home Assistant isn't configured, so I can't control "
                    "devices. Tell the user that plainly.")
        entity = (args.get("entity_id") or "").strip()
        state = (args.get("state") or "").strip().lower()
        if state not in ("on", "off"):
            return "State must be 'on' or 'off'."
        ok, detail = self.home.set_state(entity, state)
        if ok:
            self.state.set_device(entity, state)
            return f"{entity} is now {state}."
        return f"Could not change {entity}: {detail}"


_WEATHER_CODES = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain", 71: "light snow",
    73: "snow", 75: "heavy snow", 77: "snow grains", 80: "light showers",
    81: "showers", 82: "violent showers", 85: "snow showers",
    86: "heavy snow showers", 95: "thunderstorm",
    96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
}
