"""Memory and depth — the two things that decide whether she seems clever.

Memory is what separates an assistant from a chatbot: tell a chatbot on
Monday that you risk 1% per trade and by Friday it has never heard of you.
Depth is what stops every question getting the same treatment — a
committee for "what's the time" and a shrug for "should I restructure the
pricing" are the same failure twice.

These are behaviour tests. Storing a fact is not the point; the point is
that the fact comes BACK when it is relevant and stays out of the way when
it isn't.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.core import depth as D  # noqa: E402
from vesper.core.memory import Memory, notice, parse_extraction  # noqa: E402


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  {detail}" if detail else ""))
    return ok


def main() -> int:
    bad = 0
    tmp = Path(tempfile.mkdtemp())

    # -- 1. it keeps what matters and refuses what doesn't ----------------
    m = Memory(tmp / "mem.json")
    m.remember("They risk 1% of the account per trade", "semantic")
    m.remember("Their broker is Alpaca, paper account", "semantic")
    m.remember("They train on Tuesdays and Thursdays", "semantic")
    m.remember("Bought V at 362.85 on 17 July", "episodic")
    m.remember("Always address them as sir", "standing")
    bad += not check("five memories stored", len(m.items) == 5,
                     str(len(m.items)))
    bad += not check("noise is refused", m.remember("ok", "semantic") is None)
    bad += not check("a question is not a fact",
                     m.remember("what is my risk per trade?", "semantic") is None)

    # -- 2. the point: it comes back when relevant -------------------------
    hits = [h["text"] for h in m.recall("what risk do I take per trade")]
    bad += not check("asked about risk, the risk fact comes back",
                     any("1%" in h for h in hits), str(hits))
    bad += not check("and the standing instruction always does",
                     any("sir" in h for h in hits), str(hits))
    bad += not check("but the unrelated ones stay out of the way",
                     not any("Tuesdays" in h for h in hits), str(hits))

    hits2 = [h["text"] for h in m.recall("when do I train")]
    bad += not check("asked about training, training comes back",
                     any("Tuesdays" in h for h in hits2), str(hits2))

    # -- 3. saying the same thing again must not duplicate it -------------
    before = len(m.items)
    m.remember("They risk 1 percent of the account per trade", "semantic")
    bad += not check("a near-duplicate replaces rather than piles up",
                     len(m.items) == before, f"{before} -> {len(m.items)}")

    # -- 4. standing instructions survive a full store --------------------
    small = Memory(tmp / "small.json", limit=12)
    small.remember("Always address them as sir", "standing")
    for i in range(40):
        small.remember(f"An ordinary fact number {i} about something", "semantic")
    kinds = [i["kind"] for i in small.items]
    bad += not check("the store stays bounded", len(small.items) <= 12,
                     str(len(small.items)))
    bad += not check("and the standing instruction is never pruned",
                     "standing" in kinds, str(kinds[:4]))

    # -- 5. old facts fade behind fresh ones ------------------------------
    aged = Memory(tmp / "aged.json")
    aged.remember("The account risk setting is one percent", "semantic")
    aged.items[0]["at"] = time.time() - 400 * 86400        # over a year old
    aged.remember("The account risk setting is now two percent", "semantic")
    top = aged.recall("what is the account risk setting")[0]["text"]
    bad += not check("the newer of two competing facts ranks first",
                     "two percent" in top, top)

    # -- 6. noticing, without being told ----------------------------------
    cases = [
        ("always call me sir", "standing"),
        ("I risk 1 percent of my account per trade", "semantic"),
        ("yesterday I bought Visa at 362.85", "episodic"),
        ("what's the weather?", None),
        ("ok", None),
        ("thanks", None),
    ]
    for said, want in cases:
        got = notice(said)
        kind = got[0][0] if got else None
        bad += not check(f"notice: {said!r}", kind == want,
                         f"got {kind}, wanted {want}")

    # -- 7. the model-extraction format ------------------------------------
    parsed = parse_extraction(
        "FACT: they risk 1% per trade\n"
        "EVENT: bought V on 17 July\n"
        "STANDING: never quote a price without the trend\n"
        "some malformed line\n")
    bad += not check("extraction reads all three kinds",
                     [k for k, _ in parsed]
                     == ["semantic", "episodic", "standing"], str(parsed))
    bad += not check("and NOTHING means nothing",
                     parse_extraction("NOTHING") == [])

    # -- 8. depth routing ---------------------------------------------------
    routes = [
        ("what time is it", D.REFLEX),
        ("are you there", D.REFLEX),
        ("what do you remember about me", D.REFLEX),
        ("what's the capital of France", D.QUICK),
        ("remind me to call mum at six", D.QUICK),
        ("should I take the Visa trade", D.DEEP),
        ("why didn't the autopilot enter AAPL", D.DEEP),
        ("what is my risk per trade", D.DEEP),
        ("I have pain in my legs after training", D.DEEP),
        ("explain the difference between a stop and a bracket", D.DEEP),
    ]
    for said, want in routes:
        got = D.classify(said)
        bad += not check(f"depth: {said!r}", got == want,
                         f"got {got}, wanted {want}")

    # -- 9. a reflex costs no model call at all ---------------------------
    sys.argv = ["x"]
    import selftest_gateway as G
    import urllib.request as ur

    keep = ur.urlopen
    rec = G.Recorder([G.reply("should not be needed")])
    ur.urlopen = rec
    b = G.make_brain(tmp)
    b.memory = Memory(tmp / "brainmem.json")
    out = asyncio.run(b.respond("what time is it", channel="text"))
    ur.urlopen = keep
    bad += not check("a reflex makes NO request", len(rec.sent) == 0,
                     f"{len(rec.sent)} requests")
    bad += not check("and still answers, with the address",
                     bool(out) and "sir" in out.lower(), repr(out))

    # -- 10. what she is told, she keeps and then uses ---------------------
    rec = G.Recorder([G.reply("Noted, sir."), G.reply("One percent, sir.")])
    ur.urlopen = rec
    b2 = G.make_brain(tmp)
    b2.memory = Memory(tmp / "learn.json")
    asyncio.run(b2.respond("I risk 1 percent of my account per trade",
                           channel="text"))
    bad += not check("it learned from an ordinary sentence",
                     any("1 percent" in i["text"] for i in b2.memory.items),
                     str([i["text"] for i in b2.memory.items]))
    asyncio.run(b2.respond("what do I risk per trade", channel="text"))
    ur.urlopen = keep
    prompt = " ".join(str(m.get("content") or "")
                      for m in rec.sent[-1]["messages"])
    bad += not check("and put it in front of the model next time",
                     "1 percent" in prompt, prompt[-200:])

    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
