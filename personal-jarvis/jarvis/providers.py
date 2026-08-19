"""The backup bench — the best model from each maker on GitHub Models.

    python -m jarvis.providers            # show the ladder it would build
    python -m jarvis.providers --all      # show everything in the catalogue

GitHub Models carries a few hundred models. Hardcoding a list of them would
be wrong within a month: names change, models are retired, new ones land. So
this fetches the catalogue and ranks it, and the ladder is whatever is
actually available on the day you ask.

Ranking is by NAME, not by benchmark. I can read that `grok-4` outranks
`grok-3-mini`, and that an embedding model isn't a chat model — I cannot tell
you which of two flagships is cleverer. Treat the order as a sensible
default, and override it with GITHUB_LADDER if you disagree.

One model per maker, because the point of the ladder is to survive a rate
limit: five OpenAI models all sharing one quota is not a fallback plan.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from .config import CONFIG, Config, setup_logging

LOG = logging.getLogger("jarvis.providers")

# Makers we'd reach for, best first. Anything not listed still gets ranked,
# just after these.
PREFERRED_MAKERS = [
    "openai", "xai", "meta", "mistral-ai", "deepseek", "microsoft",
    "cohere", "ai21-labs", "core42",
]

# Name fragments that suggest the flagship of a family. Higher wins.
STRONG = {
    "gpt-5": 100, "o4": 95, "o3": 90, "gpt-4.1": 85, "gpt-4o": 80,
    "grok-4": 100, "grok-3": 85, "grok-2": 70,
    "llama-4": 100, "llama-3.3": 85, "llama-3.2": 75, "llama-3.1": 70,
    "405b": 40, "70b": 25, "maverick": 20, "scout": 10,
    "mistral-large": 100, "mistral-medium": 70, "magistral": 60,
    "deepseek-r1": 100, "deepseek-v3": 90,
    "phi-4": 100, "phi-3.5": 70,
    "command-a": 100, "command-r-plus": 80, "command-r": 60,
    "jamba-1.5-large": 100,
    "large": 30, "pro": 20, "max": 25, "plus": 15, "reasoning": 20,
}

# Not chat models, or too small to be a useful backup.
REJECT = ("embed", "embedding", "whisper", "tts", "dall-e", "image",
          "moderation", "guard", "rerank", "vision-only", "audio",
          "nano", "mini", "tiny", "small", "lite", "8b", "3b", "1b")


def _score(name: str) -> int:
    low = name.lower()
    score = 0
    for frag, pts in STRONG.items():
        if frag in low:
            score = max(score, pts) if pts >= 40 else score + pts
    return score


def _usable(entry: dict) -> bool:
    name = (entry.get("id") or entry.get("name") or "").lower()
    if not name or any(bad in name for bad in REJECT):
        return False
    # The catalogue tags what a model is for; trust it when present.
    tasks = entry.get("supported_input_modalities") or []
    caps = " ".join(str(x).lower() for x in (entry.get("capabilities") or []))
    if "embeddings" in caps:
        return False
    return True


def fetch_catalog(cfg: Config = CONFIG, timeout: float = 20.0) -> List[dict]:
    """Everything GitHub Models currently offers. Never raises."""
    if not cfg.github_token:
        LOG.warning("GITHUB_TOKEN is unset; can't read the catalogue")
        return []
    req = urllib.request.Request(
        cfg.github_catalog,
        headers={"Authorization": "Bearer " + cfg.github_token,
                 "Accept": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except Exception as exc:
        LOG.error("could not read the GitHub Models catalogue: %s", exc)
        return []
    # The endpoint has returned both a bare list and {"models": [...]} across
    # versions; accept either rather than breaking on a shape change.
    if isinstance(data, dict):
        data = data.get("models") or data.get("data") or []
    return [d for d in data if isinstance(d, dict)]


def build_ladder(entries: List[dict], size: int = 6) -> List[str]:
    """Best model per maker, makers in preference order."""
    best: Dict[str, tuple] = {}
    for e in entries:
        if not _usable(e):
            continue
        mid = e.get("id") or e.get("name") or ""
        maker = (e.get("publisher") or mid.split("/", 1)[0] or "?").lower()
        s = _score(mid)
        if maker not in best or s > best[maker][0]:
            best[maker] = (s, mid)

    def rank(item):
        maker, (s, mid) = item
        pref = PREFERRED_MAKERS.index(maker) if maker in PREFERRED_MAKERS else 99
        return (pref, -s, mid)

    return [mid for _maker, (_s, mid) in sorted(best.items(), key=rank)][:size]


def ladder(cfg: Config = CONFIG, refresh: bool = False) -> List[str]:
    """The ladder, cached on disk so startup doesn't wait on GitHub."""
    if cfg.github_ladder.strip():
        return [m.strip() for m in cfg.github_ladder.split(",") if m.strip()]

    cache = Path(cfg.github_cache)
    if not refresh and cache.is_file():
        try:
            blob = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - blob.get("at", 0) < 7 * 24 * 3600 and blob.get("ladder"):
                return blob["ladder"]
        except (OSError, ValueError):
            pass

    got = build_ladder(fetch_catalog(cfg), cfg.github_ladder_size)
    if got:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"at": time.time(), "ladder": got}),
                             encoding="utf-8")
        except OSError:
            pass
    return got


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Inspect the GitHub Models bench.")
    p.add_argument("--all", action="store_true", help="list the whole catalogue")
    p.add_argument("--refresh", action="store_true", help="ignore the cache")
    args = p.parse_args(argv)
    setup_logging(CONFIG.log_level)

    if not CONFIG.github_token:
        print("Set GITHUB_TOKEN in .env first — github.com/settings/tokens,")
        print("a classic token with no scopes is enough.")
        return 1

    entries = fetch_catalog(CONFIG)
    if not entries:
        print("\nNothing came back. Either the token is wrong, or the endpoint")
        print(f"has moved from:\n  {CONFIG.github_catalog}\nFix GITHUB_CATALOG in .env.")
        return 1

    print(f"\n{len(entries)} models in the catalogue.\n")
    if args.all:
        for e in sorted(entries, key=lambda x: (x.get("id") or "")):
            mid = e.get("id") or e.get("name")
            mark = "  " if _usable(e) else "x "
            print(f" {mark}{mid}")
        print("\n(x = skipped: not a chat model, or too small to be a useful backup)")

    rungs = build_ladder(entries, CONFIG.github_ladder_size)
    print("\nThe ladder Jarvis would use, one per maker:\n")
    for i, m in enumerate(rungs, 1):
        print(f"  {i}. {m}")
    print("\nPin your own order with GITHUB_LADDER=a,b,c in .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
