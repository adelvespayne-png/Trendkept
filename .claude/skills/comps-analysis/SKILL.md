---
name: comps-analysis
description: Build a comparable companies (comps) valuation analysis - identifying peer companies and comparing valuation multiples (EV/EBITDA, EV/Revenue, P/E). Use whenever the user wants relative valuation or a comps table.
---

# Comps Analysis

## Workflow
1. Identify the target company and criteria for peer selection (industry, size, growth profile, geography).
2. For real current financial data (market caps, EBITDA, multiples), search the web rather than relying on memory - this data goes stale fast.
3. Build the comps table: company | market cap | EV | revenue | EBITDA | EV/Revenue | EV/EBITDA | P/E, with the target highlighted.
4. Calculate median/mean multiples and apply to the target's metrics to derive an implied valuation range.
5. Note outliers and why they might be excluded (different growth stage, one-off items) rather than silently averaging everything.
