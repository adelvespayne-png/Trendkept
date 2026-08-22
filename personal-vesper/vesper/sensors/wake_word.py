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


class Porcupine:
    """Picovoice Porcupine — the engine that can hear a phrase of your own.

    openwakeword ships four pretrained phrases and nothing else, so
    "hello Vesper" meant training a model: an hour in Colab, a GPU, and a
    working knowledge of what a false-accept rate is. That is not a
    reasonable ask, and it is why the wake word has stayed "hey Jarvis"
    for a week.

    Porcupine's free Personal tier lets you TYPE the phrase into a web
    page and download the model. Two minutes, no training, no notebook.
    The licence is non-commercial personal use, which is exactly what
    this is -- and worth stating plainly rather than discovering later.

    It wants its own frame size and sample rate, which is why this is a
    class rather than a branch: it owns its own reading loop.
    """

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self._pv = None
        self.problem = ""
        self.frame_length = 512
        self.sample_rate = 16000

    def load(self) -> bool:
        key = self.cfg.picovoice_key
        path = (self.cfg.porcupine_keyword or "").strip()
        if not key:
            self.problem = ("no PICOVOICE_KEY in .env — get a free one at "
                            "console.picovoice.ai")
            return False
        if not path:
            self.problem = ("no PORCUPINE_KEYWORD in .env — the .ppn file "
                            "you downloaded from the Picovoice console")
            return False
        model = Path(path)
        if not model.is_absolute():
            model = Path(__file__).resolve().parent.parent.parent / path
        if not model.is_file():
            self.problem = f"no wake-word file at {model}"
            return False
        try:
            import pvporcupine
        except Exception as exc:
            self.problem = (f"pvporcupine is not installed ({exc}). Run "
                            "Install Vesper.bat again to add it.")
            return False
        try:
            self._pv = pvporcupine.create(
                access_key=key, keyword_paths=[str(model)],
                sensitivities=[self.cfg.wake_threshold])
        except Exception as exc:
            # The two that actually happen: a key that is not accepted, and
            # a .ppn built for a different platform. Both say so clearly.
            hint = ""
            low = str(exc).lower()
            if "activation" in low or "access" in low or "key" in low:
                hint = " — check PICOVOICE_KEY against console.picovoice.ai"
            elif "platform" in low or "arch" in low:
                hint = (" — that .ppn was built for a different platform; "
                        "download the Windows (x86_64) one")
            self.problem = f"Porcupine would not start: {exc}{hint}"
            return False
        self.frame_length = self._pv.frame_length
        self.sample_rate = self._pv.sample_rate
        self.problem = ""
        return True

    def heard(self, samples) -> bool:
        """True when the phrase was just said."""
        try:
            return self._pv.process(samples) >= 0
        except Exception:
            LOG.debug("porcupine frame failed", exc_info=True)
            return False

    def close(self) -> None:
        try:
            if self._pv:
                self._pv.delete()
        except Exception:
            pass
        self._pv = None


class SpeechWake:
    """Hear the phrase by transcribing what was said, not by spotting it.

    The third route to "hello Vesper", and the first that depends on
    nobody: openwakeword has four fixed phrases, Picovoice wants a company
    email and closed its free tier on 30 June 2026, and this uses the
    recogniser already installed for every other spoken word.

    It only transcribes when there IS sound, so a quiet room costs one
    RMS calculation per frame. And because the phrase and the command
    land in the same transcript, "hello Vesper, what's the weather" is one
    breath rather than a wake followed by a question.
    """

    def __init__(self, cfg, listener=None) -> None:
        self.cfg = cfg
        self.problem = ""
        self._listener = listener

    def load(self) -> bool:
        phrase = (self.cfg.wake_phrase or "").strip()
        if not phrase:
            self.problem = ("no WAKE_PHRASE in .env — the words you want to "
                            "say, e.g. 'hello vesper'")
            return False
        if self._listener is None:
            from .stt import Listener

            self._listener = Listener(self.cfg)
        if not self._listener.available:
            self.problem = ("the speech recogniser is not available, and "
                            "this way of hearing the wake word needs it")
            return False
        self.problem = ""
        return True

    def listen(self):
        """Block until the phrase is said. Returns the rest, or ''.

        `None` means nothing was heard worth considering -- the caller
        should simply go round again.
        """
        from .heard_phrase import looks_like_just_noise, split_wake

        # A long start window: this is the idle loop, and it should sit
        # patiently rather than reopening the microphone every few seconds.
        text = self._listener.listen_once(start_window=3600.0)
        if not text or looks_like_just_noise(text):
            return None
        heard, rest = split_wake(text, self.cfg.wake_phrase,
                                 self.cfg.wake_tolerance)
        if not heard:
            LOG.debug("heard %r, not the wake phrase", text[:60])
            return None
        return rest or ""


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
        self._porcupine = None
        self._speech = None
        self._listener = None      # injectable, for tests
        #: Set when the wake phrase and the command arrived together, so
        #: the caller can answer without asking them to repeat it.
        self.carried = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # After firing we ignore audio briefly, or one wake word scores above
        # threshold on several overlapping windows and fires repeatedly.
        self._refractory = 1.5

    @property
    def phrase(self) -> str:
        """What the user should actually say, for whatever model is loaded."""
        if self.cfg.wake_phrase:
            return self.cfg.wake_phrase
        if self._porcupine or (self.cfg.picovoice_key
                               and self.cfg.porcupine_keyword):
            # The phrase is baked into the .ppn and cannot be read back
            # out of it, so fall back to the filename -- which the console
            # names after the phrase you typed.
            stem = Path(self.cfg.porcupine_keyword or "").stem
            guess = stem.split("_")[0].replace("-", " ").strip()
            return guess or "your wake word"
        return spoken_phrase(self.cfg.wake_model)

    def _fail(self, message: str) -> bool:
        self.problem = message
        LOG.warning("%s", message)
        return False

    def _ensure_model(self) -> bool:
        # Porcupine first when it is configured, because it is the only
        # one that can hear a phrase you chose. openwakeword stays as the
        # fallback: four fixed phrases, but nothing to sign up for.
        want_engine = (self.cfg.wake_engine or "auto").lower()

        # `speech` first when a phrase of your own has been set, because it
        # is the only route that needs no account and cannot be withdrawn.
        if want_engine in ("auto", "speech"):
            if self.cfg.wake_phrase.strip() or want_engine == "speech":
                sw = SpeechWake(self.cfg, listener=self._listener)
                if sw.load():
                    self._speech = sw
                    self._model = None
                    self.problem = ""
                    LOG.info("wake word: listening for %r in what you say",
                             self.phrase)
                    return True
                if want_engine == "speech":
                    return self._fail(sw.problem)
                LOG.debug("speech wake unavailable (%s)", sw.problem)

        if want_engine in ("auto", "porcupine"):
            pv = Porcupine(self.cfg)
            if pv.load():
                self._porcupine = pv
                self._model = None
                self.problem = ""
                LOG.info("wake word: Porcupine, listening for %r", self.phrase)
                return True
            if want_engine == "porcupine":
                return self._fail(pv.problem)
            LOG.debug("porcupine unavailable (%s); using openwakeword",
                      pv.problem)
        return self._ensure_openwakeword()

    def _ensure_openwakeword(self) -> bool:
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
        if self._speech:
            return self._speech_loop()
        import numpy as np

        last_fire = 0.0
        # Porcupine dictates its own frame size; openwakeword takes ours.
        frame = (self._porcupine.frame_length if self._porcupine
                 else FRAME_SAMPLES)
        try:
            with self.mic.stream(frames=frame) as stream:
                while not self._stop.is_set():
                    block, _overflow = stream.read(frame)
                    samples = np.frombuffer(bytes(block), dtype=np.int16)
                    if self._porcupine:
                        best = 1.0 if self._porcupine.heard(samples) else 0.0
                        threshold = 1.0
                    else:
                        scores = self._model.predict(samples)
                        best = max(scores.values()) if scores else 0.0
                        threshold = self.cfg.wake_threshold
                    now = time.monotonic()
                    if best >= threshold and \
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


    def _speech_loop(self) -> None:
        """The transcribe-and-match loop, which owns its own microphone."""
        while not self._stop.is_set():
            try:
                rest = self._speech.listen()
            except Exception:
                LOG.exception("speech wake loop stopped")
                return
            if rest is None:
                continue
            # They may have said the whole thing at once. Hand the command
            # over so it is answered rather than asked for again.
            self.carried = rest or None
            LOG.info("wake phrase heard%s",
                     f", carrying: {rest!r}" if rest else "")
            if self.on_wake:
                try:
                    self.on_wake()
                except Exception:
                    LOG.exception("wake callback failed")


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
