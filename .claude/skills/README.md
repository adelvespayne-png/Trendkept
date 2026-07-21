# Skill Pack — 33 custom skills

## Install (one-liner)
Unzip this into your global Claude Code skills folder:

```bash
mkdir -p ~/.claude/skills
unzip skill-pack.zip -d ~/.claude/skills/
```

Then start (or restart) a Claude Code session. That's it — Claude will pull in
whichever skill's description matches what you ask for. You can also invoke
one by name, e.g. "use the contract-review skill on this PDF."

Only want it for one project instead of all of them? Put it in `.claude/skills/`
inside that repo instead of `~/.claude/skills/`.

## What's in here
33 hand-written SKILL.md files across 6 departments:
- Design: web-artifacts, canvas-design, algorithmic-art, ui-ux-pro-max, slack-gif
- Marketing: seo-audit, programmatic-seo, ai-seo, cro, ad-creative, mktg-psychology
- Social & Content: social, copywriting, content-strategy, video, pillar-content, email-sequences
- Finance: dcf-model, 3-statements, lbo-model, comps-analysis, pricing, pitch-deck
- Operations: sop-builder, incident-postmortem, business-case, launch-runbook, internal-comms
- Legal: contract-review, nda-triage, legal-risk, compliance, sql-queries

These are first-draft skills — they'll work out of the box but are worth
iterating on with real tasks (the skill-creator skill, if you have it, can
help you test and refine descriptions/instructions).

## The other 9 from the original list — not included here
These weren't fabricated because they're either already built into your
Claude Code setup or are specific third-party tools you'd install separately,
not something safe to reconstruct from a screenshot:

| Name | Why it's not here |
|---|---|
| docx | Already an official Anthropic skill — install via `git clone https://github.com/anthropics/skills ~/.claude/skills/official` |
| xlsx | Same — comes from the official repo above |
| frontend-design | Same — official repo above |
| Webapp Testing | Same — official repo above (browser-based QA skill) |
| Skill Creator | Same — official repo above |
| Superpowers | Real third-party project — search "Superpowers Claude Code skill" on GitHub for the actual repo |
| Context7 | This is an MCP server, not a skill folder — install as an MCP connector, not via `~/.claude/skills/` |
| MCP Builder | Real third-party project — search GitHub for it directly rather than trust a re-creation |
| Claude-Mem | Real third-party project — search GitHub for it directly |

For those, cloning the official repo gets you 4 of the 9 immediately:
```bash
git clone https://github.com/anthropics/skills ~/.claude/skills/official
```
