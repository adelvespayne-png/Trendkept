# Vesper — handoff brief

**Read this first if you are a new session picking up Vesper.** It is
written to be pasted whole into a fresh conversation. Everything here is
current as of 22 August 2026.

---

## 1. What Vesper is

A local-first personal voice assistant, running on the owner's ThinkPad
T480s (i5-8250U, 16GB, 256GB, Windows 11). Not a product — it is *his*
assistant. The Trendkept business is a separate thing that lives in the
same repo; do not confuse them.

- **Code lives in** `personal-vesper/` inside the PUBLIC repo
  `adelvespayne-png/Trendkept`.
- **Branch:** `claude/jarvis-iron-man-2mp2ik`. All work is pushed there.
- **On his machine:** `C:\Users\user\Documents\vesper-assistant`.

### The owner

Non-technical. Explain in plain English, never ask him to read code, and
put anything that matters into a committed file. He is direct and will
tell you when something does not work — take that at face value and go
and measure rather than reassuring him.

Budget: **£30/month**, stated explicitly. He wants it to feel like an
"artificial INTELLIGENCE, not just a simple boring AI".

---

## 2. How work reaches him

There is a three-step loop, and skipping any step means he sees nothing:

1. **Build in the scratchpad copy** — this is the working tree the tests
   run against.
2. **Copy into `personal-vesper/`, commit, push.** Exclude `.env`,
   `map.json`, `memory.json`, `private_seed.json`, all health files, and
   `*.ppn`.
3. **Zip the scratchpad copy and send it with `SendUserFile`.** He
   installs by unzipping over his folder with a one-line PowerShell
   paste, then double-clicking a `.bat`.

**He cannot `git pull`.** The zip is the delivery mechanism.

### The paste line he uses

```powershell
$z = Get-ChildItem "$HOME\Downloads\Vesper*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -First 1; $t = "$HOME\Downloads\_vesper_new"; Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue; Expand-Archive $z.FullName $t -Force; $s = Get-ChildItem $t -Recurse -Filter "Install Vesper.bat" | Select-Object -First 1; Copy-Item "$($s.Directory.FullName)\*" "$HOME\Documents\vesper-assistant" -Recurse -Force; "Updated from $($z.Name)"
```

### The double-click files

| File | What it does |
|---|---|
| `Install Vesper.bat` | Once. Builds `.venv`, writes `.env`. |
| `Vesper.bat` | **Every time.** That black window IS Vesper; closing it stops her. |
| `Tune up Vesper.bat` | Refreshes the map, adds missing `.env` settings, fixes the model ladder. |
| `Check Vesper.bat` | The doctor. Keys, provider chain, a live test of each, and one real turn. |
| `Get Piper.bat` | Installs the better voice. |
| `Hearing test.bat` | Says whether poor listening is the MIC or the SOFTWARE. |
| `_whereami.bat` | Called when run from the wrong folder; finds the real install. |

**Refreshing the browser does nothing.** Settings are read once at start.
He has been caught by this more than once — say "close the black window"
explicitly.

---

## 3. Architecture

```
vesper/
  main.py            the run loop, wake handling, speaking
  launch.py          setup, tuneup, doctor, piper install, costs
  config.py          every setting, read from .env
  providers.py       provider chain, model discovery, User-Agent
  server.py          phone bridge + serves the map page
  mapstore.py        the map (319 nodes), seed, refresh
  address.py         guarantees "sir" once per reply
  core/
    brain.py         the turn: ladder, streaming, tools, memory, depth
    memory.py        semantic / episodic / standing memory  ← NEW
    depth.py         reflex / quick / deep routing          ← NEW
    stream.py        sentence splitting for streaming       ← NEW
    ready.py         speaking first when he arrives         ← NEW
    triggers.py      ambient rules
    redflag.py       health danger classifier
    world_state.py   the room, the clock, sensors
  sensors/
    stt.py           mic, recording, transcription, hearing test
    heard_phrase.py  wake-phrase matching                   ← NEW
    wake_word.py     three wake engines
    tts.py           Windows SAPI / Piper / ElevenLabs
    health.py        wearable baseline
  tools/             the fourteen tools the model can call
  web/map.html       the 3D map page
```

**24 test suites**, all `selftest_*.py`, all must pass:
`for f in selftest_*.py; do python3 "$f"; done`

---

## 4. Current state

### Working

- Speech in and out, conversation with follow-ups, barge-in.
- The map: 319 nodes across five limbs.
- Memory that survives conversations.
- Depth routing — the time and date answer with no model call.
- Streaming: first word at ~35 ms.
- Proactive greeting on arrival.
- Custom wake phrase via the speech recogniser.
- Phone alerts via ntfy.

### His current configuration

- **Google AI Studio key** — format `AQ.…` (this is the NEW valid format,
  see §6).
- **Groq key** — `gsk_…`, working. `FALLBACK_CHAIN=google,groq`.
- **No Anthropic key yet.** He was mid-decision on the £30. This is the
  single biggest quality lever left.
- Voice: Windows SAPI. Piper downloaded but the fix for its crash has not
  been run yet.

### Outstanding

1. **The Anthropic key.** ~£9.46/month for Opus 5 with caching. Prepaid
   credit, not a subscription — buy $25, leave auto-reload OFF and that
   is a hard ceiling.
2. **Piper voice** — crash fixed, `Get Piper.bat` not yet run on a build
   with the fix.
3. **Hearing test** — sent, output not yet seen. Needed to settle whether
   his microphone or the software is the problem.
4. **The private `vesper` repo** — still not created. Everything personal
   is held out of the public repo by hand.
5. **"A few bugs"** he mentioned and we never got to.

---

## 5. Decisions already settled — do not re-litigate

- **The repo is PUBLIC on purpose.** Build-in-public, chosen eyes-open.
- **The Health limb of the map stays OUT of the public repo.** It names a
  real medical condition. It lives in `vesper/private_seed.json`, which
  is git-ignored and ships in the zip. `current_seed()` = public seed +
  that file if present. Deleting it from `SEED` would have made the next
  tune-up sweep it off his laptop, because Health ids are seed-shaped.
- **Health data never leaves the machine and is never committed.**
  Anything dangerous refuses the free gateway rather than downgrading.
- **She calls him "sir", once, in every reply.** Enforced in code
  (`address.py`), not just asked for in the prompt.
- **No vector database for memory.** A second process and dependency on a
  laptop already running a speech model, for a few thousand short lines.
- **Owner-only keys:** money, accounts/secrets, merges to main,
  publishing under his name, legal sign-off.

---

## 6. Mistakes I made — the expensive ones

Recorded because each cost him an evening, and the pattern is the same
every time: **I trusted a written-down fact about somebody else's service
instead of asking the service.**

| What I claimed | The truth |
|---|---|
| OmniRoute is "free, no account, no card" | It is a *router* with no models connected. Useless out of the box. |
| These Gemini model names work | Being in the key's `/v1beta/models` listing does NOT mean usable. `gemini-2.5-flash` 404s as retired. |
| An `AQ.` key is an OAuth token, get an `AIza` one | **Wrong.** `AQ.` is Google's NEW API key format. I sent him hunting for a format his account cannot issue. |
| Use GitHub Models as a second provider | **Retired 30 July 2026.** The whole inference API is gone. |
| Use Picovoice for a custom wake word | Needs a company email — *and* its free tier closed 30 June 2026. |

**Engineering mistakes worth the same care:**

- **Streaming never ran.** The condition was `not tools`, and a real turn
  carries fourteen tools. Written, tested against a tool-less fake, never
  executed on a real question. The test passed because the test was the
  only caller that met the condition.
- **A 429 is per MODEL, not per key.** I abandoned a whole provider on the
  first quota error, so his Pro rungs 429'd and the Flash rung with 1,500
  free requests was never asked. His key worked the entire time.
- **A test asserted a flag, not behaviour**, and passed over a live bug.
- **I told him to run `Select-String GITHUB_TOKEN .env`**, which printed
  the whole secret — and it duly appeared in a screenshot. The doctor now
  answers that question without ever showing the value.

**The rule that came out of it:** verify against the service, or say
plainly that you have not.

---

## 7. Things that bit, and their fixes

Keep these in mind; several took a long time to find.

- **`gemini` contains `mini`.** A substring test called every Google model
  small-tier. Match on whole segments.
- **Groq answered a valid key with a bodyless 403** — Cloudflare refusing
  `Python-urllib`. Every outbound call now sends a real User-Agent.
- **Groq's 413 says `Limit 8000, Requested 10021`** — that is the whole
  arithmetic. Read it and refit rather than guessing; remember the budget
  per endpoint.
- **Piper exits `3221226505`** = `0xC0000409`, a Windows crash. It
  resolves `espeak-ng-data` relative to the WORKING DIRECTORY. Run it with
  `cwd` set to its own folder.
- **Mid-stream, a full stop at the buffer edge is not a sentence end** —
  it is the next character not having arrived. `346.81` split into `346.`
  and `81.`
- **Whisper had never been told "Vesper" is a word.** `initial_prompt`
  with his vocabulary is the cheapest accuracy win available.
- **`.env` is first-occurrence-wins.** A blank line above a filled one
  silently wins.
- **A test that runs at 23:00** will hit quiet hours and look like four
  unrelated failures. Pin the clock.

---

## 8. How she should behave

From `core/brain.py`'s system prompt, and worth preserving:

- Lead with the answer. No preamble, no "great question". Dry and
  understated.
- **Stay in the room after answering** — follow the obvious thread, react
  before reporting, refer back to earlier conversations, have a view when
  asked for one. But only when it earns its place: a closing question on
  every reply is a tic. **Never** "let me know if you need anything else".
- Say "I don't know" when you don't. Disagree when he is wrong about
  something that matters.
- Money, the body and rule changes are always treated as serious.

---

## 9. Where to look first when something is wrong

1. **`Check Vesper.bat`** — keys, chain, a live test of each provider, and
   one real turn through the actual brain. It exists because a bare probe
   passing while real turns failed hid a live bug twice.
2. **`Hearing test.bat`** — mic level versus transcript, reported
   separately.
3. **`Vesper.bat --verbose`** — the log quotes the provider's own words.

Ask for the output rather than guessing. Every time I guessed in this
project I was wrong, and every time I asked for the log I found it in one
round.
