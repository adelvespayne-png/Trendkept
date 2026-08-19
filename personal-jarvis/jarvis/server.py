"""The phone bridge — a small HTTP endpoint on the laptop.

    python -m jarvis.server --new-token     # make a token for .env
    python -m jarvis.main --serve           # assistant + endpoint together

Your phone can't run this assistant (iOS won't host a background Python
process with a microphone). So the phone becomes a microphone and a speaker,
and the laptop stays the brain: a Shortcut posts what you said to `/ask` and
speaks back whatever comes out.

Deliberately stdlib-only — an always-on daemon on your home network is the
last place to add a web framework for one route.

Three endpoints:
  GET  /health   is the laptop awake? (the Shortcut probes this first)
  POST /ask      {"text": "..."} -> {"reply": "..."}
  GET  /         a human-readable page, for checking it works from a browser

**Every one of them requires the token.** This endpoint spends your API
credit, so it does not open without one — see `_check_token`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import socket
import sys
import threading
import urllib.parse
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from .config import CONFIG, Config, setup_logging

LOG = logging.getLogger("jarvis.server")

MAX_BODY = 16 * 1024        # a spoken sentence; anything bigger is not us
MAX_MAP = 4 * 1024 * 1024   # a whole map coming back from the browser


def _map_page(token: str):
    """The 3D map, with this session's token baked in so it can call back."""
    path = Path(__file__).resolve().parent / "web" / "map.html"
    try:
        return path.read_text(encoding="utf-8").replace("__TOKEN__", token)
    except OSError as exc:
        LOG.error("could not read the map page: %s", exc)
        return None


class AskServer:
    """Wraps the assistant so an HTTP thread can reach the asyncio brain."""

    def __init__(self, jarvis: Any, loop: asyncio.AbstractEventLoop,
                 cfg: Config = CONFIG) -> None:
        self.jarvis = jarvis
        self.loop = loop
        self.cfg = cfg
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        # One turn at a time, exactly as with the local path — the phone must
        # not be able to start a second turn while the first is still going.
        self._turn = threading.Lock()

    # -- the work ---------------------------------------------------------

    def ask(self, text: str) -> str:
        """Run one turn on the asyncio loop and wait for the answer."""
        if not self._turn.acquire(timeout=1.0):
            return "I'm in the middle of something. Ask me again in a moment."
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.jarvis.brain.respond(user_text=text, channel="voice"),
                self.loop)
            reply = future.result(timeout=120)
        except Exception as exc:
            LOG.exception("remote turn failed")
            return f"Something went wrong here: {type(exc).__name__}."
        finally:
            self._turn.release()

        if reply and self.cfg.server_speak_aloud:
            # Off by default: if you're asking from the pub, the laptop
            # announcing the answer to an empty room is not useful.
            threading.Thread(target=self.jarvis.speaker.say, args=(reply,),
                             daemon=True).start()
        return reply or "I had nothing to say to that."

    # -- lifecycle --------------------------------------------------------

    def start(self) -> bool:
        if not self.cfg.server_enabled:
            LOG.debug("phone bridge disabled by config")
            return False
        token = self.cfg.server_token
        if not token or len(token) < 16:
            LOG.error("SERVER_TOKEN is missing or too short; the phone bridge "
                      "will not start. Run: python -m jarvis.server --new-token")
            return False

        handler = _make_handler(self)
        try:
            self._httpd = ThreadingHTTPServer(
                (self.cfg.server_host, self.cfg.server_port), handler)
        except OSError as exc:
            LOG.error("could not bind %s:%s — %s",
                      self.cfg.server_host, self.cfg.server_port, exc)
            return False

        self._thread = threading.Thread(target=self._httpd.serve_forever,
                                        name="bridge", daemon=True)
        self._thread.start()
        LOG.info("bridge on http://%s:%s", lan_ip(), self.cfg.server_port)
        return True

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=3.0)


# --------------------------------------------------------------------------


def _make_handler(bridge: AskServer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "jarvis"

        # -- plumbing ----------------------------------------------------

        def log_message(self, fmt: str, *args) -> None:
            LOG.debug("%s - %s", self.address_string(), fmt % args)

        def _send(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # The phone walked out of wifi range, or Shortcuts gave up
                # waiting. Normal on a home network; not worth a traceback.
                LOG.debug("client disconnected before the reply was sent")

        def _check_token(self) -> bool:
            """Bearer token, compared in constant time.

            A plain `==` on a secret leaks its length and prefix to anyone
            who can time the responses. `compare_digest` costs nothing here
            and removes the question entirely.
            """
            supplied = self.headers.get("Authorization", "")
            if supplied.lower().startswith("bearer "):
                supplied = supplied[7:]
            if not supplied:
                # A browser opening /map can't set a header, so the token may
                # ride in the query string instead.
                q = urllib.parse.urlparse(self.path).query
                supplied = urllib.parse.parse_qs(q).get("t", [""])[0]
            if secrets.compare_digest(supplied.strip(), bridge.cfg.server_token):
                return True
            LOG.warning("rejected a request from %s (bad token)",
                        self.address_string())
            self._send(401, {"error": "bad or missing token"})
            return False

        # -- routes ------------------------------------------------------

        # A crash in a route would otherwise close the socket with no reply,
        # and Shortcuts reports that as an unhelpful "connection error".
        def do_GET(self) -> None:
            try:
                self._get()
            except Exception:
                LOG.exception("GET %s failed", self.path)
                self._send(500, {"error": "something broke on the laptop"})

        def do_POST(self) -> None:
            try:
                self._post()
            except Exception:
                LOG.exception("POST %s failed", self.path)
                self._send(500, {"error": "something broke on the laptop"})

        def _get(self) -> None:
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path == "/health":
                if not self._check_token():
                    return
                self._send(200, {"ok": True, "jarvis": "awake"})
            elif path == "/map":
                if not self._check_token():
                    return
                page = _map_page(bridge.cfg.server_token)
                if page is None:
                    self._send(500, {"error": "map page missing"})
                    return
                body = page.encode("utf-8")
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    LOG.debug("client left before the map was sent")
            elif path == "/map/data":
                if not self._check_token():
                    return
                store = getattr(bridge.jarvis, "map", None)
                if store is None:
                    self._send(404, {"error": "no map in this session"})
                    return
                self._send(200, store.data)
            elif path == "/":
                if not self._check_token():
                    return
                self._send(200, {
                    "jarvis": "awake",
                    "world": bridge.jarvis.state.snapshot().describe(),
                    "ask": "POST /ask with {\"text\": \"...\"}",
                })
            else:
                self._send(404, {"error": "no such endpoint"})

        def _post(self) -> None:
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path not in ("/ask", "/map/data"):
                self._send(404, {"error": "no such endpoint"})
                return
            if not self._check_token():
                return

            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                length = 0
            cap = MAX_MAP if path == "/map/data" else MAX_BODY
            if length <= 0 or length > cap:
                self._send(400, {"error": "body too large"})
                return

            try:
                payload = json.loads(self.rfile.read(length))
            except ValueError:
                self._send(400, {"error": "body was not valid JSON"})
                return
            # `"raw"` and `[1,2]` are both valid JSON but neither has a
            # `.get`, so check the shape rather than trusting the parse.
            if not isinstance(payload, dict):
                self._send(400, {"error": "expected a JSON object with a 'text' field"})
                return
            if path == "/map/data":
                store = getattr(bridge.jarvis, "map", None)
                if store is None:
                    self._send(404, {"error": "no map in this session"})
                elif store.replace(payload):
                    self._send(200, {"ok": True})
                else:
                    self._send(400, {"error": "that isn't a map"})
                return

            text = str(payload.get("text", "")).strip()
            extra = str(payload.get("context", "")).strip()
            if not text:
                self._send(400, {"error": "no text"})
                return

            LOG.info("asked: %s", text)
            reply = bridge.ask(text if not extra else text + "\n\n[" + extra + "]")
            LOG.info("replied: %s", reply)
            self._send(200, {"reply": reply, "source": "laptop"})

    return Handler


def lan_ip() -> str:
    """This machine's address on the home network.

    Opens a UDP socket to a public address purely to see which local
    interface the OS picks — nothing is actually sent.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Phone bridge helper.")
    p.add_argument("--new-token", action="store_true",
                   help="print a fresh token to paste into .env")
    args = p.parse_args(argv)
    setup_logging(CONFIG.log_level)

    if args.new_token:
        print("\nPaste this line into your .env file:\n")
        print(f"SERVER_TOKEN={secrets.token_urlsafe(32)}")
        print("\nAlso set SERVER_ENABLED=true, then start Jarvis with:")
        print("  python -m jarvis.main --serve\n")
        return 0

    print("The bridge runs as part of the assistant, not on its own:")
    print("  python -m jarvis.main --serve")
    print("\nTo create a token:  python -m jarvis.server --new-token")
    print(f"\nThis laptop's address on your network: {lan_ip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
