# The 4-week paper-trading test — step by step

This is START_HERE Step 1.4 in full detail: running Trendkept against an
Alpaca **paper** (fake-money) account every trading day for four weeks. It
is quality control, it makes you user #1, and it unlocks the r/swingtrading
launch post — which quotes *your real logs* and is blocked until they exist.

**Paper only.** Never use `--live` during this test. Paper trading uses
Alpaca's fake $100,000 account; no real money exists anywhere in this
process.

## One-time setup (~45 minutes)

### 1. Get the tools onto your computer

1. **Check Python is installed.** Open Terminal (Mac: press Cmd+Space, type
   "Terminal"; Windows: use PowerShell) and type: `python3 --version`
   If it prints "Python 3.9" or higher, you're done. If not, install it
   from python.org (big yellow Download button, default options).
2. **Download the code.** On the GitHub repo page: green **Code** button →
   **Download ZIP** → unzip it somewhere permanent (e.g. Documents). Or, if
   you have git: `git clone <repo URL>`.
3. **Open Terminal in that folder** (Mac: type `cd `, drag the folder onto
   the Terminal window, press enter) and test the engine offline:

   ```bash
   python3 -m trendkept.cli backtest examples/aapl_2015_2017.csv --account 1000 -v
   ```

   Backtest results printing = everything works.

### 2. Create the Alpaca paper account (~15 min)

1. Go to **alpaca.markets** → Sign Up (free; email + password).
2. In the dashboard, make sure you're in **Paper** mode — the account
   switcher (top-left) should say "Paper". It comes pre-loaded with
   $100,000 of fake money.
3. Find **API Keys** on the paper dashboard (right-hand panel) →
   **Generate**. You get two strings: a **Key ID** and a **Secret Key**.
   Copy both immediately — the secret is shown only once. Keys for the
   paper account can't touch real money (there is none).

### 3. Connect Trendkept to Alpaca

In Terminal, replacing the placeholders with your two keys:

```bash
echo 'export APCA_API_KEY_ID=YOUR_KEY_ID' >> ~/.zshrc
echo 'export APCA_API_SECRET_KEY=YOUR_SECRET' >> ~/.zshrc
```

Close and reopen Terminal (that file loads on startup), `cd` back to the
folder, then verify the connection:

```bash
python3 -m trendkept.cli account
```

You should see: `Alpaca account (paper)`, equity ~100,000. That's it — set
up forever. (Windows/PowerShell: use
`[Environment]::SetEnvironmentVariable('APCA_API_KEY_ID','...','User')`
for each key instead, then reopen the window.)

### 4. Pick the test parameters (write them down, then don't touch them)

- **Watchlist:** 15–20 liquid US names. Reasonable default: AAPL MSFT NVDA
  GOOGL AMZN META TSLA AVGO JPM V UNH XOM COST PG HD NFLX AMD SPY QQQ IWM.
- **Risk per trade:** `--risk 0.01` (1% of the account).
- Changing rules mid-test invalidates the test — that's the whole lesson.

## The daily routine (15 minutes, Mon–Fri)

Do it after the US market close — **from ~9pm UK time** — or first thing
the next morning (same daily bars either way). Markets are closed weekends
and US holidays; those days, no routine.

**1. Scan the watchlist (5 min).** Either in the dashboard —
`python3 -m trendkept.web`, open http://127.0.0.1:8181, paste your tickers
into the watchlist box — or per-symbol in the CLI:
`python3 -m trendkept.cli scan --symbol AAPL --provider alpaca --account 100000 --risk 0.01`

**2. If (and only if) a symbol shows an entry SIGNAL (2 min each):**

```bash
# Dry run first — prints the exact order, sends nothing:
python3 -m trendkept.cli trade AAPL --risk 0.01
# Looks right? Send it to the PAPER account:
python3 -m trendkept.cli trade AAPL --risk 0.01 --confirm
```

The order goes in as entry + protective stop together — rule #3, enforced
by the broker. Most days there is no signal. **Do nothing on those days.**

**3. Manage whatever is open (2 min):**

```bash
python3 -m trendkept.cli manage            # dry run: shows what it would do
python3 -m trendkept.cli manage --confirm  # do it (raise stops / exit breaks)
```

**4. Log the day (2 min).** One row, even (especially) for "nothing" days —
the no-action count is the launch post's headline finding. **The official
log is the spreadsheet `business/paper_log.csv`** (opens in Excel; GitHub
shows it as a table in the browser). You don't have to type into it
yourself: photograph your dashboard/Alpaca screen, send the photo to your
Claude session, and the row gets entered for you. The columns:

```markdown
| Date | Action | Symbol | Signal | Entry | Stop | Shares | Exit/R | Followed rules? | Note |
|---|---|---|---|---|---|---|---|---|---|
| 2026-07-13 | none | — | no signals on 19 tickers | | | | | Y | |
| 2026-07-14 | enter | NVDA | breakout | 182.40 | 171.10 | 88 | | Y | stop = swing low −0.5% |
| 2026-07-21 | stop hit | NVDA | | | | | −1.0R | Y | gap through stop, filled lower |
```

## The weekly close-out (Sunday, 10 min — same sitting as the newsletter)

- Run `python3 -m trendkept.cli account` and note equity + open positions.
- Count the week's log rows: trading days, signals, entries, exits.
- Screenshot the dashboard once a week — future launch material.

## What four weeks buys you

After ~20 trading days you can fill every bracket in
`business/launch/reddit_swingtrading.md` with literal truth: [N] weeks,
[X] valid entries across [Y] tickers in [N×5] days, a real entry/stop/size
example from the log, and what following the rules actually felt like. You
will also have found any rough edges in the product before a paying
customer does — report them to your Claude session as you hit them.

**The rules of the test itself** (the meta-discipline):

1. The rules decide; you execute. No overrides, no "just this once".
2. A missed day is logged as a missed day — honesty includes the log.
3. Paper only. `--live` does not exist for you this month.
4. If you *disagree* with a rule by week 4, that's a finding — write it
   down and raise it; don't silently change the config mid-test.
