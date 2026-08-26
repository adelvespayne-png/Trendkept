# Trendkept — full handoff (2026-08-26)

Paste this into a new chat. It is the complete picture: what the business is,
what is built, what is decided, what is broken, and what happens next.
**The repo is the memory** — every important fact lives in a committed file.

---

## 1. Who and what

- **Owner:** Archie (adelvespayne@icloud.com), UK, **non-technical**. Explain in
  plain English. Build things for him; never ask him to touch code.
- **Product:** Trendkept — an open-source, stdlib-only **trend-following
  toolkit** (engine, CLI, local dashboard, trade journal) plus a paid tier
  ("Trendkept Pro", £12/mo or £99/yr) that runs the ruleset on the user's own
  broker account, local-first.
- **What it sells:** *enforcement of discipline* — sizing from risk, the stop
  attached to the entry, trailed daily, journalled in R-multiples.
  **Not predictions. Not signals. Not returns.**
- **Live:** trendkept.com (Cloudflare Worker serving `site/`, tracks `main`),
  repo public at github.com/adelvespayne-png/Trendkept, newsletter
  "The Trend Check" on Buttondown (slug `trendkept`, lowercase).
- **Repo is FULLY PUBLIC by deliberate decision** — code, business plan,
  financials, and the paper-trading log including every loss. Build-in-public
  is the strategy. Nothing secret is in the repo; control (merges, secrets,
  accounts) stays owner-only.

## 2. Division of labour

Claude does **all** building, committing and pushing. The owner does only
identity-bound things: **merging PRs, posting under his name, pressing Send,
holding secrets/accounts.** Claude cannot read Alpaca directly (keys are
GitHub secrets) — it sees only what the robots report and what he screenshots.

Workflow: branch → PR → owner merges → `main`.
Branch: `claude/business-plan-ownership-8m18uu`.

## 3. Hard rules — settled, do not relax

1. **Honesty in all public content.** Every claim must be literally true of
   the owner on posting day. No invented trading history.
2. **Compliance:** descriptive, never imperative ("trend filter no longer
   met", never "get out"). No return promises, no gain screenshots, no
   per-person buy/sell language. FCA bright line. See `business/LEGAL.md` §2.
   **This applies in DMs and private messages too, not just broadcast.**
3. **Validate before spending:** ~£10 of validation before ~£100 incorporation,
   before any monthly burn.
4. **Local-first privacy:** broker keys never leave the user's machine.
5. **Model honesty:** change `business/model.py`, regenerate `FINANCIALS.md`,
   update docs that quote numbers, rebuild the manual.
6. **No prediction, no per-trade auto-tuning.** Both were asked for and
   refused; the honest versions are backtest variant comparison and journal
   insights at 20+ real trades. Review monthly, never per-trade.

## 4. Where things live

| Path | What |
|---|---|
| `business/START_HERE.md` | the owner's do-this-now sequence |
| `business/PLAN.md` | strategy, roadmap, trajectory gates (§9) |
| `business/REVIEW_PROTOCOL.md` | **when the rules may change, and how** |
| `business/THREE_WARM_YESES.md` | the £12 demand test: scripts, scoring, where to send |
| `business/paper_log.csv` | **the official public paper-trading log** |
| `business/LEGAL.md` | FCA line, US perimeter, market-data licensing |
| `business/model.py` | financial model; `--md` regenerates FINANCIALS.md |
| `business/launch/` | ready-to-post drafts (essays, Show HN, reddit, welcome email) |
| `trendkept/strategy.py` | the rules, as causal signals |
| `trendkept/backtest.py` | single-symbol backtester |
| `trendkept/portfolio.py` | **portfolio backtester + strategy lab variants** |
| `trendkept/paper_log.py` | auto-writes the log from each pass |
| `trendkept/cli.py` | CLI incl. `autopilot`, `journal`, `lab` |
| `trendkept/web.py` | local dashboard, "My Trading Diagram" |
| `.github/workflows/` | paper-pilot, strategy-lab, trend-check-draft, tests |

Tests: `python -m unittest discover -s tests` — **166 passing**. Don't quote a
hardcoded count in docs; it drifts.

## 5. The robots (all running unattended)

1. **Paper autopilot** — weekdays 21:30 UTC (GitHub queues it ~22:30). Manages
   positions, then takes cash-limited entries with GTC stops. **Paper only by
   construction — there is no `--live` flag.** Max 4 positions. Opens a GitHub
   issue when it acts; quiet passes stay silent.
2. **Auto-logger** — writes each pass into `paper_log.csv`, commits, pushes.
   Append-only, idempotent per date, marks rows `[auto]`, **never invents
   prices** (fills happen next open, so price columns stay blank).
3. **Trend Check drafter** — Saturdays, posts a paste-ready newsletter issue.
4. **Strategy lab** — manual + monthly on the 1st. Read-only variant
   comparison on real Alpaca data with an out-of-sample split.
5. **Tests** — CI on push.

## 6. The strategy, exactly

Long-only, mechanical, causally-backtestable trend-following:
- **Trade only confirmed uptrends:** close above the 50- and 200-day SMA, MAs
  aligned, higher highs and higher lows.
- **Enter** on a pullback toward the 50-day MA, or a breakout above a 20-day
  high. Never chase (skip if >12% extended above the 50-day).
- **Stop** just below the last confirmed swing low, attached to the entry, GTC.
- **Trail** the stop up under each new swing low. It only ever rises.
- **Exit** on trend break: close below the 50-day MA, or a lower low.
- **Size:** `shares = (equity × 1%) ÷ (entry − stop)`. No conviction knob.

Watchlist (20): AAPL MSFT NVDA GOOGL AMZN META TSLA AVGO JPM V UNH XOM COST PG
HD NFLX AMD SPY QQQ IWM.

## 7. Paper test — state as of 2026-08-26

Started 2026-07-13 with **$100,000** paper. Day 31 of the log.

**Open positions**
- **V** — 45 sh @ 362.8547, last 384.06, **+$954 unrealised**, stop **356.60**
  (now *above* entry: profit is locked in). This is the first real winner.
- **JPM** — 198 sh @ ~356.42, stop 351.72.

**Closed trades (8): 7 losses, 1 scratch, 0 winners.** Realised ≈ **−$5,976
(−5.80R)**.

| Trade | P/L | R | note |
|---|---|---|---|
| NVDA | −431 | −0.44 | |
| SPY #1 | +23 | +0.02 | scratch |
| SPY #2 | −828 | −0.89 | |
| PG | −1,004 | −0.90 | |
| UNH #1 | −1,082 | −1.02 | |
| AAPL | −1,624 | **−1.57** | **gapped 4.2% through its stop** |
| UNH #2 | −1,029 | −1.00 | |
| AMZN | ~flat | — | fill unconfirmed |

**Equity ≈ $93,557** (24 Aug pass) — about **−6.4%**. The −10% review gate has
never been hit.

**Why the drawdown:** the market has offered nothing. Scans have read **0–3 of
20 in a confirmed uptrend** for six weeks. A trend-follower with no trends
takes small capped losses and waits. That is the designed behaviour.

## 8. Bugs found and fixed (all with regression tests)

1. Day-order stop expired overnight → default `tif="gtc"`.
2. Double-exit HTTP 403 → skip when a sell is already pending.
3. Sub-penny stop raise HTTP 422 → full-penny threshold + try/except.
4. Newsletter robot got 403 from free data providers in CI → route via Alpaca.
5. Silent scan loop → **scan tally** printed every pass ("18 of 20 checked…").
6. **R-multiple divided by the *trailed* stop** in the lab, corrupting every
   expectancy figure and the lab's verdict → `initial_stop` kept separate.
7. **False "UNPROTECTED POSITION"** when a position was mid-exit → roll-call
   now skips symbols with a queued sell. *(fix is in open PR #43)*
8. Paper log CSV wasn't quoted → notes with commas broke parsing → rewritten.

## 9. ⚠️ OPEN ISSUE — position sizing caps risk but not capital

Found 2026-08-26. JPM's stop was tight (4.70/share), so 1% risk meant **198
shares = $70,571 = 75% of the account.** Cash fell to ~$6,600, and the next
day the pass reported:

```
SPY: signal, but cost 93,426 exceeds cash 5,672 — skipped (no margin, ever).
IWM: signal, but cost 75,709 exceeds cash 5,672 — skipped (no margin, ever).
```

The 1% risk rule was respected exactly. But **capital deployed is uncapped**,
so one tight-stop trade can eat the account and block every other signal. The
4-position cap does not help — this is a *cost* cap problem, not a count
problem. Candidate fix: cap position cost at ~25–30% of equity (i.e.
`shares = min(risk_size, cost_cap ÷ entry)`). **Must be backtested in the lab
before shipping** (REVIEW_PROTOCOL §5).

## 10. The review protocol (pre-committed, do not move the goalposts)

`business/REVIEW_PROTOCOL.md`. Key points:

- **The paper account can never prove the strategy works.** At a realistic
  edge (+0.2R, SD 1.6R) you need ~250 trades — 2–3 years. It can only detect
  **execution faults** and **divergence from backtest**.
- **Execution faults** → fix immediately, always.
- **Drawdown gates:** −5% note · **−10% formal review** · −20% halt new entries.
- **Divergence test** at 30 closed trades, not sooner.
- **Forbidden:** tightening stops after a loss, skipping signals, chasing,
  changing anything per-trade or mid-drawdown on the live sample.
- **Permitted:** a change backed by a decades-long backtest with an
  out-of-sample split.

## 11. The strategy lab

`python -m trendkept.cli lab` (read-only; no broker call in that path).
Pulls 10 years for 50 tickers via Alpaca, runs 13 variants, splits
in-sample/out-of-sample, posts an issue.

**Hypotheses, each from something observed live:**
- **H1 cooldown** (5/10d) — SPY and UNH were re-entered immediately after
  being stopped out.
- **H2 breadth filter** (≥15/25/40% of universe in uptrends) — scans read
  0–3 of 20 for weeks.
- **H3 stop distance** (8%, 12%).
- **H4 diversified universe** — the current 20 are effectively **one bet**
  (13 of 20 are US mega-cap tech or tech-dominated indices). `EXTENDED` adds
  30 liquid ETFs: bonds, metals, commodities, international, all US sectors,
  REITs, USD.

**Guards:** out-of-sample split; a variant must beat baseline on **both
expectancy and return, on both slices**; under 30 baseline trades it prints
NOT ENOUGH DATA; a **parity test** asserts the fast precompute path matches
the live strategy bar-for-bar.

**Status: the first run (issue #33) is VOID** — it predates bug #6. **Re-run
it.** One figure from it was unaffected by the bug and is worth checking:
*H4 + cooldown 5d* returned **+23.5% out-of-sample vs baseline +11.3%, with a
smaller drawdown (−5.2% vs −8.8%)**.

## 12. Business status — the honest scorecard

The day-30 gate (12 Aug) was about **demand**, not P&L. Reading:

- ✅ Product built, live, running unattended
- ✅ Discipline demonstrated in public — every loss capped, bugs fixed openly
- ❌ **Subscribers: 1 (the owner)**
- ❌ **Three warm yeses: never attempted**
- ❌ Show HN / essays: drafted, never posted
- ⏸️ Newsletter: **paused by owner decision** ("ok to skip until I have
  subscribers") — issues #34, #41 etc. sit undrafted-but-unsent

**The verdict is "not yet attempted", not "failed."** The single highest-value
action available costs £0 and doesn't involve the market: **three
conversations with real traders asking the £12 question.** Owner says he
doesn't know anyone who trades; the playbook covers that (referral question to
ordinary contacts, then genuine participation in r/swingtrading and
r/algotrading before asking).

## 13. Rejected ideas (with reasons — don't relitigate)

- **Predictions / per-trade auto-tuning** — the brand's literal anti-promise;
  overfitting noise on tiny samples.
- **Faking an ICT/SMC mode** — discretionary and predictive; a detector would
  be a caricature. `TRADING_STYLES.md` documents the honest answer, and "My
  Trading Diagram" now says so out loud when a user names such a style.
- **Tightening stops after losses** — tested 2026-07-29; evidence did not
  support it.
- **Posting results to r/Daytrading** — wrong audience for an anti-daytrading
  brand.
- **OmniRoute proxy** — would route the owner's work through 90+ third-party
  free providers, directly against the local-first/privacy pitch.

## 14. Owner's end-state vision

**TradingView webhook alerts → Trendkept.** The user charts and alerts in
TradingView; a local Trendkept listener sizes the trade by the ruleset, places
it with the stop attached via the user's own broker keys, and journals it.
*"TradingView thinks, Trendkept disciplines."* Pro-tier scope, after month-3
monetisation. This is the honest way to serve discretionary traders — their
entry, our discipline — without pretending to be ICT.

## 15. What is pending right now

**Owner (identity-bound):**
1. **Merge PR #43** — equity on every pass + the false-UNPROTECTED fix.
2. **Re-run the Strategy lab** after merging (issue #33's verdict is void).
3. **The three warm yeses** — the thing that actually decides the business.
4. Decide on the newsletter: the site still promises *"Every Sunday"* while
   sending is paused. Options offered: soften to "most Sundays", drop the
   frequency, or pause properly. **This is an honesty-rule violation until
   resolved.**

**Claude (next build candidates):**
- The **position-cost cap** (§9) — backtest first.
- Auto-logger can't see broker stop-outs (they fire between passes); diff
  positions pass-to-pass to catch them.
- Journal v2: discipline score per rule, owner notes, broker-agnostic CSV import.
- More cluster content from `CONTENT_STRATEGY.md`.

## 16. Tone that works with this owner

He gets anxious about the drawdown and asks variants of "is it working?" and
"will anyone buy this?" often. What helps:
- Separate **"the machine executes correctly"** (provable, and true) from
  **"the strategy makes money"** (unanswerable at 8 trades) from **"anyone
  wants it"** (untested, and the one that matters).
- Give the number honestly, including when it's bad. Never spin.
- Distinguish confirmed from inferred, and say which.
- When he proposes a strategy change mid-drawdown, take the idea seriously,
  route it to the lab, and change nothing live.
- End with one concrete action, not a list of five.
