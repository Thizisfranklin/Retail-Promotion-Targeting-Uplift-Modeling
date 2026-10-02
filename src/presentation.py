"""Small, testable business-language interpretations of saved analysis tables.

This layer never substitutes model predictions for experimental outcomes.
"""


def campaign_evidence(low: float, high: float) -> str:
    """Interpret one *unadjusted* randomized-arm interval relative to zero."""
    if low > 0:
        return "Evidence of an increase relative to no email"
    if high < 0:
        return "Evidence of a decrease relative to no email"
    return "Effect uncertain: interval includes no change"


def targeting_evidence(low: float, high: float) -> str:
    """Interpret bootstrap AUUC-gap interval on held-out observations."""
    if low > 0:
        return "Estimated model advantage in this held-out test"
    if high < 0:
        return "Estimated random-targeting advantage in this held-out test"
    return "No clear model advantage over random targeting"


def targeting_budget_evidence(low: float, high: float) -> str:
    if low > 0:
        return "Higher estimated incremental conversions than random targeting"
    if high < 0:
        return "Lower estimated incremental conversions than random targeting"
    return "No clear difference from random targeting at this budget"
