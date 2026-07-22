# How people trade — a survey, and where Trendkept honestly fits

Context requested by the owner (ICT, TJR, etc.). The point of this doc is
two-fold: (1) understand the landscape so we can talk to traders in their
own language, and (2) be ruthlessly honest about which styles Trendkept's
engine can and can't faithfully do — because pretending would break the
one thing the brand is built on.

**The hard line:** Trendkept is a *mechanical, causally-backtestable,
long-only trend-follower*. It enters confirmed uptrends on pullbacks or
breakouts, sizes by risk, attaches the stop, and trails it. Anything a
style needs that isn't that, it doesn't do — and "My Trading Diagram" now
says so out loud when you describe such a style, instead of faking it.

## The two families

Traders roughly split into **systematic** (rules a computer can execute
and backtest) and **discretionary** (judgement calls a human makes on a
chart). Trendkept lives entirely in the first family. Most of the trendy
retail methods live in the second.

## Systematic / mechanizable (Trendkept's world)

| Style | What it is | Timeframe | Backtests? | Trendkept fit |
|---|---|---|---|---|
| **Trend-following** | Ride established up/down-trends; MAs, higher highs/lows | days–months | Yes, robustly (decades of published evidence) | **This is the engine.** |
| **Breakout / momentum** | Buy new highs / breaks of a range; ride continuation | days–weeks | Yes | **Yes** — the engine takes breakout entries in a confirmed uptrend |
| **Pullback / retracement (with trend)** | Buy a dip *inside* an uptrend | days–weeks | Yes | **Yes** — the engine's pullback entry |
| **Moving-average systems** | Cross/slope of MAs | any | Yes | **Yes** — configurable in the Diagram |
| **Mean-reversion** | Fade extremes; buy oversold, sell overbought | intraday–days | Yes, but different engine + risk model | **No (deliberately).** It fades trends — opposite philosophy, uncapped tail risk. Roadmap only if it backtests. |

## Discretionary / prediction-flavoured (not Trendkept's world)

| Style | What it is | Reality check |
|---|---|---|
| **ICT (Inner Circle Trader)** | "Smart-money" concepts: order blocks, fair-value gaps, liquidity grabs, Judas swings, killzones — the theory that price hunts liquidity then reverses | Discretionary, intraday, and essentially *predictive* ("price will go here to grab stops"). Definitions vary between practitioners; rigorous backtests generally fail to show a durable edge. Huge on YouTube; thin on audited results. |
| **TJR** | A popular influencer's packaging of ICT/SMC ideas | Same substance as ICT — same caveats. |
| **Supply & demand / SMC** | Mark zones where big orders sit; trade reactions | Discretionary zone-drawing; hard to define mechanically; backtests are sensitive to how you draw. |
| **Wyckoff** | Accumulation/distribution phases, "composite operator" | Insightful framework, but discretionary phase-labelling; not a mechanical signal. |
| **Elliott Wave / harmonics / Gann** | Geometric/wave price forecasting | Heavily interpretive; notoriously unfalsifiable; predictive by nature. |
| **Naked price action / scalping** | Read raw candles, 1–5 min | Discretionary and screen-bound — the exact behaviour Trendkept exists to *replace*. |

**Why we don't bolt these on:** they're discretionary and predictive, so
(a) we couldn't implement them faithfully — an "ICT detector" wouldn't be
ICT, it'd be a caricature that fires bad signals; and (b) doing so would
betray the "no predictions" moat that is the entire reason a sophisticated
trader trusts us. The honest move is to name the nearest mechanical cousin
(ICT's "break of structure" ≈ our breakout entry) and be upfront about the
rest being chart study, not signals.

## What "say how you trade" does today

In **My Trading Diagram**, describe your style in plain English (or click
an example). The interpreter maps it to the engine honestly:

- *"I trade breakouts to new highs"* → confirms the breakout entry is
  active; notes it still also takes pullbacks.
- *"I buy pullbacks in an uptrend"* → confirms the pullback entry.
- *"patient / long-term"* vs *"faster / more active"* → tunes the
  averages, breakout window and swing sensitivity (same engine, different
  tempo).
- *"cautious beginner"* / *"aggressive"* / *"risk 1.5%"* → sets risk per
  trade (hard-capped at 2%).
- *"I trade ICT / smart money / order blocks / TJR / Wyckoff / Elliott"* →
  **honest note**: Trendkept can't reproduce that discretionary method;
  nearest thing is a confirmed breakout-of-structure entry; dials stay on
  that footing.
- *"I mean-revert / buy oversold / fade the top"* → **honest note**: the
  engine only buys confirmed uptrends and won't fade a move; nearest
  honest version is a pullback within an uptrend.

## Roadmap (evidence-gated, never faked)

1. **More entry vocabulary** in the interpreter as we see what real users
   type.
2. **A genuine breakout-vs-pullback toggle** (disable one entry type) —
   real engine work, backtested before shipping.
3. **A second, honestly-different strategy module** (e.g. a properly
   researched mean-reversion engine) *only* if it passes a strict
   out-of-sample backtest — added as a clearly separate mode, never
   blended into the trend engine.
4. **The end-state vision** (owner, July 2026): TradingView alerts →
   Trendkept sizes/stops/journals. That lets a discretionary trader keep
   their own method for the *entry decision* while Trendkept enforces the
   discipline around it — arguably the honest way to serve the ICT crowd
   without pretending to be ICT.
