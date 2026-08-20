"""The backup bench — the best model from each maker on GitHub Models.

    python -m vesper.providers            # show the ladder it would build
    python -m vesper.providers --all      # show everything in the catalogue

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
import re
import logging
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

from .config import CONFIG, Config, setup_logging

LOG = logging.getLogger("vesper.providers")

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
    print("\nThe ladder Vesper would use, one per maker:\n")
    for i, m in enumerate(rungs, 1):
        print(f"  {i}. {m}")
    print("\nPin your own order with GITHUB_LADDER=a,b,c in .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# --- Google -----------------------------------------------------------------
#
# Google's model names move faster than any list I can write down, and a
# stale name is not a soft failure: `gemini-2.5-flash` now answers 404 with
# "no longer available to new users". Worse, a name can be IN the key's own
# /v1beta/models listing and still 404 on use. So the ladder is discovered
# from the key, and `replacement_for` below reads the model Google names in
# its own error when one has moved.

GOOGLE_MODELS = "https://generativelanguage.googleapis.com/v1beta/models"

#: Rough tiering for Gemini names. Pro first: a ladder of only Flash models
#: is the shallowest thing a key can reach, which reads to the user as an
#: assistant that isn't really thinking.
_G_TIER = (("pro", 100), ("ultra", 110), ("flash", 40), ("lite", 10))
# Models that are in the catalogue but cannot hold a chat turn. The owner's
# tune-up put `gemini-3-pro-image-preview` on the ladder because it scores
# as "pro" -- an image generator, sitting in a chain meant for conversation.
# Filtering the family word is not enough; the JOB has to be excluded too.
_G_REJECT = ("embedding", "aqa", "imagen", "veo", "tts", "vision",
             "learnlm", "gemma", "-exp", "thinking-exp",
             "image", "audio", "computer-use", "robotics", "guard")


def _g_score(name: str) -> tuple:
    low = name.lower()
    tier = 0
    for frag, pts in _G_TIER:
        if frag in low:
            tier = max(tier, pts)
    # Version number, so gemini-3.1 outranks gemini-2.5 within a tier.
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", low)
    ver = (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)
    # "latest" aliases are stable across renames -- a small nudge, not a rule.
    return (tier, ver, 1 if low.endswith("latest") else 0)


def google_models(token: str, timeout: float = 15.0) -> List[str]:
    """Chat models this key can see. Never raises; [] means 'ask me later'."""
    if not token:
        return []
    try:
        req = urllib.request.Request(
            f"{GOOGLE_MODELS}?key={urllib.parse.quote(token)}",
            headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except Exception as exc:
        LOG.warning("could not list Google's models: %s", exc)
        return []
    out = []
    for m in data.get("models", []):
        name = (m.get("name") or "").split("/")[-1]
        methods = m.get("supportedGenerationMethods") or []
        if not name or any(b in name.lower() for b in _G_REJECT):
            continue
        if methods and "generateContent" not in methods:
            continue
        out.append(name)
    return out


def google_ladder(token: str, size: int = 4) -> List[str]:
    """Best-first: the strongest tier the key can reach, Flash underneath."""
    names = google_models(token)
    if not names:
        return []
    ranked = sorted(set(names), key=_g_score, reverse=True)
    # One Flash on the end as a backup for when the good one is busy --
    # but never a ladder made only of Flash.
    top = [n for n in ranked if _g_score(n)[0] >= 100][:size - 1]
    flash = [n for n in ranked if _g_score(n)[0] == 40][:1]
    return (top + flash) or ranked[:size]


_MOVED = re.compile(r"use\s+models/([A-Za-z0-9._-]+)")


def replacement_for(body: str) -> Optional[str]:
    """The model Google names when the one you asked for has moved.

    Its 404 says: "This model models/gemini-2.5-flash is no longer available
    to new users. Please update your code to use models/gemini-3.6-flash".
    That is a free, authoritative answer to "what should I have said" --
    following it beats making the user edit a settings file.
    """
    m = _MOVED.search(body or "")
    return m.group(1) if m else None


# --- the chain of providers -------------------------------------------------
#
# The lesson from the owner's 20 August log: three Gemini rungs all died in
# the same second, because they were three names in front of ONE free
# allowance. A ladder is only a ladder if the rungs can fail independently.
# So the unit of fallback is a PROVIDER -- its own endpoint, its own key,
# its own quota -- and models are just the rungs inside one.

#: Providers that exist, with the endpoint that lists what a key can reach.
#: Every one of these speaks the OpenAI dialect, which is the only reason a
#: single `_gateway` can talk to all of them.
PROVIDERS = {
    "google": {
        "base": "https://generativelanguage.googleapis.com"
                "/v1beta/openai/chat/completions",
        "label": "Google AI Studio",
    },
    "groq": {
        "base": "https://api.groq.com/openai/v1/chat/completions",
        "models": "https://api.groq.com/openai/v1/models",
        "label": "Groq",
    },
    "cerebras": {
        "base": "https://api.cerebras.ai/v1/chat/completions",
        "models": "https://api.cerebras.ai/v1/models",
        "label": "Cerebras",
    },
}

#: Providers that USED to be here. Keeping them named, with the reason, so
#: that anyone whose .env still points at one gets told what happened
#: instead of a bare connection error.
#:
#: GitHub Models was recommended in this file for exactly one evening
#: before its catalogue answered 410 Gone on the owner's laptop. It was
#: retired on 30 July 2026 -- playground, catalogue, inference API and BYOK
#: all withdrawn. The lesson is in `chain()`: a free tier is a business
#: decision someone else can reverse, so the code has to survive one
#: disappearing.
RETIRED = {
    "github": "GitHub Models was retired on 30 July 2026 — the whole "
              "inference API is gone, so a token for it cannot help.",
}

#: Not chat models, whoever makes them.
_OPENAI_REJECT = ("whisper", "tts", "embed", "guard", "moderation", "rerank",
                  "vision", "image", "audio", "distil", "safety", "prompt")


def openai_models(models_url: str, token: str, timeout: float = 15.0) -> List[str]:
    """What this key can reach, from an OpenAI-style /models endpoint."""
    if not (models_url and token):
        return []
    try:
        req = urllib.request.Request(
            models_url, headers={"Accept": "application/json",
                                 "Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except Exception as exc:
        LOG.warning("could not list models at %s: %s", models_url, exc)
        return []
    out = []
    for m in data.get("data", data if isinstance(data, list) else []):
        mid = (m.get("id") or "") if isinstance(m, dict) else str(m)
        if mid and not any(b in mid.lower() for b in _OPENAI_REJECT):
            out.append(mid)
    return out


def _openai_score(name: str) -> tuple:
    """Bigger and newer first. Parameter count is the strongest signal."""
    low = name.lower()
    m = re.search(r"(\d+)\s*b\b", low)
    size = int(m.group(1)) if m else 0
    bonus = 0
    for frag, pts in (("versatile", 30), ("instruct", 10), ("70", 0),
                      ("maverick", 25), ("scout", 10), ("qwen", 5),
                      ("deepseek", 20), ("llama-4", 25), ("llama-3.3", 15)):
        if frag in low:
            bonus += pts
    return (size, bonus, low)


def openai_ladder(models_url: str, token: str, size: int = 3) -> List[str]:
    names = openai_models(models_url, token)
    return sorted(set(names), key=_openai_score, reverse=True)[:size]


def _key_for(cfg: Config, name: str) -> str:
    """The key for a provider, from its own env var."""
    import os

    return os.environ.get(f"{name.upper()}_API_KEY", "")


def _google_key(cfg: Config) -> str:
    # GOOGLE_API_KEY if it is set, else the generic FALLBACK_TOKEN, which is
    # where a single-provider setup already has it.
    return cfg.google_token or cfg.fallback_token


def chain(cfg: Config = CONFIG) -> List[dict]:
    """The providers to try, in order, each with its own models and key.

    Returns [] when no chain is configured, which means "use the single
    FALLBACK_BASE" -- the behaviour every existing install already has.
    """
    names = [n.strip().lower() for n in cfg.fallback_chain.split(",")
             if n.strip()]
    if not names:
        return []

    out = []
    for name in names:
        if name in RETIRED:
            LOG.error("%s", RETIRED[name])
            continue
        spec = PROVIDERS.get(name)
        if not spec:
            LOG.warning("unknown provider %r in FALLBACK_CHAIN; skipping", name)
            continue
        if name == "google":
            token = _google_key(cfg)
            models = ([m.strip() for m in cfg.fallback_models.split(",")
                       if m.strip()]
                      if "generativelanguage" in cfg.fallback_base
                      else []) or google_ladder(token)
        else:
            token = _key_for(cfg, name)
            models = openai_ladder(spec.get("models", ""), token)
        if not token:
            LOG.info("%s has no key set; skipping that rung", spec["label"])
            continue
        if not models:
            LOG.warning("%s gave no usable models; skipping that rung",
                        spec["label"])
            continue
        out.append({"name": name, "label": spec["label"],
                    "base": spec["base"], "token": token, "models": models})
    return out
