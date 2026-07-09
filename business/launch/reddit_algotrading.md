# r/algotrading post — ready to paste

**When:** a few days after the Show HN (momentum compounds).
**Honesty rule (non-negotiable):** every sentence below is a claim about the
*code and the data*, not about your trading history. Post it as-is and it's
all literally true. Do not add war stories that haven't happened to you —
this community traces, and the brand is honesty.
**Sub rules:** value first, no naked self-promo. Read the sub's rules on the
day; if links are restricted, share the repo in a comment when asked.

---

## Title

`Look-ahead bias checklist: five places your backtest reads the future (worked examples from building an open-source backtester)`

## Body

> I've been building an open-source trend-following backtester, and the most
> useful part of the project turned out to be cataloguing every place future
> information can silently leak into a "simple" daily-bars strategy. The
> checklist, with how the code has to handle each one:
>
> **1. Swing highs/lows don't exist when you think they do.** A swing low
> needs N bars *after* it before it's confirmed. A backtest that places the
> stop under a swing low on the day the low prints is trading information
> from the future. Fix: pivots only become actionable after the confirmation
> bars have actually closed.
>
> **2. Split adjustment applied to close but not OHLC.** Adjust closes but
> test stops against raw lows and a 2:1 split reads as a 50% crash — every
> backtest position stops out on a phantom. Fix: scale the whole OHLC bar by
> the same adjustment factor.
>
> **3. Same-bar entry+stop ambiguity.** If one daily bar crosses both your
> entry and your stop, which fired first? Daily data can't tell you. Honest
> answer: assume the worst ordering (stop first).
>
> **4. Gap-throughs filled at the stop price.** If the market opens below
> your stop you don't get the stop price, you get the open. Fix: model the
> fill as min(stop, open).
>
> **5. Sizing off equity you don't have yet.** Position size must come from
> equity *at entry time*, marked to market including open-position drawdown
> — not from the smooth final curve.
>
> I encoded all five into a small stdlib-Python backtester for the boring
> 50/200 trend-following ruleset (MIT licensed, zero dependencies). Enforcing
> honesty makes the results dramatically less exciting than the backtests
> you see posted around here — which I've come to think is the point.
> Genuinely interested in what leaks this list still misses.

## Follow-up

When people ask for the link, reply with the GitHub URL and full disclosure
in one line: "I built it — it's MIT/open source; the causality bits are in
`indicators.py` (confirmed swings) and `backtest.py` (fill rules)." If
someone asks whether you trade it yourself, answer with the literal truth of
that day (e.g. "paper-trading it daily since [date]; the journal is the next
thing I'm building"). Never inflate.
