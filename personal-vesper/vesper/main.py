"""Vesper — the orchestrator.

    python -m vesper.main               # full assistant, whatever hardware exists
    python -m vesper.main --text        # typed input, spoken output
    python -m vesper.main --say "..."   # one question, then exit
    python -m vesper.main --check       # print what's on and what's off

Two paths reach the brain, and only these two:

  1. **You spoke.** Wake word fires -> record until you stop -> transcribe ->
     brain -> speak.
  2. **Something changed.** A sensor updated the world state -> a trigger rule
     matched -> brain is woken with the reason and decides whether to say
     anything at all.

Everything else — camera frames, audio frames, Home Assistant polls — runs
continuously and costs nothing. That is the entire point of the design.

One turn happens at a time. A queue with `maxsize=1` in front of a single
consumer means Vesper never talks over itself, and a burst of triggers during
a conversation collapses into at most one follow-up rather than a pile-up.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from typing import List, Optional

from .config import CONFIG, Config, setup_logging
from .core.brain import Brain
from .core.triggers import (TriggerEngine, configure_health,
                            configure_watch_words)
from .core.world_state import Change, Snapshot, WorldState
from .alerts import Alerts
from .mapstore import MapStore
from .sensors.clock import Clock
from .sensors.home_assistant import HomeAssistant
from .sensors.health import HealthFeed
from .sensors.news import NewsFeed
from .sensors.stt import Listener
from .sensors.tts import Speaker
from .sensors.vision import VisionLoop
from .sensors.wake_word import WakeWordListener
from .server import AskServer, lan_ip
from .tools.tool_executor import ToolExecutor

LOG = logging.getLogger("vesper.main")

WAKE = "wake"          # the user is about to speak
AMBIENT = "ambient"    # a trigger rule wants the brain to have a look


class Vesper:
    def __init__(self, cfg: Config = CONFIG) -> None:
        self.cfg = cfg
        self.state = WorldState(path=cfg.state_path)
        self.clock = Clock(self.state, cfg)
        self.clock.tick()

        self.speaker = Speaker(cfg)
        self.listener = Listener(cfg)
        self.home = HomeAssistant(cfg, self.state)
        self.news = NewsFeed(self.state, cfg)
        self.health = HealthFeed(self.state, cfg)
        self.vision = VisionLoop(self.state, cfg)
        self.wake = WakeWordListener(cfg, mic=self.listener.mic,
                                     on_wake=self._on_wake)

        self.map = MapStore(cfg.map_path)
        self.alerts = Alerts(cfg)
        self.executor = ToolExecutor(self.state, cfg, home=self.home,
                                     mapstore=self.map, health=self.health,
                                     alerts=self.alerts)
        self.brain = Brain(self.state, self.executor, cfg)
        configure_watch_words(cfg.news_watch)
        configure_health(cfg.health_load_sigmas)
        self.triggers = TriggerEngine(global_cooldown=cfg.proactive_cooldown)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._events: Optional[asyncio.Queue] = None
        self._busy = False
        self._running = True
        self.bridge: Optional[AskServer] = None

    # -- events in from sensor threads ------------------------------------

    def _post(self, kind: str, why: Optional[str] = None) -> None:
        """Called from sensor threads; hands the event to the asyncio loop."""
        if self._loop is None or self._events is None:
            return

        def put() -> None:
            try:
                self._events.put_nowait((kind, why))
            except asyncio.QueueFull:
                # A turn is already queued. Dropping this one is the right
                # behaviour — the world state it would have read is the same
                # world state the queued turn will read.
                LOG.debug("dropped %s event (busy)", kind)

        self._loop.call_soon_threadsafe(put)

    def _on_wake(self) -> None:
        if self._busy:
            LOG.debug("wake word during a turn; ignoring")
            return
        self._post(WAKE)

    def _on_state_change(self, changes: List[Change], snap: Snapshot) -> None:
        if not self.cfg.proactive_enabled or self._busy:
            return
        fired = self.triggers.evaluate(snap, changes)
        if fired:
            self._post(AMBIENT, fired.why)

    # -- the single consumer ----------------------------------------------

    async def _handle(self, kind: str, why: Optional[str]) -> None:
        self._busy = True
        try:
            if kind == WAKE:
                await self._handle_wake()
            else:
                await self._speak(await self.brain.respond(reason=why))
        finally:
            self._busy = False

    async def _handle_wake(self) -> None:
        if not self.listener.available:
            await self._speak("I heard you, but I have no way to listen.")
            return

        # Both the wake listener and the recorder want the microphone. Hand it
        # over cleanly rather than hoping the audio backend tolerates two
        # streams on one device — it often doesn't.
        self.wake.stop()
        try:
            LOG.info("listening…")
            text = await asyncio.to_thread(self.listener.listen_once)
        finally:
            self.wake.start()

        if not text:
            LOG.info("nothing heard after the wake word")
            return
        await self.ask(text)

    async def ask(self, text: str, channel: str = "voice") -> Optional[str]:
        """One user turn, start to finish. Returns what was said, if anything."""
        started = time.monotonic()
        reply = await self.brain.respond(user_text=text, channel=channel)
        LOG.debug("turn took %.1fs", time.monotonic() - started)
        await self._speak(reply)
        return reply

    async def _speak(self, text: Optional[str]) -> None:
        if not text:
            return
        # Speaking blocks on a subprocess; keep it off the event loop.
        await asyncio.to_thread(self.speaker.say, text)

    # -- lifecycle ---------------------------------------------------------

    def start_sensors(self) -> None:
        self.state.subscribe(self._on_state_change)
        self.clock.start()
        if self.news.start():
            LOG.info("news on")
        if self.health.start():
            LOG.info("health on")
        if self.vision.start():
            LOG.info("vision on")
        if self.home.start():
            LOG.info("home assistant on")
        if self.wake.start():
            LOG.info("wake word on")
        elif self.cfg.wake_enabled:
            LOG.warning("wake word unavailable — use --text to type instead")

    def start_bridge(self) -> None:
        """The phone endpoint. Needs the running loop, so not in __init__."""
        if not self.cfg.server_enabled:
            return
        self.bridge = AskServer(self, self._loop, self.cfg)
        if self.bridge.start():
            print(f"  Phone bridge: http://{lan_ip()}:{self.cfg.server_port}"
                  "   (see PHONE.md)")
        else:
            self.bridge = None

    def stop_sensors(self) -> None:
        self.wake.stop()
        self.clock.stop()
        self.news.stop()
        self.health.stop()
        self.vision.stop()
        self.home.stop()
        if self.bridge:
            self.bridge.stop()

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._events = asyncio.Queue(maxsize=1)

        self.brain.load_recent()
        self.start_sensors()
        self.start_bridge()

        if not self.brain.available:
            print("\nNo ANTHROPIC_API_KEY, so there is nothing to think with.")
            print("Put one in .env and run again — README step 5.\n")

        print(f"\nVesper is up. Say “{self.cfg.wake_phrase}”. Ctrl-C to stop.\n")
        try:
            while self._running:
                kind, why = await self._events.get()
                try:
                    await self._handle(kind, why)
                except Exception:
                    LOG.exception("turn failed")
        except asyncio.CancelledError:
            pass
        finally:
            self.stop_sensors()

    # -- typed mode --------------------------------------------------------

    async def run_text(self) -> None:
        """No wake word, no microphone. Ambient sensors still run."""
        self._loop = asyncio.get_running_loop()
        self._events = asyncio.Queue(maxsize=1)
        self.brain.load_recent()

        self.state.subscribe(self._on_state_change)
        self.clock.start()
        self.news.start()
        self.health.start()
        self.vision.start()
        self.home.start()
        self.start_bridge()

        print("\nTyped mode. Blank line or Ctrl-D to quit.\n")
        try:
            while True:
                try:
                    text = (await asyncio.to_thread(input, "you > ")).strip()
                except EOFError:
                    break
                if not text:
                    break
                self._busy = True
                try:
                    reply = await self.brain.respond(user_text=text,
                                                     channel="text")
                finally:
                    self._busy = False
                if reply:
                    print(f"vesper > {reply}")
                    await asyncio.to_thread(self.speaker.say, reply)
                else:
                    print("vesper > (nothing to say)")
        finally:
            self.stop_sensors()


# --------------------------------------------------------------------------


async def _one_shot(vesper: Vesper, text: str) -> int:
    vesper._loop = asyncio.get_running_loop()
    vesper._events = asyncio.Queue(maxsize=1)
    if not vesper.brain.available:
        print("There is no ANTHROPIC_API_KEY set, so there is nothing to "
              "think with. Put one in .env — README step 5.")
        return 1
    reply = await vesper.brain.respond(user_text=text, channel="text")
    if reply:
        print(reply)
        await asyncio.to_thread(vesper.speaker.say, reply)
        return 0
    print("(nothing to say)")
    return 0


def _check(cfg: Config) -> int:
    """What is actually wired up on this machine."""
    print("\nConfigured:")
    print(cfg.describe())

    print("\nDetected:")
    # Each subsystem logs its own "not installed" warning on the way up. The
    # table below says the same thing more usefully, so quieten them here.
    root = logging.getLogger("vesper")
    was = root.level
    root.setLevel(logging.ERROR)
    vesper = Vesper(cfg)
    rows = [
        ("microphone", vesper.listener.mic.available,
         "pip install sounddevice, and grant mic permission"),
        ("wake word", vesper.wake._ensure_model(),
         "pip install openwakeword"),
        ("speech out", vesper.speaker.backend != "print",
         "install piper + a player (paplay/aplay/afplay)"),
        ("reasoning", vesper.brain.available,
         "set ANTHROPIC_API_KEY in .env"),
        ("vision", vesper.vision._open(),
         "set VISION_ENABLED=true, pip install opencv-python ultralytics"),
        ("home", vesper.home.available,
         "set HA_ENABLED=true, HA_URL, HA_TOKEN"),
        ("phone", cfg.server_enabled and len(cfg.server_token) >= 16,
         "python -m vesper.server --new-token, then SERVER_ENABLED=true"),
        ("news", vesper.news.available, "set NEWS_ENABLED=true and NEWS_FEEDS"),
        ("health", vesper.health.available,
         "set HEALTH_BACKEND=file (and HEALTH_FILE), or =oura with OURA_TOKEN"),
        ("alerts", vesper.alerts.available,
         "set ALERT_BACKEND=ntfy and NTFY_TOPIC to reach your phone"),
    ]
    missing = 0
    for name, ok, fix in rows:
        if ok:
            print(f"  {name:<12} ok")
        else:
            missing += 1
            print(f"  {name:<12} -- {fix}")
    vesper.stop_sensors()
    root.setLevel(was)

    print(f"\n{len(rows) - missing}/{len(rows)} subsystems available. "
          "Vesper runs with whatever it has.\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vesper", description=__doc__.split("\n")[0])
    parser.add_argument("--text", action="store_true",
                        help="type instead of speaking (no mic needed)")
    parser.add_argument("--say", metavar="TEXT", help="ask one thing and exit")
    parser.add_argument("--check", action="store_true",
                        help="report which subsystems are available")
    parser.add_argument("--serve", action="store_true",
                        help="also open the phone endpoint (needs SERVER_TOKEN)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    cfg = CONFIG
    setup_logging("DEBUG" if args.verbose else cfg.log_level)
    if args.serve:
        cfg.server_enabled = True

    if args.check:
        return _check(cfg)

    vesper = Vesper(cfg)

    if args.say:
        return asyncio.run(_one_shot(vesper, args.say))

    async def _go() -> None:
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set)
            except (NotImplementedError, RuntimeError):
                pass    # Windows, or a non-main thread
        task = asyncio.ensure_future(
            vesper.run_text() if args.text else vesper.run())
        done, _ = await asyncio.wait(
            [task, asyncio.ensure_future(stop.wait())],
            return_when=asyncio.FIRST_COMPLETED)
        if task not in done:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    try:
        asyncio.run(_go())
    except KeyboardInterrupt:
        pass
    print("\nVesper stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
