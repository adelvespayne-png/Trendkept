# 08 — Risk Register

> Everything that can realistically go wrong, ranked by severity × likelihood,
> with the mitigation already baked into this plan. A risk you've named and
> defended is a risk that can't quietly kill you. This is the "survival first"
> half of the strategy.

Legend — **Severity**: how bad if it happens. **Likelihood**: how probable if
unmanaged. The plan's job is to drive likelihood down.

| # | Risk | Sev | Likelihood (unmanaged) | Mitigation (in this plan) |
|---|------|-----|------------------------|---------------------------|
| 1 | **Illegal health claim → FTC/FDA action, fines, shutdown** | Critical | High | Claims rules (02) + automated claims gate (06) + human sign-off on all copy |
| 2 | **Product harms a customer (contamination/adulteration/allergen)** | Critical | Medium | cGMP-only supplier + per-batch CoA + 3rd-party testing + product liability insurance (02, 03) |
| 3 | **Negative unit economics at scale (CAC ≥ LTV)** | Critical | High | The three gates + calculator; never scale a channel that fails them (04) |
| 4 | **Cash crunch from fronting ads/inventory** | High | Medium | Dropship/white-label first; grow from proven payback; spend cap (04, 07) |
| 5 | **Payment processor freezes/drops account** | High | Medium | Honest offer (no free-trial auto-ship), low chargebacks, backup processor (02, 07) |
| 6 | **Ad account / platform ban** | High | Medium | Compliant creative + diversified channels + owned email/SMS list (05) |
| 7 | **Excessive chargebacks** | High | Medium | Clear terms, one-click cancel, refill reminders, fast support, recognisable descriptor (07) |
| 8 | **Single-supplier failure / stockout / quality lapse** | High | Medium | Backup supplier identified; batch tracking; written quality + indemnity agreement (03, 07) |
| 9 | **High churn destroys LTV** | High | High | Product that works + lifecycle messaging + easy management; churn watched weekly (04, 05) |
| 10 | **Subscription/auto-renew law violation (click-to-cancel)** | High | Medium | Lawyer-drafted, compliant, genuinely easy cancel (02) |
| 11 | **Adverse-event reporting failure** | High | Low–Med | Escalation + logging process; humans handle, AI never (02, 06, 07) |
| 12 | **Label non-compliance → recall** | High | Medium | Regulatory consultant reviews artwork before first print (02) |
| 13 | **Data breach / privacy violation (GDPR/CCPA/TCPA)** | Medium–High | Low–Med | PCI processors, no card storage, consent + deletion process (07) |
| 14 | **Commoditisation / price war** | Medium | Medium | Compete on trust/niche/transparency, never price; brand ownership (01, 05) |
| 15 | **Over-reliance on one marketing channel** | Medium | Medium | 2–3 tested channels + owned list as the durable asset (05) |
| 16 | **AI publishes a non-compliant or wrong claim** | High | Medium | Bright line: AI drafts, human approves; claims gate never auto-approves (06) |
| 17 | **Founder bandwidth / burnout (tiny team)** | Medium | Medium | AI automation of repetitive work; few SKUs; tight operating rhythm (06, 07) |
| 18 | **Demand never materialises in chosen niche** | Medium | Medium | Validate with small paid test before any inventory/commitment (04, 09) |

## The meta-mitigation

Every "Critical" row is neutralised by a **rule that says "don't proceed"**:

- No confirmed compliance → don't sell (02).
- No CoA / cGMP → don't sell (03).
- Gates fail → don't scale (04).
- Can't absorb the loss → don't spend (04).

That's the whole philosophy: **make ruin impossible, and you get unlimited
attempts to find profit.** The plan is designed so the worst realistic outcome
is "this niche didn't work, try another," not "we got sued / hurt someone / went
bankrupt."

## What this register does NOT promise

It does not promise success. Demand can be soft, a competitor can out-execute
you, ad costs can rise. Those are *recoverable* business risks — you lose a test
budget, not the company. The register's job is to ensure no single event is
*fatal*. Manage these well and the downside is bounded while the upside is not.
