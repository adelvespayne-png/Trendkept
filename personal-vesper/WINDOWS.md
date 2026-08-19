# Setting up on Windows (Surface Pro)

Start to finish. Times are honest, not optimistic.

**Read this first:** stages 1 and 2 get you a working assistant in about
twenty-five minutes, and cost nothing — no card, no API key. Stages 3 and 4
are optional and add one thing each. Stop whenever you have enough; nothing
later is needed for anything earlier.

Every command goes in **PowerShell**. Open it with Win+X → *Terminal*.

---

## Stage 1 — the brain (~10 min)

Vesper ships set to run on free providers, so this comes first: OmniRoute
*is* the brain. No account, no card, no key.

### 1. Install Node

```powershell
winget install OpenJS.NodeJS.LTS
```

**Close PowerShell and open a new one** — the installer changes your PATH and
the old window won't see it.

### 2. Install and start OmniRoute

```powershell
npm install -g omniroute
omniroute
```

Leave that window running. You should see *"OmniRoute is running!"* and a
dashboard at http://localhost:20128.

> From now on you need **two** PowerShell windows: this one for OmniRoute,
> another for Vesper.

---

## Stage 2 — the assistant (~15 min)

### 1. Install Python

Download from [python.org/downloads](https://www.python.org/downloads/).

> **Tick "Add python.exe to PATH"** on the first screen of the installer.
> It's easy to miss and everything else fails without it.

Check it took:

```powershell
python --version
```

Anything 3.10 or newer is fine.

### 2. Unzip Vesper somewhere sensible

`Documents\vesper-assistant` is fine. Avoid OneDrive folders — the sync can
lock files while Vesper is writing them.

### 3. Set it up

```powershell
cd $HOME\Documents\vesper-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of your prompt. Nothing to `pip install`
yet — the free chain needs no packages at all.

If `Activate.ps1` is blocked with a script-execution error, run this once and
try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 4. Settings

```powershell
Copy-Item .env.example .env
```

That's it — no key to paste. The shipped settings run on OmniRoute, free.

> `ANTHROPIC_API_KEY` stays **blank**. Claude Pro does not cover the API;
> they are separate purchases. Leave it empty and nothing can ever bill you.

### 5. Talk to it

```powershell
python -m vesper.main --text
```

Type at it. **Checkpoint:** ask it *"what can you do?"* and then
*"add test to personal"* — if it answers and confirms the addition, everything
is working: it thinks, searches, reads pages, remembers, and keeps your map.

If it says nothing, OmniRoute isn't running. Check the other window.

**Whenever you come back to it, the two lines are:**

```powershell
cd $HOME\Documents\vesper-assistant
.\.venv\Scripts\Activate.ps1
```

---

## Stage 3 — voice (~25 min)

```powershell
pip install sounddevice numpy faster-whisper openwakeword onnxruntime
```

No PortAudio step here — unlike Mac and Linux, the Windows `sounddevice`
wheel bundles it.

### Speech out

Piper is a program, not a pip package.

1. Download `piper_windows_amd64.zip` from
   [github.com/rhasspy/piper/releases](https://github.com/rhasspy/piper/releases).
2. Unzip it to `C:\piper`.
3. Get a voice from
   [Hugging Face](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_GB/alan/medium)
   — you need **both** files: `en_GB-alan-medium.onnx` and
   `en_GB-alan-medium.onnx.json`. Put them side by side in `C:\piper`.
4. In `.env`, set the full path:

```
PIPER_MODEL=C:\piper\en_GB-alan-medium.onnx
```

5. Add Piper to your PATH for this session and test:

```powershell
$env:Path += ";C:\piper"
python -m vesper.sensors.tts "Speech output is working."
```

To make that permanent: Win → "environment variables" → *Edit environment
variables for your account* → `Path` → New → `C:\piper`.

No player to install — Vesper uses Windows' own audio.

### Speech in

```powershell
python -m vesper.sensors.stt
```

Speak when it waits; it prints what it heard. Windows will ask for microphone
permission the first time — say yes. If it doesn't ask and nothing is heard:
Settings → Privacy & security → Microphone → turn on *Let desktop apps access
your microphone*.

The Whisper model downloads itself on first use (~150 MB), so the first run is
slow. On a Surface, if it feels sluggish, set `STT_MODEL=tiny.en` in `.env`.

### The wake word

```powershell
python -m vesper.sensors.wake_word
```

Say "hey Vesper". It prints a line each time it hears you. Then run the real
thing:

```powershell
python -m vesper.main
```

---

## Stage 4 — your phone (~20 min)

### On the Surface

```powershell
python -m vesper.server --new-token
```

Paste the printed line into `.env`, and add `SERVER_ENABLED=true`.

Find the Surface's address on your wifi:

```powershell
python -m vesper.server
```

Then start everything:

```powershell
python -m vesper.main --serve
```

**Windows Firewall will pop up the first time.** Tick **Private networks** and
allow it, or your phone can't reach it. If you clicked the wrong thing:

```powershell
New-NetFirewallRule -DisplayName "Vesper" -Direction Inbound `
  -LocalPort 8765 -Protocol TCP -Action Allow -Profile Private
```

### The 3D map

On the Surface or your phone, same wifi:

```
http://<the address>:8765/map?t=<your token>
```

That is the intelligent map — talk to it and it answers with the real model.

### The Shortcut

Follow **PHONE.md**, Parts 2 and 3. It's the same on Windows; only the address
differs. Part 3 sets up Back Tap so you don't need Siri.

### Keeping it awake

A sleeping Surface can't answer your phone.

Settings → System → Power & battery → Screen and sleep → set **"When plugged
in, put my device to sleep after"** to *Never*.

---

## When the new laptop arrives

Copy four files across and you have everything, exactly as it was:

| File | What it is |
|---|---|
| `.env` | your settings |
| `map.json` | your whole project map |
| `conversations.jsonl` | what it remembers |
| `reminders.jsonl` | your reminders |

Then repeat stage 1 on the new machine and drop those files in. Nothing is
tied to the Surface.

---

## If something breaks

| What you see | What it means |
|---|---|
| `'python' is not recognized` | PATH box wasn't ticked. Re-run the installer, choose *Modify*, tick it |
| `Activate.ps1 cannot be loaded` | Run the `Set-ExecutionPolicy` line above, once |
| Speech gets printed, not spoken | Piper isn't on PATH, or `PIPER_MODEL` isn't the full path to the `.onnx` |
| Nothing heard from the mic | Settings → Privacy → Microphone → allow desktop apps |
| Phone can't reach the Surface | Firewall — allow on Private networks. Both devices on the same wifi |
| Works, then stops when you walk away | The Surface went to sleep. See *Keeping it awake* |

`python -m vesper.main --check` lists every subsystem, on or off, with the
exact fix for each. It is the first thing to run when something is wrong.

---

## What I could not test

I wrote and checked this on Linux; I have no Windows machine to run it on. So
the code is Windows-*correct* rather than Windows-*proven*, and two things in
particular were found by reading rather than running:

- **`audioop` was removed in Python 3.13.** Speech input imported it, so a
  fresh Windows install today would have crashed on startup. Replaced with
  standard-library arithmetic.
- **None of the audio players existed on Windows** (`paplay`, `aplay`,
  `afplay`, `ffplay` are all Unix), so speech would have silently fallen back
  to printing. Playback now goes through Windows' own audio.

Both fixes are in this build. If you hit something else, tell me what the
error says and I'll fix it properly rather than guess.
