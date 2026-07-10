# Trendkept — session handoff & working rules

This repo is both a product (an open-source trend-following toolkit) and a
business-in-a-box (Trendkept Pro). The owner is non-technical: explain in
plain English, build without asking them to touch code, and put anything
important into committed files — the repo is the memory between sessions.

## Where everything lives

- `business/START_HERE.md` — the owner's do-this-now sequence. Read first.
- `business/PLAN.md` — strategy, roadmap, risks, **trajectory gates (§9)**.
- `business/model.py` — the financial model ("honest edition": month-3
  revenue start, real ~9% fees, 10/7/5% churn, spike-decay traffic, stepped
  costs incl. licensed data feed, SDE valuation). `--md` regenerates
  `FINANCIALS.md`. Never quote numbers that contradict a fresh run.
- `business/LEGAL.md` — FCA bright line, **US perimeter check**, market-data
  licensing (§5 — paid product must not run on scraped Stooq/Yahoo).
- `business/GO_TO_MARKET.md`, `LAUNCH_CHECKLIST.md`, `business/launch/` —
  playbook + paste-ready posts + newsletter template/generator.
- `business/build_manual.py --pdf` — rebuilds `Trendkept_Owners_Manual.pdf`
  (the all-in-one PDF). Rebuild after any business-doc change.
- `trendkept/` — the engine + `web.py` local dashboard (scan, backtest,
  watchlist, per-user appearance settings). `python -m trendkept.web`.
- Tests: `python -m unittest discover -s tests` (all must pass; don't quote
  a hardcoded count in docs — it drifts).

## Hard rules settled in prior sessions (do not relax)

1. **Honesty in all public content.** Every claim in marketing/posts must be
   literally true of the owner on posting day — no invented trading
   history. The r/swingtrading post is gated on 4+ weeks of real
   paper-trading logs.
2. **Compliance phrasing:** broadcast copy (newsletter, site) is
   descriptive, never imperative — "trend filter no longer met", never
   "get out". No return promises, no gain screenshots, no per-person
   buy/sell language. See LEGAL.md §2.
3. **Validate before spending:** the sequence is ~£10 of validation
   (domain, landing page, waitlist, Show HN) before ~£100 incorporation,
   before any monthly burn. Gates are trajectory checks vs the three
   modelled curves, not single tripwires.
4. **Local-first privacy:** broker API keys never leave the user's machine;
   any hosted tier is analysis/journal only.
5. **Model honesty:** if an assumption changes, change `model.py`,
   regenerate FINANCIALS.md, then update any doc that quotes the numbers,
   then rebuild the manual.

## State at last handoff (July 2026)

- Branch: `claude/business-plan-ownership-8m18uu` (all work pushed; not yet
  merged — repo still named "Archie" until the owner renames it on GitHub).
- Rebrand Archie→Trendkept complete across code/docs/site.
- Product done: engine, CLI, dashboard, watchlist, appearance customization.
- Plan rebuilt after an external critique (gate contradiction, optimistic
  model, fabricated post stories, data licensing, US legal, wedge
  overstatement — all fixed; see the commit "Rebuild the plan against
  external review").
- Name is FINAL: **Trendkept / trendkept.com** (owner's call, July 2026,
  after trendrail.com fell through; previously Trendrail, before that
  Archie).
- LIVE (July 2026): trendkept.com bought and serving the landing page via
  a Cloudflare Worker (static assets from `site/`, config in
  `wrangler.jsonc`, builds track `main`); repo renamed Trendkept; `main`
  is canonical (PR #2 merged; keep new work flowing branch -> PR -> main).
  Buttondown "The Trend Check" live (slug `trendkept`, lowercase — this
  broke once), sending domain news.trendkept.com verified, signup tested
  end-to-end; subscriber #1 is the owner. The day-30 validation clock is
  running. Owner is ~day 3 of the 4-week paper-trading log.
- Next build candidates: trade journal (roadmap month 2, the retention
  hook), Sunday auto-draft GitHub Action for the newsletter, SEO calculator
  pages for the site, wiring the Buttondown form once the owner supplies
  the URL.
