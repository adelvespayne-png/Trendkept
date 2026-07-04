# Critique — Trendrail Owner's Manual, revised edition (36 pages, 03 July 2026)

Second-round evaluation of the rebuilt manual (commit `390c95d`, "Rebuild the plan against
external review"). Verified: the new `business/model.py` reproduces every table in the PDF
exactly; all 69 tests pass; the launch drafts match the new honesty rules.

---

## 1. What the revision fixed — and fixed properly

All seven priority items from the first review were implemented, and most are real repairs,
not cosmetic patches:

- **The gate contradiction is resolved structurally.** Gates are now trajectory checks
  against three modelled curves with a prescribed decision per band, and §9 openly names the
  old contradiction. The month-12 "conservative" band now demands a *deliberate* choice
  instead of pretending both outcomes at once.
- **The model was genuinely rebuilt**: revenue starts month 3; fees are 5% + £0.50 (~8–9%
  effective); churn is 10%/7%/5% with the source honesty stated ("hobbyist-trader B2C
  reality, not SaaS-blog folklore"); traffic is spike-and-decay (55%/mo) instead of a smooth
  hockey stick; costs step (£260 pre-revenue → £350–450 loaded, including the AI
  subscription, data feed, insurance, newsletter tiers); launch offers are modelled;
  valuation moved from 3×ARR to 3× trailing SDE profit. Every one of these moves the
  numbers *against* the plan's favour. The headline consequences are absorbed honestly:
  base-case £1M slips from month 26 to 50, conservative drops to £240k at year 5.
- **The astroturfing is gone.** The r/swingtrading post is hard-blocked until 4+ weeks of
  real logs exist and quotes them via brackets; the r/algotrading post claims only things
  true of the code; an explicit anti-invented-war-stories rule is in the GTM positioning.
- **Data licensing** got its own LEGAL §5, a risk-table row, a cost line, and a
  before-first-invoice checklist item. **US perimeter** is acknowledged with a working legal
  theory (publisher's exclusion) and the newsletter register softened to descriptive
  language. **Validate-first ordering** (£10 before £100), WHOIS instead of DNS, £220
  trademark, waivable cooling-off, insurance, launch weeks at 25+ hours, the broker-bracket
  objection answered, the wedge narrowed to a defensible claim — all corrected.

This is what a good revision looks like. Now the remaining problems, which are fewer but
not small.

---

## 2. The month-3 lifetime spike is load-bearing and fragile

The launch offers are now modelled — good — but look at what they're assumed to do:

- Lifetime deals sold: 20 / 60 / 150 across scenarios, into newsletter lists of ~338 / 802 /
  1,910 at month 3. That is a **6–8% list-to-£299 conversion inside a two-week window**, on
  a paid product that is two weeks old with no track record. Typical launch conversion of a
  warm list is 1–3% — at a tenth of that price point.
- In the conservative case, that one-off £5.5k spike **is** year one: cumulative profit at
  month 12 is £5.3k. Without the lifetime deal the "most likely" business is cash-negative
  through year one and beyond.
- The milestone line "Monthly profit turns positive: month 3" is generated off this one-off;
  recurring profit is **−£8 in month 6**. The prose admits recurring break-even is months
  6–7, but the milestone table still headlines month 3 in all three scenarios.

Fixes: make the milestone measure *recurring* profit; sensitivity-test lifetime sales at
5/20/50; and consider moving the lifetime presale *earlier* — it is the honest
willingness-to-pay validation instrument the plan currently lacks (see §6).

## 3. The "honest model" has no taxes in it

LEGAL §6 correctly describes corporation tax at 19–25%, yet the model's cumulative profit —
and therefore "net worth" and the £1M milestone — is entirely pre-tax. Post-CT, base-case
£1M at month 50 is roughly £800k, before dividend tax on extraction. For a model that brands
itself the "honest edition" and enumerates £25/mo insurance, omitting the single most certain
cost in the plan is the largest remaining gap between the label and the contents. One line
(`profit *= 0.75` above small-profits thresholds) fixes it.

## 4. The trajectory gates can be dissolved by their own update loop

The plan instructs: replace assumptions with actuals monthly and regenerate FINANCIALS.md;
the gates compare actuals to "the curves." But if the curves are re-fitted to actuals every
month, they converge toward whatever is actually happening, and the gates quietly lose their
bite — the goalposts walk themselves to the ball. The fix is cheap and should be explicit:
**freeze the day-0 curves as the gate reference** and maintain the re-fitted model as a
separate live forecast. Relatedly, the day-90 gate is under-powered: conservative list ≈340
vs base ≈800 is well within the swing of a single lucky-or-unlucky HN submission, so the
gate partly measures distribution luck, not message validation. Use a basket (list + stars +
waitlist-to-visitor rate) rather than one number.

## 5. The founder persona is still borrowed — the biggest unresolved integrity issue

The fake war stories are gone, but the larger impersonation survives. The Show HN draft
says "**I built Trendrail**" and the comment playbook demands fast, technical,
code-referencing replies — while the plan's own division of labour states the owner "never
needs to touch code" and Claude writes "every product feature." On Hacker News specifically:

- an owner who cannot discuss their own architecture live is one probing thread away from a
  visible credibility failure, precisely on the launch that matters most;
- undisclosed AI authorship is itself a recurring HN flashpoint, and this brand's stated
  moat is honesty.

Two coherent options: **disclose the AI-built nature** (arguably a *stronger* HN story —
"I directed an AI to build a causally-honest backtester; here's what it got wrong" — and it
future-proofs every later reveal), or invest the hours for the owner to genuinely know the
codebase before launch. The current plan — paste Claude-drafted technical replies under a
technical-founder persona — is the same fabricated-authenticity risk the revision just paid
to remove elsewhere, relocated to the highest-visibility channel.

## 6. Validation still measures resonance, not willingness to pay

Waitlist signups and GitHub stars validate the *message*; they are famously weak proxies for
paying £12/mo. The plan already owns the right instrument — the £299 lifetime / £79
founding presale — but doesn't fire it until month 3, after incorporation and build-out.
Offering the founding presale to the day-30 waitlist (money refundable if the product
doesn't ship) would convert the validation gate from "did people click?" to "did people
pay?" for £0 of extra cost. Also still absent after two editions: any plan to *talk to ten
traders*. Every persona claim remains introspection.

## 7. Duplication drift — the disease continues in the cured document

Exactly the failure mode the first review predicted for a multi-copy document, present in
the copy that fixed it:

- Plan §0: "your costs are **~£200/mo**" — the model now says £270 pre-revenue, £350–450
  loaded.
- Plan §1: "runs on your laptop and a **£200/mo stack**" — same stale figure.
- Plan §1: businesses "sell for **2–4× ARR** on Acquire.com" — the model's assumptions
  block explicitly corrects this to ~2.5–4× *SDE profit*, "not ARR." The pitch section and
  the model section of the same document now disagree about the valuation basis by roughly
  a factor of three.

`build_manual.py` exists; the hand-written sections need the same generated-from-source
discipline as FINANCIALS.md, or at minimum a consistency pass per rebuild.

## 8. The conservative case is now honest — and the plan won't look at what it shows

Full credit: the most-likely scenario is no longer flattered. But the plan also never states
what its own numbers imply. Conservative year one: ~£5.3k cumulative profit for ~500 hours
of evenings — **≈£10/hour, below UK minimum wage** — reaching £4.3k/mo profit only in year
5, for £240k of total pre-tax value. The month-12 gate offers "continue vs side-asset mode"
but omits the comparison every rational owner will actually run: those same 10 h/week
against freelance rates or career investment. A document this candid should put the
effective hourly rate next to the cumulative-profit column and let the owner decide with
eyes open. Relatedly, "worst realistic case ~£3,500–4,000 over year one" assumes running all
twelve months with zero revenue — but the day-90 gate would have stopped that spend at
~£300–600. The plan is now more pessimistic than its own rules in one paragraph and silent
on opportunity cost in the next.

## 9. Smaller residuals

- **US legal budget**: £300–500 *total* including the UK solicitor underbudgets a US
  securities-law opinion, which alone typically exceeds that. Treat the number as a floor.
- **£80/mo AI tooling** is light for the subscription tier that "builds every product
  feature" (current top tiers run ~£90–180/mo). Directionally counted, undersized.
- **Hosted tier trade-off** is handled correctly (no broker keys server-side) but the
  claim "removes the biggest funnel drop" is now only partly true: the flagship
  broker-enforced-stop feature remains install-only. Say so.
- **Churn sensitivity**: the document twice calls churn the highest-leverage variable, yet
  there is still no sensitivity table — one scenario per churn value is a point estimate,
  not an analysis. A 3×3 grid (churn × conversion) would cost ten lines of code.
- **Support burden** at base-case 2,218 subscribers remains absent from both the cost model
  and the 10 h/week budget.
- Newsletter list churn is modelled (2%/mo) — good — but engagement decay (open rates
  falling with list age) affects the list→paid conversion and isn't.

---

## Verdict

The revision is genuine. The model was rebuilt rather than re-labelled, every change moved
against the plan's own interest, the gates now form a coherent decision system, and the
launch content went from a firing offence to a defensible standard. Two editions in, this is
an unusually self-honest planning document.

What remains: one **fragile assumption doing structural work** (the month-3 lifetime spike
that single-handedly makes year one profitable in the likely case), one **honesty gap** (a
pre-tax "£1M net worth" in a self-described honest model), one **self-defeating mechanism**
(gates benchmarked against curves the owner is told to re-fit monthly), and one
**unresolved identity problem** (a non-technical owner launching under a technical-founder
persona on the internet's most forensic forum). The first three are afternoon fixes. The
fourth is a decision — disclose or learn — and it should be made before the Show HN post,
because it is the same class of risk the rest of this revision was written to eliminate.
