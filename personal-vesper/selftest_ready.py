"""Speaking first — and, far more importantly, usually not.

"Make the AI talk first when it knows I am ready." The easy half is
noticing you are there. The half that decides whether this is a feature or
an irritation is the restraint: an assistant that greets you every time
you sit down is a novelty for a day and a nuisance for a year.

So most of these tests are about silence.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vesper.config import Config  # noqa: E402
from vesper.core.ready import Opening, Readiness  # noqa: E402


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  {detail}" if detail else ""))
    return ok


def main() -> int:
    bad = 0
    cfg = Config()

    def at(hour, minute=0):
        return time.struct_time((2026, 8, 21, hour, minute, 0, 3, 233, 0))

    # -- 1. quiet hours, including over midnight --------------------------
    r = Readiness(cfg)
    for hour, want in ((9, False), (14, False), (21, False),
                       (23, True), (2, True), (7, True)):
        bad += not check(f"{hour:02d}:00 quiet", r.quiet_hours(at(hour)) == want)

    # -- 2. it fires on ARRIVAL, not on being present ---------------------
    here = {"v": False}
    r = Readiness(cfg)
    r.present = lambda: here["v"]
    r._was_away = True
    bad += not check("away: nothing", not r.just_arrived())
    here["v"] = True
    bad += not check("arriving: yes", r.just_arrived())
    bad += not check("still there: no, that would fire forever",
                     not r.just_arrived())
    here["v"] = False
    r.just_arrived()
    here["v"] = True
    bad += not check("left and came back: yes again", r.just_arrived())

    # -- 3. the three rules that keep it bearable -------------------------
    # Pin the clock to the middle of the afternoon. Without this the suite
    # passes or fails depending on what time it is run, which it duly did
    # at 23:00 -- the quiet-hours rule silencing everything, correctly, and
    # looking like four unrelated failures.
    def daytime(self, now=None):
        return False

    Readiness.quiet_hours = daytime

    r = Readiness(cfg)
    bad += not check("the first time is allowed", r.may_speak("paper-log"))
    r.spoke("paper-log")
    bad += not check("the same thing again is not",
                     not r.may_speak("paper-log"))
    bad += not check("but a different thing is", r.may_speak("weather"))

    r2 = Readiness(cfg)
    for i in range(cfg.ready_max_per_day):
        r2.spoke(f"thing-{i}")
    bad += not check("the daily cap holds", not r2.may_speak("one-more"))
    bad += not check("unless it is genuinely urgent",
                     r2.may_speak("one-more", urgency=2))

    r3 = Readiness(cfg)
    r3.quiet_hours = lambda now=None: True  # noqa: E731  (deliberate)
    bad += not check("quiet hours silence the ordinary",
                     not r3.may_speak("ordinary"))
    bad += not check("and not the urgent", r3.may_speak("urgent", urgency=2))

    r4 = Readiness(cfg)
    r4.cfg = Config()
    r4.cfg.proactive_enabled = False
    bad += not check("switched off means switched off",
                     not r4.may_speak("anything", urgency=2))

    # -- 4. the first source with something to say wins -------------------
    r5 = Readiness(cfg)
    r5.just_arrived = lambda: True
    picked = r5.opening([
        lambda: None,
        lambda: Opening("second", "Second, sir.", "had something"),
        lambda: Opening("third", "Third, sir.", "also had something"),
    ])
    bad += not check("the first source with something wins",
                     picked and picked.key == "second", str(picked))
    bad += not check("and it is not a digest of all of them",
                     picked and "Third" not in picked.text)

    # -- 5. a source that throws must not stop the rest -------------------
    def explodes():
        raise RuntimeError("boom")

    r6 = Readiness(cfg)
    r6.just_arrived = lambda: True
    got = r6.opening([explodes, lambda: Opening("ok", "Fine, sir.", "fine")])
    bad += not check("a broken source is skipped, not fatal",
                     got and got.key == "ok", str(got))

    # -- 6. nothing to say means saying nothing ---------------------------
    r7 = Readiness(cfg)
    r7.just_arrived = lambda: True
    bad += not check("no sources, no speech", r7.opening([]) is None)
    bad += not check("sources with nothing, no speech",
                     r7.opening([lambda: None, lambda: None]) is None)

    # -- 7. and not arriving means silence whatever is pending ------------
    r8 = Readiness(cfg)
    r8.just_arrived = lambda: False
    bad += not check("not arriving: silent even with something to say",
                     r8.opening([lambda: Opening("x", "Hello, sir.", "eager")])
                     is None)

    print("\nFAIL" if bad else "\nPASS")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
