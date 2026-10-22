"""Approximate tax effects of local changes, as instructed by the packet readme.

effect = delta x return_versions[base].tax_effect_rates[category] (federal and California, per dollar).
Credits and payments change tax or balance due 1:1. These are estimates: the engine is not rerun, and large changes
can cross thresholds (SALT cap, phase-outs) that the per-dollar rate does not capture.

Effects are expressed as the estimated change in balance due (positive = the household owes more).
"""

from decimal import ROUND_HALF_UP, Decimal

RATE_CATEGORIES = [
    "wages", "interest", "schc_profit", "stcg", "ltcg", "ordinary_income", "adjustment", "salt", "itemized",
    "ca_source_income",
]
DIRECT_CATEGORIES = {
    "federal_credit": "Federal credit: changes federal tax 1:1",
    "california_credit": "California credit: changes California tax 1:1",
    "federal_payment": "Federal payment: changes federal balance due 1:1",
    "california_payment": "California payment: changes California balance due 1:1",
    "none": "No direct tax effect (informational, identity or classification change)",
}
CATEGORIES = RATE_CATEGORIES + list(DIRECT_CATEGORIES)


def _q(x: float | Decimal) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def estimate(rates: dict, category: str, delta: float | Decimal) -> dict:
    d = float(delta)
    if category in RATE_CATEGORIES:
        r = rates.get(category) or {}
        fed_rate, ca_rate = r.get("federal_per_dollar", 0.0), r.get("california_per_dollar", 0.0)
        return {
            "fed_effect": _q(d * fed_rate), "ca_effect": _q(d * ca_rate), "fed_tax": _q(d * fed_rate),
            "ca_tax": _q(d * ca_rate), "fed_payments": _q(0), "ca_payments": _q(0),
            "note": f"Estimate: {d:,.2f} x {category} rate (federal {fed_rate}, California {ca_rate}) per dollar.",
        }
    zero = _q(0)
    if category == "federal_credit":
        return {"fed_effect": _q(-d), "ca_effect": zero, "fed_tax": _q(-d), "ca_tax": zero, "fed_payments": zero,
                "ca_payments": zero, "note": DIRECT_CATEGORIES[category]}
    if category == "california_credit":
        return {"fed_effect": zero, "ca_effect": _q(-d), "fed_tax": zero, "ca_tax": _q(-d), "fed_payments": zero,
                "ca_payments": zero, "note": DIRECT_CATEGORIES[category]}
    if category == "federal_payment":
        return {"fed_effect": _q(-d), "ca_effect": zero, "fed_tax": zero, "ca_tax": zero, "fed_payments": _q(d),
                "ca_payments": zero, "note": DIRECT_CATEGORIES[category]}
    if category == "california_payment":
        return {"fed_effect": zero, "ca_effect": _q(-d), "fed_tax": zero, "ca_tax": zero, "fed_payments": zero,
                "ca_payments": _q(d), "note": DIRECT_CATEGORIES[category]}
    return {"fed_effect": zero, "ca_effect": zero, "fed_tax": zero, "ca_tax": zero, "fed_payments": zero,
            "ca_payments": zero, "note": DIRECT_CATEGORIES["none"]}


def guess_category(line_key: str, jurisdiction: str) -> str:
    """Default category for a line; the user can override it when proposing an adjustment."""
    k = line_key
    if k.startswith(("SchB.1", "SchB.2", "SchB.4", "F1040.2b", "SchB.5", "F1040.3")):
        return "interest"
    if k.startswith(("F1040.1", "SchCA540NR.1.")):
        return "ca_source_income" if k.endswith(".E") else "wages"
    if k.startswith(("SchC.", "SchSE.")):
        return "schc_profit"
    if k.startswith(("F8949.A", "F8949.B", "F8949.H", "SchD.1", "SchD.2", "SchD.3", "SchD.6", "SchD.7")):
        return "stcg"
    if k.startswith(("F8949.", "SchD.", "F4797.")):
        return "ltcg"
    if k.startswith("Sch1.1") or k.startswith("Sch1.2"):
        return "adjustment"
    if k.startswith("SchA.5"):
        return "salt"
    if k.startswith(("SchA.", "F8283.")):
        return "itemized"
    if k.startswith(("F1040.25", "F1040.26", "Sch3.10", "Sch3.11")):
        return "federal_payment"
    if k.startswith(("F540NR.71", "F540NR.72", "F540NR.73")):
        return "california_payment"
    if k.startswith(("F8812", "F1040.19", "F2441.31", "F8863", "Sch3.1")):
        return "federal_credit"
    if k.startswith("SchCA540NR.") and k.endswith(".E"):
        return "ca_source_income"
    if k.startswith(("SchE.", "F8582", "Sch1.5")):
        return "ordinary_income"
    return "ordinary_income" if jurisdiction == "federal" else "ca_source_income"
