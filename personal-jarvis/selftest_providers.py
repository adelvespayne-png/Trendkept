"""Ranking a catalogue. Shapes mimic GitHub Models; the real one is unreachable here."""
import asyncio, json, tempfile
from pathlib import Path
from jarvis.config import Config
from jarvis.providers import build_ladder, _usable, _score, ladder
import jarvis.providers as prov

CATALOG = [
    {"id": "openai/gpt-4o-mini", "publisher": "openai"},
    {"id": "openai/gpt-4o", "publisher": "openai"},
    {"id": "openai/gpt-5", "publisher": "openai"},
    {"id": "openai/text-embedding-3-large", "publisher": "openai",
     "capabilities": ["embeddings"]},
    {"id": "xai/grok-3-mini", "publisher": "xai"},
    {"id": "xai/grok-4", "publisher": "xai"},
    {"id": "meta/Llama-4-Maverick-17B", "publisher": "meta"},
    {"id": "meta/Meta-Llama-3.1-8B-Instruct", "publisher": "meta"},
    {"id": "meta/Meta-Llama-3.1-405B-Instruct", "publisher": "meta"},
    {"id": "mistral-ai/mistral-large-2411", "publisher": "mistral-ai"},
    {"id": "mistral-ai/ministral-3b", "publisher": "mistral-ai"},
    {"id": "deepseek/DeepSeek-R1", "publisher": "deepseek"},
    {"id": "deepseek/DeepSeek-V3-0324", "publisher": "deepseek"},
    {"id": "microsoft/Phi-4", "publisher": "microsoft"},
    {"id": "microsoft/Phi-3.5-mini-instruct", "publisher": "microsoft"},
    {"id": "cohere/cohere-command-a", "publisher": "cohere"},
    {"id": "ai21-labs/AI21-Jamba-1.5-Large", "publisher": "ai21-labs"},
    {"id": "openai/whisper-large", "publisher": "openai"},
]

def main():
    print("1. junk rejected:",
          [e["id"] for e in CATALOG if not _usable(e)])

    rungs = build_ladder(CATALOG, size=6)
    print("2. ladder (one per maker, best first):")
    for i, m in enumerate(rungs, 1):
        print(f"     {i}. {m}")

    makers = [m.split("/")[0] for m in rungs]
    assert len(makers) == len(set(makers)), "two rungs share a quota"
    print("3. no two rungs share a maker:", makers)

    assert rungs[0] == "openai/gpt-5", rungs
    assert "xai/grok-4" in rungs and "xai/grok-3-mini" not in rungs
    assert "meta/Meta-Llama-3.1-8B-Instruct" not in rungs
    print("4. flagship beat the small sibling in each family")

    print("5. size cap honoured:", len(build_ladder(CATALOG, size=3)), "of 3")

    # a shape change in the endpoint must not crash the ladder
    for weird in ([], [{"name": "solo/model-x"}], [{"nonsense": 1}]):
        build_ladder(weird, 6)
    print("6. odd catalogue shapes survive")

    # cache round-trip, and a pinned ladder overriding discovery
    tmp = Path(tempfile.mkdtemp())
    cfg = Config(); cfg.github_cache = tmp / "c.json"; cfg.github_token = ""
    cfg.github_ladder = "a/one, b/two"
    print("7. pinned ladder wins:", ladder(cfg))

    cfg2 = Config(); cfg2.github_cache = tmp / "c2.json"; cfg2.github_token = "t"
    cfg2.github_ladder = ""
    prov.fetch_catalog = lambda c, timeout=20.0: CATALOG
    first = ladder(cfg2)
    prov.fetch_catalog = lambda c, timeout=20.0: []      # network gone
    second = ladder(cfg2)
    print("8. cached, so a dead network still gives:", second == first, second[:2])

    cfg3 = Config(); cfg3.github_cache = tmp / "none.json"
    cfg3.github_token = ""; cfg3.github_ladder = ""
    print("9. no token -> empty ladder, no crash:", ladder(cfg3))
    print("\nAll provider checks passed.")

main()
