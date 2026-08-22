"""The wake word must never listen for a phrase you are not saying.

The failure this guards against is silent and maddening: you set
WAKE_MODEL=hey_vesper.onnx, the file is missing or will not load, the old
code fell back to openWakeWord's bundled set — which listens for "hey
jarvis" and "alexa" — and you spend an evening saying "hey Vesper" into a
room that was never listening for it, with nothing on screen to explain why.

So: a model that cannot load is a hard stop with a readable reason, and the
phrase shown to the user is always derived from the model actually loaded.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.config import Config                                # noqa: E402
from vesper.sensors.wake_word import (PRETRAINED, WakeWordListener,  # noqa: E402
                                      is_custom, spoken_phrase)

bad = 0


def check(label: str, got, want) -> None:
    global bad
    ok = got == want
    if not ok:
        bad += 1
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         got  {got!r}\n         want {want!r}")


class FakeMic:
    """A microphone that exists, so mic availability never masks the point."""
    available = True


def cfg_for(model: str) -> Config:
    c = Config()
    c.wake_enabled = True
    c.wake_model = model
    c.wake_phrase = ""       # derive, which is the default
    return c


print("\n1. the phrase shown is derived from the model loaded")
check("hey_jarvis", spoken_phrase("hey_jarvis"), "hey Jarvis")
check("alexa", spoken_phrase("alexa"), "Alexa")
check("hey_vesper.onnx", spoken_phrase("hey_vesper.onnx"), "hey Vesper")
check("hey-vesper.tflite", spoken_phrase("hey-vesper.tflite"), "hey Vesper")
check("models/hey_vesper.onnx",
      spoken_phrase("models/hey_vesper.onnx"), "hey Vesper")
check("a trained file is custom", is_custom("hey_vesper.onnx"), True)
check("a shipped name is not", is_custom("hey_jarvis"), False)

print("\n2. there is no ready-made 'hey vesper' — say so, do not pretend")
check("not in the shipped set", "hey_vesper" in PRETRAINED, False)
check("the four that do ship", sorted(PRETRAINED),
      ["alexa", "hey_jarvis", "hey_mycroft", "hey_rhasspy"])

print("\n3. a missing custom model stops, and never falls back")
w = WakeWordListener(cfg_for("hey_vesper.onnx"), mic=FakeMic())
started = w.start()
check("did not start", started, False)
check("did not load anything", w.available, False)
check("names the file", "hey_vesper.onnx" in w.problem, True)
check("points at the guide", "WAKE_WORD.md" in w.problem, True)
# The heart of it: whatever it says, it must not have quietly armed a
# different phrase.
check("no fallback phrase armed", w._model, None)
print(f"         said: {w.problem}")

print("\n4. an unknown built-in name is rejected with the real list")
w = WakeWordListener(cfg_for("hey_vesper"), mic=FakeMic())
check("did not start", w.start(), False)
check("lists what does exist", "hey_jarvis" in w.problem, True)
print(f"         said: {w.problem}")

print("\n5. a custom model that IS present gets past the file check")
with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "hey_vesper.onnx"
    path.write_bytes(b"not a real model")
    w = WakeWordListener(cfg_for(str(path)), mic=FakeMic())
    started = w.start()
    # openwakeword is not installed in this sandbox, so it stops at the
    # import rather than the file — either way it must NOT be a fallback.
    check("still no silent fallback", w._model, None)
    check("the complaint is not 'missing file'",
          "is not a file" in w.problem, False)
    check("phrase would be 'hey Vesper'", w.phrase, "hey Vesper")
    print(f"         said: {w.problem}")

print("\n6. no microphone is reported as such, not as a model problem")
class NoMic:
    available = False
w = WakeWordListener(cfg_for("hey_jarvis"), mic=NoMic())
check("did not start", w.start(), False)
check("blames the microphone", "microphone" in w.problem.lower(), True)
check("tells you how to check", "--devices" in w.problem, True)

print("\n7. an explicit WAKE_PHRASE still wins, for wording only")
c = cfg_for("hey_jarvis")
c.wake_phrase = "hey you"
check("override respected", WakeWordListener(c, mic=FakeMic()).phrase, "hey you")

print("\n8. the wake word you choose yourself")
# "I need the wake word hello Vesper to work." The built-in engine ships
# four phrases and nothing else, so a phrase of your own meant an hour in
# Colab with a GPU. Porcupine lets you type it into a web page instead --
# which is the only version of this that actually gets done.
from vesper.sensors.wake_word import Porcupine

_c = cfg_for("hey_jarvis")
_c.porcupine_keyword = "hello_vesper.ppn"
_c.picovoice_key = ""
_pv = Porcupine(_c)
check("no key -> refuses to start", _pv.load(), False)
check("and names the missing key", "PICOVOICE_KEY" in _pv.problem, True)

_c2 = cfg_for("hey_jarvis")
_c2.picovoice_key = "fake"
_c2.porcupine_keyword = ""
_pv2 = Porcupine(_c2)
check("no keyword file -> refuses", _pv2.load(), False)
check("and names the missing file", "PORCUPINE_KEYWORD" in _pv2.problem, True)

_c3 = cfg_for("hey_jarvis")
_c3.picovoice_key = "fake"
_c3.porcupine_keyword = "definitely-not-here.ppn"
_pv3 = Porcupine(_c3)
check("a file that isn't there -> refuses", _pv3.load(), False)
check("and says where it looked", "no wake-word file at" in _pv3.problem, True)

# The one that matters most: adding this must not break what already works.
_c4 = cfg_for("hey_jarvis")
_c4.picovoice_key = ""
_c4.porcupine_keyword = ""
_c4.wake_engine = "auto"
check("with none of it set up, still hey Jarvis",
      WakeWordListener(_c4, mic=FakeMic()).phrase, "hey Jarvis")

# Asking for porcupine explicitly must NOT quietly fall back -- that would
# leave you saying "hello Vesper" at something listening for Jarvis.
_c5 = cfg_for("hey_jarvis")
_c5.wake_engine = "porcupine"
_c5.picovoice_key = ""
_w5 = WakeWordListener(_c5, mic=FakeMic())
check("engine=porcupine never falls back silently", _w5._ensure_model(), False)
check("and says why", "PICOVOICE_KEY" in _w5.problem, True)

# A .ppn cannot be asked which phrase it holds, so the filename is the best
# available answer -- and the console names it after what you typed.
_c6 = cfg_for("hey_jarvis")
_c6.picovoice_key = "k"
_c6.porcupine_keyword = "hello vesper_en_windows_v3_0_0.ppn"
_c6.wake_phrase = ""
check("the phrase is read off the filename",
      WakeWordListener(_c6, mic=FakeMic()).phrase, "hello vesper")


sys.exit(1 if bad else 0)
