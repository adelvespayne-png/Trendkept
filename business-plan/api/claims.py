"""Claims-compliance gate (see ../06-ai-automation-stack.md).

A dependency-free, deterministic first-pass screen for prohibited marketing
language across the two regulatory regimes this store sells under:

  * SUPPLEMENTS / VITAMINS (FDA dietary-supplement rules, DSHEA): may make
    "structure/function" claims WITH the FDA disclaimer; may NOT make disease
    claims (treat/cure/prevent/diagnose).
  * SKINCARE / COSMETICS (FDA cosmetics rules, MoCRA): may make APPEARANCE /
    beauty claims; may NOT make DRUG claims (treat/heal/repair a condition,
    antibacterial, SPF/sunscreen, "treats acne/eczema", etc.). A cosmetic that
    makes a drug claim becomes an unapproved OTC drug.

In production this sits IN FRONT of an LLM check and, crucially, IN FRONT OF A
HUMAN REVIEWER -- it NEVER auto-approves copy. Its job is to catch the obvious,
business-ending claims cheaply so humans focus on judgement calls.

No third-party dependencies; importable by the API server or run standalone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Supplement regime -------------------------------------------------------
# Disease/drug language that turns a "dietary supplement" into an unapproved
# drug in the eyes of the FDA (non-exhaustive; counsel would expand this).
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
# present on a SUPPLEMENT, the copy MUST also carry the FDA disclaimer.
STRUCTURE_FUNCTION_HINTS: tuple[str, ...] = (
    "supports", "support", "helps maintain", "promotes", "helps support",
    "maintains healthy", "for healthy", "helps you", "aids", "contributes to",
)

FDA_DISCLAIMER = (
    "This statement has not been evaluated by the Food and Drug "
    "Administration. This product is not intended to diagnose, treat, cure, "
    "or prevent any disease."
)

# --- Cosmetic / skincare regime ----------------------------------------------
# DRUG claims that make a cosmetic an unapproved drug. Hard fail.
COSMETIC_PROHIBITED: tuple[str, ...] = (
    "treat", "treats", "treating", "treatment",
    "cure", "cures", "heal", "heals", "healing",
    "repair", "repairs", "rebuild", "rebuilds", "regenerate", "regenerates",
    "antibacterial", "antibiotic", "antifungal", "antimicrobial",
    "anti-inflammatory", "antiseptic", "disinfect",
    "acne", "eczema", "psoriasis", "rosacea", "dermatitis",
    "sunscreen", "spf", "uv protection", "protects against uv",
    "blocks uv", "sunburn",
    "stimulates collagen", "boosts collagen production",
    "penetrates", "alters", "wound", "rash", "infection",
    "fda approved", "fda-approved", "clinically proven to cure",
    "botox", "filler alternative", "miracle",
)

# Borderline STRUCTURAL words that are acceptable ONLY when framed as
# appearance ("reduces the APPEARANCE of wrinkles", "for firmer-LOOKING skin").
# If present without an appearance softener, flag for rework.
COSMETIC_CAUTION: tuple[str, ...] = (
    "wrinkle", "wrinkles", "fine lines", "anti-aging", "anti aging",
    "firms", "firming", "lifts", "tightens", "plumps", "collagen",
    "cellular", "renew", "renews",
)
APPEARANCE_SOFTENERS: tuple[str, ...] = (
    "appearance", "look", "looks", "looking", "visibly", "visible",
    "the feel of", "feels", "feeling", "radiant-looking",
)
# Beauty claims a cosmetic MAY make (informational; not required).
COSMETIC_ALLOWED_HINTS: tuple[str, ...] = (
    "hydrates", "hydrating", "moisturizes", "moisturises", "moisturizing",
    "smooths", "smoothing", "softens", "softening", "cleanses",
    "nourishes", "soothes the look", "brightens the look", "glow", "radiant",
)


@dataclass
class ClaimsResult:
    passed: bool
    regime: str = "supplement"
    prohibited_hits: list[str] = field(default_factory=list)
    caution_hits: list[str] = field(default_factory=list)
    makes_structure_function_claim: bool = False
    needs_fda_disclaimer: bool = False
    has_fda_disclaimer: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "regime": self.regime,
            "prohibited_hits": self.prohibited_hits,
            "caution_hits": self.caution_hits,
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


def _screen_supplement(text: str) -> ClaimsResult:
    has_disclaimer = "not intended to diagnose" in text.lower()
    # The disclaimer itself legally contains "diagnose, treat, cure, or prevent
    # any disease" -- strip it before scanning so we don't flag required text.
    scan = re.sub(re.escape(FDA_DISCLAIMER), " ", text, flags=re.IGNORECASE)

    hits = [t for t in PROHIBITED_TERMS if _contains_word(scan, t)]
    makes_sf = any(_contains_word(scan, h) for h in STRUCTURE_FUNCTION_HINTS)
    needs_disclaimer = makes_sf and not has_disclaimer

    notes: list[str] = []
    if hits:
        notes.append(
            "Disease/drug language detected. This makes a supplement an "
            "unapproved drug. Rewrite using structure/function language."
        )
    if needs_disclaimer:
        notes.append("Structure/function claim is missing the FDA disclaimer. "
                     "Add: " + FDA_DISCLAIMER)
    if not hits and not needs_disclaimer:
        notes.append("No prohibited language detected. Route to human review.")

    return ClaimsResult(
        passed=(not hits) and (not needs_disclaimer),
        regime="supplement",
        prohibited_hits=hits,
        makes_structure_function_claim=makes_sf,
        needs_fda_disclaimer=needs_disclaimer,
        has_fda_disclaimer=has_disclaimer,
        notes=notes,
    )


def _screen_cosmetic(text: str) -> ClaimsResult:
    lower = text.lower()
    hits = [t for t in COSMETIC_PROHIBITED if _contains_word(text, t)]

    has_softener = any(s in lower for s in APPEARANCE_SOFTENERS)
    caution = [t for t in COSMETIC_CAUTION if _contains_word(text, t)]
    # Caution words are only a problem if not framed as appearance.
    caution_problem = caution and not has_softener

    notes: list[str] = []
    if hits:
        notes.append(
            "Drug claim detected on a cosmetic. This makes it an unapproved "
            "OTC drug (e.g. 'treats', 'antibacterial', 'SPF', 'acne'). "
            "Reframe as an appearance/beauty claim or drop it."
        )
    if caution_problem:
        notes.append(
            "Structural claim used without appearance framing "
            f"({', '.join(caution)}). Reframe as 'reduces the APPEARANCE of...' "
            "/ 'for firmer-LOOKING skin', or it reads as a drug claim."
        )
    if not hits and not caution_problem:
        notes.append("No prohibited cosmetic-drug language detected. Route to "
                     "human review. (Cosmetics need no FDA supplement disclaimer.)")

    return ClaimsResult(
        passed=(not hits) and (not caution_problem),
        regime="cosmetic",
        prohibited_hits=hits,
        caution_hits=caution,
        # Cosmetics do not use the supplement structure/function disclaimer.
        makes_structure_function_claim=False,
        needs_fda_disclaimer=False,
        has_fda_disclaimer=False,
        notes=notes,
    )


def screen(copy: str, product_type: str = "supplement") -> ClaimsResult:
    """Screen marketing copy. ``product_type`` is 'supplement'/'vitamin' or
    'cosmetic'/'skincare'. Even on PASS, a human must review before publishing.
    """
    text = copy or ""
    pt = (product_type or "supplement").lower()
    if pt in ("cosmetic", "skincare", "cosmetics", "beauty"):
        return _screen_cosmetic(text)
    return _screen_supplement(text)


if __name__ == "__main__":
    samples = [
        ("supplement",
         "Stillwater Magnesium Glycinate supports a healthy sleep cycle. " +
         FDA_DISCLAIMER),
        ("supplement", "Cures insomnia and treats anxiety -- guaranteed!"),
        ("supplement", "Supports relaxation before bed."),  # missing disclaimer
        ("cosmetic", "Hydrates and smooths the look of skin for a radiant glow."),
        ("cosmetic", "Treats acne and repairs the skin barrier. Antibacterial."),
        ("cosmetic", "Reduces wrinkles."),  # structural, no appearance framing
        ("cosmetic", "Reduces the appearance of fine lines."),  # OK
    ]
    for pt, s in samples:
        r = screen(s, pt)
        verdict = "PASS (->human review)" if r.passed else "FAIL"
        print(f"[{pt:10}] [{verdict}] hits={r.prohibited_hits} "
              f"caution={r.caution_hits} needs_disclaimer={r.needs_fda_disclaimer}")
