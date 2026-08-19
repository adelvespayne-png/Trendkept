"""End-to-end wiring test with a stubbed model. No hardware, no API key.

Proves the two paths that actually matter:
  1. a user turn goes brain -> tool -> speaker
  2. an ambient state change goes trigger -> queue -> brain -> speaker
     (and that silence is a real outcome, not a crash)
"""
import asyncio
import threading
import types

from vesper.config import Config
from vesper.main import Vesper

SPOKEN = []


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Resp:
    def __init__(self, content, stop_reason="tool_use"):
        self.content = content
        self.stop_reason = stop_reason


class StubMessages:
    """Answers the direct question; stays silent on the ambient wake."""

    def __init__(self):
        self.seen = []

    async def create(self, **kw):
        self.seen.append(kw)
        opening = kw["messages"][-1]["content"]
        ambient = isinstance(opening, str) and "ambient event" in opening
        if ambient:
            return Resp([Block(type="tool_use", id="t1", name="stay_silent",
                               input={"reason": "the user can see the door"})])
        return Resp([Block(type="tool_use", id="t2", name="answer",
                           input={"text": "It is raining in Bristol."})])


class StubClient:
    def __init__(self):
        self.messages = StubMessages()


async def main():
    cfg = Config()
    cfg.anthropic_api_key = "test"
    cfg.proactive_cooldown = 0.0
    cfg.models = "claude-opus-5"          # pinned, not inherited
    cfg.state_path = cfg.state_path.parent / "selftest_state.json"
    cfg.log_path = cfg.log_path.parent / "selftest_log.jsonl"

    j = Vesper(cfg)
    j.brain._client = StubClient()
    j.brain.available = True
    j.speaker.say = lambda text: SPOKEN.append(text)

    task = asyncio.ensure_future(j.run())
    await asyncio.sleep(0.2)

    # 1. a direct question
    await j.ask("what's the weather in Bristol?")
    assert SPOKEN == ["It is raining in Bristol."], SPOKEN
    print("1. user turn      ->", SPOKEN[-1])

    # 2. an ambient change, raised from a sensor thread like the real ones
    def sensor():
        j.state.update(time_of_day="night")
        j.state.update(people=["unknown"])
    threading.Thread(target=sensor).start()
    await asyncio.sleep(0.5)

    assert len(SPOKEN) == 1, f"vesper spoke when it should have stayed quiet: {SPOKEN}"
    print("2. ambient turn   -> silence, reason:", j.executor.silent_reason)

    # 3. the trigger really did fire (silence was a decision, not a no-op)
    calls = j.brain._client.messages.seen
    # The opening block is the last *string* message: by now `history` has
    # earlier turns in front of it and tool results after it.
    texts = [m["content"] for c in calls for m in c["messages"]
             if isinstance(m["content"], str)]
    assert any("ambient event" in t for t in texts), \
        "the trigger never woke the brain"
    print("3. trigger fired  -> brain woken with a reason")

    # 4. the API shape is still current
    last = calls[-1]
    assert last["model"] == "claude-opus-5"
    assert last["thinking"] == {"type": "adaptive"}
    assert last["output_config"] == {"effort": cfg.effort}
    assert not ({"temperature", "top_p", "top_k"} & set(last)), "sampling params leaked"
    print("4. request shape  -> opus-5, adaptive thinking, "
          f"effort={cfg.effort}, no sampling params")

    # 5. a burst of triggers while a turn is in flight must not pile up.
    # Stop the consumer first, so the queue is genuinely unattended — with it
    # running, it drains events as fast as they arrive and proves nothing.
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    for _ in range(5):
        j._post("ambient", "test")
    await asyncio.sleep(0.1)
    assert j._events.qsize() == 1, j._events.qsize()
    print("5. event queue    -> 5 events while busy collapsed to",
          j._events.qsize(), "queued turn")
    print("\nAll orchestrator checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
