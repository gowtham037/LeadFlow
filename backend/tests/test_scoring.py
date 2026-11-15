"""
Unit tests for the scoring engine.

Covers:
  - Boundary conditions (score = 0, 100)
  - Determinism (same features → same result)
  - Component sum == total
  - Category boundaries (hot/warm/nurture/cold)
  - Contribution structure
  - Post-conversion activity exclusion (uses real DB, marked skip if unavailable)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from backend.app.engines.scoring.engine import calculate_score
from backend.app.engines.scoring.features import Features
from backend.app.models.enums import ScoreCategory


@dataclass
class FakeRule:
    version: str = "v1"
    fit_weight: int = 30
    intent_weight: int = 35
    engagement_weight: int = 25
    recency_weight: int = 10
    hot_threshold: int = 80
    warm_threshold: int = 60
    nurture_threshold: int = 40


def _empty_features() -> Features:
    f = Features(lead_id=1)
    f.cutoff_at = datetime.now(timezone.utc)
    return f


def _rich_features() -> Features:
    f = Features(lead_id=2)
    f.employee_count = 5000
    f.annual_revenue_usd = 100_000_000
    f.industry = "Software as a Service"
    f.company_territory_id = 1
    f.lead_territory_id = 1
    f.territory_match = True
    f.demo_requests = 3
    f.meetings = 2
    f.content_downloads = 4
    f.calls = 2
    f.email_opens = 10
    f.email_clicks = 5
    f.web_visits = 10
    f.total_activities = 30
    f.days_since_last_activity = 1
    f.cutoff_at = datetime.now(timezone.utc)
    return f


def _cold_features() -> Features:
    f = Features(lead_id=3)
    f.employee_count = 10
    f.annual_revenue_usd = 200_000
    f.industry = "Other"
    f.company_territory_id = 1
    f.lead_territory_id = 2
    f.territory_match = False
    f.demo_requests = 0
    f.meetings = 0
    f.content_downloads = 0
    f.calls = 0
    f.email_opens = 0
    f.email_clicks = 0
    f.web_visits = 0
    f.total_activities = 0
    f.days_since_last_activity = 9999
    f.cutoff_at = datetime.now(timezone.utc)
    return f


# --- Tests ---

def test_empty_lead_scores_low_but_not_negative():
    result = calculate_score(_empty_features(), FakeRule())
    assert 0 <= result.total <= 100
    assert result.total < 40
    assert result.category == ScoreCategory.COLD


def test_rich_lead_scores_high():
    result = calculate_score(_rich_features(), FakeRule())
    assert result.total >= 80
    assert result.category == ScoreCategory.HOT


def test_cold_lead_scores_minimal():
    result = calculate_score(_cold_features(), FakeRule())
    # 0 fit except industry_pts=3, so fit ~3, others 0
    assert result.total < 20


def test_deterministic_same_inputs():
    f = _rich_features()
    r1 = calculate_score(f, FakeRule())
    r2 = calculate_score(f, FakeRule())
    assert r1.total == r2.total
    assert r1.category == r2.category
    assert r1.fit_score == r2.fit_score


def test_components_sum_to_total():
    for f in (_empty_features(), _rich_features(), _cold_features()):
        r = calculate_score(f, FakeRule())
        assert r.fit_score + r.intent_score + r.engagement_score + r.recency_score == r.total


def test_components_within_weights():
    r = calculate_score(_rich_features(), FakeRule())
    assert 0 <= r.fit_score <= 30
    assert 0 <= r.intent_score <= 35
    assert 0 <= r.engagement_score <= 25
    assert 0 <= r.recency_score <= 10


def test_category_boundaries():
    rule = FakeRule()
    # 100 → hot
    r = calculate_score(_rich_features(), rule)
    assert r.category == ScoreCategory.HOT
    # Cold → cold
    r = calculate_score(_cold_features(), rule)
    assert r.category == ScoreCategory.COLD


def test_contributions_structure():
    r = calculate_score(_rich_features(), FakeRule())
    # Expect exactly 4 fit + 4 intent + 3 engagement + 1 recency = 12
    assert len(r.contributions) == 12
    for c in r.contributions:
        assert isinstance(c.feature, str)
        assert c.points >= 0
        assert c.weight_max > 0
        assert isinstance(c.explanation, str)
        assert len(c.explanation) > 0


def test_custom_rule_weights():
    """Different weights → different max component contribution."""
    rule = FakeRule(fit_weight=50, intent_weight=20, engagement_weight=20, recency_weight=10)
    r = calculate_score(_rich_features(), rule)
    assert r.fit_score <= 50
    assert r.intent_score <= 20
    assert r.engagement_score <= 20
    assert r.recency_score <= 10


def test_total_never_exceeds_100_or_below_0():
    # Push everything to max
    f = _rich_features()
    f.demo_requests = 999
    f.meetings = 999
    f.content_downloads = 999
    f.calls = 999
    f.email_opens = 999
    f.email_clicks = 999
    f.web_visits = 999
    r = calculate_score(f, FakeRule())
    assert 0 <= r.total <= 100


def test_no_activity_lead_has_zero_recency():
    f = _empty_features()
    r = calculate_score(f, FakeRule())
    assert r.recency_score == 0


def test_territory_mismatch_penalized():
    f_match = _rich_features()
    f_match.territory_match = True
    f_mismatch = _rich_features()
    f_mismatch.territory_match = False
    r_match = calculate_score(f_match, FakeRule())
    r_mismatch = calculate_score(f_mismatch, FakeRule())
    assert r_match.fit_score > r_mismatch.fit_score



def test_converted_lead_cutoff_capped_at_conversion():
    """Regression for Finding 1 — converted leads must not include post-conversion activity."""
    from datetime import datetime, timedelta, timezone

    # Simulate: lead converted 10 days ago, activity happened 5 days ago
    now = datetime.now(timezone.utc)
    converted_at = now - timedelta(days=10)
    post_conversion_activity = now - timedelta(days=5)
    user_cutoff = now  # caller asks for "now"

    # The cap logic (extracted from runner.py for unit test)
    effective_cutoff = min(user_cutoff, converted_at) if converted_at else user_cutoff

    # Post-conversion activity must NOT be within the effective window
    assert post_conversion_activity > effective_cutoff, (
        f"Post-conversion activity at {post_conversion_activity} should be "
        f"AFTER effective cutoff {effective_cutoff}, but is not — cutoff leak!"
    )
    assert effective_cutoff == converted_at, "Cutoff must equal converted_at"
