"""Wake word — openWakeWord, always on, cheap.

    python -m vesper.sensors.wake_word           # listen and report hits
    python -m vesper.sensors.wake_word --list    # what phrases are available

This is the one thing that genuinely runs continuously. It is a small local
model scoring 30 ms frames; it never touches the network and never wakes the
LLM by itself — it just sets an event that the brain loop is waiting on.

**The wake phrase is a trained model, not a setting.** openWakeWord ships
four ready-made phrases and "hey vesper" is not among them, because nobody
has trained one. You can train your own — see WAKE_WORD.md — and point
WAKE_MODEL at the file. Until then the spoken trigger is one of the four
below even though the assistant is called Vesper.

The one thing this module will not do is guess. If you ask for a model it
cannot load, it stops and says so rather than quietly falling back to the
bundled set — because that fallback listens for "hey jarvis" and "alexa",
and you would be sitting there saying "hey Vesper" at something that was
never listening for it.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..config import CONFIG, Config, setup_logging
from .stt import FRAME_SAMPLES, Microphone

LOG = logging.getLogger("vesper.wake")

#: The phrases openWakeWord ships trained models for, and what you actually
#: say out loud for each. There is no "hey vesper" here — that is the whole
#: reason WAKE_WORD.md exists.
PRETRAINED = {
    "hey_jarvis": "hey Jarvis",
    "hey_mycroft": "hey Mycroft",
    "hey_rhasspy": "hey Rhasspy",
    "alexa": "Alexa",
}

MODEL_SUFFIXES = (".onnx", ".tflite")


def is_custom(model: str) -> bool:
    """Is this a file you trained, rather than one of the four built in?"""
    return model.lower().endswith(MODEL_SUFFIXES) or "/" in model or "\\" in model


def spoken_phrase(model: str) -> str:
    """What to tell the user to say, derived from whatever is loaded.

    Keeping this next to the model rather than in a separate setting means
    the interface cannot end up telling you to say one thing while the
    detector listens for another.
    """
    if is_custom(model):
        stem = Path(model).stem
        for suffix in MODEL_SUFFIXES:
            if stem.lower().endswith(suffix):
                stem = stem[: -len(suffix)]
        words = stem.replace("-", " ").replace("_", " ").split()
        # "hey_vesper" -> "hey Vesper": lead word lowercase, name capitalised.
        return " ".join(w if i == 0 else w.capitalize()
                        for i, w in enumerate(words)) or stem
    return PRETRAINED.get(model, model.replace("_", " "))


class WakeWordListener:
    """Runs a detection loop on its own thread and calls `on_wake()`."""

    def __init__(self, cfg: Config = CONFIG,
                 mic: Optional[Microphone] = None,
                 on_wake: Optional[Callable[[], None]] = None) -> None:
        self.cfg = cfg
        self.mic = mic or Microphone()
        self.on_wake = on_wake
        self.available = False
        #: Why start() failed, in words a non-technical owner can act on.
        self.problem = ""
        self._model = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # After firing we ignore audio briefly, or one wake word scores above
        # threshold on several overlapping windows and fires repeatedly.
        self._refractory = 1.5

    @property
    def phrase(self) -> str:
        """What the user should actually say, for whatever model is loaded."""
        return self.cfg.wake_phrase or spoken_phrase(self.cfg.wake_model)

    def _fail(self, message: str) -> bool:
        self.problem = message
        LOG.warning("%s", message)
        return False

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if not self.cfg.wake_enabled:
            LOG.info("wake word disabled by config")
            return self._fail("The wake word is switched off (WAKE_ENABLED=false).")
        if not self.mic.available:
            return self._fail(
                "No microphone, so the wake word cannot run. "
                "Check: python -m vesper.sensors.stt --devices")

        want = self.cfg.wake_model
        custom = is_custom(want)

        if custom and not Path(want).is_file():
            return self._fail(
                f"WAKE_MODEL points at {want!r}, which is not a file on this "
                "machine. Train the phrase and save the .onnx next to the "
                "assistant — see WAKE_WORD.md.")
        if not custom and want not in PRETRAINED:
            return self._fail(
                f"{want!r} is not one of the phrases openWakeWord ships. "
                f"Choose one of: {', '.join(sorted(PRETRAINED))} — or train "
                "your own and point WAKE_MODEL at the .onnx (WAKE_WORD.md).")

        try:
            from openwakeword.model import Model
        except Exception as exc:
            return self._fail(
                f"openwakeword is not installed ({exc}), so there is no wake "
                "word. See README step 4. Everything else still works — you "
                "can type, or use the phone.")

        try:
            self._model = Model(wakeword_models=[want],
                                inference_framework="onnx")
        except Exception as exc:
            # Deliberately NOT falling back to the bundled set. That fallback
            # listens for "hey jarvis" and "alexa", so a failed custom model
            # would leave you saying a phrase nothing is listening for, with
            # only a line in the log to explain it.
            return self._fail(
                f"Could not load the wake model {want!r}: {exc}. "
                "Not falling back to the built-in phrases, because then you "
                "would be saying one thing while it listened for another.")

        self.available = True
        self.problem = ""
        return True

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        if not self._ensure_model():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="wake",
                                        daemon=True)
        self._thread.start()
        LOG.info("listening for %r (model %s)", self.phrase, self.cfg.wake_model)
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
    import argparse

    p = argparse.ArgumentParser(description="Wake word check.")
    p.add_argument("--list", action="store_true",
                   help="show the phrases available and what is configured")
    args = p.parse_args(argv)
    setup_logging(CONFIG.log_level)

    if args.list:
        print("\nReady-made phrases (no training, work immediately):\n")
        for name, said in sorted(PRETRAINED.items()):
            here = "  <- configured" if name == CONFIG.wake_model else ""
            print(f'  WAKE_MODEL={name:<12} you say "{said}"{here}')
        print('\nThere is no ready-made "hey Vesper" — nobody has trained one.')
        print("To have it answer to its own name, train the phrase once")
        print("(free, about an hour, in a browser) and then set:\n")
        print("  WAKE_MODEL=hey_vesper.onnx")
        print("\nSee WAKE_WORD.md for the walkthrough.\n")
        print(f"Right now: WAKE_MODEL={CONFIG.wake_model} "
              f'-> say "{spoken_phrase(CONFIG.wake_model)}"')
        return 0

    heard = []
    listener = WakeWordListener(on_wake=lambda: heard.append(time.time()))
    if not listener.start():
        print(f"\n{listener.problem}\n")
        return 1
    print(f"Say “{listener.phrase}”. Ctrl-C to stop.")
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
