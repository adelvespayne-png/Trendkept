# Trendrail Pro — legal & structure guide

**This is orientation, not legal advice.** Before taking money, budget **two
hours of professional review, not one** (~£300–£500): a UK
solicitor/accountant for the company-and-contracts pack, **plus a check of
the US position** — the launch channels (HN, the subreddits) and the default
watchlist (AAPL, SPY, QQQ) mean the audience will be mostly American. This
file exists so those hours are efficient.

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

**The US perimeter (get this checked — the audience is US-heavy).** The
working theory is the US "publisher's exclusion" (Investment Advisers Act):
impersonal commentary of general and regular circulation — which is what a
weekly mechanical table sent to everyone identically is — falls outside
"investment adviser". But a weekly emailed table of tickers with entry/exit
states walks closer to a signals product than the software itself does, so:
(a) have a US-savvy adviser confirm the newsletter format before charging
money, and (b) keep the newsletter's language **descriptive, never
imperative** — "the trend filter is no longer met on this ticker's data",
not "the rules say get out". State facts about data; never tell readers to
act. The launch templates in `business/launch/` already follow this register
— keep every future issue to it.

**Hosted version (roadmap month 5): never hold broker keys.** The hosted
tier ships as analysis + journal only; broker automation remains a
local-first feature where users' API keys stay on their own machines. If key
custody is ever reconsidered, that's a security-architecture project and a
fresh legal review, not a feature toggle.

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
- **Refund policy** — 14-day no-questions refund. (Strictly, the statutory
  digital-content cooling-off right can be waived on immediate access — most
  SaaS does exactly that — so the generous policy is a *choice*, made because
  refunds kill chargebacks and fit the brand. Don't claim the law requires
  it.)
- **Insurance** — professional indemnity + cyber cover (~£25/mo, in the
  model) from the month you first charge money. You sell software to people
  who lose money; assume one of them will eventually be angry enough to try
  something.
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
- Register the trademark ("Trendrail" word mark, classes 9 + 42, UK IPO
  £170 + £50 for the second class = **£220**) once revenue exists — do a
  name search *before* buying the domain in case a clash forces a rename
  while it's still cheap.
- Contributor licence: keep it simple — small PRs to the open core under MIT
  are fine; anything substantial, ask contributors to confirm MIT licensing
  in the PR (the default anyway).

## 5. Market data licensing — fix this before charging money

The single most concrete legal exposure in the whole plan, and it's easy to
miss because the free tier gets away with it:

- `trendrail/fetch.py` pulls daily prices by **scraping Stooq and Yahoo
  Finance**. Neither source licenses that data for **commercial
  redistribution** — and both the paid product and the weekly newsletter
  table are exactly that. A business built on it is one cease-and-desist
  away from having no data. This risk sits in the PLAN.md risk table for
  that reason.
- **The fix is cheap: license an end-of-day feed before the first paid
  invoice.** EOD-licensed providers (e.g. EOD Historical Data, Polygon.io,
  Databento, or Alpaca's own data for its account holders where the licence
  fits the use) run roughly **£25–£80/month** for daily bars — it's in the
  cost model (`business/model.py`, `DATA_FEED`). Check the chosen
  provider's redistribution terms cover (a) showing derived indicator
  states in a paid app and (b) the newsletter table.
- The free, local, open-source tier — an individual fetching data for their
  own use — is a different posture, but note in the README that users are
  responsible for the data sources' terms, and prefer routing free-tier
  users to their own broker's data (Alpaca) where they have their own
  entitlement.

## 6. Taxes (UK, headline only — accountant confirms)

- Corporation tax on profits (19–25%); pay yourself small salary + dividends
  (the standard owner-director mix your accountant will set up).
- **Your own trading profits are separate from the company** — the company
  sells software; you trade your personal account personally.
- Budget ~£600–£1,200/yr for an accountant from year 1. Fixed cost is in the
  model (`business/model.py`).

## 7. Annual review

Once a year (put it in the calendar): re-check the FCA perimeter guidance
hasn't moved (and the US position if the customer mix is still US-heavy),
ToS/privacy still match the product, ICO registration renewed, the data
provider's licence still covers how the data is actually used, insurance
renewed, and the disclaimer still appears on every new surface shipped that
year.
