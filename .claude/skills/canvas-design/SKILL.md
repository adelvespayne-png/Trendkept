---
name: canvas-design
description: Generate visual designs (posters, social graphics, certificates, cards) rendered to a PNG or PDF file using HTML5 Canvas or SVG. Use whenever the user wants a downloadable graphic/image asset rather than a webpage.
---

# Canvas Design

## Workflow
1. Clarify dimensions/aspect ratio and intended use (Instagram post, poster, certificate, etc).
2. Build the design as SVG (preferred, crisp at any size) or an HTML5 canvas script.
3. Render to PNG using a headless tool (e.g. rsvg-convert, puppeteer, or cairosvg - check what's installed, install via pip/npm with --break-system-packages if missing).
4. For PDF output, render the SVG to PDF directly (cairosvg supports both).
5. Save final file(s) to /mnt/user-data/outputs and present.

## Design notes
- Establish a clear focal point and generous margins - avoid cramming.
- Pick 2 fonts max (one display, one body) and 1 accent color.
