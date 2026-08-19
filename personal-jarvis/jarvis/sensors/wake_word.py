"""Wake word — openWakeWord, always on, cheap.

    python -m jarvis.sensors.wake_word   # prints a line each time it hears you

This is the one thing that genuinely runs continuously. It is a small local
model scoring 30 ms frames; it never touches the network and never wakes the
LLM by itself — it just sets an event that the brain loop is waiting on.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Callable, Optional

from ..config import CONFIG, Config, setup_logging
from .stt import FRAME_SAMPLES, Microphone

LOG = logging.getLogger("jarvis.wake")


class WakeWordListener:
    """Runs a detection loop on its own thread and calls `on_wake()`."""

    def __init__(self, cfg: Config = CONFIG,
                 mic: Optional[Microphone] = None,
                 on_wake: Optional[Callable[[], None]] = None) -> None:
        self.cfg = cfg
        self.mic = mic or Microphone()
        self.on_wake = on_wake
        self.available = False
        self._model = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # After firing we ignore audio briefly, or one "hey jarvis" scores
        # above threshold on several overlapping windows and fires repeatedly.
        self._refractory = 1.5

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if not self.cfg.wake_enabled:
            LOG.info("wake word disabled by config")
            return False
        if not self.mic.available:
            LOG.warning("no microphone; wake word is off")
            return False
        try:
            from openwakeword.model import Model
        except Exception as exc:
            LOG.warning("openwakeword not installed (%s); wake word is off. "
                        "See README step 4.", exc)
            return False
        try:
            self._model = Model(wakeword_models=[self.cfg.wake_model],
                                inference_framework="onnx")
        except Exception as exc:
            LOG.warning("could not load wake model %r (%s); trying the bundled set",
                        self.cfg.wake_model, exc)
            try:
                self._model = Model(inference_framework="onnx")
            except Exception as exc2:
                LOG.error("no wake models available: %s", exc2)
                return False
        self.available = True
        return True

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        if not self._ensure_model():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="wake",
                                        daemon=True)
        self._thread.start()
        LOG.info("listening for %r", self.cfg.wake_model)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        import numpy as np

        last_fire = 0.0
        try:
            with self.mic.stream() as stream:
                while not self._stop.is_set():
                    block, _overflow = stream.read(FRAME_SAMPLES)
                    samples = np.frombuffer(bytes(block), dtype=np.int16)
                    scores = self._model.predict(samples)
                    best = max(scores.values()) if scores else 0.0
                    now = time.monotonic()
                    if best >= self.cfg.wake_threshold and \
                            now - last_fire > self._refractory:
                        last_fire = now
                        LOG.info("wake word (%.2f)", best)
                        if self.on_wake:
                            try:
                                self.on_wake()
                            except Exception:
                                LOG.exception("wake callback failed")
        except Exception:
            LOG.exception("wake-word loop stopped")


def main(argv=None) -> int:
    setup_logging(CONFIG.log_level)
    heard = []
    listener = WakeWordListener(on_wake=lambda: heard.append(time.time()))
    if not listener.start():
        print("Wake word unavailable here. Install openwakeword and a "
              "microphone, then run this again.")
        return 1
    print(f"Say “{CONFIG.wake_model.replace('_', ' ')}”. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
    print(f"\nDetected {len(heard)} time(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
