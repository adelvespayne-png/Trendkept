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


def _mask(tok: str) -> str:
    if not tok:
        return "(not set)"
    return f"{tok[:6]}...{tok[-4:]}  ({len(tok)} chars)" if len(tok) > 12 \
        else "(set, suspiciously short)"


def _probe(base: str, token: str, model: str, timeout: float = 30.0):
    """Send the smallest real request there is. Returns (ok, one-line why)."""
    import json
    import urllib.error
    import urllib.request

    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 16}).encode()
    req = urllib.request.Request(
        base, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
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
    for label, name in (("Google", "GOOGLE_API_KEY"),
                        ("GitHub", "GITHUB_TOKEN"),
                        ("Anthropic", "ANTHROPIC_API_KEY")):
        key = _get(text, name, "")
        if not key and name == "GOOGLE_API_KEY":
            key = _get(text, "FALLBACK_TOKEN", "")
        print(f"    {label:<10} {_mask(key)}")

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
        model = prov["models"][0] if prov["models"] else None
        if not model:
            print(f"    {prov['label']:<20} no models to try")
            continue
        ok, why = _probe(prov["base"], prov["token"], model)
        any_ok |= ok
        print(f"    {prov['label']:<20} {'OK  ' if ok else 'FAIL'}  {why}")

    print()
    if any_ok:
        print("  At least one provider answered, so Vesper can think.")
    else:
        print("  Nothing answered. Vesper will speak, and will tell you why,")
        print("  but cannot reason until one of the above works.")
    print()
    return 0 if any_ok else 1


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Start Vesper and open its map.")
    p.add_argument("--setup", action="store_true",
                   help="first run: write .env and make a token")
    p.add_argument("--tuneup", action="store_true",
                   help="refresh the map and put a proper model first")
    p.add_argument("--doctor", action="store_true",
                   help="print what Vesper can reach, and test each provider")
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
