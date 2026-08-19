# Vesper

A local-first voice assistant. Cheap sensors run all the time and cost
nothing; the model is invoked only when you speak to it or when something
happens that a rule says is worth a look.

```
 microphone ──► wake word ──► speech-to-text ─┐
                                              ├──►  brain  ──► tools ──► speech
 camera ──► YOLO ──┐                          │   (Claude)
 home assistant ───┼──► world state ──► triggers ──┘
                   │         ▲
                   └─────────┘
```

The two arrows into the brain are the only two things that ever cost money.
The camera loop, the wake-word model and the Home Assistant poller run
continuously and never call the API — they write into the world state and
stop there.

**On Windows?** Read **WINDOWS.md** instead — the steps below are macOS and
Linux. Windows needs no PortAudio, uses its own audio for playback, and has
its own firewall step for the phone.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install anthropic                 # the one required dependency
cp .env.example .env                  # then put your API key in it
python -m vesper.main --text          # type at it; no microphone needed
```

That works with no hardware at all. Add the microphone, camera and smart
home in whatever order you like — each one switches itself on when its
dependencies appear, and stays quietly off when they don't.

```bash
python -m vesper.main --check         # what's on, what's off, and how to fix it
```

## Running it

| Command | What it does |
|---|---|
| `python -m vesper.main` | The real thing: wake word, voice in, voice out |
| `python -m vesper.main --text` | Type instead of speaking (sensors still run) |
| `python -m vesper.main --say "..."` | One question, then exit |
| `python -m vesper.main --check` | Subsystem availability report |
| `python -m vesper.main --serve` | Also open the phone endpoint — see **PHONE.md** |
| `python -m vesper.sensors.news` | Fetch the headlines once and print them |
| `python -m vesper.harness` | Trigger rules against fake sensor data, no API key |

Each sensor module also runs standalone, which is how you debug one piece
without the rest: `python -m vesper.sensors.stt`, `.tts "hello"`,
`.wake_word`, `.vision`, `.home_assistant`.

---

# Build order, and what you have to do by hand

The stages are independent. Stop after any of them and you have something
that runs. **Your manual steps at each stage are called out in bold.**

### 1–2. World state and triggers — nothing to install

```bash
python -m vesper.harness
```

Walks a fake evening (someone arrives, leaves, stove goes on, nobody moves,
a stranger appears at night) and prints which rules fire. No API key, no
hardware, no network. `python -m vesper.harness --repl` lets you type state
changes at it: `people=unknown`, `devices.stove=on`, `time_of_day=night`.

**Manual setup: none.**

### 3. Speech in and out

```bash
pip install sounddevice numpy faster-whisper
python -m vesper.sensors.tts "Speech output is working."
python -m vesper.sensors.stt      # records one sentence and prints it
```

**Manual setup:**

- **PortAudio**, which `sounddevice` binds to:
  `sudo apt install portaudio19-dev` (Debian/Ubuntu) or
  `brew install portaudio` (macOS).
- **Microphone permission.** macOS pops a dialog the first time — if you
  miss it, System Settings → Privacy & Security → Microphone, and tick your
  terminal. On Linux nothing prompts, but check the mic isn't muted in
  `pavucontrol`.
- **Piper**, for speech out. It is a binary, not a pip package: download
  from [github.com/rhasspy/piper/releases](https://github.com/rhasspy/piper/releases),
  put it on your `PATH`, then fetch a voice from
  [Hugging Face](https://huggingface.co/rhasspy/piper-voices) — the `.onnx`
  and `.onnx.json` files must sit side by side. Set `PIPER_MODEL` to the
  `.onnx` path. `en_GB-alan-medium` is the closest to the voice you're
  probably imagining.
- **An audio player**: `paplay`, `aplay`, `afplay` or `ffplay`. You almost
  certainly already have one.

Skipping all of this is fine — speech falls back to printing, and the whole
assistant still works in `--text` mode.

The Whisper model downloads itself on first use (~150 MB for `base.en`), so
the first transcription is slow and every one after is not.

### 4. Wake word

```bash
pip install openwakeword onnxruntime
python -m vesper.sensors.wake_word     # prints a line each time it hears you
```

**The spoken trigger is still "hey Jarvis", and that is deliberate.**
openWakeWord ships trained models for a fixed set of phrases; there is no
"hey vesper" to download. Training a custom one takes a few hours and comes
out less reliable than a stock model, so the assistant is called Vesper and
answers to "hey Jarvis" until you decide that bothers you enough to fix.
`WAKE_PHRASE` is what the interface tells you to say, so it always matches
whatever model is loaded.

**Manual setup: none** — openWakeWord downloads its own models on first run. If it triggers on the
television, raise `WAKE_THRESHOLD` towards 0.7; if it takes two goes to hear
you, drop it to 0.4.

### 5. The brain

```bash
pip install anthropic
python -m vesper.main --say "what do you know about the room?"
```

**Manual setup: an API key.** [console.anthropic.com](https://console.anthropic.com)
→ API keys → create one, and put it in `.env` as `ANTHROPIC_API_KEY`. That
file is git-ignored; the key never goes anywhere else.

This is Claude Opus 5 — the same model behind Claude itself, not a cut-down
local one. It answers open-ended questions at real depth, and with
`WEB_ENABLED=true` it searches and reads the live web rather than being stuck
with what it was trained on.

**When a model runs out.** `VESPER_MODELS` is a chain, and the gateway sits
inside it rather than only at the end: a rung named `omniroute` hands that
turn to the gateway and, if it can't take it either, the chain carries on to
the next Claude model. The default is

```
claude-opus-5 → omniroute
```

**Which way round matters.** With Opus first you pay for nearly every
question, because Opus answers nearly every question — the gateway only picks
up the overflow. If the goal is to spend as little as possible, invert it:

```
VESPER_MODELS=omniroute,claude-opus-5
```

Free providers do the work, Claude catches what they can't. Answers get less
sharp; every tool still works either way.

**One thing the chain deliberately does not route around: a refusal.** If a
model declines a request, that ends the turn. Handing the same request to a
different model until one agrees is not a fallback, it is shopping for a yes,
and this chain won't do it. Only transient failures step down.
 A rate limit, an
overloaded API or an empty credit balance moves the turn to the next model
down; a malformed request does not, because retrying our own bug on three
models just wastes three calls. All three speak the same API and use the same
tools, so a step down costs cleverness and nothing else. It stays on the
working rung rather than bouncing back into the limit.

**Below all of them sits a gateway.** By default that is
[OmniRoute](https://github.com/diegosouzapw/OmniRoute) — `npm install -g
omniroute`, leave it running, and it fans requests out across hundreds of
providers, switching itself when one runs dry. Vesper just asks for the model
`auto` and lets it route. Anything OpenAI-compatible works here; point
`FALLBACK_BASE` at GitHub Models instead and `python -m vesper.providers`
picks the best model from each maker for you.

**It keeps your tools.** The schemas are translated into the OpenAI dialect
on the way out and the calls translated back on the way in, so on this rung
Vesper can still read and write your map, set reminders, check the weather,
read the room, and fetch a web page. Same executor, same map file.

**Search follows it too.** Anthropic's `web_search` can't cross over — it
runs on their servers — so there is a `search_web` tool that runs on yours.
It works out of the box with no key by scraping DuckDuckGo, which is
best-effort: a layout change on their side breaks it. Two minutes and a free
key from [Brave](https://brave.com/search/api) or
[Tavily](https://tavily.com) makes it solid. `SEARCH_PROVIDER=none` removes
it entirely.

The pattern the model uses is search, then `fetch_page` on whatever looks
worth reading properly.

**Two things worth knowing before you switch it on.** A gateway sees
everything you say to Vesper on that path and forwards it to whichever
provider it picks — a different posture from talking to one company you chose.
And it is third-party software running on your machine. `FALLBACK_ENABLED=false`
turns the whole rung off.

**Verified against a real OmniRoute** (v3.8.49): the endpoint accepts this
exact request shape, and the aliases in `FALLBACK_MODELS` come from its own
`/v1/models` rather than its README — it offers 38 `auto/*` routers, including
`auto/best-coding`, `auto/best-free`, `auto/cheap` and `auto/claude-opus`. It
reports `tool_calling: true`, which is what this rung depends on.

What I could not test is a *successful* completion: my sandbox blocks the
upstream providers OmniRoute routes to, so every request came back as a
routing failure. The plumbing is proven; the round trip is not.

Cost control is `VESPER_EFFORT` (`low` → `max`, default `high`) and the fact
that nothing but these two paths ever calls the API. Drop to `medium` for
cheaper, quicker replies.

### 6. The orchestrator

```bash
python -m vesper.main
```

Wake word → record → transcribe → brain → speak, plus the ambient path.

**One wake word starts a conversation, not a question.** After each answer it
keeps listening for `FOLLOW_UP_SECONDS`, so the obvious follow-up needs no
wake word; say nothing and it goes quiet on its own. **Talking over it stops
it mid-sentence** — there is no echo cancellation, so while it speaks its own
voice sets the noise floor and yours has to beat it. That works in a normal
room; headphones make it exact.
**Manual setup: none**, assuming steps 3–5.

### 7. Vision

```bash
pip install opencv-python ultralytics
# set VISION_ENABLED=true in .env
python -m vesper.sensors.vision
```

**Manual setup:**

- **Camera permission** — macOS prompts on first access; System Settings →
  Privacy & Security → Camera if you miss it.
- **`CAMERA_INDEX`** if you have more than one camera. 0 is the built-in.
- **YOLO weights download themselves** (~6 MB for `yolov8n.pt`) on first
  run, but they drag in PyTorch, so `pip install ultralytics` is a few
  hundred megabytes. This is the one stage worth skipping if you only
  wanted a voice assistant.

Detection runs every `VISION_INTERVAL` seconds (default 2), not per frame.
That single number is the difference between a background process and a
space heater.

### 8. Proactive triggers

Already wired — `PROACTIVE_ENABLED=true` in `.env`. A rule firing does not
mean Vesper speaks; it means the brain is woken with the reason and can call
`stay_silent`, which it should do most of the time. `PROACTIVE_COOLDOWN`
(default 120s) is the floor between unprompted remarks.

Add your own rules to `DEFAULT_RULES` in `vesper/core/triggers.py` — a
condition function, a plain-English `why`, and a cooldown.

**Manual setup: none.**

### 8a. Knowing what's going on

```bash
python -m vesper.sensors.news        # fetch once and print the headlines
```

On by default. Headlines are polled every 15 minutes into the world state, so
they ride along with every answer — Vesper knows roughly what today is about
without searching, and without you asking. `NEWS_FEEDS` takes any RSS or Atom
URLs; swap the BBC defaults for whatever you actually read.

A **new** headline matching `NEWS_WATCH` wakes the brain to decide whether it
is worth telling you — and most of the time it should decide no. Empty
`NEWS_WATCH` to keep the awareness but never be interrupted about it.

The clock runs alongside it, so `time_of_day` stays current even with the
camera off. Every prompt also carries the exact date and time.

**Manual setup: none** — RSS needs no key and no account.

### 9a. Your phone

```bash
python -m vesper.server --new-token     # paste the line into .env
python -m vesper.main --serve
```

Opens a small HTTP endpoint so a Siri Shortcut can ask the laptop things and
speak the answer back. **PHONE.md** has the full recipe, including what
still works when the laptop is shut.

**Manual setup: a token** (the command above generates it) and about fifteen
minutes tapping the Shortcut in. The endpoint refuses to start without a
token — it spends your API credit, so it never opens unauthenticated.

### 9b. The 3D map, made intelligent

With `--serve` running, open on any device on your network:

```
http://<your-laptop>:8765/map?t=<your SERVER_TOKEN>
```

The same 3D mainframe, but served by your laptop rather than stored in a
browser tab. Two things follow from that:

- **It is backed by a real file** (`map.json`), not browser storage. It
  survives clearing history and is the same map on every device.
- **Speech goes to the actual model**, not a keyword matcher. Say "plan the
  newsletter launch and put it under Content" and it reads the map, decides
  where things belong, and builds them. Hold any point and talk to dictate
  straight into it.

Vesper can see this map on every question, through `map_read`, `map_add` and
`map_update` — so it knows what you are working on without being told.

If the laptop can't be reached the page says **offline** and falls back to the
old keyword commands, so it still works on a train.

**Manual setup: none beyond step 9a's token.**

### 9. Home Assistant

```bash
# set HA_ENABLED=true, HA_URL and HA_TOKEN in .env
python -m vesper.sensors.home_assistant     # lists your entities
```

**Manual setup: a long-lived token.** In Home Assistant: your profile
(bottom left) → Security → Long-lived access tokens → Create. Set `HA_URL`
to your instance (`http://homeassistant.local:8123`).

Only `light`, `switch`, `binary_sensor`, `lock`, `climate`, `fan`, `cover`
and `media_player` entities are read — a full install exposes hundreds of
sun angles and battery percentages, and none of that belongs in the model's
context. Only `light`, `switch`, `fan` and `input_boolean` can be
*switched*. Locks are deliberately excluded: unlocking a door on a voice
command that might have been the television is not a good trade. Change
`CONTROLLABLE` in `vesper/sensors/home_assistant.py` if you disagree.

---

## How it's put together

```
vesper/
├── main.py                    orchestrator — wake→listen→think→speak
├── config.py                  every setting, loaded from .env
├── harness.py                 run the triggers with no hardware
├── core/
│   ├── world_state.py         thread-safe shared state + change detection
│   ├── triggers.py            the rules that decide when to wake the model
│   └── brain.py               the Claude call and the tool loop
├── sensors/
│   ├── wake_word.py           openWakeWord, always on
│   ├── stt.py                 microphone + faster-whisper
│   ├── tts.py                 Piper or ElevenLabs
│   ├── vision.py              OpenCV + YOLO, throttled
│   └── home_assistant.py      optional REST client
└── tools/
    ├── tool_definitions.py    schemas Claude sees
    └── tool_executor.py       what actually runs
```

**Four decisions worth knowing about**, because they're the ones that make
the difference between this working and this being annoying:

*Reordered detections are not news.* YOLO returns labels in confidence
order, which reshuffles constantly even when the room is perfectly still.
`world_state._same()` compares lists as unordered sets. Without that, every
frame looks like a change and the triggers fire forever.

*Silence is a first-class outcome.* `stay_silent` is a real tool with a real
description telling the model that preferring it is correct. An assistant
that remarks on everything gets switched off within a day.

*One turn at a time.* A single consumer behind a `maxsize=1` queue. A burst
of triggers during a conversation collapses into at most one follow-up, and
Vesper never talks over itself.

*Everything degrades.* No camera, no key, no speakers, no microphone — each
subsystem logs one line explaining itself and switches off. The assistant
starts anyway with whatever is left.

## Cost

Only two things call the API: you speaking to it, and a trigger deciding
something's worth a look. At `VESPER_EFFORT=medium` a typical exchange is a
few thousand tokens. The camera watching an empty room all day costs
nothing, because it never leaves the machine.

## Privacy

Wake word, transcription and detection all run locally — audio and video
never leave your machine. What *does* leave, when the brain is invoked, is
the text of what you said plus the plain-English world summary
(`Snapshot.describe()` — "one unidentified person visible, last motion 40s
ago"). Never images, never audio.

`.env` holds the keys and is git-ignored. `state.json` and
`conversations.jsonl` are local, readable, and yours to delete.

## Adding a tool

Two edits, no framework:

1. A schema in `tool_definitions.py`. Say **when** to call it, not just what
   it does — models reach for tools conservatively, and the trigger
   condition in the description is what actually lifts the call rate.
2. A method on `ToolExecutor` and an entry in `self._handlers`. Return a
   string; never raise — failures come back as error results so the model
   can adapt, which beats an exception killing the turn.

`answer` and `stay_silent` are terminal: calling either ends the turn.
