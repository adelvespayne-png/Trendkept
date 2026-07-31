# When do we change the rules? — pre-committed review protocol

Written **2026-07-29, during a losing stretch**, deliberately: thresholds
decided while calm are worth something; thresholds decided while hurting are
just feelings with numbers attached.

The question this answers: *"When do we change it if we're consistently
losing?"*

---

## 0. The uncomfortable maths that shapes everything

Trend-following has a modest per-trade edge and a wide spread of outcomes.
Typical numbers: ~37% win rate, average win ~+2.2R, average loss ~−0.95R,
giving a true edge around **+0.2R per trade** with a per-trade standard
deviation around **1.6R**.

To distinguish that edge from zero at 95% confidence:

| True edge | Trades needed |
|---|---|
| +0.10R | ~980 |
| +0.20R | ~250 |
| +0.30R | ~110 |

At roughly one trade every two or three days, **250 trades is two to three
years.**

**Therefore: the paper account can never tell us whether the strategy has an
edge.** Anyone who claims a month of live results proves or disproves a
trend system is fooling themselves. This is not an excuse — it is the reason
the protocol below is built the way it is.

What the paper account *can* detect, quickly and reliably:

1. **Execution faults** — bugs, unprotected positions, sizing errors.
2. **Divergence from backtest** — live results far outside what the backtest
   said a run of this length should look like. That points at slippage, data
   or execution, not at the rules.

Judging *the rules* is the backtest's job, over decades and out-of-sample.

---

## 1. Execution faults — fix immediately, always

Zero tolerance, no waiting for a sample. Any of these is a bug, not a
losing trade:

- A position exists without a standing stop.
- A stop is not honoured, or fills far from the stop absent a real gap.
- Position size implies risk materially different from the configured %.
- The autopilot fails to run, or silently skips part of the board.
- An order is duplicated, or an exit is stacked on a pending exit.

*Precedent: three such faults have already been found and fixed — the
day-order stop expiry (07-15), the double-exit 403 (07-20), and the
sub-penny stop-raise 422. Each was a code fix, none was a strategy change.*

**Action:** fix, add a regression test, log it in `paper_log.csv`.

---

## 2. Drawdown gates — "stop and check", not "the strategy is broken"

Measured from the $100,000 paper start, peak-to-trough.

| Level | What happens |
|---|---|
| **−5%** | Note it. No action. Normal for this style. |
| **−10%** | **Formal review** (§4). Not a halt — a mandatory look at whether faults from §1 are present and whether §3 divergence is triggered. |
| **−20%** | **Halt new entries.** Manage open positions to their stops. No live money is even discussed until a full backtest review passes. |

These are not predictions of failure. Trend systems routinely draw down
10–15% in normal operation. The gates exist so the *decision to look* is
automatic rather than emotional.

**Status 2026-07-29: −3.05%. No gate reached.**

---

## 3. The divergence test — the honest statistical check

Since we cannot measure the edge directly, we ask a narrower, answerable
question:

> Given the backtest's distribution of R-multiples, how unusual is our live
> run of N trades?

Method: take the R-multiples from the backtest, simulate many random runs of
the same length as our live sample, and see where the live expectancy falls
in that distribution.

- **Above the 5th percentile** → a normal bad patch. Change nothing.
- **Below the 5th percentile** → live is diverging from the model. Investigate
  the *implementation* first: slippage, fill quality, data differences,
  order timing. Only if implementation is clean does the ruleset itself come
  into question.

Run this at **30 closed trades**, then every 30 thereafter. Sooner is noise.

**Status: 3 closed trades (−0.44R, +0.02R, −0.89R; expectancy −0.44R).
Far too few to test — a run of three losers is unremarkable at a 37% win
rate (probability roughly one in four).**

---

## 4. What a review actually consists of

When a gate triggers, in this order:

1. **Audit for §1 faults.** Most "the strategy is losing" turns out to be a bug.
2. **Run the divergence test** (§3) if there are ≥30 closed trades.
3. **Check the market regime.** A trend-follower losing in a choppy,
   trendless market is the system working as designed, not failing. Note
   how many of the 20 tickers were in confirmed uptrends over the period —
   if almost none were, there was nothing to catch.
4. **Only then**, consider rule changes — and only via §5.

---

## 5. How rules may change (and how they may not)

**Permitted:** a change supported by a backtest over decades of licensed
data, with an out-of-sample split — tuned on the early years, validated on
years the tuning never saw. Documented, tested, then shipped.

**Forbidden — these are how systems get destroyed:**

- Tightening stops because a trade just lost. (Tested 2026-07-29: the
  evidence did **not** support it. See that session's finding.)
- Skipping a signal because the last one lost.
- Adding symbols to chase a move.
- Changing anything per-trade, or mid-drawdown, on the live sample.
- Fitting parameters to the paper account's few dozen trades. That is
  overfitting to noise, and it is the single most common way retail
  systems die.

**Review cadence: monthly. Never per-trade.**

---

## 6. What this means for the business

The paper log's public job was never to prove profitability — it is to show,
in the open, that a written ruleset is executed faithfully: sized by risk,
stop attached before the order leaves, trailed daily, losses capped, nothing
overridden. **A disciplined losing stretch demonstrates that better than a
lucky winning one.**

And the business does not rest on this number. Trendkept sells *enforcement
of discipline*, which is true whatever the market did this week. Selling on
performance would breach LEGAL.md §2 and destroy the no-predictions moat.

The day-30 validation gate is about **demand** — the three warm yeses, the
waitlist, the Show HN — not about the paper account's P&L.
