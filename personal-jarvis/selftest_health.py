"""Health: baselines, rules, the deterministic red flag, and Claude-only routing."""
import asyncio, json, tempfile, time
from pathlib import Path
from jarvis.config import Config
from jarvis.core.brain import Brain, is_health
from jarvis.core.redflag import check, SymptomLog
from jarvis.core.triggers import TriggerEngine, configure_health
from jarvis.core.world_state import WorldState
from jarvis.sensors.health import HealthFeed, Baseline
from jarvis.tools.tool_executor import ToolExecutor

class B:
    def __init__(s, **k): s.__dict__.update(k)
class R:
    def __init__(s, c, sr="tool_use"): s.content, s.stop_reason = c, sr

def cfg_at(tmp):
    c = Config()
    c.health_backend = "file"
    c.health_file = tmp/"in.json"; c.health_history = tmp/"hist.json"
    c.symptom_log = tmp/"sym.jsonl"; c.map_path = tmp/"m.json"
    return c

def main():
    tmp = Path(tempfile.mkdtemp())
    cfg = cfg_at(tmp)

    # --- baseline from a fortnight of ordinary days ---
    feed = HealthFeed(WorldState(), cfg)
    for d in range(1, 15):
        feed.baseline.add({"day": f"2026-08-{d:02d}", "resting_hr": 53 + (d % 3),
                           "hrv": 60 - (d % 4), "load": 400 + (d % 5) * 10,
                           "sleep_hours": 7.2})
    print("1. baseline built from", len(feed.baseline.history), "days |",
          "resting_hr median", feed.baseline.median("resting_hr"))

    # --- a hard session ---
    devs = feed.read({"resting_hr": 54, "hrv": 58, "load": 1400, "sleep_hours": 7})
    print("2. huge session ->", "load", devs["load"]["sigmas"], "sigma above median",
          devs["load"]["median"])
    assert devs["load"]["sigmas"] > 2.5 and devs["load"]["unfavourable"]

    # --- raw numbers must never reach the world state ---
    st = WorldState(); f2 = HealthFeed(st, cfg); f2.baseline = feed.baseline
    f2.push(devs)
    stored = json.dumps(st.snapshot().get("health"))
    print("3. world state holds deviations, not raw:", "median" in stored)

    # --- the rules ---
    # A fresh state: `st` already holds these deviations from the push above,
    # so re-setting them would be a no-op and nothing would have changed.
    configure_health(cfg.health_load_sigmas)
    eng = TriggerEngine(global_cooldown=0.0)
    st = WorldState()
    ch = st.update(health=devs)
    fired = eng.evaluate(st.snapshot(), ch, now=time.time())
    print("4. rule fired ->", fired.rule.name if fired else None)
    assert fired and fired.rule.name == "exertion_spike"

    strained = feed.read({"resting_hr": 62, "hrv": 44, "load": 410})
    st2 = WorldState(); ch2 = st2.update(health=strained)
    eng2 = TriggerEngine(global_cooldown=0.0)
    f = eng2.evaluate(st2.snapshot(), ch2, now=time.time())
    print("5. HR up AND HRV down ->", f.rule.name if f else None)
    assert f and f.rule.name == "strained_after_effort"

    quiet = feed.read({"resting_hr": 54, "hrv": 59, "load": 420})
    st3 = WorldState(); ch3 = st3.update(health=quiet)
    eng3 = TriggerEngine(global_cooldown=0.0)
    print("6. an ordinary day ->", eng3.evaluate(st3.snapshot(), ch3, now=time.time()))

    # --- the red flag is code, not a model ---
    ex = ToolExecutor(WorldState(), cfg, health=feed)
    out, err = ex.run("log_symptom", {"text": "my wee has gone brown"})
    d = json.loads(out)
    print("7. red flag ->", d["level"], "|", d["say_this_verbatim"][:46] + "...")
    assert d["level"] == "urgent" and "A&E today" in d["say_this_verbatim"]
    assert not err
    ex.run("log_symptom", {"text": "legs really sore"})
    body = json.loads(ex.run("read_body", {})[0])
    print("8. logged and readable back:",
          [s["level"] for s in body["symptoms_last_3_days"]])
    assert len(body["symptoms_last_3_days"]) == 2

    # --- routing: health never goes to the gateway ---
    c2 = cfg_at(tmp); c2.models = "omniroute"; c2.anthropic_api_key = ""
    st4 = WorldState()
    b = Brain(st4, ToolExecutor(st4, c2, health=feed), c2)
    r = asyncio.run(b.respond(user_text="my legs are really sore today"))
    print("9. free chain + health question ->", r[:60] + "...")
    assert "only discuss that with Claude" in r

    c3 = cfg_at(tmp); c3.models = "omniroute"; c3.anthropic_api_key = "k"
    seen = []
    class Client:
        messages = None
        async def create(s, **kw):
            seen.append(kw["model"])
            return R([B(type="tool_use", id="1", name="answer",
                        input={"text": "Noted."})])
    Client.messages = Client()
    st5 = WorldState()
    b2 = Brain(st5, ToolExecutor(st5, c3, health=feed), c3, client=Client())
    asyncio.run(b2.respond(user_text="how did I sleep"))
    print("10. with a key, health went to:", seen, "(chain says omniroute)")
    assert seen == ["claude-opus-5"]

    seen.clear()
    asyncio.run(b2.respond(user_text="add milk to the shopping"))
    print("11. a normal question still uses the free chain:", seen or "gateway")
    assert seen == []
    print("\nAll health checks passed.")

main()
