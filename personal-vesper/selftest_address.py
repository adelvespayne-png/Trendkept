"""She says "sir". Every reply, every path, exactly once.

The system prompt asks for it, which works nearly always — and "nearly
always" is the thing that gets noticed. So the prompt sets the habit and
`address.py` makes it a promise.

What this guards is mostly the *awkward* cases, because getting it added is
easy and getting it added gracefully is not: questions, quotes, bullet
lists, code, replies that already say it, and one-word answers.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.address import ensure, has_address              # noqa: E402
from vesper.core.redflag import ADVICE                      # noqa: E402

bad = 0


def check(got, want, label="") -> None:
    global bad
    ok = got == want
    if not ok:
        bad += 1
    print(f"  [{'ok' if ok else 'FAIL'}] {label or want}")
    if not ok:
        print(f"         got  {got!r}\n         want {want!r}")


print("\n1. ordinary sentences")
check(ensure("The trend filter is no longer met."),
      "The trend filter is no longer met, sir.")
check(ensure("Yes."), "Yes, sir.")
check(ensure("Done."), "Done, sir.")

print("\n2. a question keeps its question mark")
check(ensure("Would you like me to check?"),
      "Would you like me to check, sir?")
check(ensure("Shall I log it? It only takes a moment."),
      "Shall I log it, sir? It only takes a moment.")

print("\n3. only the FIRST sentence, and only once")
check(ensure("Two things. The stop is at 41.20. The trend still holds."),
      "Two things, sir. The stop is at 41.20. The trend still holds.")
one = ensure("It is raining. It will stop later.")
check(one.count("sir"), 1, "exactly one 'sir' in a multi-sentence reply")

print("\n4. a decimal is not a sentence end")
check(ensure("Your stop is 41.20 and the entry was 43.10."),
      "Your stop is 41.20 and the entry was 43.10, sir.")

print("\n5. already addressed -> untouched (idempotent)")
for said in ("Yes, sir.",
             "Sir, the trend filter is no longer met.",
             "No, sir — the position is still open."):
    check(ensure(said), said, f"unchanged: {said!r}")
check(ensure(ensure("Understood.")), "Understood, sir.",
      "running it twice adds nothing")

print("\n6. no trailing punctuation")
check(ensure("Trend filter no longer met"), "Trend filter no longer met, sir")
check(ensure("Right,"), "Right, sir")

print("\n7. quotes and brackets keep their closer")
check(ensure('She said "no"'), 'She said "no", sir')
check(ensure("The stop is where it was (41.20)"),
      "The stop is where it was (41.20), sir")

print("\n8. lists and headings — the address goes on prose, not markup")
check(ensure("Three open positions:\n- AAPL\n- MSFT"),
      "Three open positions, sir:\n- AAPL\n- MSFT")
check(ensure("- AAPL\n- MSFT\nThat is all of them."),
      "- AAPL\n- MSFT\nThat is all of them, sir.")

print("\n9. nothing but markup -> announced above, never wedged inside")
check(ensure("```\npython -m vesper.main\n```"),
      "Sir:\n```\npython -m vesper.main\n```")
check(ensure("- one\n- two"), "Sir:\n- one\n- two")

print("\n10. empty and off")
check(ensure(""), "", "empty stays empty")
check(ensure(None), None, "None stays None")
check(ensure("Yes.", ""), "Yes.", "blank ADDRESS switches it off")

print("\n11. a different term works, for anyone who is not a 'sir'")
check(ensure("Understood.", "ma'am"), "Understood, ma'am.")
check(ensure("Understood.", "boss"), "Understood, boss.")
check(has_address("Yes, ma'am.", "ma'am"), True, "detects its own term")
check(has_address("Yes, ma'am.", "sir"), False, "not fooled by another term")

print("\n12. not fooled by 'sir' inside another word")
check(has_address("The siren went off.", "sir"), False, "'siren' is not 'sir'")
check(ensure("The siren went off."), "The siren went off, sir.")

print("\n13. the fixed safety text still reads right")
for level, text in sorted(ADVICE.items()):
    out = ensure(text)
    ok = out.count("sir") == 1 and out != text
    if not ok:
        bad += 1
    print(f"  [{'ok' if ok else 'FAIL'}] {level}")
    print(f"         {out.split(chr(10))[0][:96]}")

print("\n14. end to end, with a model that never says it")
# The point of the enforcement is that it does not depend on the model
# complying. So the scripted model here is deliberately impolite.
import asyncio                                              # noqa: E402

from vesper.config import Config                            # noqa: E402
from vesper.core.brain import Brain                         # noqa: E402
from vesper.core.world_state import WorldState              # noqa: E402
from vesper.tools.tool_executor import ToolExecutor         # noqa: E402


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Resp:
    def __init__(self, content, stop_reason="tool_use"):
        self.content, self.stop_reason = content, stop_reason


class Script:
    def __init__(self, responses):
        self.responses, self.seen = list(responses), []
        self.messages = self

    async def create(self, **kw):
        self.seen.append({**kw, "messages": list(kw["messages"])})
        return self.responses.pop(0)


def brain_with(responses, cfg=None):
    cfg = cfg or Config()
    cfg.anthropic_api_key = "test"
    cfg.models = "claude-opus-5"          # pinned, not inherited
    state = WorldState()
    return Brain(state, ToolExecutor(state, cfg), cfg, client=Script(responses))


async def run() -> None:
    global bad

    b = brain_with([Resp([Block(type="tool_use", id="t1", name="answer",
                               input={"text": "Ten-year gilts are around "
                                              "four percent."})])])
    reply = await b.respond(user_text="what are gilt yields doing?")
    check(reply, "Ten-year gilts are around four percent, sir.",
          "a rude model still comes out polite")

    # The system prompt must ask for it too — enforcement is the safety net,
    # not the mechanism. If only the net were there, every reply would get it
    # bolted on the end rather than written in.
    sysmsg = b._client.seen[0]["system"]
    check('"sir"' in sysmsg, True, "the system prompt asks for it")

    # The danger path returns before the model is ever called, so it needs
    # its own guarantee — and it is the reply that matters most.
    cfg = Config()
    cfg.anthropic_api_key = ""            # no private model available
    cfg.health_models = ""
    state = WorldState()
    b2 = Brain(state, ToolExecutor(state, cfg), cfg, client=Script([]))
    b2.available = True
    reply = await b2.respond(user_text="my chest is really tight and the pain "
                                       "is spreading to my arm")
    ok = reply is not None and reply.count("sir") == 1 and "999" in reply
    if not ok:
        bad += 1
    print(f"  [{'ok' if ok else 'FAIL'}] the refusal path keeps both the "
          "instruction and the address")
    print(f"         {reply}")


asyncio.run(run())

print("\nFAIL" if bad else "\nPASS")
sys.exit(1 if bad else 0)
