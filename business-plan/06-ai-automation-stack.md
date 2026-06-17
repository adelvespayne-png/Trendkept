# 06 — The AI Automation Stack

> AI is the **leverage** that lets a 1–2 person team run a real brand: it
> collapses the cost of content, support, and ops. But in a regulated,
> health-adjacent business there is a bright line:
>
> **AI drafts and assists. A human approves anything customer-facing,
> health-related, or financial.** AI does not write your medical claims, does
> not decide refunds unsupervised, and does not get pointed at customers
> without a human in the loop.

## 6.1 Where AI genuinely saves money (use it here)

| Area | What AI does | Human role |
|---|---|---|
| **Content production** | Draft SEO articles, video scripts, captions, product descriptions, email/SMS flows | Edit, fact-check, run claims checklist, approve |
| **Customer support tier 1** | Draft replies to FAQs (shipping, how-to-use, subscription management) | Approve/escalate; handle anything health or complaint-related |
| **Lifecycle marketing** | Generate + personalise onboarding, refill, win-back sequences | Approve templates; AI personalises within approved bounds |
| **Ops & analytics** | Summarise sales/CAC/churn data, draft supplier emails, reconcile reports | Decisions on spend, inventory, suppliers |
| **Creative testing** | Generate ad/copy variants to A/B test | Compliance-check every variant before it runs |
| **Review/social monitoring** | Triage and summarise sentiment, flag adverse-event mentions | **Adverse events escalate to human immediately** (reporting duty, file 02) |

## 6.2 Where AI must NOT operate unsupervised (the bright line)

- **Health claims / medical advice.** No AI-written copy goes live without the
  claims checklist and human sign-off. No chatbot dispensing health guidance.
- **Adverse-event handling.** Any "this made me ill" message is escalated to a
  human and logged — you may have a legal reporting duty.
- **Refund/chargeback decisions** beyond a small pre-approved auto-refund policy.
- **Final compliance sign-off** on labels, claims, and legal docs.

## 6.3 The automated **claims-compliance gate** (the most valuable automation)

This is the highest-leverage AI use in the whole plan: a gate that screens
every draft for prohibited language **before** a human review, so the human
reviews faster and nothing illegal slips through.

A simple version is a keyword/intent screen plus an LLM check. Pseudocode:

```
PROHIBITED = ["cure", "treat", "prevent", "diagnose", "disease",
              "anxiety", "depression", "insomnia", "blood pressure",
              "diabetes", "cancer", "covid", "virus", "FDA approved",
              "clinically proven to cure", ...]

def screen(copy):
    flags = [w for w in PROHIBITED if w in copy.lower()]
    llm_verdict = llm_check(
        "Does this supplement copy make a disease/drug claim "
        "(treat/cure/prevent/diagnose) or imply it replaces medication? "
        "Answer FAIL with reasons, or PASS.", copy)
    require_fda_disclaimer = makes_structure_function_claim(copy)
    return {"keyword_flags": flags,
            "llm_verdict": llm_verdict,
            "needs_disclaimer": require_fda_disclaimer}
    # ANY flag or FAIL  ->  human must fix before publish. Always human sign-off.
```

> The gate **never auto-approves**. PASS just means "ready for human review."
> It catches the obvious violations cheaply so humans focus on judgement calls.

## 6.4 The tooling layer (off-the-shelf, no heavy build at launch)

You do **not** need a custom platform to start. Compose existing tools:

- **Store / subscriptions:** Shopify (+ a subscription app) or similar. Handles
  checkout, subscriptions, payments, fulfillment routing.
- **Fulfillment:** your white-label supplier's blind-ship integration / 3PL.
- **Email/SMS:** Klaviyo (or similar) for lifecycle automation.
- **Support:** a helpdesk with AI-draft replies (human-approved).
- **AI:** an LLM (the **Claude API** is a strong fit for drafting, the claims
  gate, support drafts, and data summaries — latest models: Opus 4.8 / Sonnet
  4.6 / Haiku 4.5 / Fable 5). Use the most capable model for compliance-
  sensitive checks; a cheaper/faster one for high-volume drafting.
- **Analytics:** the store's built-in reports + a simple dashboard; the
  `tools/unit_economics.py` calculator for margin/LTV discipline.
- **Glue:** a no/low-code automation tool (e.g. Zapier/Make) or small scripts to
  connect them.

> Build custom only when a manual/off-the-shelf step becomes a proven
> bottleneck. Early on, your time is better spent on product, suppliers, and the
> first profitable channel than on infrastructure.

## 6.5 Principle

AI is a cost-compressor and a force-multiplier, **not** an autopilot for a
business that can hurt people if done wrong. Keep the human on the safety- and
money-critical decisions; let AI take the repetitive volume.
