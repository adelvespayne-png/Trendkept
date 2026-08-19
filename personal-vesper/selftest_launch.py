"""The double-click path.

The launcher is the first thing a new install runs and the last thing anyone
would think to test, which is a bad combination. Two failures matter most:

  * clobbering an existing `.env` — someone's keys and tuned thresholds live
    there, and a launcher that overwrote it on a whim would be unforgivable;
  * opening the browser before the bridge is listening, which shows a
    connection-refused page and reads as "it doesn't work".
"""

from __future__ import annotations

import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper import launch                                   # noqa: E402
from vesper.config import Config                            # noqa: E402

bad = 0


def check(label, got, want) -> None:
    global bad
    ok = got == want
    if not ok:
        bad += 1
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         got  {got!r}\n         want {want!r}")


EXAMPLE = """# comments must survive
ANTHROPIC_API_KEY=
SERVER_ENABLED=false
SERVER_TOKEN=
SERVER_PORT=8765
WAKE_THRESHOLD=0.5
"""

print("\n1. a first run writes a usable .env")
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    ex = root / ".env.example"
    env = root / ".env"
    ex.write_text(EXAMPLE, encoding="utf-8")

    created, note = launch.ensure_env(env, ex)
    check("said it created one", created, True)
    check("the file is there", env.exists(), True)
    text = env.read_text(encoding="utf-8")
    check("bridge switched on", "SERVER_ENABLED=true" in text, True)
    check("comments kept", "# comments must survive" in text, True)
    check("other settings kept", "WAKE_THRESHOLD=0.5" in text, True)

    token = [l for l in text.splitlines() if l.startswith("SERVER_TOKEN=")][0]
    token = token.split("=", 1)[1]
    check("a real token, not a placeholder", len(token) >= 32, True)
    print(f"         token is {len(token)} chars")

print("\n2. a second run does NOT touch it — this is the one that matters")
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    ex = root / ".env.example"
    env = root / ".env"
    ex.write_text(EXAMPLE, encoding="utf-8")
    mine = "ANTHROPIC_API_KEY=sk-my-real-key\nSERVER_TOKEN=the-one-my-phone-has\n"
    env.write_text(mine, encoding="utf-8")

    created, note = launch.ensure_env(env, ex)
    check("did not claim to create", created, False)
    check("my file is byte-for-byte intact", env.read_text(encoding="utf-8"), mine)
    print(f"         said: {note}")

print("\n3. two installs do not get the same token")
check("tokens differ", launch.new_token() == launch.new_token(), False)

print("\n4. the map address is reachable from this machine")
cfg = Config()
cfg.server_host = "0.0.0.0"          # listens everywhere...
cfg.server_port = 8765
cfg.server_token = "abc123"
url = launch.map_url(cfg)
# ...but 0.0.0.0 is not somewhere a browser can GO. It has to be told 127.0.0.1.
check("no 0.0.0.0 in the browser URL", "0.0.0.0" in url, False)
check("points at this machine", url.startswith("http://127.0.0.1:8765/map"), True)
check("carries the token", "t=abc123" in url, True)
print(f"         {url}")

cfg.server_host = "192.168.1.50"
check("a real host is left alone",
      launch.map_url(cfg).startswith("http://192.168.1.50:8765/"), True)

print("\n5. it waits for the bridge instead of racing it")
port = 8797
t0 = time.monotonic()
check("nothing listening -> gives up", launch.wait_for_bridge("127.0.0.1", port, 1.0), False)
waited = time.monotonic() - t0
check("and it actually waited", 0.8 < waited < 2.5, True)
print(f"         waited {waited:.1f}s before giving up")

# Now start something late, as a slow model load would.
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def listen_late() -> None:
    time.sleep(1.2)
    srv.bind(("127.0.0.1", port))
    srv.listen(5)


threading.Thread(target=listen_late, daemon=True).start()
t0 = time.monotonic()
got = launch.wait_for_bridge("127.0.0.1", port, 8.0)
took = time.monotonic() - t0
check("a slow start is waited for, not missed", got, True)
check("and it returns as soon as it is up", took < 3.0, True)
print(f"         connected after {took:.1f}s")
srv.close()

print("\n6. --url prints the address, creates nothing, starts nothing")
import contextlib
import io as _io
with tempfile.TemporaryDirectory() as d:
    # Point the launcher at an empty folder. Printing an address must not
    # write a .env there — the first version of this did, which also meant
    # running the test dropped one into the package directory.
    keep_env, keep_ex = launch.ENV, launch.EXAMPLE
    launch.ENV = Path(d) / ".env"
    launch.EXAMPLE = Path(d) / ".env.example"
    try:
        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = launch.main(["--url"])
        out = buf.getvalue().strip()
    finally:
        launch.ENV, launch.EXAMPLE = keep_env, keep_ex
    check("exit 0", rc, 0)
    check("printed one line", out.count("\n"), 0)
    check("and it is a URL", out.startswith("http://"), True)
    check("wrote nothing", (Path(d) / ".env").exists(), False)
    print(f"         {out}")

print("\n7. a token generated on a first run is visible immediately")
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    (root / ".env.example").write_text(EXAMPLE, encoding="utf-8")
    env = root / ".env"
    launch.ensure_env(env, root / ".env.example")
    # config caches .env at import; without reload_env a brand-new install
    # generates a token and then reports it has none.
    import os
    for k in ("SERVER_TOKEN", "SERVER_ENABLED"):
        os.environ.pop(k, None)
    from vesper.config import reload_env as _reload
    _reload(env)
    cfg = Config()
    check("token is set", len(cfg.server_token) >= 32, True)
    check("bridge is on", cfg.server_enabled, True)
    check("map URL carries it", cfg.server_token in launch.map_url(cfg), True)

print("\nFAIL" if bad else "\nPASS")
sys.exit(1 if bad else 0)
