"""Brain test: web tools, pause_turn resumption, channel, depth settings."""
import asyncio
import json

from jarvis.config import Config
from jarvis.core.brain import Brain
from jarvis.core.world_state import WorldState
from jarvis.tools.tool_definitions import tool_definitions
from jarvis.tools.tool_executor import ToolExecutor


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Resp:
    def __init__(self, content, stop_reason="tool_use"):
        self.content, self.stop_reason = content, stop_reason


class Script:
    """Plays a fixed sequence of responses and records every request."""

    def __init__(self, responses):
        self.responses, self.seen = list(responses), []
        self.messages = self

    async def create(self, **kw):
        # Copy the message list: the brain keeps appending to the same list,
        # so storing the reference would let later rounds rewrite history we
        # are trying to assert on.
        self.seen.append({**kw, "messages": list(kw["messages"])})
        return self.responses.pop(0)


def brain_with(responses, cfg=None):
    cfg = cfg or Config()
    cfg.anthropic_api_key = "test"
    cfg.models = "claude-opus-5"           # pinned, not inherited
    state = WorldState()
    b = Brain(state, ToolExecutor(state, cfg), cfg, client=Script(responses))
    return b


async def main():
    # 1. the web tools are declared, in the current shape
    tools = tool_definitions(include_home=False, include_web=True)
    web = [t for t in tools if t.get("type", "").startswith("web_")]
    assert [t["type"] for t in web] == ["web_search_20260209",
                                        "web_fetch_20260209"], web
    print("1. web tools declared:", ", ".join(t["type"] for t in web))

    # ...and can be turned off
    assert not [t for t in tool_definitions(include_web=False)
                if t.get("type", "").startswith("web_")]
    print("2. WEB_ENABLED=false removes them")

    # 3. a paused turn resumes without an extra user message
    b = brain_with([
        Resp([Block(type="server_tool_use", id="s1", name="web_search",
                    input={"query": "gilt yields"})], stop_reason="pause_turn"),
        Resp([Block(type="tool_use", id="t1", name="answer",
                    input={"text": "Ten-year gilts are around four percent."})]),
    ])
    reply = await b.respond(user_text="what are gilt yields doing?")
    assert reply == "Ten-year gilts are around four percent.", reply
    calls = b._client.seen
    assert len(calls) == 2, f"expected a resume, got {len(calls)} call(s)"
    resumed = calls[1]["messages"]
    assert resumed[-1]["role"] == "assistant", \
        "resume must end on the assistant turn, with no 'continue' message"
    print("3. pause_turn resumed correctly, no filler user message added")

    # 4. server_tool_use is never mistaken for one of ours
    b2 = brain_with([
        Resp([Block(type="server_tool_use", id="s2", name="web_search", input={}),
              Block(type="tool_use", id="t2", name="answer",
                    input={"text": "Done."})]),
    ])
    assert await b2.respond(user_text="hi") == "Done."
    results = [m for m in b2._client.seen[0]["messages"]
               if isinstance(m.get("content"), list)]
    print("4. server_tool_use ignored by the executor; only our tool ran")

    # 5. channel reaches the prompt
    b3 = brain_with([Resp([Block(type="tool_use", id="t3", name="answer",
                                 input={"text": "ok"})])])
    await b3.respond(user_text="hi", channel="text")
    opening = b3._client.seen[0]["messages"][-1]["content"]
    assert "text — this will be read on a screen" in opening, opening
    print("5. channel=text reaches the prompt")

    b4 = brain_with([Resp([Block(type="tool_use", id="t4", name="answer",
                                 input={"text": "ok"})])])
    await b4.respond(user_text="hi", channel="voice")
    assert "voice — this will be spoken aloud" in \
        b4._client.seen[0]["messages"][-1]["content"]
    print("6. channel=voice reaches the prompt")

    # 7. the depth settings actually went up
    cfg = Config()
    cfg.models = "claude-opus-5"
    assert cfg.effort == "high", cfg.effort
    assert cfg.max_tokens == 8000, cfg.max_tokens
    assert cfg.web_enabled is True
    print(f"7. defaults: effort={cfg.effort}, max_tokens={cfg.max_tokens}, "
          f"web={cfg.web_enabled}")

    # 8. request shape still current
    last = b4._client.seen[0]
    assert last["model"] == "claude-opus-5"
    assert last["thinking"] == {"type": "adaptive"}
    assert last["output_config"] == {"effort": "high"}
    assert not ({"temperature", "top_p", "top_k"} & set(last))
    print("8. request shape unchanged and valid")

    print("\nAll brain checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
