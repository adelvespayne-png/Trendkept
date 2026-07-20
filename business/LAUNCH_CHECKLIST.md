# Trendkept Pro — first-90-days launch checklist

Work top to bottom. **The order is deliberate: validate with ~£10 before
spending the ~£100 on company paperwork** — the plan's gate philosophy,
applied from day one. Time budget: ~10 focused hours/week steady-state;
**launch weeks (Show HN, Product Hunt) run 25+ hours — schedule them like
sprints.**

## Week 1 — validate first (~£10 total)

- [x] Name search: UK IPO trademark search + Companies House name check for
      "Trendkept". **Done (2026-07-14), both clear: no "Trendkept" mark on
      the IPO register (nearest is "Trendpet", a different word in
      unrelated classes 12/18/20/21/28 — no conflict) and Companies House
      returns no results for the name.**
- [x] **Buy `trendkept.com`** (~£10) at Cloudflare Registrar or Namecheap —
      the name is decided; the registrar's availability search is the final
      word.
- [x] Deploy `site/index.html` (Cloudflare Pages — free) with the waitlist.
- [x] Create the newsletter list ("The Trend Check") on Buttondown free
      tier; wire the landing-page form to it. **Done: live at
      trendkept.com, sending domain news.trendkept.com verified,
      subscribe flow tested end-to-end (subscriber #1: the owner).**
- [x] Set up the domain email — **done via iCloud+ custom domain:
      archie@ / news@ / hello@trendkept.com (July 2026).**
- [x] Dogfood from day one: open an Alpaca paper account, run the daily
      cadence. **The r/swingtrading post is blocked until you have 4+ weeks
      of real logs** — clock started; the official log is
      `business/paper_log.csv` (day 1: 2026-07-13). First rules-based
      paper trade: NVDA, 2026-07-14.

## Week 2 — make the free tier shine (it's the top of the funnel)

- [ ] Record a 60-second GIF/video: `python -m trendkept.web`, scan, backtest,
      equity curve. Put it at the top of the README and the landing page.
- [ ] Add GitHub topics: `trading`, `trend-following`, `backtesting`,
      `python`, `zero-dependencies`.
- [ ] Write CONTRIBUTING.md (two paragraphs) and enable Discussions.

## Weeks 3–4 — first public swings (the validation data arrives)

- [ ] **The three-warm-yeses test** (from the July "council" review — its
      cheapest good idea): in direct, personal conversations (DMs, replies,
      the one real subscriber — never spam posts), ask ~10 traders who fit
      the profile one question: *"Would you pay £12/month for a tool that
      enforces this written ruleset on your own account — sizing, stop
      attached to the entry, trailed daily, no predictions?"* Log every
      answer in `business/metrics.csv` notes. Three sincere yeses = a pulse
      on top of the day-30 numbers; blank stares = a messaging finding.
      (The council's r/Daytrading version is rejected: wrong audience for
      an anti-daytrading brand, and results posts stay gated on the
      matured log.)

- [ ] Publish content pieces 1 & 2 (calendar in GO_TO_MARKET.md §4).
- [ ] **Show HN** — draft ready to paste in `business/launch/show_hn.md`
      (Tue–Thu ~14:00 UTC; clear the whole day for comments).
- [ ] r/algotrading value-post — `business/launch/reddit_algotrading.md`
      (all claims about the code; postable as-is).
- [x] Send "The Trend Check" #1 — **done, 2026-07-18 (ahead of schedule):
      drafted end-to-end by the Saturday robot, sent via Buttondown,
      delivery verified in the owner's inbox.** Weekly from now on, no
      matter what — the streak is the asset.
- [ ] **Day-30 validation read:** waitlist + stars vs the curves
      (GO_TO_MARKET.md §6). A pulse → proceed to incorporation below. Dead
      silence after a messaging retry → stop here, ~£10 spent, lesson cheap.

## Month 2 — incorporate, then build the retention hooks

- [ ] Incorporate the Ltd at Companies House (~£50, online, same day).
      Registered-office service (~£40/yr), you as sole director/shareholder.
      SIC code 62012.
- [ ] Open a free business bank account (Starling/Tide) with the company
      number.
- [ ] r/swingtrading post — **only once the 4-week logs exist**; fill the
      bracketed numbers in `business/launch/reddit_swingtrading.md` from
      your real journal.

## Month 2 — build the retention hooks (ship weekly)

- [x] Watchlist page in the dashboard (scan N symbols at once) — **done, shipped in `trendkept/web.py`**.
- [ ] Trade journal: log entries/exits, auto-computed R-multiples, discipline
      score ("did you follow all five rules?").
- [ ] Content pieces 5–8; keep the newsletter streak.
- [ ] Collect a waiting list for Pro on the landing page ("founding
      subscriber" £79/yr, locked forever).

## Month 3 — turn on the money (nothing gets charged before ALL of these)

- [ ] **License a market-data feed** (~£25-80/mo — EOD Historical Data,
      Polygon, Databento; check redistribution terms cover the app and the
      newsletter table). The paid product must not run on scraped
      Stooq/Yahoo data — LEGAL.md §5.
- [ ] Paddle account (merchant of record — handles VAT/sales tax for you).
- [ ] Licence-key gate for Pro features; 14-day trial, card required.
- [ ] ToS, privacy policy, refund policy live (checklist in LEGAL.md §3);
      ICO registration (~£40); professional indemnity + cyber insurance
      (~£25/mo); the professional review — UK solicitor **plus the US
      perimeter check** (LEGAL.md §2), ~£300-500 total.
- [ ] Lifetime deal (£299, cap 200) to the newsletter, T-14 before launch.
- [ ] **Launch:** Product Hunt + Show HN + Reddit, same week (this is a
      25+ hour week — plan for it).
- [ ] T+7: publish the "open startup" launch-numbers post.

## The gates (from PLAN.md §9 — trajectory vs the modelled curves)

- [ ] **Day 90:** which curve is the newsletter list on? (conservative ≈
      340, base ≈ 800). At/above base → full pace. On conservative →
      proceed, expectations set. Below and flat after a messaging retry →
      stop before sinking more time.
- [ ] **Month 6:** paying subs vs curves (conservative ≈ 65, base ≈ 230).
      Above base → double down. On conservative → freeze features, 8 weeks
      distribution only. Below → prepare the exit.
- [ ] **Month 12:** MRR vs curves. ≥£2k → winner, let it run (full-time at
      £5k). On the conservative curve (£500-1k, growing) → *choose*
      deliberately: continue (the year-3-5 payoff requires it) or side-asset
      mode (~2 h/week). Below and shrinking → sell the codebase + audience
      (Acquire.com, Tiny Acquisitions). Exiting a non-winner at a small
      profit is winning.

## Standing weekly rhythm (from day 1, ~10 h/week)

| When | What |
|---|---|
| Daily, 15 min | `manage` on the paper account; answer support |
| One evening | Ship one small improvement |
| One evening | Write the week's content piece |
| Sunday, 1 h | Send "The Trend Check"; log the four numbers (GO_TO_MARKET.md §6) |
| Month-end, 1 h | Put actuals into `business/model.py`, regenerate FINANCIALS.md, compare scenario |
