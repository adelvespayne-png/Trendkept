---
name: incident-postmortem
description: Write blameless incident post-mortem/retrospective documents: timeline, impact, root cause, and action items. Use whenever the user wants to document an outage, bug, or operational incident after the fact.
---

# Incident Postmortem

## Workflow
1. Gather: what happened, detection time, resolution time, user/business impact, and the sequence of events.
2. Structure: Summary -> Impact (quantified where possible) -> Timeline (timestamped) -> Root cause (the actual mechanism, not just "human error") -> Contributing factors -> Action items (owner + due date each) -> What went well.
3. Keep it blameless: focus on system/process failures that allowed the issue, not individual blame - this is core to the format's purpose and shouldn't be diluted even if the user vents about a specific person.
4. Action items should be specific and assignable, not vague ("improve monitoring" -> "add alert for X metric exceeding Y, owner: Z, due: date").
