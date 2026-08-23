"""Speech in — microphone capture plus faster-whisper transcription.

    python -m vesper.sensors.stt        # records one utterance and prints it

Capture is push-to-talk-free: after the wake word fires, `listen_once()`
records until you stop speaking (a short silence) or the hard ceiling is
reached, then transcribes locally. Nothing is sent anywhere.
"""

from __future__ import annotations

import array
import logging
import math
import sys
import time
from typing import Optional

from ..config import CONFIG, Config, setup_logging

LOG = logging.getLogger("vesper.stt")

def _rms(pcm: bytes) -> float:
    """Loudness of a frame of 16-bit mono audio.

    This used to be `audioop.rms`, removed in Python 3.13 — a fresh install
    today has no audioop at all, and speech input died on import. Written
    against the standard library rather than numpy so the wake path has one
    less thing that can be missing: it is 480 samples, thirty times a second.
    """
    if not pcm:
        return 0.0
    samples = array.array("h")
    samples.frombytes(pcm[:len(pcm) - (len(pcm) % 2)])
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2          # 16-bit mono


class Microphone:
    """Thin wrapper over sounddevice so the rest of the code can stay dumb."""

    def __init__(self) -> None:
        self.available = False
        self._sd = None
        try:
            import sounddevice as sd
            self._sd = sd
            self.available = True
        except Exception as exc:
            LOG.warning("microphone unavailable (%s); speech input is off. "
                        "See README step 3.", exc)

    def stream(self, frames: Optional[int] = None):
        """A raw 16-bit mono input stream at 16 kHz.

        `frames` is the block size. Porcupine dictates its own (512) and
        will not accept anything else, so the caller has to be able to
        ask -- everything else is happy with our default.
        """
        if not self.available:
            raise RuntimeError("no microphone")
        return self._sd.RawInputStream(
            samplerate=SAMPLE_RATE, blocksize=frames or FRAME_SAMPLES,
            dtype="int16", channels=1,
        )

    def devices(self):
        """Every input the OS can see, and which one you are about to use."""
        if not self.available:
            return [], None
        try:
            everything = self._sd.query_devices()
            default = self._sd.default.device[0]
        except Exception as exc:
            LOG.error("could not list audio devices: %s", exc)
            return [], None
        ins = [(i, d) for i, d in enumerate(everything)
               if d.get("max_input_channels", 0) > 0]
        return ins, default

    def level(self, seconds: float = 5.0):
        """Listen for a few seconds and report how loud it actually was.

        A laptop's built-in microphone usually works but is easy to get
        wrong — muted in the OS, or set to an input that is not the one you
        are speaking at. This answers "is it hearing me?" without involving
        speech recognition, a model download, or the network.
        """
        peak = 0.0
        floor = None
        frames = 0
        with self.stream() as stream:
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                block, _overflow = stream.read(FRAME_SAMPLES)
                rms = _rms(bytes(block))
                peak = max(peak, rms)
                floor = rms if floor is None else min(floor, rms)
                frames += 1
        return {"peak": peak, "floor": floor or 0.0, "frames": frames}


class Transcriber:
    """faster-whisper, loaded lazily — the model takes seconds to warm up."""

    def __init__(self, cfg: Config = CONFIG) -> None:
        self.cfg = cfg
        self.available = False
        self._model = None

    def _ensure(self) -> bool:
        if self._model is not None:
            return True
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:
            LOG.warning("faster-whisper not installed (%s); transcription is off",
                        exc)
            return False
        LOG.info("loading whisper model %s (%s/%s) — first run downloads it",
                 self.cfg.stt_model, self.cfg.stt_device, self.cfg.stt_compute_type)
        try:
            self._model = WhisperModel(
                self.cfg.stt_model,
                device=self.cfg.stt_device,
                compute_type=self.cfg.stt_compute_type,
            )
        except Exception as exc:
            LOG.error("could not load whisper model: %s", exc)
            return False
        self.available = True
        return True

    def transcribe(self, pcm: bytes) -> str:
        if not pcm or not self._ensure():
            return ""
        import numpy as np

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

        # LEVEL FIRST. A laptop microphone at default gain often peaks
        # around a tenth of full scale, and Whisper is measurably worse on
        # quiet audio -- it is the single most common reason a recogniser
        # "isn't very good" on a machine where the microphone is fine.
        # Normalising the peak costs one pass over a few seconds of samples.
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if 0.0 < peak < 0.7:
            audio = audio * (0.85 / peak)

        segments, _info = self._model.transcribe(
            audio,
            language="en",
            # Greedy decoding (beam_size=1) is the fastest and the least
            # accurate. On a two-second utterance the difference is a few
            # hundred milliseconds and a noticeably better transcript.
            beam_size=self.cfg.stt_beam,
            # Whisper carries context between segments by default, which on
            # a run of short independent utterances makes it repeat itself
            # and invent continuations of things you never said.
            condition_on_previous_text=False,
            # THE BIG ONE for a made-up name. Whisper has never seen
            # "Vesper" as an assistant and writes "whisper", "vespa" or
            # "Vesta" instead. A prompt containing the words you actually
            # use biases it towards them at no cost.
            initial_prompt=self._vocabulary(),
            vad_filter=True,
            # The default VAD trims too tightly and eats the first
            # consonant, which is exactly the syllable a wake word starts
            # with.
            vad_parameters={"min_silence_duration_ms": 400,
                            "speech_pad_ms": 200},
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def _vocabulary(self) -> str:
        """Words this particular user says that Whisper would not guess.

        Passed as `initial_prompt`, which biases decoding towards them. The
        wake phrase belongs here above all -- a recogniser that writes
        "hello whisper" every time is not a microphone problem.
        """
        bits = []
        if self.cfg.wake_phrase:
            bits.append(self.cfg.wake_phrase.strip())
        if self.cfg.stt_vocabulary:
            bits.append(self.cfg.stt_vocabulary.strip())
        return ". ".join(b for b in bits if b)


class Listener:
    """Record one utterance, transcribe it, return the text."""

    def __init__(self, cfg: Config = CONFIG,
                 mic: Optional[Microphone] = None,
                 transcriber: Optional[Transcriber] = None) -> None:
        self.cfg = cfg
        self.mic = mic or Microphone()
        self.transcriber = transcriber or Transcriber()

    @property
    def available(self) -> bool:
        return self.cfg.stt_enabled and self.mic.available

    def record(self, start_window: Optional[float] = None) -> bytes:
        """Capture until a pause, or until the ceiling. Returns raw PCM.

        `start_window` is how long to wait for you to BEGIN. It used to be
        three seconds, hardcoded, and that was the whole of the "it can't
        hear me after the first thing" bug: after a reply you would take a
        breath, think for a moment, and by the time you spoke it had
        already given up. Three seconds is fine for the instant after a
        wake word and far too short for the pause in a conversation.
        """
        if not self.mic.available:
            return b""

        wait_for_start = (self.cfg.stt_start_seconds if start_window is None
                          else start_window)

        frames: list = []
        pre: list = []                 # a rolling half-second, kept below
        started = time.monotonic()
        levels: list = []
        floor: Optional[float] = None
        threshold = 0.0
        quiet_for = 0.0
        spoke = False
        # Frames to measure the room over. One frame was enough to be
        # poisoned by a door, a cough, or the tail of Vesper's own voice
        # still coming out of the speaker -- and a floor set from that is
        # a floor your actual speech never gets over.
        calibrate = max(int(300 / FRAME_MS), 3)

        with self.mic.stream() as stream:
            while True:
                block, _overflow = stream.read(FRAME_SAMPLES)
                pcm = bytes(block)
                level = _rms(pcm)
                elapsed = time.monotonic() - started

                if floor is None:
                    levels.append(level)
                    pre.append(pcm)
                    if len(levels) < calibrate:
                        continue
                    # The QUIETEST of the calibration frames, not the mean:
                    # if anything loud happened while measuring, the low
                    # frames are the honest reading of the room.
                    floor = max(min(levels), 60)
                    threshold = floor * 2.2
                    continue

                if level > threshold:
                    if not spoke and pre:
                        # Keep the run-up. Speech is loudest a syllable in,
                        # so the frame that crosses the threshold is
                        # usually the SECOND one -- without this the
                        # recording starts mid-word and the transcriber
                        # loses the first thing you said.
                        frames.extend(pre[-int(500 / FRAME_MS):])
                        pre = []
                    spoke = True
                    quiet_for = 0.0
                    frames.append(pcm)
                elif spoke:
                    quiet_for += FRAME_MS / 1000
                    frames.append(pcm)
                    if quiet_for >= self.cfg.stt_silence_seconds:
                        break
                else:
                    pre.append(pcm)
                    if len(pre) > int(1000 / FRAME_MS):
                        pre.pop(0)
                    if elapsed > wait_for_start:
                        LOG.debug("no speech within %.1fs", wait_for_start)
                        return b""

                if elapsed > self.cfg.stt_max_seconds + wait_for_start:
                    LOG.debug("hit max utterance length")
                    break

        return b"".join(frames)

    def wait_for_speech(self, seconds: float, over: float = 3.0) -> bool:
        """Listen for someone starting to talk. True as soon as they do.

        Used two ways: to notice you cutting across a reply, and to keep the
        conversation open for a follow-up without the wake word.

        The noise floor is measured from the first moments of listening. When
        this runs *during* playback, those moments contain Vesper's own voice
        — which is the point. Its own speech becomes the floor, and yours has
        to be louder than it to count. That is echo cancellation for people
        without echo cancellation: crude, free, and good enough in a normal
        room. With speakers loud and a distant microphone it can still hear
        itself; headphones or a directional mic remove the problem entirely.
        """
        if not self.mic.available:
            return False
        started = time.monotonic()
        floor: Optional[float] = None
        calib: list = []
        loud_frames = 0
        need = max(2, int(0.18 / (FRAME_MS / 1000)))   # ~180ms of real speech

        try:
            with self.mic.stream() as stream:
                while time.monotonic() - started < seconds:
                    block, _ = stream.read(FRAME_SAMPLES)
                    level = _rms(bytes(block))
                    if floor is None:
                        calib.append(level)
                        if len(calib) >= 8:
                            floor = max(sorted(calib)[len(calib) // 2], 60)
                        continue
                    if level > floor * over:
                        loud_frames += 1
                        if loud_frames >= need:
                            return True
                    else:
                        loud_frames = 0
        except Exception:
            LOG.debug("listening for speech failed", exc_info=True)
        return False

    def listen_once(self, start_window: Optional[float] = None) -> str:
        if not self.available:
            return ""
        pcm = self.record(start_window=start_window)
        if not pcm:
            return ""
        LOG.debug("transcribing %.1fs of audio", len(pcm) / FRAME_BYTES * FRAME_MS / 1000)
        text = self.transcriber.transcribe(pcm)
        if text:
            LOG.info("heard: %s", text)
        return text


def hearing_test(cfg=CONFIG, rounds: int = 3) -> int:
    """Is it the microphone or the software? Measure, do not guess.

    Records you saying a known sentence a few times and reports the two
    things separately:

      * the LEVEL -- how loud you arrive. This is the microphone, its
        gain, and where you are sitting. Nothing in the code can fix a
        signal that is not there.
      * the TRANSCRIPT -- what the recogniser made of it. This is the
        model, the beam width and the vocabulary, all of which are
        settings.

    Reporting them together is the point: "it doesn't hear me well" is
    two completely different problems with two completely different
    fixes, and they are indistinguishable from the outside.
    """
    # Check the microphone BEFORE importing anything, so a machine with
    # no audio at all gets the useful sentence rather than an ImportError
    # about a maths library it was never going to need.
    listener = Listener(cfg)
    if not listener.available:
        print("\n  No microphone that Vesper can see, so there is nothing to")
        print("  measure. Check which inputs exist:")
        print("      Hearing test aside, run:  vesper.sensors.stt --devices\n")
        return 1
    try:
        import numpy as np
    except Exception as exc:
        print(f"\n  numpy is missing ({exc}), so levels cannot be measured.")
        print("  Run Install Vesper.bat again.\n")
        return 1

    SAY = "Hello Vesper, what is the weather today"
    print(f"\n  Say this, clearly, {rounds} times. Wait for each prompt.\n")
    print(f"      \"{SAY}\"\n")

    levels, texts = [], []
    for i in range(1, rounds + 1):
        print(f"  {i}. Speak now...", flush=True)
        pcm = listener.record(start_window=12.0)
        if not pcm:
            print("     heard nothing at all")
            continue
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        peak = float(np.max(np.abs(audio))) / 32768.0
        rms = float(np.sqrt(np.mean(audio ** 2))) / 32768.0
        seconds = len(pcm) / FRAME_BYTES * FRAME_MS / 1000
        said = listener.transcriber.transcribe(pcm)
        levels.append((peak, rms, seconds))
        texts.append(said)
        print(f"     peak {peak:5.1%}  loudness {rms:5.1%}  {seconds:.1f}s")
        print(f"     heard: {said!r}")

    if not levels:
        print("\n  Nothing was recorded. The microphone is not picking you up "
              "at all —\n  check Windows sound settings and that the right "
              "input is selected.\n")
        return 1

    print("\n  ── the verdict ──────────────────────────────────────────\n")
    peak = max(p for p, _r, _s in levels)
    rms = max(r for _p, r, _s in levels)
    mic_ok = peak > 0.10 and rms > 0.010

    if not mic_ok:
        print(f"  MICROPHONE. You are arriving at {peak:.1%} peak, which is "
              "very quiet.")
        print("  Windows: Settings > System > Sound > your microphone >")
        print("  turn the Input volume up, and switch ON any 'Microphone "
              "Boost'.")
        print("  Sit closer, or use a headset. No software setting recovers")
        print("  a signal that is not there.")
    else:
        print(f"  The microphone is fine — {peak:.1%} peak is a healthy level.")

    from .heard_phrase import close_enough, normalise

    good = sum(1 for x in texts if close_enough(
        normalise(x)[:len(SAY)], SAY, 0.4))
    print(f"\n  The recogniser got {good} of {len(texts)} close to right.")
    if good < len(texts):
        print("  If that is poor while the level is fine, it is the SOFTWARE,")
        print("  and these are the dials, in the order worth trying:")
        print("    STT_MODEL=small.en   more accurate, about twice as slow")
        print("    STT_BEAM=5           already on; 1 is the fast, sloppy one")
        print("    STT_VOCABULARY=...   add names it keeps getting wrong")
    if cfg.wake_phrase:
        from .heard_phrase import split_wake

        heard_wake = sum(1 for x in texts
                         if split_wake(x, cfg.wake_phrase,
                                       cfg.wake_tolerance)[0])
        print(f"\n  The wake phrase was recognised {heard_wake} of "
              f"{len(texts)} times.")
        if heard_wake < len(texts):
            print("  Raise WAKE_TOLERANCE (0.34 now, try 0.45) to forgive "
                  "more.")
    print()
    return 0 if mic_ok else 1


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Microphone and transcription check.")
    p.add_argument("--devices", action="store_true",
                   help="list the microphones this machine can see")
    p.add_argument("--hearing", action="store_true",
                   help="is it the microphone or the software? measures both")
    p.add_argument("--level", action="store_true",
                   help="check the microphone actually hears you (no models)")
    args = p.parse_args(argv)
    setup_logging(CONFIG.log_level)

    if args.hearing:
        return hearing_test()

    if args.devices:
        mic = Microphone()
        if not mic.available:
            print("\nsounddevice is not installed, so no audio device can be "
                  "seen at all.\n  pip install sounddevice\n")
            return 1
        ins, default = mic.devices()
        if not ins:
            print("\nNo input devices. On a laptop this usually means the "
                  "microphone is muted or blocked in the OS privacy "
                  "settings rather than missing.\n")
            return 1
        print("\nMicrophones this machine can see:\n")
        for i, d in ins:
            star = " <- default, this is the one Vesper uses" if i == default else ""
            print(f"  [{i}] {d['name']}{star}")
        print("\nIf the default is the wrong one, change it in the OS sound "
              "settings.\nThen check it hears you:  "
              "python -m vesper.sensors.stt --level\n")
        return 0

    if args.level:
        mic = Microphone()
        if not mic.available:
            print("\nNo microphone available here.\n")
            return 1
        print("\nTalk normally for five seconds, at the distance you would "
              "actually use…\n")
        r = mic.level(5.0)
        peak = r["peak"]
        # RMS of 16-bit audio. Judged from what the wake word needs to work,
        # not from any absolute standard.
        if peak < 60:
            verdict = ("Nothing came through. The microphone is muted, "
                       "blocked in privacy settings, or the wrong device is "
                       "selected — run --devices.")
        elif peak < 300:
            verdict = ("Very quiet. The wake word will miss you often. Move "
                       "closer, raise the input level in the OS, or use a "
                       "headset.")
        elif peak < 8000:
            verdict = "Good level. The wake word should hear you reliably."
        else:
            verdict = ("Very loud — it may be clipping. Lower the input level "
                       "if it mishears you.")
        print(f"  loudest: {peak:.0f}    quietest: {r['floor']:.0f}    "
              f"({r['frames']} frames)")
        print(f"\n  {verdict}\n")
        return 0

    listener = Listener()
    if not listener.available:
        print("No microphone available in this environment.")
        print("Install `sounddevice` and grant microphone permission, "
              "then run this again.")
        print("To see what the machine can hear: "
              "python -m vesper.sensors.stt --devices")
        return 1
    print("Speak after the beep-less prompt… (silence ends the recording)")
    text = listener.listen_once()
    print(f"\nTranscript: {text!r}" if text else "\nNothing transcribed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
