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

    def __call__(self, req, timeout=None):
        self.sent.append(json.loads(req.data.decode()))
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
    bad += not check("a spent quota is not retried on the same model",
                     len(rec.sent) == 3, f"{len(rec.sent)} requests for 3 models")
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

    ur.urlopen = keep
    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
