---
name: dcf-model
description: Build a discounted cash flow (DCF) valuation model estimating intrinsic value from projected free cash flows, discount rate (WACC), and terminal value. Use whenever the user wants a DCF, intrinsic valuation, or 'what is this company worth' analysis, ideally as a spreadsheet (see xlsx skill for spreadsheet mechanics).
---

# Dcf Model

## Workflow
1. Gather inputs: historical revenue/margins, growth assumptions, WACC (or its components: cost of equity via CAPM, cost of debt, capital structure), terminal growth rate or exit multiple.
2. Project unlevered free cash flow for 5-10 years: Revenue -> EBIT -> less taxes -> plus D&A -> less capex -> less change in NWC.
3. Discount each year's FCF and the terminal value back to present value at WACC.
4. Sum for enterprise value; bridge to equity value (less debt, plus cash) and per-share value if applicable.
5. Build as a live-formula spreadsheet (defer to the xlsx skill for spreadsheet construction mechanics) with assumptions clearly separated from calculations so the user can flex inputs.
6. Always show a sensitivity table (WACC x terminal growth) - single-point DCF outputs are misleadingly precise.
7. This is not financial advice; present it as a modeling exercise and note the sensitivity of DCF outputs to assumptions.
