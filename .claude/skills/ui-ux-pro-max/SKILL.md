---
name: ui-ux-pro-max
description: Produce a complete design system specification (color scales, type scale, spacing scale, component states, accessibility notes) for a product or brand. Use whenever the user asks for a 'design system', 'style guide', or wants consistency rules across many screens.
---

# Ui Ux Pro Max

## Workflow
1. Gather brand inputs: any existing colors/fonts/logo, target platform (web/mobile), and tone (playful, enterprise, minimal, etc).
2. Define:
   - Color scale: primary/secondary/neutral, each with 5-9 shades, plus semantic colors (success/warning/error/info)
   - Type scale: font family choices + a modular scale (e.g. 12/14/16/20/24/32/40/48px)
   - Spacing scale: 4px or 8px base unit, named tokens
   - Component states: default/hover/active/disabled/focus for buttons, inputs, cards
   - Accessibility: contrast ratios (WCAG AA minimum), focus-visible outlines
3. Present as a Markdown reference doc AND, if useful, a living HTML style-guide artifact showing swatches/components rendered.
4. Flag any contrast failures found in the given brand colors rather than silently fixing them.
