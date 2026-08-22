"""Speaking before the answer is finished.

The largest single thing you can do about how fast an assistant FEELS, and
it makes nothing faster. A four-second reply takes four seconds either
way; what changes is whether those seconds are silent or spent listening
to the first sentence. Perceived speed follows time-to-first-word, not
total time.

So these tests are about WHEN text arrives, not whether it is correct.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.core.stream import (MIN_CHUNK, first_words,  # noqa: E402
                                sentences, stream_openai)


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  {detail}" if detail else ""))
    return ok


class SSE:
    """A provider streaming a reply back the way real ones do: in pieces."""

    def __init__(self, text, size=6, tools=None):
        self.lines = [
            ("data: " + json.dumps(
                {"choices": [{"delta": {"content": text[i:i + size]}}]})).encode()
            for i in range(0, len(text), size)]
        if tools:
            self.lines.append(("data: " + json.dumps(
                {"choices": [{"delta": {"tool_calls": tools}}]})).encode())
        self.lines.append(b"data: [DONE]")

    def __iter__(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def main() -> int:
    bad = 0
    tmp = Path(tempfile.mkdtemp())

    # -- 1. splitting, including the cases that bite ----------------------
    cases = [
        ("Your stop is at 346.81. Nothing to do today.",
         ["Your stop is at 346.81.", "Nothing to do today."],
         "a decimal ending a sentence is not a list item"),
        ("Dr. Smith would call that fine. He is right.",
         ["Dr. Smith would call that fine.", "He is right."],
         "an abbreviation does not end a sentence"),
        ("1. Check the trend.\n2. Place the stop.",
         ["1. Check the trend.", "2. Place the stop."],
         "a real numbered list still splits"),
    ]
    for text, want, why in cases:
        got = list(sentences([text]))
        bad += not check(why, got == want, str(got))

    # Arriving six characters at a time must give the same answer as
    # arriving whole -- that is the entire point of the buffer.
    whole = "The trend is intact, sir. Your stop is at 346.81. Nothing to do."
    drip = list(sentences([whole[i:i + 6] for i in range(0, len(whole), 6)]))
    bad += not check("dripping in gives the same split as arriving whole",
                     drip == list(sentences([whole])), str(drip))

    # -- 2. a wall of text with no punctuation still gets spoken ----------
    runon = "word " * 200
    got = list(sentences([runon]))
    bad += not check("unpunctuated text is flushed, not held forever",
                     len(got) > 1, f"{len(got)} chunks")
    bad += not check("and nothing is lost when it is",
                     " ".join(got).split() == runon.split())

    # -- 3. tool calls are assembled, not spoken --------------------------
    seen = []
    r = SSE("Checking that.", tools=[{"index": 0, "id": "c1", "function":
                                      {"name": "read_map", "arguments": '{"a":1}'}}])
    text = "".join(stream_openai(r, on_tool=seen.append))
    bad += not check("text streams out", text == "Checking that.", repr(text))
    bad += not check("and the tool call is handed over whole",
                     bool(seen) and seen[0][0]["function"]["name"] == "read_map",
                     str(seen))

    # -- 4. the point: the first sentence lands long before the last ------
    sys.argv = ["x"]
    import selftest_gateway as G

    reply = ("The trend is intact on Visa, sir. Your stop is at 346.81. "
             "That is about four percent below the last price. "
             "Nothing to do today.")

    class Slow(SSE):
        """Six characters every 5ms, as a real model writes."""

        def __iter__(self):
            for line in self.lines:
                time.sleep(0.005)
                yield line

    keep = urllib.request.urlopen
    urllib.request.urlopen = lambda req, timeout=None: Slow(reply)
    b = G.make_brain(tmp, models="fast")
    b.tools = []
    landed = []
    started = time.monotonic()
    b.on_sentence = lambda s, first: landed.append(
        (time.monotonic() - started, s, first))
    out = asyncio.run(b.respond("how is Visa doing", channel="voice"))
    total = time.monotonic() - started
    urllib.request.urlopen = keep

    print(f"  ..   whole reply took {total * 1000:.0f}ms")
    for at, said, first in landed:
        print(f"  ..   {at * 1000:6.0f}ms {'FIRST ' if first else '      '}{said}")

    bad += not check("every sentence was delivered", len(landed) == 4,
                     str(len(landed)))
    bad += not check("the first one is marked as first",
                     landed and landed[0][2] is True)
    bad += not check("and it lands in well under half the total time",
                     landed and landed[0][0] < total * 0.5,
                     f"{landed[0][0]*1000:.0f}ms of {total*1000:.0f}ms")
    bad += not check("the full text is still returned",
                     bool(out) and "346.81" in out and out.endswith("today."),
                     repr(out))

    # -- 5. THE ONE THAT MATTERED: streaming must survive real tools ------
    # This originally asserted the OPPOSITE -- that a turn carrying tools
    # said nothing early, on the reasoning that a half-spoken answer might
    # be replaced by a tool result. But a normal turn carries fourteen
    # tools, so that condition was never false and the streaming was dead
    # code: all of the work, none of the benefit. "It still takes a while
    # to respond" was precisely this.
    from vesper.tools.tool_definitions import tool_definitions

    real = tool_definitions(include_web=True, include_map=True,
                            include_search=True)
    urllib.request.urlopen = lambda req, timeout=None: SSE(
        "The trend is intact, sir. Nothing to do today.")
    b2 = G.make_brain(tmp, models="fast")
    b2.tools = real
    early = []
    b2.on_sentence = lambda s, first: early.append(s)
    out2 = asyncio.run(b2.respond("how is Visa", channel="voice"))
    urllib.request.urlopen = keep
    bad += not check(f"a turn with {len(real)} real tools STILL streams",
                     len(early) == 2, str(early))
    bad += not check("and returns the whole answer",
                     bool(out2) and "Nothing to do" in out2, repr(out2))

    # -- 5b. a tool call inside a stream still runs -----------------------
    class WithTool:
        def __init__(self):
            pre = "Let me check that, sir."
            self.lines = [("data: " + json.dumps(
                {"choices": [{"delta": {"content": pre[i:i + 6]}}]})).encode()
                for i in range(0, len(pre), 6)]
            self.lines.append(("data: " + json.dumps({"choices": [{"delta": {
                "tool_calls": [{"index": 0, "id": "c1", "function": {
                    "name": "read_map", "arguments": "{}"}}]}}]})).encode())
            self.lines.append(b"data: [DONE]")

        def __iter__(self): return iter(self.lines)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    ran = []

    class Exec(G.FakeExecutor):
        def run(self, name, args):
            ran.append(name)
            return "the map says: Visa, stop 346.81", False

    step = {"n": 0}

    def two_rounds(req, timeout=None):
        step["n"] += 1
        return WithTool() if step["n"] == 1 else \
            G.FakeResponse(G.reply("Stop at 346.81, sir."))

    urllib.request.urlopen = two_rounds
    b3 = G.make_brain(tmp, models="fast")
    b3.executor = Exec()
    b3.tools = [{"name": "read_map", "description": "read it",
                 "input_schema": {"type": "object", "properties": {}}}]
    spoke = []
    b3.on_sentence = lambda s, first: spoke.append(s)
    out3 = asyncio.run(b3.respond("what does my map say", channel="voice"))
    urllib.request.urlopen = keep
    bad += not check("the preamble is spoken while it works",
                     bool(spoke) and "check that" in spoke[0], str(spoke))
    bad += not check("the tool call survives the stream", ran == ["read_map"],
                     str(ran))
    bad += not check("and the second round answers",
                     bool(out3) and "346.81" in out3, repr(out3))

    # -- 5c. a provider that cannot stream must not be lost ---------------
    rec = G.Recorder([G.reply("Checked, sir."), G.reply("Checked, sir.")])
    urllib.request.urlopen = rec
    b4 = G.make_brain(tmp, models="fast")
    b4.tools = real
    b4.on_sentence = lambda s, first: None
    out4 = asyncio.run(b4.respond("what is on my map", channel="voice"))
    urllib.request.urlopen = keep
    bad += not check("a non-streaming provider still answers",
                     bool(out4) and "Checked" in out4, repr(out4))

    # -- 6. first_words, for when something must be said immediately ------
    bad += not check("first_words cuts at a sentence when it can",
                     first_words(reply) == "The trend is intact on Visa, sir.",
                     first_words(reply))
    bad += not check("and never returns more than asked",
                     len(first_words("x " * 200, limit=40)) <= 41)

    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
