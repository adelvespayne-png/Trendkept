"""Spotify — what is playing, and telling it what to do.

    python -m vesper.tools.spotify --login     # once: authorise in a browser
    python -m vesper.tools.spotify             # what is playing right now

Two things worth knowing before you set this up:

  * **Playback control needs Spotify Premium.** That is Spotify's rule, not
    ours: the `/me/player/*` endpoints return 403 for free accounts. On a
    free account this still tells you what is playing and can search — it
    just cannot press play. Better to know now than to debug it later.
  * **It authorises with PKCE**, so there is no client secret to keep. You
    make an app in Spotify's dashboard, take the Client ID, and that is all
    that ever touches this machine. The tokens live in a git-ignored file
    beside the assistant and are refreshed here, never sent anywhere except
    back to Spotify.

Deliberately stdlib-only, like the rest of the plumbing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import CONFIG, Config, setup_logging

LOG = logging.getLogger("vesper.spotify")

AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"

#: Only what the assistant actually uses. Asking for less means a shorter
#: consent screen and less to regret if the token file ever leaks.
SCOPES = ("user-read-playback-state user-modify-playback-state "
          "user-read-currently-playing")


class SpotifyError(RuntimeError):
    """Something Spotify said no to, phrased for a person."""


class Spotify:
    def __init__(self, cfg: Config = CONFIG) -> None:
        self.cfg = cfg
        self.path = Path(cfg.spotify_token_path)
        self.client_id = (cfg.spotify_client_id or "").strip()
        self._tokens: Dict[str, Any] = self._load()

    @property
    def available(self) -> bool:
        """Configured AND authorised. Both are needed to be useful."""
        return bool(self.client_id and self._tokens.get("refresh_token"))

    @property
    def configured(self) -> bool:
        return bool(self.client_id)

    # -- tokens on disk ----------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError) as exc:
            LOG.warning("could not read the Spotify token file (%s)", exc)
            return {}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._tokens, indent=1), encoding="utf-8")
            # Readable only by this user where the OS supports it. These are
            # live credentials to an account, not preferences.
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            tmp.replace(self.path)
        except OSError as exc:
            LOG.error("could not save Spotify tokens: %s", exc)

    def forget(self) -> None:
        """Sign out: drop the tokens entirely."""
        self._tokens = {}
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            LOG.error("could not remove the token file: %s", exc)

    # -- authorising -------------------------------------------------------

    def login(self, timeout: float = 180.0) -> bool:
        """Open a browser, take the redirect, swap the code for tokens."""
        if not self.client_id:
            LOG.error("SPOTIFY_CLIENT_ID is not set")
            return False

        verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        state = secrets.token_urlsafe(16)
        redirect = f"http://127.0.0.1:{self.cfg.spotify_auth_port}/callback"

        got: Dict[str, str] = {}
        done = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a) -> None:
                pass

            def do_GET(self) -> None:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                got.update({k: v[0] for k, v in q.items()})
                ok = got.get("state") == state and "code" in got
                body = (b"<h2>Vesper is connected to Spotify.</h2>"
                        b"<p>You can close this tab.</p>" if ok else
                        b"<h2>That did not work.</h2><p>Check the terminal.</p>")
                self.send_response(200 if ok else 400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                done.set()

        try:
            httpd = HTTPServer(("127.0.0.1", self.cfg.spotify_auth_port), Handler)
        except OSError as exc:
            LOG.error("could not listen on port %s (%s). Close whatever is "
                      "using it, or set SPOTIFY_AUTH_PORT to something else.",
                      self.cfg.spotify_auth_port, exc)
            return False

        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = AUTH + "?" + urllib.parse.urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect,
            "scope": SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
        })
        print("\nA browser should open. If it does not, go here yourself:\n")
        print("  " + url + "\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass

        ok = done.wait(timeout)
        httpd.shutdown()
        httpd.server_close()

        if not ok:
            LOG.error("timed out waiting for Spotify to redirect back")
            return False
        if got.get("state") != state:
            # Either something went wrong, or something else answered. Either
            # way this code is not one we asked for.
            LOG.error("the redirect did not match the request; not continuing")
            return False
        if "code" not in got:
            LOG.error("Spotify said: %s", got.get("error", "no code returned"))
            return False

        return self._exchange({
            "grant_type": "authorization_code",
            "code": got["code"],
            "redirect_uri": redirect,
            "client_id": self.client_id,
            "code_verifier": verifier,
        })

    def _exchange(self, form: Dict[str, str]) -> bool:
        body = urllib.parse.urlencode(form).encode()
        req = urllib.request.Request(
            TOKEN, data=body, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as exc:
            LOG.error("Spotify refused the token request: %s %s",
                      exc.code, exc.read()[:200])
            return False
        except OSError as exc:
            LOG.error("could not reach Spotify: %s", exc)
            return False

        # A refresh response may omit refresh_token, which means keep the one
        # we have. Overwriting it with nothing would sign you out silently.
        keep = self._tokens.get("refresh_token")
        self._tokens = data
        if not data.get("refresh_token") and keep:
            self._tokens["refresh_token"] = keep
        self._tokens["expires_at"] = time.time() + int(data.get("expires_in", 3600)) - 60
        self._save()
        return True

    def _token(self) -> Optional[str]:
        if not self._tokens:
            return None
        if time.time() >= self._tokens.get("expires_at", 0):
            LOG.debug("refreshing the Spotify token")
            if not self._exchange({
                "grant_type": "refresh_token",
                "refresh_token": self._tokens.get("refresh_token", ""),
                "client_id": self.client_id,
            }):
                return None
        return self._tokens.get("access_token")

    # -- talking to the API ------------------------------------------------

    def _call(self, method: str, path: str, params: Optional[dict] = None,
              body: Optional[dict] = None) -> Any:
        token = self._token()
        if not token:
            raise SpotifyError("Spotify is not connected. Run: "
                               "python -m vesper.tools.spotify --login")
        url = API + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
                # 204 is the usual answer to play/pause/skip: it worked and
                # there is nothing to say about it.
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            raise SpotifyError(self._explain(exc)) from None
        except OSError as exc:
            raise SpotifyError(f"Could not reach Spotify: {exc}") from None

    @staticmethod
    def _explain(exc: urllib.error.HTTPError) -> str:
        """Spotify's errors, in words that say what to do about them."""
        if exc.code == 403:
            return ("Spotify refused that. Controlling playback through the "
                    "API needs Spotify Premium — a free account can see what "
                    "is playing but cannot change it.")
        if exc.code == 404:
            return ("No active Spotify device. Open Spotify on your phone, "
                    "laptop or speaker and play something for a second, then "
                    "ask again — it needs somewhere to send the music.")
        if exc.code == 401:
            return ("Spotify says the login has expired. Run: "
                    "python -m vesper.tools.spotify --login")
        if exc.code == 429:
            return "Spotify is rate-limiting; try again in a moment."
        return f"Spotify returned {exc.code}."

    # -- the things Vesper actually asks for -------------------------------

    def now_playing(self) -> str:
        data = self._call("GET", "/me/player/currently-playing")
        if not data or not data.get("item"):
            return "Nothing is playing."
        return self._describe(data["item"],
                              playing=bool(data.get("is_playing")))

    @staticmethod
    def _describe(item: dict, playing: bool = True) -> str:
        name = item.get("name", "something")
        who = ", ".join(a.get("name", "") for a in item.get("artists", []) if a)
        verb = "Playing" if playing else "Paused on"
        return f"{verb} {name}" + (f" by {who}." if who else ".")

    def play(self, query: str = "") -> str:
        if query:
            found = self._call("GET", "/search",
                               {"q": query, "type": "track", "limit": 1})
            items = (found.get("tracks") or {}).get("items") or []
            if not items:
                return f"Nothing on Spotify matches {query!r}."
            track = items[0]
            self._call("PUT", "/me/player/play", body={"uris": [track["uri"]]})
            return self._describe(track)
        self._call("PUT", "/me/player/play")
        return "Playing."

    def pause(self) -> str:
        self._call("PUT", "/me/player/pause")
        return "Paused."

    def skip(self) -> str:
        self._call("POST", "/me/player/next")
        # Spotify needs a moment before it will report the new track.
        time.sleep(0.6)
        try:
            return self.now_playing()
        except SpotifyError:
            return "Skipped."

    def previous(self) -> str:
        self._call("POST", "/me/player/previous")
        time.sleep(0.6)
        try:
            return self.now_playing()
        except SpotifyError:
            return "Went back."

    def volume(self, percent: int) -> str:
        pct = max(0, min(100, int(percent)))
        self._call("PUT", "/me/player/volume", {"volume_percent": pct})
        return f"Volume {pct} percent."

    def do(self, action: str, query: str = "", percent: int = 50) -> str:
        """One entry point, so the tool executor stays a lookup table."""
        action = (action or "").strip().lower()
        if action in ("play", "resume"):
            return self.play(query)
        if action == "pause":
            return self.pause()
        if action in ("next", "skip"):
            return self.skip()
        if action in ("previous", "back"):
            return self.previous()
        if action == "volume":
            return self.volume(percent)
        if action in ("current", "what", "now_playing"):
            return self.now_playing()
        return (f"I do not know how to {action!r} on Spotify. I can play, "
                "pause, skip, go back, set the volume, or say what is on.")


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Spotify for Vesper.")
    p.add_argument("--login", action="store_true", help="authorise in a browser")
    p.add_argument("--logout", action="store_true", help="forget the tokens")
    p.add_argument("action", nargs="?", default="current",
                   help="play | pause | next | previous | current")
    p.add_argument("query", nargs="*", help="what to play")
    args = p.parse_args(argv)
    setup_logging(CONFIG.log_level)

    sp = Spotify(CONFIG)

    if args.logout:
        sp.forget()
        print("\nForgotten. Vesper can no longer reach your Spotify.\n")
        return 0

    if not sp.configured:
        print("\nSPOTIFY_CLIENT_ID is not set.\n")
        print("  1. Go to developer.spotify.com/dashboard and create an app")
        print("  2. Add this redirect URI, exactly:")
        print(f"       http://127.0.0.1:{CONFIG.spotify_auth_port}/callback")
        print("  3. Copy the Client ID into .env as SPOTIFY_CLIENT_ID")
        print("\nThere is no client secret to copy — this uses PKCE.\n")
        return 1

    if args.login:
        ok = sp.login()
        print("\nConnected.\n" if ok else "\nDid not connect. See above.\n")
        return 0 if ok else 1

    if not sp.available:
        print("\nNot authorised yet. Run: python -m vesper.tools.spotify --login\n")
        return 1

    try:
        print("\n" + sp.do(args.action, " ".join(args.query)) + "\n")
    except SpotifyError as exc:
        print(f"\n{exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
