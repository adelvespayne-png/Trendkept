"""The conversation window and barge-in, against a scripted microphone."""
import asyncio, struct, tempfile, time
from pathlib import Path
from vesper.config import Config
from vesper.main import Vesper
from vesper.sensors.stt import FRAME_SAMPLES, _rms

QUIET = struct.pack("<%dh" % FRAME_SAMPLES, *([0] * FRAME_SAMPLES))
LOUD  = struct.pack("<%dh" % FRAME_SAMPLES, *([12000] * FRAME_SAMPLES))

class B:
    def __init__(s, **k): s.__dict__.update(k)
class R:
    def __init__(s, c, sr="tool_use"): s.content, s.stop_reason = c, sr

def cfg_at(tmp):
    c = Config()
    c.anthropic_api_key = "t"; c.models = "claude-opus-5"
    c.map_path = tmp/"m.json"; c.state_path = tmp/"s.json"; c.log_path = tmp/"l.jsonl"
    c.wake_enabled = False; c.news_enabled = False
    return c

def main():
    tmp = Path(tempfile.mkdtemp())

    # --- 1. rms-based speech detection, no hardware ---
    from vesper.sensors.stt import Listener
    class Mic:
        available = True
        def __init__(s, frames): s.frames = frames
        def stream(s):
            fr = s.frames
            class S:
                i = 0
                def read(self, n):
                    f = fr[min(self.i, len(fr) - 1)]; self.i += 1; return f, False
                def __enter__(self): return self
                def __exit__(self, *a): return False
            return S()

    silent = Listener(Config(), mic=Mic([QUIET] * 200))
    t0 = time.monotonic()
    print("1. silence for the whole window ->",
          silent.wait_for_speech(0.6), f"({time.monotonic()-t0:.1f}s, gave up)")

    speaks = Listener(Config(), mic=Mic([QUIET] * 10 + [LOUD] * 40))
    print("2. someone starts talking ->", speaks.wait_for_speech(3.0))

    # Its own voice becomes the floor: steady playback then YOU, louder.
    MED = struct.pack("<%dh" % FRAME_SAMPLES, *([3000] * FRAME_SAMPLES))
    own = Listener(Config(), mic=Mic([MED] * 60))
    print("3. only its own voice playing ->", own.wait_for_speech(1.0),
          "(must be False, or it interrupts itself)")
    over = Listener(Config(), mic=Mic([MED] * 10 + [LOUD] * 40))
    print("4. you speaking over it ->", over.wait_for_speech(3.0))

    # --- 5. the conversation loop ---
    said = []
    turns = ["what's the weather", "and tomorrow?", ""]
    class Client:
        messages = None
        async def create(s, **kw):
            return R([B(type="tool_use", id="1", name="answer",
                        input={"text": "Answer " + str(len(said) + 1)})])
    Client.messages = Client()

    cfg = cfg_at(tmp)
    cfg.follow_up_seconds = 5.0
    v = Vesper(cfg)
    v.brain._client = Client(); v.brain.available = True
    v.speaker.say = lambda t: said.append(t)
    v.speaker.backend = "print"          # skip real playback
    # A stand-in listener: `available` is a read-only property on the real
    # one, so swap the whole object rather than patching an attribute.
    class FakeListener:
        available = True
        def __init__(s, lines, follows):
            s.lines, s.follows = list(lines), list(follows)
            s.windows = []
        def listen_once(s, start_window=None):
            s.windows.append(start_window)
            return s.lines.pop(0) if s.lines else ""

        def wait_for_speech(s, *a, **k):
            return s.follows.pop(0) if s.follows else False
    v.listener = FakeListener(turns, [True, True, False])
    v.wake.stop = lambda: None; v.wake.start = lambda: None

    asyncio.run(v._handle_wake())
    print("5. one wake word, three turns without repeating it ->", said)
    # The fix for "she can't hear me after the first thing": a follow-up
    # gets the long window, and it is recorded in ONE stream rather than
    # waiting then re-opening (which lost the start of the sentence).
    w = v.listener.windows
    print("   start windows per turn:", w)
    assert w and w[0] is None, f"first turn should use the default: {w}"
    assert all(x == v.cfg.follow_up_seconds for x in w[1:]), \
        f"follow-ups should get the long window: {w}"
    assert said == ["Answer 1, sir", "Answer 2, sir"], said

    # --- 6. window off = one question and done ---
    said.clear()
    cfg2 = cfg_at(tmp); cfg2.follow_up_seconds = 0
    v2 = Vesper(cfg2)
    v2.brain._client = Client(); v2.brain.available = True
    v2.speaker.say = lambda t: said.append(t); v2.speaker.backend = "print"
    v2.listener = FakeListener(["hello"], [])
    v2.wake.stop = lambda: None; v2.wake.start = lambda: None
    asyncio.run(v2._handle_wake())
    print("6. FOLLOW_UP_SECONDS=0 ->", said, "(one turn, as before)")
    assert len(said) == 1

    # --- 7. barge-in actually stops playback ---
    stopped = {"n": 0}
    cfg3 = cfg_at(tmp)
    v3 = Vesper(cfg3)
    class Cutter(FakeListener):
        available = True
        def __init__(s, delay, result): s.delay, s.result = delay, result
        def wait_for_speech(s, *a, **k):
            time.sleep(s.delay); return s.result
    v3.listener = Cutter(0.2, True)
    v3.speaker.backend = "piper"
    v3.speaker.say = lambda t: time.sleep(1.5)          # a long sentence
    v3.speaker.stop = lambda: stopped.__setitem__("n", stopped["n"] + 1)
    asyncio.run(v3._speak("a fairly long reply that you talk over"))
    print("7. talked over ->  speaker.stop() called:", stopped["n"], "time(s)")
    assert stopped["n"] == 1

    stopped["n"] = 0
    v3.listener = Cutter(2.0, False)
    v3.speaker.say = lambda t: None
    asyncio.run(v3._speak("short"))
    print("8. left to finish -> stop() called:", stopped["n"], "time(s)")
    assert stopped["n"] == 0

    print("\nAll conversation checks passed.")

main()
