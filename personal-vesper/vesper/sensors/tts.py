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

        wanted = (cfg.tts_backend or "piper").lower()
        if wanted == "elevenlabs" and cfg.elevenlabs_api_key:
            self.backend = "elevenlabs"
        elif wanted == "elevenlabs":
            LOG.warning("TTS_BACKEND=elevenlabs but ELEVENLABS_API_KEY is unset; "
                        "falling back to piper")
            wanted = "piper"

        if self.backend != "elevenlabs":
            piper = shutil.which("piper") or shutil.which("piper-tts")
            if piper and self._player:
                self._piper = piper
                self.backend = "piper"
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
        with self._lock:
            try:
                if self.backend == "piper":
                    self._say_piper(text)
                elif self.backend == "elevenlabs":
                    self._say_elevenlabs(text)
                else:
                    print(f"[vesper] {text}")
            except Exception as exc:
                LOG.warning("speech failed (%s); printing instead: %s",
                            self.backend, exc)
                print(f"[vesper] {text}")

    def _play(self, path: str) -> None:
        if WINDOWS:
            _play_windows(path)
            return
        subprocess.run([*self._player, path], check=True,
                       capture_output=True, timeout=180)

    # -- backends --------------------------------------------------------

    def _say_piper(self, text: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "out.wav"
            subprocess.run(
                [self._piper, "--model", self.cfg.piper_model,
                 "--output_file", str(wav)],
                input=text.encode("utf-8"),
                check=True, capture_output=True, timeout=60,
            )
            self._play(str(wav))

    def _say_elevenlabs(self, text: str) -> None:
        import json
        import urllib.request

        voice = self.cfg.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM"
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            data=json.dumps({
                "text": text,
                "model_id": "eleven_turbo_v2_5",
            }).encode("utf-8"),
            headers={
                "xi-api-key": self.cfg.elevenlabs_api_key,
                "content-type": "application/json",
                "accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio = resp.read()
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
