#!/usr/bin/env python3
"""Supplement-brand unit-economics calculator.

Dependency-free (Python 3.9+ standard library only), in the same spirit as the
rest of this repo: write the numbers down, test them, and don't scale anything
that fails the gates.

It computes, for a single SKU + subscription model:

  * per-order contribution margin (before ad spend)
  * gross margin %
  * lifetime value (LTV) from expected number of orders
  * LTV : CAC ratio
  * CAC payback (in orders and approx. days)

...and checks them against the three go/no-go gates from
``04-unit-economics.md``:

  1. gross margin   >= 70%
  2. LTV : CAC      >= 3 : 1
  3. CAC payback    <  90 days

ALL NUMBERS BELOW ARE ILLUSTRATIVE PLACEHOLDERS. Replace them with your real
supplier quotes and measured marketing data before trusting any output. This
tool does not predict the future or guarantee profit; it just enforces
arithmetic discipline.

Usage:
    python3 unit_economics.py                # run with the example scenario
    python3 unit_economics.py --help         # see all overridable inputs

Example:
    python3 unit_economics.py --price 35 --cogs 9 --ship 4 \\
        --cac 30 --orders 6 --cycle-days 30
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

# --- Gate thresholds (from 04-unit-economics.md). Tune only with good reason. --
MIN_GROSS_MARGIN = 0.70   # 70%
MIN_LTV_CAC = 3.0         # 3 : 1
MAX_PAYBACK_DAYS = 90.0   # days


@dataclass
class Scenario:
    """All inputs to the model. Currency-agnostic (use one currency throughout)."""

    price: float            # retail price per order
    cogs: float             # landed unit cost (product + label + inbound)
    shipping: float         # outbound shipping cost per order (0 if baked into price)
    fulfillment_fee: float  # pick/pack/3PL fee per order
    processing_rate: float  # payment processing as a fraction of price (e.g. 0.03)
    cac: float              # customer acquisition cost (per acquired customer)
    expected_orders: float  # avg number of orders a customer makes (1 = one-off)
    cycle_days: float       # days between subscription orders


@dataclass
class Result:
    contribution_per_order: float
    gross_margin: float
    ltv: float
    ltv_cac: float
    payback_orders: float
    payback_days: float


def evaluate(s: Scenario) -> Result:
    """Compute the unit economics for a scenario.

    Contribution per order is what's left of the price after the variable costs
    of delivering that order, *before* any advertising spend. That pool is what
    pays back CAC and ultimately becomes profit.
    """
    processing_cost = s.price * s.processing_rate
    variable_cost = s.cogs + s.shipping + s.fulfillment_fee + processing_cost
    contribution = s.price - variable_cost

    # Gross margin = (price - COGS) / price. This is the standard product-margin
    # definition the 70% gate in file 04 refers to (COGS is product cost only;
    # shipping/fulfillment/processing are operating/variable costs captured in
    # contribution, not in gross margin).
    gross_margin = (s.price - s.cogs) / s.price if s.price else 0.0

    ltv = contribution * s.expected_orders
    ltv_cac = (ltv / s.cac) if s.cac else float("inf")

    # How many orders (and days) to recover CAC from contribution.
    if contribution > 0:
        payback_orders = s.cac / contribution
        payback_days = payback_orders * s.cycle_days
    else:
        payback_orders = float("inf")
        payback_days = float("inf")

    return Result(
        contribution_per_order=contribution,
        gross_margin=gross_margin,
        ltv=ltv,
        ltv_cac=ltv_cac,
        payback_orders=payback_orders,
        payback_days=payback_days,
    )


def gates(r: Result) -> list[tuple[str, bool, str]]:
    """Return (name, passed, detail) for each go/no-go gate."""
    return [
        (
            "Gross margin >= 70%",
            r.gross_margin >= MIN_GROSS_MARGIN,
            f"{r.gross_margin * 100:.1f}%",
        ),
        (
            "LTV : CAC >= 3 : 1",
            r.ltv_cac >= MIN_LTV_CAC,
            f"{r.ltv_cac:.2f} : 1",
        ),
        (
            "CAC payback < 90 days",
            r.payback_days < MAX_PAYBACK_DAYS,
            f"{r.payback_days:.0f} days",
        ),
    ]


def render(s: Scenario, r: Result) -> str:
    lines = []
    lines.append("=" * 56)
    lines.append("  SUPPLEMENT UNIT ECONOMICS  (illustrative inputs)")
    lines.append("=" * 56)
    lines.append("")
    lines.append("Inputs")
    lines.append(f"  Retail price ............... {s.price:>10.2f}")
    lines.append(f"  COGS (landed) .............. {s.cogs:>10.2f}")
    lines.append(f"  Outbound shipping .......... {s.shipping:>10.2f}")
    lines.append(f"  Fulfillment fee ............ {s.fulfillment_fee:>10.2f}")
    lines.append(f"  Processing ({s.processing_rate * 100:.1f}%) ......... "
                 f"{s.price * s.processing_rate:>10.2f}")
    lines.append(f"  CAC ........................ {s.cac:>10.2f}")
    lines.append(f"  Expected orders / customer . {s.expected_orders:>10.2f}")
    lines.append(f"  Order cycle (days) ......... {s.cycle_days:>10.0f}")
    lines.append("")
    lines.append("Results")
    lines.append(f"  Contribution / order ....... {r.contribution_per_order:>10.2f}")
    lines.append(f"  Gross margin ............... {r.gross_margin * 100:>9.1f}%")
    lines.append(f"  LTV ........................ {r.ltv:>10.2f}")
    lines.append(f"  LTV : CAC .................. {r.ltv_cac:>10.2f}")
    lines.append(f"  CAC payback ................ {r.payback_orders:>6.2f} orders "
                 f"(~{r.payback_days:.0f} days)")
    lines.append("")
    lines.append("Go / No-Go Gates")
    all_pass = True
    for name, passed, detail in gates(r):
        mark = "PASS" if passed else "FAIL"
        all_pass = all_pass and passed
        lines.append(f"  [{mark}] {name:<26} {detail}")
    lines.append("")
    if all_pass:
        lines.append("  VERDICT: all gates pass at these inputs. Validate with")
        lines.append("           REAL data at small scale before scaling spend.")
    else:
        lines.append("  VERDICT: at least one gate FAILS. Do NOT scale. Fix price,")
        lines.append("           COGS, retention, or channel first (see file 04).")
    lines.append("=" * 56)
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> Scenario:
    p = argparse.ArgumentParser(
        description="Supplement-brand unit-economics calculator (illustrative).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--price", type=float, default=35.0, help="retail price per order")
    p.add_argument("--cogs", type=float, default=9.0, help="landed unit cost")
    p.add_argument("--ship", type=float, default=4.0, help="outbound shipping/order")
    p.add_argument("--fulfillment", type=float, default=2.0, help="pick/pack fee/order")
    p.add_argument("--processing", type=float, default=0.03,
                   help="payment processing rate (fraction of price)")
    p.add_argument("--cac", type=float, default=30.0, help="customer acquisition cost")
    p.add_argument("--orders", type=float, default=6.0,
                   help="expected orders per customer (1 = one-off)")
    p.add_argument("--cycle-days", type=float, default=30.0,
                   help="days between subscription orders")
    a = p.parse_args(argv)
    return Scenario(
        price=a.price,
        cogs=a.cogs,
        shipping=a.ship,
        fulfillment_fee=a.fulfillment,
        processing_rate=a.processing,
        cac=a.cac,
        expected_orders=a.orders,
        cycle_days=a.cycle_days,
    )


def main(argv: list[str] | None = None) -> int:
    scenario = parse_args(argv)
    result = evaluate(scenario)
    print(render(scenario, result))
    # Exit non-zero if any gate fails, so this can be used in scripts/CI.
    return 0 if all(passed for _, passed, _ in gates(result)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
