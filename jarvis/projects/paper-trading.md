# Paper-trading validation

The day-30 honesty gate: four weeks of real, evidenced paper-trading logs
before any results-flavoured public post and before money gets spent.

## Where the truth lives
- **The official log: `business/paper_log.csv`** — one row per trading
  day, including "none" days.
- Guide: `business/PAPER_TRADING_GUIDE.md`
- Autopilot rows land automatically (`trendkept/paper_log.py`, the
  autopilot workflow); recent commits show the daily passes.

## The workflow
- The owner sends photos of what they ran; the session transcribes them
  into rows. **Never invent or backfill a row the owner hasn't
  evidenced** — machine rows are marked `[auto]`, human rows are
  transcribed only from evidence.
- Jarvis (dashboard chat or CLI) can summarise the log on request.

## Current status (Aug 2026)
- Clock running since late July; autopilot passes logging daily
  (latest: 2026-08-12).
- The investor-critique verdict "come back on day 30 with the log"
  matches our own gate — the log IS the pitch.

## Standing orders
- The log only appends; history is never rewritten.
- A missed day stays missed — an honest gap beats a tidy fake.
- Day 30: run the trajectory check in PLAN.md §9 before any spend or
  results post.
