# Trendkept landing page — CRO audit

Built with the `cro` skill. Goal: **more email signups** (the single
primary conversion). Baseline: pre-launch, ~1 activated subscriber, no
traffic yet — so these are set-up-right-before-traffic fixes, not
post-hoc A/B reads. No dark patterns used or recommended (no fake
urgency, no hidden costs, no forced continuity).

## Fundamentals audit

| Area | Verdict |
|---|---|
| Value prop above the fold | **Strong** — "Trade the trend. Follow the rules." + the anti-prediction kicker + one-line pain framing |
| Form friction | **Low** — single email field, one button |
| Trust signals | **Partial** — lock badge, open-source/runs-locally badges, built-in-public timeline, honest FAQ. Missing: real social proof (none exists yet — can't fake it) |
| CTA clarity | **Good** — consolidated to one primary (weekly email); GitHub demoted |
| Mobile | **Good** — responsive; hero stacks, form wraps |

## Ranked changes (hypotheses, impact × effort)

1. **[DONE] Inline email capture in the hero.** *If we let visitors type
   their email above the fold instead of clicking a button that scrolls to
   a form, then signups rise, because every extra step loses people.*
   Impact: High · Effort: Low. **Shipped.**
2. **[DONE] Set the double-opt-in expectation at the point of signup.**
   *If we tell people a confirmation email is coming and to click it, then
   the activated-subscriber rate rises, because people who don't expect it
   never confirm.* Evidence: two of the owner's own three signups sat
   **"unactivated"** — this is a real, measured leak, not a guess.
   Impact: High · Effort: Low. **Shipped** (hero + signup-section
   microcopy).
3. **[LATER — needs numbers] Add real social proof once it exists.** *If
   we show a live subscriber count / "the rules have traded in public for
   N days" once N is respectable, then trust and signups rise.* We refuse
   to fabricate it; revisit at ~50 subscribers and once the log has weeks
   on it. Impact: High · Effort: Low (when the number is real).
4. **[TEST] Pain-first headline variant.** *If the H1 leads with the
   visitor's problem — "You don't need better predictions. You need to
   follow your own rules." — vs the brand line, then engagement rises,
   because problem-first outperforms brand-first for cold traffic.*
   Impact: Medium · Effort: Low. Hold as an A/B once there's traffic.
5. **[TEST] Surface the founding price near signup.** *If we mention the
   genuine founding offer (£79/yr locked forever) beside the email
   capture, then signups rise via honest scarcity — it's a real, limited
   cohort, not a fake timer.* Impact: Medium · Effort: Low. Only truthful
   scarcity; never a countdown.

## Explicitly rejected (dark patterns)

Fake "X people viewing", countdown timers, pre-ticked consent, hard-to-
find unsubscribe, hidden pricing. All off-limits — they'd also breach the
honesty rule the whole brand rests on, and (for a UK financial-adjacent
product) invite exactly the regulatory attention we avoid.

## Next, once traffic is flowing

Wire basic analytics (privacy-respecting, e.g. Cloudflare Web Analytics —
no cookie banner needed) so #4 and #5 can be tested with real numbers
instead of opinions. That's the difference between CRO and decorating.
