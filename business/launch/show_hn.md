# Show HN post — ready to paste

**When:** Tuesday–Thursday, around 14:00–15:00 UTC (peak HN traffic).
**Where:** https://news.ycombinator.com/submit
**Golden rule:** clear your day. The submission is 10% of the work; being
present, humble and technical in the comments is the other 90%.
**Honesty rule:** every claim below was verified against the code and the log
on 2026-09-01. Before posting, re-check the two numbers marked ⚠️ — they move.

---

## Title (A recommended)

A) `Show HN: Trendkept – a dependency-free backtester that refuses to peek at the future`

B) `Show HN: I built a tool to test whether I should change my trading rules. It said no.`

## URL

https://github.com/adelvespayne-png/Trendkept

## Text (paste as the submission text)

> I built Trendkept because almost every retail backtest I saw looked too
> good to be true — usually through look-ahead bias — and because the standard
> advice ("write your rules down and follow them") has no tooling that
> actually enforces it.
>
> It turns a written trend-following ruleset into code you can backtest and
> paper-trade. Things HN might find interesting:
>
> **Every signal is causal.** A value at bar i uses only bars ≤ i. Swing
> pivots need confirmation bars before they exist, so the backtest can only
> act on information the market had actually revealed. Backtests that peek
> look brilliant and trade terribly.
>
> **Zero dependencies, stdlib only, Python 3.9+.** The CSV loader copes with
> Yahoo/Stooq/broker exports and scales whole OHLC bars by the adjustment
> factor, so a 2:1 split never reads as a 50% "lower low".
>
> **The stop is enforced by the broker, not willpower.** Entries go in as
> entry+stop pairs. The autopilot that runs the paper account has no live
> mode at all — by construction, not by flag. The manual commands that can
> touch a live account are gated behind `--confirm --live
> --i-understand-live`.
>
> **It's been flying a paper account in public since 13 July.** A GitHub
> Action runs the full pass every trading day, commits what it did to a CSV
> in the repo, and opens an issue when it acts. ⚠️ Currently down ~7% over
> 35 days — every loss capped in advance except one that gapped through its
> stop and cost 1.57× the planned risk. That's in the log too, because a
> stop is a trigger for a market order, not a guarantee of a price.
>
> **The part I'd most like feedback on:** I got twitchy during the drawdown
> and wanted to change the rules, so I built a lab that compares rule
> variants over 8 years and 50 instruments with an out-of-sample split —
> tune on the early years, validate on years the tuning never saw, and a
> variant only counts if it beats the baseline on *both* slices for *both*
> expectancy and return.
>
> Its first run printed a suspicious result: positive return, profit factor
> 1.48, and negative expectancy. That combination is impossible, and it was
> my bug — I was dividing R-multiples by the *trailed* stop instead of the
> entry stop, which corrupts exactly the trades that ran furthest. Fixed it,
> added a regression test asserting a profitable run can't report negative
> average R, re-ran, and the verdict came back: **nothing beat the baseline
> on both slices. Change nothing.**
>
> MIT licensed. The honest caveat is in the README: backtests use idealised
> fills and are an optimistic ceiling, not a promise. I'd love feedback on
> the causality boundary and on the out-of-sample criterion — particularly
> whether requiring both slices is too strict.

---

## Numbers to re-check on the morning ⚠️

Run these and update the post before submitting:

```
python3 -c "
import csv; rows=list(csv.reader(open('business/paper_log.csv')))[1:]
print('days:', rows[-1][1], '| last:', rows[-1][0])"
```

Equity and drawdown are printed at the top of the most recent log row.

## Comment playbook

- **Answer every technical question fast, with file/line references.**
- **"Trend following doesn't work"** → don't argue returns. The tool's claim
  is narrower: *if* you trade rules, it makes you follow them, and the
  backtest is honest about what those rules did historically.
- **"You're down 7%, why would I use this?"** → agree, and say the honest
  thing: 9 closed trades can't establish an edge either way. To distinguish
  a +0.2R edge from zero at 95% confidence you need ~250 trades. That's
  years. So the paper account demonstrates execution and discipline, not
  profitability — and it's public precisely so nobody has to take my word.
- **Someone finds a bug** → thank them, fix it same-day, reply with the
  commit link. Nothing plays better on HN.
- **Never mention Pro or pricing unless asked.** If asked: "planning a paid
  hosted version later; the core stays MIT."
- **Newsletter link goes in your HN profile, not the post.**

## Do not

- Claim or imply any profit.
- Post performance screenshots.
- Argue with anyone. Concede good points immediately — it reads far better
  than defending, and the good-faith critics are usually right.
