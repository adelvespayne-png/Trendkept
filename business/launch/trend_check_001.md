# The Trend Check — Issue #1 (template, ready to fill and send)

**How to produce this issue in ~20 minutes:**
1. Run `python business/launch/trend_check.py --default` (needs internet).
2. Paste the generated table where marked.
3. Fill the two [BRACKETED] spots.
4. Send on Sunday. Same skeleton every week — only the table and the lesson
   change.

---

Subject: **The Trend Check #1 — what the rules say this week**

---

Welcome to the first Trend Check.

Every Sunday, this email does one boring, useful thing: it runs a written
trend-following ruleset over ~20 liquid tickers and reports what the rules
say — uptrend confirmed, no entry, or trend broken. No predictions. No hot
takes. The ruleset is public and the code that produces this table is open
source.

## This week's board

[PASTE THE GENERATED TABLE HERE]

A quick reminder of what the states mean (they describe the data — what you
do with your own account is always your decision):

- **Uptrend confirmed** — price above the 50- and 200-day averages, averages
  aligned, structure making higher highs and lows. The ruleset only defines
  entries here, and only on a pullback or breakout that isn't over-extended.
- **No confirmed uptrend** — the ruleset's conditions aren't met, so it
  defines no action. In a mechanical system, "no action" is the most common
  state — that's a feature, not a gap.
- **Trend filter no longer met** — a close below the 50-day average or a
  lower low. This is the condition the ruleset treats as a trend break.

## One honest lesson: [THIS WEEK: R-multiples]

The only score that matters in this system is the R-multiple: profit measured
in units of what you risked. Risk £10 on a trade (that's entry minus stop,
times shares) and make £30 — that's +3R. Get stopped — that's −1R.

Here's the maths that surprises everyone: at +3R average winners, you can be
wrong 60% of the time and still grow the account. Win rate is a vanity
metric; R-expectancy is the business model. Next week: why the stop goes in
*with* the order, not after.

— [YOUR NAME]

*Trendrail is analysis software and education, not investment advice. This
table is the mechanical output of a published ruleset on public data. Trading
involves risk of loss; past and backtested performance do not predict future
results. Unsubscribe below — no hard feelings.*

---

# Issue skeletons for weeks 2–4 (so the streak never breaks)

- **#2 — The stop goes in with the order.** Lesson: OTO orders; willpower is
  not a risk-management system. Board + lesson + one reader question.
- **#3 — Position sizing has no conviction knob.** Lesson: shares =
  (account × risk%) ÷ (entry − stop), with two worked examples (tight vs
  wide stop).
- **#4 — Doing nothing is a position.** Lesson: count the board's
  "no confirmed uptrend" rows over four weeks; show how few valid entries a
  disciplined ruleset actually produces.
