"""The double-click path: set up if needed, start, open the map.

    python -m vesper.launch --setup    # first run: write .env, make a token
    python -m vesper.launch            # every run after: start and open the map

`Vesper.bat` is three lines that call this. The work lives here rather than in
the batch file because batch is untestable and unreadable, and because the
same launcher then works on a Mac or a Linux box unchanged.

What it does that `python -m vesper.main --serve` does not:

  * writes a `.env` on first run, with a real random token already in it, so
    nobody has to be told to generate one and paste it somewhere;
  * turns the phone bridge on, because that is also what serves the map;
  * waits for the bridge to actually accept a connection, then opens the
    browser at the map with the token in the URL.

That last point is the answer to "does making this an app stop the browser
part working": the browser page is served BY this program. They are not two
options. This is what opens it.
"""

from __future__ import annotations

import logging
import re
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional, Tuple

from .config import CONFIG, reload_env, setup_logging

LOG = logging.getLogger("vesper.launch")

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def ensure_env(env: Path = ENV, example: Path = EXAMPLE) -> Tuple[bool, str]:
    """Make sure a usable `.env` exists. Returns (created, note).

    Never touches an existing one. Someone's API keys and their tuned
    thresholds live in that file, and a launcher that overwrote it because a
    setting looked wrong would be unforgivable.
    """
    if env.exists():
        return False, "kept the .env you already have"
    if not example.exists():
        return False, f"no .env.example next to the code ({example})"

    try:
        text = example.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"could not read .env.example: {exc}"

    # Fill in the two settings that otherwise need a manual step, so the
    # first run works rather than stopping to explain something.
    text = _set(text, "SERVER_ENABLED", "true")
    text = _set(text, "SERVER_TOKEN", new_token())

    try:
        env.write_text(text, encoding="utf-8")
    except OSError as exc:
        return False, f"could not write .env: {exc}"
    return True, "wrote a fresh .env with a private token"


def _set(text: str, key: str, value: str) -> str:
    """Replace `KEY=...` in place, keeping the comments around it."""
    out, done = [], False
    for line in text.splitlines():
        if line.strip().startswith(key + "=") and not done:
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    return "\n".join(out) + "\n"


def _get(text: str, key: str, default: str = "") -> str:
    """Read `KEY=...` out of a .env's text — the file, not the environment."""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(key + "=") and not s.startswith("#"):
            return s[len(key) + 1:].strip()
    return default


def map_url(cfg=CONFIG, host: Optional[str] = None) -> str:
    """Where the map lives, token included so the browser gets straight in."""
    where = host or ("127.0.0.1" if cfg.server_host in ("0.0.0.0", "")
                     else cfg.server_host)
    return f"http://{where}:{cfg.server_port}/map?t={cfg.server_token}"


def wait_for_bridge(host: str, port: int, timeout: float = 25.0) -> bool:
    """Block until something is listening, so the browser isn't opened early.

    Opening the browser the instant we start the assistant races the model
    loading, and the reward for losing that race is a connection-refused page
    and a user who thinks it is broken.
    """
    end = time.monotonic() + timeout
    probe = "127.0.0.1" if host in ("0.0.0.0", "") else host
    while time.monotonic() < end:
        try:
            with socket.create_connection((probe, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def open_map_when_ready(cfg=CONFIG, timeout: float = 25.0) -> None:
    """Wait for the bridge on a background thread, then open the browser."""
    def run() -> None:
        if wait_for_bridge(cfg.server_host, cfg.server_port, timeout):
            url = map_url(cfg)
            LOG.info("opening the map: %s", url)
            try:
                webbrowser.open(url)
            except Exception as exc:
                print(f"\nCould not open a browser ({exc}). Go here yourself:\n  {url}\n")
        else:
            print("\nThe map did not come up in time. Once Vesper has "
                  "finished starting, open:\n  " + map_url(cfg) + "\n")
    threading.Thread(target=run, daemon=True, name="open-map").start()


def setup(argv=None) -> int:
    """First run. Idempotent, so double-clicking it twice is harmless."""
    created, note = ensure_env()
    print(f"\n  {note}")
    if not created and not ENV.exists():
        print("\nSetup could not finish. Fix the line above and run it again.\n")
        return 1

    # The .env we just wrote is newer than this process, so pull it in
    # before asking what the settings are.
    reload_env(ENV)
    from .config import Config
    cfg = Config()
    ok = bool(cfg.server_token and len(cfg.server_token) >= 16)
    print(f"  phone bridge {'on' if cfg.server_enabled else 'OFF'}, "
          f"token {'set' if ok else 'MISSING'}")
    print(f"  map will open at {map_url(cfg)}")
    print("\nSetup done. Start Vesper by double-clicking Vesper.bat"
          if sys.platform.startswith("win") else
          "\nSetup done. Start Vesper with: python -m vesper.launch")
    print()
    return 0 if ok else 1


# Flash-tier names, whoever makes them. A ladder of only these is the
# cheapest, shallowest thing the key can reach, which is what "it barely
# responds" actually means most of the time.
_THIN = ("flash", "mini", "lite", "nano", "8b", "haiku", "small")


def _thin_model(name: str) -> bool:
    """Is this one model id a small-tier one?

    Matched on whole segments, NOT as a substring. "gemini" contains "mini",
    so a substring test called every Google model small — including the Pro
    ones this had just put at the top, which made the tune-up rewrite its
    own work every time it ran.
    """
    parts = re.split(r"[^a-z0-9]+", name.strip().lower())
    return any(p in _THIN for p in parts)


def _looks_thin(models: str) -> bool:
    rungs = [m for m in (x.strip() for x in models.split(",")) if m]
    return bool(rungs) and all(_thin_model(m) for m in rungs)


def _unusable(models: str) -> list:
    """Rungs that cannot hold a chat turn at all, whatever they score.

    The owner's ladder carried `gemini-3-pro-image-preview` for two days
    because the tune-up only ever rewrote a ladder that was ENTIRELY
    small-tier. Theirs led with a proper Pro model, so it was declared fine
    and the image generator sat there untouched. "Leads with something
    good" is not the same as "contains nothing broken".
    """
    from .providers import _G_REJECT, _OPENAI_REJECT

    bad = set(_G_REJECT) | set(_OPENAI_REJECT)
    return [m for m in (x.strip() for x in models.split(",")) if m
            and any(b in m.lower() for b in bad)]


def tuneup() -> int:
    """Fix the two things that make an existing install feel stupid.

    Both are the same class of problem: something that is only decided when
    an install is BORN, on an install that was born before it was decided.

      * the map, which is seeded once and then never touched again, so a
        laptop set up last week still has the thin starting map;
      * the model ladder in .env, which was written from an example that
        put a Flash model first.

    Nothing here is destructive. The map is backed up beside itself and
    anything the owner added survives; .env is backed up before the one
    line is changed, and a ladder that already leads with a proper model is
    left alone.
    """
    from .config import Config

    reload_env(ENV)
    cfg = Config()
    print()

    # -- the map ---------------------------------------------------------
    from .mapstore import MapStore

    store = MapStore(Path(cfg.map_path))
    added, kept = store.refresh_from_seed()
    if added:
        print(f"  Map: {added} points added, {kept} of your own kept.")
    else:
        print(f"  Map: already up to date ({kept} of your own).")
    print(f"       {store.summary()}")

    # -- the ladder ------------------------------------------------------
    if not ENV.is_file():
        print("\n  No .env yet — run the installer first.\n")
        return 1
    added = add_missing_settings()
    if added:
        print(f"\n  Settings: added {len(added)} line(s) your .env was "
              f"missing —\n            {', '.join(added[:6])}"
              + (" ..." if len(added) > 6 else "")
              + "\n            They are blank; fill in the ones you want.")
    text = ENV.read_text(encoding="utf-8")

    # -- the brain -------------------------------------------------------
    # No amount of scaffolding makes a weak model clever. Memory, routing
    # and a checking pass all help, but they help a good model more than a
    # thin one -- so if there is a paid key, it goes at the top.
    anth = _get(text, "ANTHROPIC_API_KEY", "")
    chain_models = _get(text, "VESPER_MODELS", cfg.models)
    if anth and "claude" not in chain_models.lower():
        text = _set(text, "VESPER_MODELS", "claude-opus-5,gateway")
        ENV.write_text(text, encoding="utf-8")
        print("\n  Brain:     Claude Opus 5 first, free providers behind it.")
        print("             That is the single biggest change to how clever")
        print("             she is; everything else helps a good model more")
        print("             than a thin one.")
    elif anth:
        print(f"\n  Brain:     {chain_models.split(',')[0]} — a paid model "
              "leads. Good.")
    else:
        print("\n  Brain:     free tiers only. They are the reason answers "
              "feel thin —\n             no routing or memory fixes a small "
              "model. An\n             ANTHROPIC_API_KEY in .env is the one "
              "real upgrade;\n             run `Check Vesper` and it will "
              "price it for you.")

    # -- providers -------------------------------------------------------
    # One provider is one point of failure: when a free allowance is spent,
    # every model behind that key is spent in the same instant. So set up
    # the chain whenever there is a second key to put in it.
    from .providers import RETIRED

    goog = _get(text, "GOOGLE_API_KEY", "") or _get(text, "FALLBACK_TOKEN",
                                                    cfg.fallback_token)
    have = [n for n, tok in (("google", goog),
                             ("groq", _get(text, "GROQ_API_KEY", "")),
                             ("cerebras", _get(text, "CEREBRAS_API_KEY", "")))
            if tok]
    # A key for a service that has shut down is worse than no key: it looks
    # like a working second provider right up until the turn that needs it.
    if _get(text, "GITHUB_TOKEN", ""):
        print(f"\n  NOTE: {RETIRED['github']}")
        print("        You can delete GITHUB_TOKEN from .env.")
    chain_now = _get(text, "FALLBACK_CHAIN", "")
    if len(have) > 1 and chain_now == ",".join(have):
        # Nothing to change -- but SAY so. This branch printed nothing at
        # all, so a correctly-configured install looked identical to one
        # where the setting had silently failed to take, and the owner had
        # no way to tell "already done" from "didn't work".
        print(f"\n  Providers: {' then '.join(have)} — already set up. "
              "If one runs dry\n             the other takes the turn.")
    elif len(have) > 1:
        try:
            ENV.with_suffix(".bak4").write_text(text, encoding="utf-8")
            text = _set(text, "FALLBACK_CHAIN", ",".join(have))
            if goog and not _get(text, "GOOGLE_API_KEY", ""):
                text = _set(text, "GOOGLE_API_KEY", goog)
            ENV.write_text(text, encoding="utf-8")
            print(f"\n  Providers: {' then '.join(have)}. If one runs dry the "
                  "other takes\n             the turn — different keys, "
                  "different allowances.")
        except OSError as exc:
            print(f"\n  Could not write the provider chain ({exc}).")
    elif len(have) == 1:
        others = [x for x in ("groq", "cerebras") if x not in have]
        suggest = (others[0].upper() + "_API_KEY") if others else "another key"
        print(f"\n  Providers: {have[0]} only. One key means one allowance — "
              "when it is\n             spent there is nothing behind it. "
              f"Put a {suggest}\n             in .env for a second, separate "
              "bucket (free, no card).")
    # Straight out of the file, NOT out of Config. `.env` is
    # first-occurrence-wins and never overrides a variable already in the
    # environment, so after this function has run once the Config in this
    # process still reports the OLD ladder — and the tune-up would happily
    # prepend the same two models a second time.
    current = _get(text, "FALLBACK_MODELS", cfg.fallback_models)
    junk = _unusable(current)
    google = "generativelanguage.googleapis.com" in cfg.fallback_base
    if junk and google:
        print(f"\n  Models: {', '.join(junk)}\n          cannot hold a "
              "conversation — that is an image or audio\n          model. "
              "Rebuilding the list from your key.")
        rebuild = True
    else:
        rebuild = _looks_thin(current)
    if not rebuild:
        print(f"\n  Models: leaving {current} alone — it already leads with "
              "a full-size model.")
    elif "generativelanguage.googleapis.com" not in cfg.fallback_base:
        # Only Google's names are ours to rewrite; anywhere else and a
        # guessed model id is worse than the thin one that at least works.
        print(f"\n  Models: {current} is all small models, which is why the "
              "answers feel thin.\n          I can only rename these "
              "automatically for Google's API. Put a\n          bigger model "
              "first in FALLBACK_MODELS by hand.")
    else:
        # ASK THE KEY. Google's names move, and a name can even be in the
        # key's own listing and still answer 404 on use, so a list I wrote
        # down last month is a liability -- `gemini-2.5-flash` is already
        # "no longer available to new users". Discovery beats guessing.
        from .providers import google_ladder

        found = google_ladder(_get(text, "FALLBACK_TOKEN", cfg.fallback_token))
        if not found:
            # Could be no internet, could be a key Google won't accept. Say
            # both rather than guessing, and say what still works.
            print("\n  Models: couldn't get an answer from Google — either no\n"
                  "          internet, or that key isn't accepted. Left the\n"
                  "          list alone.")
            if "github" in have:
                print("          GitHub is still in the chain, so Vesper can\n"
                      "          still answer. Re-run this when Google is back.")
            print("\n  Done. Close this window and start Vesper again.\n")
            return 0
        better = ",".join(found)
        try:
            ENV.with_suffix(".bak3").write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"\n  Could not back up .env ({exc}); not touching it.")
            return 1
        ENV.write_text(_set(text, "FALLBACK_MODELS", better), encoding="utf-8")
        print(f"\n  Models: was {current}\n"
              f"          now {better}\n"
              "          (asked your key what it can actually reach; the "
              "strongest\n           first, one Flash on the end as backup. "
              "Old file kept\n           as .env.bak3.)")

    print("\n  Done. Close this window and start Vesper again.\n")
    return 0


def _keys_in(text: str) -> "dict":
    """Every setting a .env-shaped file defines: name -> value, in order."""
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            name, _, value = s.partition("=")
            name = name.strip()
            if name and name not in out:
                out[name] = value.strip()
    return out


def add_missing_settings() -> list:
    """Give an existing .env the settings a newer .env.example added.

    `ensure_env` deliberately never touches an existing .env -- someone's
    keys live in it. The cost of that is drift: a .env written in July has
    no GROQ_API_KEY line, so the owner opens it looking for one, cannot
    find it, and has to be told to type the name from memory. Appending the
    missing names BLANK is safe (blank means that subsystem is simply off)
    and it means the line is there to fill in next time.

    Returns the names added.
    """
    if not (ENV.is_file() and EXAMPLE.is_file()):
        return []
    try:
        env_text = ENV.read_text(encoding="utf-8")
        example = EXAMPLE.read_text(encoding="utf-8")
    except OSError:
        return []

    have = _keys_in(env_text)
    defaults = _keys_in(example)
    missing = [k for k in defaults if k not in have]
    if not missing:
        return []

    block = ["", "", "# ---------------------------------------------------",
             "# Added by the tune-up: settings that exist in the current",
             "# .env.example but were not in your file yet. Blank means the",
             "# feature is simply off, so these are safe to leave empty.",
             "# ---------------------------------------------------"]
    # The example's VALUE, not a blank. Config reads these with
    # `os.environ.get(NAME, default)`, and an empty string is a value --
    # so appending `VESPER_MODELS=` would override the default with
    # nothing and take the model ladder out entirely. Keys are blank in
    # the example anyway, which is what makes this safe for secrets.
    block += [f"{k}={defaults[k]}" for k in missing]
    try:
        ENV.write_text(env_text.rstrip("\n") + "\n" + "\n".join(block) + "\n",
                       encoding="utf-8")
    except OSError as exc:
        LOG.warning("could not add the missing settings: %s", exc)
        return []
    return missing


#: What a key from each service actually looks like. A key of the wrong
#: SHAPE is the failure that wastes the most time, because the error comes
#: back from the provider as a plausible-sounding 401/403/429 rather than
#: "that is not one of our keys" -- so the obvious reading is "my account
#: has a problem" when the real answer is "that string is not an API key".
_KEY_SHAPES = {
    # BOTH are valid. Google is midway through changing the format: older
    # keys are "AIza...", freshly issued ones are "AQ....". I flagged AQ.
    # as an OAuth token and sent the owner off to hunt for an AIza key
    # their account cannot issue any more. A shape check is only worth
    # having if it is right about the shapes.
    "GOOGLE_API_KEY": (("AIza", "AQ."),
                       "a Google AI Studio key starts 'AIza' (older) or "
                       "'AQ.' (newer) — from aistudio.google.com > Get "
                       "API key"),
    "GROQ_API_KEY": ("gsk_", "a Groq key starts 'gsk_' — from "
                             "console.groq.com > API Keys"),
    "ANTHROPIC_API_KEY": ("sk-ant-", "an Anthropic key starts 'sk-ant-'"),
    "GITHUB_TOKEN": ("github_pat_", "a fine-grained GitHub token starts "
                                    "'github_pat_'"),
}


def _shape_warning(name: str, key: str) -> str:
    """Flag a key that cannot be what it claims to be."""
    if not key:
        return ""
    prefix, why = _KEY_SHAPES.get(name, ("", ""))
    if isinstance(prefix, str):
        prefix = (prefix,) if prefix else ()
    if prefix and not any(key.startswith(x) for x in prefix):
        return f"\n               ^ WRONG SHAPE: {why}"
    return ""


def _mask(tok: str) -> str:
    if not tok:
        return "(not set)"
    return f"{tok[:6]}...{tok[-4:]}  ({len(tok)} chars)" if len(tok) > 12 \
        else "(set, suspiciously short)"


def _ua() -> str:
    from .providers import USER_AGENT

    return USER_AGENT


def _probe(base: str, token: str, model: str, timeout: float = 30.0):
    """Send the smallest real request there is. Returns (ok, one-line why)."""
    import json
    import urllib.error
    import urllib.request

    # NOT 16. Reasoning models -- gpt-oss and every current Gemini among
    # them -- spend tokens thinking before they write anything, and that
    # spend comes out of this budget. At 16 the thinking ate it and the
    # probe reported "the call worked, reply was empty", which reads as a
    # half-failure when the provider was in fact perfectly healthy. Same
    # trap as the 1500-token gateway budget earlier.
    body = json.dumps({"model": model,
                       "messages": [{"role": "user",
                                     "content": "Reply with the word: ok"}],
                       "max_tokens": 512}).encode()
    req = urllib.request.Request(
        base, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": _ua(),
                 "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        msg = ((data.get("choices") or [{}])[0].get("message") or {})
        said = (msg.get("content") or "").strip()
        # Parenthesised deliberately: `return a, b if c else d` binds as
        # `return (a, (b if c else d))`, which was nesting a whole tuple
        # into the message slot on the empty branch.
        return (True, f"answered: {said[:40]!r}" if said
                else "answered (the call worked, reply was empty)")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            blob = json.loads(exc.read().decode("utf-8", "replace"))
            detail = (blob.get("error") or {}).get("message", "")
        except Exception:
            pass
        return False, f"HTTP {exc.code} — {detail[:150] or exc.reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:120]}"


def doctor() -> int:
    """Print exactly what Vesper can and cannot reach, and why.

    Written because "it still says the allowance is spent" has at least
    four different causes -- no second provider configured, a token that
    was never pasted in, a token with the wrong permission, or a second
    provider that is genuinely also out -- and they are indistinguishable
    from the outside. Guessing at that over chat is slow and usually wrong.
    """
    from .config import Config
    from .providers import PROVIDERS, chain

    reload_env(ENV)
    cfg = Config()
    text = ENV.read_text(encoding="utf-8") if ENV.is_file() else ""

    print("\n  Settings file")
    print(f"    {ENV}   {'(found)' if ENV.is_file() else 'MISSING'}")

    print("\n  Keys")
    # Every provider that can actually serve a turn, so a key that is
    # simply absent is visible as absent. Groq was missing from this list
    # while its rung was failing, which made "is the key even set?"
    # unanswerable from the one output meant to answer exactly that.
    for label, name in (("Google", "GOOGLE_API_KEY"),
                        ("Groq", "GROQ_API_KEY"),
                        ("Cerebras", "CEREBRAS_API_KEY"),
                        ("Anthropic", "ANTHROPIC_API_KEY"),
                        ("GitHub", "GITHUB_TOKEN")):
        key = _get(text, name, "")
        if not key and name == "GOOGLE_API_KEY":
            key = _get(text, "FALLBACK_TOKEN", "")
        note = _shape_warning(name, key)
        print(f"    {label:<10} {_mask(key)}{note}")

    # The duplicate check, done HERE so nobody has to run a command that
    # prints the secret to find out. `.env` is first-occurrence-wins, so a
    # blank line above a filled one silently wins and the key looks unset.
    dupes = []
    for name in ("GOOGLE_API_KEY", "GITHUB_TOKEN", "ANTHROPIC_API_KEY",
                 "FALLBACK_TOKEN", "FALLBACK_CHAIN", "FALLBACK_MODELS"):
        hits = [ln for ln in text.splitlines()
                if ln.strip().startswith(name + "=") and not ln.strip().startswith("#")]
        if len(hits) > 1:
            blank = sum(1 for h in hits if not h.split("=", 1)[1].strip())
            dupes.append((name, len(hits), blank))
    if dupes:
        print("\n  DUPLICATE SETTINGS — the FIRST one wins, the rest are ignored")
        for name, count, blank in dupes:
            note = f", {blank} of them empty" if blank else ""
            print(f"    {name} appears {count} times{note}")
        print("    Open .env and delete the spare lines, keeping the filled one.")

    configured = _get(text, "FALLBACK_CHAIN", "")
    print("\n  Provider chain")
    print(f"    FALLBACK_CHAIN = {configured or '(blank — single provider mode)'}")

    stack = chain(cfg)
    if not stack:
        print(f"    Resolved to: nothing. Falling back to the single endpoint:")
        print(f"      {cfg.fallback_base}")
        print(f"      models: {cfg.fallback_models}")
        print("\n    ONE PROVIDER MEANS ONE ALLOWANCE. When it is spent there")
        print("    is nothing behind it. Put a GROQ_API_KEY in .env (free,")
        print("    no card) and run the tune-up to get a second one.")
        stack = [{"label": "the gateway", "base": cfg.fallback_base,
                  "token": cfg.fallback_token or cfg.github_token,
                  "models": [m.strip() for m in cfg.fallback_models.split(",")
                             if m.strip()]}]
    else:
        for i, prov in enumerate(stack, 1):
            print(f"    {i}. {prov['label']}: {len(prov['models'])} model(s), "
                  f"first is {prov['models'][0]}")

    print("\n  Live test — one tiny request to each")
    any_ok = False
    for prov in stack:
        if not prov["models"]:
            print(f"    {prov['label']:<20} no models to try")
            continue
        # EVERY model, not just the first. Google's free allowance is per
        # model, so the top rung can be out while a lower one has 1,500
        # requests left -- and testing only the top reported the whole
        # provider dead when it was not.
        for i, model in enumerate(prov["models"]):
            ok, why = _probe(prov["base"], prov["token"], model)
            label = prov["label"] if i == 0 else ""
            print(f"    {label:<20} {'OK  ' if ok else 'FAIL'}  "
                  f"{model}: {why}")
            if ok:
                any_ok = True
                break

    # -- the real thing --------------------------------------------------
    # The probe above sends a bare question with no tools. A real turn
    # sends the whole toolset, the context block and the history -- and
    # the gap between those two has now hidden a live bug twice: the
    # probe said OK while every actual question came back "every model is
    # busy". So do a real one, through the same brain the user talks to.
    if not _get(text, "ANTHROPIC_API_KEY", ""):
        costs()

    print("\n  A real turn — same path as talking to her")
    real, why = _real_turn()
    if real:
        print(f"    OK    she said: {real[:80]!r}")
    else:
        print(f"    FAIL  {why}")
        print("    Run  Vesper.bat --verbose  and the log will quote the "
              "provider.")

    print()
    if real:
        print("  Working. Close this and start Vesper.")
    elif any_ok:
        print("  A provider answers a bare question but not a real turn —")
        print("  so the problem is in the REQUEST, not the connection.")
    else:
        print("  Nothing answered. Vesper will speak, and will tell you why,")
        print("  but cannot reason until one of the above works.")
    print()
    return 0 if real else 1


def costs(turns_per_day: int = 25) -> None:
    """What a month actually costs, on the current list prices.

    Printed rather than promised. The numbers move, the assumptions are
    arguable, and an assistant that quietly costs more than someone
    budgeted is worse than one that is slightly less clever.
    """
    # USD per million tokens, input/output. August 2026 list prices.
    models = (("Claude Opus 5", "claude-opus-5", 5.00, 25.00),
              ("Claude Sonnet 5", "claude-sonnet-5", 3.00, 15.00),
              ("Claude Haiku 4.5", "claude-haiku-4-5", 1.00, 5.00))
    gbp = 1.27                      # USD per GBP, roughly
    prompt, reply, deep = 2500, 350, 0.25
    turns = turns_per_day * 30
    inp = turns * prompt * (1 + deep)
    out = turns * reply * (1 + deep)

    print(f"\n  At {turns_per_day} questions a day ({turns} a month):\n")
    print(f"    {'model':<20}{'per month':>12}{'with caching':>15}")
    for name, _id, pin, pout in models:
        plain = inp / 1e6 * pin + out / 1e6 * pout
        # The system prompt and tools are identical every turn and are
        # most of what is sent, so caching them is most of the bill.
        cached = (inp * 0.75 * pin * 0.1 + inp * 0.25 * pin) / 1e6 \
            + out / 1e6 * pout
        print(f"    {name:<20}{'£%.2f' % (plain / gbp):>12}"
              f"{'£%.2f' % (cached / gbp):>15}")
    print("\n    Caching is already on. Set a spend cap in the Anthropic")
    print("    console — it is the only thing that makes this safe to leave")
    print("    running. Claude Pro does NOT cover the API; separate purchase.")


def _real_turn():
    """Ask the actual brain one question. Returns (reply, why-not)."""
    import asyncio

    try:
        from .core.brain import Brain
        from .core.world_state import WorldState
        from .tools.tool_executor import ToolExecutor
        from .config import Config

        cfg = Config()
        state = WorldState()
        brain = Brain(state, ToolExecutor(state, cfg=cfg), cfg=cfg)
        if not brain.available:
            return None, "no reasoning configured at all"
        said = asyncio.run(brain.respond("Say the single word: ok",
                                         channel="text"))
        if said:
            return said, ""
        return None, "she returned nothing at all"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:200]}"


# The last Windows build of Piper. Confirmed reachable at this exact URL;
# the project's newer work is Linux-first, so this is the one that runs on
# a ThinkPad. Pinned rather than "latest" on purpose: a release URL that
# resolves to whatever is newest is a URL that breaks without warning.
PIPER_ZIP = ("https://github.com/rhasspy/piper/releases/download/"
             "2023.11.14-2/piper_windows_amd64.zip")
VOICE_BASE = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
              "en/en_GB/alan/medium/")
VOICE_NAME = "en_GB-alan-medium.onnx"


def _download(url: str, dest: Path) -> bool:
    import urllib.request

    from .providers import USER_AGENT

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=180) as r, \
                dest.open("wb") as fh:
            while True:
                chunk = r.read(262144)
                if not chunk:
                    break
                fh.write(chunk)
        return dest.stat().st_size > 0
    except Exception as exc:
        print(f"    could not download {url.rsplit('/', 1)[-1]}: {exc}")
        dest.unlink(missing_ok=True)
        return False


def piper_setup(home: Optional[Path] = None) -> int:
    """Fetch Piper, find the voice, and wire both into .env.

    Written as a single double-click because the manual version has four
    steps that each fail quietly: download the right zip, extract it, put
    it on PATH, then remember that PATH only reaches windows opened
    afterwards. The owner got as far as the voice files and stopped, which
    is exactly where that sequence loses people.

    Nothing here needs PATH at all -- it writes the full path to piper.exe
    into PIPER_BIN instead.
    """
    import zipfile

    home = home or Path.home()
    where = home / "Documents" / "piper"
    where.mkdir(parents=True, exist_ok=True)
    print(f"\n  Piper folder: {where}")

    # -- the program -----------------------------------------------------
    exe = next(iter(sorted(where.rglob("piper.exe"))), None)
    if exe:
        print(f"  Program:      already here ({exe.name})")
    else:
        print("  Program:      downloading (about 20 MB)...")
        zip_path = where / "piper_windows_amd64.zip"
        if not _download(PIPER_ZIP, zip_path):
            print("\n  Could not fetch Piper. Check the internet and try "
                  "again.\n")
            return 1
        try:
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(where)
        except zipfile.BadZipFile:
            print("\n  The download was not a usable zip. Try again.\n")
            return 1
        zip_path.unlink(missing_ok=True)
        exe = next(iter(sorted(where.rglob("piper.exe"))), None)
        if not exe:
            print("\n  Unpacked, but no piper.exe inside. Nothing I can "
                  "do automatically.\n")
            return 1
        print(f"  Program:      installed ({exe})")

    # Piper is useless without its pronunciation data, and the failure is
    # a raw Windows crash code rather than a message, so check it here.
    if not (exe.parent / "espeak-ng-data").is_dir():
        print(f"\n  WARNING: no espeak-ng-data folder beside {exe.name}.")
        print("  Piper will crash without it. Delete the piper folder and")
        print("  run this again to get a clean copy.\n")
        return 1
    print("  Speech data:  espeak-ng-data present")

    # -- the voice -------------------------------------------------------
    voice = next(iter(sorted(where.rglob(VOICE_NAME))), None)
    if voice:
        print(f"  Voice:        already here ({voice.name})")
    else:
        print("  Voice:        downloading (about 60 MB)...")
        voice = where / VOICE_NAME
        if not (_download(VOICE_BASE + VOICE_NAME, voice)
                and _download(VOICE_BASE + VOICE_NAME + ".json",
                              where / (VOICE_NAME + ".json"))):
            print("\n  Could not fetch the voice.\n")
            return 1
        print(f"  Voice:        installed ({voice})")

    if not (voice.with_suffix(".onnx.json")).is_file() \
            and not Path(str(voice) + ".json").is_file():
        print("\n  The voice's .json companion is missing; Piper needs "
              "both files.\n")
        return 1

    # -- the settings ----------------------------------------------------
    if not ENV.is_file():
        print("\n  No .env — run the installer first.\n")
        return 1
    text = ENV.read_text(encoding="utf-8")
    try:
        ENV.with_suffix(".bak5").write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"\n  Could not back up .env ({exc}); not touching it.\n")
        return 1
    text = _set(text, "TTS_BACKEND", "piper")
    text = _set(text, "PIPER_BIN", str(exe))
    text = _set(text, "PIPER_MODEL", str(voice))

    # Without this, installing Piper changes nothing you can hear. The map
    # page speaks replies with the BROWSER's voice (speechSynthesis);
    # Piper is the laptop's. SERVER_SPEAK_ALOUD is off by default so a
    # question asked from the phone doesn't make the laptop announce the
    # answer to an empty room -- sensible, but it also means the one
    # interface the owner actually uses would never play the voice they
    # just installed.
    spoke = _get(text, "SERVER_SPEAK_ALOUD", "").lower()
    if spoke not in ("true", "1", "yes", "on"):
        text = _set(text, "SERVER_SPEAK_ALOUD", "true")
        aloud = ("\n  Also on:      SERVER_SPEAK_ALOUD=true — otherwise the "
                 "map page speaks\n                with the BROWSER's voice "
                 "and Piper is never heard.\n                Set it back to "
                 "false if you ask from your phone a lot.")
    else:
        aloud = ""

    ENV.write_text(text, encoding="utf-8")
    print("  Settings:     TTS_BACKEND=piper, PIPER_BIN and PIPER_MODEL "
          "written\n                (old .env kept as .env.bak5)")
    if aloud:
        print(aloud)

    print("\n  Done — but CLOSE VESPER AND START HER AGAIN.")
    print("  Refreshing the browser only reloads the page; the settings are")
    print("  read once when the black window starts.")
    print("\n  To go back: set TTS_BACKEND=windows in .env.\n")
    return 0


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Start Vesper and open its map.")
    p.add_argument("--setup", action="store_true",
                   help="first run: write .env and make a token")
    p.add_argument("--tuneup", action="store_true",
                   help="refresh the map and put a proper model first")
    p.add_argument("--doctor", action="store_true",
                   help="print what Vesper can reach, and test each provider")
    p.add_argument("--piper", action="store_true",
                   help="install the Piper voice and wire it into .env")
    p.add_argument("--no-browser", action="store_true",
                   help="start, but do not open the map")
    p.add_argument("--url", action="store_true",
                   help="just print the map address and exit")
    args = p.parse_args(argv)

    if args.setup:
        setup_logging(CONFIG.log_level)
        return setup()

    if args.tuneup:
        setup_logging(CONFIG.log_level)
        return tuneup()

    if args.doctor:
        setup_logging(CONFIG.log_level)
        return doctor()

    if args.piper:
        setup_logging(CONFIG.log_level)
        return piper_setup()

    from .config import Config

    if args.url:
        # Read-only: printing an address must never create a file. This is
        # what people run to find out where the map is, sometimes from a
        # different folder, and it should leave no trace.
        print(map_url(Config()))
        return 0

    # A first double-click of the launcher, with no setup run: do it rather
    # than complaining about it.
    if not ENV.exists():
        created, note = ensure_env()
        print(f"  {note}")
        reload_env(ENV)

    cfg = Config()
    setup_logging(cfg.log_level)

    if not cfg.server_token or len(cfg.server_token) < 16:
        print("\nNo SERVER_TOKEN, so the map cannot be served.")
        print("Run:  python -m vesper.launch --setup\n")
        return 1

    if not args.no_browser:
        open_map_when_ready(cfg)

    # Hand over to the assistant proper, with the bridge on — that is what
    # serves the page the browser is about to ask for.
    from . import main as vesper_main
    return vesper_main.main(["--serve"])


if __name__ == "__main__":
    sys.exit(main())
