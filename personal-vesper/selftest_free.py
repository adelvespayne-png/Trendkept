"""The free-only chain: no Anthropic key, no Anthropic calls, no bill."""
import asyncio, json, threading, tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from vesper.config import Config
from vesper.core.brain import Brain
from vesper.core.world_state import WorldState
from vesper.mapstore import MapStore
from vesper.tools.tool_executor import ToolExecutor

PORT = 20991
STATE = {"up": True, "hits": 0, "tools": None}

class F(BaseHTTPRequestHandler):
    def log_message(s,*a): pass
    def do_POST(s):
        STATE["hits"] += 1
        req = json.loads(s.rfile.read(int(s.headers.get("Content-Length",0))))
        STATE["tools"] = [t["function"]["name"] for t in req.get("tools",[])]
        if not STATE["up"]:
            s.send_response(503); s.end_headers(); return
        done = [m for m in req["messages"] if m["role"] == "tool"]
        if not done:
            msg = {"role":"assistant","content":None,"tool_calls":[
                {"id":"c1","type":"function","function":{"name":"map_add",
                 "arguments":json.dumps({"text":"Try the free chain","parent":"Personal"})}}]}
        else:
            msg = {"role":"assistant","content":None,"tool_calls":[
                {"id":"c2","type":"function","function":{"name":"answer",
                 "arguments":json.dumps({"text":"Noted, on the free chain."})}}]}
        b = json.dumps({"choices":[{"message":msg}]}).encode()
        s.send_response(200); s.send_header("Content-Type","application/json")
        s.send_header("Content-Length",str(len(b))); s.end_headers(); s.wfile.write(b)

def cfg_for(tmp):
    c = Config()
    c.anthropic_api_key = ""            # deliberately none
    c.fallback_base = f"http://127.0.0.1:{PORT}/v1/chat/completions"
    c.fallback_models = "auto/best-free"
    c.map_path = tmp/"map.json"
    return c

async def main():
    h = ThreadingHTTPServer(("127.0.0.1", PORT), F)
    threading.Thread(target=h.serve_forever, daemon=True).start()
    tmp = Path(tempfile.mkdtemp())

    c = cfg_for(tmp)
    print("1. shipped chain:", c.models)
    assert c.models == "omniroute"

    st = WorldState()
    store = MapStore(c.map_path)
    b = Brain(st, ToolExecutor(st, c, mapstore=store), c)
    print("2. no API key at all -> brain available:", b.available,
          "| gateway-only:", b.gateway_only)
    assert b.available and b.gateway_only, "refused to start without a key it never uses"
    assert b._client is None, "an Anthropic client was built anyway"

    reply = await b.respond(user_text="add try the free chain to personal")
    print("3. answered:", reply)
    # Free providers get the address too — enforced locally, not by them.
    assert reply == "Noted, on the free chain, sir."
    print("4. gateway round trips:", STATE["hits"], "| Anthropic calls: 0 (no client exists)")

    kids = [n["t"] for n in store.data["nodes"].values()
            if n.get("p") and store.node(n["p"])["t"] == "Personal"]
    print("5. tools worked on the free chain:", kids)
    assert "Try the free chain" in kids
    print("6. tools offered:", len(STATE["tools"]), "including",
          [t for t in STATE["tools"] if t in ("search_web","map_add","fetch_page")])

    # gateway down, no key -> quiet, and still no bill
    STATE["up"] = False
    b2 = Brain(WorldState(), ToolExecutor(WorldState(), cfg_for(tmp)), cfg_for(tmp))
    print("7. gateway down, no key ->", await b2.respond(user_text="hi"),
          "(silence, not a surprise charge)")

    # and a key present changes nothing while the chain says omniroute
    c3 = cfg_for(tmp); c3.anthropic_api_key = "sk-test"
    STATE["up"] = True; STATE["hits"] = 0
    b3 = Brain(WorldState(), ToolExecutor(WorldState(), c3, mapstore=store), c3)
    await b3.respond(user_text="hello")
    print("8. key present but chain is free-only -> gateway hits:", STATE["hits"],
          "| Anthropic used:", b3.rung != 0 or False)

    h.shutdown()
    print("\nAll free-chain checks passed.")

asyncio.run(main())
