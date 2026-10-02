"""Business-language results should follow the *current* stored estimates."""
from src.presentation import campaign_evidence, targeting_evidence, targeting_budget_evidence


def test_campaign_ci_excludes_zero_only_for_evidence():
    assert "increase" in campaign_evidence(.005, .009)
    assert "decrease" in campaign_evidence(-.015, -.002)
    assert "uncertain" in campaign_evidence(-.002, .009)
    assert "uncertain" in campaign_evidence(0, .009)


def test_targeting_ci_spanning_zero_is_not_a_win():
    assert "No clear" in targeting_evidence(-1.73, .63)
    assert "No clear" in targeting_evidence(-.33, 2.05)
    assert "advantage" in targeting_evidence(.05, .70)
    assert "random-targeting" in targeting_evidence(-.9, -.02)


def test_budget_explanation_uses_zero_inclusion():
    assert "No clear" in targeting_budget_evidence(-2.96, 1.0)
    assert "No clear" in targeting_budget_evidence(-1.03, 2.29)
    assert "Higher" in targeting_budget_evidence(.2, 1)
    assert "Lower" in targeting_budget_evidence(-2, -.01)
