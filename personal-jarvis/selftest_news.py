"""News + clock test. No network: feeds are stubbed, same as the weather test."""
import time

from jarvis.config import Config
from jarvis.core.triggers import TriggerEngine, configure_watch_words
from jarvis.core.world_state import WorldState
from jarvis.sensors import news as news_mod
from jarvis.sensors.clock import Clock, time_of_day
from jarvis.sensors.news import NewsFeed, parse_feed

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Bank holds rates at 4%</title></item>
<item><title>Breaking: power outage hits the south west</title></item>
<item><title>Cricket &amp; rain &lt;b&gt;stop play&lt;/b&gt;</title></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Markets open lower</title></entry>
<entry><title>Bank holds rates at 4%</title></entry>
</feed>"""


def main():
    # 1. both feed formats
    rss = parse_feed(RSS)
    assert rss == ["Bank holds rates at 4%",
                   "Breaking: power outage hits the south west",
                   "Cricket & rain stop play"], rss
    print("1. RSS parsed, entities and tags stripped:", rss[2])
    atom = parse_feed(ATOM)
    assert atom == ["Markets open lower", "Bank holds rates at 4%"], atom
    print("2. Atom parsed:", atom[0])

    # 3. junk never raises
    assert parse_feed(b"<html>not a feed</html>") == []
    assert parse_feed(b"") == []
    print("3. malformed feeds return nothing rather than exploding")

    # 4. merge interleaves sources and drops duplicate stories
    cfg = Config()
    cfg.news_feeds = "http://a/rss,http://b/atom"
    calls = []

    def fake_fetch(url, timeout=10.0, limit=10):
        calls.append(url)
        return parse_feed(RSS if url.endswith("rss") else ATOM, limit=limit)

    news_mod.fetch_feed = fake_fetch
    feed = NewsFeed(WorldState(), cfg)
    merged = feed.poll_once()
    assert len(calls) == 2
    assert merged[0] == "Bank holds rates at 4%"
    assert merged[1] == "Markets open lower", merged
    assert merged.count("Bank holds rates at 4%") == 1, "duplicate not collapsed"
    print("4. merged + deduped across sources:", merged)

    # 5. headlines reach the summary the model reads
    state = WorldState()
    state.update(headlines=merged, headlines_at=time.time())
    described = state.snapshot().describe(news=2)
    assert "Headlines today" in described and "just now" in described
    assert described.count("\n- ") == 2, "news= cap not honoured"
    print("5. summary carries capped headlines:\n     "
          + described.replace("\n", "\n     "))

    # 6. the trigger only fires on a NEW headline matching a watch word
    configure_watch_words(cfg.news_watch)
    engine = TriggerEngine(global_cooldown=0.0)
    state2 = WorldState()
    t = time.time()

    ch = state2.update(headlines=["Bank holds rates at 4%"])
    assert not engine.evaluate(state2.snapshot(), ch, now=t), \
        "ordinary headline should not fire"
    print("6. ordinary headline -> no trigger")

    ch = state2.update(headlines=["Bank holds rates at 4%",
                                  "Breaking: power outage hits the south west"])
    fired = engine.evaluate(state2.snapshot(), ch, now=t + 1)
    assert fired and fired.rule.name == "major_news", fired
    print("7. new watch-word headline -> trigger:", fired.rule.name)

    # the same story reshuffled is not news again
    ch = state2.update(headlines=["Breaking: power outage hits the south west",
                                  "Bank holds rates at 4%"])
    assert not engine.evaluate(state2.snapshot(), ch, now=t + 5000), \
        "reordered headlines re-fired"
    print("8. same story, reordered -> no trigger")

    # 9. the clock keeps time_of_day current
    assert time_of_day(time.struct_time((2026, 8, 16, 23, 0, 0, 0, 0, 0))) == "night"
    assert time_of_day(time.struct_time((2026, 8, 16, 9, 0, 0, 0, 0, 0))) == "morning"
    state3 = WorldState()
    Clock(state3, cfg).tick()
    snap = state3.snapshot()
    assert snap.get("time_of_day") and snap.get("date") and snap.get("weekday")
    print(f"9. clock: {snap.get('weekday')} {snap.get('date')}, "
          f"{snap.get('time_of_day')}")

    # 10. a minute passing must not look like a state change
    before = state3.snapshot().data
    changed = Clock(state3, cfg).tick()
    assert state3.snapshot().data == before
    print("10. repeat tick in the same hour -> no spurious state change")

    print("\nAll news/clock checks passed.")


if __name__ == "__main__":
    main()
