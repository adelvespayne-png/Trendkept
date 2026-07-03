# r/swingtrading post — ready to fill and paste

**Precondition — do not post before this is true:** you have **at least four
weeks of real paper-trading logs** from running the rules daily (START_HERE
Step 3). The post quotes your actual logs; the brackets below get filled
with your real numbers. If the logs don't exist yet, the post waits. An
invented version of this post would be astroturfing from a brand whose whole
pitch is honesty — and these communities are good at catching it.

**When:** the week after the r/algotrading post, logs permitting.
**Sub rules:** check self-promo rules on the day; no link in the body —
offer the repo in comments, with the one-line "I built this" disclosure.

---

## Title

`I made the classic trend rules mechanical so I couldn't improvise, then paper-traded them for [N] weeks. What the logs actually show`

## Body

> The rules are the boring ones everyone knows: only confirmed uptrends
> (price above the 50 and 200 SMA, higher highs/lows), enter on pullback or
> breakout, stop below the last swing low, risk max 1–2% per trade, trail
> the stop, exit on trend break. What I changed: I wrote them as code so
> that every day there's exactly one mechanical answer, and I've followed
> that answer on a paper account for [N] weeks. From the actual logs:
>
> **1. Most days the correct action is nothing.** Out of [N×5] trading
> days, the rules produced [X] valid entries across a [Y]-ticker watchlist.
> Backtesting the same rules over [period] shows the same pattern. Eyeballing
> charts, I would have "found" far more trades — every extra one would have
> been a rule violation (chasing extension, or trading an unconfirmed
> trend).
>
> **2. The stop distance decides the position size — conviction doesn't get
> a knob.** Risking 1% with a stop 5% away forces a position of 20% of the
> account, mechanically. [Real example from your log: ticker, entry, stop,
> computed size.]
>
> **3. Honest backtests of these rules win by asymmetry, not accuracy.**
> The edge, when it shows up, is the average win being a multiple of the
> average loss (R-multiples), not a high win rate. Once the scorecard is R
> instead of win %, losing small stops feeling like failing.
>
> **4. The stop goes in with the entry order.** The ruleset sends entries as
> entry+stop pairs so the broker holds the exit from second one. Willpower
> isn't part of the system, which — [N] weeks in — I've concluded is the
> entire point.
>
> The ruleset and the code that enforces it are open source (I built it —
> happy to share in comments). Curious what the discretionary traders here
> think: what do you do when the mechanical answer is "nothing" for a week?

## Follow-up

Give the repo link when asked, with the disclosure line. When someone shares
a discipline failure story, reply with empathy first — those threads are
where newsletter subscribers come from. Answer every "does it make money?"
with the honest frame: it's a discipline tool and an honest backtester, not
a promise of returns — and your paper results to date, stated plainly,
whatever they are.
