# Trendkept — content strategy (topic map + cadence)

Built with the `content-strategy` skill. Goal: **email signups** (top of
funnel → the weekly → Pro at month 3) and **SEO authority** in the
"trading discipline, not prediction" niche. Audience: part-time/retail
traders who already suspect discipline (not analysis) is their problem —
they live on r/algotrading, r/swingtrading, Hacker News, YouTube, and
Google searches for calculators and how-tos.

**Two rules sit over everything here** (from CLAUDE.md / LEGAL.md):
1. Descriptive, never advice. No return promises, no "buy/sell", no
   invented trading history. Educational + tool content is always safe;
   personal-results content is **gated on 4+ weeks of the real log**
   (~early Aug 2026).
2. Sustainable cadence only. I draft; the owner reviews and posts under
   their name. One piece a week + the automated newsletter + one batch of
   programmatic pages. Not 3×/week — that breaks by week three.

## The 6 pillars

| # | Pillar | Buyer question / intent | Why it's ours |
|---|---|---|---|
| 1 | **Position sizing & risk** | "how much should I risk per trade" | Highest commercial intent; the calculators *are* the product demo |
| 2 | **Trend-following rules** | "when is a trend actually over" | Educational authority; matches the engine |
| 3 | **Trading discipline / psychology** | "why do I keep breaking my own rules" | The wedge; most shareable; the emotional core |
| 4 | **Stop-losses & trade management** | "where do I put my stop" | Practical; matches the enforce-the-stop feature |
| 5 | **Honest backtesting** | "why do my backtests fail live" | Credibility with the technical crowd (HN, r/algotrading) |
| 6 | **Built in public** (distribution, not SEO) | "does this actually work?" | The transparent log — the one thing no competitor dares show |

## Cluster map (pillar | subtopics | target keyword | format)

**1 · Position sizing & risk** → all internally link to the calculators
- Risk-per-trade calculator | `risk per trade calculator` | **interactive page**
- Position size calculator | `position size calculator` | **interactive page**
- R-multiple calculator + explainer | `r multiple calculator` | **interactive page + blog**
- "The 1% rule, worked through" | `1% risk rule trading` | blog
- "Why win rate is a vanity metric" | `win rate vs expectancy` | blog (Reddit-friendly)

**2 · Trend-following rules**
- Pillar guide: "A written trend-following ruleset, in plain English" | `trend following rules` | **pillar article**
- "50/200 moving average — what it does and doesn't tell you" | `50 200 moving average strategy` | blog
- "Pullback vs breakout entries" | `pullback vs breakout entry` | blog
- "How to know a trend has broken" | `how to know when a trend is over` | blog

**3 · Trading discipline / psychology** (the shareable wedge)
- "Why you keep moving your stop-loss (and how to stop)" | `moving stop loss` | essay
- "Knowing the rules isn't the problem. Following them is." | `trading discipline` | essay
- "Revenge trading, in one chart" | `revenge trading` | essay + graphic
- "The gap between knowing and doing" | `trading psychology discipline` | essay

**4 · Stop-losses & trade management**
- Pillar: "Where to place a stop-loss" | `where to place a stop loss` | **pillar article**
- "Trailing stops explained" | `trailing stop loss explained` | blog
- "Bracket/OCO orders vs a mental stop" | `bracket order stop loss` | blog
- Stop-distance calculator | `stop loss calculator` | **interactive page**

**5 · Honest backtesting** (technical audience → HN/r/algotrading)
- "Look-ahead bias: the reason your backtest lies" | `look ahead bias backtesting` | blog
- "Curve-fitting vs a real edge" | `curve fitting trading strategy` | blog
- "How to backtest without fooling yourself" | `how to backtest a strategy` | pillar
- "Our backtester is causal by construction (and open source)" | `open source backtesting python` | blog + repo link

**6 · Built in public** (Reddit / HN / X / the newsletter — distribution)
- "I let a written ruleset paper-trade in public — every trade, wins and losses" | — | Reddit/HN post (**gated on the 4-week log**)
- Weekly log recap woven into The Trend Check | — | newsletter (live)
- "What 30 days of doing-nothing-most-days looks like" | — | X thread + blog (gated)

## Realistic cadence (against the plan's gates)

| When | Content | Channel | Gate |
|---|---|---|---|
| Every Sunday | The Trend Check | Buttondown (auto-drafted) | live now |
| Weeks 2–3 | Batch: the 4 calculator pages | trendkept.com (programmatic SEO) | build once, ranks for months |
| Week 3 | 1 discipline essay (Pillar 3) + r/algotrading value-post | blog + Reddit | claims about the *code* only — safe now |
| Week 3–4 | Show HN (draft ready) | Hacker News | needs the owner present all day |
| Week 4 | 1 backtesting piece (Pillar 5) | blog + r/algotrading | safe now |
| **~Day 30+** (log matured) | The "built in public" results post | r/swingtrading, HN, X | **unlocks here — not before** |
| Ongoing, 1/week | Rotate pillars 1→2→4→5, then results content | blog + one social repurpose | educational always safe |

**Sequencing logic:** everything before the log matures is *educational
or tool* content (no personal claims — postable today). The high-traffic
*results* content waits for the 4-week log, which is exactly the plan's
existing gate. The calculators are the SEO workhorse: build once, they
rank and demo the product simultaneously, and every one links to the
weekly-email signup.
