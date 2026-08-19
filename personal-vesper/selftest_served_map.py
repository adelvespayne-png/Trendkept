"""The served map, end to end: real bridge, real browser, real taps.

`selftest_map.py` checks the browser-only page. This checks the one the
laptop serves — which is the one a real install uses, and which pulls its
nodes over HTTP rather than seeding them locally. A map that renders fine
from disk can still come up empty when served, so this asks the actual
question: start the bridge, open /map in Chromium, and see what arrives.

Skips cleanly (exit 0) if Playwright or the bundled Chromium is missing —
this is the only suite that needs a browser.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CHROMIUM = "/opt/pw-browsers/chromium"
PORT = 8791
TOKEN = "selftest-token-not-a-real-secret-0123456789"

DRIVER = r"""
import { chromium } from 'playwright';
const [url, exe] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: exe });
const out = { errors: [] };
const p = await b.newPage({ viewport: { width: 1280, height: 800 } });
p.on('pageerror', e => out.errors.push('PAGEERROR: ' + e.message));
p.on('console', m => { if (m.type() === 'error') out.errors.push('CONSOLE: ' + m.text()); });
await p.goto(url);
await p.waitForTimeout(2000);

out.nodes = await p.evaluate(() => Object.keys(store.nodes).length);
out.limbs = await p.evaluate(() => kids('root').map(n => n.t));
out.offline = await p.evaluate(() => document.body.classList.contains('offline'));

// Tap each limb dead-centre; you should select that limb.
out.taps = await p.evaluate(() => {
  const r = [];
  for (const n of kids('root')) {
    const q = project(P[n.id]);
    if (q.d <= 40) continue;
    const got = hit(q.x, q.y);
    r.push([n.t, got ? store.nodes[got].t : null]);
  }
  return r;
});

// The brief prompt must name the branch and carry its subtree.
out.brief = await p.evaluate(() => {
  const mk = Object.values(store.nodes).find(n => n.t === 'Markets');
  return briefRequest(mk.id);
});

await b.close();
console.log('@@' + JSON.stringify(out));
"""


def main() -> int:
    node = subprocess.run(["node", "-e", "require.resolve('playwright')"],
                          cwd=HERE.parent, capture_output=True)
    if node.returncode != 0 or not Path(CHROMIUM).exists():
        print("SKIP: playwright/chromium not available here")
        return 0

    from vesper.config import Config
    from vesper.mapstore import MapStore
    from vesper.server import AskServer

    tmp = Path(tempfile.mkdtemp())
    cfg = Config()
    cfg.server_enabled = True
    cfg.server_token = TOKEN
    cfg.server_host = "127.0.0.1"
    cfg.server_port = PORT
    cfg.server_speak_aloud = False

    class FakeVesper:
        def __init__(self) -> None:
            self.map = MapStore(tmp / "map.json")

    async def run() -> int:
        loop = asyncio.get_running_loop()
        bridge = AskServer(FakeVesper(), loop, cfg)
        if not bridge.start():
            print("FAIL: bridge would not start")
            return 1
        # The driver has to sit beside node_modules: an ESM import resolves
        # from the FILE's directory, not the working directory, so a driver
        # written to /tmp cannot find playwright however we invoke node.
        drv = HERE.parent / ".selftest-drive.mjs"
        try:
            drv.write_text(DRIVER, encoding="utf-8")
            url = f"http://127.0.0.1:{PORT}/map?t={TOKEN}"
            proc = await asyncio.to_thread(
                subprocess.run, ["node", str(drv), url, CHROMIUM],
                capture_output=True, text=True, timeout=120, cwd=str(HERE.parent))
        finally:
            bridge.stop()
            drv.unlink(missing_ok=True)

        line = next((l for l in proc.stdout.splitlines() if l.startswith("@@")), "")
        if not line:
            print("FAIL: the browser said nothing\n", proc.stdout, proc.stderr)
            return 1
        out = json.loads(line[2:])

        bad = 0
        want = ["Trendkept", "Health", "Markets", "News & weather", "Personal"]

        print(f"served {out['nodes']} nodes")
        if out["nodes"] < 90:
            bad += 1
            print("  FAIL: the served map came up nearly empty")

        print(f"limbs: {', '.join(out['limbs'])}")
        if out["limbs"] != want:
            bad += 1
            print(f"  FAIL: expected {want}")

        if out["offline"]:
            bad += 1
            print("  FAIL: the page thinks the laptop is offline")

        wrong = [f"{a}→{b}" for a, b in out["taps"] if a != b]
        print(f"taps: {len(out['taps'])} limbs, "
              + ("WRONG: " + ", ".join(wrong) if wrong else "each selects itself"))
        bad += len(wrong)

        brief = out["brief"]
        for needle in ("Markets", "Watchlist", "Never: predictions"):
            if needle not in brief:
                bad += 1
                print(f"  FAIL: brief prompt is missing {needle!r}")
        if "no predictions" not in brief:
            bad += 1
            print("  FAIL: brief prompt dropped the descriptive-only rule")
        print(f"brief prompt: {len(brief)} chars, carries the subtree "
              "and the no-predictions rule")

        if out["errors"]:
            bad += len(out["errors"])
            print("  " + "\n  ".join(out["errors"]))

        print("\nFAIL" if bad else "\nPASS")
        return 1 if bad else 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
