"""Archie Pro financial model — the path-to-£1M calculator.

    python business/model.py                # print all scenarios
    python business/model.py --md           # regenerate business/FINANCIALS.md

Same philosophy as the trading rules: write the assumptions down, run the
numbers mechanically, and never let a wish masquerade as a forecast. Every
input below is a knob you can change; the maths is just a subscriber-flow
simulation:

    new subscribers   = monthly visitors x visitor->paid conversion
    churned           = active subscribers x monthly churn
    active            = active + new - churned

"Net worth" counts two things: cumulative owner profit (cash you kept) plus
what the business itself would sell for (a sober 3x ARR for a small,
owner-operated SaaS; real multiples range roughly 2-4x). The model reports the
month each milestone is crossed — or says plainly that it never is.

Honesty notes, before you believe any row:
* The conservative scenario is the most likely one. Most tool businesses die
  of no-distribution, not bad product. The plan's job is to move you from
  conservative toward base, and to cut the loss early if it isn't working —
  cut losers fast, let winners run applies to the business too.
* Churn is the lever that matters most. Halving churn roughly doubles the
  steady-state subscriber count; no growth hack compensates for a leaky bucket.
* Annual plans prepay cash but recognize monthly here; real cashflow is
  slightly front-loaded (in your favour).
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import List, Optional

# --- pricing ---------------------------------------------------------------
PRICE_MONTHLY = 12.0      # GBP / month
PRICE_ANNUAL = 99.0       # GBP / year (a ~31% discount; prepaid cash)
ANNUAL_MIX = 0.40         # fraction of subscribers who choose annual
PAYMENT_FEES = 0.04       # Stripe/Paddle + FX, as a fraction of revenue

# Blended monthly revenue per active subscriber, before fees.
ARPU = (1 - ANNUAL_MIX) * PRICE_MONTHLY + ANNUAL_MIX * (PRICE_ANNUAL / 12.0)

# --- costs (solo owner; salary excluded — profit IS the owner's pay) --------
FIXED_MONTHLY = 200.0     # hosting, email, licences, accounting software
VARIABLE_PER_SUB = 0.10   # support tooling, data egress, per-subscriber cruft

VALUATION_MULTIPLE = 3.0  # x ARR — sober for a small owner-run SaaS (2-4x)
HORIZON_MONTHS = 60


@dataclass(frozen=True)
class Scenario:
    name: str
    story: str
    visitors_start: float      # monthly site/channel visitors at launch
    visitor_growth: float      # month-over-month growth while below the cap
    visitors_cap: float        # audience plateau for this level of effort
    conversion: float          # visitor -> paying subscriber
    churn: float               # monthly subscriber churn


SCENARIOS = [
    Scenario(
        name="Conservative",
        story=("Content gets modest traction; you keep the day job. This is "
               "the most likely outcome and the one to budget your life "
               "around."),
        visitors_start=2_000, visitor_growth=0.08, visitors_cap=15_000,
        conversion=0.005, churn=0.06,
    ),
    Scenario(
        name="Base",
        story=("The plan works: weekly content compounds, a channel or two "
               "takes off, churn stays tame because the tool is genuinely "
               "used daily."),
        visitors_start=4_000, visitor_growth=0.12, visitors_cap=30_000,
        conversion=0.007, churn=0.05,
    ),
    Scenario(
        name="Ambitious",
        story=("A breakout: front page of HN/Product Hunt, a big YouTube "
               "collab, word of mouth. Plan for it, don't count on it."),
        visitors_start=6_000, visitor_growth=0.18, visitors_cap=120_000,
        conversion=0.010, churn=0.04,
    ),
]


@dataclass
class MonthRow:
    month: int
    visitors: float
    new_subs: float
    churned: float
    active: float
    mrr: float                 # net of payment fees
    profit: float              # mrr - fixed - variable
    cum_profit: float
    valuation: float           # VALUATION_MULTIPLE x ARR
    net_worth: float           # cum_profit + valuation


def simulate(sc: Scenario, months: int = HORIZON_MONTHS) -> List[MonthRow]:
    rows: List[MonthRow] = []
    active = 0.0
    cum_profit = 0.0
    visitors = sc.visitors_start
    for m in range(1, months + 1):
        new = visitors * sc.conversion
        churned = active * sc.churn
        active = active + new - churned
        mrr = active * ARPU * (1 - PAYMENT_FEES)
        profit = mrr - FIXED_MONTHLY - active * VARIABLE_PER_SUB
        cum_profit += profit
        valuation = mrr * 12 * VALUATION_MULTIPLE
        rows.append(MonthRow(
            month=m, visitors=visitors, new_subs=new, churned=churned,
            active=active, mrr=mrr, profit=profit, cum_profit=cum_profit,
            valuation=valuation, net_worth=cum_profit + valuation,
        ))
        visitors = min(visitors * (1 + sc.visitor_growth), sc.visitors_cap)
    return rows


def first_month(rows: List[MonthRow], attr: str, threshold: float
                ) -> Optional[int]:
    for r in rows:
        if getattr(r, attr) >= threshold:
            return r.month
    return None


def _fmt_month(m: Optional[int]) -> str:
    if m is None:
        return f"not within {HORIZON_MONTHS} months"
    years, rem = divmod(m - 1, 12)
    return f"month {m} (~year {years + 1})"


def scenario_report(sc: Scenario, md: bool = False) -> str:
    rows = simulate(sc)
    sample = [r for r in rows if r.month % 6 == 0 or r.month == 1]

    out: List[str] = []
    if md:
        out.append(f"### {sc.name}\n")
        out.append(f"*{sc.story}*\n")
        out.append("| Month | Visitors | Active subs | MRR (net) | "
                   "Profit /mo | Cum. profit | Valuation (3x ARR) | "
                   "Net worth |")
        out.append("|---|---|---|---|---|---|---|---|")
        for r in sample:
            out.append(
                f"| {r.month} | {r.visitors:,.0f} | {r.active:,.0f} | "
                f"£{r.mrr:,.0f} | £{r.profit:,.0f} | £{r.cum_profit:,.0f} | "
                f"£{r.valuation:,.0f} | £{r.net_worth:,.0f} |")
        out.append("")
    else:
        out.append(f"== {sc.name} ==")
        out.append(sc.story)
        out.append(f"  {'mo':>3} {'visitors':>9} {'subs':>7} {'MRR':>9} "
                   f"{'profit/mo':>10} {'cum profit':>11} {'net worth':>11}")
        for r in sample:
            out.append(
                f"  {r.month:>3} {r.visitors:>9,.0f} {r.active:>7,.0f} "
                f"{r.mrr:>9,.0f} {r.profit:>10,.0f} {r.cum_profit:>11,.0f} "
                f"{r.net_worth:>11,.0f}")

    milestones = [
        ("Profit covers its own costs", "profit", 0.0),
        ("MRR £1,000 (real side income)", "mrr", 1_000),
        ("MRR £5,000 (quit-the-job territory)", "mrr", 5_000),
        ("MRR £10,000", "mrr", 10_000),
        ("Net worth £250,000", "net_worth", 250_000),
        ("Net worth £1,000,000", "net_worth", 1_000_000),
    ]
    bullet = "- " if md else "  * "
    out.append("**Milestones**\n" if md else "  milestones:")
    for label, attr, threshold in milestones:
        out.append(f"{bullet}{label}: {_fmt_month(first_month(rows, attr, threshold))}")
    out.append("")
    return "\n".join(out)


def assumptions_block(md: bool = False) -> str:
    lines = [
        f"Pricing: £{PRICE_MONTHLY:.0f}/mo or £{PRICE_ANNUAL:.0f}/yr "
        f"({ANNUAL_MIX:.0%} choose annual) -> blended ARPU £{ARPU:.2f}/mo "
        f"before {PAYMENT_FEES:.0%} payment fees.",
        f"Costs: £{FIXED_MONTHLY:.0f}/mo fixed + £{VARIABLE_PER_SUB:.2f}"
        f"/subscriber/mo. Owner salary excluded — profit is the owner's pay.",
        f"Business valuation: {VALUATION_MULTIPLE:.0f}x ARR (small "
        f"owner-operated SaaS trades at roughly 2-4x).",
        f"Horizon: {HORIZON_MONTHS} months. All figures GBP.",
    ]
    bullet = "- " if md else "* "
    return "\n".join(bullet + l for l in lines)


def render(md: bool = False) -> str:
    parts: List[str] = []
    if md:
        parts.append("# Archie Pro — financial projections\n")
        parts.append("> Generated by `python business/model.py --md`. "
                     "Do not edit by hand — change the assumptions in "
                     "`business/model.py` and regenerate.\n")
        parts.append("## Assumptions\n")
        parts.append(assumptions_block(md=True) + "\n")
        parts.append("## Scenarios\n")
    else:
        parts.append("Archie Pro — financial projections")
        parts.append(assumptions_block())
        parts.append("")
    for sc in SCENARIOS:
        parts.append(scenario_report(sc, md=md))
    closing = (
        "The single highest-leverage variable is churn: at 6%/mo the average "
        "subscriber stays ~17 months; at 4%/mo, 25 months. Retention work "
        "(the daily `manage` habit, the journal, the weekly email) is worth "
        "more than any acquisition hack. The conservative scenario never "
        "reaches £1M — which is exactly why the plan includes explicit "
        "review gates (see PLAN.md §9) instead of blind persistence."
    )
    parts.append(("## Reading the numbers\n\n" + closing + "\n") if md
                 else "reading the numbers:\n" + closing)
    return "\n".join(parts)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--md", action="store_true",
                        help="write business/FINANCIALS.md instead of stdout")
    args = parser.parse_args(argv)
    if args.md:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "FINANCIALS.md")
        with open(path, "w") as handle:
            handle.write(render(md=True))
        print(f"wrote {path}")
    else:
        print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
