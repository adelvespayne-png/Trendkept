"""The starting map exists twice — keep the two copies identical.

`vesper/web/map.html` has a JS `seed()` for when it is opened straight from
disk; `vesper/mapstore.py` has a Python `SEED` for what the laptop serves.
The served one wins on a real install, so if only the browser copy gets a new
limb, a fresh install quietly comes up missing it. That is exactly what
happened when Markets and News & weather were added.

This parses the JS and compares it to the Python, so the next time they drift
a test says so instead of a user finding out.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.mapstore import SEED  # noqa: E402

MAP_HTML = HERE / "vesper" / "web" / "map.html"

ADD = re.compile(
    r'add\(\s*"([^"]*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,\s*(null|"[^"]*")'
    r'(?:\s*,\s*(true|false))?\s*\)')
LINKS = re.compile(r'links\.push\(([^;]*)\);', re.S)
PAIR = re.compile(r'\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]')


def parse_js_seed(text: str) -> dict:
    body = text.split("function seed()", 1)[1].split("\n}", 1)[0]
    nodes = {}
    for nid, title, parent, done in ADD.findall(body):
        nodes[nid] = {
            "id": nid,
            "t": title.replace('\\"', '"').replace("\\\\", "\\"),
            "p": None if parent == "null" else parent.strip('"'),
            "done": done == "true",
        }
    links = []
    m = LINKS.search(body)
    if m:
        links = [[a, b] for a, b in PAIR.findall(m.group(1))]
    return {"nodes": nodes, "links": links}


def main() -> int:
    js = parse_js_seed(MAP_HTML.read_text(encoding="utf-8"))
    bad = 0

    jn, pn = js["nodes"], SEED["nodes"]
    print(f"browser seed: {len(jn)} nodes, {len(js['links'])} links")
    print(f"python  seed: {len(pn)} nodes, {len(SEED['links'])} links")

    only_js = sorted(set(jn) - set(pn))
    only_py = sorted(set(pn) - set(jn))
    if only_js:
        bad += 1
        print(f"  MISSING from mapstore.py ({len(only_js)}): "
              + ", ".join(f"{k}={jn[k]['t']!r}" for k in only_js[:8])
              + (" ..." if len(only_js) > 8 else ""))
    if only_py:
        bad += 1
        print(f"  EXTRA in mapstore.py ({len(only_py)}): " + ", ".join(only_py[:8]))

    for k in sorted(set(jn) & set(pn)):
        if jn[k] != pn[k]:
            bad += 1
            print(f"  DIFFERS {k}: browser={jn[k]} python={pn[k]}")

    a = sorted(tuple(x) for x in js["links"])
    b = sorted(tuple(x) for x in SEED["links"])
    if a != b:
        bad += 1
        print(f"  LINKS differ: only-browser={sorted(set(a)-set(b))} "
              f"only-python={sorted(set(b)-set(a))}")

    # The five limbs the owner asked for, by name, in order.
    want = ["Trendkept", "Health", "My trading", "News & weather",
            "Personal"]
    for name, seed in (("browser", jn), ("python", pn)):
        limbs = [n["t"] for n in seed.values() if n["p"] == "root"]
        if limbs != want:
            bad += 1
            print(f"  {name} limbs are {limbs}, expected {want}")
        else:
            print(f"  {name} limbs: {', '.join(limbs)}")

    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
