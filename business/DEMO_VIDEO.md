# The 60-second demo video — shot list

**Why:** the site *describes* the product; it doesn't *show* it. One short
clip at the top of the landing page and the README does more than three
paragraphs. It's also the asset a Show HN post needs later.

**Claude cannot edit video** (no ffmpeg in the build environment). Claude
writes the script, captions and the post; the owner records and cuts.

---

## Before you record

1. **Make the terminal readable.** Font size up to ~18–20pt. Dark background.
   Full screen. Nobody can read a 12pt terminal on a phone.
2. **Clear the screen** between shots (`clear`).
3. **Close everything else** — no notifications, no other tabs, no email.
4. **Record at 1080p minimum.** Built-in tools are fine:
   - Mac: QuickTime → File → New Screen Recording
   - Windows: Win+G (Xbox Game Bar) or Win+Alt+R
5. **No voiceover.** Captions instead — most people watch muted, and you
   avoid re-recording every stumble.

## The hard rule

**Do not cherry-pick a winning run.** If the journal shows losses, show the
losses. The entire differentiator is that the numbers are real. A staged
green screen would destroy the one thing the brand has.

---

## Shot list — 60 seconds

### Shot 1 · 0:00–0:08 · The board
```
python -m trendkept.cli scan --symbol AAPL --account 1000
```
Let the output sit on screen. It will usually say *no entry*.

> **Caption:** "Most days it says: do nothing."

*Why this first: it's the anti-hype opening. Nobody else leads with "no trade".*

---

### Shot 2 · 0:08–0:22 · The dashboard
```
python -m trendkept.web
```
Open the browser, show the watchlist page, scroll slowly once. Click one
symbol to show its rules view.

> **Caption:** "Your rules, applied to 20 tickers, every day."

---

### Shot 3 · 0:22–0:38 · The honest backtest
```
python -m trendkept.cli backtest --symbol AAPL --account 1000 --risk 0.02
```
Hold on the results block. Do not scroll past the drawdown.

> **Caption 1:** "A backtest that can't peek at the future."
> **Caption 2 (over the drawdown line):** "Drawdown shown as loudly as the return."

---

### Shot 4 · 0:38–0:52 · The real account
Best option — show the public log on GitHub:
`business/paper_log.csv`, scrolled to the recent rows.

Or, if broker keys are set up locally:
```
python -m trendkept.cli journal
```

> **Caption 1:** "A paper account the rules have flown since July."
> **Caption 2:** "Currently down ~7%. Every loss capped in advance."

*This is the shot that earns trust. Do not skip it and do not sanitise it.*

---

### Shot 5 · 0:52–1:00 · The close
Static frame — the site, or a plain title card.

> **Caption:** "Trendkept — open source. No predictions.
> trendkept.com"

---

## Editing

Free and quick: **CapCut** (any platform), **iMovie** (Mac),
**Clipchamp** (built into Windows).

- Cut every pause and every typo. Nothing dead.
- Speed up any waiting to 2–4×.
- Captions large, high contrast, bottom third.
- **No music**, or something very quiet. This is a tool, not a trailer.
- Export 1080p MP4.

## Where it goes

1. Top of `site/index.html`, above or beside the hero.
2. Top of `README.md`.
3. Held back for the Show HN post.
4. **Not** posted to Reddit as a standalone promo while the account is new.

## Caption for when it is posted

> Built a tool that runs a written trend-following ruleset over 20 tickers,
> sizes each trade off risk, and sends the stop with the entry. It's been
> flying a paper account since July — currently down about 7%, every loss
> capped, all of it public. Open source, no predictions.
