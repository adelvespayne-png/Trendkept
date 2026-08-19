"""The intelligent map: model -> map tools -> disk -> served page."""
import asyncio, json, tempfile, urllib.error, urllib.request
from pathlib import Path
from vesper.config import Config
from vesper.main import Vesper
from vesper.mapstore import MapStore
from vesper.server import AskServer

TOKEN = "map-test-token-long-enough-x"
PORT = 8811

class B:
    def __init__(s, **k): s.__dict__.update(k)
class R:
    def __init__(s, c, sr="tool_use"): s.content, s.stop_reason = c, sr

class Client:
    """Plays the model: reads the map, builds a project, then answers."""
    def __init__(s):
        s.turns = [
            R([B(type="tool_use", id="1", name="map_read", input={})]),
            R([B(type="tool_use", id="2", name="map_add",
                 input={"text": "Newsletter launch"}),
               B(type="tool_use", id="3", name="map_add",
                 input={"text": "Write welcome email", "parent": "Newsletter launch"}),
               B(type="tool_use", id="4", name="map_add",
                 input={"text": "Set send day", "parent": "Newsletter launch"})]),
            R([B(type="tool_use", id="5", name="map_update",
                 input={"name": "Set send day", "action": "done"})]),
            R([B(type="tool_use", id="6", name="answer",
                 input={"text": "Newsletter launch is on the map with two points."})]),
        ]
        s.seen = []
        s.messages = s
    async def create(s, **kw):
        s.seen.append(kw)
        return s.turns.pop(0)

def call(path, payload=None, token=TOKEN, method=None):
    url = f"http://127.0.0.1:{PORT}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data else "GET"))
    if token: req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            try: return r.status, json.loads(body)
            except ValueError: return r.status, body.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")

async def main():
    tmp = Path(tempfile.mkdtemp())
    cfg = Config()
    cfg.anthropic_api_key = "t"; cfg.server_enabled = True
    cfg.models = "claude-opus-5"   # pinned: this suite stubs the Claude client
    cfg.server_token = TOKEN; cfg.server_port = PORT; cfg.server_host = "127.0.0.1"
    cfg.map_path = tmp / "map.json"
    cfg.state_path = tmp / "s.json"; cfg.log_path = tmp / "l.jsonl"

    j = Vesper(cfg)
    j.brain._client = Client(); j.brain.available = True
    j.speaker.say = lambda t: None
    task = asyncio.ensure_future(j.run()); await asyncio.sleep(0.4)

    print("1. map tools offered:",
          [t.get("name") for t in j.brain.tools if str(t.get("name","")).startswith("map")])

    st, page = await asyncio.to_thread(call, "/map?t=" + TOKEN)
    print("2. /map serves html:", st, "| token injected:",
          TOKEN in page, "| placeholder gone:", "__TOKEN__" not in page)
    # No header at all, so the query string is the only credential offered.
    bad1, _ = await asyncio.to_thread(call, "/map?t=wrong", None, None)
    bad2, _ = await asyncio.to_thread(call, "/map", None, None)
    bad3, _ = await asyncio.to_thread(call, "/map/data", None, None)
    print("3. unauthenticated /map:", bad1, bad2, "| /map/data:", bad3,
          "(all must be 401)")
    assert (bad1, bad2, bad3) == (401, 401, 401), "the map served without a token"

    st, data = await asyncio.to_thread(call, "/map/data")
    print("4. /map/data:", st, "| limbs:", [n["t"] for n in data["nodes"].values() if n.get("p")=="root"])

    # the model builds a project from one sentence
    reply = await asyncio.to_thread(call, "/ask",
        {"text": "plan the newsletter launch", "context": "pointing at Personal"})
    print("5. /ask ->", reply[1])

    st, data = await asyncio.to_thread(call, "/map/data")
    nodes = data["nodes"]
    nl = [n for n in nodes.values() if n["t"] == "Newsletter launch"]
    kids = [n["t"] + (" [done]" if n.get("done") else "")
            for n in nodes.values() if nl and n.get("p") == nl[0]["id"]]
    print("6. model built on disk ->", nl[0]["t"] if nl else "MISSING", "|", sorted(kids))
    print("7. persisted to file:", json.loads(cfg.map_path.read_text())["nodes"] != {})
    print("8. context reached the prompt:",
          any("pointing at Personal" in m["content"] for c in j.brain._client.seen
              for m in c["messages"] if isinstance(m["content"], str)))

    # browser pushing a whole map back
    data["nodes"]["root"]["t"] = "Vesper"
    st, _ = await asyncio.to_thread(call, "/map/data", data)
    st2, junk = await asyncio.to_thread(call, "/map/data", {"nope": 1})
    print("9. browser save:", st, "| junk rejected:", st2)

    # the store's own guards
    m = MapStore(tmp / "m2.json")
    print("10. loop guard:", m.move("Personal", "Ideas")[1])
    print("11. fuzzy find:", m.find("the paper log"), "|", m.find("ideas")["t"])

    task.cancel()
    try: await task
    except asyncio.CancelledError: pass
    print("\nAll map checks passed.")

asyncio.run(main())
