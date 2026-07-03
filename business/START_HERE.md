# START HERE — your steps, in order

This is the front door to the whole package. Do these steps in order; every
one is explained. Nothing needs anyone's permission and nothing before month 3
costs more than ~£150. The documents after this section contain the full
detail — this section is what you *do*.

## Step 0 — Today, from your phone (~30 minutes)

1. **Check the domain (2 min).** Go to Cloudflare Registrar or Namecheap and
   search `trendrail.com`. It showed no DNS records when checked (July 2026),
   so it is very likely free (~£10/yr). If it's somehow taken, buy
   `trendkept.com` (checked clear across .com/.io/.co.uk) and say so — the
   rebrand is a five-minute job for your Claude session.
2. **Trademark sanity check (5 min).** Search "Trendrail" at
   trademarks.ipo.gov.uk and in the Companies House name search. You're
   looking for an existing trading-software company with the same name.
   Don't *register* a trademark yet — that waits for revenue (~£170, later).
3. **Rename the GitHub repository (2 min).** Repo → Settings → rename
   `Archie` to `Trendrail`. Old links redirect automatically. Then merge the
   working branch (`claude/business-plan-ownership-8m18uu`) — or ask Claude
   to open the pull request and just click Merge.

## Step 1 — This weekend, part one: the company (~1 hour)

1. **Incorporate Trendrail Ltd (~£50, 40 min).** gov.uk → "Set up a limited
   company" → register online. You need: the company name (**Trendrail
   Ltd**), your details as sole director and sole shareholder (1 share, £1),
   and a SIC code — use **62012** (business and domestic software
   development). Before you start, buy a **registered-office address
   service** (~£40/yr, e.g. 1st Formations) so your home address isn't on
   the public record. Approval usually lands within 24 hours.
2. **Business bank account (20 min, free).** Download **Tide** or
   **Starling**, choose a business account, photograph your ID, enter the
   company number from the step above. Approved in a day or two. Never mix
   this money with personal money.

## Step 2 — This weekend, part two: domain, email, website (~1.5 hours)

1. **Buy `trendrail.com`** at Cloudflare Registrar (~£10/yr — you'll use
   Cloudflare for the website anyway).
2. **Business email — yes, you need one, and here's the exact setup.**
   - **Why:** payment processors (Paddle/Stripe) trust a domain address;
     newsletter deliverability needs your own domain (otherwise you're in
     spam folders — that's revenue); and every business account signup stays
     separate from your personal email, which matters the day you sell the
     company.
   - **Create three addresses** (all can land in one inbox):
     `hello@trendrail.com` (public: support, website, social profiles),
     `[yourname]@trendrail.com` (private: bank, Paddle, Cloudflare, GitHub
     signups), and `news@trendrail.com` (the newsletter's sending address).
   - **Where:** if you already pay for any iCloud+ storage tier, custom
     email domains are **included free** — iPhone Settings → [your name] →
     iCloud → Custom Email Domain → add `trendrail.com`, create the
     addresses, and mail arrives in the Mail app you already use. No iCloud+?
     Use Zoho Mail's free tier. Upgrade to Google Workspace (~£5/mo) only
     once revenue exists.
   - Either way it's ten minutes of copy-pasting DNS records (MX, SPF,
     DKIM) from the email provider into Cloudflare. Screenshot anything
     confusing and ask Claude.
3. **Put the landing page live (free, 20 min).** pages.cloudflare.com →
   Create a project → connect GitHub → pick the Trendrail repo → set the
   build output directory to `site` → deploy → add the custom domain
   `trendrail.com`. The page is already built (`site/index.html`), including
   per-visitor appearance settings (theme, accent colour, text size).
4. **Create the newsletter (15 min).** buttondown.com → free tier → name it
   **The Trend Check** → set the sending address to `news@trendrail.com`
   (it gives you two more DNS records — paste into Cloudflare). Then give
   Claude your Buttondown form URL and the landing-page signup box gets
   wired to it.

## Step 3 — Next week: become user #1 (~1 hour, then 15 min/day)

1. **Open an Alpaca paper-trading account** (free, alpaca.markets — choose
   *paper*, which is fake money). Put the two API keys in your environment
   as the README shows.
2. **Run the daily routine yourself:** open the dashboard
   (`python -m trendrail.web`), scan your watchlist, and run
   `python -m trendrail.cli manage` after market close. Fifteen minutes a
   day. This is quality control *and* it generates the honest screenshots
   and journal history that become your launch content.

## Step 4 — Weeks 2–4: launch (the part only you can do)

1. **Record a 60-second demo** of the dashboard (scan → backtest → hover the
   equity curve). It goes at the top of the README and the landing page.
2. **Post, one channel per 3–4 days, in this order.** All three posts are
   pre-written in `business/launch/` — copy, paste, post from your own
   accounts:
   - **Show HN** (`show_hn.md`) — Tuesday–Thursday, ~2pm UTC. Stay in the
     comments all day; the replies are the marketing.
   - **r/algotrading** (`reddit_algotrading.md`) a few days later.
   - **r/swingtrading** (`reddit_swingtrading.md`) the week after.
   Claude drafts your comment replies if you paste the thread; the posting
   account and the final voice must be yours — communities ban obvious
   proxies, and this brand runs on trust.
3. **Start the Sunday streak.** Run
   `python business/launch/trend_check.py --default`, paste the generated
   table into the Issue #1 template (`trend_check_001.md`), add two
   sentences, send. **Every Sunday, no matter what.** The streak is the
   single non-negotiable habit in this plan. (A GitHub Action can
   auto-generate the draft each Sunday — ask Claude to build it.)

## Your operating rhythm from then on (~2–4 focused hours/week)

- **Daily, 15 min:** dashboard scan on the paper account; answer any support.
- **One evening:** paste the week's content piece (Claude drafts it) to the
  scheduled channel; reply to comments.
- **Sunday, ~30 min:** send The Trend Check; write down the four numbers —
  visitors, newsletter subscribers, paying subscribers, cancellations.
- **Monthly, 1 h:** give the four numbers to Claude → the financial model is
  re-run with reality instead of assumptions.
- **Month 3:** turn on payments (Paddle + licence keys + the legal pack —
  see the Legal guide and checklist), run the Product Hunt launch.

## What this business is (one page, plain English)

**Trendrail sells discipline to hobbyist stock traders.** The free,
open-source core is a toolkit that tests a written set of trend-following
rules against real market history and says what the rules would do today.
**Trendrail Pro (£12/mo or £99/yr)** is the cockpit around it: a browser
dashboard, a watchlist that scans many stocks at once, a trade journal that
scores rule-following, a daily "what the rules say" email — and the
stop-loss order placed *with* the broker, so exits are enforced by the
broker rather than willpower.

**Why people pay:** the best-documented fact about retail trading is that
most people lose money not from bad picks but from broken discipline — no
stop-loss, oversized positions, panic exits. Someone who just torched £2,000
ignoring their own rules doesn't compare £12/month to other software; they
compare it to the £2,000. Comparable subscription tools (TradingView,
Edgewonk, TraderSync) prove the market pays. Trendrail's wedge is that
nobody else sells discipline: everyone else sells predictions and hype,
which is exactly why a calm, open-source, no-promises product stands out —
and why it stays on the right side of financial regulation.

**The money:** ~£10.50/subscriber/month blended revenue, ~£200/month total
running costs, break-even at ~20 subscribers. Two ways to win: monthly
profit, plus the business itself becomes a sellable asset (small
subscription software businesses sell for roughly 2–4× annual revenue).

**Risk to reward, honestly:** worst realistic case is ~£3,000 cash over year
one plus your evenings — and even then the code plus audience has salvage
value on micro-acquisition marketplaces. The conservative scenario (the most
likely one) builds a £8–10k/month asset by years 3–4 but does **not** reach
£1M in five years. The base scenario (the plan working) crosses £1M in
combined kept-profit and business value around month 26. No plan can
guarantee the base case; this one caps the downside, forces early exits via
review gates, and leaves the upside uncapped — the same logic as the
trading rules it sells.

**The review gates (the business's stop-losses):**

- **Month 3:** 1,000 newsletter subs *or* 500 GitHub stars — else change the
  message, not the product, and re-run for 8 weeks.
- **Month 6:** 50 paying subscribers — else freeze features; 8 weeks of
  distribution only.
- **Month 12:** £2k monthly recurring revenue → let it run (full-time at
  £5k). Under → keep as a side asset or sell the codebase + audience.
  Exiting a non-winner at a small profit is winning.

## Who does what

**You (it's a short list):** identity-bound admin (company, bank, domain,
account signups), pressing "post" under your own name, replying to comments
in your own voice, the Sunday send, and the owner decisions (pricing,
launch timing, acting on the gates).

**Claude (Code sessions on the repo, or Cowork for desktop work):**
everything else — building every product feature on the roadmap, drafting
all content and newsletter issues, comment-reply suggestions, the legal
document drafts for the solicitor to review, monthly financial-model
updates, and automations like the Sunday draft generator. You describe the
outcome in plain English; you never need to touch code.
