---
name: seo-audit
description: Audit a webpage or site's on-page SEO - title tags, meta descriptions, heading structure, internal linking, image alt text, page speed signals, and keyword targeting. Use whenever the user pastes a URL or content and asks about SEO, rankings, or 'why isn't this page ranking'.
---

# Seo Audit

## Workflow
1. Fetch the page (web_fetch) if a URL is given; otherwise use the pasted content.
2. Check systematically:
   - Title tag: length (50-60 chars), primary keyword placement, uniqueness
   - Meta description: 140-160 chars, includes a call to action
   - Heading structure: single H1, logical H2/H3 nesting
   - Keyword usage: primary term in title/H1/first 100 words, without stuffing
   - Internal links: anchor text relevance, orphaned-page risk
   - Images: alt text present and descriptive
   - Technical basics if visible: canonical tag, indexability, mobile viewport
3. Report as a prioritized fix list (highest-impact first), not just an inventory.
4. Don't invent ranking positions or traffic numbers you can't verify - search live if the user wants current SERP data.
