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

## Installed skills (`.claude/skills/`, July 2026)

33 business skills the owner supplied, flattened to the discoverable
layout so future Claude Code sessions auto-load them. They are expert
playbooks — apply their methodology when doing that kind of work
(you don't need the Skill tool to follow a SKILL.md checklist). Map to
this business: marketing (`cro`, `seo-audit`, `programmatic-seo`,
`ai-seo`, `ad-creative`, `mktg-psychology`), content (`copywriting`,
`content-strategy`, `email-sequences`, `pillar-content`, `social`,
`video`), finance (`pricing`, `pitch-deck`, `3-statements`,
`comps-analysis`; `dcf-model`/`lbo-model` are overkill for a bootstrap
SaaS), design (`web-artifacts`, `ui-ux-pro-max`), ops (`launch-runbook`,
`sop-builder`, `incident-postmortem`), legal (`compliance`,
`contract-review`, `legal-risk` — cross-check against LEGAL.md, never
replace a real solicitor). Compliance skill must respect the FCA
bright line + descriptive-never-imperative rule already settled.

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
- **The official paper-trading log is `business/paper_log.csv`.** Workflow:
  the owner sends photos of what they ran; the session transcribes them
  into rows (one row per trading day, even "none" days — and never invent
  or backfill rows the owner hasn't evidenced). Sunday auto-draft Action
  shipped: `.github/workflows/trend-check-draft.yml` (active once merged
  to `main`; PR #4).
- Trade journal v1 shipped (July 2026, ~6 weeks ahead of roadmap):
  `trendkept/journal.py` pairs broker fills into round trips FIFO,
  scores them in R-multiples against the standing stop from order
  history; `python -m trendkept.cli journal` + dashboard `/journal`
  page (needs Alpaca keys). Account/risk boxes now remember the last
  typed value per browser (the 1000-default kept sizing plans at 0 sh).
- SEO/distribution layer shipped (July 2026, overnight batch): 4
  interactive no-signup calculator pages (`site/tools/`: position-size,
  risk-per-trade, r-multiple, stop-loss) each with OG + WebApplication
  JSON-LD, cross-linked and funnelling to signup; homepage "Free tools"
  section + nav link; branded OG share image (`site/og.png`) + Open
  Graph/Twitter/JSON-LD on the homepage; `robots.txt`, `sitemap.xml`,
  `llm.txt`. CRO: inline hero email capture + double-opt-in expectation
  microcopy (two of the owner's own signups were "unactivated"). Content
  drafts ready to post (compliance-safe, gate-respecting) in
  `business/launch/`: essay_moving_stops.md, essay_lookahead_bias.md,
  welcome_email.md. Plans: `business/CONTENT_STRATEGY.md`,
  `business/CRO_AUDIT.md`.
- Next build candidates: journal v2 (discipline score per rule, owner
  notes per trade + broker-agnostic CSV import), one-click Windows
  installer, "Open in TradingView" links on symbols, more cluster
  content from CONTENT_STRATEGY.md.
- Owner decision (July 2026): the repo stays FULLY PUBLIC — code,
  paper log, autopilot reports, and the business docs (plan, financials,
  checklist). Build-in-public is the strategy, chosen eyes-open after the
  privacy trade-offs were laid out. Control stays owner-only (merges,
  secrets, accounts); nothing secret lives in the repo.
- Second external critique ("the council", July 2026) processed:
  ADOPTED — put the wedge on the website (journals score after the fact /
  brackets are one static rule / Trendkept enforces before+during+after;
  now a site section + FAQ) and the "three warm yeses" £12 question test
  (checklist, weeks 3-4, direct conversations only). REJECTED — posting
  results threads on r/Daytrading (wrong audience, gated content) and
  panic about the open core (deliberate: Pro sells the effortless
  version, not secrets; same as every open-core company). NOTED — the
  investor's verdict "come back on day 30 with the log" matches our own
  gate exactly.
- Third critique round (website, July 2026) processed: ADOPTED — backtest
  block reframed as "the report, not a pitch" (annotated output, drawdown
  co-equal, run-it-yourself); "most days = do nothing, that's the
  discipline" framing added to the hero board and tape; CTAs consolidated
  to one primary (weekly email; GitHub demoted to text link + contextual
  pricing button); audience honesty line in the hero (free = terminal
  people, Pro = one-click, announced via the weekly); keys-never-leave
  promise elevated to a lock badge by the CTAs. DEFERRED — third-party
  proof (a real user's log beside ours) awaits actual users, priority
  once a handful exist; visual differentiation from navy/blue fintech
  default noted for a future brand pass, not urgent.
- Owner asked (July 2026) for prediction + per-trade self-improving
  strategy. Settled answer: NO to prediction (the brand's literal
  anti-promise) and NO to per-trade auto-tuning (overfitting noise on
  tiny samples). The honest versions, roadmapped: (a) backtest variant
  comparison — same ruleset, different parameters, decades of data,
  out-of-sample split — so rule changes are evidence-gated; (b) journal
  insights once ~20+ real trades exist (expectancy by signal type,
  symbol class, hold time). Review cadence: monthly, never per-trade.
- **Owner's stated end-state vision (July 2026): TradingView webhook
  alerts flowing into Trendkept** — the user charts/alerts in
  TradingView (paid TV plans can fire webhooks), a local Trendkept
  listener sizes the trade by the ruleset, places it with the stop
  attached via the user's broker keys (local-first, keys never leave
  the machine), and journals it. "TradingView thinks, Trendkept
  disciplines." Pro-tier scope, after month-3 monetisation switches on.
