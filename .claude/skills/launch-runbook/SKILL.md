---
name: launch-runbook
description: Write a launch/go-live runbook covering pre-launch checks, the cutover sequence (e.g. DNS changes), rollback plan, and post-launch monitoring. Use whenever the user is planning a product launch, migration, or DNS/infra cutover.
---

# Launch Runbook

## Workflow
1. Get the launch type (new product, migration, DNS cutover, infra change) and current architecture details relevant to it.
2. Structure: Pre-launch checklist (what must be verified/ready) -> Go/no-go criteria -> Step-by-step cutover sequence with exact commands/actions and who owns each -> Rollback plan (the trigger condition for rolling back, and exact rollback steps) -> Post-launch monitoring checklist (what to watch, for how long).
3. For DNS specifically: note TTL lowering ahead of time, propagation wait expectations, and verification steps (dig/nslookup checks) before declaring success.
4. Assign an owner and a communication point person for the window, not just a task list.
