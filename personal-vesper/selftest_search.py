"""Web search: backend choice, and each backend's parsing."""
import json
from vesper.config import Config
from vesper.core.world_state import WorldState
from vesper.tools.tool_executor import ToolExecutor
import vesper.tools.tool_executor as te

BRAVE = {"web": {"results": [
    {"title": "Trendkept", "url": "https://trendkept.com", "description": "Trend following."},
    {"title": "Other", "url": "https://x.test", "description": "Second."}]}}
TAVILY = {"results": [
    {"title": "T", "url": "https://t.test", "content": "c" * 900}]}
DDG = '''<html><body>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ftrendkept.com%2Fabout&amp;rut=x">Trend&amp;kept <b>about</b></a>
<a class="result__snippet" href="#">A trend-following toolkit.</a>
<a class="result__a" href="https://plain.test/page">Plain result</a>
<a class="result__snippet" href="#">Second snippet.</a>
</body></html>'''

class FakeResp:
    def __init__(s, payload): s.payload = payload
    def read(s): return s.payload
    def __enter__(s): return s
    def __exit__(s, *a): return False

def patch(payload):
    te.urllib.request.urlopen = lambda req, timeout=None: FakeResp(payload)

def main():
    cfg = Config()
    ex = ToolExecutor(WorldState(), cfg)

    print("1. backend choice:")
    for prov, brave, tav, want in [("auto","","","duckduckgo"), ("auto","k","","brave"),
                                   ("auto","","k","tavily"), ("brave","","","duckduckgo"),
                                   ("none","k","","")]:
        c = Config(); c.search_provider=prov; c.brave_api_key=brave; c.tavily_api_key=tav
        got = c.search_backend()
        assert got == want, (prov, brave, tav, got, want)
        print(f"     {prov:<5} brave={brave or '-'} tavily={tav or '-'} -> {got or '(off)'}")

    cfg.search_provider = "brave"; cfg.brave_api_key = "k"
    patch(json.dumps(BRAVE).encode())
    out, err = ex.run("search_web", {"query": "trendkept"})
    d = json.loads(out)
    print("2. brave:", d["source"], "|", d["results"][0]["title"], d["results"][0]["url"])
    assert not err and len(d["results"]) == 2

    cfg.search_provider = "tavily"; cfg.tavily_api_key = "k"
    patch(json.dumps(TAVILY).encode())
    d = json.loads(ex.run("search_web", {"query": "x"})[0])
    print("3. tavily:", d["source"], "| snippet capped at", len(d["results"][0]["snippet"]))
    assert len(d["results"][0]["snippet"]) == 400

    cfg.search_provider = "duckduckgo"
    patch(DDG.encode())
    d = json.loads(ex.run("search_web", {"query": "trendkept"})[0])
    print("4. duckduckgo:", d["source"])
    for r in d["results"]:
        print("     ", r["title"], "->", r["url"], "|", r["snippet"][:30])
    assert d["results"][0]["url"] == "https://trendkept.com/about", "redirect not unwrapped"
    assert d["results"][0]["title"] == "Trend&kept about", d["results"][0]["title"]
    assert d["results"][0]["snippet"], "snippet not paired"
    print("5. redirect unwrapped, entities decoded, snippets paired")

    # failures are results, never crashes
    def boom(req, timeout=None): raise OSError("network is down")
    te.urllib.request.urlopen = boom
    print("6. backend down ->", ex.run("search_web", {"query": "x"})[0][:60])
    print("7. empty query ->", ex.run("search_web", {"query": "  "})[0])
    cfg.search_provider = "none"
    print("8. switched off ->", ex.run("search_web", {"query": "x"})[0])

    # the tool only appears when a backend exists
    from vesper.tools.tool_definitions import tool_definitions
    on = [t.get("name") for t in tool_definitions(include_search=True)]
    off = [t.get("name") for t in tool_definitions(include_search=False)]
    print("9. tool offered:", "search_web" in on, "| hidden when off:", "search_web" not in off)
    print("\nAll search checks passed.")

main()
