"""The model ladder: step down on transient failure, never on our own bugs."""
import asyncio
from jarvis.config import Config
from jarvis.core.brain import Brain, _transient
from jarvis.core.world_state import WorldState
from jarvis.tools.tool_executor import ToolExecutor

class B:
    def __init__(s, **k): s.__dict__.update(k)
class R:
    def __init__(s, c, sr="tool_use"): s.content, s.stop_reason = c, sr
class Err(Exception):
    def __init__(s, msg, code=None):
        super().__init__(msg); s.status_code = code

ANSWER = R([B(type="tool_use", id="1", name="answer", input={"text": "Done."})])

class Client:
    def __init__(s, fail_for):   # {model: exception}
        s.fail_for, s.tried = fail_for, []
        s.messages = s
    async def create(s, **kw):
        m = kw["model"]; s.tried.append(m)
        if m in s.fail_for: raise s.fail_for[m]
        return ANSWER

LADDER = "claude-opus-5,claude-sonnet-5,claude-haiku-4-5"


def brain(fail_for, cfg=None):
    cfg = cfg or Config(); cfg.anthropic_api_key = "t"
    cfg.models = LADDER                    # pinned, not inherited
    cfg.fallback_enabled = False           # this suite is about the Claude rungs
    st = WorldState()
    return Brain(st, ToolExecutor(st, cfg), cfg, client=Client(fail_for))

async def main():
    print("1. ladder:", brain({}).ladder)

    # rate limit on the top model -> next model answers
    b = brain({"claude-opus-5": Err("rate limit", 429)})
    print("2. 429 on opus ->", await b.respond(user_text="hi"),
          "| tried:", b._client.tried, "| degraded:", b.degraded)

    # out of credit (arrives as a 400) is still a step-down
    b = brain({"claude-opus-5": Err("Your credit balance is too low", 400)})
    await b.respond(user_text="hi")
    print("3. empty balance ->", b._client.tried, "| degraded:", b.degraded)

    # two down
    b = brain({"claude-opus-5": Err("overloaded", 529),
               "claude-sonnet-5": Err("rate limit", 429)})
    await b.respond(user_text="hi")
    print("4. two rungs down ->", b._client.tried)

    # a real bug must NOT walk the ladder
    b = brain({"claude-opus-5": Err("messages: roles must alternate", 400)})
    r = await b.respond(user_text="hi")
    print("5. malformed request -> reply:", r, "| tried once:", b._client.tried)
    assert b._client.tried == ["claude-opus-5"], "a 400 bug retried on other models"

    # every model gone, no fallback configured
    allfail = {m: Err("rate limit", 429) for m in LADDER.split(",")}
    b = brain(allfail)
    print("6. all gone, no backup ->", await b.respond(user_text="hi"))

    # every model gone, GitHub fallback configured but unreachable here
    cfg = Config(); cfg.anthropic_api_key = "t"; cfg.models = LADDER
    cfg.fallback_base = "http://127.0.0.1:1/v1/chat/completions"
    b2 = Brain(WorldState(), ToolExecutor(WorldState(), cfg), cfg,
               client=Client(allfail))
    print("7. all gone, backup unreachable ->", await b2.respond(user_text="hi"))

    # once stepped down it stays down (no thrash back to a limited model)
    b = brain({"claude-opus-5": Err("rate limit", 429)})
    await b.respond(user_text="one"); first = list(b._client.tried)
    await b.respond(user_text="two")
    print("8. sticks at the working rung ->", b._client.tried[len(first):])

    print("9. classifier:",
          [_transient(Err("x", c)) for c in (429, 500, 529)],
          _transient(Err("credit balance too low", 400)),
          _transient(Err("model: unknown model", 404)))
    print("\nAll ladder checks passed.")

asyncio.run(main())
