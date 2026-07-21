---
name: web-artifacts
description: Build production-quality HTML artifacts styled with shadcn/ui design tokens (via Tailwind CDN). Use whenever the user asks for a landing page, dashboard mockup, or any standalone HTML UI, even if they don't say 'shadcn'.
---

# Web Artifacts

## Workflow
1. Clarify: what's the page for, and any brand colors/fonts if given.
2. Build a single self-contained .html file: Tailwind via CDN + shadcn-style component classes (cards, buttons, inputs) hand-rolled in CSS since no compiler is available.
3. Use a real visual point of view: pick one accent color, consistent spacing scale (4/8/12/16/24/32px), and a clear type hierarchy. Avoid generic centered-hero-with-3-cards templates.
4. Add subtle interaction (hover states, transitions) with plain JS/CSS - no external framework needed.
5. Save to /mnt/user-data/outputs and present it as an artifact.

## Checklist before delivering
- [ ] No lorem ipsum - write real, specific copy
- [ ] Responsive at mobile width
- [ ] One dominant accent color, not five
