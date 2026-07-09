"""Trendkept Pro financial model — honest edition.

    python business/model.py                # print all scenarios
    python business/model.py --md           # regenerate business/FINANCIALS.md

Same philosophy as the trading rules: write the assumptions down, run the
numbers mechanically, and never let a wish masquerade as a forecast. This
version exists because the first draft failed its own standard in six ways,
all fixed here:

1. **Revenue starts month 3**, when payments actually ship (roadmap) — not
   month 1. Months 1-2 are pre-revenue audience building; costs still run.
2. **Real payment fees**: Paddle-style 5% + £0.50 per transaction is ~9% on
   a £12 monthly charge and ~5.5% on a £99 annual — not a flat 4%.
3. **Costs step with scale**: newsletter tiers, a licensed market-data feed
   (required before charging — see LEGAL.md), insurance, accounting, and the
   AI tooling the operation actually depends on. Not a flat £200.
4. **Churn is honest**: hobbyist-trader B2C commonly churns 8-15%/month
   (people churn out of trading itself). Conservative here is 10%, base 7%.
5. **Traffic spikes and decays**: launches produce spikes that lose ~55% of
   their traffic each following month, on top of a slower organic base.
   Nothing grows smoothly forever.
6. **Launch offers are modelled**: lifetime deals (one-off cash, zero MRR,
   ongoing cost) and discounted founding-cohort annuals dilute ARPU exactly
   as they will in life. Valuation uses a profit (SDE) multiple — small
   owner-run SaaS sells on profit, not ARR.

"Net worth" = cumulative kept profit + what the business would sell for
(3x trailing-12-month profit, excluding one-off lifetime revenue; the real
range is ~2.5-4x). The model reports the month each milestone is crossed —
or says plainly that it never is.

The conservative scenario remains the most likely outcome. If these numbers
still clear break-even by months 6-8, the plan is robust; where they say a
milestone slipped versus the old draft, believe this version.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- pricing & fees ----------------------------------------------------------
PRICE_MONTHLY = 12.0        # GBP / month
PRICE_ANNUAL = 99.0         # GBP / year
ANNUAL_MIX = 0.40           # fraction of recurring subscribers on annual
FEE_PCT = 0.05              # merchant-of-record % (Paddle-style)
FEE_FIXED = 0.50            # per-transaction fixed fee, GBP

_NET_MONTHLY = PRICE_MONTHLY - (PRICE_MONTHLY * FEE_PCT + FEE_FIXED)   # 10.90
_NET_ANNUAL_PM = (PRICE_ANNUAL - (PRICE_ANNUAL * FEE_PCT + FEE_FIXED)) / 12.0
ARPU_NET = (1 - ANNUAL_MIX) * _NET_MONTHLY + ANNUAL_MIX * _NET_ANNUAL_PM

FOUNDING_PRICE = 79.0       # £/yr locked forever, months 3-4 cohort only
FOUNDING_NET_PM = (FOUNDING_PRICE - (FOUNDING_PRICE * FEE_PCT + FEE_FIXED)) / 12
LIFETIME_PRICE = 299.0      # one-off; capped at 200 sold, month 3 only
LIFETIME_NET = LIFETIME_PRICE - (LIFETIME_PRICE * FEE_PCT + FEE_FIXED)
LIFETIME_CHURN = 0.02       # lifetime users still stop using the product

REVENUE_START_MONTH = 3     # payments ship with the month-3 Pro launch

# --- costs (solo owner; salary excluded — profit IS the owner's pay) ---------
BASE_FIXED = 180.0          # hosting, email, domain, registered office,
                            # accounting (~£80/mo of it), misc
AI_TOOLING = 80.0           # the AI subscription the operation runs on —
                            # a real dependency, so a real cost line
DATA_FEED = 60.0            # licensed EOD market data, from revenue start —
                            # scraped Stooq/Yahoo is not licensed for a
                            # commercial product (LEGAL.md §5)
INSURANCE = 25.0            # professional indemnity + cyber, from revenue
VARIABLE_PER_SUB = 0.10     # support tooling, egress, per-user cruft

# Newsletter platform tiers by list size (GBP/mo, Buttondown-shaped).
NEWSLETTER_TIERS = [(100, 0.0), (1_000, 8.0), (5_000, 25.0),
                    (10_000, 70.0), (20_000, 120.0)]
NEWSLETTER_TIER_MAX = 200.0

NEWS_JOIN_RATE = 0.025      # visitors who join the newsletter
NEWS_CHURN = 0.02           # monthly list churn
WAITLIST_CONV = 0.04        # newsletter list converting to paid at launch

SPIKE_RETAIN = 0.45         # a launch spike keeps 45% of its traffic each
                            # following month (spike-and-decay, not a plateau)

VALUATION_MULTIPLE = 3.0    # x trailing-12-month profit (SDE); range 2.5-4x
HORIZON_MONTHS = 60


@dataclass(frozen=True)
class Scenario:
    name: str
    story: str
    organic_start: float        # monthly organic visitors at launch
    organic_growth: float       # m/m growth of the organic base
    organic_cap: float          # organic plateau for this level of effort
    spikes: Dict[int, float]    # month -> initial spike visitors
    conversion: float           # visitor -> paying subscriber (post-launch)
    churn: float                # monthly subscriber churn
    lifetime_sold: int          # lifetime deals sold at launch (cap 200)


SCENARIOS = [
    Scenario(
        name="Conservative",
        story=("Content gets modest traction; you keep the day job. This is "
               "the most likely outcome and the one to budget your life "
               "around."),
        organic_start=800, organic_growth=0.06, organic_cap=12_000,
        spikes={1: 5_000, 3: 3_000, 12: 2_500, 24: 2_000, 36: 2_000,
                48: 2_000},
        conversion=0.005, churn=0.10, lifetime_sold=20,
    ),
    Scenario(
        name="Base",
        story=("The plan works: launches land, weekly content compounds, and "
               "churn stays merely bad (7%/mo) instead of typical (10%+), "
               "because the journal and daily habit genuinely hold people."),
        organic_start=1_500, organic_growth=0.09, organic_cap=25_000,
        spikes={1: 12_000, 3: 8_000, 12: 6_000, 24: 6_000, 36: 6_000,
                48: 6_000},
        conversion=0.007, churn=0.07, lifetime_sold=60,
    ),
    Scenario(
        name="Ambitious",
        story=("A breakout: front page of HN and Product Hunt, a big collab, "
               "word of mouth, retention near best-in-class. Plan for it, "
               "don't count on it."),
        organic_start=2_500, organic_growth=0.12, organic_cap=60_000,
        spikes={1: 30_000, 3: 20_000, 12: 15_000, 24: 15_000, 36: 15_000},
        conversion=0.010, churn=0.05, lifetime_sold=150,
    ),
]


@dataclass
class MonthRow:
    month: int
    visitors: float
    newsletter: float
    new_subs: float
    active: float               # recurring + founding + lifetime users
    mrr: float                  # net of payment fees; excludes one-offs
    profit: float
    cum_profit: float
    valuation: float            # 3x trailing-12mo profit (ex one-offs)
    net_worth: float
    profits_trailing: List[float] = field(default_factory=list, repr=False)


def _newsletter_cost(list_size: float) -> float:
    for cap, cost in NEWSLETTER_TIERS:
        if list_size < cap:
            return cost
    return NEWSLETTER_TIER_MAX


def simulate(sc: Scenario, months: int = HORIZON_MONTHS) -> List[MonthRow]:
    rows: List[MonthRow] = []
    regular = founding = lifetime = 0.0
    newsletter = 0.0
    organic = sc.organic_start
    cum_profit = 0.0
    trailing: List[float] = []

    for m in range(1, months + 1):
        spike_traffic = sum(
            initial * (SPIKE_RETAIN ** (m - s))
            for s, initial in sc.spikes.items() if m >= s
        )
        visitors = organic + spike_traffic

        newsletter += visitors * NEWS_JOIN_RATE - newsletter * NEWS_CHURN

        one_off = 0.0
        new = 0.0
        if m >= REVENUE_START_MONTH:
            new = visitors * sc.conversion
            if m == REVENUE_START_MONTH:
                # Launch: the pre-built waitlist converts, and the capped
                # lifetime deal sells (one-off cash, no MRR ever).
                new += newsletter * WAITLIST_CONV
                lifetime = float(min(sc.lifetime_sold, 200))
                one_off = lifetime * LIFETIME_NET
            if m in (REVENUE_START_MONTH, REVENUE_START_MONTH + 1):
                founding += new          # discounted cohort, locked forever
            else:
                regular += new
        regular -= regular * sc.churn
        founding -= founding * sc.churn
        lifetime -= lifetime * LIFETIME_CHURN

        active = regular + founding + lifetime
        mrr = regular * ARPU_NET + founding * FOUNDING_NET_PM

        costs = BASE_FIXED + AI_TOOLING + _newsletter_cost(newsletter) \
            + active * VARIABLE_PER_SUB
        if m >= REVENUE_START_MONTH:
            costs += DATA_FEED + INSURANCE

        profit = mrr + one_off - costs
        cum_profit += profit

        # Valuation on trailing 12-month *recurring* profit (SDE multiple);
        # one-off lifetime cash is excluded — a buyer would exclude it too.
        trailing.append(mrr - costs)
        window = trailing[-12:]
        annual_profit = sum(window) * (12 / len(window))
        valuation = max(0.0, annual_profit) * VALUATION_MULTIPLE

        rows.append(MonthRow(
            month=m, visitors=visitors, newsletter=newsletter, new_subs=new,
            active=active, mrr=mrr, profit=profit, cum_profit=cum_profit,
            valuation=valuation, net_worth=cum_profit + valuation,
        ))
        organic = min(organic * (1 + sc.organic_growth), sc.organic_cap)
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
    years, _ = divmod(m - 1, 12)
    return f"month {m} (~year {years + 1})"


def scenario_report(sc: Scenario, md: bool = False) -> str:
    rows = simulate(sc)
    sample = [r for r in rows if r.month % 6 == 0 or r.month in (1, 3)]

    out: List[str] = []
    if md:
        out.append(f"### {sc.name}\n")
        out.append(f"*{sc.story}*\n")
        out.append("| Month | Visitors | List | Active | MRR (net) | "
                   "Profit /mo | Cum. profit | Valuation (3x SDE) | "
                   "Net worth |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for r in sample:
            out.append(
                f"| {r.month} | {r.visitors:,.0f} | {r.newsletter:,.0f} | "
                f"{r.active:,.0f} | £{r.mrr:,.0f} | £{r.profit:,.0f} | "
                f"£{r.cum_profit:,.0f} | £{r.valuation:,.0f} | "
                f"£{r.net_worth:,.0f} |")
        out.append("")
    else:
        out.append(f"== {sc.name} ==")
        out.append(sc.story)
        out.append(f"  {'mo':>3} {'visitors':>9} {'list':>7} {'subs':>7} "
                   f"{'MRR':>8} {'profit':>8} {'cum':>10} {'worth':>10}")
        for r in sample:
            out.append(
                f"  {r.month:>3} {r.visitors:>9,.0f} {r.newsletter:>7,.0f} "
                f"{r.active:>7,.0f} {r.mrr:>8,.0f} {r.profit:>8,.0f} "
                f"{r.cum_profit:>10,.0f} {r.net_worth:>10,.0f}")

    milestones = [
        ("Monthly profit turns positive", "profit", 0.01),
        ("MRR £1,000 (real side income)", "mrr", 1_000),
        ("MRR £2,000 (the month-12 gate line)", "mrr", 2_000),
        ("MRR £5,000 (quit-the-job territory)", "mrr", 5_000),
        ("MRR £10,000", "mrr", 10_000),
        ("Net worth £250,000", "net_worth", 250_000),
        ("Net worth £1,000,000", "net_worth", 1_000_000),
    ]
    bullet = "- " if md else "  * "
    out.append("**Milestones**\n" if md else "  milestones:")
    for label, attr, threshold in milestones:
        out.append(f"{bullet}{label}: "
                   f"{_fmt_month(first_month(rows, attr, threshold))}")
    out.append("")
    return "\n".join(out)


def assumptions_block(md: bool = False) -> str:
    lines = [
        f"Pricing: £{PRICE_MONTHLY:.0f}/mo or £{PRICE_ANNUAL:.0f}/yr "
        f"({ANNUAL_MIX:.0%} annual). Fees {FEE_PCT:.0%} + "
        f"£{FEE_FIXED:.2f}/transaction -> net ARPU £{ARPU_NET:.2f}/mo "
        f"(~{1 - ARPU_NET / ((1-ANNUAL_MIX)*PRICE_MONTHLY + ANNUAL_MIX*PRICE_ANNUAL/12):.0%} "
        "effective fee).",
        f"Revenue starts month {REVENUE_START_MONTH} (when payments ship). "
        "Months 1-2 are pre-revenue: costs run, the newsletter builds, "
        "nothing is for sale yet.",
        f"Launch offers modelled: founding cohort at £{FOUNDING_PRICE:.0f}/yr "
        f"(months {REVENUE_START_MONTH}-{REVENUE_START_MONTH + 1} signups, "
        f"net £{FOUNDING_NET_PM:.2f}/mo forever); lifetime £"
        f"{LIFETIME_PRICE:.0f} one-off (no MRR, still costs to serve).",
        f"Costs step with scale: £{BASE_FIXED + AI_TOOLING:.0f}/mo baseline "
        f"(incl. £{AI_TOOLING:.0f} AI tooling), + licensed data feed "
        f"£{DATA_FEED:.0f} and insurance £{INSURANCE:.0f} from revenue "
        "start, + newsletter platform tiers, + £"
        f"{VARIABLE_PER_SUB:.2f}/user/mo.",
        "Traffic = organic base (grows to a cap) + launch spikes that decay "
        f"{1 - SPIKE_RETAIN:.0%} per month. Churn: 10%/7%/5% by scenario — "
        "hobbyist-trader B2C reality, not SaaS-blog folklore.",
        f"Valuation: {VALUATION_MULTIPLE:.0f}x trailing-12-month profit "
        "(SDE; small owner-run SaaS trades ~2.5-4x profit, not ARR), "
        "excluding one-off lifetime revenue.",
        f"Horizon: {HORIZON_MONTHS} months. All figures GBP. Owner salary "
        "excluded — profit is the owner's pay.",
    ]
    bullet = "- " if md else "* "
    return "\n".join(bullet + l for l in lines)


def render(md: bool = False) -> str:
    parts: List[str] = []
    if md:
        parts.append("# Trendkept Pro — financial projections\n")
        parts.append("> Generated by `python business/model.py --md`. "
                     "Do not edit by hand — change the assumptions in "
                     "`business/model.py` and regenerate.\n")
        parts.append("## Assumptions\n")
        parts.append(assumptions_block(md=True) + "\n")
        parts.append("## Scenarios\n")
    else:
        parts.append("Trendkept Pro — financial projections (honest edition)")
        parts.append(assumptions_block())
        parts.append("")
    for sc in SCENARIOS:
        parts.append(scenario_report(sc, md=md))
    closing = (
        "Churn remains the highest-leverage variable: at 10%/mo the average "
        "subscriber stays 10 months; at 7%, 14 months. Retention work (the "
        "journal, the daily habit, the weekly email) beats any acquisition "
        "hack. Traffic spikes decay — the organic base and the newsletter "
        "are what compound. The conservative scenario never reaches £1M and "
        "sits under the £2k-MRR gate line at month 12: that is exactly the "
        "situation the trajectory gates in PLAN.md §9 exist to adjudicate — "
        "deliberately continue in side-asset mode, or exit. Neither is "
        "failure; drifting without deciding is."
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
