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
  const mk = Object.values(store.nodes).find(n => n.t === 'My trading');
  return briefRequest(mk.id);
});

// The opening view has to frame the whole map. The fit used to oscillate
// rather than converge and could leave a third of it off the left edge.
out.frame = await p.evaluate(() => {
  let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9, off = 0;
  for (const k in P) {
    const q = project(P[k]);
    if (q.d <= 40) continue;
    minX = Math.min(minX, q.x); maxX = Math.max(maxX, q.x);
    minY = Math.min(minY, q.y); maxY = Math.max(maxY, q.y);
    if (q.x < 0 || q.x > innerWidth || q.y < 0 || q.y > innerHeight) off++;
  }
  return { off, dx: Math.abs((minX + maxX) / 2 - innerWidth / 2),
           dy: Math.abs((minY + maxY) / 2 - innerHeight / 2) };
});

// A main branch must look like one from every angle.
out.rank = await p.evaluate(() => {
  const rec = [];
  const real = drawLabel;
  drawLabel = function (L, taken) {
    const before = taken.length;
    real(L, taken);
    if (taken.length > before) rec.push({ dep: L.dep, size: L.size, f: L.f });
  };
  let minLimb = 1e9, dwarfed = 0, faded = 0, seen = 0;
  for (let y = 0; y < 6.28; y += 0.5) {
    window.yaw = y; window.glide = null;
    rec.length = 0;
    draw(performance.now());
    const limbs = rec.filter(r => r.dep === 1);
    const deep = rec.filter(r => r.dep >= 2);
    seen += limbs.length;
    for (const L of limbs) {
      minLimb = Math.min(minLimb, L.size);
      if (L.f < 0.6) faded++;
      for (const d of deep) if (d.size > L.size * 1.15) dwarfed++;
    }
  }
  drawLabel = real;
  return { minLimb: minLimb === 1e9 ? 0 : minLimb, dwarfed, faded, seen };
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
        want = ["Trendkept", "Health", "My trading", "News & weather",
                "Personal"]

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
        # The heading wording is allowed to change; what must survive is
        # that the subtree reaches the trading branch AND still carries the
        # rule that Vesper does not predict.
        for needle in ("My trading", "Watchlist", "No predictions"):
            if needle not in brief:
                bad += 1
                print(f"  FAIL: brief prompt is missing {needle!r}")
        if "no predictions" not in brief:
            bad += 1
            print("  FAIL: brief prompt dropped the descriptive-only rule")
        print(f"brief prompt: {len(brief)} chars, carries the subtree "
              "and the no-predictions rule")

        fr = out["frame"]
        framed = fr["off"] == 0 and fr["dx"] < 110 and fr["dy"] < 80
        if not framed:
            bad += 1
        print(f"opening view: {fr['off']} off-screen, centre off by "
              f"{fr['dx']:.0f}x{fr['dy']:.0f}px"
              + ("" if framed else "  <- NOT FRAMED"))

        rk = out["rank"]
        if rk["seen"] == 0:
            bad += 1
            print("  FAIL: no limb labels drawn at all")
        if rk["minLimb"] < 16.9:
            bad += 1
            print(f"  FAIL: a limb shrank to {rk['minLimb']:.1f}px")
        if rk["dwarfed"] or rk["faded"]:
            bad += 1
            print(f"  FAIL: {rk['dwarfed']} dwarfed, {rk['faded']} faded")
        print(f"limb rank: {rk['seen']} limb labels across the turn, "
              f"smallest {rk['minLimb']:.1f}px, "
              f"{rk['dwarfed']} dwarfed, {rk['faded']} faded")

        if out["errors"]:
            bad += len(out["errors"])
            print("  " + "\n  ".join(out["errors"]))

        print("\nFAIL" if bad else "\nPASS")
        return 1 if bad else 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
