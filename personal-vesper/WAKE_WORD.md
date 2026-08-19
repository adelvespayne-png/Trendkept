# Making it answer to "hey Vesper"

Everything else about this assistant was renamed by editing text. The wake
word cannot be, and it is worth understanding why before you spend an hour
on it.

## Why it is not just a setting

The wake word is the one part that listens all the time. For that to be
practical it has to be tiny, run on your own machine, and cost nothing — so
it is not speech recognition. It is a small neural network trained on one
specific phrase, which does nothing but answer "did I just hear that
sound?" thousands of times a minute.

That means a phrase exists only if somebody has trained a model for it.
openWakeWord ships four:

| Set `WAKE_MODEL=` | You say |
|---|---|
| `hey_jarvis` | "hey Jarvis" — the default, closest thing to a name |
| `hey_mycroft` | "hey Mycroft" |
| `hey_rhasspy` | "hey Rhasspy" |
| `alexa` | "Alexa" |

There is no "hey Vesper", because Vesper is a name we made up last week.
To get one, you train it. It is free and you do not need to write any code,
but it is an hour of waiting rather than a line in a config file.

Check what you are currently set to:

```
python -m vesper.sensors.wake_word --list
```

## What it costs

Free. About 60–90 minutes, nearly all of it waiting. No account beyond a
Google login, and no ongoing cost — the result is a file on your laptop.

You are not recording yourself hundreds of times. The training generates
thousands of synthetic voices saying "hey Vesper" in different accents,
speeds, and background noise, and trains against those. Your own voice is
optional.

## How to do it

1. Open the openWakeWord training notebook in Google Colab. The official
   one from the openWakeWord project has bit-rotted and fails out of the
   box, so use a maintained 2026 fork —
   `github.com/alfiedennen/openwakeword-colab-2026` is the one to start
   with. Search for "openWakeWord colab 2026" if that has moved on.

2. In the notebook, set the target phrase to **hey vesper** (lower case,
   two words). Leave everything else alone the first time.

3. Runtime → Run all. Then leave it. It generates the synthetic speech,
   downloads background noise, and trains. On the free Colab tier expect
   around 90 minutes; it will sit apparently idle for long stretches, which
   is normal.

4. At the end it produces **`hey_vesper.onnx`**. Download it.

5. Put that file in the same folder as this README, and in your `.env`:

   ```
   WAKE_MODEL=hey_vesper.onnx
   ```

6. Test it before trusting it:

   ```
   python -m vesper.sensors.wake_word
   ```

   Say "hey Vesper" from where you normally sit — across the room, not
   leaning into the laptop. It prints a line each time it hears you.

## If it does not hear you

Adjust `WAKE_THRESHOLD` in `.env`, then re-run the test above:

- **Missing you** — lower it, `0.4` or `0.35`. More sensitive.
- **Firing at the television** — raise it, `0.6` or `0.7`.

A custom model is usually a little less accurate than the shipped ones,
which were trained much harder. If yours is disappointing, the usual fix is
to re-run the notebook with more training steps rather than to fight the
threshold.

If it hears nothing at all, check the microphone before blaming the model:

```
python -m vesper.sensors.stt --devices
python -m vesper.sensors.stt --level
```

## Not falling back, on purpose

If the file is missing or will not load, the wake word **stops** and tells
you why. It does not quietly load the built-in phrases instead.

That is deliberate. The fallback would listen for "hey Jarvis" while you
sat there saying "hey Vesper", with nothing on screen to explain it. A
clear stop costs you a minute; a silent wrong phrase costs you an evening.

## If you would rather not bother

Perfectly reasonable — an hour for one word. The alternatives:

- **Leave it on `hey_jarvis`.** The assistant is still Vesper everywhere
  else; only the two syllables that wake it are borrowed.
- **Use one of the other three.** "Alexa" is the most reliably trained of
  them, if you have no Amazon device to confuse.
- **Skip the wake word.** `WAKE_ENABLED=false`, then talk to it from your
  phone (PHONE.md) or type with `--text`. Nothing else changes.
