# START HERE — your steps, in order

This is the front door to the whole package. Do these steps in order; every
one is explained. **The order is deliberate: validate the idea with ~£10
before spending the ~£100 on company paperwork** — the plan's own
stop-loss philosophy, applied from the first day. The documents after this
section contain the full detail — this section is what you *do*.

## Step 0 — Today, from your phone (~30 minutes)

1. **Check the domain properly (2 min).** Search `trendrail.com` at a
   registrar (Cloudflare Registrar or Namecheap) — the registrar's own
   availability search or a WHOIS/RDAP lookup is the real answer (an
   earlier DNS check showing "no records" is *not* proof: registered
   domains often have no DNS). If it's free, buy it (~£10/yr). If taken,
   buy `trendkept.com` and say so — the rebrand is a five-minute job for
   your Claude session.
2. **Trademark sanity check (5 min).** Search "Trendrail" at
   trademarks.ipo.gov.uk and in the Companies House name search. You're
   looking for an existing trading-software company with the same name.
   Don't *register* a trademark yet — that waits for revenue (£220 for
   classes 9+42, later).
3. **Rename the GitHub repository (2 min).** Repo → Settings → rename
   `Archie` to `Trendrail`. Old links redirect automatically. Then merge
   the working branch — or ask Claude to open the pull request and just
   click Merge.

## Step 1 — This weekend: validate for £10 (~2 hours)

*No company yet, no bank yet — first, find out if anyone cares.*

1. **Put the landing page live (free, 20 min).** pages.cloudflare.com →
   Create a project → connect GitHub → pick the Trendrail repo → build
   output directory `site` → deploy → add the custom domain. The page is
   already built, waitlist included.
2. **Business email — yes, you need one (30 min).**
   - **Why:** payment processors trust a domain address; newsletter
     deliverability needs your own domain (a personal address lands in
     spam — that's lost revenue); and business signups stay separate from
     your personal email, which matters the day you sell the company.
   - **Create three addresses** (all can land in one inbox):
     `hello@trendrail.com` (public: support, website, social profiles),
     `[yourname]@trendrail.com` (private: registrar, Buttondown, later the
     bank and Paddle), and `news@trendrail.com` (the newsletter's sending
     address).
   - **Where:** if you already pay for any iCloud+ tier, custom email
     domains are **included free** — iPhone Settings → [your name] →
     iCloud → Custom Email Domain. No iCloud+? Zoho Mail's free tier.
     Google Workspace (~£5/mo) only once revenue exists. Either way it's
     ten minutes of copy-pasting DNS records (MX, SPF, DKIM) into
     Cloudflare — screenshot anything confusing and ask Claude.
3. **Create the newsletter (15 min).** buttondown.com → free tier → name it
   **The Trend Check** → sending address `news@trendrail.com` (two more DNS
   records). Give Claude the form URL and the landing-page signup box gets
   wired to it.
4. **Start the dogfooding clock (30 min).** Open a free Alpaca
   paper-trading account (fake money), put the keys in your environment as
   the README shows, and run the daily routine from today: dashboard scan
   (`python -m trendrail.web`) and `python -m trendrail.cli manage` after
   the close, 15 minutes a day. This is quality control, it generates your
   only honest marketing material, **and the r/swingtrading launch post is
   blocked until you have 4+ weeks of these logs** — so the clock starts
   now.

## Step 2 — Weeks 2–4: launch the free tier and read the signal

1. **Record a 60-second demo** of the dashboard (scan → backtest → hover
   the equity curve); it goes at the top of the README and landing page.
2. **Post, in this order** (drafts in `business/launch/` — every claim in
   them is true on the day you post; keep it that way):
   - **Show HN** (`show_hn.md`) — Tuesday–Thursday ~2pm UTC. Clear the
     whole day for comments; launch weeks are 25+ hours, plan them like
     sprints.
   - **r/algotrading** (`reddit_algotrading.md`) a few days later — all
     claims are about the code, postable as-is.
   - **r/swingtrading** (`reddit_swingtrading.md`) — **only after** the
     4-week paper-trading logs exist; fill its bracketed numbers from your
     real journal.
3. **Start the Sunday streak.** Run
   `python business/launch/trend_check.py --default`, paste the table into
   the Issue #1 template, add two sentences, send. **Every Sunday, no
   matter what.** (Ask Claude for the GitHub Action that auto-drafts it.)
4. **Day-30 validation read:** compare waitlist and stars to the curves in
   GO_TO_MARKET.md §6. A pulse → go to Step 3. Silence even after one
   messaging retry → stop here having spent ~£10, not ~£120 and a company.

## Step 3 — Month 2: incorporate and build the retention hook

1. **Incorporate Trendrail Ltd (~£50, 40 min).** gov.uk → "Set up a limited
   company". You need: the name (**Trendrail Ltd**), your details as sole
   director and shareholder (1 share, £1), SIC code **62012**. Buy a
   **registered-office address service** first (~£40/yr) so your home
   address isn't public. Approval usually within 24 hours.
2. **Business bank account (20 min, free).** Tide or Starling app, business
   account, photo ID, company number. Never mix funds.
3. **Have Claude build the trade journal** (the retention hook) while your
   newsletter streak and weekly content continue.

## Step 4 — Month 3: turn on the money (all of these, before any charge)

License a market-data feed (~£25–80/mo — the paid product must not run on
scraped Stooq/Yahoo data, LEGAL.md §5) · Paddle account · licence-key gate ·
ToS/privacy/refund pages · ICO registration (~£40) · indemnity + cyber
insurance (~£25/mo) · the professional review, UK **plus a US-perimeter
check** (~£300–500) · then the launch week: lifetime deal to the newsletter,
founding pricing, Product Hunt. Full detail in LAUNCH_CHECKLIST.md.

## Your operating rhythm (~10 h/week steady; launch weeks 25+)

- **Daily, 15 min:** dashboard scan on the paper account; answer support.
- **One evening:** paste the week's content piece (Claude drafts it); reply
  to comments in your own voice.
- **Sunday, ~30 min:** send The Trend Check; write down the four numbers —
  visitors, newsletter subscribers, paying subscribers, cancellations.
- **Monthly, 1 h:** give the four numbers to Claude → the model re-runs on
  reality and tells you which curve you're on.
- **Quarterly:** act on the gates (below). No exceptions.

## What this business is (one page, plain English)

**Trendrail sells discipline to hobbyist stock traders.** The free,
open-source core tests a written set of trend-following rules against real
market history and reports what the rules' conditions show today.
**Trendrail Pro (£12/mo or £99/yr)** is the cockpit: a browser dashboard, a
watchlist scanning many stocks at once, a trade journal that scores
rule-following, a daily "what the rules say" email — and the stop-loss
placed *with* the broker order, so exits don't depend on willpower.

**Why people pay:** the best-documented fact about retail trading is that
most people lose money through broken discipline, not bad picks. Someone
who just torched £2,000 ignoring their own rules compares £12/month to the
£2,000. Journalling tools (Edgewonk, TraderSync) prove the market pays for
discipline; Trendrail's edge is being the only one that structures the
trade *before* it happens — trend qualification, risk-based sizing, the
stop in the entry order — with an open-source, provably honest engine. And
the objection "my broker's bracket orders are free" has a straight answer:
a bracket is one rule (a static stop on a trade you already picked);
Trendrail is the whole ruleset, plus the scorecard.

**The money (from the honest model — `business/FINANCIALS.md`):**
~£9.66/subscriber/month after real payment fees. Costs step from ~£270/month
pre-revenue to ~£350–450/month running (licensed data feed, insurance,
newsletter tiers, AI tooling — all counted). Break-even at ~35–40
subscribers. Revenue starts month 3, when payments ship.

**Risk to reward, honestly:** worst realistic case is ~£3,500–4,000 cash
over year one plus your evenings — and the validate-first ordering means a
dead-on-arrival idea costs ~£10 and a few weekends before you'd have
incorporated anything. The **conservative scenario (the most likely one)**
builds to ~£4–5k/month profit by year 5 and ~£240k of combined value — a
genuinely good side business; **it never reaches £1M**. The **base
scenario** (the plan working) crosses £1M around **month 50**; the
**ambitious** one around month 27. No plan can promise the base case; this
one caps the downside, forces early decisions via the gates, and leaves the
upside uncapped — the same logic as the trading rules it sells.

**The gates (trajectory checks against the three modelled curves —
FINANCIALS.md):**

- **Day 90:** newsletter list vs curves (conservative ≈ 340, base ≈ 800).
  Below conservative and flat after a messaging retry → stop cheaply.
- **Month 6:** paying subs vs curves (conservative ≈ 65, base ≈ 230).
  On conservative → freeze features, distribution only, 8 weeks.
- **Month 12:** MRR vs curves. ≥£2k → winner, let it run. On the
  conservative curve → a deliberate choice: continue (the year-3-5 payoff
  requires it) or side-asset mode at ~2 h/week. Below and shrinking → sell
  the codebase + audience. Exiting a non-winner at a small profit is
  winning; drifting without deciding is the only losing move.

## Who does what

**You (short list, but only you):** identity-bound admin (domain, company,
bank, account signups), pressing "post" under your own name, replying to
comments in your own voice, the Sunday send, and the owner decisions
(pricing, launch timing, acting on the gates).

**Claude (Code sessions on the repo; Cowork for desktop work):** everything
else — every product feature on the roadmap, every content draft and
newsletter issue, comment-reply suggestions, the legal drafts for the
professional review, monthly model updates, and automations like the Sunday
draft generator. Its subscription is a real dependency, so it's a real line
in the cost model. You describe outcomes in plain English; you never need
to touch code.
