# Content & distribution

Getting Trendkept found: the website, free tools, newsletter, and the
content pipeline — all honesty-gated.

## Where the truth lives
- Site: `site/` (served by the Cloudflare Worker, tracks `main`);
  `wrangler.jsonc`
- Free calculator pages: `site/tools/` (position-size, risk-per-trade,
  r-multiple, stop-loss)
- Plans: `business/CONTENT_STRATEGY.md`, `business/CRO_AUDIT.md`
- Ready-to-post drafts: `business/launch/` (essays, welcome email,
  newsletter template + generator)
- Newsletter: Buttondown "The Trend Check", sending domain
  news.trendkept.com; Sunday auto-draft Action:
  `.github/workflows/trend-check-draft.yml`

## Current status (Aug 2026)
- Shipped: 4 no-signup calculator pages with OG + JSON-LD, cross-linked;
  homepage free-tools section; branded OG image; robots/sitemap/llm.txt;
  inline hero email capture with double-opt-in microcopy.
- Drafts ready (compliance-safe, gate-respecting): moving-stops essay,
  lookahead-bias essay, welcome email.
- Third website critique adopted: backtest-as-report framing, "most days
  = do nothing" line, single primary CTA, audience-honesty line, lock
  badge by CTAs.

## Standing orders
- Nothing publishes without the owner pressing send.
- Every claim literally true on posting day; no invented trading history.
- Newsletter/site copy descriptive, never imperative.
- Results-flavoured posts gated on the paper log (4+ weeks real entries).

## Next moves
- More cluster content from CONTENT_STRATEGY.md.
- Third-party proof section deferred until real users exist.
- Brand/visual differentiation pass noted, not urgent.
