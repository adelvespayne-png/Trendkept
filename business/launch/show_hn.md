# Show HN post — ready to paste

**When:** Tuesday–Thursday, around 14:00–15:00 UTC (peak HN traffic).
**Where:** https://news.ycombinator.com/submit
**Golden rule:** clear your day — launch days are 8+ hours of comments, and
launch weeks run 25+ hours total. The submission is 10% of the work; being
present, humble, and technical in the comments is the other 90%.
**Honesty rule:** every claim in the draft below is about the software's
design, which is why it's safe to post as-is. Don't add personal trading
history that isn't literally yours on the day.

---

## Title (pick one — A is recommended)

A) `Show HN: Trendkept – a dependency-free backtester that refuses to peek at the future`

B) `Show HN: Trendkept – trend-following rules as code, stdlib Python only`

## URL

Your GitHub repo link.

## Text (paste as the submission text)

> I built Trendkept because almost every retail backtesting result I saw
> looked too good to be true — and usually was, through look-ahead bias —
> and because the standard advice ("write your rules down and follow them")
> has no tooling that actually enforces it.
>
> Trendkept is a small toolkit that turns a written trend-following ruleset —
> confirmed uptrend only, stop below the last swing low, risk 1–2% per trade,
> trail the stop, exit on trend break — into code you can backtest and
> paper-trade. Design choices HN might find interesting:
>
> - **Every signal is causal.** A value at bar i is computed only from bars
>   ≤ i. Swing pivots need confirmation bars before they exist, so the
>   backtest can only act on information the market had actually revealed.
> - **Zero dependencies.** Pure Python stdlib, runs on 3.9+. The CSV loader
>   copes with Yahoo/Stooq/broker exports and adjusts whole OHLC bars for
>   splits so a 2:1 split never reads as a 50% "lower low".
> - **The stop is enforced by the broker, not willpower.** Orders go in as
>   entry+stop pairs (OTO). Live trading is triple-gated behind
>   --confirm --live --i-understand-live.
> - There's a local web dashboard (also stdlib only) — `python -m
>   trendkept.web`.
>
> It's MIT licensed. The honest caveat is in the README: backtests use
> idealized fills and are an optimistic ceiling, not a promise. Would love
> feedback on the causality approach and what I've missed.

## Comment playbook

- Answer every technical question, fast, with code references.
- If someone says "trend following doesn't work": don't argue returns. Say
  the tool's claim is narrower — *if* you trade rules, it makes you follow
  them, and the backtest is honest about what the rules did historically.
- If someone finds a bug: thank them, fix it same-day, reply with the commit.
  Nothing plays better on HN.
- Never mention Pro/pricing unless directly asked; if asked: "planning a paid
  hosted version later; the core stays MIT."
- Have the newsletter link in your HN profile, not in the post.
