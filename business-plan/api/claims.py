"""Claims-compliance gate (see ../06-ai-automation-stack.md).

A dependency-free, deterministic first-pass screen for prohibited
supplement-marketing language. In production this would sit IN FRONT of an LLM
check and, crucially, IN FRONT OF A HUMAN REVIEWER -- it NEVER auto-approves
copy for publication. Its job is to catch the obvious, business-ending disease
claims cheaply so humans focus on judgement calls.

This module has no third-party dependencies and can be imported by the API
server or run standalone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Words/phrases that indicate an illegal disease/drug claim (non-exhaustive).
# A real list would be far longer and reviewed by counsel. These turn a
# "dietary supplement" into an "unapproved drug" in the eyes of the FDA.
PROHIBITED_TERMS: tuple[str, ...] = (
    "cure", "cures", "curing",
    "treat", "treats", "treating", "treatment",
    "prevent", "prevents", "preventing",
    "diagnose", "diagnoses", "diagnosing",
    "disease", "illness",
    "anxiety", "depression", "insomnia",
    "blood pressure", "hypertension",
    "diabetes", "diabetic",
    "cancer", "tumor", "tumour",
    "covid", "coronavirus", "virus", "infection",
    "heart disease", "stroke",
    "fda approved", "fda-approved", "clinically proven to cure",
    "replaces medication", "stop taking", "instead of your medication",
    "miracle", "guaranteed cure",
)

# Phrases that look like compliant US "structure/function" claims. If any are
# present, the copy MUST also carry the FDA disclaimer.
STRUCTURE_FUNCTION_HINTS: tuple[str, ...] = (
    "supports", "support", "helps maintain", "promotes", "helps support",
    "maintains healthy", "for healthy", "helps you", "aids", "contributes to",
)

FDA_DISCLAIMER = (
    "This statement has not been evaluated by the Food and Drug "
    "Administration. This product is not intended to diagnose, treat, cure, "
    "or prevent any disease."
)


@dataclass
class ClaimsResult:
    passed: bool
    prohibited_hits: list[str] = field(default_factory=list)
    makes_structure_function_claim: bool = False
    needs_fda_disclaimer: bool = False
    has_fda_disclaimer: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "prohibited_hits": self.prohibited_hits,
            "makes_structure_function_claim": self.makes_structure_function_claim,
            "needs_fda_disclaimer": self.needs_fda_disclaimer,
            "has_fda_disclaimer": self.has_fda_disclaimer,
            "notes": self.notes,
            "reminder": (
                "PASS means 'ready for human review', NOT 'approved to "
                "publish'. A human must sign off on all customer-facing copy."
            ),
        }


def _contains_word(text: str, term: str) -> bool:
    """Whole-word / phrase match, case-insensitive."""
    pattern = r"\b" + re.escape(term) + r"\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def screen(copy: str) -> ClaimsResult:
    """Screen marketing copy for prohibited disease/drug claims.

    Returns a ClaimsResult. ``passed`` is True only when no prohibited terms are
    found AND, if a structure/function claim is made, the FDA disclaimer is
    present. Even on PASS, a human must review before publishing.
    """
    text = copy or ""
    has_disclaimer = "not intended to diagnose" in text.lower()

    # The FDA disclaimer legally MUST contain the words "diagnose, treat, cure,
    # or prevent any disease". Scanning it for prohibited terms would flag the
    # very text we require, so strip the disclaimer before the prohibited scan.
    scan_text = re.sub(
        re.escape(FDA_DISCLAIMER), " ", text, flags=re.IGNORECASE
    )

    hits = [t for t in PROHIBITED_TERMS if _contains_word(scan_text, t)]
    makes_sf = any(_contains_word(scan_text, h) for h in STRUCTURE_FUNCTION_HINTS)
    needs_disclaimer = makes_sf and not has_disclaimer

    notes: list[str] = []
    if hits:
        notes.append(
            "Contains prohibited disease/drug language. This makes the product "
            "an unapproved drug. Rewrite using structure/function language."
        )
    if needs_disclaimer:
        notes.append(
            "Makes a structure/function claim but is missing the FDA "
            "disclaimer. Add it. Suggested text: " + FDA_DISCLAIMER
        )
    if not hits and not needs_disclaimer:
        notes.append(
            "No prohibited language detected. Route to human review (and, in "
            "production, an LLM check) before publishing."
        )

    passed = (not hits) and (not needs_disclaimer)
    return ClaimsResult(
        passed=passed,
        prohibited_hits=hits,
        makes_structure_function_claim=makes_sf,
        needs_fda_disclaimer=needs_disclaimer,
        has_fda_disclaimer=has_disclaimer,
        notes=notes,
    )


if __name__ == "__main__":
    # Tiny self-demo.
    samples = [
        "Stillwater Magnesium Glycinate supports a healthy sleep cycle. "
        "This statement has not been evaluated by the Food and Drug "
        "Administration. This product is not intended to diagnose, treat, "
        "cure, or prevent any disease.",
        "Cures insomnia and treats anxiety -- guaranteed!",
        "Supports relaxation before bed.",  # missing disclaimer
    ]
    for s in samples:
        r = screen(s)
        verdict = "PASS (->human review)" if r.passed else "FAIL"
        print(f"[{verdict}] hits={r.prohibited_hits} "
              f"needs_disclaimer={r.needs_fda_disclaimer}")
