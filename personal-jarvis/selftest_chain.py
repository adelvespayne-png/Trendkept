"""The interleaved ladder: fable -> opus -> omniroute -> sonnet -> haiku."""
import asyncio, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from jarvis.config import Config
from jarvis.core.brain import Brain
from jarvis.core.world_state import WorldState
from jarvis.tools.tool_executor import ToolExecutor

PORT = 20977
GATE = {"up": True, "hits": 0}

class B:
    def __init__(s, **k): s.__dict__.update(k)
class R:
    def __init__(s, c, sr="tool_use"): s.content, s.stop_reason = c, sr
class Err(Exception):
    def __init__(s, m, c): super().__init__(m); s.status_code = c

ANSWER = R([B(type="tool_use", id="1", name="answer", input={"text": "Done."})])

class Fake(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_POST(self):
        GATE["hits"] += 1
        self.rfile.read(int(self.headers.get("Content-Length",0)))
        if not GATE["up"]:
            self.send_response(503); self.end_headers(); return
        body = json.dumps({"choices":[{"message":{"role":"assistant",
            "content":None,"tool_calls":[{"id":"c","type":"function","function":{
              "name":"answer","arguments":json.dumps({"text":"Gateway here."})}}]}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body))); self.end_headers()
        self.wfile.write(body)

class Client:
    def __init__(s, dead): s.dead, s.tried = set(dead), []; s.messages = s
    async def create(s, **kw):
        m = kw["model"]; s.tried.append(m)
        if m in s.dead: raise Err("rate limit", 429)
        return ANSWER

def brain(dead, gateway_up=True):
    GATE["up"] = gateway_up; GATE["hits"] = 0
    cfg = Config(); cfg.anthropic_api_key="t"
    cfg.models = ("claude-fable-5,claude-opus-5,omniroute,"
                  "claude-sonnet-5,claude-haiku-4-5")   # pinned, not inherited
    cfg.fallback_base=f"http://127.0.0.1:{PORT}/v1/chat/completions"
    cfg.fallback_models="auto/best-reasoning"
    st = WorldState()
    return Brain(st, ToolExecutor(st, cfg), cfg, client=Client(dead))

async def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    b = brain([])
    print("1. ladder:", b.ladder)
    assert b.ladder == ["claude-fable-5","claude-opus-5","omniroute",
                        "claude-sonnet-5","claude-haiku-4-5"], b.ladder

    print("2. all healthy ->", await b.respond(user_text="hi"),
          "| tried:", b._client.tried, "| gateway hits:", GATE["hits"])
    assert b._client.tried == ["claude-fable-5"] and GATE["hits"] == 0

    b = brain(["claude-fable-5"])
    print("3. fable down ->", await b.respond(user_text="hi"), "| tried:", b._client.tried)
    assert b._client.tried == ["claude-fable-5","claude-opus-5"]

    b = brain(["claude-fable-5","claude-opus-5"])
    r = await b.respond(user_text="hi")
    print("4. fable+opus down -> gateway answers:", r, "| gateway hits:", GATE["hits"])
    assert r == "Gateway here." and GATE["hits"] == 1
    assert "claude-sonnet-5" not in b._client.tried, "skipped past the gateway"

    b = brain(["claude-fable-5","claude-opus-5"], gateway_up=False)
    r = await b.respond(user_text="hi")
    print("5. gateway also down -> falls through to sonnet:", r,
          "| tried:", b._client.tried)
    assert r == "Done." and b._client.tried[-1] == "claude-sonnet-5"

    b = brain(["claude-fable-5","claude-opus-5","claude-sonnet-5"], gateway_up=False)
    r = await b.respond(user_text="hi")
    print("6. only haiku left ->", r, "| tried:", b._client.tried)
    assert b._client.tried[-1] == "claude-haiku-4-5"

    b = brain(["claude-fable-5","claude-opus-5","claude-sonnet-5","claude-haiku-4-5"],
              gateway_up=False)
    print("7. everything down ->", await b.respond(user_text="hi"))

    httpd.shutdown()
    print("\nAll chain checks passed.")

asyncio.run(main())
