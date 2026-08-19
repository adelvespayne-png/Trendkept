# Jarvis on your phone

You say **"Hey Siri, Jarvis"**, speak, and it answers out loud. Screen off,
hands free, from anywhere.

There are two Jarvises behind that one phrase, and it's worth knowing which
one you're talking to:

| | **Home Jarvis** | **Pocket Jarvis** |
|---|---|---|
| When | Laptop awake | Laptop shut or away |
| Can | Everything: reminders, weather, the camera, the lights, memory of past conversations | Answer questions, and that's it |
| Can't | — | See the room, switch anything, remember yesterday |
| Costs | Your API credit | Your API credit |

**Why the split is real and not laziness:** the camera is plugged into the
laptop. The reminders file is on the laptop's disk. When the laptop is shut,
those things don't exist to ask. No amount of code moves a webcam into your
pocket. What Pocket Jarvis gives you is the voice and the thinking; what it
can't give you is the house.

If you want the full Jarvis reachable at all times, the honest fix is
hardware, not software — see *Always-on* at the bottom.

---

## Part 1 — Open the door on the laptop (10 minutes)

**1. Make a token.** In Terminal, in the `jarvis-assistant` folder:

```
python -m jarvis.server --new-token
```

It prints a line like `SERVER_TOKEN=xK9...`. Open `.env` and paste it in.
Add this line too:

```
SERVER_ENABLED=true
```

> This token is the only thing standing between your API credit and anyone
> else on the wifi. Don't shorten it, don't reuse a password, don't post it.
> Jarvis refuses to open the endpoint at all if the token is missing or under
> 16 characters.

**2. Find the laptop's address.**

```
python -m jarvis.server
```

It prints something like `192.168.1.24`. Write it down — that's the laptop
on your home network.

**3. Start Jarvis with the door open:**

```
python -m jarvis.main --serve
```

You'll see `Phone bridge: http://192.168.1.24:8765`.

**4. Test it from the phone.** Same wifi, open Safari, go to
`http://192.168.1.24:8765` — you'll get "bad or missing token". That error is
the good outcome: the laptop is reachable and it's refusing strangers.

## Part 2 — Build the Shortcut (15 minutes of tapping)

Open **Shortcuts** → **+** → name it exactly **Jarvis** (that's the phrase
Siri will listen for).

Add these actions in order. Search the name in the action list, tap to add.

**1. Dictate Text**
   Tap *Show More* → Stop Listening: **After Pause**

**2. Get Network Details**
   Change the dropdown to **Wi-Fi Network Name**

**3. If**
   Condition: **is** — value: your home wifi name, exactly as it appears

Everything up to *Otherwise* is the home path:

**4. Text** (inside the If)
   Paste exactly, replacing nothing but the words in CAPITALS — and put the
   *Dictated Text* variable where it says `DICTATED`:
   ```
   {"text": "DICTATED"}
   ```

**5. Get Contents of URL** (inside the If)
   - URL: `http://192.168.1.24:8765/ask` *(your address from Part 1)*
   - Method: **POST**
   - Request Body: **File**, and pass the **Text** from step 4
   - Headers:
     - `Authorization` → `Bearer YOUR_TOKEN_HERE`
     - `Content-Type` → `application/json`

**6. Get Dictionary Value** (inside the If)
   Get **Value** for key `reply`

Now tap **Otherwise** — this is the pocket path:

**7. Text** (after Otherwise)
   ```
   {"model":"claude-opus-5","max_tokens":1000,
    "thinking":{"type":"disabled"},
    "output_config":{"effort":"medium"},
    "system":"You are Jarvis, a voice assistant. Everything you say is read aloud: one or two sentences of plain spoken English, no lists, no markdown. Lead with the answer. Dry and understated. If you don't know, say so in one sentence.",
    "messages":[{"role":"user","content":"DICTATED"}]}
   ```
   Again, put the *Dictated Text* variable where `DICTATED` is.

**8. Get Contents of URL** (after Otherwise)
   - URL: `https://api.anthropic.com/v1/messages`
   - Method: **POST**
   - Request Body: **File**, passing the **Text** from step 7
   - Headers:
     - `x-api-key` → your Anthropic API key
     - `anthropic-version` → `2023-06-01`
     - `Content-Type` → `application/json`

**9. Get Dictionary Value** — Value for key `content`
**10. Get Item from List** — **First Item**
**11. Get Dictionary Value** — Value for key `text`

Tap **End If**, then after it:

**12. Speak Text** — pass the result

Tap **Done**. The Shortcut is built.

## Part 3 — Launching it without saying "Hey Siri"

iOS does not let any app register its own wake word. "Jarvis" alone, from a
locked pocket, is not possible on an iPhone — that's Apple's rule, not a gap
in this build. What *is* possible is launching it without speaking first.

**Back Tap — the good one. Works on iPhone 8 and later, including the 13.**

Settings → Accessibility → Touch → scroll to the very bottom → **Back Tap**
→ **Double Tap** → scroll down to the Shortcuts list → tap **Jarvis**.

Now double-tap the back of the phone and talk. No wake phrase, no unlocking,
works through a jacket pocket. A very thick case can muffle it; try Triple
Tap instead if doubles get missed.

**Other ways in:**

- **Lock Screen widget** — press and hold the lock screen → Customise → add
  a **Shortcuts** widget → pick Jarvis. One tap, no unlock.
- **Home Screen icon** — in Shortcuts, tap ⓘ → *Add to Home Screen*.
- **Just "Siri"** — on iOS 17 and later you can drop the "Hey": Settings →
  Apple Intelligence & Siri → *Listen for* → **"Siri"**. Then it's
  "Siri, Jarvis". Two words rather than three.
- **Action Button** — squeeze to launch, but that's iPhone 15 Pro and newer.
  Not the 13.

**Try it:** double-tap the back → "what's the weather in Bristol?"

> **Want to genuinely just say "Jarvis"?** That works today at the laptop —
> the wake word in this build is real and local, no Siri involved. For the
> whole house, put it on a Raspberry Pi with a USB microphone (~£70) and the
> phone stops being part of the story. See *Always-on* below.

> **Why `"thinking":{"type":"disabled"}` in step 7 and not on the laptop?**
> With thinking on, the reply comes back as several blocks and step 10 would
> grab the wrong one. Shortcuts is bad at picking through JSON, so the pocket
> path asks for one plain block. The laptop path keeps thinking on — it has
> real code to parse the answer.

## Keeping the laptop awake

The home path only works while the laptop is on and awake. On macOS, run
this in a second Terminal window and leave it:

```
caffeinate -s
```

Closing the lid still sleeps it unless you have an external display. If you
want Jarvis reachable with the lid shut, that's the *Always-on* section.

## Reaching it from outside the house

The wifi-name check sends you to Pocket Jarvis the moment you leave. To get
Home Jarvis from anywhere:

1. Install **Tailscale** (free) on both laptop and phone, same account.
2. Tailscale gives the laptop a permanent address like `100.x.y.z` that works
   from anywhere.
3. In the Shortcut, change step 5's URL to that address. Leave everything
   else alone — the wifi check now just decides which address to try, and
   you'll reach Home Jarvis on mobile data too.

Once that works you can simplify: delete the If/Otherwise and steps 7–11
entirely, so the Shortcut is only ever the home path. Keep the pocket path
if you want an answer even when the laptop is off.

Tailscale is a private link between your own devices — it doesn't put the
endpoint on the public internet, which is exactly what you don't want with a
key that spends money.

## Always-on (the honest fix)

If what you actually want is full Jarvis with the laptop shut in a drawer,
you need something at home that never sleeps:

- **A Raspberry Pi 5** (~£60–80). Runs the whole thing including the camera.
  Plug it in once, forget it.
- **An old laptop** left on a shelf, lid open, plugged in. Free if you have one.

Either becomes the always-on Jarvis; your daily laptop and your phone both
just talk to it. That's a build I can do whenever you want the hardware.

**What I'd steer you away from:** renting a cloud server. It costs monthly,
it puts your assistant on the public internet, and the camera and lights are
at your house anyway — so it'd be a more expensive Pocket Jarvis, not a Home
one.

## If it doesn't work

| What you see | What it means |
|---|---|
| "bad or missing token" | The `Authorization` header is wrong. It needs the word `Bearer`, a space, then the token |
| Shortcut hangs, then errors | Laptop is asleep, or you're not on home wifi. Check `caffeinate` |
| Works at home, not away | Expected — that's the Otherwise path. Check your API key is in step 8 |
| Siri opens the app instead of running it | Rename the Shortcut to one clear word: **Jarvis** |
| Back Tap doesn't fire | Thick case. Use Triple Tap, or tap nearer the Apple logo |
| Speaks JSON at you | Step 10 or 11 is wrong — it's reading the whole response instead of the text |

To watch what the laptop sees, run it with `python -m jarvis.main --serve
--verbose` and every request from the phone prints.
