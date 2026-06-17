# 03 — Product Selection & Sourcing

## 3.1 How to choose the niche (don't guess — score it)

Score candidate niches 1–5 on each axis; pick the highest total. The goal is a
niche that is **consumable, habit-forming, low-regulatory-risk, and ownable.**

| Criterion | What good looks like |
|---|---|
| **Repeat consumption** | Used daily/regularly → natural subscription |
| **Established, safe ingredients** | Widely sold, no NDI issues, strong safety record |
| **Demonstrable demand** | Real search volume & existing competitors (competition = a market exists) |
| **Defensible angle** | A specific buyer, format, or quality story you can own |
| **Low claims risk** | Benefit can be described in compliant structure/function language |
| **Margin headroom** | Retail price supports ≥ 70% gross margin (see file 04) |

### Strong launch candidates (illustrative)
- **Magnesium glycinate (sleep/relaxation):** daily use, excellent safety,
  easy compliant copy ("supports relaxation and a healthy sleep cycle").
- **Creatine monohydrate (recovery/strength):** one of the most-studied,
  safest supplements; huge repeat demand.
- **Electrolyte mix (hydration):** daily use, strong subscription fit.
- **Daily greens:** higher AOV, strong habit, but more crowded.

> **Avoid at launch:** weight-loss/fat-burners (highest enforcement + health
> risk + ad-platform bans), "testosterone boosters," nootropic stacks with
> grey-market ingredients, anything making an implicit disease claim, and any
> novel/exotic ingredient (NDI risk).

## 3.2 White-label vs. private-label vs. true dropship

| Model | What it is | Use it? |
|---|---|---|
| **Generic dropship (marketplace ingestibles)** | Reselling unknown-factory supplements | **No.** Unsafe, non-compliant, no brand |
| **White-label** | Manufacturer's proven stock formula, **your label**, they ship | **Yes — start here.** Low cost, low risk, fast |
| **Private-label / custom formula** | Your own formulation, MOQ, your label | **Later**, once a SKU is proven |

Start white-label to validate demand with near-zero inventory risk, then move
your winning SKU to a custom private-label formula for better margin and
defensibility.

## 3.3 Supplier vetting — the gate that protects customers and you

A supplier must pass **all** of these or you walk away:

1. **Current cGMP / GMP certification** (21 CFR Part 111 in the US; verify the
   certificate, don't take their word).
2. **Per-batch Certificate of Analysis (CoA)** for identity, potency,
   contaminants (heavy metals, microbials).
3. **Third-party testing** available (NSF, USP, or independent lab).
4. **FDA-registered facility** (US) / appropriate registration for your market.
5. **Blind / white-label & branded shipping** capability (ships under *your*
   brand, no supplier marketing in the box).
6. **Written agreement** with quality specs, indemnification, and recall
   cooperation.
7. **References / track record**; ideally order samples and **independently lab
   test** them before committing.
8. **Realistic lead times and capacity** so you don't stock out.

> **Rule:** No CoA, no cGMP, no sale. This is the product-safety equivalent of
> the "confirmed uptrend" rule — if it isn't confirmed, you stay out.

### Where these suppliers are found
US/EU contract manufacturers and white-label "supplement fulfillment" companies
(many explicitly offer dropship/blind-ship). Prioritise domestic GMP facilities
over overseas marketplaces for ingestibles — the small extra COGS buys you
safety, faster shipping, and defensible compliance.

## 3.4 COGS targets

To hit the margins in file 04, target:

- **Landed unit cost (product + label + pick/pack + inbound):** ≤ 25–30% of
  retail price.
- **Per-order shipping to customer:** known and ideally baked into price or
  free-over-threshold.

If a supplier can't get you to ~70%+ gross margin at a believable retail price,
the niche or the supplier is wrong. Don't proceed on hope.

## 3.5 SKU strategy

- **Launch:** 1 hero SKU (+ maybe 1 size or 1 complement). That's it.
- **Add SKUs only** when the first is profitable and a clear cross-sell exists.
- **Bundles** (hero + complement) to lift AOV without adding much complexity.

Few SKUs = simpler compliance, simpler ops, less cash tied up, sharper brand.

## 3.6 Selling across categories (supplements + vitamins + skincare)

Selling supplements, vitamins **and** skincare under one brand ("beauty + wellness")
is a proven, coherent model — but treat it with discipline:

- **Architect for all three, launch one hero per category** (the demo store
  ships ~2–3 SKUs per category, not 30). Prove the economics (file 04) before
  going wide. Breadth multiplies compliance, inventory, and support load.
- **Skincare uses a different supplier and a different regime.** Find a
  **cosmetic-GMP (ISO 22716)** manufacturer with a safety-assessment / CPSR
  capability — *not* your supplement facility. Verify with `02 §2.7`.
- **The cross-sell is the point:** a vitamin C supplement buyer is a natural
  vitamin C serum buyer. Bundles across categories lift AOV and LTV.
- **Two compliance regimes, one gate:** route supplement/vitamin copy through
  the structure/function check and skincare copy through the cosmetic check
  (the `api/claims.py` gate does both; the server audits every product on start).
- **Margins differ:** skincare often carries strong gross margins but watch
  shelf life, actives stability, and higher return/irritation risk — model it.
