"""Reference product catalog for the Stillwater brand.

Single hero SKU + a subscribe-and-save option, matching the launch strategy in
../03-product-and-sourcing.md (one niche, few SKUs). Prices are illustrative.
All copy uses compliant structure/function language and carries the FDA
disclaimer (see ../02-legal-compliance.md). In a real store this would live in
the e-commerce platform; here it's static data so the demo API is self-contained.
"""
from __future__ import annotations

from claims import FDA_DISCLAIMER

# One hero product, two purchase options (one-off and subscription). The
# subscription is the profit engine (see ../04-unit-economics.md), so it is
# priced below the one-off to drive sign-up.
PRODUCTS = [
    {
        "id": "mag-glycinate-60",
        "name": "Stillwater Magnesium Glycinate",
        "subtitle": "Highly absorbable magnesium for evening wind-down",
        "servings": 60,
        "claim": "Supports relaxation and a healthy sleep cycle.",
        "ingredients": [
            "Magnesium (as magnesium glycinate) 200mg",
            "Other ingredients: vegetable capsule",
        ],
        "third_party_tested": True,
        "coa_published": True,
        "options": [
            {
                "sku": "mag-glycinate-60-onetime",
                "label": "One-time purchase",
                "price": 35.00,
                "subscription": False,
            },
            {
                "sku": "mag-glycinate-60-sub",
                "label": "Subscribe & Save (every 30 days)",
                "price": 29.75,  # ~15% off; drives the subscription engine
                "subscription": True,
                "interval_days": 30,
            },
        ],
        "fda_disclaimer": FDA_DISCLAIMER,
    },
]


def list_products() -> list[dict]:
    return PRODUCTS


def find_option(sku: str) -> dict | None:
    for product in PRODUCTS:
        for option in product["options"]:
            if option["sku"] == sku:
                return {"product": product, "option": option}
    return None
