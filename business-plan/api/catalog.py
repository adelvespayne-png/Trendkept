"""Reference product catalog for the Stillwater health & beauty brand.

Three categories -- Supplements, Vitamins, and Skincare -- but only a small
number of hero SKUs per category, matching the launch strategy in
../03-product-and-sourcing.md (start focused, prove economics, then go wide).

Each product carries a ``product_type`` that drives which compliance regime
applies (see ../02-legal-compliance.md and claims.py):
  * "supplement" / "vitamin" -> structure/function claims + FDA disclaimer
  * "skincare"               -> cosmetic appearance claims, NO drug claims,
                                NO supplement disclaimer

All copy below is written in compliant language. Prices are illustrative.
In a real store this lives in the e-commerce platform; here it is static data
so the demo API is self-contained.
"""
from __future__ import annotations

from claims import FDA_DISCLAIMER

# Category metadata for the storefront.
CATEGORIES = [
    {"id": "supplements", "name": "Supplements",
     "blurb": "Single-ingredient, third-party tested supplements."},
    {"id": "vitamins", "name": "Vitamins",
     "blurb": "Foundational daily vitamins, honestly dosed."},
    {"id": "skincare", "name": "Skincare",
     "blurb": "Simple, effective skincare. Cosmetic claims only -- no hype."},
]


def _opts(base_sku: str, onetime: float, sub: float, interval: int = 30):
    """Build a standard one-time + subscribe-and-save option pair.

    Subscription is priced below one-off to drive sign-up -- the profit engine
    (see ../04-unit-economics.md).
    """
    return [
        {"sku": f"{base_sku}-onetime", "label": "One-time purchase",
         "price": onetime, "subscription": False},
        {"sku": f"{base_sku}-sub", "label": f"Subscribe & Save (every {interval} days)",
         "price": sub, "subscription": True, "interval_days": interval},
    ]


PRODUCTS = [
    # --- Supplements ---------------------------------------------------------
    {
        "id": "mag-glycinate-60",
        "category": "supplements",
        "product_type": "supplement",
        "name": "Magnesium Glycinate",
        "subtitle": "Highly absorbable magnesium for evening wind-down",
        "claim": "Supports relaxation and a healthy sleep cycle.",
        "ingredients": ["Magnesium (as magnesium glycinate) 200mg",
                        "Other ingredients: vegetable capsule"],
        "third_party_tested": True, "coa_published": True,
        "options": _opts("mag-glycinate-60", 35.00, 29.75),
        "fda_disclaimer": FDA_DISCLAIMER,
    },
    {
        "id": "creatine-monohydrate",
        "category": "supplements",
        "product_type": "supplement",
        "name": "Creatine Monohydrate",
        "subtitle": "Micronised creatine for active routines",
        "claim": "Supports muscle strength and exercise performance.",
        "ingredients": ["Creatine monohydrate 5g per serving"],
        "third_party_tested": True, "coa_published": True,
        "options": _opts("creatine-monohydrate", 29.00, 24.65),
        "fda_disclaimer": FDA_DISCLAIMER,
    },
    # --- Vitamins ------------------------------------------------------------
    {
        "id": "vitamin-d3-k2",
        "category": "vitamins",
        "product_type": "vitamin",
        "name": "Vitamin D3 + K2",
        "subtitle": "Daily D3 with K2 for synergy",
        "claim": "Supports immune health and the maintenance of normal bones.",
        "ingredients": ["Vitamin D3 (cholecalciferol) 2000 IU", "Vitamin K2 (MK-7) 100mcg"],
        "third_party_tested": True, "coa_published": True,
        "options": _opts("vitamin-d3-k2", 22.00, 18.70),
        "fda_disclaimer": FDA_DISCLAIMER,
    },
    {
        "id": "vitamin-c-1000",
        "category": "vitamins",
        "product_type": "vitamin",
        "name": "Vitamin C 1000mg",
        "subtitle": "Buffered vitamin C for daily intake",
        "claim": "Supports normal immune function and collagen formation.",
        "ingredients": ["Vitamin C (as sodium ascorbate) 1000mg"],
        "third_party_tested": True, "coa_published": True,
        "options": _opts("vitamin-c-1000", 18.00, 15.30),
        "fda_disclaimer": FDA_DISCLAIMER,
    },
    # --- Skincare (cosmetics: appearance claims only, NO disclaimer) ---------
    {
        "id": "ha-hydrating-serum",
        "category": "skincare",
        "product_type": "skincare",
        "name": "Hydrating Serum",
        "subtitle": "Hyaluronic acid serum",
        "claim": "Hydrates and smooths the look of skin for a radiant glow.",
        "ingredients": ["Hyaluronic acid", "Glycerin", "Panthenol"],
        "third_party_tested": True, "coa_published": False,
        "options": _opts("ha-hydrating-serum", 32.00, 27.20),
        "cosmetic_note": "Cosmetic product. For external use only.",
    },
    {
        "id": "vitc-brightening-serum",
        "category": "skincare",
        "product_type": "skincare",
        "name": "Vitamin C Brightening Serum",
        "subtitle": "Stabilised vitamin C serum",
        "claim": "Helps improve the appearance of dullness for brighter-looking skin.",
        "ingredients": ["Vitamin C (sodium ascorbyl phosphate)", "Vitamin E", "Ferulic acid"],
        "third_party_tested": True, "coa_published": False,
        "options": _opts("vitc-brightening-serum", 38.00, 32.30),
        "cosmetic_note": "Cosmetic product. For external use only.",
    },
    {
        "id": "daily-moisturizer",
        "category": "skincare",
        "product_type": "skincare",
        "name": "Daily Moisturizer",
        "subtitle": "Lightweight everyday moisturiser",
        "claim": "Moisturizes for softer, smoother-feeling skin.",
        "ingredients": ["Glycerin", "Squalane", "Ceramides", "Niacinamide"],
        "third_party_tested": True, "coa_published": False,
        "options": _opts("daily-moisturizer", 28.00, 23.80),
        "cosmetic_note": "Cosmetic product. For external use only.",
    },
]


def list_categories() -> list[dict]:
    return CATEGORIES


def list_products(category: str | None = None) -> list[dict]:
    if category:
        return [p for p in PRODUCTS if p["category"] == category]
    return PRODUCTS


def find_option(sku: str) -> dict | None:
    for product in PRODUCTS:
        for option in product["options"]:
            if option["sku"] == sku:
                return {"product": product, "option": option}
    return None
