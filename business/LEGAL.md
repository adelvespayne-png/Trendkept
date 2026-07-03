# Trendrail Pro — legal & structure guide

**This is orientation, not legal advice.** Before taking money, spend one hour
with a UK solicitor/accountant to confirm the specifics (~£150–£300 — the best
money the business will spend). This file exists so that hour is efficient.

## 1. Company structure

- **Form a UK private limited company** (e.g. "Trendrail Ltd").
  ~£50 online at Companies House, done in a day. Why a Ltd and not sole
  trader: liability protection (you sell to traders; someone will lose money
  and be angry), credibility with payment processors, clean asset to sell
  later, and corporation-tax flexibility.
- You own 100% of the shares. Director: you. Registered office: a registered-
  office service (~£40/yr), not your home address.
- Open a business bank account (Starling/Tide are free) — never mix funds.
- Register for VAT only when turnover approaches the threshold (currently
  £90k/yr); your accountant will time it. Use **Paddle** as merchant of
  record early on and it handles VAT/sales tax globally for you — worth its
  ~5% for a solo owner.

## 2. The regulatory bright line (the part that matters most)

Selling **software and education** is unregulated. Giving **investment
advice** or making **personal recommendations** requires FCA authorisation in
the UK (and equivalents elsewhere). Trendrail is designed to stay on the safe
side of the line — keep it there:

**Trendrail may (all fine):**
- Execute *the user's* mechanical ruleset on market data and show the result.
- Compute position sizes from a formula the user configures.
- Say "the 50/200 ruleset's conditions are met for AAPL today" — that's a
  factual statement about data, like a calculator or a chart.
- Teach risk-management concepts generally.

**Trendrail (and you, in all marketing) must NEVER:**
1. Make a **personal recommendation** — "given your situation, you should buy
   X". No "buy/sell" language directed at a person. The tool reports rule
   states; the user decides.
2. **Promise or imply returns** — no "make £X", no cherry-picked gain
   screenshots in ads, no "beat the market". (Also the marketing wedge — see
   GO_TO_MARKET.md §1.)
3. **Hold or manage client money** — users connect *their own* broker with
   *their own* API keys; funds never touch you.

Also stay away from: running a "signals group" (drifts into advice),
copy-trading features (regulated), and managing anyone's account "just this
once" (absolutely regulated).

The product already embodies this: dry-run by default, `--confirm` for every
order, `--live --i-understand-live` double-gate, and a disclaimer on every
surface. Keep those; they are compliance features, not just safety features.

## 3. Documents needed before charging money

All are standard SaaS boilerplate; a solicitor can review the pack in the same
hour:

- **Terms of Service** — key clauses: no advice given; no warranty on data
  accuracy or outcomes; user is responsible for orders their broker executes;
  limitation of liability to fees paid; English law.
- **Privacy policy** (UK GDPR) — you hold emails and (if hosted) watchlists/
  journals. Never hold broker API secrets on your servers if avoidable; the
  local-first design means you usually don't. Register with the ICO (~£40/yr).
- **Refund policy** — 14-day no-questions refund. UK consumer law requires
  cooling-off for digital services anyway, and generous refunds kill disputes.
- **The disclaimer**, on the site, in the app, in the newsletter footer:
  *"Trendrail is analysis software, not investment advice. Trading involves risk
  of loss. Past or backtested performance does not predict future results.
  Backtests use idealized fills."*

## 4. Intellectual property & licensing

- The current repo is **MIT** — that ships; it's the open core and the
  marketing engine (PLAN.md §2). You cannot un-MIT what's published, and you
  shouldn't want to.
- **Pro features live in a separate private repository** owned by the Ltd,
  under a commercial licence (licence key per subscription). The dashboard in
  this repo is the free seed; watchlist/journal/email/hosted are Pro.
- Register the trademark ("Trendrail" word mark, class 9/42, UK IPO ~£170) once
  revenue exists — do a name search *before* buying the domain in case a
  clash forces a rename while it's still cheap.
- Contributor licence: keep it simple — small PRs to the open core under MIT
  are fine; anything substantial, ask contributors to confirm MIT licensing
  in the PR (the default anyway).

## 5. Taxes (UK, headline only — accountant confirms)

- Corporation tax on profits (19–25%); pay yourself small salary + dividends
  (the standard owner-director mix your accountant will set up).
- **Your own trading profits are separate from the company** — the company
  sells software; you trade your personal account personally.
- Budget ~£600–£1,200/yr for an accountant from year 1. Fixed cost is in the
  model (`business/model.py`).

## 6. Annual review

Once a year (put it in the calendar): re-check the FCA perimeter guidance
hasn't moved, ToS/privacy still match the product, ICO registration renewed,
and the disclaimer still appears on every new surface shipped that year.
