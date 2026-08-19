"""Phone-bridge test: a real HTTP server, real requests, stubbed model.

Note the `asyncio.to_thread` around every request. The bridge hands work to
the event loop and waits for it, so calling it *from* the loop thread would
deadlock — the loop can't service the coroutine while it's blocked on the
HTTP response. Your phone is a separate machine, so this never arises in
real use, but the test has to imitate that.
"""
import asyncio
import json
import urllib.error
import urllib.request

from vesper.config import Config
from vesper.main import Vesper
from vesper.server import AskServer

TOKEN = "test-token-that-is-long-enough-32chars"
PORT = 8799


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Resp:
    def __init__(self, content, stop_reason="tool_use"):
        self.content, self.stop_reason = content, stop_reason


class StubClient:
    class messages:
        @staticmethod
        async def create(**kw):
            return Resp([Block(type="tool_use", id="t", name="answer",
                               input={"text": "The stove is off and nobody is in."})])


def _call(path, payload=None, token=TOKEN):
    url = f"http://127.0.0.1:{PORT}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


async def call(path, payload=None, token=TOKEN):
    return await asyncio.to_thread(_call, path, payload, token)


async def main():
    cfg = Config()
    cfg.anthropic_api_key = "test"
    cfg.models = "claude-opus-5"   # pinned: this suite stubs the Claude client
    cfg.server_enabled = True
    cfg.server_token = TOKEN
    cfg.server_port = PORT
    cfg.server_host = "127.0.0.1"
    cfg.state_path = cfg.state_path.parent / "bridgetest_state.json"
    cfg.log_path = cfg.log_path.parent / "bridgetest_log.jsonl"

    j = Vesper(cfg)
    j.brain._client = StubClient()
    j.brain.available = True
    spoken = []
    j.speaker.say = lambda t: spoken.append(t)

    task = asyncio.ensure_future(j.run())
    await asyncio.sleep(0.4)

    checks = [
        ("health", await call("/health"), 200),
        ("ask", await call("/ask", {"text": "is the stove on?"}), 200),
        ("no token", await call("/health", token=None), 401),
        ("wrong token", await call("/health", token="nope"), 401),
        ("bad route", await call("/nope"), 404),
        ("empty text", await call("/ask", {"text": "   "}), 400),
        ("not json", await call("/ask", "raw"), 400),
    ]
    for n, (name, (status, body), want) in enumerate(checks, 1):
        assert status == want, f"{name}: got {status}, wanted {want} — {body}"
        print(f"{n}. {name:<14} {status}  {json.dumps(body)[:70]}")

    assert checks[1][1][1]["reply"], "no reply text came back"
    assert not spoken, f"laptop spoke aloud when it shouldn't have: {spoken}"
    print("\n8. silent by default -> laptop did not speak the phone's answer")

    # ...but it does when you ask it to
    j.bridge.cfg.server_speak_aloud = True
    await call("/ask", {"text": "hello"})
    await asyncio.sleep(0.3)
    assert spoken, "SERVER_SPEAK_ALOUD had no effect"
    print("9. SPEAK_ALOUD=true  -> laptop said:", spoken[-1])

    # a short or blank token must refuse to open at all
    weak = Config()
    weak.server_enabled = True
    weak.server_token = "short"
    weak.server_port = PORT + 1
    assert not AskServer(j, asyncio.get_running_loop(), weak).start()
    print("10. weak token       -> bridge refused to start")

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print("\nAll bridge checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
