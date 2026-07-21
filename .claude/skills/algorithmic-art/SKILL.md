---
name: algorithmic-art
description: Create generative/algorithmic art using p5.js (particle systems, flow fields, noise-based patterns, geometric tilings). Use whenever the user wants procedural/generative visuals, not a static illustration.
---

# Algorithmic Art

## Workflow
1. Identify the visual language: organic (noise, flow fields, particles) vs geometric (tilings, grids, fractals).
2. Build a single HTML file importing p5.js from cdnjs.
3. Use a restrained palette (3-4 colors) and seed randomness so results are reproducible (randomSeed(), noiseSeed()).
4. Add a few exposed parameters (speed, density, palette) at the top of the sketch so the user can tweak easily.
5. Save as an .html artifact.

## Good defaults
- Frame rate capped reasonably (30-60fps) to avoid runaway CPU use.
- Background drawn once or with subtle alpha trails for motion effects, not full clear-and-redraw unless intended.
