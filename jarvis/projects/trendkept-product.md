# Trendkept — product

The open-source trend-following toolkit: engine, CLI, and local dashboard.
Free core for terminal people; Trendkept Pro (the effortless version) is
the business on top.

## Where the truth lives
- Code: `trendkept/` (engine, `web.py` dashboard, `cli.py`, `jarvis.py`)
- Tests: `tests/` — `python -m unittest discover -s tests`, all must pass
- Run it: `python -m trendkept.web` → http://127.0.0.1:8181

## Current status (Aug 2026)
- Shipped: engine, CLI, dashboard (scan / backtest / watchlist / charts /
  appearance), My Trading Diagram (plain-English ruleset), trade journal
  v1 (R-multiples from Alpaca fills), Jarvis chat assistant (`/jarvis`
  page + CLI — deterministic, local, refuses predictions).
- Jarvis is on branch `claude/jarvis-iron-man-2mp2ik`, pushed, awaiting
  the owner's PR/merge.

## Standing orders
- Local-first, standard library only, causal signals (no peeking).
- Broker keys never leave the user's machine.
- Product language descriptive, never imperative — no "should buy".
- No prediction features, ever — it's the brand's anti-promise.
- No per-trade auto-tuning; rule changes are evidence-gated (the lab,
  out-of-sample splits, monthly review cadence).

## Next moves
- Journal v2: discipline score per rule, owner notes per trade,
  broker-agnostic CSV import.
- "Why didn't it enter?" answers in Jarvis (name the exact blocking rule).
- One-click Windows installer; "Open in TradingView" links.
- End-state vision (Pro, post month-3): TradingView webhook alerts into a
  local listener — "TradingView thinks, Trendkept disciplines."

## Decisions log
- Jul 2026 — NO to prediction and per-trade self-tuning; honest versions
  are variant backtesting + journal insights at ~20+ trades.
- Jul 2026 — discretionary styles (ICT/SMC etc.) get honest "we can't
  reproduce that" notes, never a fake mode.
