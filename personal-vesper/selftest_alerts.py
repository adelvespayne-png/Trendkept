"""Alerts: a real HTTP server standing in for ntfy, and the severity floor."""
import json, tempfile, threading, time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from vesper.alerts import Alerts
from vesper.config import Config
from vesper.core.world_state import WorldState
from vesper.tools.tool_executor import ToolExecutor

PORT = 20993
GOT = []

class F(BaseHTTPRequestHandler):
    def log_message(s,*a): pass
    def do_POST(s):
        n = int(s.headers.get("Content-Length", 0))
        GOT.append({"body": s.rfile.read(n).decode(),
                    "title": s.headers.get("Title"),
                    "priority": s.headers.get("Priority"),
                    "tags": s.headers.get("Tags")})
        s.send_response(200); s.send_header("Content-Length","0"); s.end_headers()

def cfg_at(tmp, floor="urgent"):
    c = Config()
    c.alert_backend = "ntfy"
    c.ntfy_server = f"http://127.0.0.1:{PORT}"
    c.ntfy_topic = "vesper-test-topic"
    c.alert_min_level = floor
    c.symptom_log = tmp/"s.jsonl"
    return c

def main():
    h = ThreadingHTTPServer(("127.0.0.1", PORT), F)
    threading.Thread(target=h.serve_forever, daemon=True).start()
    tmp = Path(tempfile.mkdtemp())

    cfg = cfg_at(tmp)
    a = Alerts(cfg)
    print("1. available:", a.available, "| target:", a._target())
    assert a.available

    # Deliberately an em dash: headers are latin-1, and this exact character
    # made every alert fail silently until it was caught.
    a.send("hello", "urgent", "Vesper — test"); time.sleep(0.6)
    print("2. sent ->", GOT[-1]["title"], "| priority", GOT[-1]["priority"],
          "| tag", GOT[-1]["tags"])
    assert GOT[-1]["priority"] == "5"

    # a red flag must push by itself, without any model involved
    GOT.clear()
    ex = ToolExecutor(WorldState(), cfg, alerts=a)
    ex.run("log_symptom", {"text": "my urine has gone dark brown"})
    time.sleep(0.8)
    print("3. red flag pushed on its own:", len(GOT) == 1)
    print("   phone gets:", GOT[0]["body"].replace("\n", " ")[:88] + "...")
    assert "A&E" in GOT[0]["body"] and GOT[0]["priority"] == "5"

    # ...and a minor one does not, at the default floor
    GOT.clear()
    ex.run("log_symptom", {"text": "legs a bit sore"}); time.sleep(0.6)
    print("4. 'legs a bit sore' at floor=urgent -> pushes:", len(GOT))
    assert not GOT

    # unless you lower the floor
    GOT.clear()
    cfg2 = cfg_at(tmp, floor="watch")
    ex2 = ToolExecutor(WorldState(), cfg2, alerts=Alerts(cfg2))
    ex2.run("log_symptom", {"text": "legs a bit sore"}); time.sleep(0.6)
    print("5. same thing at floor=watch -> pushes:", len(GOT),
          "| priority", GOT[0]["priority"] if GOT else "-")
    assert len(GOT) == 1 and GOT[0]["priority"] == "3"

    # 999-level gets the emergency wording
    GOT.clear()
    ex.run("log_symptom", {"text": "chest pain spreading to my arm"}); time.sleep(0.8)
    print("6. emergency ->", GOT[0]["body"].split("\n")[-1][:46] + "...",
          "| tag", GOT[0]["tags"])
    assert "999" in GOT[0]["body"]

    # a dead phone endpoint must not take the assistant down
    cfg3 = cfg_at(tmp); cfg3.ntfy_server = "http://127.0.0.1:1"
    ex3 = ToolExecutor(WorldState(), cfg3, alerts=Alerts(cfg3))
    out, err = ex3.run("log_symptom", {"text": "dark brown urine"})
    time.sleep(0.6)
    print("7. push unreachable -> tool still returned cleanly:", not err,
          "| instruction intact:", "A&E" in out)
    assert not err and "A&E" in out

    # off by default
    off = Config(); off.alert_backend = "none"
    print("8. shipped default ->", Alerts(off).available, "(off until you set it up)")
    assert not Alerts(off).available

    # 9. the wearable path. This is the one that was missing: a bad number
    # from the bracelet woke the brain to SPEAK, and speaking only reaches
    # you if you are in the room. The body rules fire exactly when you may
    # not be — mid-session, asleep, away from the laptop.
    from vesper.core.triggers import DEFAULT_RULES

    body = {r.name: r for r in DEFAULT_RULES
            if r.name in ("exertion_spike", "strained_after_effort")}
    assert len(body) == 2, sorted(r.name for r in DEFAULT_RULES)
    for name, rule in sorted(body.items()):
        print(f"9. {name} reaches the phone:", rule.alert)
        assert rule.alert, f"{name} would only ever be said out loud"

    # ...and nothing else does, so ordinary remarks stay off your lock screen.
    chatty = [r.name for r in DEFAULT_RULES
              if r.alert and r.name not in body]
    print("   rules that buzz the phone:", sorted(body), "| others:", chatty)
    assert not chatty, chatty

    h.shutdown()
    print("\nAll alert checks passed.")

main()
