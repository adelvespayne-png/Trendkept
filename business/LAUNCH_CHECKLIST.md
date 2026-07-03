# Trendrail Pro — first-90-days launch checklist

Work top to bottom. Nothing here needs anyone's permission, and nothing costs
more than ~£150 until money is already coming in. Time budget: ~10 focused
hours/week.

## Week 1 — foundations (one sitting each)

- [ ] Name search: Companies House + UK IPO trademark search + domain
      availability for "Trendrail" / fallback name. Decide once, move on.
- [ ] Buy the domain (~£10). Suggested: `trendrail.com` (checked: no DNS records as of 2026-07) or
      `trendrail.io` / `.co.uk` — whatever survives the registrar check.
- [ ] Incorporate the Ltd at Companies House (~£50, online, same day).
      Registered-office service, you as sole director/shareholder.
- [ ] Open a free business bank account (Starling/Tide).
- [ ] Deploy `site/index.html` (GitHub Pages / Cloudflare Pages — free).
- [ ] Create the newsletter list ("The Trend Check") on Buttondown or
      ConvertKit free tier; wire the landing-page form to it.
- [ ] Set up a support email (hello@…) on the domain.

## Week 2 — make the free tier shine (it's the top of the funnel)

- [ ] Record a 60-second GIF/video: `python -m trendrail.web`, scan, backtest,
      equity curve. Put it at the top of the README and the landing page.
- [ ] Add GitHub topics: `trading`, `trend-following`, `backtesting`,
      `python`, `zero-dependencies`.
- [ ] Write CONTRIBUTING.md (two paragraphs) and enable Discussions.
- [ ] Dogfood: open an Alpaca paper account, run the daily `manage` cadence
      yourself from today onward. Your own journal becomes launch content.

## Weeks 3–4 — first public swings

- [ ] Publish content pieces 1 & 2 (calendar in GO_TO_MARKET.md §4).
- [ ] **Show HN** — draft ready to paste in `business/launch/show_hn.md` (Tue–Thu ~14:00 UTC; stay in the comments all day).
- [ ] Reddit value-posts — drafts ready in `business/launch/reddit_algotrading.md` and `business/launch/reddit_swingtrading.md`.
- [ ] Send "The Trend Check" #1 — template + table generator ready in
      `business/launch/trend_check_001.md` and `business/launch/trend_check.py`. Weekly from
      now on, no matter what — the streak is the asset.

## Month 2 — build the retention hooks (ship weekly)

- [x] Watchlist page in the dashboard (scan N symbols at once) — **done, shipped in `trendrail/web.py`**.
- [ ] Trade journal: log entries/exits, auto-computed R-multiples, discipline
      score ("did you follow all five rules?").
- [ ] Content pieces 5–8; keep the newsletter streak.
- [ ] Collect a waiting list for Pro on the landing page ("founding
      subscriber" £79/yr, locked forever).

## Month 3 — turn on the money

- [ ] Paddle account (merchant of record — handles VAT for you) or Stripe.
- [ ] Licence-key gate for Pro features; 14-day trial, card required.
- [ ] ToS, privacy policy, refund policy live (checklist in LEGAL.md §3);
      ICO registration (~£40); the one-hour solicitor review.
- [ ] Lifetime deal (£299, cap 200) to the newsletter, T-14 before launch.
- [ ] **Launch:** Product Hunt + Show HN + Reddit, same week.
- [ ] T+7: publish the "open startup" launch-numbers post.

## The gates (from PLAN.md §9 — check, don't negotiate)

- [ ] **Day 90:** 1,000 newsletter subs OR 500 GitHub stars? If neither,
      change the *message* (positioning), not the product, and re-run 8 weeks.
- [ ] **Month 6:** 50 paying subscribers? If not: freeze features, 8 weeks of
      distribution only.
- [ ] **Month 12:** £2k MRR → let it run. Under → keep as side asset or sell
      the codebase + audience (Acquire.com, Tiny Acquisitions). Exiting a
      non-winner at a small profit is winning.

## Standing weekly rhythm (from day 1, ~10 h/week)

| When | What |
|---|---|
| Daily, 15 min | `manage` on the paper account; answer support |
| One evening | Ship one small improvement |
| One evening | Write the week's content piece |
| Sunday, 1 h | Send "The Trend Check"; log the four numbers (GO_TO_MARKET.md §6) |
| Month-end, 1 h | Put actuals into `business/model.py`, regenerate FINANCIALS.md, compare scenario |
