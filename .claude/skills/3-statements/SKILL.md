---
name: 3-statements
description: Build an integrated 3-statement financial model (income statement, balance sheet, cash flow statement) that links together - net income flows to retained earnings, cash flow ties to the balance sheet cash balance, etc. Use whenever the user wants a full financial model rather than a single statement.
---

# 3 Statements

## Workflow
1. Gather historicals (at least 1-3 years) and key drivers/assumptions (revenue growth, margins, capex, working capital days, debt schedule).
2. Build income statement first (revenue -> net income), then balance sheet (linking retained earnings to net income, debt schedule to interest expense), then cash flow statement (deriving from IS + BS changes) as the reconciling statement.
3. Critical check: the model must actually balance (Assets = Liabilities + Equity) every period - build a balance-check row and don't consider it done until it nets to zero.
4. Build in a spreadsheet with live formulas (see xlsx skill), assumptions on a separate tab from outputs.
5. Flag circularity risk (interest expense depends on debt balance, which depends on cash flow, which depends on interest expense) and use a standard fix (copy-paste values or an iterative-calc toggle) rather than ignoring it.
