---
name: slack-gif
description: Create small looping animated GIFs sized for Slack custom emoji/reactions (128x128 max) or Slack message attachments. Use whenever the user wants a reaction GIF, animated emoji, or celebratory loop for Slack/Discord.
---

# Slack Gif

## Workflow
1. Clarify: emoji-sized (128x128, transparent bg) vs a larger in-message GIF, and the concept/emotion.
2. Build frames with a canvas/SVG loop script (Python + Pillow, or an HTML canvas capture), keep it simple (looping in 8-20 frames).
3. Export as an optimized animated GIF (use gifsicle -O3 or Pillow's save with save_all=True) - keep file size under Slack's emoji limit (128KB for custom emoji).
4. Preview frame count/loop before finalizing; save to /mnt/user-data/outputs.

## Constraints
- Custom Slack emoji: square, <=128x128px, <=128KB, transparent background preferred.
