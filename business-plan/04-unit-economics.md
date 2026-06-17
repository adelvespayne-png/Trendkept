# 04 — Unit Economics (where the business is won or lost)

> A supplement brand lives or dies on three numbers: **gross margin**, **CAC**
> (customer acquisition cost), and **LTV** (lifetime value). If LTV doesn't
> comfortably exceed CAC, scaling ads just makes you lose money faster. Prove
> these on a small budget *before* scaling — same discipline as paper-trading
> before going live.

Run [`tools/unit_economics.py`](tools/unit_economics.py) to test your own
numbers. The figures below are **illustrative** to show the structure of the
math, not promises.

---

## 4.1 The per-order P&L (one bottle, one-time purchase)

| Line | Example | Note |
|---|---|---|
| Retail price | £35.00 | Premium, single niche |
| COGS (landed unit) | −£9.00 | ≤ ~26% (file 03 target) |
| Shipping to customer | −£4.00 | Or build into price |
| Payment processing (~3%) | −£1.05 | |
| Pick/pack/fulfillment fee | −£2.00 | If charged separately |
| **Contribution before ad spend** | **£18.95** | ~54% of price |

That ~£19 of contribution is your **budget to acquire and keep a customer**.
On a one-off sale, if CAC > £19 you lose money. This is why one-off DTC
supplement businesses so often fail — and why subscription is the answer.

## 4.2 Why subscription changes everything

A subscriber who reorders for, say, **6 months** turns one acquisition into
multiple contribution events:

```
LTV ≈ contribution_per_order × expected_number_of_orders
```

If contribution is ~£19 and the average subscriber stays ~6 orders:

```
LTV ≈ £19 × 6 ≈ £114
```

Now a CAC of, say, £30 is healthy:

```
LTV / CAC ≈ £114 / £30 ≈ 3.8  →  above the 3× minimum ✅
```

The same CAC against a single £19 one-off order would be a **loss**.

## 4.3 The three gates (don't scale until all three pass)

These are hard go/no-go thresholds. Test at small spend first.

1. **Gross margin ≥ ~70%** (before ads). If not, fix COGS or price.
2. **LTV : CAC ≥ 3 : 1.** Below 3, the model is fragile; below 1, you're
   lighting money on fire.
3. **CAC payback < 90 days** (ideally < 60). You must recover acquisition cost
   fast, because you're funding the next order's inventory and ads from cash.

> If any gate fails, the answer is **not** "spend more to grow into it." It's
> stop, diagnose (price, COGS, retention, or channel), and fix.

## 4.4 The retention lever (the highest-leverage number)

Because LTV is `contribution × orders`, **churn is the master variable.**
Improving month-over-month retention does more for profit than cheaper ads.

Levers that move retention:
- A product that genuinely works and arrives reliably.
- Easy reorder + truly easy cancel (paradoxically lowers churn — trust).
- Lifecycle email/SMS: onboarding, "how to use," refill reminders, win-backs.
- Bundles and "subscribe and save" framing.

This is where the **AI automation** (file 06) earns its keep: it runs the
lifecycle messaging cheaply so retention stays high without a big team.

## 4.5 Cash-flow reality (the silent killer)

Even a profitable-on-paper business dies if it runs out of cash:

- **CAC is paid today; LTV arrives over months.** The faster you scale, the
  more cash you front for acquisition before it's repaid.
- **Starting white-label/dropship** (file 03) keeps inventory cash near zero
  at launch — deliberately. Only buy bulk inventory once a SKU is proven,
  because bulk improves margin but ties up cash and adds spoilage/expiry risk.
- **Chargebacks and refunds** are real costs — model them (file 07).

> **Cash rule:** never commit spend (ads or inventory) beyond a loss you can
> absorb without sinking the business. Grow from profit and proven payback,
> not from hope or debt you can't service.

## 4.6 What to actually do with this file

1. Open `tools/unit_economics.py`, put in *your* real quotes (supplier COGS,
   shipping, processor fee, expected price).
2. Estimate retention conservatively (assume customers churn faster than you'd
   like).
3. Only greenlight a channel in file 05 once the three gates in 4.3 pass at
   small scale with **real** data, not projections.
