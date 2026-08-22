"""Hearing a wake phrase you chose, with nobody's permission.

Three routes were tried for "hello Vesper":

  * openwakeword — four fixed phrases; your own means an hour in Colab.
  * Picovoice    — lets you type it, but wants a company email, and
                   withdrew its free tier on 30 June 2026.
  * this         — the recogniser already installed for everything else.

The risk with the third is the opposite of the first two. Those failed
closed: no phrase, no wake. This can fail OPEN — waking at the television,
at a hallucinated transcript of silence, or at somebody saying the word
in passing. So most of these tests are about NOT waking.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.config import Config  # noqa: E402
from vesper.sensors.heard_phrase import (close_enough,  # noqa: E402
                                         looks_like_just_noise, normalise,
                                         split_wake)
from vesper.sensors.wake_word import SpeechWake  # noqa: E402

PHRASE = "hello vesper"


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  {detail}" if detail else ""))
    return ok


class FakeListener:
    available = True

    def __init__(self, lines):
        self.lines = list(lines)
        self.windows = []

    def listen_once(self, start_window=None):
        self.windows.append(start_window)
        return self.lines.pop(0) if self.lines else ""


def main() -> int:
    bad = 0

    # -- 1. it wakes to what you actually said -----------------------------
    for said in ("Hello Vesper.", "hello vesper", "Hello, Vesper!",
                 "um, hello Vesper"):
        heard, _rest = split_wake(said, PHRASE)
        bad += not check(f"wakes: {said!r}", heard)

    # -- 2. and to what the recogniser heard instead -----------------------
    # These are near-misses a machine makes and a person never does.
    for said in ("hello vespa", "hello whisper", "Hello Vester",
                 "hello vesber"):
        heard, _rest = split_wake(said, PHRASE)
        bad += not check(f"forgives: {said!r}", heard)

    # -- 3. THE IMPORTANT HALF: it does not wake to everything else -------
    for said in ("hello there", "what is the weather", "goodbye vesper",
                 "I said hello to Vesper yesterday", "hello",
                 "tell Vesper hello from me", "yellow pepper"):
        heard, _rest = split_wake(said, PHRASE)
        bad += not check(f"ignores: {said!r}", not heard)

    # -- 4. the command rides in with the phrase ---------------------------
    # A keyword spotter can only say "the phrase happened". Because this
    # reads the whole sentence, "hello Vesper, what's the weather" is one
    # breath rather than a wake and then a question.
    cases = [
        # The question mark survives: it is meaning, not punctuation.
        ("Hello Vesper, what's the weather today?",
         "what's the weather today?"),
        ("hello vespa brief me", "brief me"),
        # ...and the trailing full stop does not: it carries nothing.
        ("Hello Vesper — should I take the V trade? It's 4% off.",
         "should I take the V trade? It's 4% off"),
        ("Hello Vesper.", None),
    ]
    for said, want in cases:
        _heard, rest = split_wake(said, PHRASE)
        bad += not check(f"carries: {said[:34]!r}...", rest == want, repr(rest))

    # The command keeps its OWN words. It goes to the model, so stripping
    # the apostrophes out of it ("what s the weather") is a real loss.
    _h, rest = split_wake("Hello Vesper, what's on my map?", PHRASE)
    bad += not check("the command keeps its apostrophes",
                     rest == "what's on my map?", repr(rest))

    # -- 5. silence must not wake it ---------------------------------------
    # Whisper hallucinates on a quiet room, reliably and always the same
    # few phrases. Without this a silent kitchen wakes her every minute.
    for junk in ("Thank you.", "you", "", "   ", "Thanks for watching!",
                 "Subtitles by the Amara.org community"):
        bad += not check(f"silence: {junk!r}", looks_like_just_noise(junk))
    bad += not check("but real speech is not noise",
                     not looks_like_just_noise("hello vesper"))

    # -- 6. tolerance is a dial, and it moves ------------------------------
    bad += not check("strict rejects a near-miss",
                     not close_enough("hello vespa", PHRASE, 0.05))
    bad += not check("loose accepts it",
                     close_enough("hello vespa", PHRASE, 0.34))
    bad += not check("even loose rejects a different phrase",
                     not close_enough("goodbye everyone", PHRASE, 0.34))

    # -- 7. the listener end to end ----------------------------------------
    cfg = Config()
    cfg.wake_phrase = PHRASE
    sw = SpeechWake(cfg, listener=FakeListener(["Hello Vesper, brief me."]))
    bad += not check("it loads with a phrase set", sw.load(), sw.problem)
    bad += not check("and returns the carried command",
                     sw.listen() == "brief me")

    sw2 = SpeechWake(cfg, listener=FakeListener(["Thank you."]))
    sw2.load()
    bad += not check("a hallucination returns nothing",
                     sw2.listen() is None)

    sw3 = SpeechWake(cfg, listener=FakeListener(["what's the weather"]))
    sw3.load()
    bad += not check("speech without the phrase returns nothing",
                     sw3.listen() is None)

    sw4 = SpeechWake(cfg, listener=FakeListener(["Hello Vesper."]))
    sw4.load()
    bad += not check("the bare phrase returns an empty string, not None",
                     sw4.listen() == "")

    # -- 8. it refuses clearly rather than half-working --------------------
    blank = Config()
    blank.wake_phrase = ""
    sw5 = SpeechWake(blank, listener=FakeListener([]))
    bad += not check("no phrase set: refuses", not sw5.load())
    bad += not check("and names the setting", "WAKE_PHRASE" in sw5.problem,
                     sw5.problem)

    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
