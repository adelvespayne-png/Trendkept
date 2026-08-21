"""Start speaking before the answer has finished being written.

The single largest thing you can do about how fast an assistant *feels*,
and it is not about making anything faster. A reply that takes four
seconds to generate takes four seconds either way; the difference is
whether you spend them in silence or listening to the first sentence.

The measured effect is large. Streaming with sentence-level chunking puts
time-to-first-audio in the region of a few hundred milliseconds where
batching puts it at the full generation time — several seconds — and the
perceived speed follows the first number, not the total. A system that
takes LONGER overall but starts sooner feels faster, because you are
listening while the rest is still being written.

Two pieces here:

  * `sentences()` — split a growing text into speakable units the moment
    each one is complete, and not before.
  * `stream_openai()` — read an OpenAI-dialect SSE response and yield the
    text as it arrives.

Sources for the approach: soniox.com/wiki/streaming-tts and
smallest.ai's latency-budget write-up, both August 2026.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Iterable, Iterator, List, Optional

LOG = logging.getLogger("vesper.stream")

#: Enough to say on its own. Below this, waiting for more is better than
#: emitting a fragment -- a TTS engine given two words reads them flatly,
#: with none of the intonation that makes a sentence sound like one.
#:
#: Sixteen, not twenty-four: "Your stop is at 346.81." is twenty-three
#: characters and a perfectly good thing to say on its own. The floor is
#: here to stop "Yes." and "Right." being spoken as separate utterances,
#: not to swallow short real sentences into the next one.
MIN_CHUNK = 16

#: An end mark followed by whitespace or a closing quote.
#:
#: Deliberately NOT anchored to end-of-string. Mid-stream the buffer ends
#: wherever the last packet happened to stop, and "$" there means "we have
#: not received the next character yet" -- not "the sentence is over". With
#: it, "your stop is at 346.81" arriving six characters at a time split
#: into "Your stop is at 346." and "81." The final flush handles the tail;
#: everything before it must wait for real evidence the sentence ended.
_END = re.compile(r"[.!?…](?=[\s\"'’”)\]])|[:;](?=\s)")

#: Abbreviations that end in a full stop without ending a sentence. Cutting
#: at "Mr." or "e.g." gives the speech engine a fragment and a false pause.
_NOT_AN_END = re.compile(
    r"(?:\b(?:mr|mrs|ms|dr|prof|sr|jr|st|vs|etc|e\.g|i\.e|approx|fig|no)\.$"
    r"|\b[A-Z]\.$"                       # a single initial
    # A numbered list item -- but ONLY at the start of a line. Without
    # that anchor this matched the tail of any decimal, so "your stop is
    # at 346.81." was read as list item 81 and the sentence never ended.
    r"|(?:^|\n)\s*\d{1,2}\.$)", re.I)


def _is_real_end(text: str, at: int) -> bool:
    """Is the mark at `at` actually the end of a sentence?"""
    head = text[:at + 1].rstrip()
    return not _NOT_AN_END.search(head)


def sentences(chunks: Iterable[str], flush_at: int = 320) -> Iterator[str]:
    """Turn a stream of text fragments into a stream of speakable ones.

    Yields as soon as a sentence is complete, so the first one can be
    spoken while the rest is still arriving. `flush_at` is the point where
    a run of text with no punctuation is emitted anyway — some models write
    long unpunctuated stretches, and waiting for a full stop that may never
    come is how a "streaming" assistant ends up silent for four seconds.
    """
    buf = ""
    for piece in chunks:
        if not piece:
            continue
        buf += piece
        while True:
            cut = -1
            for m in _END.finditer(buf):
                if m.end() >= MIN_CHUNK and _is_real_end(buf, m.start()):
                    cut = m.end()
                    break
            if cut < 0:
                # No end in sight. If it has run long, break at the last
                # comma or space rather than holding the whole thing.
                if len(buf) >= flush_at:
                    soft = max(buf.rfind(", ", 0, flush_at),
                               buf.rfind(" ", 0, flush_at))
                    cut = soft + 1 if soft > MIN_CHUNK else flush_at
                else:
                    break
            said, buf = buf[:cut].strip(), buf[cut:].lstrip()
            if said:
                yield said
    if buf.strip():
        yield buf.strip()


def stream_openai(response, on_tool=None) -> Iterator[str]:
    """Yield text from an OpenAI-dialect streaming response.

    Tool calls arrive in the same stream, assembled across deltas. They
    cannot be acted on until complete, so they are collected and handed to
    `on_tool` at the end rather than yielded — there is nothing to say
    about a tool call while it is still being spelled out.
    """
    calls: dict = {}
    for raw in response:
        line = raw.decode("utf-8", "replace").strip() if isinstance(raw, bytes) \
            else str(raw).strip()
        if not line or not line.startswith("data:"):
            continue
        body = line[5:].strip()
        if body == "[DONE]":
            break
        try:
            packet = json.loads(body)
        except ValueError:
            continue
        for choice in packet.get("choices") or []:
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if text:
                yield text
            for call in delta.get("tool_calls") or []:
                idx = call.get("index", 0)
                slot = calls.setdefault(
                    idx, {"id": "", "function": {"name": "", "arguments": ""}})
                if call.get("id"):
                    slot["id"] = call["id"]
                fn = call.get("function") or {}
                if fn.get("name"):
                    slot["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["function"]["arguments"] += fn["arguments"]
    if calls and on_tool:
        on_tool([calls[k] for k in sorted(calls)])


def first_words(text: str, limit: int = 90) -> str:
    """The opening of a reply, cut at a sentence if one is near.

    Used when something has to be said immediately — the opening line of a
    long answer, spoken while the rest is still being written.
    """
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    window = text[:limit]
    # The FIRST complete sentence, not the last that fits. This is used
    # for the opening line of a long answer, and an opening line should
    # be one sentence rather than as many as happen to fit in ninety
    # characters.
    for m in _END.finditer(window + " "):
        if m.end() >= MIN_CHUNK:
            return window[:m.end()].strip()
    cut = window.rfind(" ")
    return (window[:cut] if cut > MIN_CHUNK else window).strip() + "…"
