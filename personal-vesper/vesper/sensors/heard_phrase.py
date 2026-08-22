"""Matching a wake phrase in something that was actually transcribed.

The third attempt at "hello Vesper", and the first that needs nobody's
permission.

  * openwakeword ships four fixed phrases. Training your own is an hour in
    Colab with a GPU.
  * Picovoice lets you type a phrase — but wants a company email, and
    withdrew its free tier on 30 June 2026 anyway.
  * This uses the speech recogniser already installed for everything else.
    Any phrase, no account, no training, nothing that can be discontinued.

The cost is that a transcriber is slower than a keyword spotter, so it
only runs when there is actually sound — silence costs one RMS
calculation per frame and nothing else.

The gain is bigger than parity. A keyword spotter tells you the phrase
happened and then you start listening; here the phrase and the command
arrive in the SAME transcript, so "hello Vesper, what's the weather"
works as one breath instead of two turns.

Matching has to be loose. A recogniser hears "hello vespa", "hello
whisper", "hello vester" — near-misses that a person would never make and
a strict comparison rejects every time.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

LOG = logging.getLogger("vesper.phrase")

_TIDY = re.compile(r"[^a-z0-9 ]+")

#: Filler a recogniser inserts that no one meant to say.
_NOISE = {"um", "uh", "erm", "ah", "oh", "hmm", "mm", "so", "okay", "ok"}


def normalise(text: str) -> str:
    """Lowercase, punctuation gone, filler gone, single spaces."""
    words = _TIDY.sub(" ", (text or "").lower()).split()
    return " ".join(w for w in words if w not in _NOISE)


def _distance(a: str, b: str) -> int:
    """Levenshtein, iterative. Short strings, so the simple one is fine."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1,
                               current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def close_enough(said: str, want: str, tolerance: float = 0.34) -> bool:
    """Is `said` near enough to `want` to count as having said it?

    Proportional rather than a fixed edit count: two wrong letters in
    "hi" is a different word, two wrong letters in "hello vesper" is a
    microphone in a kitchen.
    """
    said, want = normalise(said), normalise(want)
    if not (said and want):
        return False
    if said == want:
        return True
    allowed = max(1, int(len(want) * tolerance))
    if _distance(said, want) > allowed:
        return False

    # AND the first word has to be close, on a tighter budget.
    #
    # Whole-string distance alone is too generous over two words: it let
    # through "tell Vesper hello from me" and, memorably, "yellow pepper"
    # -- both within four edits of "hello vesper" across twelve
    # characters. The opening word is what a person actually says
    # deliberately, so it gets held to a stricter standard than the rest.
    head_said = said.split()[0]
    head_want = want.split()[0]
    head_allowed = max(1, int(len(head_want) * tolerance * 0.6))
    return _distance(head_said, head_want) <= head_allowed


def split_wake(text: str, phrase: str,
               tolerance: float = 0.34) -> Tuple[bool, Optional[str]]:
    """Was the phrase said, and what came after it?

    Returns (heard, rest). `rest` is None when the phrase was all they
    said — that is the plain "wake me up" case and the caller should
    listen for the command. When `rest` has words in it, they said the
    whole thing in one breath and it can be answered immediately.

    The phrase is matched against the OPENING of the utterance, at a few
    different lengths, because a recogniser splits words unpredictably:
    "hello vesper" may arrive as two words or as one.
    """
    want = normalise(phrase)
    if not ((text or "").strip() and want):
        return False, None

    # Work on the ORIGINAL words, keeping where each one starts. The
    # command is handed to the model, so it must keep its apostrophes and
    # its capitals -- matching on a stripped copy and then returning the
    # stripped copy turned "what's the weather" into "what s the weather".
    spans = [(m.start(), m.end(), m.group())
             for m in re.finditer(r"\S+", text)]
    kept = [(s, e, w) for s, e, w in spans if normalise(w)]
    if not kept:
        return False, None

    want_words = len(want.split())
    for take in range(max(1, want_words - 1), want_words + 2):
        if take > len(kept):
            break
        head = normalise(" ".join(w for _s, _e, w in kept[:take]))
        if close_enough(head, want, tolerance):
            after = kept[take][0] if take < len(kept) else len(text)
            # Leading separators go, and so does a trailing full stop --
            # but NOT a question mark. The command is handed to the model,
            # where "what's on my map?" is a better prompt than the same
            # words flattened into a statement, while a full stop carries
            # nothing at all.
            rest = text[after:].lstrip(" ,.;:-—").rstrip(" ,;:-—.")
            return True, (rest or None)
    return False, None


def looks_like_just_noise(text: str, min_words: int = 1) -> bool:
    """Transcripts that are not worth considering at all.

    Whisper hallucinates on silence — "Thank you.", "you", a subtitle
    credit — reliably enough that these have to be excluded by name or
    a quiet room wakes the assistant every few seconds.
    """
    said = normalise(text)
    if not said or len(said.split()) < min_words:
        return True
    return said in {
        "you", "thank you", "thanks", "thanks for watching",
        "thank you for watching", "bye", "the", "subtitles by the amara org "
        "community", "amara org", "please subscribe",
    }
