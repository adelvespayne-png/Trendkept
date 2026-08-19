"""The fallback gateway, against a stand-in OmniRoute on localhost."""
import asyncio, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from vesper.config import Config
from vesper.core.brain import Brain
from vesper.core.world_state import WorldState
from vesper.tools.tool_executor import ToolExecutor

PORT = 20129
SEEN = []

class Fake(BaseHTTPRequestHandler):
    """Mimics OmniRoute: OpenAI-compatible, 429s the first alias, and on the
    second uses tools — add to the map, then answer."""
    def log_message(self, *a): pass
    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-OmniRoute-Decision", "lkgp/groq/llama-3.3-70b 412ms")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n))
        SEEN.append({"model": req["model"],
                     "auth": self.headers.get("Authorization"),
                     "roles": [m["role"] for m in req["messages"]],
                     "tools": [t["function"]["name"] for t in req.get("tools", [])]})
        if req["model"] == "auto/smart":          # quota exhausted
            self.send_response(429); self.end_headers(); return
        done = [m for m in req["messages"] if m["role"] == "tool"]
        if not done:
            return self._json({"choices": [{"message": {"role": "assistant",
                "content": None, "tool_calls": [
                  {"id": "c1", "type": "function", "function": {
                     "name": "map_add",
                     "arguments": json.dumps({"text": "Buy the domain",
                                              "parent": "Personal"})}}]}}]})
        return self._json({"choices": [{"message": {"role": "assistant",
            "content": None, "tool_calls": [
              {"id": "c2", "type": "function", "function": {
                 "name": "answer",
                 "arguments": json.dumps({"text": "Added it under Personal."})}}]}}]})

class Err(Exception):
    def __init__(s, m, c): super().__init__(m); s.status_code = c
class Client:
    messages = None
    async def create(s, **kw): raise Err("rate limit", 429)
Client.messages = Client()

async def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    cfg = Config()
    cfg.anthropic_api_key = "t"
    cfg.fallback_base = f"http://127.0.0.1:{PORT}/v1/chat/completions"
    cfg.fallback_token = "omni-key"
    # Pinned here rather than inherited from the shipped default, so changing
    # the defaults doesn't silently rewrite what this test is checking.
    cfg.fallback_models = "auto/smart,auto"
    import tempfile
    from pathlib import Path
    from vesper.mapstore import MapStore
    cfg.map_path = Path(tempfile.mkdtemp()) / "map.json"
    st = WorldState()
    store = MapStore(cfg.map_path)
    b = Brain(st, ToolExecutor(st, cfg, mapstore=store), cfg, client=Client())

    reply = await b.respond(user_text="what's the weather in Bristol?")
    print("1. every Claude model gone -> gateway took the turn")
    # A tool-using turn is several round trips on the same model, so compare
    # the sequence of models, not the number of calls.
    seq = [k for i, k in enumerate([s["model"] for s in SEEN])
           if i == 0 or k != [s["model"] for s in SEEN][i - 1]]
    print("2. models tried in order:", seq,
          f"({len(SEEN)} round trips)")
    assert seq == ["auto/smart", "auto"], SEEN
    print("3. 429 on the first alias moved to the next: True")
    print("4. bearer token sent:", SEEN[-1]["auth"])
    print("5. system prompt carried over:", SEEN[-1]["roles"])
    print("6. tools offered to the gateway:", SEEN[-1]["tools"])
    assert "map_add" in SEEN[-1]["tools"] and "answer" in SEEN[-1]["tools"]
    assert "web_search" not in SEEN[-1]["tools"], "server-side tool leaked across"
    kids = [n["t"] for n in store.data["nodes"].values()
            if n.get("p") and store.node(n["p"])["t"] == "Personal"]
    print("7. it actually touched the map:", kids)
    assert "Buy the domain" in kids, "the tool call did not reach the map"
    print("8. and spoke through the answer tool:", reply)
    assert reply == "Added it under Personal, sir.", reply

    # gateway down entirely -> quiet failure, not a crash
    cfg2 = Config(); cfg2.anthropic_api_key = "t"
    cfg2.fallback_base = "http://127.0.0.1:1/v1/chat/completions"
    b2 = Brain(WorldState(), ToolExecutor(WorldState(), cfg2), cfg2, client=Client())
    print("9. gateway unreachable ->", await b2.respond(user_text="hi"))

    # switched off
    cfg3 = Config(); cfg3.anthropic_api_key = "t"; cfg3.fallback_enabled = False
    b3 = Brain(WorldState(), ToolExecutor(WorldState(), cfg3), cfg3, client=Client())
    print("10. FALLBACK_ENABLED=false ->", await b3.respond(user_text="hi"))

    httpd.shutdown()
    print("\nAll gateway checks passed.")

asyncio.run(main())
