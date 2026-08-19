"""Test harness — drive the world state by hand and watch triggers fire.

    python -m jarvis.harness            # scripted scenario, no hardware
    python -m jarvis.harness --repl     # type state changes yourself

This exists so the situational-awareness logic can be developed and proved
without a camera, a microphone, or an API key. Everything it exercises is
the same code the live assistant runs.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from typing import List

from .config import setup_logging
from .core.triggers import TriggerEngine
from .core.world_state import Change, WorldState


# Fields the world state holds as lists, so the REPL can accept a bare word.
_LIST_FIELDS = ("people", "objects")


def _show(label: str, state: WorldState, changes: List[Change],
          engine: TriggerEngine, now: float) -> bool:
    snap = state.snapshot()
    print(f"\n── {label}")
    if changes:
        for c in changes:
            print(f"   changed  {c.key}: {c.old!r} -> {c.new!r}")
    else:
        print("   (no change)")
    print(f"   world    {snap.describe()}")
    fired = engine.evaluate(snap, changes, now=now)
    if fired:
        print(f"   TRIGGER  {fired.rule.name}")
        print(f"            {fired.why}")
        return True
    return False


def scenario() -> int:
    """A morning-to-night walk through the rules."""
    state = WorldState()
    engine = TriggerEngine(global_cooldown=0.0)  # no throttle while demoing
    t = time.time()
    fired = 0

    steps = [
        ("Boot: vision comes up, empty room",
         dict(vision_active=True, people=[], objects=[], time_of_day="morning")),
        ("Adam walks in",
         dict(people=["adam"], objects=["person", "chair"])),
        ("Same frame again (detector reordered the labels)",
         dict(people=["adam"], objects=["chair", "person"])),
        ("Adam leaves",
         dict(people=[])),
        ("Evening; stove switched on",
         dict(time_of_day="evening", devices={"kitchen_stove": "on"},
              last_motion_at=t)),
        ("Twenty-five minutes of no motion",
         dict(last_motion_at=t - 25 * 60)),
        ("Night falls, unfamiliar face at the camera",
         dict(time_of_day="night", people=["unknown"])),
    ]

    for label, fields in steps:
        changes = state.update(**fields)
        if _show(label, state, changes, engine, now=t):
            fired += 1
        t += 1

    print(f"\n{fired} trigger(s) fired across {len(steps)} state changes.")
    print("Nothing above called the model — this is all local rule evaluation.")
    return 0


def repl() -> int:
    state = WorldState()
    engine = TriggerEngine(global_cooldown=0.0)
    print("Type field=value pairs, e.g.:")
    print("   people=unknown              (bare words become one-item lists)")
    print("   people=none                 (empties it)")
    print("   devices.kitchen_stove=on    (dotted keys set one device)")
    print("   time_of_day=night")
    print("   last_motion_at=-1500        (relative seconds are converted)")
    print("JSON works too: people=[\"adam\",\"unknown\"]")
    print("'state' prints the world, 'quit' exits.\n")

    while True:
        try:
            line = input("state> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("quit", "exit"):
            return 0
        if line == "state":
            print(json.dumps(state.snapshot().data, indent=1, default=str))
            continue

        fields = {}
        ok = True
        # posix=False keeps the quote characters, so a JSON value survives
        # the split intact — posix mode eats them and ["a","b"] arrives as
        # the meaningless [a,b].
        for token in shlex.split(line, posix=False):
            if "=" not in token:
                print(f"  ? expected key=value, got {token!r}")
                ok = False
                break
            key, _, raw = token.partition("=")
            try:
                value = json.loads(raw)
            except ValueError:
                value = raw.strip('"').strip("'")

            if key == "last_motion_at" and isinstance(value, (int, float)) and value <= 0:
                value = time.time() + value      # "-1500" = 25 minutes ago

            # `devices.kitchen_stove=on` sets one device without retyping the
            # whole dict — merged over whatever is already staged or stored.
            if "." in key:
                key, _, sub = key.partition(".")
                current = dict(fields.get(key) or state.get(key) or {})
                current[sub] = value
                value = current
            elif key in _LIST_FIELDS and isinstance(value, str):
                # A bare word is one item, not seven letters.
                value = [] if value.lower() in ("none", "empty", "") else [value]

            fields[key] = value
        if not ok or not fields:
            continue

        _show("manual update", state, state.update(**fields), engine, time.time())


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Drive the world state by hand.")
    p.add_argument("--repl", action="store_true", help="interactive mode")
    args = p.parse_args(argv)
    setup_logging("WARNING")
    return repl() if args.repl else scenario()


if __name__ == "__main__":
    sys.exit(main())
