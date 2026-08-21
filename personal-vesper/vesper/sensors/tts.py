"""Speech out — Piper locally, ElevenLabs if you've configured a key.

    python -m vesper.sensors.tts "Good evening."

Both backends are swappable behind `Speaker.say()`. If neither is usable the
speaker degrades to printing the line, which keeps the whole assistant
runnable on a machine with no audio output at all.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

from ..config import CONFIG, Config, setup_logging

LOG = logging.getLogger("vesper.tts")


WINDOWS = os.name == "nt"


def _first_player() -> Optional[list]:
    """The first available command-line audio player, as an argv prefix.

    Windows ships none of these, so there it returns a marker and playback
    goes through `_play_windows` instead — without that, speech output
    silently degraded to printing on every Windows machine.
    """
    if WINDOWS:
        return ["<windows>"]
    for cmd, args in (
        ("paplay", []),          # PulseAudio / PipeWire
        ("aplay", ["-q"]),       # ALSA
        ("afplay", []),          # macOS
        ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
    ):
        if shutil.which(cmd):
            return [cmd, *args]
    return None


def _play_windows(path: str) -> None:
    """Play a file on Windows with what's already on the machine.

    winsound handles WAV natively and is in the standard library. Anything
    else (ElevenLabs returns MP3) goes through PowerShell's media player,
    which is present on every Windows install.
    """
    if path.lower().endswith(".wav"):
        import winsound

        winsound.PlaySound(path, winsound.SND_FILENAME)
        return
    script = (
        "Add-Type -AssemblyName presentationCore;"
        "$p = New-Object system.windows.media.mediaplayer;"
        f"$p.open([uri]'{path}');"
        "Start-Sleep -Milliseconds 400;"
        "$d = $p.NaturalDuration.TimeSpan.TotalMilliseconds;"
        "$p.Play(); Start-Sleep -Milliseconds ([int]$d + 300); $p.Close();"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script],
                   check=True, capture_output=True, timeout=180)


class Speaker:
    """Text in, sound out. Never raises — a dead speaker must not stop Vesper."""

    def __init__(self, cfg: Config = CONFIG) -> None:
        self.cfg = cfg
        self.backend = "print"
        self._lock = threading.Lock()   # one utterance at a time
        self._piper: Optional[str] = None
        self._player = _first_player()
        # The running playback process, so it can be cut off mid-sentence.
        self._proc: Optional[subprocess.Popen] = None
        self._interrupted = False

        wanted = (cfg.tts_backend or "piper").lower()
        if wanted == "elevenlabs" and cfg.elevenlabs_api_key:
            self.backend = "elevenlabs"
        elif wanted == "elevenlabs":
            LOG.warning("TTS_BACKEND=elevenlabs but ELEVENLABS_API_KEY is unset; "
                        "falling back to piper")
            wanted = "piper"

        if wanted == "windows" and WINDOWS:
            self.backend = "windows"
        elif wanted == "windows":
            LOG.warning("TTS_BACKEND=windows only works on Windows; "
                        "falling back to piper")
            wanted = "piper"

        if self.backend not in ("elevenlabs", "windows"):
            # An explicit path first: a setting that says exactly where the
            # program is cannot be defeated by a stale PATH in an open
            # window. `which` stays as the fallback for a normal install.
            piper = ""
            if cfg.piper_bin and Path(cfg.piper_bin).is_file():
                piper = cfg.piper_bin
            elif cfg.piper_bin:
                LOG.warning("PIPER_BIN is set but there is no file at %s",
                            cfg.piper_bin)
            piper = piper or shutil.which("piper") or shutil.which("piper-tts")
            # Windows needs no paplay/aplay/afplay — `_play` routes through
            # the OS there. Requiring one meant a Windows box with Piper
            # properly installed still refused to use it.
            if piper and (self._player or WINDOWS):
                self._piper = piper
                self.backend = "piper"
            elif WINDOWS:
                # Windows has had a speech engine built in for twenty years.
                # Printing instead of using it was silly: it costs nothing,
                # needs no download, no key and no account, and it is a great
                # deal better than silence while someone decides whether to
                # install Piper or pay a subscription.
                self.backend = "windows"
                LOG.info("piper not installed; using the voice built into "
                         "Windows. Install Piper for a better one.")
            elif piper and not self._player:
                LOG.warning("piper found but no audio player "
                            "(paplay/aplay/afplay/ffplay); speech will be printed")
            else:
                LOG.warning("piper not found on PATH; speech will be printed. "
                            "See README step 3.")

        LOG.info("speech out: %s", self.backend)

    # -- public ----------------------------------------------------------

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self._interrupted = False
        with self._lock:
            try:
                if self.backend == "piper":
                    self._say_piper(text)
                elif self.backend == "elevenlabs":
                    self._say_elevenlabs(text)
                elif self.backend == "windows":
                    self._say_windows(text)
                else:
                    print(f"[vesper] {text}")
            except Exception as exc:
                LOG.warning("speech failed (%s); printing instead: %s",
                            self.backend, exc)
                print(f"[vesper] {text}")

    def _play(self, path: str) -> None:
        """Play, and stay interruptible while doing it."""
        if WINDOWS:
            _play_windows(path)
            return
        self._proc = subprocess.Popen([*self._player, path],
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
        try:
            self._proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        finally:
            self._proc = None

    def stop(self) -> None:
        """Cut it off. Called when you start talking over it."""
        self._interrupted = True
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                LOG.debug("playback interrupted")
            except Exception:
                pass

    @property
    def interrupted(self) -> bool:
        was, self._interrupted = self._interrupted, False
        return was

    # -- backends --------------------------------------------------------

    def _say_windows(self, text: str) -> None:
        """The speech engine that ships with Windows (SAPI, via PowerShell).

        No download, no key, no account. Not as good as Piper and nowhere
        near ElevenLabs, but it is already on the machine and it talks.

        The text goes via a FILE rather than on the command line: a spoken
        reply can contain quotes, apostrophes and newlines, and every one of
        those breaks a PowerShell one-liner in a different way.
        """
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "say.txt"
            src.write_text(text, encoding="utf-8")
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                # Prefer a British adult voice if the machine has one, but
                # never fail over it — installed voices vary by machine and
                # by Windows edition.
                "try { $s.SelectVoiceByHints('NotSet','NotSet',0,"
                "[System.Globalization.CultureInfo]::GetCultureInfo('en-GB')) }"
                " catch { };"
                f"$s.Speak([IO.File]::ReadAllText('{src}', "
                "[Text.Encoding]::UTF8))"
            )
            self._proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _, err = self._proc.communicate(timeout=120)
            code = self._proc.returncode
            self._proc = None
            if code != 0 and not self._interrupted:
                raise RuntimeError(
                    "the Windows voice failed: "
                    + (err or b"").decode("utf-8", "replace").strip()[:200])

    def _say_piper(self, text: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "out.wav"
            # RUN IT FROM ITS OWN FOLDER. Piper loads espeak-ng-data from a
            # path relative to the working directory, and we were starting
            # it from wherever Vesper happened to be. On Windows the miss
            # is not a polite error -- it crashes with 0xC0000409
            # (STATUS_STACK_BUFFER_OVERRUN), which looks like a broken
            # download rather than a missing folder it never looked in.
            here = Path(self._piper).parent
            proc = subprocess.run(
                [self._piper, "--model", self.cfg.piper_model,
                 "--output_file", str(wav)],
                input=text.encode("utf-8"),
                capture_output=True, timeout=60, cwd=str(here),
            )
            if proc.returncode != 0 or not wav.is_file():
                err = (proc.stderr or b"").decode("utf-8", "replace").strip()
                hint = ""
                if not (here / "espeak-ng-data").is_dir():
                    hint = (f" — there is no espeak-ng-data folder in {here}, "
                            "which Piper needs. Re-run Get Piper.bat.")
                elif not Path(self.cfg.piper_model).is_file():
                    hint = f" — no voice file at {self.cfg.piper_model}."
                elif not Path(str(self.cfg.piper_model) + ".json").is_file():
                    hint = (" — the voice's .json companion is missing; "
                            "Piper needs both files.")
                raise RuntimeError(
                    f"piper exited {proc.returncode}{hint} {err[:200]}".strip())
            self._play(str(wav))

    def _say_elevenlabs(self, text: str) -> None:
        import json
        import urllib.error
        import urllib.request

        voice = self.cfg.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM"
        # Settable, because providers retire model names and a hardcoded one
        # fails as a bare 400 that mentions neither the model nor the voice.
        model = self.cfg.elevenlabs_model or "eleven_turbo_v2_5"
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            data=json.dumps({
                "text": text,
                "model_id": model,
            }).encode("utf-8"),
            headers={
                "xi-api-key": self.cfg.elevenlabs_api_key,
                "content-type": "application/json",
                "accept": "audio/mpeg",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio = resp.read()
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:400]
            except Exception:
                pass
            hint = ""
            if exc.code == 401:
                hint = " — the API key looks wrong."
            elif exc.code == 400 and "model" in detail.lower():
                hint = (f" — the model {model!r} was rejected. Set "
                        "ELEVENLABS_MODEL to one they still offer.")
            elif exc.code == 400:
                hint = (f" — usually the voice id. Yours is {voice!r}; check "
                        "it against https://api.elevenlabs.io/v1/voices")
            elif exc.code == 429:
                hint = " — out of credits for this month."
            raise RuntimeError(
                f"ElevenLabs said {exc.code}{hint}\n    {detail}") from None
        if not self._player:
            raise RuntimeError("no audio player available")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fh:
            fh.write(audio)
            path = fh.name
        try:
            self._play(path)
        finally:
            os.unlink(path)


def main(argv=None) -> int:
    setup_logging(CONFIG.log_level)
    text = " ".join(argv or sys.argv[1:]) or "Speech output is working."
    speaker = Speaker()
    print(f"backend: {speaker.backend}")
    speaker.say(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
