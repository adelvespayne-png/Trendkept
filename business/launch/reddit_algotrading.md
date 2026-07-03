# r/algotrading post — ready to paste

**When:** a few days after the Show HN (momentum compounds).
**Rules of the sub:** value first, no naked self-promo. This post teaches the
look-ahead-bias lesson and mentions the tool once, at the end, as the
implementation. Read the sub's rules on the day; if links are restricted,
put the repo in a comment when asked.

---

## Title

`Your backtest is probably lying to you: a checklist for look-ahead bias (with a worked example)`

## Body

> After getting burned by a backtest that made +40%/yr on paper and lost money
> live, I went through every place future information can leak into a
> "simple" moving-average strategy. Sharing the checklist since most of these
> are subtle:
>
> **1. Swing highs/lows don't exist when you think they do.** A swing low
> needs N bars *after* it to be confirmed. If your backtest puts the stop
> under a swing low on the day it forms, you're trading information from the
> future. Fix: only act on pivots once the confirmation bars have printed.
>
> **2. Split/dividend adjustment applied to close but not OHLC.** If you
> adjust closes but test stops against raw lows, a 2:1 split reads as a 50%
> crash and stops you out of every backtest position. Adjust the whole bar by
> the same factor.
>
> **3. Same-bar entry+exit optimism.** If price crosses your entry and your
> stop in one bar, which happened first? You don't know from daily data.
> Honest answer: assume the worst (stop first).
>
> **4. Gap-throughs filled at the stop price.** If the market opens below
> your stop, you don't get the stop price — you get the open. Model the fill
> as min(stop, open).
>
> **5. Position sizing off future equity.** Size from equity *at entry time*,
> including open-position drawdown, not from the final curve.
>
> I ended up encoding all five into a small stdlib-Python backtester for a
> plain 50/200 trend-following ruleset (MIT, no dependencies) — happy to
> share the repo if useful, and genuinely interested in what leaks I've
> still missed.

## Follow-up

When people ask for the link (they will — that's the point of "happy to
share"), reply with the GitHub URL and one sentence: "The causality bits are
in `indicators.py` (confirmed swings) and `backtest.py` (fill rules)."
