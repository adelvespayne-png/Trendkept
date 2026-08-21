"""The gateway turn, which on a setup with no Anthropic key IS the brain.

Three things went wrong here at once and they all looked identical from the
outside — Vesper saying nothing, or saying something thin:

  1. A busy model ("this model is currently experiencing high demand", a
     503) was treated as a dead one. The ladder stepped down on the first
     refusal, ran off the end, and the turn came back empty.
  2. The gateway was handed the bare sentence: no clock, no room, no
     channel note, and no memory of the turn before it. The Anthropic path
     gets all four. So on a free-only setup Vesper genuinely had no context
     to be intelligent with.
  3. When every rung really was out, the turn returned None — silence the
     user cannot tell apart from stupidity.

These are behaviour tests against a fake HTTP layer, not assertions that a
flag is set somewhere. The last time I tested the flag instead of the
behaviour the test passed over the top of a live bug.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.config import Config  # noqa: E402
from vesper.core import brain as brain_mod  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()
        self.headers = {}

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Body:
    """An HTTPError whose .read() returns a body, as urllib's really does."""

    def __init__(self, blob):
        self._b = blob.encode()

    def read(self):
        return self._b


def http(code, msg, body=""):
    e = urllib.error.HTTPError("http://x", code, msg, {}, None)
    if body:
        e.read = _Body(body).read
    return e


def busy(code=503):
    return http(code, "Service Unavailable")


# The three refusals from the owner's own log on 20 August, verbatim.
QUOTA = http(429, "Too Many Requests", json.dumps({"error": {
    "code": 429, "message": "You exceeded your current quota, please check "
    "your plan and billing details. For more information on this error, head "
    "to: https://ai.google.dev/gemini-api/docs/rate-limits."}}))
RETIRED = http(404, "Not Found", json.dumps({"error": {
    "code": 404, "message": "This model models/gemini-2.5-flash is no longer "
    "available to new users. Please update your code to use "
    "models/gemini-3.6-flash for the latest features and improvements.",
    "status": "NOT_FOUND"}}))
BADKEY = http(401, "Unauthorized", json.dumps({"error": {
    "code": 401, "message": "API key not valid. Please pass a valid API key."}}))


def reply(text):
    return {"choices": [{"message": {"content": text},
                         "finish_reason": "stop"}]}


class Recorder:
    """Stands in for urlopen. Plays a script, and keeps every request body."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.reqs = []

    def __call__(self, req, timeout=None):
        self.sent.append(json.loads(req.data.decode()))
        self.reqs.append(req)
        step = self.script.pop(0) if self.script else reply("(ran out)")
        if isinstance(step, Exception):
            raise step
        return FakeResponse(step)


class FakeState:
    def snapshot(self):
        class S:
            def describe(self, news=False):
                return "the room is quiet"

            def get(self, k):
                return {}
        return S()

    def append_conversation(self, *a):
        pass


class FakeExecutor:
    map = None
    spoken = None
    silent_reason = None

    def reset_turn(self):
        self.spoken = None

    def run(self, name, args):
        return "", False


def make_brain(tmp: Path, models="a,b,c"):
    cfg = Config()
    cfg.fallback_enabled = True
    cfg.fallback_models = models
    cfg.fallback_base = "http://fake/v1/chat/completions"
    cfg.fallback_token = "t"
    cfg.models = "gateway"
    cfg.anthropic_api_key = ""
    cfg.log_path = tmp / "conv.jsonl"
    b = brain_mod.Brain(FakeState(), FakeExecutor(), cfg=cfg, client=None)
    b.tools = []
    return b


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  {detail}" if detail else ""))
    return ok


def main() -> int:
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    bad = 0
    brain_mod._GATEWAY_BACKOFF = 0.001      # don't actually wait in a test

    import urllib.request as ur
    keep = ur.urlopen

    # -- 1. a busy model is asked again, not abandoned --------------------
    rec = Recorder([busy(), busy(), reply("Markets closed at four, sir.")])
    ur.urlopen = rec
    b = make_brain(tmp)
    out = asyncio.run(b.respond("what did the market do", channel="text"))
    bad += not check("a 503 is retried on the same model rather than dropped",
                     len(rec.sent) == 3, f"{len(rec.sent)} requests")
    bad += not check("and the answer comes back",
                     out and "four" in out, repr(out))
    bad += not check("all three went to the FIRST model, not down the ladder",
                     {s["model"] for s in rec.sent} == {"a"},
                     str({s["model"] for s in rec.sent}))

    # -- 2. a genuine 400 still steps down immediately ---------------------
    bad_req = urllib.error.HTTPError("http://x", 400, "Bad Request", {}, None)
    rec = Recorder([bad_req, reply("Second model, sir.")])
    ur.urlopen = rec
    b = make_brain(tmp)
    out = asyncio.run(b.respond("hello", channel="text"))
    bad += not check("a 400 is not retried; it moves to the next model",
                     [s["model"] for s in rec.sent] == ["a", "b"],
                     str([s["model"] for s in rec.sent]))

    # -- 3. the gateway gets the same context the Anthropic path gets ------
    rec = Recorder([reply("Noted, sir.")])
    ur.urlopen = rec
    b = make_brain(tmp)
    asyncio.run(b.respond("what time is it", channel="text"))
    sent = rec.sent[0]["messages"]
    joined = " ".join(str(m.get("content") or "") for m in sent)
    bad += not check("the clock is in the prompt", "Local time:" in joined)
    bad += not check("the room is in the prompt", "the room is quiet" in joined)
    bad += not check("the channel is named", "Channel:" in joined)
    bad += not check("the user's words are still there",
                     "what time is it" in joined)

    # -- 4. and it remembers the turn before ------------------------------
    rec = Recorder([reply("It was AAPL, sir.")])
    ur.urlopen = rec
    b2 = make_brain(tmp)
    b2.history = [{"role": "user", "content": "look at AAPL"},
                  {"role": "assistant", "content": "Above both averages."}]
    asyncio.run(b2.respond("what was that symbol again", channel="text"))
    roles = [(m["role"], str(m.get("content"))[:24]) for m in rec.sent[0]["messages"]]
    bad += not check("the earlier turn is replayed to the gateway",
                     any("look at AAPL" in c for _, c in roles), str(roles))
    bad += not check("in order, before the new question",
                     [r for r, _ in roles][:2] == ["system", "user"], str(roles))

    # -- 5. everything out -> a sentence, not silence ----------------------
    rec = Recorder([busy(), busy(), busy(),
                    busy(), busy(), busy(),
                    busy(), busy(), busy()])
    ur.urlopen = rec
    b = make_brain(tmp)
    out = asyncio.run(b.respond("are you there", channel="text"))
    bad += not check("a fully exhausted ladder says so out loud",
                     bool(out) and "busy" in out.lower(), repr(out))
    bad += not check("and it still calls him sir",
                     bool(out) and "sir" in out.lower(), repr(out))

    # -- 6. an ambient wake with nothing to add stays silent ---------------
    rec = Recorder([busy()] * 9)
    ur.urlopen = rec
    b = make_brain(tmp)
    out = asyncio.run(b.respond(None, reason="the room went quiet"))
    bad += not check("an ambient wake with no model stays quiet", out is None,
                     repr(out))

    # -- 7. the token budget is the configured one, not a stub -------------
    rec = Recorder([reply("Fine, sir.")])
    ur.urlopen = rec
    b = make_brain(tmp)
    b.cfg.max_tokens = 4096
    asyncio.run(b.respond("hello", channel="text"))
    bad += not check("max_tokens comes from the config",
                     rec.sent[0]["max_tokens"] == 4096,
                     str(rec.sent[0].get("max_tokens")))

    # -- 8. an exhausted quota is not a busy queue ------------------------
    # Asking three more times inside five seconds cannot refill a daily
    # allowance. It should give up on that model at once, and the sentence
    # the user hears should say WHICH problem it was.
    rec = Recorder([QUOTA, QUOTA, QUOTA])
    ur.urlopen = rec
    b = make_brain(tmp)
    out = asyncio.run(b.respond("are you there", channel="text"))
    # All three, and NOT one. This assertion has now been wrong in both
    # directions, which is worth recording: first it expected three because
    # nobody had thought about it, then I "fixed" it to expect one on the
    # theory that a quota belongs to the key. On Google it belongs to the
    # MODEL, so asking the next one is exactly right.
    bad += not check("a spent quota still tries the other models",
                     len(rec.sent) == 3,
                     f"{len(rec.sent)} requests across a 3-model list")
    bad += not check("and the reply names the quota, not 'everything refused'",
                     bool(out) and "allowance" in out, repr(out))
    bad += not check("it still calls him sir", bool(out) and "sir" in out.lower())

    # -- 9. a retired model: follow the rename Google hands us -------------
    rec = Recorder([RETIRED, reply("Evening, sir.")])
    ur.urlopen = rec
    b = make_brain(tmp, models="gemini-2.5-flash")
    out = asyncio.run(b.respond("hello", channel="text"))
    bad += not check("a 404 that names a replacement is followed",
                     [s["model"] for s in rec.sent]
                     == ["gemini-2.5-flash", "gemini-3.6-flash"],
                     str([s["model"] for s in rec.sent]))
    bad += not check("and the answer comes back from the new name",
                     bool(out) and "Evening" in out, repr(out))

    # -- 10. a bad key says so rather than blaming the weather -------------
    rec = Recorder([BADKEY, BADKEY, BADKEY])
    ur.urlopen = rec
    b = make_brain(tmp)
    out = asyncio.run(b.respond("hello", channel="text"))
    bad += not check("a rejected key is reported as a key problem",
                     bool(out) and "key" in out.lower(), repr(out))

    # -- 11. a busy queue still reads as busy ------------------------------
    rec = Recorder([busy()] * 9)
    ur.urlopen = rec
    b = make_brain(tmp)
    out = asyncio.run(b.respond("hello", channel="text"))
    bad += not check("a genuine 503 still says busy",
                     bool(out) and "busy" in out.lower(), repr(out))

    # -- 12. the whole point: one provider dry, the other answers ---------
    # This is the fix for 20 August. Three Gemini names behind ONE key all
    # died in the same second; a second PROVIDER has its own key and its own
    # allowance, so it fails independently.
    import vesper.providers as prov

    keep_chain = prov.chain
    prov.chain = lambda cfg=None: [
        {"name": "google", "label": "Google AI Studio",
         "base": "http://google/v1", "token": "g", "models": ["gem-a", "gem-b"]},
        {"name": "github", "label": "GitHub Models",
         "base": "http://github/v1", "token": "h", "models": ["openai/gpt-4.1"]},
    ]
    try:
        rec = Recorder([QUOTA, QUOTA, reply("Good evening, sir.")])
        ur.urlopen = rec
        b = make_brain(tmp)
        out = asyncio.run(b.respond("what time is it", channel="text"))
        bad += not check("a spent Google quota hands the turn to GitHub",
                         bool(out) and "Good evening" in out, repr(out))
        bad += not check("it exhausts Google's models before moving on",
                         [s["model"] for s in rec.sent]
                         == ["gem-a", "gem-b", "openai/gpt-4.1"],
                         str([s["model"] for s in rec.sent]))
        bad += not check("and each request went to its own endpoint",
                         [r.full_url for r in rec.reqs]
                         == ["http://google/v1", "http://google/v1",
                             "http://github/v1"],
                         str([r.full_url for r in rec.reqs]))
        bad += not check("with its own key",
                         [r.headers.get("Authorization") for r in rec.reqs]
                         == ["Bearer g", "Bearer g", "Bearer h"],
                         str([r.headers.get("Authorization") for r in rec.reqs]))

        # Both dry: the sentence must name the ACTIONABLE reason, not
        # whichever provider happened to fail last.
        rec = Recorder([QUOTA, QUOTA, BADKEY])
        ur.urlopen = rec
        b = make_brain(tmp)
        out = asyncio.run(b.respond("hello", channel="text"))
        bad += not check("with both out, the key problem is what gets said",
                         bool(out) and "key" in out.lower(), repr(out))
    finally:
        prov.chain = keep_chain

    # -- 13. a 429 is per MODEL on Google, not per key --------------------
    # The owner's real ladder: three Pro rungs whose free tier was
    # withdrawn, then a Flash rung with 1,500 requests a day. Stopping the
    # provider on the first 429 never reached the one that works, so a
    # perfectly good key looked dead for an entire evening.
    theirs = ("gemini-3.1-pro-preview-customtools,gemini-3.1-pro-preview,"
              "gemini-2.5-pro,gemini-3.7-flash")
    rec = Recorder([QUOTA, QUOTA, QUOTA, reply("Good evening, sir.")])
    ur.urlopen = rec
    b = make_brain(tmp, models=theirs)
    out = asyncio.run(b.respond("what time is it", channel="text"))
    bad += not check("a 429 on one model still tries the next",
                     len(rec.sent) == 4, f"gave up after {len(rec.sent)}")
    bad += not check("and the working rung answers",
                     bool(out) and "Good evening" in out, repr(out))

    # A rejected KEY is different: nothing behind it can work.
    rec = Recorder([BADKEY, BADKEY, BADKEY, BADKEY])
    ur.urlopen = rec
    b = make_brain(tmp, models=theirs)
    asyncio.run(b.respond("hello", channel="text"))
    bad += not check("but a rejected key stops the provider at once",
                     len(rec.sent) == 1, f"{len(rec.sent)} requests")

    # -- 14. a refusal is remembered, so the next turn is fast ------------
    # Without this every question re-walks the same dead rungs. On the
    # owner's ladder that was three 429s and a timeout before reaching the
    # provider that works -- long enough that the phone bridge refused the
    # next question with "I'm in the middle of something".
    b = make_brain(tmp, models=theirs)
    rec = Recorder([QUOTA, QUOTA, QUOTA, reply("Evening, sir.")])
    ur.urlopen = rec
    asyncio.run(b.respond("first", channel="text"))
    rec2 = Recorder([reply("Evening again, sir.")])
    ur.urlopen = rec2
    out = asyncio.run(b.respond("second", channel="text"))
    bad += not check("the first turn learns which rungs are dead",
                     len(rec.sent) == 4, f"{len(rec.sent)}")
    bad += not check("and the second goes straight to the one that works",
                     [s["model"] for s in rec2.sent] == ["gemini-3.7-flash"],
                     str([s["model"] for s in rec2.sent]))
    bad += not check("still answering", bool(out) and "Evening" in out)

    # A rung that answers is proven good, so it must never be cooled down.
    b2 = make_brain(tmp, models="good,other")
    for _ in range(3):
        ur.urlopen = Recorder([reply("Fine, sir.")])
        asyncio.run(b2.respond("hello", channel="text"))
    bad += not check("a working rung is never cooled down",
                     not b2._cooldown, str(b2._cooldown))

    # -- 15. a model that cannot do tools still gets to answer ------------
    # The doctor's probe sends no tools and Groq answered; a real turn
    # sends all of them and came back "every model is busy". Most free
    # models cannot do function calling and say so with a 400 -- which
    # was being classified as busy, telling the user to wait for something
    # that would never change.
    NOTOOLS = http(400, "Bad Request", json.dumps({"error": {
        "message": "tool use is not supported for this model", "code": 400}}))
    rec = Recorder([NOTOOLS, reply("Evening, sir.")])
    ur.urlopen = rec
    b = make_brain(tmp, models="openai/gpt-oss-120b")
    b.tools = [{"name": "answer", "description": "say it",
                "input_schema": {"type": "object", "properties": {}}}]
    out = asyncio.run(b.respond("hello", channel="text"))
    bad += not check("a 400 with tools is retried without them",
                     len(rec.sent) == 2 and not rec.sent[1].get("tools"),
                     f"{len(rec.sent)} requests")
    bad += not check("on the SAME model, not the next one",
                     len({s["model"] for s in rec.sent}) == 1)
    bad += not check("and the answer comes back",
                     bool(out) and "Evening" in out, repr(out))

    # A 400 that survives losing the tools is reported as a rejection, not
    # as "busy" -- the user must not be told to wait for a request bug.
    rec = Recorder([NOTOOLS, NOTOOLS, NOTOOLS, NOTOOLS])
    ur.urlopen = rec
    b = make_brain(tmp, models="only-one")
    b.tools = [{"name": "answer", "description": "say it",
                "input_schema": {"type": "object", "properties": {}}}]
    out = asyncio.run(b.respond("hello", channel="text"))
    bad += not check("a persistent 400 does not read as 'busy'",
                     bool(out) and "busy" not in out.lower(), repr(out))

    # -- 16. steady state is ONE round trip -------------------------------
    # "It takes extremely long to reply." The owner's chain is Google
    # (three spent Pro rungs and a Flash rung that times out) then Groq.
    # Every turn re-walked all of it: four wasted round trips, one of them
    # costing the whole request timeout, before reaching the provider that
    # answers. Cooldowns skip the dead rungs; _last_good goes straight to
    # the live one, provider and model.
    keep_chain2 = prov.chain
    prov.chain = lambda cfg=None: [
        {"name": "google", "label": "Google AI Studio", "base": "http://g/v1",
         "token": "g", "models": ["pro-a", "pro-b", "pro-c", "flash"]},
        {"name": "groq", "label": "Groq", "base": "http://q/v1",
         "token": "q", "models": ["openai/gpt-oss-120b"]},
    ]
    try:
        b = make_brain(tmp)
        slow = TimeoutError("The read operation timed out")
        counts = []
        for turn in range(3):
            script = [QUOTA, QUOTA, QUOTA, slow] if turn == 0 else []
            rec = Recorder(script + [reply(f"Answer {turn}, sir.")])
            ur.urlopen = rec
            out = asyncio.run(b.respond(f"q{turn}", channel="text"))
            counts.append(len(rec.sent))
        bad += not check("the first turn pays to find out what works",
                         counts[0] == 5, str(counts))
        bad += not check("every turn after costs ONE round trip",
                         counts[1:] == [1, 1], str(counts))
        bad += not check("and it still answers",
                         bool(out) and "Answer" in out, repr(out))
        bad += not check("a timeout is not filed as 'busy'",
                         brain_mod._why_refused(slow) == "timeout",
                         brain_mod._why_refused(slow))
    finally:
        prov.chain = keep_chain2

    # -- 17. Groq's 413, verbatim from the owner's log --------------------
    # "Limit 8000, Requested 10021". We were asking for max_tokens=8000
    # and Groq counts that against a per-MINUTE budget of 8000, so the
    # request could never fit however short the question. Their message
    # contains the whole arithmetic, so read it rather than guess.
    TOOBIG = http(413, "Payload Too Large", json.dumps({"error": {"message":
        "Request too large for model `openai/gpt-oss-120b` in organization "
        "`org_x` service tier `on_demand` on tokens per minute (TPM): "
        "Limit 8000, Requested 10021, please reduce your message size and "
        "try again."}}))
    b = make_brain(tmp, models="openai/gpt-oss-120b")
    b.cfg.max_tokens = 8000
    rec = Recorder([TOOBIG, reply("Fifteen and cloudy, sir.")])
    ur.urlopen = rec
    out = asyncio.run(b.respond("what's the weather", channel="text"))
    bad += not check("a 413 is refitted from the provider's own numbers",
                     [s["max_tokens"] for s in rec.sent] == [8000, 5915],
                     str([s["max_tokens"] for s in rec.sent]))
    bad += not check("on the same model, and it answers",
                     bool(out) and "cloudy" in out, repr(out))

    rec2 = Recorder([reply("Still cloudy, sir.")])
    ur.urlopen = rec2
    asyncio.run(b.respond("and now", channel="text"))
    bad += not check("the fitting budget is remembered for next time",
                     [s["max_tokens"] for s in rec2.sent] == [5915],
                     str([s["max_tokens"] for s in rec2.sent]))

    # If even a refit will not fit, the tools are the bulk -- drop them.
    TIGHT = http(413, "Payload Too Large", json.dumps({"error": {"message":
        "tokens per minute (TPM): Limit 8000, Requested 12000, please "
        "reduce your message size."}}))
    b2 = make_brain(tmp, models="tight")
    b2.cfg.max_tokens = 1000
    b2.tools = [{"name": "answer", "description": "x" * 400,
                 "input_schema": {"type": "object", "properties": {}}}]
    rec3 = Recorder([TIGHT, reply("Managed it, sir.")])
    ur.urlopen = rec3
    out3 = asyncio.run(b2.respond("hello", channel="text"))
    bad += not check("an impossible refit drops the tools instead",
                     len(rec3.sent) == 2 and not rec3.sent[1].get("tools"),
                     f"{len(rec3.sent)} requests")
    bad += not check("and still answers", bool(out3) and "Managed" in out3,
                     repr(out3))

    ur.urlopen = keep
    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
