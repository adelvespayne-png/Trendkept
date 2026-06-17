# 07 — Operations & Fulfillment

> Boring, but this is where margin leaks and trust is lost. The aim: a process
> so clean that a tiny team (you + AI) can run it without dropping orders,
> botching refunds, or losing the payment processor.

## 7.1 Order-to-delivery flow

```
Customer orders on store
   → payment captured (processor approved for supplements, file 02)
   → order routed automatically to white-label supplier / 3PL
   → supplier blind-ships under YOUR brand (no supplier marketing in box)
   → tracking synced back to customer (automated email/SMS)
   → subscription scheduled for next cycle
```

Keep it automated end-to-end via the store + supplier integration (file 06).
The only manual touches should be exceptions.

## 7.2 Inventory & supplier discipline

- **Launch:** white-label/dropship → near-zero inventory, near-zero cash risk.
- **Once a SKU is proven:** consider holding bulk stock for margin — but only
  after weighing **cash tied up + expiry/spoilage risk** (supplements have
  shelf lives and lot/batch tracking obligations).
- **Always keep a backup supplier** identified for your hero SKU. Single-
  supplier dependency is a real risk (file 08).
- **Batch/lot tracking + CoA on file** for every batch sold — essential for a
  recall and for adverse-event traceability.

## 7.3 Returns, refunds & quality issues

- **Clear, fair, lawful return policy** published at checkout.
- **Quality complaint** → log it, request lot number, pull the CoA, escalate to
  a human. If it's a safety issue, follow the **adverse-event reporting**
  process (file 02) and consider whether a recall is warranted.
- **AI may draft refund replies; humans approve** anything beyond a small
  pre-set auto-refund threshold.

## 7.4 Chargebacks (protect your payment processor — it's your lifeline)

Supplements + subscriptions are a **high-chargeback category**, and excessive
chargebacks get you **dropped by your processor**, which can halt the business.

Minimise them by design:
- **Honest, clear pricing and subscription terms** (no surprise auto-ship).
- **One-click cancel** and obvious subscription management.
- **Recognisable billing descriptor** so customers know what the charge is.
- **Proactive refill reminders** before each renewal charge.
- **Fast, human support** so people email you instead of disputing.
- **Track chargeback rate as a first-class metric**; investigate any spike.

> The single best chargeback defense is *not running a sketchy offer.* The
> honest model (file 02) is also the safest commercially.

## 7.5 Customer support

- **Tier 1 (FAQ, shipping, sub management):** AI-drafted, human-approved (or
  human-light for the most routine), fast SLA.
- **Tier 2 (complaints, health questions, refunds):** human, always.
- **Adverse events:** immediate human escalation + log (legal duty).
- A good support experience is a **retention and chargeback** tool, not a cost
  center — treat it as such.

## 7.6 Data, privacy & security

- Customer PII and payment data → use PCI-compliant processors; don't store card
  data yourself.
- **GDPR/CCPA**: consent for marketing, easy unsubscribe, data-deletion process.
- **SMS**: TCPA-style opt-in compliance.
- Keep records: orders, CoAs, batch numbers, complaints, adverse events,
  claim-notification filings.

## 7.7 The weekly operating rhythm (small team + AI)

| Cadence | Review |
|---|---|
| **Daily** | Orders shipped, support queue clear, any adverse-event flags, ad spend vs. cap |
| **Weekly** | CAC/LTV/payback by channel, churn, refund + chargeback rate, inventory/lead times |
| **Monthly** | P&L, cash position, supplier performance, retention cohort curve, compliance review of new copy |

This rhythm is the business equivalent of "follow the rules every time" — the
edge is in the consistency, not any single heroic move.
